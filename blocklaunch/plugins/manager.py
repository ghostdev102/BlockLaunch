"""Plugin manager — unified interface for searching and installing plugins from multiple sources."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from blocklaunch.config import BlockLaunchSettings
from blocklaunch.plugins.hangar import HangarClient, HangarProject
from blocklaunch.plugins.modrinth import ModrinthClient, ModrinthProject
from blocklaunch.plugins.spigotmc import SpigotMCClient, SpigotProject
from blocklaunch.utils.logging import setup_logging

logger = setup_logging(name="blocklaunch.plugins")


@dataclass
class PluginSearchResult:
    """Unified plugin search result across all sources."""
    id: str
    name: str
    description: str
    source: str
    downloads: int
    url: str
    icon_url: Optional[str] = None
    version: str = ""
    extra: Optional[dict[str, Any]] = None


@dataclass
class InstallResult:
    """Result of a plugin install operation."""
    success: bool
    error: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class PluginManager:
    """Manages plugin search, download, and installation across multiple sources."""

    SOURCE_MAP = {
        "modrinth": "modrinth",
        "hangar": "hangar",
        "spigotmc": "spigotmc",
        "spigot": "spigotmc",
    }

    def __init__(self, settings: BlockLaunchSettings) -> None:
        self.settings = settings
        self.modrinth = ModrinthClient()
        self.hangar = HangarClient()
        self.spigotmc = SpigotMCClient()
        self._installed: dict[str, dict[str, Any]] = {}
        self._load_installed()

    # ── Persistence ──────────────────────────────────────────────────

    def _installed_path(self) -> Path:
        return self.settings.data_dir / "installed_plugins.json"

    def _load_installed(self) -> None:
        path = self._installed_path()
        if path.exists():
            try:
                self._installed = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load installed plugins: {e}")

    def _save_installed(self) -> None:
        path = self._installed_path()
        path.write_text(json.dumps(self._installed, indent=2), encoding="utf-8")

    # ── Search ───────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        limit: int = 10,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
    ) -> list[PluginSearchResult]:
        """Search for plugins across specified sources."""
        if sources is None:
            sources = ["modrinth", "hangar", "spigotmc"]

        results: list[PluginSearchResult] = []
        tasks = []

        for source in sources:
            normalized = self.SOURCE_MAP.get(source.lower(), source.lower())
            if normalized == "modrinth":
                tasks.append(self._search_modrinth(query, limit, game_version, loader))
            elif normalized == "hangar":
                tasks.append(self._search_hangar(query, limit))
            elif normalized == "spigotmc":
                tasks.append(self._search_spigotmc(query, limit))

        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in search_results:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Search task failed: {result}")

        # Sort by downloads descending
        results.sort(key=lambda r: r.downloads, reverse=True)
        return results

    async def _search_modrinth(
        self, query: str, limit: int,
        game_version: Optional[str], loader: Optional[str],
    ) -> list[PluginSearchResult]:
        projects = await self.modrinth.search(
            query, project_type="mod", game_version=game_version, loader=loader, limit=limit,
        )
        return [
            PluginSearchResult(
                id=p.id, name=p.name, description=p.description,
                source="modrinth", downloads=p.downloads, url=p.url,
                icon_url=p.icon_url, version=p.version,
            )
            for p in projects
        ]

    async def _search_hangar(self, query: str, limit: int) -> list[PluginSearchResult]:
        projects = await self.hangar.search(query, limit=limit)
        return [
            PluginSearchResult(
                id=p.slug or p.id, name=p.name, description=p.description,
                source="hangar", downloads=p.downloads, url=p.url,
                icon_url=p.icon_url, version=p.version,
            )
            for p in projects
        ]

    async def _search_spigotmc(self, query: str, limit: int) -> list[PluginSearchResult]:
        projects = await self.spigotmc.search(query, limit=limit)
        return [
            PluginSearchResult(
                id=p.id, name=p.name, description=p.description,
                source="spigotmc", downloads=p.downloads, url=p.url,
                icon_url=p.icon_url, version=p.version,
                extra={"rating": p.rating},
            )
            for p in projects
        ]

    # ── Install ──────────────────────────────────────────────────────

    async def install(
        self,
        server_name: str,
        plugin_id: str,
        source: str,
        version_id: Optional[str] = None,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
    ) -> InstallResult:
        """Install a plugin to a server's plugins directory."""
        from blocklaunch.server.manager import ServerManager

        # Resolve server directory
        manager = ServerManager(self.settings)
        servers = manager.list_servers()
        server = next((s for s in servers if s["name"] == server_name), None)
        if not server:
            return InstallResult(success=False, error=f"Server '{server_name}' not found")

        config = manager._configs.get(server_name)
        if not config:
            return InstallResult(success=False, error=f"Server config not found for '{server_name}'")

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / server_name
        plugins_dir = server_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        # Get download URL
        normalized = self.SOURCE_MAP.get(source.lower(), source.lower())
        download_url, filename = None, None

        if normalized == "modrinth":
            result = await self.modrinth.get_download_url(
                plugin_id, game_version=game_version, loader=loader, version_id=version_id,
            )
            if result:
                download_url, filename = result
        elif normalized == "hangar":
            result = await self.hangar.get_download_url(plugin_id)
            if result:
                download_url, filename = result
        elif normalized == "spigotmc":
            result = await self.spigotmc.get_download_url(plugin_id)
            if result:
                download_url, filename = result
        else:
            return InstallResult(success=False, error=f"Unknown source: {source}")

        if not download_url:
            return InstallResult(success=False, error=f"Could not resolve download URL for {plugin_id}")

        # Download
        target_path = plugins_dir / (filename or f"{plugin_id}.jar")
        success = False

        if normalized == "modrinth":
            success = await self.modrinth.download_plugin(download_url, str(target_path))
        elif normalized == "hangar":
            success = await self.hangar.download_plugin(download_url, str(target_path))
        elif normalized == "spigotmc":
            success = await self.spigotmc.download_plugin(download_url, str(target_path))

        if not success:
            return InstallResult(success=False, error=f"Failed to download plugin {plugin_id}")

        # Record installation
        key = f"{server_name}:{plugin_id}"
        self._installed[key] = {
            "server": server_name,
            "plugin_id": plugin_id,
            "source": normalized,
            "filename": filename,
            "path": str(target_path),
            "version_id": version_id,
        }
        self._save_installed()

        logger.info(f"Installed plugin {plugin_id} to {server_name}")
        return InstallResult(success=True, data={"name": filename, "path": str(target_path)})

    # ── Uninstall ────────────────────────────────────────────────────

    async def uninstall(self, server_name: str, plugin_id: str) -> InstallResult:
        """Remove a plugin from a server."""
        from blocklaunch.server.manager import ServerManager

        manager = ServerManager(self.settings)
        config = manager._configs.get(server_name)
        if not config:
            return InstallResult(success=False, error=f"Server '{server_name}' not found")

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / server_name
        key = f"{server_name}:{plugin_id}"
        info = self._installed.get(key)

        if info and info.get("path"):
            target = Path(info["path"])
            if target.exists():
                target.unlink()
                self._installed.pop(key, None)
                self._save_installed()
                return InstallResult(success=True, data={"removed": str(target)})

        # Fallback: search plugins dir
        plugins_dir = server_dir / "plugins"
        if plugins_dir.exists():
            for jar in plugins_dir.glob("*.jar"):
                if plugin_id.lower() in jar.name.lower():
                    jar.unlink()
                    self._installed.pop(key, None)
                    self._save_installed()
                    return InstallResult(success=True, data={"removed": str(jar)})

        return InstallResult(success=False, error=f"Plugin {plugin_id} not found in {server_name}")

    # ── List installed ───────────────────────────────────────────────

    def list_installed(self, server_name: str) -> list[dict[str, Any]]:
        """List installed plugins for a server."""
        return [
            info for key, info in self._installed.items()
            if info.get("server") == server_name
        ]

    # ── Cleanup ──────────────────────────────────────────────────────

    async def close(self) -> None:
        await self.modrinth.close()
        await self.hangar.close()
        await self.spigotmc.close()
