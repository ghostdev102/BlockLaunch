"""Plugin Browser screen — search and install plugins from Modrinth, Hangar, SpigotMC."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static

from blocklaunch.plugins.manager import PluginManager
from blocklaunch.config import settings


class PluginBrowserScreen(Screen):
    """Screen for searching and installing plugins."""

    TITLE = "Plugin Browser"

    SOURCES = [
        ("All Sources", "all"),
        ("Modrinth", "modrinth"),
        ("Hangar (PaperMC)", "hangar"),
        ("SpigotMC", "spigotmc"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-browser"):
            yield Label("🔌 Plugin Browser", classes="title")
            yield Label("Search and install plugins from Modrinth, Hangar, and SpigotMC", classes="info-label")

            yield Horizontal(
                Input(placeholder="Search plugins...", id="plugin-search-input"),
                Select(options=self.SOURCES, value="all", id="plugin-source"),
                Button("🔍 Search", id="search-btn", variant="primary"),
                classes="plugin-search",
            )

            yield ListView(id="plugin-results")
            yield Static("", id="plugin-status")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-btn":
            await self._do_search()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "plugin-search-input":
            await self._do_search()

    async def _do_search(self) -> None:
        query = self.query_one("#plugin-search-input", Input).value.strip()
        source = str(self.query_one("#plugin-source", Select).value)
        status = self.query_one("#plugin-status", Static)
        results_list = self.query_one("#plugin-results", ListView)

        if not query:
            status.update("❌ Please enter a search query")
            return

        status.update("⏳ Searching...")
        results_list.clear()

        pm = PluginManager(settings)
        try:
            sources = [source] if source != "all" else None
            results = await pm.search(query, sources=sources, limit=15)

            if not results:
                status.update("No plugins found.")
                return

            for r in results:
                item = ListItem(
                    Horizontal(
                        Label(f"[{r.source.upper()}] {r.name}", classes="plugin-name"),
                        Label(f"  ⬇️ {r.downloads:,}", classes="plugin-downloads"),
                        Label(f"  {r.description[:80]}", classes="plugin-desc"),
                    ),
                    classes="plugin-item",
                )
                item.plugin_data = r
                results_list.append(item)

            status.update(f"Found {len(results)} plugins")
        finally:
            await pm.close()
