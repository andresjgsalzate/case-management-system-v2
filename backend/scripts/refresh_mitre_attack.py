"""Download and project the MITRE ATT&CK Enterprise dataset.

Pulls the full STIX bundle from MITRE's CTI repo, filters to
non-revoked / non-deprecated `attack-pattern` objects (techniques +
sub-techniques), and writes a slim JSON (~50-100 KB) the backend
can hold in memory and serve from `/api/v1/mitre/techniques`.

Usage:
    python -m backend.scripts.refresh_mitre_attack

Output: backend/data/mitre/techniques.json

Run quarterly (MITRE's release cadence) or whenever a new TTP needs
to be selectable in the taxonomy editor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx


SOURCE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)

OUTPUT = (
    Path(__file__).resolve().parent.parent / "data" / "mitre" / "techniques.json"
)


def fetch_bundle() -> dict:
    print(f"GET {SOURCE_URL}")
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        response = client.get(SOURCE_URL)
        response.raise_for_status()
    print(f"  {len(response.content) / 1024 / 1024:.1f} MB downloaded")
    return response.json()


def extract_external_id(stix_obj: dict) -> str | None:
    for ref in stix_obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            ext_id = ref.get("external_id")
            if ext_id and ext_id.startswith("T"):
                return ext_id
    return None


def extract_tactics(stix_obj: dict) -> list[str]:
    # kill_chain_phases carry the tactic ("initial-access", "execution"...)
    # for MITRE's kill chain. There can be more than one tactic per technique.
    return sorted(
        {
            phase["phase_name"]
            for phase in stix_obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        }
    )


def project(bundle: dict) -> list[dict]:
    out: list[dict] = []
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        ext_id = extract_external_id(obj)
        if not ext_id:
            continue

        out.append(
            {
                "id": ext_id,
                "name": obj.get("name", ""),
                "tactics": extract_tactics(obj),
                "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
            }
        )

    # Stable order: parent before sub, then ID lexicographic
    out.sort(key=lambda r: (r["id"].split(".")[0], r["id"]))
    return out


def main() -> int:
    bundle = fetch_bundle()
    techniques = project(bundle)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(techniques, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"Wrote {len(techniques)} techniques "
        f"({OUTPUT.stat().st_size / 1024:.1f} KB) to {OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
