"""SYNTHETIC catalog generator (ground truth).

Every SKU, product name and spec sheet produced here is SYNTHETIC. Nothing
here describes a real product.

For each component we first pick a *structured* truth (layers, dimensions,
units), compute its mass with nominal densities (epr/physics.py), assign the
PLACEHOLDER category (epr/categories.py), and only then render messy text from
the same values. Text numbers are chosen in their display unit first, then
converted, so the text and the truth always agree exactly.

Output per catalog:
  data/catalogs/<id>/spec.txt           <- the only thing the AI sees
  data/catalogs/<id>/ground_truth.json  <- never shown to the AI or the checker
"""
import argparse
import json
import random
from pathlib import Path

from . import categories, units
from .physics import Layer, area_m2, layered_mass_g, family_mass_fractions

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ numbers
def num(v):
    """Format a number without trailing zeros."""
    s = f"{v:.5f}".rstrip("0").rstrip(".")
    return s


# Thickness options as (value, unit) in the DISPLAY unit.
PET_T = [(12, "um"), (48, "ga"), (12, "um"), (23, "um"), (92, "ga")]
BOPP_T = [(18, "um"), (20, "um"), (70, "ga"), (0.7, "mil"), (25, "um")]
PE_T = [(25, "um"), (30, "um"), (1.0, "mil"), (40, "um")]
SEAL_T = [(50, "um"), (60, "um"), (75, "um"), (2.0, "mil"), (3.0, "mil"), (2.5, "mil"), (90, "um"), (100, "um")]
FOIL_T = [(7, "um"), (9, "um"), (6.35, "um"), (0.00035, "in"), (0.35, "mil"), (8, "um")]
PA_T = [(15, "um"), (20, "um"), (60, "ga")]
WRAP_T = [(12, "um"), (0.6, "mil"), (1.2, "mil"), (20, "um"), (0.8, "mil"), (15, "um")]
PAPER_G = [(50, "gsm"), (60, "gsm"), (70, "gsm"), (40, "lb3000"), (80, "gsm")]
KRAFT_G = [(70, "gsm"), (90, "gsm"), (50, "lb3000"), (60, "lb3000"), (100, "gsm")]
BOARD_G = [(250, "gsm"), (300, "gsm"), (350, "gsm"), (400, "gsm"), (230, "gsm")]
LABEL_G = [(60, "gsm"), (70, "gsm"), (80, "gsm"), (50, "lb3000"), (60, "lb3000")]
PE_COAT_G = [(12, "gsm"), (15, "gsm"), (18, "gsm"), (20, "gsm"), (25, "gsm")]


def to_um(v, u):
    return units.thickness_um(v, u)


def to_gsm(v, u):
    return units.grammage_gsm(v, u)


# ------------------------------------------------------------------ rendering
def r_thick(v, u, rng):
    pats = {
        "um": ["{} µm", "{}µm", "{} micron", "{}um", "{} µ", "{} mic"],
        "mil": ["{} mil", "{} mils", "{}mil"],
        "ga": ["{} ga", "{} gauge", "{}ga"],
        "in": ['{}"', "{} in"],
        "mm": ["{} mm", "{}mm"],
    }[u]
    return rng.choice(pats).format(num(v))


def r_gram(v, u, rng):
    pats = {
        "gsm": ["{} gsm", "{} g/m²", "{}g/m2", "{} gsm", "{} g/m2"],
        "lb3000": ["{} lb/3000 ft²", "{}# (3000 ft² ream)", "{} lb basis wt (3000 sq ft)"],
    }[u]
    return rng.choice(pats).format(num(v))


MM_PER = {"mm": 1.0, "cm": 10.0, "in": 25.4}
STEPS = {"mm": 1.0, "cm": 0.5, "in": 0.25}   # display resolution per unit


def pick_in_unit(rng, u, lo_mm, hi_mm):
    """Pick a 'nice' value in display unit u. Returns (display_value, mm)."""
    step = STEPS[u]
    v = round(rng.uniform(lo_mm, hi_mm) / MM_PER[u] / step) * step
    v = round(v, 2)
    return v, units.length_mm(v, u) if u != "cm" else v * 10


def r_len_unit(u, rng):
    return {"mm": "mm", "cm": "cm", "in": rng.choice(["in", '"'])}[u]


def r_dims(wv, hv, u, rng):
    """Render W x H in one unit. Dimension pairs are ALWAYS width x height."""
    U = r_len_unit(u, rng)
    if U == '"':
        return rng.choice([f'{num(wv)}" x {num(hv)}"', f'{num(wv)}" W x {num(hv)}" H'])
    return rng.choice([
        f"{num(wv)} x {num(hv)} {U}",
        f"{num(wv)}{U} × {num(hv)}{U}",
        f"{num(wv)} {U} W x {num(hv)} {U} H",
        f"(W x H) {num(wv)} x {num(hv)} {U}",
    ])


def r_len(v, u, rng):
    U = r_len_unit(u, rng)
    return f'{num(v)}"' if U == '"' else f"{num(v)} {U}"


# ------------------------------------------------------------------ laminates
# Each recipe: list of (material, kind, options, text_names, metallized?)
LAMINATES = {
    "PET/foil/PE": [("PET", "film", PET_T, ["PET", "BOPET", "polyester"], False),
                    ("ALUMINUM", "foil", FOIL_T, ["Al foil", "aluminium foil", "AL foil", "aluminum foil"], False),
                    ("LLDPE", "film", SEAL_T, ["LLDPE", "LLDPE sealant", "mLLDPE"], False)],
    "PET/metPET/PE": [("PET", "film", PET_T, ["PET", "BOPET"], False),
                      ("PET", "film", PET_T, ["met-PET", "metallized PET", "VMPET", "metallised PET"], True),
                      ("LDPE", "film", SEAL_T, ["LDPE", "PE", "polyethylene"], False)],
    "BOPP/metBOPP": [("PP", "film", BOPP_T, ["BOPP", "OPP"], False),
                     ("PP", "film", BOPP_T, ["metallized BOPP", "met-OPP", "VM BOPP"], True)],
    "PE/metPE": [("LLDPE", "film", PE_T, ["MDO-PE", "LLDPE"], False),
                 ("LLDPE", "film", SEAL_T, ["metallized LLDPE", "met-PE", "metallised PE"], True)],
    "paper/PE/foil/PE": [("PAPER", "paper", PAPER_G, ["bleached kraft paper", "paper", "MG kraft"], False),
                         ("LDPE", "coating", PE_COAT_G, ["LDPE extrusion coat", "PE extrusion layer"], False),
                         ("ALUMINUM", "foil", FOIL_T, ["Al foil", "aluminium foil"], False),
                         ("LLDPE", "film", SEAL_T, ["LLDPE", "LLDPE sealant"], False)],
    "PET/PE": [("PET", "film", PET_T, ["PET", "OPET"], False),
               ("PE", "film", SEAL_T, ["PE", "polyethylene"], False)],
    "PA/PE": [("PA6", "film", PA_T, ["BOPA", "nylon", "PA6"], False),
              ("LLDPE", "film", SEAL_T, ["LLDPE"], False)],
    "monoPE": [("LLDPE", "film", SEAL_T, ["LLDPE", "PE", "mono-PE"], False)],
    "kraft/PE": [("PAPER", "paper", KRAFT_G, ["natural kraft", "kraft paper"], False),
                 ("LDPE", "coating", PE_COAT_G, ["LDPE coating", "PE extrusion coat"], False)],
}


def build_layers(recipe, rng):
    """Return (layers, chain_text, tags, interfaces)."""
    layers, tokens, tags = [], [], set()
    for mat, kind, opts, names, met in LAMINATES[recipe]:
        v, u = rng.choice(opts)
        name = rng.choice(names)
        if kind in ("paper", "coating"):
            layers.append(Layer(mat, kind, grammage_gsm=to_gsm(v, u)))
            tokens.append(f"{r_gram(v, u, rng)} {name}")
            tags.add("grammage")
        else:
            layers.append(Layer(mat, kind, thickness_um=to_um(v, u)))
            t = r_thick(v, u, rng)
            tokens.append(rng.choice([f"{t} {name}", f"{name} {t}"]))
        if met:
            nm = rng.choice([30, 35, 40, 45, 50])
            layers.append(Layer("ALUMINUM", "metallization", thickness_um=nm / 1000))
            if rng.random() < 0.3:
                tokens[-1] += f" (~{nm} nm Al)"
            elif rng.random() < 0.5:
                tokens[-1] += f" (OD {rng.choice(['2.2', '2.4', '2.8'])})"
            tags.add("metallized")
        if kind == "foil":
            tags.add("foil")
        if kind == "coating":
            tags.add("coating")
    # adhesive interfaces: between bonded webs, not after an extrusion coat
    webs = [l for l in layers if l.kind in ("film", "foil", "paper")]
    interfaces = len(webs) - 1 - sum(1 for l in layers if l.kind == "coating")
    sep = rng.choice([" / ", " // ", "/"])
    chain = sep.join(tokens)
    if len(webs) > 1:
        tags.add("laminate")
    return layers, chain, tags, max(interfaces, 0)


def add_adhesive(layers, interfaces, rng):
    if interfaces <= 0:
        return ""
    g = rng.choice([1.5, 1.8, 2.0, 2.2, 2.5, 3.0])
    for _ in range(interfaces):
        layers.append(Layer("ADHESIVE", "adhesive", grammage_gsm=g))
    return rng.choice([
        f"; adhesive laminated, {interfaces} x {num(g)} gsm PU adhesive",
        f". Solventless adhesive {num(g)} g/m² per interface",
        f"; bonded with {num(g)} gsm adhesive at each of the {interfaces} interfaces",
    ])


LEADS = ["Structure (out→in):", "Laminate:", "Construction:", "Spec:", "Layers:", "Build (outside first):"]


# ------------------------------------------------------------------ components
def comp_flexible(rng, ctype, recipes, w_rng, h_rng, g_rng=None):
    recipe = rng.choice(recipes)
    layers, chain, tags, n_if = build_layers(recipe, rng)
    adh = add_adhesive(layers, n_if, rng)
    if adh:
        tags.add("adhesive")
    u = rng.choice(["mm", "mm", "in", "cm"])
    wv, w = pick_in_unit(rng, u, *w_rng)
    hv, h = pick_in_unit(rng, u, *h_rng)
    g = 0.0
    geom = {"standup pouch": "standup_pouch", "flat pouch": "flat_pouch", "sachet": "flat_pouch",
            "side-gusset bag": "side_gusset_bag", "liner bag": "flat_pouch"}[ctype]
    dims_txt = r_dims(wv, hv, u, rng)
    gus_txt = ""
    if geom in ("standup_pouch", "side_gusset_bag"):
        gv, g = pick_in_unit(rng, u, *g_rng)
        which = "bottom gusset" if geom == "standup_pouch" else "side gussets"
        gus_txt = rng.choice([f", {which} {r_len(gv, u, rng)} (fully opened)",
                              f"; {which} depth {r_len(gv, u, rng)} unfolded",
                              f", {which}: {r_len(gv, u, rng)} opened out"])
        tags.add("gusset")
    tags.add("two-faced")
    names = {"standup pouch": ["Stand-up pouch (doypack)", "SUP with bottom gusset", "Stand up pouch"],
             "flat pouch": ["3-side-seal flat pouch", "Flat pouch", "Pillow pack (flat, 2 faces)"],
             "sachet": ["Sachet, 4-side seal", "Single-serve sachet"],
             "side-gusset bag": ["Side-gusset bag", "Quad-seal side gusset bag"],
             "liner bag": ["Inner liner bag (flat)", "Bag-in-box liner, flat"]}[ctype]
    body = (f"{rng.choice(names)}. Face size {dims_txt}{gus_txt}. {rng.choice(LEADS)} {chain}{adh}."
            if rng.random() < 0.5 else
            f"{rng.choice(names)} — {rng.choice(LEADS)} {chain}{adh}. Dimensions per face {dims_txt}{gus_txt}.")
    return dict(ctype=ctype, fmt="flexible", geometry=geom, dims_mm=dict(w=w, h=h, g=g),
                layers=layers, text=body, tags=sorted(tags), recipe=recipe)


def comp_sheet(rng, ctype):
    """Single flat pieces: overwrap, lidding, labels, carton blanks."""
    tags = {"sheet"}
    if ctype == "film wrap":
        v, u = rng.choice(WRAP_T)
        mat, name = rng.choice([("LDPE", "LDPE"), ("LLDPE", "LLDPE stretch film"), ("PP", "BOPP"), ("PVC", "PVC cling film")])
        layers = [Layer(mat, "film", thickness_um=to_um(v, u))]
        fmt = "flexible"
        wr, hr = (250, 500), (250, 600)
        desc = rng.choice([f"Overwrap film, {name} {r_thick(v, u, rng)}", f"{name} wrap, gauge {r_thick(v, u, rng)}"])
    elif ctype == "lidding":
        fmt = "flexible"
        wr, hr = (60, 130), (60, 130)
        if rng.random() < 0.5:
            v, u = rng.choice([(38, "um"), (40, "um"), (1.5, "mil"), (30, "um")])
            lac = rng.choice([2.0, 2.5, 3.0, 8.0, 10.0])
            layers = [Layer("ALUMINUM", "foil", thickness_um=to_um(v, u)),
                      Layer("COATING", "coating", grammage_gsm=lac)]
            desc = f"Die-cut lid, {r_thick(v, u, rng)} aluminium foil + {num(lac)} gsm heat-seal lacquer"
            tags |= {"foil", "coating"}
        else:
            layers, chain, t2, n_if = build_layers("PET/PE", rng)
            desc = f"Peelable lidding film, {chain}{add_adhesive(layers, n_if, rng)}"
            tags |= t2 | {"adhesive"}
    elif ctype == "label":
        wr, hr = (50, 260), (30, 120)
        if rng.random() < 0.6:
            v, u = rng.choice(LABEL_G)
            layers = [Layer("PAPER", "paper", grammage_gsm=to_gsm(v, u))]
            fmt = "paper"
            desc = rng.choice([f"Wrap-around paper label, {r_gram(v, u, rng)} uncoated",
                               f"Front label, coated paper {r_gram(v, u, rng)}"])
            tags.add("grammage")
        else:
            v, u = rng.choice([(50, "um"), (2.0, "mil"), (60, "um"), (40, "um")])
            layers = [Layer("PP", "film", thickness_um=to_um(v, u))]
            fmt = "flexible"
            desc = rng.choice([f"BOPP film label {r_thick(v, u, rng)}", f"Clear OPP wrap label, {r_thick(v, u, rng)}"])
    else:  # carton
        fmt = "paper"
        wr, hr = (200, 600), (150, 500)
        v, u = rng.choice(BOARD_G)
        layers = [Layer("PAPER", "paper", grammage_gsm=to_gsm(v, u))]
        board = rng.choice(["SBS board", "CUK board", "folding boxboard (FBB)", "recycled CCNB board"])
        desc = f"Folding carton, {r_gram(v, u, rng)} {board}"
        tags.add("grammage")
        x = rng.random()
        if x < 0.3:
            c, cu = rng.choice(PE_COAT_G)
            layers.append(Layer("LDPE", "coating", grammage_gsm=to_gsm(c, cu)))
            desc += f", one side LDPE extrusion coat {r_gram(c, cu, rng)}"
            tags.add("coating")
        elif x < 0.6:
            vv = rng.choice([2.0, 3.0, 4.0])
            layers.append(Layer("COATING", "coating", grammage_gsm=vv))
            desc += f", aqueous varnish {num(vv)} gsm"
            tags.add("coating")
    u = rng.choice(["mm", "mm", "in", "cm"])
    wv, w = pick_in_unit(rng, u, *wr)
    hv, h = pick_in_unit(rng, u, *hr)
    dims = r_dims(wv, hv, u, rng)
    lead = {"film wrap": "cut sheet", "lidding": "lid blank", "label": "label size", "carton": "flat blank"}[ctype]
    body = f"{desc}; {lead} {dims}."
    return dict(ctype=ctype, fmt=fmt, geometry="sheet", dims_mm=dict(w=w, h=h, g=0.0),
                layers=layers, text=body, tags=sorted(tags))


def r_area(cm2, rng):
    """Render a surface area in cm2, in2 or mm2 (value chosen in display unit)."""
    u = rng.choice(["cm2", "cm2", "in2", "mm2"])
    if u == "cm2":
        v = round(cm2)
        return v, rng.choice([f"{v} cm²", f"{v} cm2", f"{v} sq cm"])
    if u == "in2":
        v = round(cm2 / 6.4516, 1)
        return v * 6.4516, rng.choice([f"{num(v)} in²", f"{num(v)} sq in", f"{num(v)} in2"])
    v = round(cm2 * 100, -1)
    return v / 100, f"{num(v)} mm²"


def comp_rigid(rng, ctype):
    tags = {"rigid"}
    spec = {
        "bottle": [("PET", "PET", (250, 600), [(0.30, "mm"), (12, "mil"), (300, "um"), (0.25, "mm")], ["PET bottle", "rPET bottle, blow-moulded"]),
                   ("HDPE", "HDPE", (300, 800), [(0.8, "mm"), (30, "mil"), (700, "um")], ["HDPE bottle", "EBM HDPE bottle"])],
        "tray": [("PET", "APET", (250, 700), [(20, "mil"), (0.4, "mm"), (15, "mil")], ["APET thermoformed tray", "PET punnet"]),
                 ("PS", "HIPS", (200, 600), [(0.6, "mm"), (25, "mil")], ["HIPS tray"]),
                 ("PVC", "PVC", (80, 250), [(250, "um"), (10, "mil")], ["PVC blister cavity tray"]),
                 ("PP", "PP", (250, 600), [(0.5, "mm"), (20, "mil")], ["PP thermoformed tub"])],
        "can": [("STEEL", "tinplate", (300, 600), [(0.20, "mm"), (0.18, "mm"), (0.22, "mm")], ["Tinplate food can (body + 2 ends)", "3-piece steel can"]),
                ("ALUMINUM", "aluminium", (250, 350), [(0.10, "mm"), (100, "um")], ["Aluminium beverage can (body + end)"])],
    }[ctype]
    mat, mname, srange, topts, names = rng.choice(spec)
    cm2_true, area_txt = r_area(rng.uniform(*srange), rng)
    v, u = rng.choice(topts)
    layers = [Layer(mat if mat != "HDPE" else "HDPE", "wall", thickness_um=to_um(v, u))]
    desc = f"{rng.choice(names)}"
    # Co-extruded HDPE/EVOH/HDPE barrier bottle (EVOH share chosen away from 5 % threshold)
    if mat == "HDPE" and rng.random() < 0.4:
        total = to_um(v, u)
        evoh_share = rng.choice([0.02, 0.03, 0.08, 0.10])
        e = round(total * evoh_share)
        o = round((total - e) / 2)
        layers = [Layer("HDPE", "wall", thickness_um=o), Layer("EVOH", "wall", thickness_um=e),
                  Layer("HDPE", "wall", thickness_um=o)]
        desc = f"Co-ex barrier bottle, HDPE {o} µm / EVOH {e} µm / HDPE {o} µm"
        tags.add("multilayer-rigid")
        body = f"{desc}; surface area {area_txt}."
    else:
        body = rng.choice([f"{desc}; surface area {area_txt}, average wall {r_thick(v, u, rng)} {mname}.",
                           f"{desc}, {mname}, avg wall thickness {r_thick(v, u, rng)}, total surface {area_txt}."])
    return dict(ctype=ctype, fmt="rigid", geometry="surface", surface_cm2=cm2_true,
                layers=layers, text=body, tags=sorted(tags))


def r_weight(g, rng, allow_oz=True):
    """Render a stated part weight; returns (true_g, text)."""
    u = rng.choice(["g", "g", "oz"] if allow_oz else ["g"])
    if g > 150 and rng.random() < 0.3:
        u = rng.choice(["oz", "lb", "kg"])
    if u == "g":
        v = round(g, 1)
        return v, rng.choice([f"{num(v)} g", f"{num(v)}g", f"{num(v)} grams"])
    if u == "oz":
        v = round(g / 28.349523125, 2)
        return units.mass_g(v, "oz"), f"{num(v)} oz"
    if u == "lb":
        v = round(g / 453.59237, 3)
        return units.mass_g(v, "lb"), f"{num(v)} lb"
    v = round(g / 1000, 3)
    return v * 1000, f"{num(v)} kg"


def comp_weighed(rng, ctype):
    """Parts specified by stated weight (closures, glass, injection-moulded tubs)."""
    tags = {"stated-weight"}
    opts = {
        "cap": [("PP", "PP screw cap 28 mm", (1.8, 3.5)), ("HDPE", "HDPE flip-top closure", (2.5, 6.0)),
                ("ALUMINUM", "Aluminium ROPP closure", (1.2, 2.5)), ("STEEL", "Steel lug cap 63 mm", (7.0, 12.0)),
                ("PP", "PP dispensing pump (all-PP)", (8.0, 14.0))],
        "glass jar": [("GLASS", "Flint glass jar", (150, 380)), ("GLASS", "Amber glass bottle", (180, 450))],
        "tub": [("PP", "Injection-moulded PP tub", (12, 30)), ("PS", "PS yoghurt cup", (4, 9))],
        "valve": [("PE", "One-way degassing valve (PE)", (0.8, 1.6))],
    }[ctype]
    mat, name, wr = rng.choice(opts)
    g, wtxt = r_weight(rng.uniform(*wr), rng)
    cap = ""
    if ctype == "glass jar":
        cap = rng.choice([f", {rng.choice([8, 12, 16, 24])} oz capacity", f", {rng.choice([250, 375, 500])} mL brimful"])
        tags.add("capacity-trap")
    body = rng.choice([f"{name}{cap}; part weight {wtxt}.", f"{name}{cap}, weighs {wtxt}.",
                       f"{name}{cap}. Unit wt: {wtxt}."])
    kind = "wall"
    return dict(ctype=ctype, fmt="rigid", geometry="stated", stated_weight_g=g,
                layers=[Layer(mat, kind)], text=body, tags=sorted(tags))


# ------------------------------------------------------------------ products
FLEX_RECIPES = list(LAMINATES)
PRODUCTS = {
    "snack": (["Trail Mix", "Kettle Chips", "Granola Bites", "Veggie Crisps", "Pretzel Thins"],
              lambda r: [comp_flexible(r, "standup pouch", FLEX_RECIPES, (100, 220), (150, 320), (50, 110))]),
    "candy": (["Gummy Bears", "Dark Chocolate Squares", "Mint Drops"],
              lambda r: [comp_flexible(r, "flat pouch", ["BOPP/metBOPP", "PET/metPET/PE", "PE/metPE", "PET/PE"], (80, 200), (100, 260)),
                         comp_sheet(r, "carton")] if r.random() < 0.5 else
                        [comp_flexible(r, "flat pouch", ["BOPP/metBOPP", "PET/metPET/PE", "PE/metPE"], (80, 200), (100, 260))]),
    "beverage": (["Sparkling Water", "Cold Brew", "Electrolyte Drink", "Iced Tea"],
                 lambda r: [comp_rigid(r, "bottle"), comp_weighed(r, "cap"), comp_sheet(r, "label")]),
    "coffee": (["Whole Bean Coffee", "Ground Espresso"],
               lambda r: [comp_flexible(r, "side-gusset bag", ["PET/foil/PE", "paper/PE/foil/PE", "PET/metPET/PE", "kraft/PE"], (90, 140), (200, 330), (50, 90)),
                          comp_weighed(r, "valve")]),
    "sauce": (["Marinara", "Salsa Verde", "Peanut Butter", "Honey"],
              lambda r: [comp_weighed(r, "glass jar"), comp_weighed(r, "cap"), comp_sheet(r, "label")]),
    "canned": (["Black Beans", "Diced Tomatoes", "Coconut Milk", "Tuna"],
               lambda r: [comp_rigid(r, "can"), comp_sheet(r, "label")]),
    "dairy": (["Greek Yogurt", "Cottage Cheese", "Hummus"],
              lambda r: [comp_weighed(r, "tub"), comp_sheet(r, "lidding")] + ([comp_weighed(r, "cap")] if r.random() < 0.4 else [])),
    "produce": (["Cherry Tomatoes", "Blueberries", "Mixed Salad"],
                lambda r: [comp_rigid(r, "tray"), comp_sheet(r, "film wrap")] + ([comp_sheet(r, "label")] if r.random() < 0.5 else [])),
    "personal": (["Shampoo", "Body Lotion", "Hand Soap"],
                 lambda r: [comp_rigid(r, "bottle"), comp_weighed(r, "cap"), comp_sheet(r, "carton"), comp_sheet(r, "label")][: r.choice([2, 3, 4])]),
    "cereal": (["Oat Flakes", "Corn Puffs", "Muesli"],
               lambda r: [comp_sheet(r, "carton"), comp_flexible(r, "liner bag", ["monoPE", "PE/metPE"], (180, 300), (250, 400))]),
    "single-serve": (["Drink Mix Stick", "Protein Powder Sachet", "Ketchup Packet"],
                     lambda r: [comp_flexible(r, "sachet", ["PET/foil/PE", "paper/PE/foil/PE", "PET/metPET/PE", "PET/PE"], (40, 90), (60, 140))]),
}

BRANDS = ["Northfield", "Bluepeak", "Harvest & Co", "Kestrel", "Meridian", "Oakline", "Sunward", "Tidewater"]


def finalize(comp):
    """Compute ground-truth mass, fractions and placeholder category."""
    layers = comp["layers"]
    if comp["geometry"] == "stated":
        mass = comp["stated_weight_g"]
        fr = {categories_family(layers[0].material): 1.0}
    else:
        if comp["geometry"] == "surface":
            area = comp["surface_cm2"] / 1e4
        else:
            d = comp["dims_mm"]
            area = area_m2(comp["geometry"], d["w"], d["h"], d["g"])
        mass = layered_mass_g(area, layers)
        fr = family_mass_fractions(area, layers)
        comp["area_m2"] = area
    comp["true_mass_g"] = mass
    comp["family_fractions"] = fr
    comp["true_category"] = categories.assign(comp["fmt"], fr)
    return comp


def categories_family(material):
    from . import materials
    return materials.family(material)


def make_component(rng, builder_result_fn):
    """Resample until no family fraction sits near the 5 % threshold (keeps truth unambiguous)."""
    for _ in range(50):
        comp = finalize(builder_result_fn())
        if not categories.near_threshold(comp["family_fractions"]):
            return comp
    raise RuntimeError("could not sample unambiguous component")


AMBIG_RATE = 0.05


def make_ambiguous(comp, rng):
    """Strip a unit or a dimension from the text to create a genuinely
    under-specified spec. Ground truth still knows the answer; the checker
    should say 'inconclusive'."""
    import re
    t = comp["text"]
    new = re.sub(r"(\d)\s?(µm|micron|mils?|ga|gauge|gsm)\b", r"\1", t, count=1)
    if new == t:
        return comp
    comp["text"] = new + " [thickness unit missing on supplier sheet]"
    comp["ambiguous_spec"] = True
    comp["tags"] = sorted(set(comp["tags"]) | {"ambiguous"})
    return comp


def make_catalog(cat_id, seed, n_skus):
    rng = random.Random(seed)
    skus, texts, used = [], [], set()
    for i in range(n_skus):
        ptype = rng.choice(list(PRODUCTS))
        names, builder = PRODUCTS[ptype]
        while True:
            sku = f"{rng.choice('ABCDEFGHJKLMNPRSTVW')}{rng.choice('ABCDEFGHJKLMNPRSTVW')}{rng.choice('ABCDEFGHJKLMNPRSTVW')}-{rng.randrange(1000, 9999)}"
            if sku not in used:
                used.add(sku)
                break
        pname = f"{rng.choice(BRANDS)} {rng.choice(names)}"
        # build components; resample whole set if any is near-threshold
        comps = None
        for _ in range(50):
            raw = builder(rng)
            raw = [finalize(c) for c in raw]
            if not any(categories.near_threshold(c["family_fractions"]) for c in raw):
                comps = raw
                break
        if comps is None:
            raise RuntimeError("sampling failed")
        net = rng.choice(["Net wt 12 oz (340 g)", "Net 500 mL", "Net wt 1 lb", "NET WT 8 OZ", "250 g", "16 fl oz", "Net wt 2.5 oz (70 g)"])
        header = rng.choice([f"SKU: {sku} | {pname} | {net}", f"SKU# {sku} — {pname} ({net})",
                             f"Item code {sku}: {pname}, {net}"])
        lines = [header, rng.choice(["Packaging components:", "Pack BOM:", "Packaging spec:"])]
        out_comps = []
        for j, c in enumerate(comps, 1):
            cid = f"C{j}"
            c["ambiguous_spec"] = False
            if rng.random() < AMBIG_RATE and c["geometry"] != "stated":
                c = make_ambiguous(c, rng)
            label = rng.choice([f"[{cid}]", f"Component {cid}:", f"{cid} –", f"{cid})"])
            lines.append(f"  {label} {c['text']}")
            out_comps.append(dict(
                component_id=cid, component_type=c["ctype"], format=c["fmt"], geometry=c["geometry"],
                dims_mm=c.get("dims_mm"), surface_cm2=c.get("surface_cm2"), stated_weight_g=c.get("stated_weight_g"),
                area_m2=c.get("area_m2"), layers=[l.to_dict() for l in c["layers"]],
                family_fractions=c["family_fractions"], true_mass_g=round(c["true_mass_g"], 4),
                true_category=c["true_category"], tags=c["tags"], ambiguous_spec=c["ambiguous_spec"],
                spec_text=c["text"]))
        skus.append(dict(sku=sku, product=pname, product_type=ptype, components=out_comps))
        texts.append("\n".join(lines))
    totals = {}
    for s in skus:
        for c in s["components"]:
            totals[c["true_category"]] = totals.get(c["true_category"], 0) + c["true_mass_g"]
    spec = (f"PACKAGING SPECIFICATION CATALOG {cat_id}\n(SYNTHETIC test data — not real products)\n"
            + "\n" + ("\n" + "-" * 60 + "\n").join(texts) + "\n")
    gt = dict(catalog_id=cat_id, seed=seed, synthetic=True, skus=skus,
              totals_by_category={k: round(v, 4) for k, v in sorted(totals.items())},
              total_weight_g=round(sum(totals.values()), 4))
    return spec, gt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "data" / "catalogs"))
    a = ap.parse_args()
    rng = random.Random(a.seed)
    for i in range(1, a.n + 1):
        cid = f"cat_{i:02d}"
        spec, gt = make_catalog(cid, a.seed * 1000 + i, rng.randint(15, 40))
        d = Path(a.out) / cid
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.txt").write_text(spec)
        (d / "ground_truth.json").write_text(json.dumps(gt, indent=2))
        n = sum(len(s["components"]) for s in gt["skus"])
        print(f"{cid}: {len(gt['skus'])} SKUs, {n} components, total {gt['total_weight_g']:.1f} g")


if __name__ == "__main__":
    main()
