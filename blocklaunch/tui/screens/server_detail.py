"""Server Detail screen — view and manage a single server."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from blocklaunch.server.manager import ServerManager
from blocklaunch.config import settings


class ServerDetailScreen(Screen):
    """Screen showing details and controls for a server."""

    TITLE = "Server Detail"

    def __init__(self, server_name: str) -> None:
        super().__init__()
        self.server_name = server_name
        self._status: dict = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="server-detail"):
            yield Label(f"⚙️ Server: {self.server_name}", classes="title")
            yield Static("", id="server-info")

            yield Horizontal(
                Button("▶️ Start", id="start-btn", variant="success"),
                Button("⏹ Stop", id="stop-btn", variant="error"),
                Button("🔄 Restart", id="restart-btn", variant="warning"),
                Button("💻 Console", id="console-btn", variant="primary"),
                Button("👥 Players", id="players-btn", variant="primary"),
                Button("🔌 Plugins", id="plugins-btn", variant="primary"),
                Button("💾 Backup", id="backup-btn", variant="default"),
                Button("🗑 Delete", id="delete-btn", variant="error"),
                classes="server-actions",
            )

            yield Static("", id="status")

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        manager = ServerManager(settings)
        self._status = manager.get_server_status(self.server_name)
        info = self.query_one("#server-info", Static)

        lines = [
            f"  Name:      {self._status.get('name', 'N/A')}",
            f"  Mode:      {self._status.get('mode', 'N/A').upper()}",
            f"  Type:      {self._status.get('type', 'N/A')}",
            f"  Version:   {self._status.get('version', 'N/A')}",
            f"  Port:      {self._status.get('port', 'N/A')}",
            f"  Memory:    {self._status.get('memory', 'N/A')}",
            f"  Status:    {self._status.get('status', 'N/A').upper()}",
        ]

        if self._status.get("pid"):
            lines.append(f"  PID:       {self._status.get('pid', 'N/A')}")
        if self._status.get("uptime"):
            uptime = self._status.get("uptime", 0)
            hours = int(uptime // 3600)
            mins = int((uptime % 3600) // 60)
            lines.append(f"  Uptime:    {hours}h {mins}m")
        if self._status.get("memory_usage_mb"):
            lines.append(f"  Memory:    {self._status.get('memory_usage_mb', 0):.0f} MB")

        info.update("\n".join(lines))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        status = self.query_one("#status", Static)
        manager = ServerManager(settings)

        if event.button.id == "start-btn":
            status.update("⏳ Starting server...")
            result = await manager.start_server(self.server_name)
            if result.success:
                status.update("✅ Server started!")
            else:
                status.update(f"❌ {result.error}")
            self._refresh()

        elif event.button.id == "stop-btn":
            status.update("⏳ Stopping server...")
            result = await manager.stop_server(self.server_name)
            if result.success:
                status.update("✅ Server stopped!")
            else:
                status.update(f"❌ {result.error}")
            self._refresh()

        elif event.button.id == "restart-btn":
            status.update("⏳ Restarting server...")
            result = await manager.restart_server(self.server_name)
            if result.success:
                status.update("✅ Server restarted!")
            else:
                status.update(f"❌ {result.error}")
            self._refresh()

        elif event.button.id == "console-btn":
            self.app.open_console(self.server_name)

        elif event.button.id == "players-btn":
            self.app.open_player_manager(self.server_name)

        elif event.button.id == "plugins-btn":
            self.app.action_plugin_browser()

        elif event.button.id == "backup-btn":
            status.update("⏳ Creating backup...")
            result = await manager.create_backup(self.server_name)
            if result.success:
                size = result.data.get("size_mb", 0) if result.data else 0
                status.update(f"✅ Backup created ({size:.1f} MB)")
            else:
                status.update(f"❌ {result.error}")

        elif event.button.id == "delete-btn":
            result = await manager.delete_server(self.server_name, delete_files=True)
            if result.success:
                self.app.pop_screen()
            else:
                status.update(f"❌ {result.error}")
