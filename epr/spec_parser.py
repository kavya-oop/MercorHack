"""The CHECKER's own parser for raw spec-sheet text.

It never reads ground truth and never trusts the AI's extracted values.
It turns one component's text into: geometry, dimensions, layers, and a
physically plausible mass RANGE. Anything it cannot read confidently is
recorded in `uncertain` so downstream checks return INCONCLUSIVE instead
of guessing.

HONEST LIMITATION: these regexes were written against the phrasing variety
our synthetic generator produces (plus common real-world variants). Real
supplier sheets will contain phrasings this parser does not know; those
should surface as INCONCLUSIVE, not as silent errors - but that has only
been tested on synthetic data.
"""
import re
from dataclasses import dataclass, field

from . import materials, units, categories
from .physics import (Layer, area_m2, area_range_m2, layer_areal_mass,
                      layer_areal_range, family_mass_fractions)

NUM = r"(\d+(?:\.\d+)?)"

# ------------------------------------------------------------- normalisation
def normalize_text(t):
    t = t.replace("×", "x").replace("″", '"').replace("”", '"').replace("–", "-")
    t = re.sub(NUM + r"\s*(?:g/m²|g/m2|gsm)\b", r"\1 GSM", t, flags=re.I)
    t = re.sub(NUM + r"\s*(?:lb|#)\s*(?:/|basis wt)?\s*\(?\s*3000\s*(?:ft²|ft2|sq ft)\s*(?:ream)?\)?",
               r"\1 LB3000 ", t, flags=re.I)
    t = re.sub(NUM + r"\s*(?:cm²|cm2|sq cm)", r"\1 CM2", t, flags=re.I)
    t = re.sub(NUM + r"\s*(?:in²|in2|sq in)", r"\1 IN2", t, flags=re.I)
    t = re.sub(NUM + r"\s*(?:mm²|mm2)", r"\1 MM2", t, flags=re.I)
    return t


THICK_RE = re.compile(NUM + r'\s*(µm|um|microns?|mic|µ|mils?|gauge|ga|nm|mm|in\b|")', re.I)
GRAM_RE = re.compile(NUM + r"\s*(GSM|LB3000)\b")
THICK_UNIT = {"µm": "um", "um": "um", "micron": "um", "microns": "um", "mic": "um", "µ": "um",
              "mil": "mil", "mils": "mil", "gauge": "ga", "ga": "ga", "nm": "nm", "mm": "mm",
              "in": "in", '"': "in"}
LEN_UNIT = {"mm": "mm", "cm": "cm", "in": "in", '"': "in"}
DIM_RE = re.compile(NUM + r'\s*(mm|cm|in\b|")?\s*(?:W)?\s*x\s*' + NUM + r'\s*(mm|cm|in\b|")', re.I)
GUSSET_RE = re.compile(r"gussets?(?:\s*depth)?\s*:?\s*" + NUM + r'\s*(mm|cm|in\b|")', re.I)
AREA_RE = re.compile(NUM + r"\s*(CM2|IN2|MM2)")
AREA_TO_CM2 = {"CM2": 1.0, "IN2": 6.4516, "MM2": 0.01}   # 1 in^2 = 6.4516 cm^2 exactly
WEIGHT_RE = re.compile(r"(?:part weight|weighs|unit wt\.?:?|weight)\s*:?\s*" + NUM +
                       r"\s*(grams|g|oz|lb|kg)\b(?!\s*/)", re.I)
WALL_RE = re.compile(r"wall(?:\s*thickness)?\s*" + NUM + r'\s*(µm|um|microns?|mic|µ|mils?|mm|in\b|")', re.I)
LEAD_RE = re.compile(r"(?:Structure \(out→in\)|Laminate|Construction|Spec|Layers|Build \(outside first\))\s*:\s*", re.I)
MET_RE = re.compile(r"\bmet\b|met-|metalli[sz]ed|\bvm", re.I)
COAT_RE = re.compile(r"coat|lacquer|varnish|extrusion", re.I)
NM_RE = re.compile(r"\(~?\s*" + NUM + r"\s*nm[^)]*\)", re.I)


def find_materials(text):
    """All canonical materials mentioned in text (unordered set)."""
    s = text.lower()
    found = set()
    for canon, pat in materials.SYNONYMS:
        if re.search(pat, s):
            found.add(canon)
    # 'PE' is implied by LDPE/LLDPE/HDPE, not separately present
    return found


@dataclass
class Parsed:
    text: str
    geometry: str = None
    fmt: str = None
    dims_mm: dict = None
    surface_cm2: float = None
    stated_weight_g: float = None
    layers: list = field(default_factory=list)
    uncertain: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    mass_nominal_g: float = None
    mass_range_g: tuple = None
    fractions: dict = None
    has_foil: bool = False
    has_metallization: bool = False
    materials_mentioned: set = field(default_factory=set)
    derived_category: str = None
    category_ambiguous: bool = False

    @property
    def mass_ok(self):
        return self.mass_range_g is not None and not self.uncertain

    def significant_families(self):
        if self.fractions is None:
            return None
        return categories.significant_families(self.fractions)

    def summary(self):
        return dict(geometry=self.geometry, dims_mm=self.dims_mm, surface_cm2=self.surface_cm2,
                    stated_weight_g=self.stated_weight_g,
                    layers=[l.to_dict() for l in self.layers],
                    mass_nominal_g=self.mass_nominal_g, mass_range_g=self.mass_range_g,
                    fractions=self.fractions, derived_category=self.derived_category,
                    has_foil=self.has_foil, has_metallization=self.has_metallization,
                    uncertain=self.uncertain, notes=self.notes)


# ------------------------------------------------------------- token parsing
def parse_token(tok, segment_text, p):
    """Parse one layer token like '48 ga met-PET (OD 2.4)'. Returns list of Layers."""
    nm = None
    m = NM_RE.search(tok)
    if m:
        nm = float(m.group(1))
    clean = re.sub(r"\([^)]*\)", " ", tok)            # drop parentheticals (OD, nm notes)
    is_met = bool(MET_RE.search(clean))
    words = re.sub(r"\d+(?:\.\d+)?", " ", clean)
    mat = materials.normalize(re.sub(r"\b(GSM|LB3000)\b", " ", words))
    if mat is None:
        cands = find_materials(segment_text) - {"COATING", "ADHESIVE"}
        if len(cands) == 1:
            mat = cands.pop()
            p.notes.append(f"material for '{tok.strip()}' inferred from context as {mat}")
        else:
            p.uncertain.append(f"no recognisable material in layer '{tok.strip()}'")
            return []
    g = GRAM_RE.search(clean)
    t = THICK_RE.search(clean)
    out = []
    if g:
        val = units.grammage_gsm(float(g.group(1)), {"GSM": "gsm", "LB3000": "lb3000"}[g.group(2)])
        if mat == "PAPER":
            kind = "paper"
        elif COAT_RE.search(clean):
            kind = "coating"
        elif "adhesive" in clean.lower():
            kind, mat = "adhesive", "ADHESIVE"
        else:
            kind = "coating"
        out.append(Layer(mat, kind, grammage_gsm=val))
    elif t:
        val = units.thickness_um(float(t.group(1)), THICK_UNIT[t.group(2).lower()])
        if mat == "ALUMINUM":
            # physics rule: vacuum-deposited Al is ~0.01-0.1 um; foil is >= ~5 um.
            kind = "foil" if val >= 1.0 else "metallization"
        elif mat in ("PAPER", "COATING", "ADHESIVE"):
            p.uncertain.append(f"{mat} given as a thickness ('{tok.strip()}'); need grammage")
            return []
        else:
            kind = "film"
        out.append(Layer(mat, kind, thickness_um=val))
    else:
        if re.search(r"\d", clean):
            p.uncertain.append(f"number without a recognised unit in '{tok.strip()}'")
        else:
            p.uncertain.append(f"no thickness/grammage in '{tok.strip()}'")
        return []
    if is_met and mat != "ALUMINUM":
        out.append(Layer("ALUMINUM", "metallization",
                         thickness_um=(nm / 1000) if nm else 0.04))  # nominal 40 nm if not stated
        if not nm:
            p.notes.append("metallization thickness not stated; nominal 40 nm, range 10-100 nm")
    return out


def split_tokens(segment):
    toks = re.split(r"\s*/+\s*|\s+\+\s+|,\s+", segment)
    return [t for t in toks if t.strip()]


def first_sentence(s):
    """Text up to the first ';' or a '. ' (period followed by space) - decimals are safe."""
    m = re.search(r";|\.\s|\.$", s)
    return s[: m.start()] if m else s


def parse_adhesive(text, n_interfaces, p):
    low = text.lower()
    if "adhesive" not in low:
        return []
    m = re.search(r"(\d+)\s*x\s*" + NUM + r"\s*GSM\s*(?:PU\s*)?adhesive", text, re.I)
    if m:
        n, g = int(m.group(1)), float(m.group(2))
    else:
        m = re.search(NUM + r"\s*GSM adhesive at each of the (\d+) interfaces", text, re.I)
        if m:
            g, n = float(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"adhesive\s*" + NUM + r"\s*GSM\s*per interface", text, re.I)
            if m:
                g, n = float(m.group(1)), n_interfaces
                p.notes.append(f"adhesive interfaces inferred from layer count: {n}")
            else:
                p.uncertain.append("adhesive mentioned but coat weight not parseable")
                return []
    return [Layer("ADHESIVE", "adhesive", grammage_gsm=g) for _ in range(n)]


# ------------------------------------------------------------- main entry
def parse_component(raw_text, tol):
    text = normalize_text(raw_text)
    p = Parsed(text=raw_text)
    p.materials_mentioned = find_materials(text)
    low = text.lower()

    wm = WEIGHT_RE.search(text)
    am = AREA_RE.search(text)
    if wm:
        p.geometry, p.fmt = "stated", "rigid"
        p.stated_weight_g = units.mass_g(float(wm.group(1)),
                                         {"grams": "g"}.get(wm.group(2).lower(), wm.group(2).lower()))
        desc = text[: wm.start()]
        desc = re.sub(r"\d+\s*(oz|ml|fl oz)\s*(capacity|brimful)", " ", desc, flags=re.I)
        mat = materials.normalize(desc)
        if mat is None:
            p.uncertain.append("could not identify material of weighed part")
        else:
            p.layers = [Layer(mat, "wall")]
        if "capacity" in low or "brimful" in low or "ml" in low:
            p.notes.append("capacity (volume) ignored; only the stated part weight is used")
    elif am:
        p.geometry, p.fmt = "surface", "rigid"
        p.surface_cm2 = float(am.group(1)) * AREA_TO_CM2[am.group(2)]
        head = first_sentence(text)
        if "/" in head:
            for tok in split_tokens(head):
                if re.search(r"\d", tok):
                    p.layers += parse_token(tok, head, p)
        else:
            w = WALL_RE.search(text)
            mat = materials.normalize(re.sub(r"surface.*", "", text, flags=re.I)) or materials.normalize(text)
            if not w:
                p.uncertain.append("no wall thickness found")
            elif mat is None:
                p.uncertain.append("no material found for rigid part")
            else:
                p.layers = [Layer(mat, "wall",
                                  thickness_um=units.thickness_um(float(w.group(1)), THICK_UNIT[w.group(2).lower()]))]
    else:
        p.fmt = "flexible"
        if re.search(r"stand[- ]?up|doypack|\bsup\b", low):
            p.geometry = "standup_pouch"
        elif re.search(r"side[- ]gusset", low):
            p.geometry = "side_gusset_bag"
        elif re.search(r"pouch|sachet|pillow|liner bag|bag", low):
            p.geometry = "flat_pouch"
        else:
            p.geometry = "sheet"
        dm = DIM_RE.search(text)
        if not dm:
            p.uncertain.append("no W x H dimensions found")
        else:
            u2 = LEN_UNIT[dm.group(4).lower()]
            u1 = LEN_UNIT[dm.group(2).lower()] if dm.group(2) else u2
            w = units.length_mm(float(dm.group(1)), u1)
            h = units.length_mm(float(dm.group(3)), u2)
            g = 0.0
            if p.geometry in ("standup_pouch", "side_gusset_bag"):
                gm = GUSSET_RE.search(text)
                if gm:
                    g = units.length_mm(float(gm.group(1)), LEN_UNIT[gm.group(2).lower()])
                else:
                    p.uncertain.append("gusseted pack but gusset depth not found")
            p.dims_mm = dict(w=w, h=h, g=g)
        lead = LEAD_RE.search(text)
        seg = first_sentence(text[lead.end():]) if lead else first_sentence(text)
        for tok in split_tokens(seg):
            if re.search(r"\d", re.sub(r"\([^)]*\)", "", tok)) or materials.normalize(tok) and lead:
                p.layers += parse_token(tok, seg, p)
        # extra coating sentence after the first segment (e.g. ', one side LDPE extrusion coat 18 GSM')
        webs = [l for l in p.layers if l.kind in ("film", "foil", "paper")]
        coats = [l for l in p.layers if l.kind == "coating"]
        p.layers += parse_adhesive(text, max(len(webs) - 1 - len(coats), 0), p)
        if not p.layers and not p.uncertain:
            p.uncertain.append("no layers found")

    p.has_foil = any(l.kind == "foil" for l in p.layers)
    p.has_metallization = any(l.kind == "metallization" for l in p.layers)
    _compute(p, tol)
    return p


def _compute(p, tol):
    if not p.layers:
        return
    if p.geometry == "stated":
        if p.stated_weight_g is None:
            return
        w = p.stated_weight_g
        r = tol["stated_weight_rel"]
        p.fractions = {materials.family(p.layers[0].material): 1.0}
        p.derived_category = categories.assign("rigid", p.fractions)
        if not p.uncertain:
            p.mass_nominal_g, p.mass_range_g = w, (w * (1 - r), w * (1 + r))
        return
    if p.uncertain:
        # we may still know families qualitatively, but not their mass fractions
        return
    if p.geometry == "surface":
        a = p.surface_cm2 / 1e4
        a_lo = a * (1 - tol["dimension_rel"]) ** 2
        a_hi = a * (1 + tol["dimension_rel"]) ** 2
    else:
        d = p.dims_mm
        a = area_m2(p.geometry, d["w"], d["h"], d["g"])
        a_lo, a_hi = area_range_m2(p.geometry, d["w"], d["h"], d["g"], tol["dimension_rel"])
    p.mass_nominal_g = a * sum(layer_areal_mass(l) for l in p.layers)
    lo = sum(layer_areal_range(l, tol)[0] for l in p.layers)
    hi = sum(layer_areal_range(l, tol)[1] for l in p.layers)
    p.mass_range_g = (a_lo * lo, a_hi * hi)
    p.fractions = family_mass_fractions(a, p.layers)
    p.derived_category = categories.assign(p.fmt, p.fractions)
    p.category_ambiguous = categories.near_threshold(p.fractions, band=0.015)


# ------------------------------------------------------------- catalog split
SKU_RE = re.compile(r"^(?:SKU[:#]?|Item code)\s*([A-Z]{3}-\d{4})", re.M)
COMP_RE = re.compile(r"^\s*(?:\[(C\d+)\]|Component (C\d+):|(C\d+) –|(C\d+)\))\s*(.*)$", re.M)


def split_catalog(spec_text):
    """Return {sku: {component_id: raw_text}} parsed from the catalog text."""
    out = {}
    heads = list(SKU_RE.finditer(spec_text))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(spec_text)
        block = spec_text[h.start():end]
        comps = {}
        for m in COMP_RE.finditer(block):
            cid = next(g for g in m.groups()[:4] if g)
            comps[cid] = m.group(5).strip()
        out[h.group(1)] = comps
    return out
