"""
Streaming endpoints for Active Assistant.

Provides Server-Sent Events (SSE) endpoints for real-time screen monitoring,
system metrics, and agent events that can be consumed by web clients.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route

from active_assistant.core.state import state, event_bus
from active_assistant.core.monitor import screen_capture, image_to_base64
from active_assistant.core.state import event_bus as event_bus_module


async def screen_stream(request):
    """Server-sent events stream for screen captures."""
    async def event_generator():
        while True:
            try:
                from active_assistant.core.monitor import screen_capture, image_to_base64
                img = screen_capture.capture_region(0, 0, 1920, 1080)
                if img:
                    b64 = image_to_base64(img)
                    yield f"data: {json.dumps({'type': 'screen', 'image': b64})}\n\n"
                await asyncio.sleep(1.0)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def metrics_stream(request):
    """Server-sent events stream for system metrics."""
    async def event_generator():
        while True:
            try:
                from active_assistant.core.state import state
                metrics = state.metrics
                data = {
                    "type": "metrics",
                    "uptime_seconds": metrics.uptime_seconds,
                    "screens_captured": metrics.screens_captured,
                    "issues_detected": metrics.issues_detected,
                    "tools_executed": metrics.tools_executed,
                }
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(2.0)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def events_stream(request):
    """Server-sent events stream for general assistant events."""
    async def event_generator():
        # Subscribe to event bus
        event_queue = []

        def on_event(event):
            event_queue.append(event)

        event_bus.subscribe("state_changed", on_event)
        event_bus.subscribe("notification", on_event)
        event_bus.subscribe("agent_task_started", on_event)
        event_bus.subscribe("agent_task_completed", on_event)

        try:
            while True:
                if event_queue:
                    event = event_queue.pop(0)
                    yield f"data: {json.dumps({'type': event.type, 'payload': event.payload})}\n\n"
                await asyncio.sleep(0.5)
        except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def create_streaming_routes() -> list:
    """Create Starlette routes for streaming endpoints."""
    return [
        Route("/stream/screen", screen_stream),
        Route("/stream/metrics", metrics_stream),
        Route("/stream/events", events_stream),
    ]