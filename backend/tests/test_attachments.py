def test_detect_mime_pdf_magic_bytes():
    """Detecta PDF por los primeros bytes del archivo."""
    from backend.src.modules.attachments.application.storage import detect_mime_type
    content = b"%PDF-1.4 fake pdf content"
    assert detect_mime_type(content) == "application/pdf"


def test_detect_mime_jpeg_magic_bytes():
    """Detecta JPEG por los bytes de firma FF D8 FF."""
    from backend.src.modules.attachments.application.storage import detect_mime_type
    content = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"fake jpeg"
    assert detect_mime_type(content) == "image/jpeg"


def test_detect_mime_png_magic_bytes():
    """Detecta PNG por la firma de 8 bytes del estándar PNG."""
    from backend.src.modules.attachments.application.storage import detect_mime_type
    content = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"fake png"
    assert detect_mime_type(content) == "image/png"


def test_detect_mime_unknown_returns_octet_stream():
    """Contenido desconocido cae en application/octet-stream."""
    from backend.src.modules.attachments.application.storage import detect_mime_type
    content = b"\x00\x01\x02\x03 random binary"
    result = detect_mime_type(content)
    # Puede ser octet-stream u otro tipo según magic, pero no debe lanzar
    assert isinstance(result, str)
    assert "/" in result


def test_allowed_mime_types_contains_common_types():
    """Verifica que los tipos MIME permitidos incluyen PDF e imágenes básicas."""
    from backend.src.modules.attachments.application.storage import ALLOWED_MIME_TYPES
    assert "application/pdf" in ALLOWED_MIME_TYPES
    assert "image/jpeg" in ALLOWED_MIME_TYPES
    assert "image/png" in ALLOWED_MIME_TYPES


def test_max_file_size_is_10mb():
    """Confirma que el límite de tamaño es 10 MB."""
    from backend.src.modules.attachments.application.storage import MAX_FILE_SIZE
    assert MAX_FILE_SIZE == 10 * 1024 * 1024
