"""WebSocket route for live server console streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from blocklaunch.server.manager import ServerManager
from blocklaunch.utils.process import ServerProcess

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for live console streaming."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, server_name: str) -> None:
        await websocket.accept()
        if server_name not in self.active_connections:
            self.active_connections[server_name] = []
        self.active_connections[server_name].append(websocket)

    def disconnect(self, websocket: WebSocket, server_name: str) -> None:
        if server_name in self.active_connections:
            self.active_connections[server_name].remove(websocket)
            if not self.active_connections[server_name]:
                del self.active_connections[server_name]

    async def broadcast(self, server_name: str, message: str) -> None:
        if server_name in self.active_connections:
            dead = []
            for ws in self.active_connections[server_name]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[server_name].remove(ws)


manager = ConnectionManager()


@router.websocket("/console/{server_name}")
async def console_websocket(websocket: WebSocket, server_name: str) -> None:
    """WebSocket endpoint for live server console.

    Protocol:
    - Client connects to /ws/console/{server_name}
    - Server sends: {"type": "output", "line": "..."} for each console line
    - Client sends: {"type": "command", "command": "..."} to execute commands
    - Server sends: {"type": "status", "status": "running|stopped|..."} for status changes
    """
    await manager.connect(websocket, server_name)

    try:
        # Send recent log output first
        from blocklaunch.config import settings
        server_manager = ServerManager(settings)
        recent = await server_manager.get_console_output(server_name, lines=50)
        for line in recent:
            await websocket.send_text(json.dumps({"type": "output", "line": line}))

        # Start a background task to poll for new output
        last_line_count = len(recent)

        async def poll_output():
            nonlocal last_line_count
            while True:
                try:
                    lines = await server_manager.get_console_output(server_name, lines=200)
                    if len(lines) > last_line_count:
                        new_lines = lines[last_line_count:]
                        for line in new_lines:
                            await websocket.send_text(json.dumps({"type": "output", "line": line}))
                        last_line_count = len(lines)
                    await asyncio.sleep(1)
                except Exception:
                    await asyncio.sleep(2)

        poll_task = asyncio.create_task(poll_output())

        try:
            # Listen for incoming commands
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "command":
                        command = msg.get("command", "").strip()
                        if command:
                            result = await server_manager.send_command(server_name, command)
                            await websocket.send_text(json.dumps({
                                "type": "command_result",
                                "success": result.success,
                                "command": command,
                            }))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            poll_task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, server_name)


@router.websocket("/status/{server_name}")
async def status_websocket(websocket: WebSocket, server_name: str) -> None:
    """WebSocket endpoint for server status updates.

    Sends periodic status updates including CPU, memory, uptime.
    """
    await websocket.accept()
    try:
        from blocklaunch.config import settings
        server_manager = ServerManager(settings)

        while True:
            status = server_manager.get_server_status(server_name)
            await websocket.send_text(json.dumps({"type": "status", "data": status}))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
