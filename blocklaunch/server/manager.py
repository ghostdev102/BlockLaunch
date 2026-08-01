"""Server lifecycle management — create, start, stop, configure Minecraft servers."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from blocklaunch.config import BlockLaunchSettings
from blocklaunch.server.downloader import ServerJarDownloader
from blocklaunch.server.eaglercraft import EaglercraftManager
from blocklaunch.server.properties import ServerProperties
from blocklaunch.utils.java import JavaDetector
from blocklaunch.utils.logging import get_server_logger, setup_logging
from blocklaunch.utils.process import ProcessManager, ServerProcess, ServerStatus

logger = setup_logging()


@dataclass
class OperationResult:
    """Result of a server operation."""
    success: bool
    error: Optional[str] = None
    data: Optional[dict[str, Any]] = None


@dataclass
class ServerConfig:
    """Persistent configuration for a server."""
    name: str
    mode: str  # premium, cracked, eaglercraft
    server_type: str  # vanilla, paper, spigot, forge, fabric
    mc_version: str
    memory: str = "2G"
    port: int = 25565
    directory: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_started: Optional[float] = None
    auto_restart: bool = False
    backup_enabled: bool = True

    @property
    def path(self) -> Path:
        if self.directory:
            return Path(self.directory)
        return Path(self.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "server_type": self.server_type,
            "mc_version": self.mc_version,
            "memory": self.memory,
            "port": self.port,
            "directory": self.directory,
            "created_at": self.created_at,
            "last_started": self.last_started,
            "auto_restart": self.auto_restart,
            "backup_enabled": self.backup_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ServerManager:
    """Manages Minecraft server lifecycle."""

    def __init__(self, settings: BlockLaunchSettings) -> None:
        self.settings = settings
        self.process_manager = ProcessManager()
        self.java_detector = JavaDetector(settings)
        self.downloader = ServerJarDownloader(settings)
        self.eaglercraft_manager = EaglercraftManager(settings)
        self._configs: dict[str, ServerConfig] = {}
        self._load_configs()

    def _configs_path(self) -> Path:
        return self.settings.data_dir / "servers.json"

    def _load_configs(self) -> None:
        """Load server configurations from disk."""
        path = self._configs_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for name, cfg in data.items():
                    self._configs[name] = ServerConfig.from_dict(cfg)
            except Exception as e:
                logger.error(f"Failed to load server configs: {e}")

    def _save_configs(self) -> None:
        """Save server configurations to disk."""
        path = self._configs_path()
        data = {name: cfg.to_dict() for name, cfg in self._configs.items()}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def create_server(
        self,
        name: str,
        mode: str,
        mc_version: str,
        server_type: str = "paper",
        memory: str = "2G",
        port: int = 25565,
        accept_eula: bool = False,
        directory: Optional[str] = None,
        skip_java_check: bool = False,
        skip_download: bool = False,
    ) -> OperationResult:
        """Create a new Minecraft server.

        Args:
            skip_java_check: If True, skip Java validation (useful for testing or
                when Java will be installed later).
            skip_download: If True, skip JAR download (creates the server config
                and directory structure only).
        """
        if name in self._configs:
            return OperationResult(success=False, error=f"Server '{name}' already exists")

        # Validate mode
        valid_modes = ("premium", "cracked", "eaglercraft")
        if mode not in valid_modes:
            return OperationResult(success=False, error=f"Invalid mode: {mode}. Must be one of {valid_modes}")

        # Validate server type
        valid_types = ("vanilla", "paper", "spigot", "forge", "fabric")
        if server_type not in valid_types:
            return OperationResult(success=False, error=f"Invalid server type: {server_type}")

        # Set up directory
        if directory:
            server_dir = Path(directory)
        else:
            server_dir = self.settings.servers_dir / name
        server_dir.mkdir(parents=True, exist_ok=True)

        # Check Java
        if not skip_java_check:
            java_info = await self.java_detector.detect()
            if not java_info.is_valid:
                return OperationResult(success=False, error=java_info.error)

        # Download server JAR
        download_warnings = []
        if not skip_download:
            download_result = await self.downloader.download(server_type, mc_version, server_dir)
            if not download_result.success:
                download_warnings.append(f"JAR download failed: {download_result.error}")
                # Don't fail entirely — create the config anyway so the user can
                # download the JAR manually later
                logger.warning(download_warnings[-1])
        else:
            # Create a placeholder so the user knows to download the JAR
            placeholder = server_dir / "PLACE_SERVER_JAR_HERE.txt"
            placeholder.write_text(
                f"Place your {server_type} {mc_version} server.jar in this directory.\n"
                f"BlockLaunch will detect it automatically.\n",
                encoding="utf-8",
            )

        # Accept EULA
        if accept_eula:
            eula_path = server_dir / "eula.txt"
            eula_path.write_text(
                "# By changing the setting below to TRUE you are indicating your agreement to our EULA "
                "(https://aka.ms/MinecraftEULA).\n"
                f"# Generated by BlockLaunch on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                "eula=true\n",
                encoding="utf-8",
            )
        else:
            # Create eula.txt that needs acceptance
            eula_path = server_dir / "eula.txt"
            eula_path.write_text(
                "# By changing the setting below to TRUE you are indicating your agreement to our EULA "
                "(https://aka.ms/MinecraftEULA).\n"
                "eula=false\n",
                encoding="utf-8",
            )

        # Create server.properties
        props_path = server_dir / "server.properties"
        props = ServerProperties(props_path)
        props.server_port = port
        props.apply_mode(mode)
        props.save()

        # Create server config
        config = ServerConfig(
            name=name,
            mode=mode,
            server_type=server_type,
            mc_version=mc_version,
            memory=memory,
            port=port,
            directory=str(server_dir),
        )

        # Eaglercraft-specific setup
        if mode == "eaglercraft":
            wss_port = self.settings.eaglercraft_wss_port
            eaglercraft_result = await self.eaglercraft_manager.setup_eaglercraft(
                server_dir, wss_port=wss_port
            )
            if eaglercraft_result.get("errors"):
                logger.warning(f"Eaglercraft setup had errors: {eaglercraft_result['errors']}")

        self._configs[name] = config
        self._save_configs()

        server_logger = get_server_logger(name)
        server_logger.info(f"Server created: {name} ({mode}/{server_type}/{mc_version})")

        return OperationResult(
            success=True,
            data={"path": str(server_dir), "config": config.to_dict()},
        )

    async def start_server(self, name: str) -> OperationResult:
        """Start a Minecraft server."""
        config = self._configs.get(name)
        if not config:
            return OperationResult(success=False, error=f"Server '{name}' not found")

        # Check if already running
        existing = self.process_manager.get(name)
        if existing and existing.is_running:
            return OperationResult(success=False, error=f"Server '{name}' is already running")

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / name
        if not server_dir.exists():
            return OperationResult(success=False, error=f"Server directory not found: {server_dir}")

        # Check EULA
        eula_path = server_dir / "eula.txt"
        if eula_path.exists():
            eula_content = eula_path.read_text(encoding="utf-8", errors="replace")
            if "eula=true" not in eula_content.lower():
                return OperationResult(
                    success=False,
                    error="You must accept the Minecraft EULA. "
                          "Use --eula flag or set eula=true in eula.txt",
                )

        # Check Java
        java_info = await self.java_detector.detect()
        if not java_info.is_valid:
            return OperationResult(success=False, error=java_info.error)

        # Build command
        java_path = java_info.path
        jar_path = server_dir / "server.jar"

        # For Forge installer, we need to run the installer first
        forge_installer = server_dir / "forge-installer.jar"
        if forge_installer.exists():
            logger.info("Running Forge installer...")
            install_proc = await asyncio.create_subprocess_exec(
                java_path,
                "-jar",
                str(forge_installer),
                "--installServer",
                cwd=str(server_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await install_proc.wait()
            # Find the actual forge jar after installation
            for jar in server_dir.glob("forge-*-server.jar"):
                jar_path = jar
                break
            for jar in server_dir.glob("run.jar"):
                jar_path = jar
                break

        if not jar_path.exists():
            return OperationResult(success=False, error=f"Server JAR not found at {jar_path}")

        # JVM arguments
        jvm_args = [
            java_path,
            f"-Xmx{config.memory}",
            f"-Xms{config.memory}",
            "-XX:+UseG1GC",
            "-XX:+ParallelRefProcEnabled",
            "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=8M",
            "-XX:G1ReservePercent=20",
            "-XX:G1HeapWastePercent=5",
            "-XX:G1MixedGCCountTarget=4",
            "-XX:InitiatingHeapOccupancyPercent=15",
            "-XX:G1MixedGCLiveThresholdPercent=90",
            "-XX:G1RSetUpdatingPauseTimePercent=5",
            "-XX:SurvivorRatio=32",
            "-XX:+PerfDisableSharedMem",
            "-XX:MaxTenuringThreshold=1",
            "-Dusing.aikars.flags=https://mcflags.emc.gs",
            "-Daikars.new.flags=true",
            "-jar",
            str(jar_path),
            "--nogui",
        ]

        # Start server process
        process = await asyncio.create_subprocess_exec(
            *jvm_args,
            cwd=str(server_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        server_process = ServerProcess(name=name, process=process)
        server_process.on_output(self._make_output_handler(name))
        self.process_manager.register(name, server_process)

        # Start Eaglercraft WSS proxy if needed
        if config.mode == "eaglercraft":
            bungee_dir = server_dir / "eaglercraft-bungee"
            if bungee_dir.exists():
                try:
                    wss_process = await self.eaglercraft_manager.start_wss_proxy(
                        bungee_dir, java_path
                    )
                    logger.info(f"Eaglercraft WSS proxy started for {name}")
                except Exception as e:
                    logger.error(f"Failed to start Eaglercraft WSS proxy: {e}")

        # Update config
        config.last_started = time.time()
        self._save_configs()

        # Start output reader task
        asyncio.create_task(self._read_server_output(name, server_process))

        return OperationResult(
            success=True,
            data={"pid": process.pid, "name": name, "directory": str(server_dir)},
        )

    def _make_output_handler(self, name: str):
        """Create an output handler for server console output."""
        server_logger = get_server_logger(name)

        def handler(line: str) -> None:
            server_logger.info(line)

        return handler

    async def _read_server_output(self, name: str, process: ServerProcess) -> None:
        """Read server output and track status."""
        async for line in process.read_output():
            # Detect server ready
            if "Done (" in line and "For help, type \"help\"" in line:
                process.status = ServerStatus.RUNNING
                logger.info(f"Server '{name}' is now running")

            # Detect crash
            if "Exception" in line and "Shutting down" in line:
                process.status = ServerStatus.CRASHED

        # Process exited
        if process.status not in (ServerStatus.STOPPED, ServerStatus.CRASHED):
            process.status = ServerStatus.STOPPED
        logger.info(f"Server '{name}' process exited with status: {process.status}")

    async def stop_server(self, name: str, force: bool = False) -> OperationResult:
        """Stop a running Minecraft server."""
        process = self.process_manager.get(name)
        if not process or not process.is_running:
            return OperationResult(success=False, error=f"Server '{name}' is not running")

        if force:
            success = await process.force_kill()
        else:
            success = await process.graceful_stop()

        if success:
            return OperationResult(success=True, data={"name": name})
        return OperationResult(success=False, error=f"Failed to stop server '{name}'")

    async def restart_server(self, name: str) -> OperationResult:
        """Restart a running server."""
        stop_result = await self.stop_server(name)
        if not stop_result.success:
            return stop_result

        # Wait a moment for cleanup
        await asyncio.sleep(2)

        return await self.start_server(name)

    async def send_command(self, name: str, command: str) -> OperationResult:
        """Send a command to a running server."""
        process = self.process_manager.get(name)
        if not process or not process.is_running:
            return OperationResult(success=False, error=f"Server '{name}' is not running")

        success = await process.send_command(command)
        if success:
            return OperationResult(success=True, data={"command": command})
        return OperationResult(success=False, error="Failed to send command")

    def get_server_status(self, name: str) -> dict[str, Any]:
        """Get the status of a server."""
        config = self._configs.get(name)
        if not config:
            return {"name": name, "status": "unknown", "error": "Server not found"}

        process = self.process_manager.get(name)
        status = {
            "name": name,
            "mode": config.mode,
            "type": config.server_type,
            "version": config.mc_version,
            "port": config.port,
            "memory": config.memory,
            "status": process.status.value if process else "stopped",
        }

        if process and process.is_running:
            status["pid"] = process.pid
            status["uptime"] = process.uptime
            status["memory_usage_mb"] = process.memory_usage
            status["cpu_usage"] = process.cpu_usage

        return status

    def list_servers(self) -> list[dict[str, Any]]:
        """List all servers."""
        return [self.get_server_status(name) for name in self._configs]

    async def delete_server(self, name: str, delete_files: bool = False) -> OperationResult:
        """Delete a server configuration and optionally its files."""
        if name not in self._configs:
            return OperationResult(success=False, error=f"Server '{name}' not found")

        # Stop server if running
        process = self.process_manager.get(name)
        if process and process.is_running:
            await self.stop_server(name, force=True)

        config = self._configs.pop(name)
        self._save_configs()

        if delete_files and config.directory:
            server_dir = Path(config.directory)
            if server_dir.exists():
                shutil.rmtree(server_dir)
                logger.info(f"Deleted server files for '{name}'")

        return OperationResult(success=True, data={"name": name})

    async def get_server_properties(self, name: str) -> Optional[ServerProperties]:
        """Get the server properties for a server."""
        config = self._configs.get(name)
        if not config:
            return None

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / name
        props_path = server_dir / "server.properties"
        if not props_path.exists():
            return None

        return ServerProperties(props_path)

    async def update_server_properties(self, name: str, updates: dict[str, Any]) -> OperationResult:
        """Update server properties for a server."""
        props = await self.get_server_properties(name)
        if not props:
            return OperationResult(success=False, error=f"Server properties not found for '{name}'")

        for key, value in updates.items():
            props.set(key, value)

        props.save()
        return OperationResult(success=True, data={"name": name, "updates": updates})

    async def create_backup(self, name: str) -> OperationResult:
        """Create a backup of a server."""
        config = self._configs.get(name)
        if not config:
            return OperationResult(success=False, error=f"Server '{name}' not found")

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / name
        if not server_dir.exists():
            return OperationResult(success=False, error=f"Server directory not found")

        backup_dir = self.settings.backups_dir / name
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{timestamp}.tar.gz"

        # Create tar.gz backup excluding logs and cache
        proc = await asyncio.create_subprocess_exec(
            "tar", "czf", str(backup_path),
            "--exclude=logs", "--exclude=cache",
            "--exclude=eaglercraft-bungee",
            "-C", str(server_dir.parent),
            server_dir.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.wait(), b""
        if proc.returncode != 0:
            return OperationResult(success=False, error=f"Backup failed: {stderr.decode()}")

        # Clean old backups
        backups = sorted(backup_dir.glob("backup_*.tar.gz"), reverse=True)
        for old_backup in backups[self.settings.backup_max_count:]:
            old_backup.unlink()

        return OperationResult(
            success=True,
            data={"path": str(backup_path), "size_mb": backup_path.stat().st_size / 1024 / 1024},
        )

    async def get_console_output(self, name: str, lines: int = 100) -> list[str]:
        """Get recent console output from the server log file."""
        config = self._configs.get(name)
        if not config:
            return []

        server_dir = Path(config.directory) if config.directory else self.settings.servers_dir / name
        log_path = server_dir / "logs" / "latest.log"

        if not log_path.exists():
            return []

        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
            all_lines = content.splitlines()
            return all_lines[-lines:]
        except Exception:
            return []

    async def get_available_versions(self, server_type: str) -> list[str]:
        """Get available versions for a server type."""
        return await self.downloader.get_available_versions(server_type)
