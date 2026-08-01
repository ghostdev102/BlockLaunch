"""Process management utilities for Minecraft server processes."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

import psutil


class ServerStatus(str, Enum):
    """Server status enum."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    UNKNOWN = "unknown"


@dataclass
class ServerProcess:
    """Represents a running Minecraft server process."""
    name: str
    process: asyncio.subprocess.Process
    status: ServerStatus = ServerStatus.STARTING
    started_at: float = field(default_factory=time.time)
    pid: Optional[int] = None
    _output_callbacks: list[Callable[[str], None]] = field(default_factory=list)
    _task: Optional[asyncio.Task] = None

    def __post_init__(self):
        self.pid = self.process.pid

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Register a callback for server output lines."""
        self._output_callbacks.append(callback)

    async def read_output(self) -> AsyncIterator[str]:
        """Async iterator over server stdout/stderr lines."""
        if not self.process.stdout:
            return
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                for cb in self._output_callbacks:
                    try:
                        cb(decoded)
                    except Exception:
                        pass
                yield decoded
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def send_command(self, command: str) -> bool:
        """Send a command to the server's stdin."""
        if self.process.returncode is not None:
            return False
        try:
            self.process.stdin.write(f"{command}\n".encode("utf-8"))
            await self.process.stdin.drain()
            return True
        except Exception:
            return False

    async def graceful_stop(self, timeout: float = 30.0) -> bool:
        """Stop the server gracefully by sending 'stop' command, then SIGTERM."""
        self.status = ServerStatus.STOPPING

        # Send 'stop' command
        await self.send_command("stop")

        # Wait for the process to exit
        try:
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
            self.status = ServerStatus.STOPPED
            return True
        except asyncio.TimeoutError:
            pass

        # Force kill
        return await self.force_kill()

    async def force_kill(self) -> bool:
        """Force kill the server process and all children."""
        try:
            parent = psutil.Process(self.pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            self.status = ServerStatus.STOPPED
            return True
        except psutil.NoSuchProcess:
            self.status = ServerStatus.STOPPED
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        """Check if the process is still running."""
        return self.process.returncode is None

    @property
    def uptime(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self.started_at

    @property
    def memory_usage(self) -> Optional[float]:
        """Get memory usage in MB."""
        try:
            proc = psutil.Process(self.pid)
            return proc.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, Exception):
            return None

    @property
    def cpu_usage(self) -> Optional[float]:
        """Get CPU usage percentage."""
        try:
            proc = psutil.Process(self.pid)
            return proc.cpu_percent(interval=0.1)
        except (psutil.NoSuchProcess, Exception):
            return None


class ProcessManager:
    """Manages all server processes."""

    def __init__(self) -> None:
        self._processes: dict[str, ServerProcess] = {}

    def register(self, name: str, process: ServerProcess) -> None:
        """Register a server process."""
        self._processes[name] = process

    def get(self, name: str) -> Optional[ServerProcess]:
        """Get a server process by name."""
        proc = self._processes.get(name)
        if proc and not proc.is_running:
            if proc.status not in (ServerStatus.STOPPED, ServerStatus.CRASHED):
                proc.status = ServerStatus.CRASHED
        return proc

    def remove(self, name: str) -> None:
        """Remove a server process."""
        self._processes.pop(name, None)

    def list_running(self) -> list[str]:
        """List all running server names."""
        return [name for name, proc in self._processes.items() if proc.is_running]

    def get_all(self) -> dict[str, ServerProcess]:
        """Get all registered processes."""
        return dict(self._processes)

    async def stop_all(self, timeout: float = 30.0) -> None:
        """Stop all running servers."""
        for name, proc in list(self._processes.items()):
            if proc.is_running:
                await proc.graceful_stop(timeout=timeout)
