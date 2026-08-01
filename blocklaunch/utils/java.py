"""Java detection and management utilities."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from blocklaunch.config import BlockLaunchSettings


@dataclass
class JavaInfo:
    """Information about a Java installation."""
    path: str
    version: str
    major_version: int
    is_valid: bool
    error: Optional[str] = None


class JavaDetector:
    """Detect and validate Java installations."""

    MIN_VERSION = 17
    RECOMMENDED_VERSION = 21

    def __init__(self, settings: BlockLaunchSettings) -> None:
        self.settings = settings
        self._cache: Optional[JavaInfo] = None

    async def detect(self) -> JavaInfo:
        """Detect Java installation and return info."""
        if self._cache and self._cache.is_valid:
            return self._cache

        # Check configured path first
        if self.settings.java_path:
            info = await self._check_java(self.settings.java_path)
            if info.is_valid:
                self._cache = info
                return info

        # Check JAVA_HOME
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            java_bin = str(Path(java_home) / "bin" / "java")
            info = await self._check_java(java_bin)
            if info.is_valid:
                self._cache = info
                return info

        # Check PATH
        java_path = shutil.which("java")
        if java_path:
            info = await self._check_java(java_path)
            if info.is_valid:
                self._cache = info
                return info

        # Common install locations
        common_paths = [
            "/usr/bin/java",
            "/usr/local/bin/java",
            "/usr/lib/jvm/java-21-openjdk/bin/java",
            "/usr/lib/jvm/java-17-openjdk/bin/java",
            "/usr/lib/jvm/default-java/bin/java",
        ]
        # macOS
        if Path("/Library/Java/JavaVirtualMachines").exists():
            jvms = sorted(Path("/Library/Java/JavaVirtualMachines").iterdir(), reverse=True)
            for jvm in jvms:
                common_paths.append(str(jvm / "Contents" / "Home" / "bin" / "java"))

        # Windows
        if os.name == "nt":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            common_paths.extend([
                f"{program_files}\\Java\\jdk-21\\bin\\java.exe",
                f"{program_files}\\Java\\jdk-17\\bin\\java.exe",
                f"{program_files}\\Eclipse Adoptium\\jdk-21\\bin\\java.exe",
                f"{program_files}\\Eclipse Adoptium\\jdk-17\\bin\\java.exe",
            ])

        for path in common_paths:
            if Path(path).exists():
                info = await self._check_java(path)
                if info.is_valid:
                    self._cache = info
                    return info

        return JavaInfo(
            path="",
            version="0",
            major_version=0,
            is_valid=False,
            error=f"Java {self.MIN_VERSION}+ not found. Install Java and set JAVA_HOME or "
                  f"configure java_path in settings.",
        )

    async def _check_java(self, path: str) -> JavaInfo:
        """Check a specific Java binary and return info."""
        try:
            proc = await asyncio.create_subprocess_exec(
                path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stderr.decode("utf-8", errors="replace").strip()

            # Parse version from output like: java version "17.0.8" 2023-07-18 LTS
            # or: openjdk version "21.0.1" 2023-10-17
            version_str = "0"
            for line in output.split("\n"):
                if "version" in line.lower():
                    # Extract version from quotes
                    start = line.find('"')
                    end = line.rfind('"')
                    if start != -1 and end != -1 and start != end:
                        version_str = line[start + 1:end]
                    break

            # Parse major version
            major = self._parse_major_version(version_str)

            is_valid = major >= self.MIN_VERSION
            error = None
            if not is_valid:
                error = f"Java {version_str} found but {self.MIN_VERSION}+ required for modern Minecraft"

            return JavaInfo(
                path=path,
                version=version_str,
                major_version=major,
                is_valid=is_valid,
                error=error,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, asyncio.TimeoutError):
            return JavaInfo(path=path, version="0", major_version=0, is_valid=False,
                            error=f"Java not found at {path}")
        except Exception as e:
            return JavaInfo(path=path, version="0", major_version=0, is_valid=False,
                            error=f"Error checking Java at {path}: {e}")

    @staticmethod
    def _parse_major_version(version_str: str) -> int:
        """Parse the major version from a Java version string."""
        try:
            parts = version_str.split(".")
            if parts[0] == "1":
                # Old-style: 1.8.0_xxx → 8
                return int(parts[1])
            return int(parts[0])
        except (ValueError, IndexError):
            return 0

    def get_java_path(self) -> Optional[str]:
        """Get the detected Java path (synchronous shortcut)."""
        if self._cache and self._cache.is_valid:
            return self._cache.path
        return None
