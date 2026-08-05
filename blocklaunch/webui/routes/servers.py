"""Server management API routes and page routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from blocklaunch.server.manager import ServerManager

router = APIRouter()
page_router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────────────


class CreateServerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    mode: str = Field(..., pattern=r"^(premium|cracked|eaglercraft)$")
    server_type: str = Field(default="paper", pattern=r"^(vanilla|paper|spigot|forge|fabric)$")
    mc_version: str = Field(default="1.20.4")
    description: str = Field(default="", max_length=200)
    memory: str = Field(default="2G")
    port: int = Field(default=25565, ge=1, le=65535)
    accept_eula: bool = Field(default=True)
    skip_java_check: bool = Field(default=False, description="Skip Java validation (for testing or when Java will be installed later)")
    skip_download: bool = Field(default=False, description="Skip JAR download (creates config & directory only)")


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=1024)


class UpdatePropertiesRequest(BaseModel):
    properties: dict[str, Any]


# ── API Routes ───────────────────────────────────────────────────────


@router.get("")
async def list_servers(request: Request) -> list[dict[str, Any]]:
    """List all servers."""
    manager: ServerManager = request.app.state.server_manager
    return manager.list_servers()


@router.get("/versions/{server_type}")
async def get_versions(server_type: str, request: Request) -> list[str]:
    """Get available versions for a server type."""
    manager: ServerManager = request.app.state.server_manager
    return await manager.get_available_versions(server_type)


@router.post("")
async def create_server(body: CreateServerRequest, request: Request) -> dict[str, Any]:
    """Create a new server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.create_server(
        name=body.name,
        mode=body.mode,
        mc_version=body.mc_version,
        server_type=body.server_type,
        description=body.description,
        memory=body.memory,
        port=body.port,
        accept_eula=body.accept_eula,
        skip_java_check=body.skip_java_check,
        skip_download=body.skip_download,
    )
    if result.success:
        return {"success": True, "data": result.data}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.get("/{name}")
async def get_server(name: str, request: Request) -> dict[str, Any]:
    """Get server details."""
    manager: ServerManager = request.app.state.server_manager
    status = manager.get_server_status(name)
    if status.get("error"):
        return JSONResponse(status_code=404, content={"error": status["error"]})
    return status


@router.post("/{name}/start")
async def start_server(name: str, request: Request) -> dict[str, Any]:
    """Start a server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.start_server(name)
    if result.success:
        return {"success": True, "data": result.data}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.post("/{name}/stop")
async def stop_server(name: str, request: Request) -> dict[str, Any]:
    """Stop a server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.stop_server(name)
    if result.success:
        return {"success": True}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.post("/{name}/restart")
async def restart_server(name: str, request: Request) -> dict[str, Any]:
    """Restart a server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.restart_server(name)
    if result.success:
        return {"success": True}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.post("/{name}/command")
async def send_command(name: str, body: CommandRequest, request: Request) -> dict[str, Any]:
    """Send a command to a running server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.send_command(name, body.command)
    if result.success:
        return {"success": True}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.get("/{name}/console")
async def get_console(name: str, request: Request, lines: int = 100) -> list[str]:
    """Get recent console output."""
    manager: ServerManager = request.app.state.server_manager
    return await manager.get_console_output(name, lines=lines)


@router.get("/{name}/properties")
async def get_properties(name: str, request: Request) -> dict[str, Any]:
    """Get server properties."""
    manager: ServerManager = request.app.state.server_manager
    props = await manager.get_server_properties(name)
    if props:
        return props.to_dict()
    return JSONResponse(status_code=404, content={"error": "Properties not found"})


@router.put("/{name}/properties")
async def update_properties(name: str, body: UpdatePropertiesRequest, request: Request) -> dict[str, Any]:
    """Update server properties."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.update_server_properties(name, body.properties)
    if result.success:
        return {"success": True}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.post("/{name}/backup")
async def create_backup(name: str, request: Request) -> dict[str, Any]:
    """Create a backup of a server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.create_backup(name)
    if result.success:
        return {"success": True, "data": result.data}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


@router.delete("/{name}")
async def delete_server(name: str, delete_files: bool = False, request: Request = None) -> dict[str, Any]:
    """Delete a server."""
    manager: ServerManager = request.app.state.server_manager
    result = await manager.delete_server(name, delete_files=delete_files)
    if result.success:
        return {"success": True}
    return JSONResponse(status_code=400, content={"success": False, "error": result.error})


# ── Page Routes (HTML) ───────────────────────────────────────────────


@page_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page."""
    templates = request.app.state.templates
    manager: ServerManager = request.app.state.server_manager
    servers = manager.list_servers()
    return templates.TemplateResponse(request, "dashboard.html", {
        "servers": servers, "page": "dashboard"
    })


@page_router.get("/server/{name}", response_class=HTMLResponse)
async def server_detail(name: str, request: Request):
    """Server detail page."""
    templates = request.app.state.templates
    manager: ServerManager = request.app.state.server_manager
    status = manager.get_server_status(name)
    return templates.TemplateResponse(request, "server_detail.html", {
        "server": status, "page": "server"
    })


@page_router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request):
    """Create server page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "create_server.html", {
        "page": "create"
    })


@page_router.get("/players/{name}", response_class=HTMLResponse)
async def players_page(name: str, request: Request):
    """Player management page."""
    templates = request.app.state.templates
    manager: ServerManager = request.app.state.server_manager
    from blocklaunch.server.players import PlayerManager
    from blocklaunch.config import settings
    config = manager._configs.get(name)
    if config:
        from pathlib import Path
        server_dir = Path(config.directory) if config.directory else settings.servers_dir / name
        pm = PlayerManager(server_dir, name)
        overview = pm.get_player_overview()
    else:
        overview = {"ops": [], "whitelist": [], "banned_players": [], "banned_ips": []}
    return templates.TemplateResponse(request, "players.html", {
        "server_name": name, "overview": overview, "page": "players"
    })


@page_router.get("/plugins")
@page_router.get("/plugins/{server_name}")
async def plugins_page(request: Request, server_name: Optional[str] = None):
    """Plugin browser page (optionally scoped to a server)."""
    templates = request.app.state.templates
    manager: ServerManager = request.app.state.server_manager
    servers = manager.list_servers()
    from blocklaunch.plugins.manager import PluginManager
    pm = PluginManager(request.app.state.settings)

    installed = []
    if server_name:
        installed = pm.list_installed(server_name)
    elif servers:
        server_name = servers[0]["name"]
        installed = pm.list_installed(server_name)

    return templates.TemplateResponse(request, "plugins.html", {
        "servers": servers, "selected_server": server_name,
        "installed": installed, "page": "plugins",
    })
