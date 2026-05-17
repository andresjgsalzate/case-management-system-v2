"""Replaces the Sub-spec 05 ``attach_artifact`` stub.

Handles n8n callbacks that carry Velociraptor hunt results back to the
CMS. Responsibilities:

- Match the inbound payload to a CMS ``ForensicHuntModel`` row (via
  ``velo_hunt_id`` scoped by tenant).
- Persist one ``ForensicHuntResultModel`` row per host result, hashed
  for chain of custody.
- Download any blob attachments, verify the claimed SHA-256, persist as
  a ``CaseAttachmentModel`` joined through ``ForensicHuntAttachmentModel``.
- Finalize the hunt: aggregate ``result_summary``, compute the overall
  ``result_hash`` over the summary + sorted attachment hashes, mark the
  row ``completed``.

The handler is idempotent on already-completed hunts (n8n retry safety).
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError, NotFoundError, ValidationError,
)
from backend.src.modules.attachments.application.storage import (
    generate_stored_filename, save_file,
)
from backend.src.modules.attachments.infrastructure.models import (
    CaseAttachmentModel,
)
from backend.src.modules.forensic.application.hash_utils import (
    sha256_canonical,
)
from backend.src.modules.forensic.infrastructure.models import (
    ForensicHuntAttachmentModel, ForensicHuntModel, ForensicHuntResultModel,
)

logger = logging.getLogger(__name__)


class ForensicCallbackHandler:
    def __init__(
        self,
        db: AsyncSession,
        *,
        system_user_id: str | None = None,
        upload_dir: str = "uploads",
    ):
        self.db = db
        self.system_user_id = system_user_id
        self.upload_dir = upload_dir

    async def handle_attach_artifact(
        self, *, case, run, payload: dict
    ) -> dict:
        velo_hunt_id = payload.get("velo_hunt_id")
        if not velo_hunt_id:
            raise ValidationError("velo_hunt_id required in payload")

        hunt = await self._find_hunt_by_velo_id(
            velo_hunt_id, tenant_id=case.tenant_id
        )
        if not hunt:
            raise NotFoundError(
                f"Hunt with velo_hunt_id={velo_hunt_id} not found in CMS"
            )

        if hunt.status not in ("running", "starting"):
            return {
                "ok": True, "noop": True,
                "hunt_status": hunt.status, "hunt_id": hunt.id,
            }

        for cr in payload.get("client_results", []):
            await self._persist_client_result(hunt, cr, run, case)

        await self._finalize_hunt_results(hunt)
        hunt.status = "completed"
        hunt.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        return {
            "ok": True, "hunt_id": hunt.id,
            "result_hash": hunt.result_hash,
        }

    async def _find_hunt_by_velo_id(
        self, velo_hunt_id: str, *, tenant_id: str
    ) -> ForensicHuntModel | None:
        result = await self.db.execute(
            select(ForensicHuntModel).where(
                ForensicHuntModel.velo_hunt_id == velo_hunt_id,
                ForensicHuntModel.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _persist_client_result(
        self, hunt: ForensicHuntModel, client_result: dict, run, case
    ) -> None:
        row = ForensicHuntResultModel(
            hunt_id=hunt.id,
            velo_client_id=client_result["client_id"],
            hostname=client_result.get("hostname"),
            os=client_result.get("os"),
            output_summary={
                "row_count": client_result.get("row_count", 0),
                "sample_rows": client_result.get("sample_rows", []),
            },
            output_total_rows=client_result.get("row_count", 0),
            status="completed",
        )
        velo_completed_at = client_result.get("velo_completed_at")
        if velo_completed_at:
            try:
                row.velo_completed_at = datetime.fromisoformat(
                    velo_completed_at.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        row.row_hash = sha256_canonical(row.output_summary)
        self.db.add(row)
        await self.db.flush()

        for blob in client_result.get("blob_uploads", []):
            await self._download_and_attach_blob(hunt, row, blob, case, run)
            row.attachments_count += 1

    async def _download_and_attach_blob(
        self,
        hunt: ForensicHuntModel,
        row: ForensicHuntResultModel,
        blob: dict,
        case,
        run,
    ) -> None:
        blob_url = blob["url"]
        expected_sha256 = blob["sha256"]

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.get(
                blob_url,
                headers=self._velo_auth_headers(hunt.velo_org_id),
            )
            response.raise_for_status()
            content = response.content

        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != expected_sha256:
            raise BusinessRuleError(
                f"Blob hash mismatch: expected={expected_sha256}, "
                f"actual={actual_hash}. Possible tampering or corruption."
            )

        original_filename = blob["name"]
        stored_name = generate_stored_filename(original_filename)
        file_path = await save_file(
            content, stored_name, case.id, self.upload_dir
        )

        attachment = CaseAttachmentModel(
            id=str(uuid.uuid4()),
            case_id=case.id,
            user_id=self.system_user_id or "velociraptor_via_n8n",
            tenant_id=case.tenant_id,
            original_filename=original_filename,
            stored_filename=stored_name,
            file_path=file_path,
            mime_type=self._guess_mime_type(original_filename),
            file_size=len(content),
        )
        self.db.add(attachment)
        await self.db.flush()

        pivot = ForensicHuntAttachmentModel(
            hunt_id=hunt.id,
            hunt_result_id=row.id,
            attachment_id=attachment.id,
            artifact_name=hunt.artifact_name,
            sha256_hash=actual_hash,
            is_immutable=True,
        )
        self.db.add(pivot)

    async def _finalize_hunt_results(self, hunt: ForensicHuntModel) -> None:
        result = await self.db.execute(
            select(ForensicHuntResultModel).where(
                ForensicHuntResultModel.hunt_id == hunt.id
            )
        )
        rows = list(result.scalars().all())

        per_client = {
            r.velo_client_id: {
                "status": r.status, "row_count": r.output_total_rows,
            }
            for r in rows
        }
        total_rows = sum(r.output_total_rows for r in rows)

        sample: list[dict] = []
        for r in rows:
            if r.output_summary and r.output_summary.get("sample_rows"):
                for sample_row in r.output_summary["sample_rows"][:5]:
                    sample.append(
                        {"client_id": r.velo_client_id, **sample_row}
                    )
            if len(sample) >= 10:
                break

        hunt.result_summary = {
            "total_rows": total_rows,
            "per_client": per_client,
            "sample_rows": sample[:10],
            "client_count": len(rows),
        }

        attachments_result = await self.db.execute(
            select(ForensicHuntAttachmentModel).where(
                ForensicHuntAttachmentModel.hunt_id == hunt.id
            )
        )
        attachment_hashes = sorted(
            a.sha256_hash for a in attachments_result.scalars().all()
        )
        hunt.result_hash = sha256_canonical({
            "summary": hunt.result_summary,
            "attachments": attachment_hashes,
        })

    def _velo_auth_headers(self, org_id: str) -> dict[str, str]:
        from backend.src.core.config import get_settings
        settings = get_settings()
        api_key = getattr(settings, "VELOCIRAPTOR_API_KEY", "") or ""
        return {
            "Authorization": f"Bearer {api_key}",
            "X-Velo-Org-Id": org_id,
        }

    def _guess_mime_type(self, filename: str) -> str:
        guess, _ = mimetypes.guess_type(filename)
        return guess or "application/octet-stream"
