import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "MaleMitra (ಮಳೆ ಮಿತ್ರ)"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "backend/app/data/malemitra.db")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "malemitra-secret-key-bobathon-2026")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    CORS_ORIGINS: list = ["*"]
    
    # Bounded Bengaluru bounding box (Koramangala, Indiranagar, Domlur, HSR, Ejipura)
    MIN_LAT: float = 12.9000
    MAX_LAT: float = 12.9950
    MIN_LON: float = 77.5800
    MAX_LON: float = 77.6800
    
    # Congestion BPR function parameters
    BPR_ALPHA: float = 0.20
    BPR_BETA: float = 2.5
    
    # Routing Penalty Weights (seconds equivalence)
    HAZARD_LAMBDA: float = 180.0  # Reported unverified hazard penalty in seconds
    CONGESTION_MU: float = 1.0    # Modeled congestion delay multiplier

settings = Settings()
