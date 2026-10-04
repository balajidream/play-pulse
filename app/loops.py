"""Map a Play listing to a recognizable gameplay loop.

Title tokens decide the loop. Description tokens only confirm a title hint
(for example "block" in the title plus "blast" in the description). A lone
description word like "race" or "merge" is not enough — store copy uses those
casually and was producing nonsense loops.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PlayApp
from .query_planner import tokenize

GENERIC = frozenset(
    {
        "game",
        "games",
        "puzzle",
        "play",
        "free",
        "app",
        "apps",
        "new",
        "best",
        "fun",
        "offline",
        "online",
        "3d",
        "2d",
        "hd",
        "pro",
        "the",
        "and",
        "for",
    }
)


@dataclass(frozen=True)
class LoopDef:
    loop_id: str
    name: str
    twist: str


def _title(app: PlayApp) -> set[str]:
    return set(tokenize(app.title))


def _desc(app: PlayApp) -> set[str]:
    return set(tokenize(app.description))


def _has(toks: set[str], *words: str) -> bool:
    return bool(toks & set(words))


def classify_loop(app: PlayApp) -> str | None:
    title = _title(app)
    desc = _desc(app)
    blob = title | desc

    if _has(title, "survivor") or (
        _has(title, "io") and _has(blob, "survivor", "vampire", "horde")
    ):
        return "survivor_io"

    # Bus / parking sort: the title itself has to carry the vehicle or jam.
    if _has(title, "bus", "buses", "parking") and _has(
        blob, "jam", "sort", "parking", "unblock", "traffic", "passenger", "passengers"
    ):
        return "bus_parking_sort"
    if _has(title, "jam") and _has(title, "bus", "buses", "car", "cars", "parking", "park", "traffic"):
        return "bus_parking_sort"

    if _has(title, "water", "liquid") and _has(blob, "sort", "color", "colour", "tube", "tubes"):
        return "water_sort"

    # Merge only when the title says merge. "merge" inside a 2048 blurb is not a merge game.
    if _has(title, "merge"):
        return "merge"

    if _has(title, "idle") or (_has(title, "tycoon") and _has(title, "idle", "miner", "farm", "city")):
        return "idle_tycoon"

    # Tile blast: "blast" in the title, or a block/wood/tile title whose copy says blast.
    if _has(title, "blast") or (
        _has(title, "block", "blocks", "wood", "tile", "tiles") and _has(blob, "blast")
    ):
        return "tile_blast"

    if _has(title, "monopoly"):
        return "board_dice"

    # Match-3: title says match/matching, or a known scapes/royal match title.
    if _has(title, "match", "matching", "homescapes", "gardenscapes", "fishdom"):
        return "match3"
    if _has(title, "royal") and _has(blob, "match", "matching"):
        return "match3"
    if _has(title, "candy", "crush", "jewel", "jewels") and _has(blob, "match", "matching"):
        return "match3"

    if _has(title, "farm", "township") and not _has(title, "match"):
        return "farm_sim"

    # Racing only from the title. Descriptions say "race against the clock" constantly.
    if _has(title, "race", "racing", "racer") and not _has(title, "jam", "parking", "sort"):
        return "racing"

    return None


LOOP_DEFS: dict[str, LoopDef] = {
    "bus_parking_sort": LoopDef(
        "bus_parking_sort",
        "bus / parking sort",
        "a rule or fantasy those jam titles do not already lead with "
        "(timed island bays, passenger matching, or a non-vehicle board) — "
        "not another title built from jam, sort, bus, or parking",
    ),
    "tile_blast": LoopDef(
        "tile_blast",
        "tile blast",
        "a blast board that is not another Block Blast or Wood Block title — "
        "those names already chart",
    ),
    "water_sort": LoopDef(
        "water_sort",
        "water / color sort",
        "a sort puzzle whose title is not Water Sort or Color Sort",
    ),
    "survivor_io": LoopDef(
        "survivor_io",
        "survivor.io style",
        "a horde survivor whose title is not Survivor, .io, or Vampire — "
        "change the fantasy, not the suffix",
    ),
    "merge": LoopDef(
        "merge",
        "merge",
        "a merge board whose title theme is not already Mansion, Garden, or Dragons",
    ),
    "idle_tycoon": LoopDef(
        "idle_tycoon",
        "idle tycoon",
        "an idle loop whose title is not Miner, Farm, or City Tycoon",
    ),
    "match3": LoopDef(
        "match3",
        "match-3",
        "a match-3 whose title is not Match, Royal, Homescapes, or Gardenscapes — "
        "the mechanic is owned; only a different fantasy would be new",
    ),
    "board_dice": LoopDef(
        "board_dice",
        "board / dice",
        "a board game that is not a Monopoly-style title — that incumbent already charts",
    ),
    "farm_sim": LoopDef(
        "farm_sim",
        "farm sim",
        "a farm or town sim that is not another Township or Farm City",
    ),
    "racing": LoopDef(
        "racing",
        "racing",
        "a racer whose title is not Race or Racing Master",
    ),
}


def loop_name(loop_id: str) -> str:
    defin = LOOP_DEFS.get(loop_id)
    return defin.name if defin else loop_id


def loop_twist(loop_id: str) -> str:
    defin = LOOP_DEFS.get(loop_id)
    return defin.twist if defin else "a twist those exact titles do not already use"
