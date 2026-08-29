#!/usr/bin/env bash
# Install the Venture Studio poller as a systemd --user timer.
# Copies the unit files into ~/.config/systemd/user/, reloads the user
# systemd instance, and enables the timer. Idempotent: safe to re-run.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="$HERE/systemd"
USER_SYSTEMD="$HOME/.config/systemd/user"

mkdir -p "$USER_SYSTEMD"

cp "$UNIT_SRC/legion-studio-poll.service" "$USER_SYSTEMD/legion-studio-poll.service"
cp "$UNIT_SRC/legion-studio-poll.timer" "$USER_SYSTEMD/legion-studio-poll.timer"

systemctl --user daemon-reload
systemctl --user enable --now legion-studio-poll.timer

systemctl --user list-timers legion-studio-poll.timer
