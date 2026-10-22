#!/bin/bash
# One-shot slot waiter (RULEBOOK D1, v5.2.12). Sleeps on the system clock until HH:MM:06 ET today, prints one line, exits.
# Run it with Bash run_in_background (timeout 7200000, description "Slot waiter HH:MM"): the exit wakes the session at that slot, independent of the scheduler.
# Usage: slot_clock.sh HH:MM [UTC_OFFSET_HOURS=4]. The 6 seconds let the bar ending at HH:MM be published.
# Appends date,slot,due_epoch,fired_epoch to archive/waiter_log.csv for the success-rate report (tools/live/slot_report.py).
slot=$1; off=${2:-4}; today=$(date -u -d "now - $off hours" +%F)
due=$(( $(date -u -d "$today ${slot}:00 UTC" +%s) + off*3600 ))
while [ "$(date -u +%s)" -lt "$((due+6))" ]; do sleep 1; done
now=$(date -u +%s)
echo "$today,$slot,$due,$now" >> "$(dirname "$0")/../../archive/waiter_log.csv"
echo "CLOCK SLOT $slot ET fired at $(date -u +%T) UTC"
