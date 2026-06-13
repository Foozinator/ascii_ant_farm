# TODO / Open Questions

Items that need a decision or cross-module coordination. These are deliberately
**not fixed unilaterally** — they touch the `sim` ⇄ `llm` seam and the `sim` side
needs to move first. Each has a matching `TODO(coordination)` marker in the code.

## Coordination (sim ⇄ llm seam)

### 1. `mood_deltas` should be sim-owned, not model-invented

- **Now:** `ColonyReport.mood_deltas` is populated on the `llm` side. The stub
  fills canned per-resident values; the Ollama model may emit its own. Both can
  **contradict** the deterministic mood numbers produced by `sim.tick`.
- **Agreed direction:** mood numbers come from `sim.tick` (deterministic); the LLM
  owns prose, with `flags` as soft, aggregate signals only.
- **Needed:** a sim-side change to compute `mood_deltas` during the tick, then have
  the digest stop inventing them.
- **Code:** `TODO(coordination)` in `llm/backends.py` (stub + Ollama `digest`).
- **Owner:** sim agent, then llm follow-up to drop model-sourced deltas.

### 2. Residents need real catalog ids (archetype tags don't match persona ids)

- **Now:** residents carry placeholder role tags (`forager`/`nurse`/`drone`/
  `queen`). `llm/personas.py` reads the interim `llm/character_seeds.json`, which
  is keyed to those tags so voices land today; any unmatched tag falls back to the
  neutral default card.
- **Agreed direction:** residents carry real per-character catalog ids; the seeds
  file is re-keyed to those ids and matched per character.
- **Needed:** a sim-side change to assign catalog ids to residents, then re-key
  the seeds to match.
- **Code:** `TODO(coordination)` in `llm/personas.py` (`PersonaCatalog.card_for`)
  and the `_comment` in `llm/character_seeds.json`.
- **Owner:** sim agent, then llm to re-key the seeds.

### 2a. Two character files exist — pick one source of truth

- **Now:** there are **two** persona files:
  - `characters.json` (repo root, committed in 62665b6) — the rich "prune pool":
    real catalog ids (`bryce_hustle`, `marlo_burnout`, …) with a *draft, unlocked*
    schema (`satire`/`normalcy`/`coping`/`behavior_tell`/`voice`/`voice_sample`).
    **Not wired into the code yet.**
  - `llm/character_seeds.json` (this branch) — a small interim file the llm code
    actually loads, keyed by the current role tags, with a minimal card schema.
- **Needed (decision):** choose the single source of truth + final card schema,
  run the cards through the distinctiveness / constrained-JSON gate described in
  `characters.json` `_meta`, then point `llm/personas.py` at the chosen file and
  drop the other. Also settle naming/location (`characters.json` at root vs
  `character_seeds.json` under `llm/`).
- **Owner:** llm + whoever owns the character pool (joint).

## Smaller open questions

- **Who speaks:** the digest voices the first `N` residents
  (`LLM_DIGEST_VOICES`, default 3). Distribution-based speaker selection is
  considered sim-side — confirm where that logic should live.
- **Naming in prose:** should narration address residents by persona name
  (e.g. "Vela") or by id ("ant-02")? The model is currently given both and chooses.
- **Resident `mood` range:** `mood` is treated as `0.0–1.0` across sim/llm — worth
  pinning down in the contract docs so both sides agree on bounds.
