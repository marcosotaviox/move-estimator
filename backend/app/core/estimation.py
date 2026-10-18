"""Calibration constants for volume estimates. Tune these with real job data."""

SHAPE_FACTORS: dict[str, float] = {
    "solid": 1.0,      # fridges, wardrobes, boxes: nothing fits around them
    "irregular": 0.7,  # bikes, tables, armchairs: gaps get filled with small items
    "stackable": 0.5,  # dining chairs, stools: stack or nest
}

# Used when an item dismantles but the catalog has no dismantled volume
DISMANTLED_FALLBACK_FACTOR = 0.3