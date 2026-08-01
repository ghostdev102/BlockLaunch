"""Player management module — ops, bans, whitelist, IP bans, pardons, and more."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from blocklaunch.utils.logging import setup_logging

logger = setup_logging(name="blocklaunch.players")


# ── Data models ──────────────────────────────────────────────────────


class PlayerRank(str, Enum):
    """Player rank/permission level."""
    OP_4 = "4"  # Full OP
    OP_3 = "3"  # OP
    OP_2 = "2"  # Reduced OP
    OP_1 = "1"  # Minimal OP
    NORMAL = "0"


class BanType(str, Enum):
    """Ban type."""
    PLAYER = "player"
    IP = "ip"


@dataclass
class PlayerInfo:
    """Information about a player."""
    name: str
    uuid: Optional[str] = None
    online: bool = False
    op_level: int = 0
    whitelisted: bool = False
    banned: bool = False
    ip_banned: bool = False
    last_seen: Optional[str] = None
    last_position: Optional[str] = None
    game_mode: Optional[str] = None
    ping: Optional[int] = None
    display_name: Optional[str] = None


@dataclass
class BanEntry:
    """A ban entry from banned-players.json or banned-ips.json."""
    uuid: Optional[str] = None
    name: Optional[str] = None
    created: Optional[str] = None
    source: Optional[str] = None
    expires: Optional[str] = None
    reason: Optional[str] = None
    ip: Optional[str] = None


@dataclass
class OpEntry:
    """An OP entry from ops.json."""
    uuid: str
    name: str
    level: int
    bypasses_player_limit: bool = False


@dataclass
class WhitelistEntry:
    """A whitelist entry from whitelist.json."""
    uuid: str
    name: str


# ── Player file parsers ──────────────────────────────────────────────


class PlayerFileManager:
    """Reads and writes Minecraft player management files.

    Supports:
      - ops.json
      - whitelist.json
      - banned-players.json
      - banned-ips.json
      - usercache.json
    """

    def __init__(self, server_dir: Path) -> None:
        self.server_dir = server_dir

    # ── ops.json ─────────────────────────────────────────────────────

    def read_ops(self) -> list[OpEntry]:
        path = self.server_dir / "ops.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                OpEntry(
                    uuid=e.get("uuid", ""),
                    name=e.get("name", ""),
                    level=e.get("level", 0),
                    bypasses_player_limit=e.get("bypassesPlayerLimit", False),
                )
                for e in data
            ]
        except Exception as e:
            logger.error(f"Failed to read ops.json: {e}")
            return []

    def write_ops(self, entries: list[OpEntry]) -> None:
        path = self.server_dir / "ops.json"
        data = [
            {
                "uuid": e.uuid,
                "name": e.name,
                "level": e.level,
                "bypassesPlayerLimit": e.bypasses_player_limit,
            }
            for e in entries
        ]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_op(self, name: str, uuid_str: Optional[str] = None, level: int = 4,
               bypasses_player_limit: bool = False) -> OpEntry:
        """Add an operator. If uuid is unknown, will resolve later."""
        entries = self.read_ops()
        # Remove existing entry for same name
        entries = [e for e in entries if e.name.lower() != name.lower()]
        if not uuid_str:
            # Try to find in usercache
            uuid_str = self._resolve_uuid(name) or str(uuid.uuid4())
        entry = OpEntry(uuid=uuid_str, name=name, level=level,
                        bypasses_player_limit=bypasses_player_limit)
        entries.append(entry)
        self.write_ops(entries)
        logger.info(f"Added OP: {name} (level {level})")
        return entry

    def remove_op(self, name: str) -> bool:
        """Remove an operator."""
        entries = self.read_ops()
        original_len = len(entries)
        entries = [e for e in entries if e.name.lower() != name.lower()]
        if len(entries) < original_len:
            self.write_ops(entries)
            logger.info(f"Removed OP: {name}")
            return True
        return False

    # ── whitelist.json ────────────────────────────────────────────────

    def read_whitelist(self) -> list[WhitelistEntry]:
        path = self.server_dir / "whitelist.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                WhitelistEntry(uuid=e.get("uuid", ""), name=e.get("name", ""))
                for e in data
            ]
        except Exception as e:
            logger.error(f"Failed to read whitelist.json: {e}")
            return []

    def write_whitelist(self, entries: list[WhitelistEntry]) -> None:
        path = self.server_dir / "whitelist.json"
        data = [{"uuid": e.uuid, "name": e.name} for e in entries]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_whitelist(self, name: str, uuid_str: Optional[str] = None) -> WhitelistEntry:
        """Add a player to the whitelist."""
        entries = self.read_whitelist()
        # Check if already whitelisted
        if any(e.name.lower() == name.lower() for e in entries):
            return WhitelistEntry(uuid=uuid_str or "", name=name)
        if not uuid_str:
            uuid_str = self._resolve_uuid(name) or str(uuid.uuid4())
        entry = WhitelistEntry(uuid=uuid_str, name=name)
        entries.append(entry)
        self.write_whitelist(entries)
        logger.info(f"Added to whitelist: {name}")
        return entry

    def remove_whitelist(self, name: str) -> bool:
        """Remove a player from the whitelist."""
        entries = self.read_whitelist()
        original_len = len(entries)
        entries = [e for e in entries if e.name.lower() != name.lower()]
        if len(entries) < original_len:
            self.write_whitelist(entries)
            logger.info(f"Removed from whitelist: {name}")
            return True
        return False

    # ── banned-players.json ───────────────────────────────────────────

    def read_banned_players(self) -> list[BanEntry]:
        path = self.server_dir / "banned-players.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [self._parse_ban_entry(e) for e in data]
        except Exception as e:
            logger.error(f"Failed to read banned-players.json: {e}")
            return []

    def write_banned_players(self, entries: list[BanEntry]) -> None:
        path = self.server_dir / "banned-players.json"
        data = [self._serialize_ban_entry(e) for e in entries]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def ban_player(self, name: str, reason: str = "Banned by an operator",
                   source: str = "BlockLaunch", expires: Optional[str] = None,
                   uuid_str: Optional[str] = None) -> BanEntry:
        """Ban a player."""
        entries = self.read_banned_players()
        # Remove existing ban for same name
        entries = [e for e in entries if e.name and e.name.lower() != name.lower()]
        if not uuid_str:
            uuid_str = self._resolve_uuid(name) or str(uuid.uuid4())
        entry = BanEntry(
            uuid=uuid_str, name=name,
            created=datetime.utcnow().isoformat(),
            source=source, expires=expires or "forever",
            reason=reason,
        )
        entries.append(entry)
        self.write_banned_players(entries)
        logger.info(f"Banned player: {name} (reason: {reason})")
        return entry

    def unban_player(self, name: str) -> bool:
        """Pardon a banned player."""
        entries = self.read_banned_players()
        original_len = len(entries)
        entries = [e for e in entries if not e.name or e.name.lower() != name.lower()]
        if len(entries) < original_len:
            self.write_banned_players(entries)
            logger.info(f"Unbanned player: {name}")
            return True
        return False

    # ── banned-ips.json ───────────────────────────────────────────────

    def read_banned_ips(self) -> list[BanEntry]:
        path = self.server_dir / "banned-ips.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [self._parse_ban_entry(e) for e in data]
        except Exception as e:
            logger.error(f"Failed to read banned-ips.json: {e}")
            return []

    def write_banned_ips(self, entries: list[BanEntry]) -> None:
        path = self.server_dir / "banned-ips.json"
        data = [self._serialize_ban_entry(e) for e in entries]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def ban_ip(self, ip: str, reason: str = "Banned by an operator",
               source: str = "BlockLaunch", expires: Optional[str] = None) -> BanEntry:
        """Ban an IP address."""
        entries = self.read_banned_ips()
        entries = [e for e in entries if e.ip != ip]
        entry = BanEntry(
            ip=ip,
            created=datetime.utcnow().isoformat(),
            source=source, expires=expires or "forever",
            reason=reason,
        )
        entries.append(entry)
        self.write_banned_ips(entries)
        logger.info(f"Banned IP: {ip} (reason: {reason})")
        return entry

    def unban_ip(self, ip: str) -> bool:
        """Pardon a banned IP address."""
        entries = self.read_banned_ips()
        original_len = len(entries)
        entries = [e for e in entries if e.ip != ip]
        if len(entries) < original_len:
            self.write_banned_ips(entries)
            logger.info(f"Unbanned IP: {ip}")
            return True
        return False

    # ── usercache.json ────────────────────────────────────────────────

    def read_usercache(self) -> list[dict[str, Any]]:
        """Read the usercache.json for UUID resolution."""
        path = self.server_dir / "usercache.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _resolve_uuid(self, name: str) -> Optional[str]:
        """Try to resolve a player's UUID from usercache or Mojang API."""
        # Try usercache first
        for entry in self.read_usercache():
            if entry.get("name", "").lower() == name.lower():
                return entry.get("uuid")

        # Try Mojang API
        try:
            import httpx
            resp = httpx.get(f"https://api.mojang.com/users/profiles/minecraft/{name}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                raw_id = data.get("id", "")
                # Format UUID with dashes
                if len(raw_id) == 32:
                    formatted = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
                    return formatted
                return raw_id
        except Exception:
            pass

        return None

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_ban_entry(data: dict) -> BanEntry:
        return BanEntry(
            uuid=data.get("uuid"),
            name=data.get("name"),
            created=data.get("created"),
            source=data.get("source"),
            expires=data.get("expires"),
            reason=data.get("reason"),
            ip=data.get("ip"),
        )

    @staticmethod
    def _serialize_ban_entry(entry: BanEntry) -> dict:
        d = {}
        if entry.uuid:
            d["uuid"] = entry.uuid
        if entry.name:
            d["name"] = entry.name
        d["created"] = entry.created or datetime.utcnow().isoformat()
        d["source"] = entry.source or "BlockLaunch"
        d["expires"] = entry.expires or "forever"
        d["reason"] = entry.reason or "Banned by an operator"
        if entry.ip:
            d["ip"] = entry.ip
        return d


# ── High-level player manager ────────────────────────────────────────


class PlayerManager:
    """High-level player management for a Minecraft server.

    This wraps PlayerFileManager and also provides in-game command passthrough
    for live servers (kick, gamemode, tp, etc.).
    """

    def __init__(self, server_dir: Path, server_name: str = "") -> None:
        self.server_dir = server_dir
        self.server_name = server_name
        self.file_mgr = PlayerFileManager(server_dir)

    # ── OP management ────────────────────────────────────────────────

    def get_ops(self) -> list[OpEntry]:
        """Get all operators."""
        return self.file_mgr.read_ops()

    def op(self, name: str, level: int = 4) -> OpEntry:
        """Grant operator status to a player."""
        return self.file_mgr.add_op(name, level=level)

    def deop(self, name: str) -> bool:
        """Revoke operator status from a player."""
        return self.file_mgr.remove_op(name)

    # ── Whitelist management ─────────────────────────────────────────

    def get_whitelist(self) -> list[WhitelistEntry]:
        """Get all whitelisted players."""
        return self.file_mgr.read_whitelist()

    def whitelist_add(self, name: str) -> WhitelistEntry:
        """Add a player to the whitelist."""
        return self.file_mgr.add_whitelist(name)

    def whitelist_remove(self, name: str) -> bool:
        """Remove a player from the whitelist."""
        return self.file_mgr.remove_whitelist(name)

    # ── Ban management ───────────────────────────────────────────────

    def get_banned_players(self) -> list[BanEntry]:
        """Get all banned players."""
        return self.file_mgr.read_banned_players()

    def get_banned_ips(self) -> list[BanEntry]:
        """Get all banned IP addresses."""
        return self.file_mgr.read_banned_ips()

    def ban(self, name: str, reason: str = "Banned by an operator",
            expires: Optional[str] = None) -> BanEntry:
        """Ban a player."""
        return self.file_mgr.ban_player(name, reason=reason, expires=expires)

    def ban_ip(self, ip: str, reason: str = "Banned by an operator",
               expires: Optional[str] = None) -> BanEntry:
        """Ban an IP address."""
        return self.file_mgr.ban_ip(ip, reason=reason, expires=expires)

    def pardon(self, name: str) -> bool:
        """Pardon a banned player."""
        return self.file_mgr.unban_player(name)

    def pardon_ip(self, ip: str) -> bool:
        """Pardon a banned IP address."""
        return self.file_mgr.unban_ip(ip)

    # ── Live server commands (via server process stdin) ──────────────

    async def kick(self, name: str, reason: str = "Kicked by an operator") -> dict[str, Any]:
        """Kick a player from the server (requires running server)."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'kick {name} {reason}')
        return {"success": result.success, "player": name, "reason": reason}

    async def set_gamemode(self, name: str, gamemode: str) -> dict[str, Any]:
        """Set a player's gamemode."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'gamemode {gamemode} {name}')
        return {"success": result.success, "player": name, "gamemode": gamemode}

    async def teleport(self, player: str, target: str) -> dict[str, Any]:
        """Teleport a player to another player."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'tp {player} {target}')
        return {"success": result.success, "player": player, "target": target}

    async def teleport_coords(self, player: str, x: float, y: float, z: float) -> dict[str, Any]:
        """Teleport a player to coordinates."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'tp {player} {x} {y} {z}')
        return {"success": result.success, "player": player, "coords": f"{x} {y} {z}"}

    async def give(self, player: str, item: str, amount: int = 1) -> dict[str, Any]:
        """Give items to a player."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'give {player} {item} {amount}')
        return {"success": result.success, "player": player, "item": item, "amount": amount}

    async def say(self, message: str) -> dict[str, Any]:
        """Broadcast a message to the server."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'say {message}')
        return {"success": result.success, "message": message}

    async def msg(self, player: str, message: str) -> dict[str, Any]:
        """Send a private message to a player."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'msg {player} {message}')
        return {"success": result.success, "player": player, "message": message}

    async def time_set(self, time_str: str) -> dict[str, Any]:
        """Set the server time (day, night, noon, midnight, or ticks)."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'time set {time_str}')
        return {"success": result.success, "time": time_str}

    async def weather(self, weather: str) -> dict[str, Any]:
        """Set the weather (clear, rain, thunder)."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, f'weather {weather}')
        return {"success": result.success, "weather": weather}

    async def save_all(self) -> dict[str, Any]:
        """Save all world data."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, 'save-all')
        return {"success": result.success}

    async def whitelist_toggle(self, enabled: bool) -> dict[str, Any]:
        """Enable or disable the whitelist."""
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings

        cmd = "whitelist on" if enabled else "whitelist off"
        manager = ServerManager(settings)
        result = await manager.send_command(self.server_name, cmd)
        return {"success": result.success, "enabled": enabled}

    # ── Comprehensive player overview ────────────────────────────────

    def get_player_overview(self) -> dict[str, Any]:
        """Get a comprehensive overview of all player management data."""
        ops = self.file_mgr.read_ops()
        whitelist = self.file_mgr.read_whitelist()
        banned = self.file_mgr.read_banned_players()
        banned_ips = self.file_mgr.read_banned_ips()

        return {
            "ops": [
                {"name": o.name, "uuid": o.uuid, "level": o.level,
                 "bypasses_player_limit": o.bypasses_player_limit}
                for o in ops
            ],
            "whitelist": [
                {"name": w.name, "uuid": w.uuid} for w in whitelist
            ],
            "banned_players": [
                {"name": b.name, "uuid": b.uuid, "reason": b.reason,
                 "created": b.created, "expires": b.expires}
                for b in banned
            ],
            "banned_ips": [
                {"ip": b.ip, "reason": b.reason, "created": b.created, "expires": b.expires}
                for b in banned_ips
            ],
        }
