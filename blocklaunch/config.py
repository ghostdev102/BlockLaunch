"""BlockLaunch configuration management using pydantic-settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_data_dir() -> Path:
    """Get the default data directory for BlockLaunch."""
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "blocklaunch"
    return Path.home() / ".local" / "share" / "blocklaunch"


def _default_config_dir() -> Path:
    """Get the default config directory for BlockLaunch."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "blocklaunch"
    return Path.home() / ".config" / "blocklaunch"


class BlockLaunchSettings(BaseSettings):
    """BlockLaunch application settings."""

    # Directory configuration
    data_dir: Path = Field(default_factory=_default_data_dir)
    config_dir: Path = Field(default_factory=_default_config_dir)

    # Server defaults
    default_memory: str = "2G"
    default_server_type: str = "paper"
    default_mc_version: str = "1.20.4"
    default_port: int = 25565

    # Java configuration
    java_path: Optional[str] = None
    java_min_version: str = "17"

    # WebUI
    webui_host: str = "0.0.0.0"
    webui_port: int = 8080
    webui_secret_key: str = "blocklaunch-change-me-in-production"

    # Eaglercraft
    eaglercraft_wss_port: int = 8081
    eaglercraft_wss_host: str = "0.0.0.0"

    # Plugin API
    modrinth_api_base: str = "https://api.modrinth.com/v2"
    hangar_api_base: str = "https://hangar.papermc.io/api/v1"
    spigotmc_api_base: str = "https://api.spiget.org/v2"
    plugin_cache_ttl: int = 300  # seconds

    # Backup
    backup_enabled: bool = True
    backup_interval_hours: int = 6
    backup_max_count: int = 10

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    model_config = {"env_prefix": "BLOCKLAUNCH_", "env_file": ".env", "env_file_encoding": "utf-8"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "servers").mkdir(parents=True, exist_ok=True)

    @property
    def servers_dir(self) -> Path:
        return self.data_dir / "servers"

    @property
    def plugins_cache_dir(self) -> Path:
        p = self.data_dir / "cache" / "plugins"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def server_jars_cache_dir(self) -> Path:
        p = self.data_dir / "cache" / "jars"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backups_dir(self) -> Path:
        p = self.data_dir / "backups"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def server_dir(self, name: str) -> Path:
        """Get the directory for a specific server."""
        return self.servers_dir / name

    def save(self) -> None:
        """Save settings to config file."""
        config_file = self.config_dir / "settings.json"
        config_file.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls) -> "BlockLaunchSettings":
        """Load settings from config file, falling back to defaults."""
        config_dir = _default_config_dir()
        config_file = config_dir / "settings.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                return cls(**data)
            except Exception:
                pass
        return cls()


# Singleton settings instance
settings = BlockLaunchSettings.load()
