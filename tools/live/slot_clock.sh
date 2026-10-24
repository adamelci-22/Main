#!/bin/bash
# One-shot slot waiter (RULEBOOK D1, v5.2.12; DST-proof since v5.2.15). Sleeps on the system clock until HH:MM:06 America/New_York today, prints one line, exits.
# Run it with Bash run_in_background (timeout 7200000, description "Slot waiter HH:MM"): the exit wakes the session at that slot, independent of the scheduler.
# Usage: slot_clock.sh HH:MM [ignored]. The time zone is read from the system's tz database, so the EDT/EST change on 2026-11-01 needs no argument.
# The old second argument (UTC offset) is ignored; a mismatch with the real offset is printed as a warning.
# The 6 seconds let the bar ending at HH:MM be published.
# Appends date,slot,due_epoch,fired_epoch to archive/waiter_log.csv for the success-rate report (tools/live/slot_report.py).
slot=$1
today=$(TZ=America/New_York date +%F)
due=$(TZ=America/New_York date -d "$today ${slot}:00" +%s)
real_off=$(( -$(TZ=America/New_York date +%z | sed 's/^\([+-]\)0*\([0-9]\)\([0-9]\)\{2\}$/\1\2/') ))
[ -n "$2" ] && [ "$2" != "$real_off" ] && echo "WARNING: offset argument $2 ignored; the real UTC offset today is $real_off (ET = UTC-$real_off)"
while [ "$(date -u +%s)" -lt "$((due+6))" ]; do sleep 1; done
now=$(date -u +%s)
echo "$today,$slot,$due,$now" >> "$(dirname "$0")/../../archive/waiter_log.csv"
echo "CLOCK SLOT $slot ET fired at $(date -u +%T) UTC"
