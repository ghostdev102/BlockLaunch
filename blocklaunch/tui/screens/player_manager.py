"""Player Manager screen — manage ops, bans, whitelist, and live player actions."""

from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static, TabPane, TabbedContent

from blocklaunch.server.manager import ServerManager
from blocklaunch.server.players import PlayerManager
from blocklaunch.config import settings


class PlayerManagerScreen(Screen):
    """Screen for managing players on a server."""

    TITLE = "Player Manager"

    def __init__(self, server_name: str) -> None:
        super().__init__()
        self.server_name = server_name
        self._player_mgr: Optional[PlayerManager] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="player-manager"):
            yield Label(f"👥 Player Manager: {self.server_name}", classes="title")

            with TabbedContent():
                # Ops tab
                with TabPane("⚡ Ops"):
                    yield Label("Grant or revoke operator status:", classes="info-label")
                    yield Horizontal(
                        Input(placeholder="Player name", id="op-name-input"),
                        Button("OP", id="op-btn", variant="success"),
                        Button("DEOP", id="deop-btn", variant="error"),
                    )
                    yield ListView(id="op-list")

                # Whitelist tab
                with TabPane("📋 Whitelist"):
                    yield Label("Manage the whitelist:", classes="info-label")
                    yield Horizontal(
                        Input(placeholder="Player name", id="whitelist-name-input"),
                        Button("Add", id="wl-add-btn", variant="success"),
                        Button("Remove", id="wl-remove-btn", variant="error"),
                    )
                    yield ListView(id="whitelist-list")

                # Bans tab
                with TabPane("🔨 Bans"):
                    yield Label("Manage player and IP bans:", classes="info-label")
                    yield Horizontal(
                        Input(placeholder="Player name or IP", id="ban-input"),
                        Input(placeholder="Reason", id="ban-reason-input"),
                        Button("Ban Player", id="ban-btn", variant="error"),
                        Button("Ban IP", id="ban-ip-btn", variant="error"),
                        Button("Pardon", id="pardon-btn", variant="success"),
                        Button("Pardon IP", id="pardon-ip-btn", variant="success"),
                    )
                    yield ListView(id="ban-list")

                # Live Commands tab
                with TabPane("🎮 Live Commands"):
                    yield Label("Send commands to running server (requires server to be running):",
                               classes="info-label")
                    yield Horizontal(
                        Input(placeholder="Player name", id="live-player-input"),
                        Button("Kick", id="kick-btn", variant="warning"),
                        Button("Survival", id="gms-btn", variant="primary"),
                        Button("Creative", id="gmc-btn", variant="primary"),
                        Button("Adventure", id="gma-btn", variant="primary"),
                        Button("Spectator", id="gmsp-btn", variant="primary"),
                    )
                    yield Horizontal(
                        Input(placeholder="Target player", id="tp-target-input"),
                        Button("Teleport To", id="tp-btn", variant="primary"),
                    )
                    yield Horizontal(
                        Input(placeholder="Item (e.g., minecraft:diamond)", id="give-item-input"),
                        Button("Give x64", id="give-btn", variant="success"),
                    )
                    yield Horizontal(
                        Button("☀️ Day", id="day-btn", variant="primary"),
                        Button("🌙 Night", id="night-btn", variant="primary"),
                        Button("☀️ Clear Weather", id="clear-weather-btn", variant="primary"),
                        Button("🌧 Rain", id="rain-btn", variant="primary"),
                        Button("⚡ Thunder", id="thunder-btn", variant="primary"),
                        Button("💾 Save All", id="save-btn", variant="success"),
                    )
                    yield Static("", id="live-status")
            yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _get_player_manager(self) -> PlayerManager:
        if self._player_mgr is None:
            manager = ServerManager(settings)
            config = manager._configs.get(self.server_name)
            if config:
                from pathlib import Path
                server_dir = Path(config.directory) if config.directory else settings.servers_dir / self.server_name
                self._player_mgr = PlayerManager(server_dir, self.server_name)
            else:
                self._player_mgr = PlayerManager(settings.servers_dir / self.server_name, self.server_name)
        return self._player_mgr

    def _load_data(self) -> None:
        """Load all player management data."""
        pm = self._get_player_manager()

        # Load ops
        op_list = self.query_one("#op-list", ListView)
        op_list.clear()
        for op in pm.get_ops():
            op_list.append(ListItem(Label(f"  {op.name} (Level {op.level})")))

        # Load whitelist
        wl_list = self.query_one("#whitelist-list", ListView)
        wl_list.clear()
        for entry in pm.get_whitelist():
            wl_list.append(ListItem(Label(f"  {entry.name}")))

        # Load bans
        ban_list = self.query_one("#ban-list", ListView)
        ban_list.clear()
        for ban in pm.get_banned_players():
            ban_list.append(ListItem(Label(f"  🔨 {ban.name} — {ban.reason}")))
        for ban in pm.get_banned_ips():
            ban_list.append(ListItem(Label(f"  🌐 {ban.ip} — {ban.reason}")))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        pm = self._get_player_manager()
        live_status = self.query_one("#live-status", Static)

        # ── Ops ──
        if event.button.id == "op-btn":
            name = self.query_one("#op-name-input", Input).value.strip()
            if name:
                pm.op(name, level=4)
                live_status.update(f"✅ {name} is now OP")
                self._load_data()

        elif event.button.id == "deop-btn":
            name = self.query_one("#op-name-input", Input).value.strip()
            if name:
                pm.deop(name)
                live_status.update(f"✅ {name} is no longer OP")
                self._load_data()

        # ── Whitelist ──
        elif event.button.id == "wl-add-btn":
            name = self.query_one("#whitelist-name-input", Input).value.strip()
            if name:
                pm.whitelist_add(name)
                live_status.update(f"✅ {name} added to whitelist")
                self._load_data()

        elif event.button.id == "wl-remove-btn":
            name = self.query_one("#whitelist-name-input", Input).value.strip()
            if name:
                pm.whitelist_remove(name)
                live_status.update(f"✅ {name} removed from whitelist")
                self._load_data()

        # ── Bans ──
        elif event.button.id == "ban-btn":
            target = self.query_one("#ban-input", Input).value.strip()
            reason = self.query_one("#ban-reason-input", Input).value.strip() or "Banned by operator"
            if target:
                pm.ban(target, reason=reason)
                live_status.update(f"✅ {target} has been banned")
                self._load_data()

        elif event.button.id == "ban-ip-btn":
            target = self.query_one("#ban-input", Input).value.strip()
            reason = self.query_one("#ban-reason-input", Input).value.strip() or "Banned by operator"
            if target:
                pm.ban_ip(target, reason=reason)
                live_status.update(f"✅ IP {target} has been banned")
                self._load_data()

        elif event.button.id == "pardon-btn":
            target = self.query_one("#ban-input", Input).value.strip()
            if target:
                pm.pardon(target)
                live_status.update(f"✅ {target} has been pardoned")
                self._load_data()

        elif event.button.id == "pardon-ip-btn":
            target = self.query_one("#ban-input", Input).value.strip()
            if target:
                pm.pardon_ip(target)
                live_status.update(f"✅ IP {target} has been pardoned")
                self._load_data()

        # ── Live commands ──
        elif event.button.id == "kick-btn":
            name = self.query_one("#live-player-input", Input).value.strip()
            if name:
                result = await pm.kick(name)
                live_status.update(f"✅ Kicked {name}" if result["success"] else "❌ Failed to kick")

        elif event.button.id in ("gms-btn", "gmc-btn", "gma-btn", "gmsp-btn"):
            name = self.query_one("#live-player-input", Input).value.strip()
            gm_map = {"gms-btn": "survival", "gmc-btn": "creative", "gma-btn": "adventure", "gmsp-btn": "spectator"}
            gm = gm_map[event.button.id]
            if name:
                result = await pm.set_gamemode(name, gm)
                live_status.update(f"✅ Set {name} to {gm}" if result["success"] else "❌ Failed")

        elif event.button.id == "tp-btn":
            player = self.query_one("#live-player-input", Input).value.strip()
            target = self.query_one("#tp-target-input", Input).value.strip()
            if player and target:
                result = await pm.teleport(player, target)
                live_status.update(f"✅ Teleported {player} to {target}" if result["success"] else "❌ Failed")

        elif event.button.id == "give-btn":
            player = self.query_one("#live-player-input", Input).value.strip()
            item = self.query_one("#give-item-input", Input).value.strip()
            if player and item:
                result = await pm.give(player, item, 64)
                live_status.update(f"✅ Gave {item} x64 to {player}" if result["success"] else "❌ Failed")

        elif event.button.id == "day-btn":
            result = await pm.time_set("day")
            live_status.update("✅ Time set to day" if result["success"] else "❌ Failed")

        elif event.button.id == "night-btn":
            result = await pm.time_set("night")
            live_status.update("✅ Time set to night" if result["success"] else "❌ Failed")

        elif event.button.id == "clear-weather-btn":
            result = await pm.weather("clear")
            live_status.update("✅ Weather cleared" if result["success"] else "❌ Failed")

        elif event.button.id == "rain-btn":
            result = await pm.weather("rain")
            live_status.update("✅ Weather set to rain" if result["success"] else "❌ Failed")

        elif event.button.id == "thunder-btn":
            result = await pm.weather("thunder")
            live_status.update("✅ Weather set to thunder" if result["success"] else "❌ Failed")

        elif event.button.id == "save-btn":
            result = await pm.save_all()
            live_status.update("✅ World saved" if result["success"] else "❌ Failed")
