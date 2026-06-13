# TODO / Open Questions

Items that need a decision or cross-module coordination. Coordination items touch
the `sim` ⇄ `llm` seam and **must not be fixed unilaterally** — the `sim` side
generally moves first. Items marked **Decided** record a direction agreed in design
discussion; they still need the sim-first implementation ordering. Coordination
items have a matching `TODO(coordination)` marker in the code.

## Coordination (sim ⇄ llm seam)

### 1. `mood_deltas` are sim-owned; reconcile mood units while you're there

- **Now:** `ColonyReport.mood_deltas` is populated on the `llm` side. The stub fills
  canned values; the Ollama model may emit its own. Both can **contradict** the
  deterministic mood numbers from `sim.tick` (the walking-skeleton demo showed the
  report saying `+0.02` while residents actually dropped ~`0.06`).
- **Decided:** mood numbers come from `sim.tick` (deterministic). The LLM owns
  prose. `flags` are **soft, aggregate** signals — count them across the colony and
  act on the trend; never let a single resident's flag pull a mechanical lever (they
  jitter run-to-run; `rumor`↔`calm` flipped on identical input in testing).
- **Coupled units bug:** `mood` is a `0.0–1.0` float, but the digest schema asks the
  model for `mood_delta` as an integer `-2..2` — incompatible scales (a `+2` delta
  is twice the entire range). When sim takes ownership, emit deltas as **small
  floats consistent with `0.0–1.0`** and drop the `-2..2` integer framing. Pin the
  mood range in the contract docs at the same time.
- **Code:** `TODO(coordination)` in `llm/backends.py` (stub + Ollama `digest`).
- **Owner:** sim computes deltas in tick + pins range → llm drops model-sourced
  deltas and the `-2..2` schema.

### 2. Residents carry real catalog ids

- **Now:** the `sim`-side branch already assigns each resident a catalog id drawn at
  random from the character pool (part of the fill work), so the placeholder role
  tags (`forager`/`nurse`/`drone`/`queen`) are on their way out. `llm/personas.py`
  still falls back to a neutral card for any unmatched tag.
- **Decided:** residents carry real per-character catalog ids; voices match per id.
- **Remaining:** once the sim change merges, re-key (or retire) the interim seeds
  file and drop the role-tag matching path; keep the neutral-default fallback only
  as a safety net.
- **Code:** `TODO(coordination)` in `llm/personas.py` (`PersonaCatalog.card_for`).
- **Owner:** sim (assign ids — in progress) → llm (drop role-tag path).

### 3. One character file — converge on the rich catalog

- **Now:** two files exist, and the names collide confusingly:
  - root `characters.json` (committed `62665b6`) — the rich **prune pool**: real
    catalog ids (`bryce_hustle`, `marlo_burnout`, …), draft/unlocked schema
    (`satire`/`normalcy`/`coping`/`behavior_tell`/`voice`/`voice_sample`). **Not
    wired into code yet.**
  - `llm/character_seeds.json` (this branch) — a small interim file the code
    actually loads, keyed to role tags, minimal schema. A scaffolding expedient to
    get voices working today.
- **Decided:** the rich root catalog is the **single source of truth**; the interim
  `llm/` file is temporary and gets deleted once item 2 lands. Card content lives in
  a **content path, not under `llm/`** (code), consistent with the licensing split —
  code is PolyForm, card content is CC BY-NC, so it shouldn't sit inside a code
  module.
- **Remaining (decisions):**
  - Final content location + name (root `characters.json` vs a `content/` or
    `data/` dir), and add a content `LICENSE` (CC BY-NC) alongside it.
  - Run the pool through the distinctiveness / constrained-JSON gate described in
    the catalog `_meta`, prune the duds, then lock the card schema. **Stress the
    optimistic-corporate cluster first** (`bryce_hustle`, `dell_consultant`,
    `brynn_wellness`, `kit_influencer`, `quentin_tycoon`) — that's where the voices
    are likeliest to converge.
  - Point `llm/personas.py` at the chosen file; delete the interim one.
- **Owner:** joint (llm + character-pool owner).

## Smaller open questions

### Who speaks — **Decided: sim-side**

Speaker selection lives on the sim side: voices are sampled from the **extremes of
the mood distribution** (the silent middle doesn't file). The llm digest voices
whoever it is handed. The current first-`N` (`LLM_DIGEST_VOICES`, default 3) is a
**temporary stand-in** until the sim implements distribution-based selection.

### Naming in prose — surface settled, deeper question open

- Prose should address residents by a **human display name, never the technical id**
  (`ant-02` in colony dialogue breaks immersion). Settled.
- Open underneath: **are catalog entries unique named individuals, or reusable
  archetype templates?** If unique, "Bryce" is one person and the display name *is*
  the catalog name. If templates, many residents share an archetype and each needs
  its own generated display name distinct from the type. Genuinely undecided, and it
  determines the naming scheme — do not lock the scheme before deciding this.

### Persona output shape — open

Two unsettled conventions, both affecting the digest prompt and the renderer:

- **Stage directions:** do personas emit action beats (Bryce clapping his hands) or
  speech only? Charming as flavor, noise in a tight UI — pick one.
- **Length cap:** big personalities overran the "2–3 sentences" instruction in
  testing (Bryce wrote four paragraphs). Enforce a hard cap via schema/prompt so one
  verbose resident can't blow the panel or the context budget.

### Knob semantics — needs documenting (sim-side)

`feed 5` currently behaves as a **level** (set the dial to 5), not a **quantity
added** (+5 food). Either is fine; pick one and write it down, since it changes how
the tutorial teaches the knob.

## Decided in principle, not yet built (roadmap — non-blocking)

Captured so these don't get lost in chat history; none block current work.

- **Growth over time:** the accretion primitive is built and exposed but **not wired
  into the tick** — one-shot fill only for now. Per-tick growth is the deferred
  mechanic.
- **Function vs costume:** buildings are a small set of mechanical *functions*
  wearing many *names*; the name is mood-colored and re-skins as the colony's mood
  shifts, while function stays legible from form (glyph/color/region), not the name.
- **No dashboards:** information reaches the player through visible behavior,
  color-coded residents, and persona digests — plus tickets (the *filed* truth) read
  against the glass (the *unfiled* truth). Instruments are physical objects that
  contaminate what they measure (observer effect).
- **Three-pillar metrics + Goodhart:** happiness / meaning / psychological richness
  as partly-orthogonal axes; the player reads only chosen proxies, which rot under
  optimization (a gaming coefficient that grows while watched, decays when ignored).
- **Knob registry as shared artifact:** the command grammar's vocabulary == the
  canonical knob list == the material layer's full surface; both the command parser
  and any future widget panel render from it.
- **Framing:** new keeper on a fresh migrant colony; tutorial is diegetic, short,
  and silent (the silence calibrates the player's ear). Top-down play view, vertical
  "ant farm" identity in title, key art, and language.
  