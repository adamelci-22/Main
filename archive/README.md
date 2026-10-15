# Archive map

**Live records (the scheduled checkpoints read and write these paths — do not move):**
- `live_trades.csv` — real trades from 2026-10-16, append-only (RULEBOOK D2).
- `paper_trades.csv`, `paper_state.json` — the model's own record, written by `paper.py --close`.
- `paper_rvol_<day>.json` — the day's RVOL tie-break baseline.

**`trade_history/`** — closed history, not in use.
- `old_system_trades.csv` — every real trade of the retired ORB system (2026-08 – 10-15).
- `old_system_selection_log.csv` — its candidate-ranking log.

**`former_systems/`** — retired rules and tools; nothing here is in force.
- `RULEBOOK_v3.132_full.md` — the complete old rulebook, word for word.
- `SHELVED_SELECTION_RULES.md` — the ORB gate / ranking rules shelved 2026-10-15, with the evidence.
- `EXPERIMENTS.md`, `RULE_HISTORY.md` — old proposal log and a stale rule-change index.
- `tools/` — old gate, profile and replay tools (see its README).

**Current system:** `/RULEBOOK.md` (rules), `tools/live/paper.py` (engine), `tools/backtest/` (evidence; see its README and `results/`).
