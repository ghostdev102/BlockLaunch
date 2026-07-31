"""SpigotMC (Spiget) API client for searching and downloading plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from blocklaunch.utils.logging import setup_logging

logger = setup_logging(name="blocklaunch.spigotmc")


@dataclass
class SpigotProject:
    """A SpigotMC resource."""
    id: str
    name: str
    description: str
    downloads: int
    rating: float
    icon_url: Optional[str]
    source: str = "spigotmc"
    url: str = ""
    version: str = ""


class SpigotMCClient:
    """Client for the Spiget API (SpigotMC resource repository)."""

    BASE_URL = "https://api.spiget.org/v2"

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
        page: int = 1,
    ) -> list[SpigotProject]:
        """Search for resources on SpigotMC."""
        params = {
            "sort": "-downloads",
            "page": page,
            "size": limit,
            "fields": "id,name,tag,downloads,icon,rating",
        }

        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/search/resources/{query}", params=params
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for hit in data:
                icon_data = hit.get("icon", {})
                icon_url = None
                if icon_data and isinstance(icon_data, dict):
                    icon_url = icon_data.get("url")
                    if icon_url and not icon_url.startswith("http"):
                        icon_url = f"https://www.spigotmc.org/{icon_url}"

                rating_data = hit.get("rating", {})
                rating = rating_data.get("average", 0) if isinstance(rating_data, dict) else 0

                results.append(SpigotProject(
                    id=str(hit.get("id", "")),
                    name=hit.get("name", ""),
                    description=hit.get("tag", "")[:200],
                    downloads=hit.get("downloads", 0),
                    rating=rating,
                    icon_url=icon_url,
                    source="spigotmc",
                    url=f"https://www.spigotmc.org/resources/{hit.get('id', '')}",
                ))
            return results
        except Exception as e:
            logger.error(f"SpigotMC search failed: {e}")
            return []

    async def get_project(self, resource_id: str) -> Optional[SpigotProject]:
        """Get a resource by ID."""
        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/resources/{resource_id}",
                params={"fields": "id,name,tag,downloads,icon,rating,versions"},
            )
            resp.raise_for_status()
            data = resp.json()

            icon_data = data.get("icon", {})
            icon_url = None
            if icon_data and isinstance(icon_data, dict):
                icon_url = icon_data.get("url")
                if icon_url and not icon_url.startswith("http"):
                    icon_url = f"https://www.spigotmc.org/{icon_url}"

            rating_data = data.get("rating", {})
            rating = rating_data.get("average", 0) if isinstance(rating_data, dict) else 0

            return SpigotProject(
                id=str(data.get("id", "")),
                name=data.get("name", ""),
                description=data.get("tag", "")[:200],
                downloads=data.get("downloads", 0),
                rating=rating,
                icon_url=icon_url,
                source="spigotmc",
                url=f"https://www.spigotmc.org/resources/{data.get('id', '')}",
            )
        except Exception as e:
            logger.error(f"SpigotMC get project failed: {e}")
            return None

    async def get_versions(self, resource_id: str) -> list[dict]:
        """Get versions for a resource."""
        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/resources/{resource_id}/versions",
                params={"size": 20, "sort": "-id"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"SpigotMC get versions failed: {e}")
            return []

    async def get_download_url(self, resource_id: str) -> Optional[tuple[str, str]]:
        """Get the download URL for a resource. Returns (url, filename)."""
        try:
            # Spiget provides a direct download endpoint
            url = f"{self.BASE_URL}/resources/{resource_id}/download"
            filename = f"spigotmc-{resource_id}.jar"
            return url, filename
        except Exception as e:
            logger.error(f"SpigotMC get download URL failed: {e}")
            return None

    async def download_plugin(self, url: str, target_path: str) -> bool:
        """Download a plugin JAR from URL."""
        try:
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()

            # Check if we got an HTML page (SpigotMC download page)
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                # Try to extract the actual download link from the page
                # This is a common pattern with SpigotMC
                logger.warning("SpigotMC returned HTML instead of direct download. "
                              "The plugin may require manual download from the website.")
                return False

            with open(target_path, "wb") as f:
                f.write(resp.content)

            logger.info(f"Downloaded plugin to {target_path} ({len(resp.content) / 1024:.1f} KB)")
            return True
        except Exception as e:
            logger.error(f"Plugin download failed: {e}")
            return False
