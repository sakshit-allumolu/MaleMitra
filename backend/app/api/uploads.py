from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from backend.app.api.auth import get_current_user
from backend.app.config import settings
from backend.app.models.schemas import UserProfile
from backend.app.ratelimit import hit
from backend.app.services import upload_service

router = APIRouter(tags=["uploads"])


@router.post("/uploads", status_code=201)
async def upload_photo(request: Request, user: UserProfile = Depends(get_current_user)):
    """
    Upload one photo as the raw request body (Content-Type is ignored: the file type is read from its bytes).
    Returns an id to pass as `photo_id` when submitting a report or field verification.
    """
    hit("uploads", user.id, settings.RATE_LIMIT_UPLOADS_PER_HOUR, 3600)
    limit = settings.MAX_UPLOAD_BYTES
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"Photo too large (max {limit // 1024} KB).")
    chunks, size = [], 0
    async for chunk in request.stream():       # enforce the cap even if Content-Length is missing or lies
        size += len(chunk)
        if size > limit:
            raise HTTPException(status_code=413, detail=f"Photo too large (max {limit // 1024} KB).")
        chunks.append(chunk)
    return upload_service.save_upload(user.id, b"".join(chunks))


@router.get("/uploads/{upload_id}")
def get_photo(upload_id: str):
    """
    Photos are addressed by a random 128-bit id (a capability URL), because <img> tags cannot send an
    Authorization header. They carry no EXIF/GPS (stripped on upload).
    """
    found = upload_service.locate(upload_id)
    if not found:
        raise HTTPException(status_code=404, detail="Photo not found")
    path, mime = found
    return FileResponse(path, media_type=mime, headers={
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": "inline",
    })
