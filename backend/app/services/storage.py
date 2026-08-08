import hashlib
import io
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 12_000
MAX_CASE_ATTACHMENTS = 8
MAX_MESSAGE_ATTACHMENTS = 4
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


@dataclass(frozen=True)
class StoredImage:
    storage_key: str
    display_name: str
    media_type: str
    byte_count: int
    sha256: str
    width: int
    height: int
    path: Path


def ensure_storage() -> None:
    for child in ("uploads", "exports"):
        path = settings.DATA_ROOT / child
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".probe-{uuid.uuid4()}"
        probe.write_bytes(b"")
        probe.unlink()


def sanitized_filename(filename: str | None, media_type: str) -> str:
    default = "photo.jpg" if media_type == "image/jpeg" else "photo.png"
    if not filename:
        return default
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name).strip(" .")
    cleaned = cleaned[:170]
    return cleaned or default


async def store_image(upload: UploadFile) -> StoredImage:
    raw = await upload.read(MAX_IMAGE_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded image is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413, detail="Each image must be 8 MiB or smaller"
        )

    try:
        verification_image = Image.open(io.BytesIO(raw))
        verification_image.verify()
        source: Image.Image = Image.open(io.BytesIO(raw))
        source_format = source.format
        source = ImageOps.exif_transpose(source)
        width, height = source.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise HTTPException(
                status_code=422, detail="Image dimensions are too large"
            )
        if width * height > MAX_IMAGE_PIXELS:
            raise HTTPException(
                status_code=422, detail="Image contains too many pixels"
            )
        if source_format not in {"JPEG", "PNG"}:
            raise HTTPException(
                status_code=422, detail="Only JPEG and PNG images are allowed"
            )
        output = io.BytesIO()
        if source_format == "JPEG":
            source.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
            media_type = "image/jpeg"
            extension = "jpg"
        else:
            if source.mode not in {"RGB", "RGBA"}:
                source = source.convert("RGBA")
            source.save(output, format="PNG", optimize=True)
            media_type = "image/png"
            extension = "png"
    except HTTPException:
        raise
    except UnidentifiedImageError, OSError, SyntaxError, ValueError:
        raise HTTPException(status_code=422, detail="Image could not be validated")

    encoded = output.getvalue()
    digest = hashlib.sha256(encoded).hexdigest()
    key = f"{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}.{extension}"
    final_path = settings.DATA_ROOT / "uploads" / key
    final_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="upload-", dir=final_path.parent
    )
    try:
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, final_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise

    return StoredImage(
        storage_key=key,
        display_name=sanitized_filename(upload.filename, media_type),
        media_type=media_type,
        byte_count=len(encoded),
        sha256=digest,
        width=width,
        height=height,
        path=final_path,
    )


def remove_stored_image(image: StoredImage) -> None:
    image.path.unlink(missing_ok=True)


def storage_path(storage_key: str, *, export: bool = False) -> Path:
    root = settings.DATA_ROOT / ("exports" if export else "uploads")
    candidate = (root / storage_key).resolve()
    if root.resolve() not in candidate.parents:
        raise RuntimeError("Invalid storage key")
    return candidate
