"""Hangar (PaperMC) API client for searching and downloading plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from blocklaunch.utils.logging import setup_logging

logger = setup_logging(name="blocklaunch.hangar")


@dataclass
class HangarProject:
    """A Hangar project."""
    id: str
    name: str
    slug: str
    description: str
    downloads: int
    icon_url: Optional[str]
    source: str = "hangar"
    url: str = ""
    version: str = ""


class HangarClient:
    """Client for the Hangar API (PaperMC plugin repository)."""

    BASE_URL = "https://hangar.papermc.io/api/v1"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "BlockLaunch/1.0 (https://github.com/fuegotechnology/BlockLaunch)",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[HangarProject]:
        """Search for projects on Hangar."""
        params = {
            "q": query,
            "limit": limit,
            "offset": offset,
        }

        try:
            resp = await self.client.get(f"{self.BASE_URL}/projects", params=params)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for hit in data.get("result", []):
                namespace = hit.get("namespace", {})
                results.append(HangarProject(
                    id=str(hit.get("id", "")),
                    name=hit.get("name", ""),
                    slug=namespace.get("slug", ""),
                    description=hit.get("description", "")[:200] if hit.get("description") else "",
                    downloads=hit.get("stats", {}).get("downloads", 0),
                    icon_url=None,
                    source="hangar",
                    url=f"https://hangar.papermc.io/{namespace.get('owner', '')}/{namespace.get('slug', '')}",
                ))
            return results
        except Exception as e:
            logger.error(f"Hangar search failed: {e}")
            return []

    async def get_project(self, slug: str) -> Optional[HangarProject]:
        """Get a project by slug."""
        try:
            resp = await self.client.get(f"{self.BASE_URL}/projects/{slug}")
            resp.raise_for_status()
            data = resp.json()

            namespace = data.get("namespace", {})
            return HangarProject(
                id=str(data.get("id", "")),
                name=data.get("name", ""),
                slug=namespace.get("slug", ""),
                description=data.get("description", "")[:200] if data.get("description") else "",
                downloads=data.get("stats", {}).get("downloads", 0),
                icon_url=None,
                source="hangar",
                url=f"https://hangar.papermc.io/{namespace.get('owner', '')}/{namespace.get('slug', '')}",
            )
        except Exception as e:
            logger.error(f"Hangar get project failed: {e}")
            return None

    async def get_versions(self, slug: str, limit: int = 10) -> list[dict]:
        """Get versions for a project."""
        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/projects/{slug}/versions",
                params={"limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception as e:
            logger.error(f"Hangar get versions failed: {e}")
            return []

    async def get_download_url(
        self,
        slug: str,
        version_name: Optional[str] = None,
    ) -> Optional[tuple[str, str]]:
        """Get the download URL for a plugin. Returns (url, filename)."""
        try:
            versions = await self.get_versions(slug)
            if not versions:
                return None

            target_version = versions[0]
            if version_name:
                for v in versions:
                    if v.get("name") == version_name:
                        target_version = v
                        break

            # Get download info
            downloads = target_version.get("downloads", [])
            if downloads:
                platform_download = downloads[0]
                download_info = platform_download.get("download", {})
                file_info = download_info.get("fileInfo", {})
                version_id = target_version.get("id", "")
                # Construct download URL
                namespace = slug
                url = f"{self.BASE_URL}/projects/{slug}/versions/{version_id}/" \
                      f"platforms/{platform_download.get('platform', 'PAPER')}/download"
                filename = file_info.get("name", f"{slug}.jar")
                return url, filename

        except Exception as e:
            logger.error(f"Hangar get download URL failed: {e}")

        return None

    async def download_plugin(self, url: str, target_path: str) -> bool:
        """Download a plugin JAR from URL."""
        try:
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()

            with open(target_path, "wb") as f:
                f.write(resp.content)

            logger.info(f"Downloaded plugin to {target_path} ({len(resp.content) / 1024:.1f} KB)")
            return True
        except Exception as e:
            logger.error(f"Plugin download failed: {e}")
            return False
