"""Console screen — live server console with command input."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Static
from textual.worker import Worker, get_current_worker

from blocklaunch.server.manager import ServerManager
from blocklaunch.utils.process import ProcessManager
from blocklaunch.config import settings


class ConsoleScreen(Screen):
    """Live server console with command input."""

    TITLE = "Server Console"

    def __init__(self, server_name: str) -> None:
        super().__init__()
        self.server_name = server_name
        self._auto_scroll = True

    def compose(self) -> ComposeResult:
        with Vertical(id="console-view"):
            yield Label(f"💻 Console: {self.server_name}", classes="title")
            yield Static("", id="console-output")
            yield Input(placeholder="Type a command...", id="console-input")

    def on_mount(self) -> None:
        self._load_recent_output()
        self._start_output_watcher()

    def _load_recent_output(self) -> None:
        """Load recent console output from the log file."""
        manager = ServerManager(settings)
        output = self.query_one("#console-output", Static)

        async def _load():
            lines = await manager.get_console_output(self.server_name, lines=100)
            if lines:
                output.update("\n".join(lines[-100:]))

        asyncio.create_task(_load())

    def _start_output_watcher(self) -> None:
        """Watch for new server output and update the display."""
        self._watcher = self.set_interval(2, self._refresh_output)

    def _refresh_output(self) -> None:
        """Refresh the console output from the log file."""
        manager = ServerManager(settings)
        output = self.query_one("#console-output", Static)

        async def _load():
            lines = await manager.get_console_output(self.server_name, lines=200)
            if lines:
                output.update("\n".join(lines[-200:]))

        asyncio.create_task(_load())

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        if event.input.id == "console-input":
            command = event.value.strip()
            if not command:
                return

            manager = ServerManager(settings)
            result = await manager.send_command(self.server_name, command)

            # Show the command in the output
            output = self.query_one("#console-output", Static)
            current = output.renderable or ""
            output.update(f"{current}\n> {command}")

            event.input.value = ""
