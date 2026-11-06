"""PLACEHOLDER category assignment. NOT official CAA categories (see config)."""
import json
from . import materials

_CFG = json.load(open(materials.ROOT / "config" / "categories.json"))
CATEGORIES = _CFG["categories"]
THRESH = _CFG["significance_threshold_mass_fraction"]

# Families that never make a component "multi-material" on their own.
IGNORED = {"METALLIZATION"}


def significant_families(fractions, threshold=THRESH):
    return sorted(f for f, x in fractions.items() if f not in IGNORED and x >= threshold)


def assign(fmt, fractions):
    """fmt in {rigid, flexible, paper}; fractions = {family: mass fraction}."""
    sig = significant_families(fractions)
    if len(sig) == 1:
        return _CFG["mono_rules"].get(fmt, {}).get(sig[0]) or \
               _CFG["mono_rules"]["rigid"].get(sig[0])
    if fractions.get("PAPER", 0) > 0.5:
        return _CFG["multi_rules"]["paper_dominant"]
    return _CFG["multi_rules"]["flexible" if fmt == "flexible" else "rigid"]


def near_threshold(fractions, band=0.02):
    """True if any family fraction is within +/-band of the threshold (ambiguous)."""
    return any(abs(x - THRESH) < band for f, x in fractions.items() if f not in IGNORED)
