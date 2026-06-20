#!/usr/bin/env bash
# Caffeinated mode — end / safety net (plan §9).
# Release the wake assertion and reap any stray caffeinate processes so a crashed
# run never leaves the machine awake.
set -uo pipefail

PIDFILE="$HOME/.agentic-sdlc/caffeinate.pid"
if [ -f "$PIDFILE" ]; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"
fi
# Sweep any orphaned PID-tied caffeinate assertions.
pkill -f 'caffeinate.*-w' 2>/dev/null || true
exit 0
