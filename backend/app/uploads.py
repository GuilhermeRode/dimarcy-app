import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
# Lists show product photos at most ~96px tall; 480px stays sharp on phone screens (3x)
THUMB_SIZE = 480


def thumb_name(name: str) -> str:
    """Thumbnail file next to a full-size upload: 12_abc.jpg -> 12_abc_thumb.jpg"""
    return Path(name).stem + "_thumb.jpg"


def make_thumb(content: bytes) -> bytes:
    """Small JPEG for lists (a 13 MB catalog photo becomes ~30 KB). Raises on a corrupt image."""
    with Image.open(io.BytesIO(content)) as im:
        im.draft("RGB", (THUMB_SIZE, THUMB_SIZE))  # JPEG: decode at reduced scale, fast and low-memory
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):  # transparent PNG/GIF: white background instead of black
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.getchannel("A"))
            im = bg
        im = im.convert("RGB")
        im.thumbnail((THUMB_SIZE, THUMB_SIZE))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        return out.getvalue()


def backfill_thumbs(folder: Path) -> None:
    """Creates missing thumbnails for photos uploaded before thumbnails existed (runs at startup)."""
    for f in folder.glob("*"):
        if f.stem.endswith("_thumb") or (folder / thumb_name(f.name)).exists():
            continue
        try:
            (folder / thumb_name(f.name)).write_bytes(make_thumb(f.read_bytes()))
        except Exception:  # an unreadable old file must not stop the app from starting
            pass


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
