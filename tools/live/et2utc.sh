#!/bin/bash
# Convert a New York wall-clock time to the UTC timestamp that create_trigger needs (DST-proof; RULEBOOK D1, v5.2.15).
# Usage: et2utc.sh "2026-11-02 10:00"   ->  2026-11-02T15:00:00Z
# Never hard-code the UTC offset when arming: ET = UTC-4 until Sun 2026-11-01 (EDT), UTC-5 from Mon 2026-11-02 (EST), back to UTC-4 on Sun 2027-03-14.
TZ=America/New_York date -d "$1" +%s | xargs -I{} date -u -d @{} +%Y-%m-%dT%H:%M:%SZ
