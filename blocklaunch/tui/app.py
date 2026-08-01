"""BlockLaunch TUI main application."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Label, Static

from blocklaunch.tui.screens.dashboard import DashboardScreen
from blocklaunch.tui.screens.create_server import CreateServerScreen
from blocklaunch.tui.screens.server_detail import ServerDetailScreen
from blocklaunch.tui.screens.plugin_browser import PluginBrowserScreen
from blocklaunch.tui.screens.player_manager import PlayerManagerScreen
from blocklaunch.tui.screens.console import ConsoleScreen
from blocklaunch.config import settings


class BlockLaunchApp(App):
    """BlockLaunch — Run Minecraft servers easily, free with a simple TUI."""

    TITLE = "BlockLaunch"
    SUB_TITLE = "Run Minecraft servers easily"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("d", "show_dashboard", "Dashboard", show=True),
        Binding("c", "create_server", "Create Server", show=True),
        Binding("p", "plugin_browser", "Plugins", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_server: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DashboardScreen()
        yield Footer()

    def on_mount(self) -> None:
        self.install_screen(DashboardScreen(), "dashboard")
        self.install_screen(CreateServerScreen(), "create_server")
        self.install_screen(PluginBrowserScreen(), "plugin_browser")

    def action_show_dashboard(self) -> None:
        self.push_screen("dashboard")

    def action_create_server(self) -> None:
        self.push_screen("create_server")

    def action_plugin_browser(self) -> None:
        self.push_screen("plugin_browser")

    def open_server_detail(self, server_name: str) -> None:
        """Open the detail view for a server."""
        self._current_server = server_name
        screen = ServerDetailScreen(server_name)
        self.push_screen(screen)

    def open_console(self, server_name: str) -> None:
        """Open the console view for a server."""
        screen = ConsoleScreen(server_name)
        self.push_screen(screen)

    def open_player_manager(self, server_name: str) -> None:
        """Open the player manager for a server."""
        screen = PlayerManagerScreen(server_name)
        self.push_screen(screen)
