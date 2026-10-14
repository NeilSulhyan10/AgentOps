"""
WebSocket Connection Manager for Real-time Investigation Updates
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

from backend.events import connection_manager, broadcast_investigation_update
from backend.services.investigation_service import investigation_service

logger = logging.getLogger(__name__)


# WebSocket endpoint for real-time investigation updates
async def investigation_websocket(websocket: WebSocket, investigation_id: str):
    """WebSocket endpoint for real-time investigation updates."""
    await connection_manager.connect(investigation_id, websocket)
    try:
        # Send initial state
        investigation = await investigation_service.get_investigation(investigation_id)
        if investigation:
            await websocket.send_json({
                "type": "initial_state",
                "investigation_id": investigation_id,
                "data": {
                    "status": investigation.investigation_status if isinstance(investigation.investigation_status, str) else investigation.investigation_status.value,
                    "iteration": investigation.iteration_count,
                    "max_iterations": investigation.max_iterations,
                    "overall_confidence": investigation.overall_confidence,
                    "current_agent": investigation.current_agent if isinstance(investigation.current_agent, str) else investigation.current_agent.value if investigation.current_agent else None,
                    "agents_invoked": [a.value if hasattr(a, 'value') else str(a) for a in investigation.agents_invoked],
                    "evidence_gaps": investigation.evidence_gaps,
                }
            })
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages (ping/pong or client messages)
                data = await websocket.receive_json()
                # Handle client messages if needed
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception:
                # Ignore other errors, keep connection alive
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.getLogger(__name__).error(f"WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(investigation_id, websocket)