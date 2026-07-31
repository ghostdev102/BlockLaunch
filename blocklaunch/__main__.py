"""BlockLaunch CLI entry point and main launcher."""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import click

from blocklaunch import __version__


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    """BlockLaunch — Run Minecraft servers easily, free with a simple TUI and/or WebUI."""
    if version:
        click.echo(f"BlockLaunch v{__version__}")
        return
    if ctx.invoked_subcommand is None:
        # Default: launch TUI
        ctx.invoke(tui)


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="WebUI bind host.")
@click.option("--port", "-p", default=8080, type=int, help="WebUI bind port.")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically.")
def webui(host: str, port: int, no_browser: bool) -> None:
    """Launch the BlockLaunch WebUI."""
    from blocklaunch.webui.app import create_app
    import uvicorn

    app = create_app()
    if not no_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")

    click.echo(f"🚀 BlockLaunch WebUI starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


@cli.command()
def tui() -> None:
    """Launch the BlockLaunch TUI."""
    from blocklaunch.tui.app import BlockLaunchApp

    app = BlockLaunchApp()
    app.run()


@cli.command()
@click.option("--name", "-n", required=True, help="Server name.")
@click.option("--mode", "-m", type=click.Choice(["premium", "cracked", "eaglercraft"]), required=True,
              help="Server mode: premium, cracked, or eaglercraft.")
@click.option("--version", "-v", default="1.20.4", help="Minecraft version.")
@click.option("--type", "-t", "server_type",
              type=click.Choice(["vanilla", "paper", "spigot", "forge", "fabric"]),
              default="paper", help="Server software type.")
@click.option("--memory", default="2G", help="Max memory allocation (e.g., 2G, 4G).")
@click.option("--port", "-p", default=25565, type=int, help="Server port.")
@click.option("--eula", is_flag=True, help="Accept Minecraft EULA automatically.")
@click.option("--directory", "-d", default=None, help="Server directory.")
def create(name: str, mode: str, version: str, server_type: str, memory: str,
           port: int, eula: bool, directory: Optional[str]) -> None:
    """Create a new Minecraft server."""
    from blocklaunch.server.manager import ServerManager
    from blocklaunch.config import settings

    manager = ServerManager(settings)
    result = asyncio.run(manager.create_server(
        name=name,
        mode=mode,
        mc_version=version,
        server_type=server_type,
        memory=memory,
        port=port,
        accept_eula=eula,
        directory=directory,
    ))
    if result.success:
        click.echo(f"✅ Server '{name}' created successfully at {result.path}")
    else:
        click.echo(f"❌ Failed to create server: {result.error}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--name", "-n", required=True, help="Server name.")
@click.option("--attach", "-a", is_flag=True, help="Attach to server console after starting.")
def start(name: str, attach: bool) -> None:
    """Start a Minecraft server."""
    from blocklaunch.server.manager import ServerManager
    from blocklaunch.config import settings

    manager = ServerManager(settings)
    result = asyncio.run(manager.start_server(name))
    if result.success:
        click.echo(f"✅ Server '{name}' started (PID: {result.data.get('pid', 'N/A')})")
    else:
        click.echo(f"❌ Failed to start server: {result.error}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--name", "-n", required=True, help="Server name.")
@click.option("--force", "-f", is_flag=True, help="Force kill the server.")
def stop(name: str, force: bool) -> None:
    """Stop a running Minecraft server."""
    from blocklaunch.server.manager import ServerManager
    from blocklaunch.config import settings

    manager = ServerManager(settings)
    result = asyncio.run(manager.stop_server(name, force=force))
    if result.success:
        click.echo(f"✅ Server '{name}' stopped")
    else:
        click.echo(f"❌ Failed to stop server: {result.error}", err=True)
        sys.exit(1)


@cli.command(name="list")
def list_servers() -> None:
    """List all servers."""
    from blocklaunch.server.manager import ServerManager
    from blocklaunch.config import settings

    manager = ServerManager(settings)
    servers = manager.list_servers()
    if not servers:
        click.echo("No servers found. Create one with 'blocklaunch create'.")
        return
    click.echo(f"{'Name':<20} {'Mode':<15} {'Type':<10} {'Version':<10} {'Status':<10} {'Port':<8}")
    click.echo("-" * 73)
    for s in servers:
        click.echo(f"{s['name']:<20} {s['mode']:<15} {s['type']:<10} {s['version']:<10} "
                    f"{s['status']:<10} {s['port']:<8}")


@cli.command()
@click.option("--query", "-q", required=True, help="Search query.")
@click.option("--source", "-s", type=click.Choice(["modrinth", "hangar", "spigotmc", "all"]),
              default="all", help="Plugin source to search.")
@click.option("--limit", "-l", default=10, type=int, help="Max results per source.")
def search(query: str, source: str, limit: int) -> None:
    """Search for plugins across sources."""
    from blocklaunch.plugins.manager import PluginManager
    from blocklaunch.config import settings

    async def _search() -> None:
        pm = PluginManager(settings)
        results = await pm.search(query, sources=[source] if source != "all" else None, limit=limit)
        if not results:
            click.echo("No plugins found.")
            return
        for r in results:
            click.echo(f"[{r.source}] {r.name} (v{r.version}) — {r.description[:80]}")
            click.echo(f"  ID: {r.id} | Downloads: {r.downloads:,} | {r.url}")
            click.echo()

    asyncio.run(_search())


@cli.command()
@click.option("--server", "-s", required=True, help="Server name to install plugin to.")
@click.option("--plugin-id", "-p", required=True, help="Plugin ID from search results.")
@click.option("--source", "-t", type=click.Choice(["modrinth", "hangar", "spigotmc"]),
              required=True, help="Plugin source.")
@click.option("--version-id", default=None, help="Specific version ID (optional).")
def install(server: str, plugin_id: str, source: str, version_id: Optional[str]) -> None:
    """Install a plugin to a server."""
    from blocklaunch.plugins.manager import PluginManager
    from blocklaunch.config import settings

    async def _install() -> None:
        pm = PluginManager(settings)
        result = await pm.install(server_name=server, plugin_id=plugin_id,
                                  source=source, version_id=version_id)
        if result.success:
            click.echo(f"✅ Plugin installed: {result.data.get('name', plugin_id)}")
        else:
            click.echo(f"❌ Failed to install plugin: {result.error}", err=True)
            sys.exit(1)

    asyncio.run(_install())


if __name__ == "__main__":
    cli()
