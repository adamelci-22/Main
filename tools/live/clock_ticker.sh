#!/bin/bash
# Clock-driven slot ticker (RULEBOOK D1, v5.2.9). Prints one line at HH:MM:06 on every 5-minute mark from START to END (ET), then exits.
# Use with the Monitor tool (timeout_ms 1800000, re-arm on expiry). Usage: clock_ticker.sh [UTC_OFFSET_HOURS=4] [START=10:00] [END=13:30]
# The 6 seconds let the bar ending at the mark be published. An event is a checkpoint trigger: run the slot's usual checkpoint,
# and if the scheduled primary for the same slot already ran, answer with one line (and vice versa).
off=${1:-4}; start=${2:-10:00}; end=${3:-13:30}; last=""
while true; do
  s=$(date -u +%s); et=$(date -u -d "@$((s-off*3600))" +%H:%M); sec=$((s%60)); mm=$((10#${et#*:}%5))
  if [ "$mm" = "0" ] && [ "$sec" -ge 6 ] && [ "$et" != "$last" ] && [[ ! "$et" < "$start" ]] && [[ ! "$et" > "$end" ]]; then
    last=$et; echo "CLOCK SLOT $et ET fired at $(date -u +%T) UTC"; [[ "$et" == "$end" ]] && exit 0
  fi
  [[ "$et" > "$end" ]] && exit 0
  sleep 1
done
