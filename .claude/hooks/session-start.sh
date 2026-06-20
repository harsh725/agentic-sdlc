#!/usr/bin/env bash
# Caffeinated mode — start (plan §9).
# Tie a wake assertion to the long-lived orchestrator process so the laptop
# stays awake only while it is working. Opt-in via CAFFEINATE_MODE=1. Tolerant of
# non-macOS hosts. Defense in depth: -w (release on PID exit) + -t (idle timeout
# so a crashed run can't hold the machine awake forever).
set -euo pipefail

[ "${CAFFEINATE_MODE:-0}" = "1" ] || exit 0
command -v caffeinate >/dev/null 2>&1 || exit 0   # not macOS / no caffeinate

mkdir -p "$HOME/.agentic-sdlc"
ORCH_PID="${ORCHESTRATOR_PID:-$PPID}"

# Shorter awake window on battery (deep-discharge safety); longer on AC.
if pmset -g ps 2>/dev/null | grep -q 'AC Power'; then
  TIMEOUT=14400   # 4h
else
  TIMEOUT=1800    # 30m
fi

# -i system idle sleep, -m disk idle sleep. Display sleep is deliberately allowed
# (headless run); -s/-u dropped (AC-only / redundant). See plan §9.1.
caffeinate -i -m -w "$ORCH_PID" -t "$TIMEOUT" &
echo $! > "$HOME/.agentic-sdlc/caffeinate.pid"
echo "caffeinated: holding wake for PID $ORCH_PID (timeout ${TIMEOUT}s)"
