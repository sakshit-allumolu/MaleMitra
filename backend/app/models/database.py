import sqlite3
import json
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.app.config import settings

def get_db_connection():
    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        team_id TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # Password reset tokens
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        email TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Response Teams
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS response_teams (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        status TEXT NOT NULL,
        current_incident_id TEXT,
        demo_flag INTEGER DEFAULT 1
    )
    """)
    
    # Incidents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY,
        road_edge_id TEXT,
        road_name TEXT,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        type TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL DEFAULT 0.85,
        reported_by_id TEXT NOT NULL,
        reported_by_name TEXT NOT NULL,
        reports_count INTEGER DEFAULT 1,
        assigned_team_id TEXT,
        verification_notes TEXT,
        water_depth_cm REAL,
        restriction_notes TEXT,
        is_blocked INTEGER DEFAULT 0,
        agent_summary TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Incident Reports (individual submissions that can aggregate into incidents)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incident_reports (
        id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        reporter_id TEXT NOT NULL,
        reporter_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        description TEXT NOT NULL,
        evidence_note TEXT,
        photo_url TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(id)
    )
    """)
    
    # Incident Evidence
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incident_evidence (
        id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        submitted_by TEXT NOT NULL,
        submitter_name TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        text_notes TEXT NOT NULL,
        water_depth_cm REAL,
        is_impassable INTEGER,
        photo_url TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(id)
    )
    """)
    
    # Agent Events log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_events (
        id TEXT PRIMARY KEY,
        incident_id TEXT,
        agent TEXT NOT NULL,
        action TEXT NOT NULL,
        input_refs TEXT,
        result TEXT NOT NULL,
        data_mode TEXT DEFAULT 'simulated',
        requires_approval INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Audit Events log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        before_state TEXT,
        after_state TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    # Simulation Runs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS simulation_runs (
        id TEXT PRIMARY KEY,
        seed INTEGER NOT NULL,
        graph_version INTEGER NOT NULL,
        blocked_edges TEXT NOT NULL,
        summary_metrics TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn: sqlite3.Connection):
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    # Check if users already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        demo_users = [
            ("usr-citizen-1", "Citizen Commuter (Pooja)", "citizen@malemitra.in", "citizen", "demo123", None, 1, now),
            ("usr-citizen-2", "Citizen Driver (Kiran)", "kiran@malemitra.in", "citizen", "demo123", None, 1, now),
            ("usr-admin-1", "BBMP Monsoon Control Room Admin", "admin@malemitra.in", "admin", "demo123", None, 1, now),
            ("usr-resp-1", "Inspector Ramesh (Stormwater Unit)", "responder1@malemitra.in", "responder", "demo123", "team-alpha", 1, now),
            ("usr-resp-2", "Officer Kavitha (Traffic & Pump Unit)", "responder2@malemitra.in", "responder", "demo123", "team-beta", 1, now),
        ]
        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)", demo_users)
    
    # Check if response teams already seeded
    cursor.execute("SELECT COUNT(*) FROM response_teams")
    if cursor.fetchone()[0] == 0:
        demo_teams = [
            ("team-alpha", "Team Alpha - Stormwater Response", "available", None, 1),
            ("team-beta", "Team Beta - Traffic & Debris Unit", "available", None, 1),
            ("team-gamma", "Team Gamma - Quick Drainage & Pump", "available", None, 1),
        ]
        cursor.executemany("INSERT INTO response_teams VALUES (?, ?, ?, ?, ?)", demo_teams)
    
    conn.commit()

init_db()
