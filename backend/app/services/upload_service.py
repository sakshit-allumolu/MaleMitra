"""
Citizen/responder photo uploads.

What is enforced (no image library is installed, so the checks are structural and deliberately strict):
* only JPEG and PNG, decided from the file's magic bytes, never from the client's Content-Type or filename;
* the file must parse as a well-formed JPEG/PNG end to end (no trailing payload after EOI / IEND);
* location and device metadata are removed before storing (JPEG APP1/APP13/COM segments - EXIF GPS,
  XMP, IPTC - and PNG eXIf/tEXt/iTXt/zTXt chunks), so a reporter's phone GPS is never published;
* a size cap, a per-user rate limit, unguessable ids and orphan cleanup;
* files are served with the type we detected, `nosniff` and a sandboxing CSP.

Not done: re-encoding, virus scanning or content moderation. Photos are evidence for a human reviewer.
"""
import hashlib
import logging
import os
import re
import struct
import time
import uuid
from typing import Optional, Tuple

from fastapi import HTTPException

from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.timeutil import utcnow

log = logging.getLogger("malemitra.uploads")

PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_DROP = {b"eXIf", b"tEXt", b"iTXt", b"zTXt"}
ID_RE = re.compile(r"^[0-9a-f]{32}$")
ORPHAN_MAX_AGE_S = 24 * 3600


class BadImage(ValueError):
    pass


def _clean_jpeg(data: bytes) -> bytes:
    if data[:3] != b"\xff\xd8\xff":
        raise BadImage("not a JPEG")
    out = bytearray(b"\xff\xd8")
    i, n = 2, len(data)
    saw_sof = False
    while True:
        if i + 4 > n or data[i] != 0xFF:
            raise BadImage("corrupt JPEG segment structure")
        marker = data[i + 1]
        if marker == 0xFF:          # fill byte
            i += 1
            continue
        if marker == 0xD9:          # EOI before any scan data
            raise BadImage("JPEG has no image data")
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if seg_len < 2 or i + 2 + seg_len > n:
            raise BadImage("corrupt JPEG segment length")
        segment = data[i:i + 2 + seg_len]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            saw_sof = True
        if marker == 0xDA:          # start of scan: entropy-coded data runs to EOI
            if not saw_sof:
                raise BadImage("JPEG has no frame header")
            rest = data[i:]
            eoi = rest.rfind(b"\xff\xd9")
            if eoi == -1 or rest[eoi + 2:].strip(b"\x00"):
                raise BadImage("JPEG is truncated or has trailing data")
            out += rest[:eoi + 2]
            return bytes(out)
        if marker in (0xE1, 0xED, 0xFE):   # EXIF/XMP, IPTC, comments
            i += 2 + seg_len
            continue
        out += segment
        i += 2 + seg_len


def _clean_png(data: bytes) -> bytes:
    if data[:8] != PNG_SIG:
        raise BadImage("not a PNG")
    out = bytearray(PNG_SIG)
    i, n = 8, len(data)
    first = True
    saw_idat = False
    while i + 12 <= n:
        length = struct.unpack(">I", data[i:i + 4])[0]
        ctype = data[i + 4:i + 8]
        end = i + 12 + length
        if end > n:
            raise BadImage("corrupt PNG chunk length")
        if first and ctype != b"IHDR":
            raise BadImage("PNG must start with IHDR")
        first = False
        if ctype == b"IDAT":
            saw_idat = True
        if ctype not in _PNG_DROP:
            out += data[i:end]
        i = end
        if ctype == b"IEND":
            if i != n:
                raise BadImage("PNG has trailing data")
            if not saw_idat:
                raise BadImage("PNG has no image data")
            return bytes(out)
    raise BadImage("PNG is truncated")


def sanitize_image(data: bytes) -> Tuple[bytes, str, str]:
    """Validate and strip metadata. Returns (clean_bytes, mime, extension). Raises BadImage."""
    if data[:3] == b"\xff\xd8\xff":
        return _clean_jpeg(data), "image/jpeg", "jpg"
    if data[:8] == PNG_SIG:
        return _clean_png(data), "image/png", "png"
    raise BadImage("only JPEG and PNG images are accepted")


def _dir() -> str:
    d = settings.UPLOAD_DIR or os.path.join(os.path.dirname(settings.DATABASE_PATH) or ".", "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _purge_orphans() -> None:
    """Delete uploads that were never attached to a report within a day (best effort)."""
    cutoff = time.time() - ORPHAN_MAX_AGE_S
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT id, filename FROM uploads WHERE attached = 0 AND created_ts < ? LIMIT 200",
                            (cutoff,)).fetchall()
        for r in rows:
            try:
                os.remove(os.path.join(_dir(), r["filename"]))
            except FileNotFoundError:
                pass
            conn.execute("DELETE FROM uploads WHERE id = ? AND attached = 0", (r["id"],))
        conn.commit()
    finally:
        conn.close()


def save_upload(owner_id: str, data: bytes) -> dict:
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    try:
        clean, mime, ext = sanitize_image(data)
    except BadImage as e:
        raise HTTPException(status_code=415, detail=f"Rejected image: {e}.")
    upload_id = uuid.uuid4().hex
    filename = f"{upload_id}.{ext}"
    path = os.path.join(_dir(), filename)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(clean)
    os.replace(tmp, path)                       # never expose a half-written file
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO uploads (id, owner_id, filename, mime, size, sha256, created_at, created_ts, attached) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                     (upload_id, owner_id, filename, mime, len(clean), hashlib.sha256(clean).hexdigest(),
                      utcnow().isoformat(), time.time()))
        conn.commit()
    finally:
        conn.close()
    try:
        _purge_orphans()
    except Exception as e:
        log.warning("orphan cleanup failed: %s", e)
    return {"id": upload_id, "url": url_for(upload_id), "mime": mime, "size": len(clean)}


def url_for(upload_id: str) -> str:
    return f"{settings.API_PREFIX}/uploads/{upload_id}"


def claim(upload_id: Optional[str], user_id: str) -> Optional[str]:
    """Turn an upload id into a stored photo URL, checking it exists and belongs to `user_id`."""
    if not upload_id:
        return None
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT owner_id FROM uploads WHERE id = ?", (upload_id,)).fetchone()
        if row is None or row["owner_id"] != user_id:
            raise HTTPException(status_code=422, detail="Unknown photo. Upload it again and retry.")
        conn.execute("UPDATE uploads SET attached = 1 WHERE id = ?", (upload_id,))
        conn.commit()
    finally:
        conn.close()
    return url_for(upload_id)


def locate(upload_id: str) -> Optional[Tuple[str, str]]:
    """(absolute path, mime) for a stored upload, or None."""
    if not ID_RE.match(upload_id):
        return None
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT filename, mime FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    path = os.path.join(_dir(), row["filename"])
    return (path, row["mime"]) if os.path.isfile(path) else None
