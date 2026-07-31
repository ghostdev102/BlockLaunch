"""Player management API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from blocklaunch.server.manager import ServerManager
from blocklaunch.server.players import PlayerManager

router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────────────


class OpRequest(BaseModel):
    player: str = Field(..., min_length=1)
    level: int = Field(default=4, ge=1, le=4)


class WhitelistRequest(BaseModel):
    player: str = Field(..., min_length=1)


class BanRequest(BaseModel):
    target: str = Field(..., min_length=1)
    reason: str = Field(default="Banned by an operator")
    expires: Optional[str] = None


class KickRequest(BaseModel):
    player: str = Field(..., min_length=1)
    reason: str = Field(default="Kicked by an operator")


class GamemodeRequest(BaseModel):
    player: str = Field(..., min_length=1)
    gamemode: str = Field(..., pattern=r"^(survival|creative|adventure|spectator)$")


class TeleportRequest(BaseModel):
    player: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class GiveRequest(BaseModel):
    player: str = Field(..., min_length=1)
    item: str = Field(..., min_length=1)
    amount: int = Field(default=1, ge=1, le=2304)


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1)


# ── Helpers ───────────────────────────────────────────────────────────

def _get_player_manager(request: Request, server_name: str) -> PlayerManager:
    """Get a PlayerManager for the given server."""
    from pathlib import Path
    from blocklaunch.config import settings

    manager: ServerManager = request.app.state.server_manager
    config = manager._configs.get(server_name)
    if config:
        server_dir = Path(config.directory) if config.directory else settings.servers_dir / server_name
    else:
        server_dir = settings.servers_dir / server_name
    return PlayerManager(server_dir, server_name)


# ── OP Management ─────────────────────────────────────────────────────

@router.get("/{server_name}/ops")
async def get_ops(server_name: str, request: Request) -> dict[str, Any]:
    """Get all operators for a server."""
    pm = _get_player_manager(request, server_name)
    ops = pm.get_ops()
    return {
        "ops": [
            {"name": o.name, "uuid": o.uuid, "level": o.level,
             "bypasses_player_limit": o.bypasses_player_limit}
            for o in ops
        ]
    }


@router.post("/{server_name}/ops")
async def add_op(server_name: str, body: OpRequest, request: Request) -> dict[str, Any]:
    """Grant operator status to a player."""
    pm = _get_player_manager(request, server_name)
    entry = pm.op(body.player, level=body.level)
    return {"success": True, "data": {"name": entry.name, "level": entry.level}}


@router.delete("/{server_name}/ops/{player}")
async def remove_op(server_name: str, player: str, request: Request) -> dict[str, Any]:
    """Revoke operator status from a player."""
    pm = _get_player_manager(request, server_name)
    success = pm.deop(player)
    if success:
        return {"success": True}
    return JSONResponse(status_code=404, content={"success": False, "error": f"Player '{player}' not found in ops"})


# ── Whitelist Management ──────────────────────────────────────────────

@router.get("/{server_name}/whitelist")
async def get_whitelist(server_name: str, request: Request) -> dict[str, Any]:
    """Get all whitelisted players."""
    pm = _get_player_manager(request, server_name)
    wl = pm.get_whitelist()
    return {"whitelist": [{"name": w.name, "uuid": w.uuid} for w in wl]}


@router.post("/{server_name}/whitelist")
async def add_whitelist(server_name: str, body: WhitelistRequest, request: Request) -> dict[str, Any]:
    """Add a player to the whitelist."""
    pm = _get_player_manager(request, server_name)
    entry = pm.whitelist_add(body.player)
    return {"success": True, "data": {"name": entry.name}}


@router.delete("/{server_name}/whitelist/{player}")
async def remove_whitelist(server_name: str, player: str, request: Request) -> dict[str, Any]:
    """Remove a player from the whitelist."""
    pm = _get_player_manager(request, server_name)
    success = pm.whitelist_remove(player)
    if success:
        return {"success": True}
    return JSONResponse(status_code=404, content={"success": False, "error": f"Player '{player}' not in whitelist"})


# ── Ban Management ────────────────────────────────────────────────────

@router.get("/{server_name}/bans")
async def get_bans(server_name: str, request: Request) -> dict[str, Any]:
    """Get all banned players and IPs."""
    pm = _get_player_manager(request, server_name)
    return {
        "banned_players": [
            {"name": b.name, "uuid": b.uuid, "reason": b.reason,
             "created": b.created, "expires": b.expires}
            for b in pm.get_banned_players()
        ],
        "banned_ips": [
            {"ip": b.ip, "reason": b.reason, "created": b.created, "expires": b.expires}
            for b in pm.get_banned_ips()
        ],
    }


@router.post("/{server_name}/bans/player")
async def ban_player(server_name: str, body: BanRequest, request: Request) -> dict[str, Any]:
    """Ban a player."""
    pm = _get_player_manager(request, server_name)
    entry = pm.ban(body.target, reason=body.reason, expires=body.expires)
    return {"success": True, "data": {"name": entry.name, "reason": entry.reason}}


@router.post("/{server_name}/bans/ip")
async def ban_ip(server_name: str, body: BanRequest, request: Request) -> dict[str, Any]:
    """Ban an IP address."""
    pm = _get_player_manager(request, server_name)
    entry = pm.ban_ip(body.target, reason=body.reason, expires=body.expires)
    return {"success": True, "data": {"ip": entry.ip, "reason": entry.reason}}


@router.delete("/{server_name}/bans/player/{player}")
async def pardon_player(server_name: str, player: str, request: Request) -> dict[str, Any]:
    """Pardon a banned player."""
    pm = _get_player_manager(request, server_name)
    success = pm.pardon(player)
    if success:
        return {"success": True}
    return JSONResponse(status_code=404, content={"success": False, "error": f"Player '{player}' not found in bans"})


@router.delete("/{server_name}/bans/ip/{ip}")
async def pardon_ip(server_name: str, ip: str, request: Request) -> dict[str, Any]:
    """Pardon a banned IP."""
    pm = _get_player_manager(request, server_name)
    success = pm.pardon_ip(ip)
    if success:
        return {"success": True}
    return JSONResponse(status_code=404, content={"success": False, "error": f"IP '{ip}' not found in bans"})


# ── Live Server Commands ──────────────────────────────────────────────

@router.post("/{server_name}/kick")
async def kick_player(server_name: str, body: KickRequest, request: Request) -> dict[str, Any]:
    """Kick a player from the server."""
    pm = _get_player_manager(request, server_name)
    result = await pm.kick(body.player, reason=body.reason)
    return result


@router.post("/{server_name}/gamemode")
async def set_gamemode(server_name: str, body: GamemodeRequest, request: Request) -> dict[str, Any]:
    """Set a player's gamemode."""
    pm = _get_player_manager(request, server_name)
    result = await pm.set_gamemode(body.player, body.gamemode)
    return result


@router.post("/{server_name}/teleport")
async def teleport(server_name: str, body: TeleportRequest, request: Request) -> dict[str, Any]:
    """Teleport a player to another player."""
    pm = _get_player_manager(request, server_name)
    result = await pm.teleport(body.player, body.target)
    return result


@router.post("/{server_name}/give")
async def give_items(server_name: str, body: GiveRequest, request: Request) -> dict[str, Any]:
    """Give items to a player."""
    pm = _get_player_manager(request, server_name)
    result = await pm.give(body.player, body.item, body.amount)
    return result


@router.post("/{server_name}/time")
async def set_time(server_name: str, body: CommandRequest, request: Request) -> dict[str, Any]:
    """Set server time."""
    pm = _get_player_manager(request, server_name)
    result = await pm.time_set(body.command)
    return result


@router.post("/{server_name}/weather")
async def set_weather(server_name: str, body: CommandRequest, request: Request) -> dict[str, Any]:
    """Set server weather."""
    pm = _get_player_manager(request, server_name)
    result = await pm.weather(body.command)
    return result


@router.post("/{server_name}/save-all")
async def save_all(server_name: str, request: Request) -> dict[str, Any]:
    """Save all world data."""
    pm = _get_player_manager(request, server_name)
    result = await pm.save_all()
    return result


# ── Overview ──────────────────────────────────────────────────────────

@router.get("/{server_name}/overview")
async def get_player_overview(server_name: str, request: Request) -> dict[str, Any]:
    """Get a comprehensive player overview for a server."""
    pm = _get_player_manager(request, server_name)
    return pm.get_player_overview()
