"""Plugin Browser screen — search, install and uninstall plugins for a server."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Select, Static

from blocklaunch.plugins.manager import PluginManager
from blocklaunch.config import settings
from blocklaunch.server.manager import ServerManager


class PluginBrowserScreen(Screen):
    """Screen for searching and installing plugins for a specific server."""

    TITLE = "Plugin Browser"

    SOURCES = [
        ("All Sources", "all"),
        ("Modrinth", "modrinth"),
        ("Hangar (PaperMC)", "hangar"),
        ("SpigotMC", "spigotmc"),
    ]

    def __init__(self, server_name: Optional[str] = None) -> None:
        super().__init__()
        self.server_name = server_name
        self._pm: Optional[PluginManager] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-browser"):
            yield Label("🔌 Plugin Browser", classes="title")

            # Server + source selection
            yield Horizontal(
                Label("Server:", classes="form-label"),
                Select(options=[], id="server-select"),
                Select(options=self.SOURCES, value="all", id="plugin-source"),
                classes="plugin-search",
            )

            # Search bar
            yield Horizontal(
                Input(placeholder="Search plugins...", id="plugin-search-input"),
                Button("🔍 Search", id="search-btn", variant="primary"),
                classes="plugin-search",
            )

            yield Label("📦 Installed Plugins", classes="section-label")
            yield ListView(id="installed-list")
            yield Label("🔎 Search Results (Enter to install)", classes="section-label")
            yield ListView(id="plugin-results")
            yield Static("", id="plugin-status")
            yield Footer()

    def on_mount(self) -> None:
        self._populate_servers()
        self._load_installed()

    def _get_pm(self) -> PluginManager:
        if self._pm is None:
            self._pm = PluginManager(settings)
        return self._pm

    def _populate_servers(self) -> None:
        """Populate the server selector with all known servers."""
        manager = ServerManager(settings)
        servers = manager.list_servers()
        select = self.query_one("#server-select", Select)
        select.set_options([(s["name"], s["name"]) for s in servers])

        if not servers:
            status = self.query_one("#plugin-status", Static)
            status.update("❌ No servers found. Create a server first!")
            return

        # Choose the requested server, else the first one
        if self.server_name and any(s["name"] == self.server_name for s in servers):
            select.value = self.server_name
        else:
            self.server_name = servers[0]["name"]
            select.value = self.server_name

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "server-select":
            self.server_name = str(event.value) if event.value else None
            self._load_installed()

    def _load_installed(self) -> None:
        """Load and display the plugins installed on the current server."""
        if not self.server_name:
            return
        pm = self._get_pm()
        installed = pm.list_installed(self.server_name)
        installed_list = self.query_one("#installed-list", ListView)
        installed_list.clear()

        if not installed:
            installed_list.append(
                ListItem(Label("  No plugins installed yet", classes="muted"))
            )
            return

        for info in installed:
            name = info.get("filename") or info.get("plugin_id") or "unknown"
            item = ListItem(
                Label(f"  📦 {name}   [{info.get('source', '?')}]"),
                id=f"installed-{info.get('plugin_id', '')}",
            )
            installed_list.append(item)

    async def _do_search(self) -> None:
        query = self.query_one("#plugin-search-input", Input).value.strip()
        source = str(self.query_one("#plugin-source", Select).value)
        status = self.query_one("#plugin-status", Static)
        results_list = self.query_one("#plugin-results", ListView)

        if not self.server_name:
            status.update("❌ Please select a server first")
            return
        if not query:
            status.update("❌ Please enter a search query")
            return

        status.update("⏳ Searching...")
        results_list.clear()

        pm = self._get_pm()
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
                        Label(f"  {r.description[:60]}", classes="plugin-desc"),
                    ),
                    classes="plugin-item",
                )
                item.plugin_data = r
                results_list.append(item)

            status.update(f"Found {len(results)} plugins")
        finally:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-btn":
            await self._do_search()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "plugin-search-input":
            await self._do_search()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        status = self.query_one("#plugin-status", Static)

        if not self.server_name:
            status.update("❌ Please select a server first")
            return

        pm = self._get_pm()

        # Installing from search results
        if event.list_view.id == "plugin-results":
            plugin = getattr(item, "plugin_data", None)
            if not plugin:
                return
            status.update(f"⏳ Installing {plugin.name}...")
            result = await pm.install(
                server_name=self.server_name,
                plugin_id=plugin.id,
                source=plugin.source,
            )
            if result.success:
                status.update(f"✅ Installed {result.data.get('name', plugin.name)}")
                self._load_installed()
            else:
                status.update(f"❌ {result.error}")

        # Uninstalling from the installed list
        elif event.list_view.id == "installed-list":
            plugin_id = item.id.removeprefix("installed-") if item.id else ""
            if not plugin_id:
                return
            result = await pm.uninstall(self.server_name, plugin_id)
            if result.success:
                status.update(f"✅ Removed {result.data.get('removed', plugin_id)}")
                self._load_installed()
            else:
                status.update(f"❌ {result.error}")

    def on_unmount(self) -> None:
        if self._pm is not None:
            import asyncio
            asyncio.create_task(self._pm.close())
            self._pm = None
