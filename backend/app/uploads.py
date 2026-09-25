from fastapi import HTTPException, UploadFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _looks_like_image(head: bytes) -> bool:
    if head.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if head[:6] in (b"GIF87a", b"GIF89a"):  # GIF
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":  # WEBP
        return True
    return False


def read_validated_image(file: UploadFile) -> bytes:
    """Reads an uploaded image with a size cap, checking the file's real bytes
    (not the client-supplied content_type header) before accepting it."""
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Envie uma imagem de até 5 MB (JPEG, PNG, WEBP ou GIF).")
    if not _looks_like_image(content[:12]):
        raise HTTPException(400, "Envie uma imagem válida (JPEG, PNG, WEBP ou GIF).")
    return content
