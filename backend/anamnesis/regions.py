"""Body-region vocabulary (SPEC §5). Source of truth: docs/regions.md → scripts/gen_regions.py."""

import json
from functools import lru_cache
from importlib import resources
from typing import Any

SIDES = ("left", "right", "both")


@lru_cache
def all_regions() -> list[dict[str, Any]]:
    text = resources.files("anamnesis").joinpath("data/regions.json").read_text(encoding="utf-8")
    return json.loads(text)


@lru_cache
def regions_by_id() -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in all_regions()}


def descendants(region_id: str) -> set[str]:
    """region_id plus all regions below it in the hierarchy."""
    out = {region_id}
    changed = True
    while changed:
        changed = False
        for r in all_regions():
            if r["parent"] in out and r["id"] not in out:
                out.add(r["id"])
                changed = True
    return out


def parse_ref(ref: str) -> tuple[str, str | None]:
    """'knee:left' -> ('knee', 'left'). Raises ValueError with a helpful message."""
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("region must be a non-empty string")
    rid, _, side = ref.strip().partition(":")
    region = regions_by_id().get(rid)
    if region is None:
        close = [r for r in regions_by_id() if rid and (rid in r or r in rid)][:5]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(f"unknown region '{rid}'.{hint}")
    if side:
        if side not in SIDES:
            raise ValueError(f"invalid side '{side}' for region '{rid}' (use left/right/both)")
        if not region["lateral"]:
            raise ValueError(f"region '{rid}' is not lateral; remove ':{side}'")
        return rid, side
    if region["lateral"]:
        raise ValueError(f"region '{rid}' is lateral; use '{rid}:left', '{rid}:right' or '{rid}:both'")
    return rid, None


def normalize_region(value: Any) -> str | dict[str, Any]:
    """Accepts 'id[:side]' or {'region': 'id[:side]', 'offset': [x,y,z]}; returns canonical form."""
    if isinstance(value, dict):
        rid, side = parse_ref(value.get("region", ""))
        canonical = f"{rid}:{side}" if side else rid
        offset = value.get("offset")
        if offset is None:
            return canonical
        if (
            not isinstance(offset, list)
            or len(offset) != 3
            or not all(isinstance(v, int | float) and not isinstance(v, bool) and -1 <= v <= 1 for v in offset)
        ):
            raise ValueError("offset must be [x, y, z] with values between -1 and 1")
        return {"region": canonical, "offset": [float(v) for v in offset]}
    rid, side = parse_ref(value)
    return f"{rid}:{side}" if side else rid


def region_base_id(value: str | dict[str, Any]) -> str:
    ref = value["region"] if isinstance(value, dict) else value
    return ref.split(":", 1)[0]
