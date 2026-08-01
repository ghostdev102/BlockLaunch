"""Dashboard screen — main overview of all servers."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from blocklaunch.server.manager import ServerManager
from blocklaunch.config import settings


class ServerListItem(ListItem):
    """A server list item."""

    def __init__(self, server_data: dict) -> None:
        super().__init__()
        self.server_data = server_data

    def compose(self) -> ComposeResult:
        name = self.server_data.get("name", "unknown")
        mode = self.server_data.get("mode", "unknown")
        status = self.server_data.get("status", "unknown")
        version = self.server_data.get("version", "unknown")
        port = self.server_data.get("port", 25565)
        server_type = self.server_data.get("type", "unknown")

        # Status emoji
        status_emoji = "🟢" if status == "running" else "🔴" if status == "stopped" else "🟡"

        # Mode label
        mode_label = mode.upper()
        if mode == "eaglercraft":
            mode_class = "mode-eaglercraft"
        elif mode == "cracked":
            mode_class = "mode-cracked"
        else:
            mode_class = "mode-premium"

        yield Horizontal(
            Label(f"{status_emoji}", classes="status-dot"),
            Label(f" {name}", classes="server-name"),
            Label(f" [{mode_label}] ", classes=mode_class),
            Label(f" {server_type}/{version}", classes="server-type"),
            Label(f" :{port}", classes="server-port"),
            classes="server-item",
        )


class DashboardScreen(Screen):
    """Dashboard screen showing all servers and their status."""

    TITLE = "BlockLaunch Dashboard"

    class ServerSelected(Message):
        """Message sent when a server is selected."""

        def __init__(self, server_name: str) -> None:
            super().__init__()
            self.server_name = server_name

    def compose(self) -> ComposeResult:
        with Vertical(id="dashboard"):
            yield Label("🚀 BlockLaunch Dashboard", classes="title")
            yield Label("Select a server to manage, or press [C] to create a new one.", classes="info-label")
            yield ListView(id="server-list")
            yield Horizontal(
                Button("🔄 Refresh", id="refresh-btn", variant="primary"),
                Button("➕ Create Server", id="create-btn", variant="success"),
                classes="dashboard-actions",
            )

    def on_mount(self) -> None:
        self._load_servers()

    @staticmethod
    def _load_servers() -> list[dict]:
        """Load servers from the server manager."""
        manager = ServerManager(settings)
        return manager.list_servers()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-btn":
            self._refresh()
        elif event.button.id == "create-btn":
            self.app.action_create_server()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ServerListItem):
            self.app.open_server_detail(item.server_data["name"])

    def _refresh(self) -> None:
        list_view = self.query_one("#server-list", ListView)
        list_view.clear()
        servers = self._load_servers()
        for server in servers:
            list_view.append(ServerListItem(server))

    def _load_servers(self) -> list[dict]:
        manager = ServerManager(settings)
        return manager.list_servers()
