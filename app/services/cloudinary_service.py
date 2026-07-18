import logging
import os
import re
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# Cloudinary asset folders — one per route, mirroring the old
# uploads/blog and uploads/courses local subdirectory layout so the two
# kinds of media stay organized in the Cloudinary media library too.
BLOG_FOLDER = "gordon-it/blog"
COURSE_FOLDER = "gordon-it/courses"

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")

# Configured once, at import time — the same pattern payments_router.py
# already uses for Stripe (`stripe.api_key = os.getenv(...)` at module
# scope). By the time this module is imported (transitively, via the
# routers, when app/main.py starts up) the process environment is already
# populated, whether that's a local .env or Coolify's injected env vars.
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    secure=True,
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def upload_image(upload: UploadFile, folder: str) -> str:
    """
    Validate an uploaded image and stream it to Cloudinary.

    Returns the HTTPS secure_url to store in the database. `folder` groups
    the asset in the Cloudinary media library — pass BLOG_FOLDER or
    COURSE_FOLDER from this module.
    """
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type '{content_type}'. Allowed: JPEG, PNG, WEBP, GIF."
        )

    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    if size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB limit."
        )

    try:
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            upload.file,
            folder=folder,
            resource_type="image",
            use_filename=False,    # never derive the public_id from the client's original filename
            unique_filename=True,  # Cloudinary mints a random public_id — the same collision/guessing protection the old UUID filenames gave
            overwrite=False,
        )
    except Exception:
        logger.exception("Cloudinary upload failed (folder=%s)", folder)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image upload failed. Please try again."
        )

    return result["secure_url"]


_PUBLIC_ID_RE = re.compile(r"/upload/(?:v\d+/)?(.+?)\.[a-zA-Z0-9]+$")


async def delete_image(image_url: Optional[str]) -> None:

    if not image_url or not CLOUDINARY_CLOUD_NAME:
        return
    if f"res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/" not in image_url:
        return

    match = _PUBLIC_ID_RE.search(image_url.split("?", 1)[0])
    if not match:
        return

    try:
        await run_in_threadpool(cloudinary.uploader.destroy, match.group(1), resource_type="image")
    except Exception:
        logger.warning("Cloudinary cleanup failed for %s", image_url, exc_info=True)