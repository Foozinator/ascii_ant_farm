"""Procedural colony generator — seeded, deterministic, agent-based accretion.

Call ``generate(width, height, seed)`` to get a fully populated :class:`GameState`
with rooms carved from sand and residents placed inside them. All randomness
routes through a single ``random.Random(seed)`` instance, so the same seed always
produces the same tank.

Algorithm: one seed room near the centre, then K accretion steps. Each step
finds the frontier (dirt cells adjacent to the existing network), picks one,
carves a short TUNNEL corridor, and hollows a 2D room at the end. Because
every new room grows from the frontier of the existing network, the colony
stays fully connected after every step.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from sim.state import CellType, GameState, Resident, Room

# Cycling room types assigned round-robin as rooms are carved.
_ROOM_TYPES = [CellType.NURSERY, CellType.OFFICES, CellType.PANTRY]

_CHARS_FILE = Path(__file__).parent.parent / "characters.json"

_FALLBACK_ARCHETYPES = [
    "bryce_hustle", "marlo_burnout", "pell_theorist", "sol_faithful",
    "brynn_wellness", "dell_consultant", "kit_influencer", "ramona_organizer",
    "gus_enforcer", "edna_oldtimer", "theo_native", "quentin_tycoon",
    "iris_doomer", "posey_connector",
]


def _load_archetypes() -> list[str]:
    try:
        data = json.loads(_CHARS_FILE.read_text(encoding="utf-8"))
        return [c["id"] for c in data["characters"]]
    except Exception:
        return _FALLBACK_ARCHETYPES


def _carve_rect(
    grid: list[list[CellType]],
    room_type: CellType,
    top_r: int,
    left_c: int,
    h: int,
    w: int,
    height: int,
    width: int,
) -> list[list[int]]:
    """Set a rectangular region to ``room_type``, respecting the 1-cell border."""
    cells: list[list[int]] = []
    for r in range(top_r, top_r + h):
        for c in range(left_c, left_c + w):
            if 1 <= r < height - 1 and 1 <= c < width - 1:
                grid[r][c] = room_type
                cells.append([r, c])
    return cells


def _accretion_step(
    grid: list[list[CellType]],
    rooms: list[Room],
    width: int,
    height: int,
    rng: random.Random,
    room_idx: int,
) -> None:
    """Carve one new room from the frontier, keeping the colony connected."""
    # Frontier: interior dirt cells with at least one non-dirt cardinal neighbour.
    frontier: list[tuple[int, int]] = []
    for r in range(1, height - 1):
        for c in range(1, width - 1):
            if grid[r][c] is not CellType.DIRT:
                continue
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < height and 0 <= nc < width and grid[nr][nc] is not CellType.DIRT:
                    frontier.append((r, c))
                    break

    if not frontier:
        return

    fr, fc = rng.choice(frontier)
    # The frontier cell becomes TUNNEL — connecting the new branch to the network.
    grid[fr][fc] = CellType.TUNNEL

    # Pick a direction into dirt, then carve a short corridor that way.
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    rng.shuffle(dirs)
    cr, cc = fr, fc
    max_corridor = max(1, min(4, min(width, height) // 6))
    corridor_len = rng.randint(1, max_corridor)

    for dr, dc in dirs:
        nr, nc = fr + dr, fc + dc
        if 1 <= nr < height - 1 and 1 <= nc < width - 1 and grid[nr][nc] is CellType.DIRT:
            # Carve corridor cells in this direction.
            r, c = fr, fc
            for _ in range(corridor_len):
                nr2, nc2 = r + dr, c + dc
                if 1 <= nr2 < height - 1 and 1 <= nc2 < width - 1 and grid[nr2][nc2] is CellType.DIRT:
                    grid[nr2][nc2] = CellType.TUNNEL
                    r, c = nr2, nc2
                else:
                    break
            cr, cc = r, c
            break  # only one direction per step

    # Hollow a 2D room at the corridor endpoint.
    room_type = _ROOM_TYPES[room_idx % len(_ROOM_TYPES)]
    room_w = rng.randint(2, max(2, min(5, width // 4)))
    room_h = rng.randint(2, max(2, min(4, height // 4)))
    top_r = max(1, min(height - 1 - room_h, cr - room_h // 2))
    left_c = max(1, min(width - 1 - room_w, cc - room_w // 2))
    cells = _carve_rect(grid, room_type, top_r, left_c, room_h, room_w, height, width)
    if cells:
        rooms.append(Room(id=f"room-{room_idx}", room_type=room_type, cells=cells))


def generate(width: int, height: int, seed: int) -> GameState:
    """Build a fully populated colony from scratch with the given seed.

    The grid starts as all-dirt; a seed room is placed near the centre; then
    K accretion steps grow the colony outward. Residents are seeded with
    archetype tags drawn from characters.json and placed inside rooms.
    """
    rng = random.Random(seed)
    archetypes = _load_archetypes()

    grid: list[list[CellType]] = [[CellType.DIRT] * width for _ in range(height)]
    rooms: list[Room] = []

    # Place initial seed room near centre.
    cr, cc = height // 2, width // 2
    seed_h = max(2, height // 6)
    seed_w = max(2, width // 6)
    top_r = max(1, cr - seed_h // 2)
    left_c = max(1, cc - seed_w // 2)
    cells = _carve_rect(grid, _ROOM_TYPES[0], top_r, left_c, seed_h, seed_w, height, width)
    if cells:
        rooms.append(Room(id="room-0", room_type=_ROOM_TYPES[0], cells=cells))

    # Run K accretion steps to populate the tank.
    K = max(5, (width * height) // 25)
    for i in range(1, K + 1):
        _accretion_step(grid, rooms, width, height, rng, i)

    # Seed residents: scale with tank, cap at available archetypes.
    num_residents = max(4, min(len(archetypes), K // 2))
    residents = _place_residents(rooms, num_residents, archetypes, rng)

    return GameState(
        width=width,
        depth=height,
        grid=grid,
        rooms=rooms,
        food=3.0,
        power=50.0,
        residents=residents,
        event_log=["The colony stirs in the carved dark."],
        metric="mood",
        turn=0,
    )


def _place_residents(
    rooms: list[Room],
    count: int,
    archetypes: list[str],
    rng: random.Random,
) -> list[Resident]:
    """Distribute residents across rooms with random positions and archetypes."""
    if not rooms:
        return []

    pool = archetypes.copy()
    rng.shuffle(pool)
    residents: list[Resident] = []
    for i in range(count):
        room = rooms[i % len(rooms)]
        archetype = pool[i % len(pool)]
        cell = rng.choice(room.cells)
        residents.append(
            Resident(
                id=f"ant-{i + 1:02d}",
                mood=round(rng.uniform(0.3, 0.8), 2),
                archetype=archetype,
                row=cell[0],
                col=cell[1],
                room_id=room.id,
            )
        )
    return residents
