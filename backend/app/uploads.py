from fastapi import HTTPException, UploadFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _image_ext(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


def read_validated_image(file: UploadFile) -> tuple[bytes, str]:
    """Reads an uploaded image with a size cap, checking the file's real bytes
    (not the client-supplied content_type header) before accepting it.
    Returns the bytes and the extension matching them — never the client's filename
    extension, or a JPEG-headed "x.html" would be served as HTML from /uploads (stored XSS)."""
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Envie uma imagem de até 5 MB (JPEG, PNG, WEBP ou GIF).")
    ext = _image_ext(content[:12])
    if not ext:
        raise HTTPException(400, "Envie uma imagem válida (JPEG, PNG, WEBP ou GIF).")
    return content, ext
