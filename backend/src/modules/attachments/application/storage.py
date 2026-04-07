import uuid
from pathlib import Path

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def detect_mime_type(content: bytes) -> str:
    """Detecta MIME real desde los bytes del archivo (no confía en el Content-Type del cliente)."""
    try:
        import magic
        return magic.from_buffer(content, mime=True)
    except Exception:
        # Fallback: detectar por magic bytes básicos
        if content[:4] == b"%PDF":
            return "application/pdf"
        if content[:2] in (b"\xff\xd8", b"\xff\xe0", b"\xff\xe1"):
            return "image/jpeg"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if content[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        return "application/octet-stream"


def generate_stored_filename(original: str) -> str:
    ext = Path(original).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def get_case_upload_dir(base_dir: str, case_id: str) -> Path:
    path = Path(base_dir) / "cases" / str(case_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_file(content: bytes, stored_filename: str, case_id: str, upload_dir: str) -> str:
    dir_path = get_case_upload_dir(upload_dir, case_id)
    file_path = dir_path / stored_filename
    file_path.write_bytes(content)
    return str(file_path)


def delete_file(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()
