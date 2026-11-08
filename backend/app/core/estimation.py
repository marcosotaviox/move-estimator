"""Calibration constants for volume estimates. Tune these with real job data."""

# --- Item volumes ---

SHAPE_FACTORS: dict[str, float] = {
    "solid": 1.0,      # fridges, wardrobes, boxes: nothing fits around them
    "irregular": 0.7,  # bikes, tables, armchairs: gaps get filled with small items
    "stackable": 0.5,  # dining chairs (incl. upholstered), stools: stack or get wrapped to fill gaps
}

# Used when an item dismantles but the catalog has no dismantled volume
DISMANTLED_FALLBACK_FACTOR = 0.3

# --- Boxes ---

BOX_VOLUME_M3 = 0.1

# bedrooms -> (min boxes, max boxes). 0 = studio. 4 covers 4 or more.
BOX_GUIDE: dict[int, tuple[int, int]] = {
    0: (10, 15),
    1: (20, 30),
    2: (30, 50),
    3: (50, 70),
    4: (70, 100),
}
MAX_GUIDE_BEDROOMS = 4

# +/- applied when the customer gives their own box count
CUSTOMER_BOXES_MARGIN = 0.10

# --- Totals ---

DEFAULT_PACKING_ALLOWANCE = 0.15  # blankets, wrapping, space that can't be used
FURNITURE_RANGE_MARGIN = 0.10     # +/- uncertainty on the furniture estimate

# (truck name, usable m3). Replace with each partner company's real fleet later.
TRUCKS: list[tuple[str, float]] = [
    ("2t", 11),
    ("4.5t", 22),
    ("6t", 30),
    ("8t", 38),
    ("10t", 48),
    ("12t", 55),
]


def box_guide(bedrooms: int) -> tuple[int, int]:
    return BOX_GUIDE[min(max(bedrooms, 0), MAX_GUIDE_BEDROOMS)]


def suggest_truck(volume_m3: float) -> str:
    for name, capacity in TRUCKS:
        if volume_m3 <= capacity:
            return name
    return f"{TRUCKS[-1][0]} + extra truck"