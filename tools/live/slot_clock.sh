#!/bin/bash
# One-shot slot waiter (RULEBOOK D1, v5.2.10). Sleeps on the system clock until HH:MM:06 ET today, prints one line, exits.
# Run it with Bash run_in_background (timeout 7200000): the exit wakes the session at that slot, independent of the scheduler.
# Usage: slot_clock.sh HH:MM [UTC_OFFSET_HOURS=4]. The 6 seconds let the bar ending at HH:MM be published.
slot=$1; off=${2:-4}; today=$(date -u -d "now - $off hours" +%F)
target=$(( $(date -u -d "$today ${slot}:00 UTC" +%s) + off*3600 + 6 ))
while [ "$(date -u +%s)" -lt "$target" ]; do sleep 1; done
echo "CLOCK SLOT $slot ET fired at $(date -u +%T) UTC"
