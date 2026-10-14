"""
Event Broadcasting Module for Real-time Investigation Updates

This module provides event broadcasting functions without creating circular imports.
It uses a lazy import pattern to avoid circular dependencies.
"""
import asyncio
import json
import logging
from typing import Dict, Set, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per investigation."""
    
    def __init__(self):
        # investigation_id -> set of WebSocket connections
        self._connections: Dict[str, Set[object]] = {}  # WebSocket type
        self._lock = asyncio.Lock()
    
    async def connect(self, investigation_id: str, websocket: object):
        """Accept and register a new WebSocket connection."""
        # Import here to avoid circular imports
        from fastapi import WebSocket
        if isinstance(websocket, WebSocket):
            await websocket.accept()
        async with self._lock:
            if investigation_id not in self._connections:
                self._connections[investigation_id] = set()
            self._connections[investigation_id].add(websocket)
        logger.info(f"WebSocket connected for investigation {investigation_id}. Total connections: {len(self._connections.get(investigation_id, set()))}")
    
    async def disconnect(self, investigation_id: str, websocket: object):
        """Remove a WebSocket connection."""
        async with self._lock:
            if investigation_id in self._connections:
                self._connections[investigation_id].discard(websocket)
                if not self._connections[investigation_id]:
                    del self._connections[investigation_id]
        logger.info(f"WebSocket disconnected for investigation {investigation_id}")
    
    async def broadcast(self, investigation_id: str, message: dict):
        """Broadcast a message to all connections for an investigation."""
        async with self._lock:
            connections = self._connections.get(investigation_id, set()).copy()
        
        if not connections:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for websocket in connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections.get(investigation_id, set()).discard(ws)


# Global connection manager
connection_manager = ConnectionManager()


# Event callback registry - allows other modules to register for events
_event_callbacks: Dict[str, list[Callable[[str, dict], Awaitable[None]]]] = {}


def register_event_callback(event_type: str, callback: Callable[[str, dict], Awaitable[None]]):
    """Register a callback for a specific event type."""
    if event_type not in _event_callbacks:
        _event_callbacks[event_type] = []
    _event_callbacks[event_type].append(callback)


async def _emit_event(event_type: str, investigation_id: str, data: dict):
    """Emit an event to all registered callbacks."""
    message = {
        "type": "investigation_update",
        "update_type": event_type,
        "investigation_id": investigation_id,
        "data": data,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }
    
    # Broadcast to WebSocket connections
    await connection_manager.broadcast(investigation_id, message)
    
    # Call registered callbacks
    for callback in _event_callbacks.get(event_type, []):
        try:
            await callback(investigation_id, data)
        except Exception as e:
            logger.warning(f"Event callback failed: {e}")


async def broadcast_agent_thinking(investigation_id: str, agent_type: str, status: str, reasoning: str = None):
    """Broadcast agent thinking status."""
    await _emit_event("agent_thinking", investigation_id, {
        "agent_type": agent_type,
        "status": status,  # "started", "thinking", "completed"
        "reasoning": reasoning
    })


async def broadcast_routing_decision(investigation_id: str, selected_agent: str, reasoning: str, iteration: int):
    """Broadcast routing decision."""
    await _emit_event("routing_decision", investigation_id, {
        "selected_agent": selected_agent,
        "reasoning": reasoning,
        "iteration": iteration
    })


async def broadcast_agent_finding(investigation_id: str, agent_type: str, finding: dict):
    """Broadcast agent finding."""
    await _emit_event("agent_finding", investigation_id, {
        "agent_type": agent_type,
        "finding": finding
    })


async def broadcast_progress(investigation_id: str, iteration: int, max_iterations: int, overall_confidence: float):
    """Broadcast investigation progress."""
    await _emit_event("progress", investigation_id, {
        "iteration": iteration,
        "max_iterations": max_iterations,
        "overall_confidence": overall_confidence,
        "progress_percent": round((iteration / max_iterations) * 100, 1) if max_iterations > 0 else 0
    })


async def broadcast_status_change(investigation_id: str, status: str):
    """Broadcast investigation status change."""
    await _emit_event("status_change", investigation_id, {
        "status": status
    })


async def broadcast_investigation_update(investigation_id: str, update_type: str, data: dict):
    """Broadcast an investigation update to all connected clients."""
    await _emit_event(update_type, investigation_id, data)