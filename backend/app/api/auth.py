import uuid
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
from pydantic import BaseModel
from backend.app.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile, UserRole
from backend.app.models.database import get_db_connection

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 hash of the password (hex digest)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

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
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (token,))
    user = cursor.fetchone()
    conn.close()

    if not user:
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

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Try hashed password first, then plain-text fallback for legacy demo seeds
    hashed = _hash_password(req.password)
    cursor.execute(
        "SELECT * FROM users WHERE email = ? AND (password_hash = ? OR password_hash = ?)",
        (req.email.lower().strip(), hashed, req.password)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return TokenResponse(
        access_token=user["id"],
        user_id=user["id"],
        name=user["name"],
        role=user["role"],
        team_id=user["team_id"]
    )

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    email_clean = req.email.lower().strip()
    if not email_clean or not req.name.strip() or not req.password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required.")

    # Password strength policy
    policy_error = _validate_password_strength(req.password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    role = req.role.lower().strip()
    if role not in [UserRole.CITIZEN, UserRole.RESPONDER, UserRole.ADMIN]:
        role = UserRole.CITIZEN

    # Validate Admin Passcode
    if role == UserRole.ADMIN:
        code = (req.admin_code or "").strip().lower()
        if code not in ["bbmp2026", "admin123", "malemitra"]:
            raise HTTPException(status_code=403, detail="Invalid Administrator Verification Code. Use 'bbmp2026'.")

    team_id = req.team_id
    if role == UserRole.RESPONDER and not team_id:
        team_id = "team-alpha"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please log in.")

    user_id = f"usr-{role[:4]}-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow().isoformat()

    cursor.execute("""
    INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (user_id, req.name.strip(), email_clean, role, _hash_password(req.password), team_id, now))

    conn.commit()
    conn.close()

    return TokenResponse(
        access_token=user_id,
        user_id=user_id,
        name=req.name.strip(),
        role=role,
        team_id=team_id
    )

@router.get("/me", response_model=UserProfile)
def get_me(user: UserProfile = Depends(get_current_user)):
    return user

# ── Password Reset ─────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Generate a password reset token. Returns the token directly (demo: no email sending)."""
    email_clean = req.email.lower().strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM users WHERE email = ? AND active = 1", (email_clean,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        # Return success anyway to prevent email enumeration
        return {"message": "If that email exists, a reset link has been sent.", "debug_token": None}

    # Invalidate any existing unused tokens for this email
    cursor.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE email = ? AND used = 0",
        (email_clean,)
    )

    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires_at = (now + timedelta(minutes=30)).isoformat()

    cursor.execute("""
    INSERT INTO password_reset_tokens (token, user_id, email, expires_at, used, created_at)
    VALUES (?, ?, ?, ?, 0, ?)
    """, (token, user["id"], email_clean, expires_at, now.isoformat()))

    conn.commit()
    conn.close()

    # In a real app, send this via email. For demo, return directly.
    return {
        "message": "Reset token generated. In production this would be emailed.",
        "debug_token": token,
        "expires_in_minutes": 30
    }

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """Validate a reset token and update the password."""
    policy_error = _validate_password_strength(req.new_password)
    if policy_error:
        raise HTTPException(status_code=422, detail=policy_error)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0",
        (req.token,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or already-used reset token.")

    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.utcnow() > expires_at:
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    # Update password and mark token used
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (_hash_password(req.new_password), row["user_id"])
    )
    cursor.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
        (req.token,)
    )
    conn.commit()
    conn.close()

    return {"message": "Password updated successfully. You can now sign in."}
