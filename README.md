# BlockLaunch

**Run Minecraft servers easily, free with a simple TUI and/or WebUI.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## Features

### 🎮 Three Server Modes
- **Minecraft Premium** — Standard online-mode server with Mojang authentication
- **Minecraft Cracked** — Offline-mode server for players without premium accounts
- **Eaglercraft (WSS Proxy)** — Browser-based Minecraft with WebSocket proxy for browser connections

### 🖥️ Dual Interface
- **TUI** — Full terminal UI built with Textual (rich, keyboard-driven)
- **WebUI** — Modern web dashboard built with FastAPI + HTMX (dark theme, responsive)

### 🔌 Plugin System
- Search and install plugins from **Modrinth**, **Hangar (PaperMC)**, and **SpigotMC**
- One-click install from any source to any server
- Unified search across all sources

### 👥 Player Management
- **OP Management** — Grant/revoke operator status with permission levels 1-4
- **Whitelist** — Add/remove players from the server whitelist
- **Ban System** — Ban/unban players and IP addresses with reasons
- **Live Commands** — Kick, gamemode, teleport, give items, time/weather control
- **Save All** — Force save world data

### ⚙️ Server Management
- Create servers with Paper, Vanilla, Spigot, Forge, or Fabric
- Start/stop/restart servers with one click
- Live console with WebSocket streaming
- Server properties editor
- Automatic backups with rotation
- Aikar's JVM flags for optimal performance
- Java auto-detection and validation

---

## Installation

### From PyPI (when published)
```bash
pip install blocklaunch
```

### From Source
```bash
git clone https://github.com/fuegotechnology/BlockLaunch.git
cd BlockLaunch
pip install -e .
```

### With dev dependencies
```bash
pip install -e ".[dev]"
```

---

## Quick Start

### Launch the TUI
```bash
blocklaunch
# or explicitly:
blocklaunch tui
```

### Launch the WebUI
```bash
blocklaunch webui
# or with custom host/port:
blocklaunch webui --host 0.0.0.0 --port 8080
```

### Create a Server (CLI)
```bash
# Premium Paper server
blocklaunch create -n my-server -m premium -t paper -v 1.20.4 --eula

# Cracked server
blocklaunch create -n cracked-server -m cracked -t paper -v 1.20.4 --eula

# Eaglercraft server (with WSS proxy)
blocklaunch create -n eagler-server -m eaglercraft -t paper -v 1.20.4 --eula
```

### Start a Server
```bash
blocklaunch start -n my-server
```

### Stop a Server
```bash
blocklaunch stop -n my-server
```

### List Servers
```bash
blocklaunch list
```

### Search Plugins
```bash
blocklaunch search -q "essentials" -s modrinth
```

### Install a Plugin
```bash
blocklaunch install -s my-server -p essentialsx -t modrinth
```

---

## Server Modes

### 🎮 Minecraft Premium
Standard Minecraft server with `online-mode=true`. Players must authenticate with a Mojang/Microsoft account. This is the official, secure way to run a server.

### 🔓 Minecraft Cracked
Server with `online-mode=false`. Players can join without a premium account. **Important:** You should install a login plugin like [AuthMe Reloaded](https://modrinth.com/plugin/authme) to prevent name spoofing!

### 🦅 Eaglercraft (WSS Proxy)
Eaglercraft allows players to connect from a web browser. BlockLaunch automatically:
1. Downloads and configures EaglercraftXServer plugin
2. Sets up EaglercraftXBungee (WebSocket proxy)
3. Configures the WSS proxy for browser connections
4. Sets `online-mode=false` with appropriate settings

Players connect by opening an Eaglercraft client in their browser and pointing it to your WSS URL.

---

## Configuration

BlockLaunch uses `pydantic-settings` with environment variable support. Configuration is stored in `~/.config/blocklaunch/settings.json`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BLOCKLAUNCH_DATA_DIR` | `~/.local/share/blocklaunch` | Data directory |
| `BLOCKLAUNCH_DEFAULT_MEMORY` | `2G` | Default server memory |
| `BLOCKLAUNCH_JAVA_PATH` | Auto-detected | Java executable path |
| `BLOCKLAUNCH_WEBUI_HOST` | `0.0.0.0` | WebUI bind host |
| `BLOCKLAUNCH_WEBUI_PORT` | `8080` | WebUI bind port |
| `BLOCKLAUNCH_EAGLERCRAFT_WSS_PORT` | `8081` | Eaglercraft WSS port |
| `BLOCKLAUNCH_LOG_LEVEL` | `INFO` | Logging level |

---

## API Reference

BlockLaunch exposes a full REST API at `/api/` when the WebUI is running.

### Server Endpoints
- `GET /api/servers` — List all servers
- `POST /api/servers` — Create a server
- `GET /api/servers/{name}` — Get server details
- `POST /api/servers/{name}/start` — Start a server
- `POST /api/servers/{name}/stop` — Stop a server
- `POST /api/servers/{name}/restart` — Restart a server
- `POST /api/servers/{name}/command` — Send a command
- `GET /api/servers/{name}/console` — Get recent console output
- `GET /api/servers/{name}/properties` — Get server properties
- `PUT /api/servers/{name}/properties` — Update server properties
- `POST /api/servers/{name}/backup` — Create a backup
- `DELETE /api/servers/{name}` — Delete a server

### Plugin Endpoints
- `POST /api/plugins/search` — Search plugins
- `POST /api/plugins/install` — Install a plugin
- `POST /api/plugins/uninstall` — Uninstall a plugin
- `GET /api/plugins/installed/{server}` — List installed plugins

### Player Endpoints
- `GET /api/players/{server}/ops` — List operators
- `POST /api/players/{server}/ops` — Grant OP
- `DELETE /api/players/{server}/ops/{player}` — Revoke OP
- `GET /api/players/{server}/whitelist` — List whitelist
- `POST /api/players/{server}/whitelist` — Add to whitelist
- `DELETE /api/players/{server}/whitelist/{player}` — Remove from whitelist
- `GET /api/players/{server}/bans` — List bans
- `POST /api/players/{server}/bans/player` — Ban player
- `POST /api/players/{server}/bans/ip` — Ban IP
- `DELETE /api/players/{server}/bans/player/{player}` — Pardon player
- `DELETE /api/players/{server}/bans/ip/{ip}` — Pardon IP
- `POST /api/players/{server}/kick` — Kick player
- `POST /api/players/{server}/gamemode` — Set gamemode
- `POST /api/players/{server}/teleport` — Teleport player
- `POST /api/players/{server}/give` — Give items
- `POST /api/players/{server}/time` — Set time
- `POST /api/players/{server}/weather` — Set weather
- `POST /api/players/{server}/save-all` — Save all

### WebSocket
- `WS /ws/console/{server}` — Live console stream
- `WS /ws/status/{server}` — Live status updates

---

## Project Structure

```
blocklaunch/
├── __init__.py
├── __main__.py          # CLI entry point
├── config.py            # Configuration management
├── server/
│   ├── downloader.py    # Server JAR downloader
│   ├── eaglercraft.py   # Eaglercraft WSS proxy setup
│   ├── manager.py       # Server lifecycle management
│   ├── players/         # Player management
│   │   └── __init__.py  # OP, bans, whitelist, live commands
│   └── properties.py    # server.properties parser
├── plugins/
│   ├── hangar.py        # Hangar (PaperMC) API client
│   ├── manager.py       # Unified plugin manager
│   ├── modrinth.py      # Modrinth API client
│   └── spigotmc.py      # SpigotMC API client
├── tui/
│   ├── app.py           # Textual TUI application
│   ├── screens/         # TUI screens
│   │   ├── dashboard.py
│   │   ├── create_server.py
│   │   ├── server_detail.py
│   │   ├── console.py
│   │   ├── plugin_browser.py
│   │   └── player_manager.py
│   └── styles.tcss      # TUI styles
├── webui/
│   ├── app.py           # FastAPI application
│   ├── routes/          # API routes
│   │   ├── servers.py
│   │   ├── plugins.py
│   │   ├── players.py
│   │   └── websocket.py
│   ├── templates/       # Jinja2 templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── create_server.html
│   │   ├── server_detail.html
│   │   ├── players.html
│   │   └── plugins.html
│   └── static/          # CSS & JS
├── utils/
│   ├── java.py          # Java detection
│   ├── logging.py       # Logging setup
│   └── process.py       # Process management
```

---

## Requirements

- **Python 3.10+**
- **Java 17+** (for Minecraft 1.17+)
- **Java 21+** (recommended for Minecraft 1.20.5+)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

Made with 🔥 by [Fuego Technology](https://github.com/fuegotechnology)
