"""Plugin management API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from blocklaunch.plugins.manager import PluginManager

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    sources: Optional[list[str]] = Field(default=None)
    limit: int = Field(default=10, ge=1, le=50)
    game_version: Optional[str] = None
    loader: Optional[str] = None


class InstallRequest(BaseModel):
    server_name: str = Field(..., min_length=1)
    plugin_id: str = Field(..., min_length=1)
    source: str = Field(..., pattern=r"^(modrinth|hangar|spigotmc|spigot)$")
    version_id: Optional[str] = None
    game_version: Optional[str] = None
    loader: Optional[str] = None


class UninstallRequest(BaseModel):
    server_name: str = Field(..., min_length=1)
    plugin_id: str = Field(..., min_length=1)


def _get_plugin_manager(request: Request) -> PluginManager:
    """Get or create a PluginManager instance."""
    if request.app.state.plugin_manager is None:
        from blocklaunch.config import settings
        request.app.state.plugin_manager = PluginManager(settings)
    return request.app.state.plugin_manager


@router.post("/search")
async def search_plugins(body: SearchRequest, request: Request) -> dict[str, Any]:
    """Search for plugins across sources."""
    pm = _get_plugin_manager(request)
    results = await pm.search(
        query=body.query,
        sources=body.sources,
        limit=body.limit,
        game_version=body.game_version,
        loader=body.loader,
    )
    return {
        "success": True,
        "results": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "source": r.source,
                "downloads": r.downloads,
                "url": r.url,
                "icon_url": r.icon_url,
                "version": r.version,
            }
            for r in results
        ],
    }


@router.post("/install")
async def install_plugin(body: InstallRequest, request: Request) -> dict[str, Any]:
    """Install a plugin to a server."""
    pm = _get_plugin_manager(request)
    result = await pm.install(
        server_name=body.server_name,
        plugin_id=body.plugin_id,
        source=body.source,
        version_id=body.version_id,
        game_version=body.game_version,
        loader=body.loader,
    )
    if result.success:
        return {"success": True, "data": result.data}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.post("/uninstall")
async def uninstall_plugin(body: UninstallRequest, request: Request) -> dict[str, Any]:
    """Uninstall a plugin from a server."""
    pm = _get_plugin_manager(request)
    result = await pm.uninstall(server_name=body.server_name, plugin_id=body.plugin_id)
    if result.success:
        return {"success": True, "data": result.data}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.get("/installed/{server_name}")
async def list_installed(server_name: str, request: Request) -> list[dict[str, Any]]:
    """List installed plugins for a server."""
    pm = _get_plugin_manager(request)
    return pm.list_installed(server_name)
