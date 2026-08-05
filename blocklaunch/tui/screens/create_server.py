"""Create Server screen — wizard for creating a new Minecraft server."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Select, Static

from blocklaunch.server.manager import ServerManager
from blocklaunch.config import settings


class CreateServerScreen(Screen):
    """Screen for creating a new Minecraft server."""

    TITLE = "Create Server"

    MODES = [
        ("🎮 Minecraft Premium", "premium"),
        ("🔓 Minecraft Cracked", "cracked"),
        ("🦅 Eaglercraft (WSS Proxy)", "eaglercraft"),
    ]

    SERVER_TYPES = [
        ("Paper (Recommended)", "paper"),
        ("Vanilla", "vanilla"),
        ("Spigot", "spigot"),
        ("Forge", "forge"),
        ("Fabric", "fabric"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="create-form"):
            yield Label("🚀 Create New Server", classes="title")
            yield Label("")

            yield Label("Server Name:")
            yield Input(placeholder="my-server", id="server-name")

            yield Label("Description (optional):")
            yield Input(placeholder="A friendly survival server", id="server-description")

            yield Label("Server Mode:")
            yield Select(
                options=self.MODES,
                value="premium",
                id="server-mode",
            )

            yield Label("Server Software:")
            yield Select(
                options=self.SERVER_TYPES,
                value="paper",
                id="server-type",
            )

            yield Label("Minecraft Version:")
            yield Input(value="1.20.4", placeholder="1.20.4", id="mc-version")

            yield Label("Max Memory:")
            yield Input(value="2G", placeholder="2G", id="memory")

            yield Label("Server Port:")
            yield Input(value="25565", placeholder="25565", id="server-port")

            yield Label("")

            # Mode explanation
            yield Static("", id="mode-explanation")

            yield Horizontal(
                Button("✅ Create Server", id="create-btn", variant="success"),
                Button("❌ Cancel", id="cancel-btn", variant="error"),
            )

            yield Static("", id="status")
            yield Footer()

    def on_mount(self) -> None:
        self._update_mode_explanation("premium")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "server-mode":
            self._update_mode_explanation(str(event.value))

    def _update_mode_explanation(self, mode: str) -> None:
        explanations = {
            "premium": (
                "🎮 Minecraft Premium — Standard online-mode server. "
                "Players must authenticate with Mojang/Microsoft. "
                "This is the official way to run a server."
            ),
            "cracked": (
                "🔓 Minecraft Cracked — Offline-mode server. "
                "Players can join without a premium account. "
                "WARNING: Use a login plugin (like AuthMe) to prevent name spoofing!"
            ),
            "eaglercraft": (
                "🦅 Eaglercraft — Browser-based Minecraft with WSS proxy. "
                "Players can join from a web browser! "
                "Includes EaglercraftXBungee WebSocket proxy for browser connections."
            ),
        }
        widget = self.query_one("#mode-explanation", Static)
        widget.update(explanations.get(mode, ""))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.pop_screen()
            return

        if event.button.id == "create-btn":
            name = self.query_one("#server-name", Input).value.strip()
            description = self.query_one("#server-description", Input).value.strip()
            mode = str(self.query_one("#server-mode", Select).value)
            server_type = str(self.query_one("#server-type", Select).value)
            mc_version = self.query_one("#mc-version", Input).value.strip()
            memory = self.query_one("#memory", Input).value.strip()
            port_str = self.query_one("#server-port", Input).value.strip()

            status = self.query_one("#status", Static)

            if not name:
                status.update("❌ Server name is required!")
                return

            try:
                port = int(port_str)
            except ValueError:
                status.update("❌ Invalid port number!")
                return

            status.update("⏳ Creating server...")

            manager = ServerManager(settings)
            result = await manager.create_server(
                name=name,
                mode=mode,
                mc_version=mc_version,
                server_type=server_type,
                description=description,
                memory=memory,
                port=port,
                accept_eula=True,
            )

            if result.success:
                status.update(f"✅ Server '{name}' created successfully!")
                # Pop back to dashboard after a short delay
                self.app.pop_screen()
            else:
                status.update(f"❌ Failed: {result.error}")
