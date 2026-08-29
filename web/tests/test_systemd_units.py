# web/tests/test_systemd_units.py
"""The Studio poller's systemd --user units are hand-written INI files with
no test runner of their own. Parse the real bytes so a typo in the deploy
path, the cadence, or the WantedBy target fails loudly here instead of
silently at install time on legion2."""
from __future__ import annotations
import configparser
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent
SYSTEMD_DIR = PLUGIN_DIR / "scripts" / "systemd"
DEPLOY_WORKTREE = "/home/shawn/.local/opt/legion-plugins-main/plugins/claude-ventures"


def _parse(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(strict=False)
    cp.optionxform = str  # preserve case: systemd keys are case-sensitive
    cp.read(path, encoding="utf-8")
    return cp


def test_service_unit_execs_the_deploy_worktrees_poller_once():
    cp = _parse(SYSTEMD_DIR / "legion-studio-poll.service")
    assert cp.get("Service", "Type") == "oneshot"
    exec_start = cp.get("Service", "ExecStart")
    assert f"{DEPLOY_WORKTREE}/web/studio_poll.py" in exec_start
    assert exec_start.strip().endswith("--once")
    assert cp.get("Service", "WorkingDirectory") == f"{DEPLOY_WORKTREE}/web"


def test_timer_unit_runs_every_minute_and_is_persistent():
    cp = _parse(SYSTEMD_DIR / "legion-studio-poll.timer")
    assert cp.get("Timer", "OnUnitActiveSec") == "60"
    assert cp.get("Timer", "Persistent") == "true"
    assert cp.get("Install", "WantedBy") == "timers.target"


def test_installer_copies_reloads_and_enables_idempotently():
    text = (PLUGIN_DIR / "scripts" / "install-studio-poll.sh").read_text(encoding="utf-8")
    assert "legion-studio-poll.service" in text
    assert "legion-studio-poll.timer" in text
    assert "$HOME/.config/systemd/user" in text
    assert "systemctl --user daemon-reload" in text
    assert "systemctl --user enable --now legion-studio-poll.timer" in text
    assert "systemctl --user list-timers legion-studio-poll.timer" in text
    assert "set -euo pipefail" in text
