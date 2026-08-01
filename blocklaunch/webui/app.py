"""BlockLaunch WebUI application factory."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from blocklaunch.webui.routes import servers, plugins, players, websocket as ws


def create_app() -> FastAPI:
    """Create and configure the BlockLaunch FastAPI application."""
    app = FastAPI(
        title="BlockLaunch",
        description="Run Minecraft servers easily, free with a simple WebUI",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files and templates
    static_dir = Path(__file__).parent / "static"
    templates_dir = Path(__file__).parent / "templates"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routes
    app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
    app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
    app.include_router(players.router, prefix="/api/players", tags=["players"])
    app.include_router(ws.router, prefix="/ws", tags=["websocket"])

    # Page routes
    app.include_router(servers.page_router, tags=["pages"])

    # Templates
    app.state.templates = Jinja2Templates(directory=str(templates_dir))

    # Startup/shutdown
    @app.on_event("startup")
    async def startup():
        from blocklaunch.server.manager import ServerManager
        from blocklaunch.config import settings
        app.state.server_manager = ServerManager(settings)
        app.state.plugin_manager = None  # Lazy init
        app.state.settings = settings

    @app.on_event("shutdown")
    async def shutdown():
        from blocklaunch.server.manager import ServerManager
        manager: ServerManager = app.state.server_manager
        await manager.process_manager.stop_all()

    return app
