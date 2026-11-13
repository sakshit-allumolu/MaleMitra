import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from fastapi import HTTPException
from backend.app.models.database import get_db_connection
from backend.app.models.schemas import IncidentStatus, UserRole
from backend.app.services.graph_service import road_graph

class IncidentService:
    @staticmethod
    def get_all_incidents(role: str = "citizen", user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        incidents = []
        for r in rows:
            inc_id = r["id"]
            cursor.execute("SELECT * FROM incident_evidence WHERE incident_id = ? ORDER BY created_at ASC", (inc_id,))
            evidence_rows = cursor.fetchall()
            evidence_list = [dict(ev) for ev in evidence_rows]
            
            # Fetch assigned team label if assigned
            team_label = None
            if r["assigned_team_id"]:
                cursor.execute("SELECT label FROM response_teams WHERE id = ?", (r["assigned_team_id"],))
                t_row = cursor.fetchone()
                if t_row:
                    team_label = t_row["label"]
            
            summary_dict = None
            if r["agent_summary"]:
                try:
                    summary_dict = json.loads(r["agent_summary"])
                except Exception:
                    summary_dict = None
            
            # Sanitization for citizen privacy: hide reporter identity from OTHER citizens.
            # The original reporter always sees their own id and name.
            is_own = (r["reported_by_id"] == user_id)
            reporter_display = "Verified Citizen"
            if role in [UserRole.ADMIN, UserRole.RESPONDER] or is_own:
                reporter_display = r["reported_by_name"]
                
            inc_dict = {
                "id": r["id"],
                "road_edge_id": r["road_edge_id"],
                "road_name": r["road_name"],
                "lat": r["lat"],
                "lon": r["lon"],
                "type": r["type"],
                "severity": r["severity"],
                "status": r["status"],
                "confidence": r["confidence"],
                # Return real id only to admins/responders or the owner; others get "anonymous"
                "reported_by_id": r["reported_by_id"] if (role != UserRole.CITIZEN or is_own) else "anonymous",
                "reported_by_name": reporter_display,
                "is_mine": is_own,
                "reports_count": r["reports_count"],
                "assigned_team_id": r["assigned_team_id"],
                "assigned_team_label": team_label,
                "verification_notes": r["verification_notes"],
                "water_depth_cm": r["water_depth_cm"],
                "restriction_notes": r["restriction_notes"],
                "is_blocked": bool(r["is_blocked"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "evidence_list": evidence_list,
                "agent_summary": summary_dict
            }
            incidents.append(inc_dict)
            
        conn.close()
        return incidents

    @staticmethod
    def get_incident_by_id(incident_id: str, role: str = "citizen") -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        r = cursor.fetchone()
        if not r:
            conn.close()
            return None
            
        cursor.execute("SELECT * FROM incident_evidence WHERE incident_id = ? ORDER BY created_at ASC", (incident_id,))
        evidence_rows = cursor.fetchall()
        evidence_list = [dict(ev) for ev in evidence_rows]
        
        team_label = None
        if r["assigned_team_id"]:
            cursor.execute("SELECT label FROM response_teams WHERE id = ?", (r["assigned_team_id"],))
            t_row = cursor.fetchone()
            if t_row:
                team_label = t_row["label"]
                
        summary_dict = None
        if r["agent_summary"]:
            try:
                summary_dict = json.loads(r["agent_summary"])
            except Exception:
                summary_dict = None
                
        inc_dict = {
            "id": r["id"],
            "road_edge_id": r["road_edge_id"],
            "road_name": r["road_name"],
            "lat": r["lat"],
            "lon": r["lon"],
            "type": r["type"],
            "severity": r["severity"],
            "status": r["status"],
            "confidence": r["confidence"],
            "reported_by_id": r["reported_by_id"] if role != UserRole.CITIZEN else "anonymous",
            "reported_by_name": r["reported_by_name"] if role != UserRole.CITIZEN else "Citizen Commuter",
            "reports_count": r["reports_count"],
            "assigned_team_id": r["assigned_team_id"],
            "assigned_team_label": team_label,
            "verification_notes": r["verification_notes"],
            "water_depth_cm": r["water_depth_cm"],
            "restriction_notes": r["restriction_notes"],
            "is_blocked": bool(r["is_blocked"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "evidence_list": evidence_list,
            "agent_summary": summary_dict
        }
        conn.close()
        return inc_dict

    @staticmethod
    def create_report(user_id: str, user_name: str, lat: float, lon: float, 
                      inc_type: str, severity: str, description: str, 
                      evidence_note: Optional[str] = None, photo_url: Optional[str] = None) -> Dict[str, Any]:
        
        # Spatial edge mapping
        nearest_edge, dist_m, is_ambiguous = road_graph.find_nearest_edge(lat, lon)
        edge_id = nearest_edge.edge_id if nearest_edge else None
        road_name = nearest_edge.road_name if nearest_edge else "Unmapped Bounded Street"
        
        # Calculate initial confidence
        confidence = 0.85
        if is_ambiguous:
            confidence = 0.55
        elif dist_m > 300.0:
            confidence = 0.65
            
        now = datetime.utcnow().isoformat()
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        
        # Agent summary
        agent_summary = {
            "edge_mapped": edge_id,
            "distance_to_edge_m": round(dist_m, 1),
            "is_ambiguous": is_ambiguous,
            "confidence": confidence,
            "recommendation": "Triage review required before response assignment" if is_ambiguous else "Eligible for priority inspection",
            "duplicate_cluster": False
        }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO incidents (
            id, road_edge_id, road_name, lat, lon, type, severity, status, 
            confidence, reported_by_id, reported_by_name, reports_count, 
            agent_summary, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_id, edge_id, road_name, lat, lon, inc_type, severity, 
            IncidentStatus.REPORTED, confidence, user_id, user_name, 1, 
            json.dumps(agent_summary), now, now
        ))
        
        # Insert report entry
        report_id = f"rep-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
        INSERT INTO incident_reports (
            id, incident_id, reporter_id, reporter_name, lat, lon, description, evidence_note, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (report_id, incident_id, user_id, user_name, lat, lon, description, evidence_note, photo_url, now))
        
        # Insert evidence entry
        evidence_id = f"ev-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
        INSERT INTO incident_evidence (
            id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (evidence_id, incident_id, user_id, user_name, "citizen_report", description, now))
        
        # Log Agent Event
        event_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, incident_id, "incident_intelligence", "classify_and_map_edge",
            json.dumps([f"coord:({lat},{lon})", f"report:{report_id}"]),
            json.dumps(agent_summary), "simulated", 1, now
        ))
        
        # Log Audit Event
        audit_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id, user_id, user_name, "CREATE_REPORT", "incident", incident_id,
            None, json.dumps({"status": IncidentStatus.REPORTED, "edge_id": edge_id}), now
        ))
        
        conn.commit()
        conn.close()
        
        # Update unverified hazard score in graph (warning penalty, not closure)
        if edge_id:
            road_graph.set_edge_hazard(edge_id, severity, water_depth_cm=20.0)
            
        return IncidentService.get_incident_by_id(incident_id, role="citizen")

    @staticmethod
    def admin_review(incident_id: str, admin_id: str, admin_name: str, notes: str, severity: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot review incident in state '{inc['status']}'")
            
        now = datetime.utcnow().isoformat()
        new_severity = severity if severity else inc["severity"]
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, severity = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.UNDER_REVIEW, new_severity, now, incident_id))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, "ADMIN_REVIEW", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.UNDER_REVIEW, "notes": notes}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def admin_assign_team(incident_id: str, admin_id: str, admin_name: str, team_id: str, notes: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW, IncidentStatus.ASSIGNED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot assign team for incident in state '{inc['status']}'")
            
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, assigned_team_id = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.ASSIGNED, team_id, now, incident_id))
        
        cursor.execute("UPDATE response_teams SET current_incident_id = ?, status = 'dispatched' WHERE id = ?", (incident_id, team_id))
        
        # Evidence entry
        cursor.execute("""
        INSERT INTO incident_evidence (id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, admin_id, admin_name, "admin_assignment", f"Dispatched Team {team_id}: {notes}", now))
        
        # Agent Event
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), incident_id, "response_coordinator", "dispatch_responder",
            json.dumps([f"incident:{incident_id}", f"team:{team_id}"]),
            json.dumps({"assigned_team": team_id, "status": "dispatched"}), "simulated", 0, now
        ))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, "ASSIGN_TEAM", "incident", incident_id,
            json.dumps({"status": inc["status"], "assigned_team_id": inc["assigned_team_id"]}),
            json.dumps({"status": IncidentStatus.ASSIGNED, "assigned_team_id": team_id}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def responder_verify(incident_id: str, responder_id: str, responder_name: str, 
                         findings: str, water_depth_cm: float, is_impassable: bool,
                         recommended_action: str, evidence_note: Optional[str] = None,
                         photo_url: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.ASSIGNED, IncidentStatus.FIELD_VERIFIED, IncidentStatus.BLOCKED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot verify incident in state '{inc['status']}'. Must be assigned first.")
            
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, verification_notes = ?, water_depth_cm = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.FIELD_VERIFIED, findings, water_depth_cm, now, incident_id))
        
        # Insert evidence
        evidence_text = f"Field Inspection Findings: {findings}. Water Depth: {water_depth_cm}cm. Impassable: {is_impassable}. Recommendation: {recommended_action}."
        if evidence_note:
            evidence_text += f" Notes: {evidence_note}"
            
        cursor.execute("""
        INSERT INTO incident_evidence (
            id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, water_depth_cm, is_impassable, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, responder_id, responder_name, "responder_inspection", evidence_text, water_depth_cm, 1 if is_impassable else 0, photo_url, now))
        
        # Agent Event
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), incident_id, "incident_intelligence", "field_evidence_verified",
            json.dumps([f"responder:{responder_id}", f"depth:{water_depth_cm}cm"]),
            json.dumps({"water_depth_cm": water_depth_cm, "is_impassable": is_impassable, "recommended_action": recommended_action}),
            "simulated", 1, now
        ))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), responder_id, responder_name, "RESPONDER_VERIFY", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.FIELD_VERIFIED, "water_depth_cm": water_depth_cm}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="responder")

    @staticmethod
    def responder_propose_clearance(incident_id: str, responder_id: str, responder_name: str, findings: str, evidence_note: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.BLOCKED, IncidentStatus.FIELD_VERIFIED, IncidentStatus.ASSIGNED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot propose clearance for incident in state '{inc['status']}'")
            
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, verification_notes = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.CLEARANCE_PROPOSED, findings, now, incident_id))
        
        # Add evidence
        cursor.execute("""
        INSERT INTO incident_evidence (id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, water_depth_cm, is_impassable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, responder_id, responder_name, "clearance_evidence", f"Clearance proposal: {findings}", 5.0, 0, now))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), responder_id, responder_name, "PROPOSE_CLEARANCE", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.CLEARANCE_PROPOSED}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="responder")

    @staticmethod
    def admin_authorize_restriction(incident_id: str, admin_id: str, admin_name: str, 
                                     action: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Admin Authorization:
        - action == 'authorize_block': Sets incident to BLOCKED, sets edge.is_blocked = True, increments graph_version
        - action == 'authorize_reopen': Sets incident to CLEARED, sets edge.is_blocked = False, increments graph_version
        - action == 'reject': Sets incident to REJECTED, clears edge hazard
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        edge_id = inc["road_edge_id"]
        now = datetime.utcnow().isoformat()
        
        if action == "authorize_block":
            if inc["status"] not in [IncidentStatus.FIELD_VERIFIED, IncidentStatus.ASSIGNED, IncidentStatus.UNDER_REVIEW]:
                conn.close()
                raise HTTPException(status_code=409, detail=f"Cannot authorize blockage on incident in status '{inc['status']}'. Requires field verification.")
                
            cursor.execute("""
            UPDATE incidents 
            SET status = ?, is_blocked = 1, restriction_notes = ?, updated_at = ?
            WHERE id = ?
            """, (IncidentStatus.BLOCKED, notes or "Authorized road closure by Monsoon Control Room.", now, incident_id))
            
            # Apply hard exclusion to RoadGraph
            if edge_id:
                road_graph.set_edge_restriction(edge_id, is_blocked=True, notes=notes)
                
            # Log Agent Event
            cursor.execute("""
            INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), incident_id, "mobility", "invalidate_route_cache_and_block_edge",
                json.dumps([f"incident:{incident_id}", f"edge:{edge_id}"]),
                json.dumps({"blocked_edge_id": edge_id, "graph_version": road_graph.graph_version}),
                "simulated", 0, now
            ))
            
        elif action == "authorize_reopen":
            cursor.execute("""
            UPDATE incidents 
            SET status = ?, is_blocked = 0, restriction_notes = ?, updated_at = ?
            WHERE id = ?
            """, (IncidentStatus.CLEARED, notes or "Authorized road reopening after verification.", now, incident_id))
            
            # Release team
            if inc["assigned_team_id"]:
                cursor.execute("UPDATE response_teams SET current_incident_id = NULL, status = 'available' WHERE id = ?", (inc["assigned_team_id"],))
                
            # Reopen edge on RoadGraph
            if edge_id:
                road_graph.set_edge_restriction(edge_id, is_blocked=False, notes=notes)
                road_graph.clear_edge_hazard(edge_id)
                
            cursor.execute("""
            INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), incident_id, "mobility", "reopen_road_and_restore_capacity",
                json.dumps([f"incident:{incident_id}", f"edge:{edge_id}"]),
                json.dumps({"reopened_edge_id": edge_id, "graph_version": road_graph.graph_version}),
                "simulated", 0, now
            ))
            
        elif action == "reject":
            cursor.execute("UPDATE incidents SET status = ?, is_blocked = 0, updated_at = ? WHERE id = ?", (IncidentStatus.REJECTED, now, incident_id))
            if edge_id:
                road_graph.clear_edge_hazard(edge_id)
        else:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Unknown restriction action '{action}'")
            
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, f"AUTHORIZE_{action.upper()}", "incident", incident_id,
            json.dumps({"status": inc["status"], "is_blocked": inc["is_blocked"]}),
            json.dumps({"action": action, "graph_version": road_graph.graph_version}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def withdraw_report(incident_id: str, user_id: str) -> Dict[str, Any]:
        """
        Citizen withdraws their own report.
        Rules:
          - Only the original reporter can withdraw.
          - Only allowed when status is 'reported' or 'under_review'
            (once field-verified or blocked, control room must handle it).
          - Clears the edge hazard from the graph so routing is not affected.
          - Sets status to 'rejected' (re-uses existing terminal status)
            with a restriction_notes label of 'Withdrawn by reporter'.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")

        if inc["reported_by_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="You can only withdraw your own reports")

        withdrawable = {IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW}
        if inc["status"] not in withdrawable:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail=f"Cannot withdraw a report with status '{inc['status']}'. "
                       f"Only reports that are 'reported' or 'under_review' can be withdrawn."
            )

        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE incidents SET status = ?, restriction_notes = ?, updated_at = ? WHERE id = ?",
            (IncidentStatus.REJECTED, "Withdrawn by reporter", now, incident_id)
        )

        # Clear edge hazard so routing is unaffected
        edge_id = inc["road_edge_id"]
        if edge_id:
            road_graph.clear_edge_hazard(edge_id)

        # Audit trail
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), user_id, inc["reported_by_name"], "WITHDRAW_REPORT",
            "incident", incident_id,
            json.dumps({"status": inc["status"]}),
            json.dumps({"status": IncidentStatus.REJECTED, "note": "Withdrawn by reporter"}),
            now
        ))

        conn.commit()
        conn.close()
        return {"message": "Report withdrawn successfully", "incident_id": incident_id}

incident_service = IncidentService()
