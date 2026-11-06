"""Material property table loader + material-name normalisation."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TABLE = None


def table():
    """Return {material: row dict} from config/materials.csv (densities as floats)."""
    global _TABLE
    if _TABLE is None:
        _TABLE = {}
        with open(ROOT / "config" / "materials.csv") as f:
            for row in csv.DictReader(f):
                for k in ("density_min_g_cm3", "density_nominal_g_cm3", "density_max_g_cm3"):
                    row[k] = float(row[k])
                _TABLE[row["material"]] = row
    return _TABLE


def density(material, which="nominal"):
    return table()[material][f"density_{which}_g_cm3"]


# Non-density "materials" (specified by coat weight / grammage).
NON_DENSITY_FAMILIES = {"PAPER": "PAPER", "ADHESIVE": "ADHESIVE", "COATING": "COATING"}


def family(material):
    if material in NON_DENSITY_FAMILIES:
        return NON_DENSITY_FAMILIES[material]
    return table()[material]["family"]


# Ordered synonym list: first match wins, so specific names come before generic.
SYNONYMS = [
    ("LLDPE", r"\b(m?lldpe|linear low[- ]density polyethylene)\b"),
    ("LDPE", r"\b(ldpe|low[- ]density polyethylene)\b"),
    ("HDPE", r"\b(hdpe|high[- ]density polyethylene)\b"),
    ("EVOH", r"\b(evoh|ethylene[- ]vinyl alcohol)\b"),
    ("PET", r"\b(r?pet|bopet|opet|apet|cpet|vmpet|met[- ]?pet|polyester|polyethylene terephthalate)\b"),
    ("PP", r"\b(bopp|opp|cpp|pp|vmopp|met[- ]?opp|polypropylene)\b"),
    ("PE", r"\b(pe|polyethylene)\b"),
    ("PS", r"\b(ps|hips|polystyrene)\b"),
    ("PVC", r"\b(pvc|polyvinyl chloride)\b"),
    ("PA6", r"\b(pa6?|bopa|nylon|polyamide)\b"),
    ("ALUMINUM", r"\b(al|alu|aluminium|aluminum|foil)\b"),
    ("STEEL", r"\b(steel|tinplate|tfs)\b"),
    ("GLASS", r"\b(glass|flint|amber glass)\b"),
    ("PAPER", r"\b(paper|kraft|sbs|paperboard|board|cuk|ccnb|carton ?board|folding boxboard|fbb)\b"),
    ("ADHESIVE", r"\b(adhesive|pu adh|pur|tie[- ]layer|tie)\b"),
    ("COATING", r"\b(coating|lacquer|varnish|primer|ink)\b"),
]


def normalize(name):
    """Map a free-text material name to a canonical table key, or None."""
    s = name.lower().replace("®", "")
    for canon, pat in SYNONYMS:
        if re.search(pat, s):
            return canon
    return None
