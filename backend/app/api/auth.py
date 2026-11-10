import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
from backend.app.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile, UserRole
from backend.app.models.database import get_db_connection

router = APIRouter(prefix="/auth", tags=["auth"])

def get_current_user(authorization: Optional[str] = Header(None)) -> UserProfile:
    """Simple auth resolver supporting Bearer token with demo user IDs or email tokens."""
    if not authorization:
        # Default anonymous citizen in demo mode
        return UserProfile(id="usr-citizen-1", name="Citizen Commuter (Pooja)", email="citizen@malemitra.in", role=UserRole.CITIZEN)
        
    token = authorization.replace("Bearer ", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check by ID or Email
    cursor.execute("SELECT * FROM users WHERE id = ? OR email = ?", (token, token))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return UserProfile(
            id=user["id"],
            name=user["name"],
            email=user["email"],
            role=user["role"],
            team_id=user["team_id"],
            active=bool(user["active"])
        )
        
    # Fallback to citizen
    return UserProfile(id="usr-citizen-1", name="Citizen Commuter", email="citizen@malemitra.in", role=UserRole.CITIZEN)

def require_role(allowed_roles: list):
    def role_checker(current_user: UserProfile = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Forbidden: role '{current_user.role}' lacks authorization for this endpoint.")
        return current_user
    return role_checker

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?", (req.email.lower().strip(), req.password))
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
    """, (user_id, req.name.strip(), email_clean, role, req.password, team_id, now))

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

@router.get("/demo-accounts")
def get_demo_accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, team_id FROM users WHERE active = 1")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"demo_accounts": users}
