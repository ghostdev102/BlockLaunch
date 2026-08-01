"""Modrinth API client for searching and downloading plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from blocklaunch.utils.logging import setup_logging

logger = setup_logging(name="blocklaunch.modrinth")


@dataclass
class ModrinthProject:
    """A Modrinth project."""
    id: str
    slug: str
    name: str
    description: str
    icon_url: Optional[str]
    downloads: int
    project_type: str
    source: str = "modrinth"
    url: str = ""
    version: str = ""


@dataclass
class ModrinthVersion:
    """A specific version of a Modrinth project."""
    id: str
    name: str
    version_number: str
    game_versions: list[str]
    loaders: list[str]
    files: list[dict]
    downloads: int


class ModrinthClient:
    """Client for the Modrinth API (v2)."""

    BASE_URL = "https://api.modrinth.com/v2"

    def __init__(self, cache_dir: Optional[str] = None) -> None:
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
        project_type: str = "mod",
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ModrinthProject]:
        """Search for projects on Modrinth."""
        facets = [[f"project_type:{project_type}"]]
        if game_version:
            facets.append([f"versions:{game_version}"])
        if loader:
            facets.append([f"categories:{loader}"])

        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "facets": str(facets).replace("'", '"'),
        }

        try:
            resp = await self.client.get(f"{self.BASE_URL}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for hit in data.get("hits", []):
                results.append(ModrinthProject(
                    id=hit["project_id"],
                    slug=hit.get("slug", ""),
                    name=hit["title"],
                    description=hit.get("description", ""),
                    icon_url=hit.get("icon_url"),
                    downloads=hit.get("downloads", 0),
                    project_type=project_type,
                    source="modrinth",
                    url=f"https://modrinth.com/{project_type}/{hit.get('slug', hit['project_id'])}",
                ))
            return results
        except Exception as e:
            logger.error(f"Modrinth search failed: {e}")
            return []

    async def get_project(self, project_id: str) -> Optional[ModrinthProject]:
        """Get a project by ID or slug."""
        try:
            resp = await self.client.get(f"{self.BASE_URL}/project/{project_id}")
            resp.raise_for_status()
            data = resp.json()

            return ModrinthProject(
                id=data["id"],
                slug=data["slug"],
                name=data["title"],
                description=data.get("description", ""),
                icon_url=data.get("icon_url"),
                downloads=data.get("downloads", 0),
                project_type=data.get("project_type", "mod"),
                source="modrinth",
                url=f"https://modrinth.com/{data.get('project_type', 'mod')}/{data['slug']}",
            )
        except Exception as e:
            logger.error(f"Modrinth get project failed: {e}")
            return None

    async def get_versions(
        self,
        project_id: str,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
    ) -> list[ModrinthVersion]:
        """Get versions for a project."""
        params = {}
        if game_version:
            params["game_versions"] = f'["{game_version}"]'
        if loader:
            params["loaders"] = f'["{loader}"]'

        try:
            resp = await self.client.get(
                f"{self.BASE_URL}/project/{project_id}/version", params=params
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                ModrinthVersion(
                    id=v["id"],
                    name=v.get("name", ""),
                    version_number=v.get("version_number", ""),
                    game_versions=v.get("game_versions", []),
                    loaders=v.get("loaders", []),
                    files=v.get("files", []),
                    downloads=v.get("downloads", 0),
                )
                for v in data
            ]
        except Exception as e:
            logger.error(f"Modrinth get versions failed: {e}")
            return []

    async def get_download_url(
        self,
        project_id: str,
        game_version: Optional[str] = None,
        loader: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> Optional[tuple[str, str]]:
        """Get the download URL for a plugin. Returns (url, filename)."""
        if version_id:
            try:
                resp = await self.client.get(f"{self.BASE_URL}/version/{version_id}")
                resp.raise_for_status()
                version = resp.json()
                for f in version.get("files", []):
                    if f.get("primary", False):
                        return f["url"], f["filename"]
                if version.get("files"):
                    f = version["files"][0]
                    return f["url"], f["filename"]
            except Exception as e:
                logger.error(f"Modrinth get version failed: {e}")
                return None

        versions = await self.get_versions(project_id, game_version, loader)
        if not versions:
            return None

        # Get the latest version's primary file
        latest = versions[0]
        for f in latest.files:
            if f.get("primary", False):
                return f["url"], f["filename"]
        if latest.files:
            f = latest.files[0]
            return f["url"], f["filename"]

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
