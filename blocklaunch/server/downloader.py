"""Server JAR downloader — downloads vanilla, Paper, Spigot, Forge, Fabric server JARs."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from blocklaunch.config import BlockLaunchSettings
from blocklaunch.utils.logging import setup_logging

logger = setup_logging()


@dataclass
class DownloadResult:
    """Result of a JAR download operation."""
    success: bool
    path: Optional[Path] = None
    error: Optional[str] = None
    version: Optional[str] = None


class ServerJarDownloader:
    """Downloads Minecraft server JARs from various sources."""

    def __init__(self, settings: BlockLaunchSettings) -> None:
        self.settings = settings
        self.cache_dir = settings.server_jars_cache_dir
        self.client = httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            headers={"User-Agent": "BlockLaunch/1.0 (https://github.com/fuegotechnology/BlockLaunch)"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def download(self, server_type: str, version: str, target_dir: Path) -> DownloadResult:
        """Download a server JAR of the given type and version."""
        downloaders = {
            "vanilla": self._download_vanilla,
            "paper": self._download_paper,
            "spigot": self._download_spigot,
            "forge": self._download_forge,
            "fabric": self._download_fabric,
        }

        downloader = downloaders.get(server_type)
        if not downloader:
            return DownloadResult(success=False, error=f"Unknown server type: {server_type}")

        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            return await downloader(version, target_dir)
        except Exception as e:
            logger.error(f"Failed to download {server_type} {version}: {e}")
            return DownloadResult(success=False, error=str(e))

    async def _download_vanilla(self, version: str, target_dir: Path) -> DownloadResult:
        """Download vanilla Minecraft server from Mojang."""
        logger.info(f"Downloading vanilla server {version}...")

        # Get version manifest
        manifest_resp = await self.client.get("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
        manifest_resp.raise_for_status()
        manifest = manifest_resp.json()

        # Find the version
        version_url = None
        for v in manifest.get("versions", []):
            if v["id"] == version:
                version_url = v["url"]
                break

        if not version_url:
            return DownloadResult(success=False, error=f"Vanilla version {version} not found")

        # Get version details
        version_resp = await self.client.get(version_url)
        version_resp.raise_for_status()
        version_data = version_resp.json()

        server_info = version_data.get("downloads", {}).get("server")
        if not server_info:
            return DownloadResult(success=False, error=f"No server download for vanilla {version}")

        server_url = server_info["url"]
        server_sha1 = server_info.get("sha1", "")

        # Download
        jar_path = target_dir / "server.jar"
        await self._download_file(server_url, jar_path, expected_sha1=server_sha1)

        return DownloadResult(success=True, path=jar_path, version=version)

    async def _download_paper(self, version: str, target_dir: Path) -> DownloadResult:
        """Download Paper server from PaperMC."""
        logger.info(f"Downloading Paper server {version}...")

        # Get builds for version
        builds_resp = await self.client.get(
            f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds"
        )
        builds_resp.raise_for_status()
        builds_data = builds_resp.json()

        builds = builds_data.get("builds", [])
        if not builds:
            return DownloadResult(success=False, error=f"No Paper builds for version {version}")

        # Get latest stable build
        latest_build = None
        for build in reversed(builds):
            if build.get("channel") == "default" or not build.get("channel"):
                latest_build = build
                break

        if not latest_build:
            latest_build = builds[-1]

        build_number = latest_build["build"]
        # Find the application jar
        downloads = latest_build.get("downloads", {})
        application = downloads.get("application", {})
        jar_name = application.get("name", f"paper-{version}-{build_number}.jar")

        download_url = (
            f"https://api.papermc.io/v2/projects/paper/versions/{version}/"
            f"builds/{build_number}/downloads/{jar_name}"
        )

        jar_path = target_dir / "server.jar"
        await self._download_file(download_url, jar_path)

        return DownloadResult(success=True, path=jar_path, version=version)

    async def _download_spigot(self, version: str, target_dir: Path) -> DownloadResult:
        """Download Spigot server from GetBukkit."""
        logger.info(f"Downloading Spigot server {version}...")

        # Try GetBukkit API
        url = f"https://download.getbukkit.org/spigot/spigot-{version}.jar"
        try:
            resp = await self.client.head(url)
            if resp.status_code == 200:
                jar_path = target_dir / "server.jar"
                await self._download_file(url, jar_path)
                return DownloadResult(success=True, path=jar_path, version=version)
        except Exception:
            pass

        # Fallback: download from Yatopia mirror or suggest BuildTools
        return DownloadResult(
            success=False,
            error=f"Spigot {version} not available for direct download. "
                  f"Use Paper instead, or build Spigot using BuildTools manually.",
        )

    async def _download_forge(self, version: str, target_dir: Path) -> DownloadResult:
        """Download Forge server installer."""
        logger.info(f"Downloading Forge server {version}...")

        # Get Forge promotions
        promos_resp = await self.client.get(
            "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
        )
        promos_resp.raise_for_status()
        promos = promos_resp.json()

        # Find recommended or latest version
        forge_version = None
        for key in [f"{version}-recommended", f"{version}-latest"]:
            if key in promos.get("promos", {}):
                forge_version = promos["promos"][key]
                break

        if not forge_version:
            return DownloadResult(success=False, error=f"No Forge build for Minecraft {version}")

        full_version = f"{version}-{forge_version}"
        download_url = (
            f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
            f"{full_version}/forge-{full_version}-installer.jar"
        )

        installer_path = target_dir / "forge-installer.jar"
        await self._download_file(download_url, installer_path)

        return DownloadResult(
            success=True,
            path=installer_path,
            version=full_version,
        )

    async def _download_fabric(self, version: str, target_dir: Path) -> DownloadResult:
        """Download Fabric server installer."""
        logger.info(f"Downloading Fabric server {version}...")

        # Get Fabric loader versions
        loader_resp = await self.client.get("https://meta.fabricmc.net/v2/versions/loader")
        loader_resp.raise_for_status()
        loaders = loader_resp.json()

        if not loaders:
            return DownloadResult(success=False, error="No Fabric loader versions found")

        loader_version = loaders[0]["version"]

        # Download the installer
        installer_url = (
            f"https://meta.fabricmc.net/v2/versions/loader/"
            f"{version}/{loader_version}/server/jar"
        )

        jar_path = target_dir / "server.jar"
        await self._download_file(installer_url, jar_path)

        return DownloadResult(
            success=True,
            path=jar_path,
            version=f"{version}-fabric-{loader_version}",
        )

    async def _download_file(
        self,
        url: str,
        target: Path,
        expected_sha1: Optional[str] = None,
    ) -> None:
        """Download a file with progress tracking and optional SHA1 verification."""
        import hashlib

        async with self.client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            sha1 = hashlib.sha1()

            with open(target, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    sha1.update(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = (downloaded / total) * 100
                        if downloaded % (5 * 65536) < 65536:  # Log every ~320KB
                            logger.debug(f"Download progress: {pct:.1f}%")

        if expected_sha1 and sha1.hexdigest() != expected_sha1:
            target.unlink()
            raise ValueError(f"SHA1 mismatch: expected {expected_sha1}, got {sha1.hexdigest()}")

        logger.info(f"Downloaded {target.name} ({downloaded / 1024 / 1024:.1f} MB)")

    async def get_available_versions(self, server_type: str) -> list[str]:
        """Get list of available versions for a server type."""
        try:
            if server_type == "vanilla":
                resp = await self.client.get(
                    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
                )
                resp.raise_for_status()
                versions = [v["id"] for v in resp.json().get("versions", [])]
                # Filter to release versions only
                return [v for v in versions if re.match(r"^\d+\.\d+(\.\d+)?$", v)]

            elif server_type == "paper":
                resp = await self.client.get("https://api.papermc.io/v2/projects/paper")
                resp.raise_for_status()
                return resp.json().get("versions", [])

            elif server_type == "forge":
                promos_resp = await self.client.get(
                    "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
                )
                promos_resp.raise_for_status()
                versions = set()
                for key in promos_resp.json().get("promos", {}):
                    mc_version = key.rsplit("-", 1)[0]
                    versions.add(mc_version)
                return sorted(versions, reverse=True)

            elif server_type == "fabric":
                resp = await self.client.get(
                    "https://meta.fabricmc.net/v2/versions/game"
                )
                resp.raise_for_status()
                return [v["version"] for v in resp.json() if v.get("stable")]

            elif server_type == "spigot":
                # Spigot versions match vanilla
                return await self.get_available_versions("vanilla")

        except Exception as e:
            logger.error(f"Failed to get versions for {server_type}: {e}")

        return []
