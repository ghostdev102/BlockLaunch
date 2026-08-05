"""Console screen — live server console with command input."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, Static

from blocklaunch.server.manager import ServerManager
from blocklaunch.config import settings


class ConsoleScreen(Screen):
    """Live server console with command input."""

    TITLE = "Server Console"

    def __init__(self, server_name: str) -> None:
        super().__init__()
        self.server_name = server_name
        self._lines: list[str] = []
        self._auto_scroll = True
        self._watcher: Optional[asyncio.TimerHandle] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="console-view"):
            yield Label(f"💻 Console: {self.server_name}", classes="title")
            yield Static("", id="console-output")
            yield Input(placeholder="Type a command...", id="console-input")
            yield Footer()

    def on_mount(self) -> None:
        self._load_recent_output()
        self._start_output_watcher()

    def _load_recent_output(self) -> None:
        """Load recent console output from the log file."""
        manager = ServerManager(settings)

        async def _load():
            lines = await manager.get_console_output(self.server_name, lines=100)
            self._lines = lines[-100:] if lines else []
            self._render()

        asyncio.create_task(_load())

    def _start_output_watcher(self) -> None:
        """Watch for new server output and update the display."""
        self.set_interval(2, self._refresh_output)

    def _refresh_output(self) -> None:
        """Refresh the console output from the log file."""
        manager = ServerManager(settings)

        async def _load():
            lines = await manager.get_console_output(self.server_name, lines=200)
            self._lines = lines[-200:] if lines else []
            self._render()

        asyncio.create_task(_load())

    def _render(self) -> None:
        """Render the tracked output lines into the Static widget."""
        output = self.query_one("#console-output", Static)
        output.update("\n".join(self._lines))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        if event.input.id == "console-input":
            command = event.value.strip()
            if not command:
                return

            # Echo the command locally so it shows even if the server
            # is stopped or slow to respond.
            self._lines.append(f"> {command}")
            self._render()

            manager = ServerManager(settings)
            result = await manager.send_command(self.server_name, command)
            if not result.success:
                self._lines.append(f"⚠️ {result.error}")
                self._render()

            event.input.value = ""
