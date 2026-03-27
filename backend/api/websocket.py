"""
WebSocket endpoint for real-time AnomalyIQ updates.
Manages connected client sessions and broadcasts anomaly / cost events.
Includes a thread-safe sync bridge so background agent threads can push events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Set of currently connected WebSocket clients
_connected_clients: Set[WebSocket] = set()

# Reference to the main event loop — set on startup so background threads
# can schedule coroutines with asyncio.run_coroutine_threadsafe()
_main_loop: Optional[asyncio.AbstractEventLoop] = None

# Heartbeat interval in seconds
_HEARTBEAT_SECONDS = 30


# ---------------------------------------------------------------------------
# Loop registration (called from main.py on startup)
# ---------------------------------------------------------------------------


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store a reference to the running event loop for thread-safe broadcasts."""
    global _main_loop
    _main_loop = loop
    logger.debug("WebSocket main event loop registered.")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


def _register(ws: WebSocket) -> None:
    _connected_clients.add(ws)
    logger.info("WebSocket client connected. Total: %d", len(_connected_clients))


def _unregister(ws: WebSocket) -> None:
    _connected_clients.discard(ws)
    logger.info("WebSocket client disconnected. Total: %d", len(_connected_clients))


# ---------------------------------------------------------------------------
# Broadcasting (async — called from within the event loop)
# ---------------------------------------------------------------------------


async def broadcast(message: Dict[str, Any]) -> None:
    """Send a JSON message to all connected WebSocket clients."""
    if not _connected_clients:
        return

    payload = json.dumps(message, default=str)
    dead: Set[WebSocket] = set()

    for ws in list(_connected_clients):
        try:
            await ws.send_text(payload)
        except Exception as exc:
            logger.debug("Failed to send to client: %s", exc)
            dead.add(ws)

    for ws in dead:
        _unregister(ws)


async def broadcast_anomaly(anomaly: Dict[str, Any]) -> None:
    """Broadcast a newly detected anomaly to all WS clients."""
    await broadcast(
        {
            "type": "anomaly_detected",
            "payload": anomaly,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


async def broadcast_cost_update(cost_data: Dict[str, Any]) -> None:
    """Broadcast a cost data update to all WS clients."""
    await broadcast(
        {
            "type": "cost_update",
            "payload": cost_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Thread-safe sync bridge (called from background agent threads)
# ---------------------------------------------------------------------------


def broadcast_anomaly_sync(anomaly: Dict[str, Any]) -> None:
    """
    Thread-safe wrapper — schedules broadcast_anomaly on the main event loop.
    Safe to call from any background thread (scheduler, downstream agents).
    """
    if _main_loop is None or not _main_loop.is_running():
        logger.debug("WS broadcast skipped — main loop not available.")
        return
    asyncio.run_coroutine_threadsafe(broadcast_anomaly(anomaly), _main_loop)


def broadcast_cost_update_sync(cost_data: Dict[str, Any]) -> None:
    """Thread-safe wrapper for broadcast_cost_update."""
    if _main_loop is None or not _main_loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(broadcast_cost_update(cost_data), _main_loop)


def broadcast_alert_sync(alert: Dict[str, Any]) -> None:
    """
    Thread-safe wrapper — broadcasts a new alert to all WS clients.
    Called from agent5 after an alert is stored.
    """
    if _main_loop is None or not _main_loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(
        broadcast(
            {
                "type": "new_alert",
                "payload": alert,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        _main_loop,
    )


def broadcast_budget_warning_sync(warning: Dict[str, Any]) -> None:
    """
    Thread-safe wrapper — broadcasts a budget breach warning to all WS clients.
    Called from the budget breach check job.
    """
    if _main_loop is None or not _main_loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(
        broadcast(
            {
                "type": "budget_warning",
                "payload": warning,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        _main_loop,
    )


# ---------------------------------------------------------------------------
# Heartbeat task
# ---------------------------------------------------------------------------


async def _heartbeat_loop() -> None:
    """Send a heartbeat ping to all clients every HEARTBEAT_SECONDS seconds."""
    while True:
        await asyncio.sleep(_HEARTBEAT_SECONDS)
        if _connected_clients:
            await broadcast(
                {"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}
            )


# ---------------------------------------------------------------------------
# FastAPI WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _register(websocket)

    # Send initial connection confirmation
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "message": "AnomalyIQ WebSocket connected.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    )

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await _handle_client_message(websocket, msg)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        _unregister(websocket)


async def _handle_client_message(ws: WebSocket, msg: Dict[str, Any]) -> None:
    """Process messages received from a client."""
    msg_type = msg.get("type", "")

    if msg_type == "ping":
        await ws.send_text(
            json.dumps({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
        )
    elif msg_type == "acknowledge_alert":
        alert_id = msg.get("alert_id")
        if alert_id:
            await _acknowledge_alert(alert_id, ws)
    else:
        logger.debug("Unknown WS message type: %s", msg_type)


async def _acknowledge_alert(alert_id: str, ws: WebSocket) -> None:
    """Mark an alert as acknowledged in MongoDB."""
    try:
        from backend.database.mongodb import get_db
        from bson import ObjectId

        db = get_db()
        result = db["alerts_sent"].update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_at": datetime.now(timezone.utc),
                }
            },
        )
        status = "ok" if result.modified_count > 0 else "not_found"
    except Exception as exc:
        logger.error("Acknowledge alert error: %s", exc)
        status = "error"

    await ws.send_text(
        json.dumps({"type": "alert_acknowledged", "alert_id": alert_id, "status": status})
    )
