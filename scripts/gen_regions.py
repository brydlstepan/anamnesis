#!/usr/bin/env python3
"""Generate backend/anamnesis/data/regions.json from docs/regions.md.

docs/regions.md is the human-edited source of truth; run this after editing it:
    python scripts/gen_regions.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "regions.md"
OUT = ROOT / "backend" / "anamnesis" / "data" / "regions.json"

SECTION_PARENTS = {
    "Pseudo-regions": None,
    "Head & neck": "head_neck",
    "Trunk — thorax": "thorax",
    "Trunk — abdomen & pelvis": "abdomen_pelvis",
    "Spine": "spine",
    "Upper limb": "upper_limb",
    "Lower limb": "lower_limb",
}
GROUP_LABELS = {
    "head_neck": ("Head & neck", "Hlava a krk"),
    "thorax": ("Thorax", "Hrudník"),
    "abdomen_pelvis": ("Abdomen & pelvis", "Břicho a pánev"),
    "spine": ("Spine", "Páteř"),
    "upper_limb": ("Upper limb", "Horní končetina"),
    "lower_limb": ("Lower limb", "Dolní končetina"),
}


def main() -> None:
    regions = []
    for gid, (en, cs) in GROUP_LABELS.items():
        regions.append({"id": gid, "parent": None, "group": True, "lateral": False,
                        "projected": False, "sex": None, "labels": {"en": en, "cs": cs}})
    parent = None
    all_lateral = False
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            title = line[3:]
            parent = next((p for k, p in SECTION_PARENTS.items() if title.startswith(k)), None)
            all_lateral = "(all L)" in title
            continue
        m = re.match(r"^\| `([a-z_]+)` \| ([^|]+) \| ([^|]+) \|(?: ([^|]*) \|)?", line)
        if not m:
            continue
        rid, en, cs, flags = m.group(1), m.group(2).strip(), m.group(3).strip(), (m.group(4) or "")
        flagset = {f.strip() for f in flags.split(",")}
        regions.append({
            "id": rid,
            "parent": parent,
            "group": False,
            "lateral": all_lateral or "L" in flagset,
            "projected": "P" in flagset,
            "sex": "male" if "M" in flagset else "female" if "F" in flagset else None,
            "labels": {"en": en, "cs": cs},
        })
    ids = [r["id"] for r in regions]
    assert len(ids) == len(set(ids)), "duplicate region ids"
    OUT.write_text(json.dumps(regions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(regions)} regions to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
