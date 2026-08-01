"""Server properties management — parse and modify server.properties."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional


class ServerProperties:
    """Manages a Minecraft server.properties file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._props: dict[str, str] = {}
        self._comments: dict[str, str] = {}
        if path.exists():
            self.load()

    def load(self) -> None:
        """Load properties from file."""
        self._props.clear()
        self._comments.clear()
        current_comment_lines: list[str] = []

        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                current_comment_lines.append(line)
                continue

            match = re.match(r"^([a-zA-Z._-]+)\s*=\s*(.*)$", stripped)
            if match:
                key, value = match.group(1), match.group(2)
                self._props[key] = value
                if current_comment_lines:
                    self._comments[key] = "\n".join(current_comment_lines)
                    current_comment_lines = []
            else:
                current_comment_lines = []

    def save(self) -> None:
        """Save properties to file."""
        lines: list[str] = []
        written_keys: set[str] = set()

        # Preserve original order and comments
        if self.path.exists():
            current_comment_lines: list[str] = []
            for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    current_comment_lines.append(line)
                    continue

                match = re.match(r"^([a-zA-Z._-]+)\s*=\s*(.*)$", stripped)
                if match:
                    key = match.group(1)
                    if key in self._props:
                        for cl in current_comment_lines:
                            lines.append(cl)
                        lines.append(f"{key}={self._props[key]}")
                        written_keys.add(key)
                    current_comment_lines = []

        # Add any new keys not in the original file
        for key, value in self._props.items():
            if key not in written_keys:
                if key in self._comments:
                    lines.append(self._comments[key])
                lines.append(f"{key}={value}")

        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a property value."""
        return self._props.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a property value."""
        self._props[key] = str(value)

    def __getitem__(self, key: str) -> Optional[str]:
        return self._props.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._props

    @property
    def online_mode(self) -> bool:
        return self._props.get("online-mode", "true").lower() == "true"

    @online_mode.setter
    def online_mode(self, value: bool) -> None:
        self._props["online-mode"] = str(value).lower()

    @property
    def server_port(self) -> int:
        return int(self._props.get("server-port", "25565"))

    @server_port.setter
    def server_port(self, value: int) -> None:
        self._props["server-port"] = str(value)

    @property
    def max_players(self) -> int:
        return int(self._props.get("max-players", "20"))

    @max_players.setter
    def max_players(self, value: int) -> None:
        self._props["max-players"] = str(value)

    @property
    def motd(self) -> str:
        return self._props.get("motd", "A Minecraft Server")

    @motd.setter
    def motd(self, value: str) -> None:
        self._props["motd"] = value

    @property
    def difficulty(self) -> str:
        return self._props.get("difficulty", "easy")

    @difficulty.setter
    def difficulty(self, value: str) -> None:
        self._props["difficulty"] = value

    @property
    def gamemode(self) -> str:
        return self._props.get("gamemode", "survival")

    @gamemode.setter
    def gamemode(self, value: str) -> None:
        self._props["gamemode"] = value

    @property
    def view_distance(self) -> int:
        return int(self._props.get("view-distance", "10"))

    @view_distance.setter
    def view_distance(self, value: int) -> None:
        self._props["view-distance"] = str(value)

    @property
    def simulation_distance(self) -> int:
        return int(self._props.get("simulation-distance", "10"))

    @simulation_distance.setter
    def simulation_distance(self, value: int) -> None:
        self._props["simulation-distance"] = str(value)

    @property
    def pvp(self) -> bool:
        return self._props.get("pvp", "true").lower() == "true"

    @pvp.setter
    def pvp(self, value: bool) -> None:
        self._props["pvp"] = str(value).lower()

    def to_dict(self) -> dict[str, str]:
        """Export all properties as a dictionary."""
        return dict(self._props)

    def apply_mode(self, mode: str) -> None:
        """Apply server mode configuration (premium/cracked/eaglercraft)."""
        if mode == "premium":
            self.online_mode = True
        elif mode == "cracked":
            self.online_mode = False
            # Prevents proxy connections stealing names
            self.set("prevent-proxy-connections", "true")
        elif mode == "eaglercraft":
            self.online_mode = False
            self.set("prevent-proxy-connections", "false")
            # Eaglercraft needs these settings
            self.set("enable-command-block", "true")
