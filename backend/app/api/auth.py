import logging
import uuid
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
from pydantic import BaseModel
from backend.app.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile, UserRole
from backend.app.models.database import get_db_connection
from backend.app.config import settings
from backend.app.security import hash_password, verify_password
from backend.app.timeutil import utcnow
from backend.app import ratelimit
from backend.app.ratelimit import rate_limit_ip
from backend.app.services import notification_service

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Session tokens ─────────────────────────────────────────────────────────────
# Format: <user_id>.<token_version>.<expiry_unix>.<hmac_sha256(user_id.version.expiry, JWT_SECRET)>
# The version must equal users.token_version, so logout / password change revokes every session
# issued before it. Bare user ids are only accepted while settings.ALLOW_LEGACY_TOKENS is true.

def _sign(payload: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

def create_session_token(user_id: str, version: int = 0) -> str:
    expiry = int(time.time()) + settings.SESSION_TTL_SECONDS
    payload = f"{user_id}.{version}.{expiry}"
    return f"{payload}.{_sign(payload)}"

def _parse_token(token: str) -> Optional[tuple]:
    """Return (user_id, version) for a validly signed, unexpired token ((id, None) for a legacy id)."""
    parts = token.rsplit(".", 3)
    if len(parts) == 4 and parts[1].isdigit() and parts[2].isdigit():
        user_id, version, expiry, sig = parts
        if not hmac.compare_digest(sig, _sign(f"{user_id}.{version}.{expiry}")):
            return None
        if int(expiry) < time.time():
            return None
        return user_id, int(version)
    return (token, None) if settings.ALLOW_LEGACY_TOKENS else None

log = logging.getLogger("malemitra.auth")


def hash_token(token: str) -> str:
    """Reset tokens are stored hashed so a DB leak does not leak usable tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

# ── Helpers ────────────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Strip spaces/dashes/brackets; accept 10-15 digits with optional '+'. Bare 10-digit numbers are Indian mobiles."""
    if raw is None or not raw.strip():
        return None
    cleaned = re.sub(r"[\s\-().]", "", raw)
    if not _PHONE_RE.match(cleaned):
        raise HTTPException(status_code=422, detail="Phone must be 10-15 digits, optionally starting with '+'.")
    if not cleaned.startswith("+") and len(cleaned) == 10:
        cleaned = "+91" + cleaned
    return cleaned


_auth_limit = rate_limit_ip("auth", "RATE_LIMIT_AUTH_PER_MIN", 60)

def _validate_password_strength(password: str) -> Optional[str]:
    """Return an error message if the password fails policy, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r'\d', password):
        return "Password must contain at least one number."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?`~]', password):
        return "Password must contain at least one special character (!@#$%^&* etc.)."
    return None

# ── Auth dependency ─────────────────────────────────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)) -> UserProfile:
    """Auth resolver: Bearer token must be a valid user ID returned at login."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")

    token = authorization.replace("Bearer ", "").strip()
    parsed = _parse_token(token)
    if not parsed:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
    user_id, version = parsed
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user or not user["active"] or (version is not None and version != user["token_version"]):
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    return UserProfile(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        team_id=user["team_id"],
        active=bool(user["active"])
    )

def require_role(allowed_roles: list):
    def role_checker(current_user: UserProfile = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Forbidden: role '{current_user.role}' lacks authorization for this endpoint.")
        return current_user
    return role_checker

# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_auth_limit)])
def login(req: LoginRequest):
    email_key = req.email.lower().strip()
    if settings.RATE_LIMIT_ENABLED and settings.LOGIN_MAX_FAILURES > 0 and \
            ratelimit.count("login_fail", email_key, settings.LOGIN_LOCKOUT_SECONDS) >= settings.LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, headers={"Retry-After": str(settings.LOGIN_LOCKOUT_SECONDS)},
                            detail="Too many failed sign-in attempts. Try again later or reset your password.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND active = 1", (email_key,))
    user = cursor.fetchone()

    valid, needs_upgrade = (False, False)
    if user:
        valid, needs_upgrade = verify_password(req.password, user["password_hash"])
    else:
        hash_password(req.password)  # comparable timing whether or not the account exists
    if not valid:
        conn.close()
        ratelimit.record("login_fail", email_key)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    ratelimit.clear("login_fail", email_key)

    if needs_upgrade:  # legacy plaintext / unsalted hash -> scrypt
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(req.password), user["id"]))
        conn.commit()
    conn.close()

    return TokenResponse(
        access_token=create_session_token(user["id"], user["token_version"]),
        user_id=user["id"],
        name=user["name"],
        role=user["role"],
        team_id=user["team_id"]
    )

def _create_user(name: str, email: str, password: str, role: str, team_id: Optional[str],
                 phone: Optional[str] = None) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please log in.")
    if team_id:
        cursor.execute("SELECT 1 FROM response_teams WHERE id = ?", (team_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=422, detail=f"Unknown team '{team_id}'.")
    user_id = f"usr-{role[:4]}-{uuid.uuid4().hex[:6]}"
    cursor.execute("""
    INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at, phone)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (user_id, name, email, role, hash_password(password), team_id, utcnow().isoformat(), phone))
    conn.commit()
    conn.close()
    return user_id


@router.post("/register", response_model=TokenResponse, dependencies=[Depends(_auth_limit)])
def register(req: RegisterRequest):
    """
    Public sign-up. Outside DEMO_MODE this only creates citizen accounts; responders and admins
    are created by an admin through POST /auth/users.
    """
    email_clean = req.email.lower().strip()
    name = req.name.strip()
    if not email_clean or "@" not in email_clean or not name or not req.password:
        raise HTTPException(status_code=400, detail="Name, a valid email, and password are required.")
    if len(name) > 100 or len(email_clean) > 200:
        raise HTTPException(status_code=422, detail="Name or email is too long.")

    policy_error = _validate_password_strength(req.password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    role = req.role.lower().strip()
    if role not in [UserRole.CITIZEN, UserRole.RESPONDER, UserRole.ADMIN]:
        role = UserRole.CITIZEN

    team_id = None
    if role != UserRole.CITIZEN:
        if not settings.DEMO_MODE:
            raise HTTPException(
                status_code=403,
                detail="Responder and administrator accounts are created by an administrator.")
        if role == UserRole.ADMIN:
            code = (req.admin_code or "").strip().lower()
            if not settings.ADMIN_SIGNUP_CODE or code != settings.ADMIN_SIGNUP_CODE.lower():
                raise HTTPException(status_code=403, detail="Invalid Administrator Verification Code.")
        if role == UserRole.RESPONDER:
            team_id = req.team_id or "team-alpha"

    user_id = _create_user(name, email_clean, req.password, role, team_id, normalize_phone(req.phone))
    return TokenResponse(
        access_token=create_session_token(user_id),
        user_id=user_id,
        name=name,
        role=role,
        team_id=team_id
    )


class AdminCreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str
    team_id: Optional[str] = None
    phone: Optional[str] = None


@router.post("/users", response_model=UserProfile)
def admin_create_user(req: AdminCreateUserRequest, admin: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Admin creates a responder or administrator account."""
    email_clean = req.email.lower().strip()
    name = req.name.strip()
    role = req.role.lower().strip()
    if role not in (UserRole.RESPONDER, UserRole.ADMIN, UserRole.CITIZEN):
        raise HTTPException(status_code=422, detail="role must be citizen, responder or admin.")
    if not name or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Name and a valid email are required.")
    policy_error = _validate_password_strength(req.password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)
    team_id = req.team_id if role == UserRole.RESPONDER else None
    if role == UserRole.RESPONDER and not team_id:
        raise HTTPException(status_code=422, detail="A responder needs a team_id.")
    user_id = _create_user(name, email_clean, req.password, role, team_id, normalize_phone(req.phone))
    return UserProfile(id=user_id, name=name, email=email_clean, role=role, team_id=team_id, active=True)

@router.get("/me", response_model=UserProfile)
def get_me(user: UserProfile = Depends(get_current_user)):
    return user

class PhoneUpdate(BaseModel):
    phone: Optional[str] = None


@router.put("/me/phone")
def update_my_phone(req: PhoneUpdate, user: UserProfile = Depends(get_current_user)):
    """Set (or clear, with null/empty) the number used for SMS notifications."""
    phone = normalize_phone(req.phone)
    conn = get_db_connection()
    conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user.id))
    conn.commit()
    conn.close()
    return {"phone": phone}


@router.post("/logout")
def logout(user: UserProfile = Depends(get_current_user)):
    """Revoke every session token issued to this account so far (all devices)."""
    conn = get_db_connection()
    conn.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (user.id,))
    conn.commit()
    conn.close()
    return {"message": "Signed out."}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", response_model=TokenResponse, dependencies=[Depends(_auth_limit)])
def change_password(req: ChangePasswordRequest, user: UserProfile = Depends(get_current_user)):
    """Change the signed-in user's password. Other sessions are revoked; a fresh token is returned."""
    policy_error = _validate_password_strength(req.new_password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)
    conn = get_db_connection()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
    if not row or not verify_password(req.current_password, row["password_hash"])[0]:
        conn.close()
        raise HTTPException(status_code=403, detail="Current password is incorrect.")
    conn.execute("UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
                 (hash_password(req.new_password), user.id))
    conn.commit()
    version = conn.execute("SELECT token_version FROM users WHERE id = ?", (user.id,)).fetchone()[0]
    conn.close()
    return TokenResponse(access_token=create_session_token(user.id, version), user_id=user.id,
                         name=user.name, role=user.role, team_id=user.team_id)


# ── Password Reset ─────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/forgot-password", dependencies=[Depends(_auth_limit)])
def forgot_password(req: ForgotPasswordRequest):
    """
    Create a one-time password-reset token (30 min). The token is only ever returned in DEMO_MODE
    (there is no email/SMS integration); otherwise it is logged for the operator to deliver and the
    response is identical whether or not the email exists, so accounts cannot be enumerated.
    """
    email_clean = req.email.lower().strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM users WHERE email = ? AND active = 1", (email_clean,))
    user = cursor.fetchone()
    generic = {"message": "If that email exists, a reset link has been sent.", "debug_token": None}

    if not user:
        conn.close()
        return generic

    cursor.execute("UPDATE password_reset_tokens SET used = 1 WHERE email = ? AND used = 0", (email_clean,))

    token = secrets.token_urlsafe(32)
    now = utcnow()
    expires_at = (now + timedelta(minutes=30)).isoformat()
    cursor.execute("""
    INSERT INTO password_reset_tokens (token, user_id, email, expires_at, used, created_at)
    VALUES (?, ?, ?, ?, 0, ?)
    """, (hash_token(token), user["id"], email_clean, expires_at, now.isoformat()))
    # Same transaction: the token exists only if its delivery message was queued.
    queued = notification_service.enqueue(
        cursor, user["id"], "password_reset", "Reset your MaleMitra password",
        f"Hello {user['name']},\n\nUse this one-time code to reset your MaleMitra password. "
        f"It expires in 30 minutes.\n\n    {token}\n\nIf you did not ask for this, ignore this message.")
    conn.commit()
    conn.close()

    if settings.DEMO_MODE and settings.EXPOSE_RESET_TOKEN:
        return {"message": "Demo mode: reset token returned directly.",
                "debug_token": token, "expires_in_minutes": 30}
    if not queued:
        log.error("Password reset for user %s could not be delivered: no email/SMS channel is configured "
                  "(set SMTP_HOST or NOTIFY_WEBHOOK_URL).", user["id"])
    return generic

@router.post("/reset-password", dependencies=[Depends(_auth_limit)])
def reset_password(req: ResetPasswordRequest):
    """Validate a reset token and update the password."""
    policy_error = _validate_password_strength(req.new_password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0",
        (hash_token(req.token),)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or already-used reset token.")

    expires_at = datetime.fromisoformat(row["expires_at"])
    if utcnow() > expires_at:
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    # Update password and mark token used
    cursor.execute(
        "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
        (hash_password(req.new_password), row["user_id"])
    )
    cursor.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
        (hash_token(req.token),)
    )
    conn.commit()
    conn.close()

    return {"message": "Password updated successfully. You can now sign in."}
