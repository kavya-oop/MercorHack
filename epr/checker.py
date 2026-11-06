"""The physics-based checker for AI-produced EPR packaging reports.

Inputs : raw catalog spec text + the AI's JSON report.
NOT inputs: ground truth (never read here).

Each AI line item gets these checks, each with status PASS / FAIL /
INCONCLUSIVE / N/A, the expected vs reported values, and an explanation:
  a completeness   b unit_sanity   c physics_mass   d structure
  e metallized_vs_foil             f category_validity
plus catalog-level   g totals.
"""
import argparse
import json
from pathlib import Path

from . import materials, categories, spec_parser
from .units import UNIT_CONFUSIONS

ROOT = Path(__file__).resolve().parent.parent
TOL = json.load(open(ROOT / "config" / "tolerances.json"))
PASS, FAIL, INC, NA = "PASS", "FAIL", "INCONCLUSIVE", "N/A"


def chk(rule, status, explanation, expected=None, reported=None):
    return dict(rule=rule, status=status, expected=expected, reported=reported, explanation=explanation)


def fnum(x, nd=2):
    return None if x is None else round(float(x), nd)


# ------------------------------------------------------------ AI item helpers
def ai_families(item):
    """Families of the AI-reported layers (metallization tracked separately)."""
    fams, unknown = set(), []
    for l in item.get("layers") or []:
        name = str(l.get("material", ""))
        form = str(l.get("form", "")).lower()
        canon = materials.normalize(name)
        if canon is None:
            unknown.append(name)
            continue
        if canon == "ALUMINUM" and _is_metallization(l):
            fams.add("METALLIZATION")
        else:
            fams.add(materials.family(canon))
    return fams, unknown


def _is_metallization(l):
    form = str(l.get("form", "")).lower()
    name = str(l.get("material", "")).lower()
    t = l.get("thickness_um")
    if "metal" in form or "vapor" in form or "vacuum" in form or "metalli" in name:
        return True
    try:
        return t is not None and float(t) < 1.0
    except (TypeError, ValueError):
        return False


def ai_al_forms(item):
    forms = set()
    for l in item.get("layers") or []:
        if materials.normalize(str(l.get("material", ""))) == "ALUMINUM" or "metalli" in str(l.get("form", "")).lower():
            forms.add("metallization" if _is_metallization(l) else "foil")
    return forms


MONO_CATEGORIES = {c for c in categories.CATEGORIES if not c.startswith(("Multi", "Paper-based"))}


# ------------------------------------------------------------ per-item checks
def check_unit_and_physics(w, p):
    if w is None:
        bad = chk("physics_mass", FAIL, "No numeric weight_g reported.", reported=w)
        return chk("unit_sanity", FAIL, "No numeric weight_g reported.", reported=w), bad
    if w <= 0:
        e = f"Reported weight {w} g is not physically possible (must be > 0)."
        return chk("unit_sanity", FAIL, e, reported=w), chk("physics_mass", FAIL, e, reported=w)
    if not p.mass_ok:
        why = "; ".join(p.uncertain) or "could not compute a mass from the spec text"
        e = f"Checker could not read the spec confidently ({why})."
        return chk("unit_sanity", INC, e, reported=w), chk("physics_mass", INC, e, reported=w)
    lo, hi = p.mass_range_g
    nom = p.mass_nominal_g
    ratio = w / nom
    exp = dict(nominal_g=fnum(nom, 3), range_g=[fnum(lo, 3), fnum(hi, 3)])
    if lo <= w <= hi:
        return (chk("unit_sanity", PASS, "Weight is in the physically plausible range; no unit error indicated.", exp, w),
                chk("physics_mass", PASS, f"{w:g} g is within the physical range {lo:.3g}-{hi:.3g} g "
                                          f"(ratio to nominal {ratio:.2f}).", exp, w))
    # outside the physics range
    phys = chk("physics_mass", FAIL,
               f"Reported {w:g} g but the spec's dimensions x thickness x density give {lo:.3g}-{hi:.3g} g "
               f"(nominal {nom:.3g} g). Reported/nominal = {ratio:.2f}x.", exp, w)
    for name, f in UNIT_CONFUSIONS.items():
        for direction, r in (("too high", ratio / f), ("too low", ratio * f)):
            if abs(r - 1) < TOL["unit_error_match_rel"]:
                return (chk("unit_sanity", FAIL,
                            f"Reported value is ~{f:g}x {direction} vs physics - matches a {name} unit confusion.",
                            dict(exp, suspected_confusion=name), w), phys)
    return chk("unit_sanity", PASS, "Out of range, but not by a known unit-conversion factor.", exp, w), phys


def check_structure(item, p):
    fams, unknown = ai_families(item)
    cat = item.get("category")
    if not item.get("layers"):
        return chk("structure", FAIL, "AI listed no materials/layers for this component.",
                   expected=sorted(p.materials_mentioned), reported=[])
    # foil presence can be judged even when mass fractions are uncertain
    spec_has_foil = p.has_foil or ("foil" in p.text.lower() and "ALUMINUM" in p.materials_mentioned)
    if spec_has_foil and "ALUMINUM" not in fams:
        return chk("structure", FAIL,
                   "Spec contains aluminium FOIL (real mass, ~20 % of a typical laminate) but the AI's layers omit aluminium.",
                   expected="ALUMINUM foil layer", reported=sorted(fams))
    sig = p.significant_families()
    if sig is None:
        return chk("structure", INC, "Checker could not compute mass fractions from the spec: " + "; ".join(p.uncertain),
                   reported=sorted(fams))
    missing = [f for f in sig if f not in fams]
    if missing:
        return chk("structure", FAIL,
                   f"Spec has significant (>= {categories.THRESH:.0%} of mass) material families {sig}; "
                   f"AI's layers are missing {missing}.", expected=sig, reported=sorted(fams))
    if len(sig) > 1 and cat in MONO_CATEGORIES:
        return chk("structure", FAIL,
                   f"Spec is multi-material {sig}, but AI reported a mono-material category '{cat}'.",
                   expected=sig, reported=cat)
    note = f" (AI material names not recognised: {unknown})" if unknown else ""
    return chk("structure", PASS, f"AI layers cover all significant material families {sig}.{note}",
               expected=sig, reported=sorted(fams))


def check_metal(item, p):
    forms = ai_al_forms(item)
    # fall back on raw wording when a layer could not be fully parsed (e.g. unit missing)
    low = p.text.lower()
    spec_foil = p.has_foil or ("foil" in low and "ALUMINUM" in p.materials_mentioned)
    spec_met = p.has_metallization or bool(spec_parser.MET_RE.search(p.text))
    if not (spec_foil or spec_met or forms):
        return chk("metallized_vs_foil", NA, "No aluminium foil or metallization in spec or report.")
    if p.geometry in ("stated", "surface") and not (spec_foil or spec_met):
        return chk("metallized_vs_foil", NA, "Rigid aluminium/other part; foil vs metallization not applicable.")
    if spec_met and not spec_foil and "foil" in forms:
        return chk("metallized_vs_foil", FAIL,
                   "Spec says METALLIZED film (vacuum-deposited Al, ~10-100 nm, <0.3 g/m²) but the AI reported "
                   "aluminium FOIL (micrometre-scale, ~19-24 g/m² at 7-9 µm). This changes mass and category.",
                   expected="metallization", reported=sorted(forms))
    if spec_foil and "foil" not in forms and "metallization" in forms:
        return chk("metallized_vs_foil", FAIL,
                   "Spec says aluminium FOIL (real mass) but the AI reported it as metallization (negligible mass).",
                   expected="foil", reported=sorted(forms))
    if not (spec_foil or spec_met) and "foil" in forms:
        return chk("metallized_vs_foil", FAIL, "AI reported aluminium foil that does not appear in the spec.",
                   expected="none", reported=sorted(forms))
    if p.uncertain and not (spec_foil or spec_met):
        return chk("metallized_vs_foil", INC, "Spec could not be fully parsed.", reported=sorted(forms))
    exp = sorted(x for x, b in (("foil", spec_foil), ("metallization", spec_met)) if b)
    return chk("metallized_vs_foil", PASS, "Aluminium form (foil vs metallization) consistent with spec.",
               expected=exp, reported=sorted(forms))


def check_category(item, p):
    cat = item.get("category")
    if cat not in categories.CATEGORIES:
        return chk("category_validity", FAIL,
                   f"'{cat}' is not in the (placeholder) category list.", expected="one of config list", reported=cat)
    if p.derived_category is None:
        return chk("category_validity", INC,
                   "Category is a valid list value, but checker could not derive the expected category: "
                   + "; ".join(p.uncertain), reported=cat)
    if p.category_ambiguous:
        return chk("category_validity", INC,
                   "A material's mass fraction is within 1.5 points of the 5 % significance threshold; category ambiguous.",
                   expected=p.derived_category, reported=cat)
    if cat != p.derived_category:
        fr = {k: f"{v:.1%}" for k, v in (p.fractions or {}).items()}
        return chk("category_validity", FAIL,
                   f"From the spec's materials (mass fractions {fr}) the placeholder rules give "
                   f"'{p.derived_category}', not '{cat}'.", expected=p.derived_category, reported=cat)
    return chk("category_validity", PASS, "Category consistent with spec materials under placeholder rules.",
               expected=p.derived_category, reported=cat)


def overall(checks):
    st = [c["status"] for c in checks]
    if FAIL in st:
        return FAIL
    # inconclusive only matters for the checks that judge the number/category
    if any(c["status"] == INC for c in checks):
        return INC
    return PASS


def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------ catalog level
def check_catalog(spec_text, report):
    split = spec_parser.split_catalog(spec_text)
    parsed = {(s, c): spec_parser.parse_component(t, TOL) for s, comps in split.items() for c, t in comps.items()}
    items = report.get("items") or []
    seen = {}
    results = []
    for idx, it in enumerate(items):
        sku = str(it.get("sku", "")).strip().upper()
        cid = str(it.get("component_id", "")).strip().upper()
        key = (sku, cid)
        w = _float(it.get("weight_g"))
        row = dict(index=idx, sku=sku, component_id=cid, ai_item=it, checks=[])
        if key not in parsed:
            row["checks"].append(chk("completeness", FAIL,
                                     f"{sku}/{cid} does not exist in the catalog (invented or mis-keyed item).",
                                     expected="an SKU/component present in spec", reported=f"{sku}/{cid}"))
            row["overall"] = FAIL
            results.append(row)
            continue
        if key in seen:
            row["checks"].append(chk("completeness", FAIL,
                                     f"{sku}/{cid} is reported more than once (duplicate of item #{seen[key]}).",
                                     expected="exactly once", reported="duplicate"))
        else:
            seen[key] = idx
            row["checks"].append(chk("completeness", PASS, "Component exists in spec and is reported once."))
        p = parsed[key]
        row["spec_text"] = split[sku][cid]
        row["parsed"] = p.summary()
        u, ph = check_unit_and_physics(w, p)
        row["checks"] += [u, ph, check_structure(it, p), check_metal(it, p), check_category(it, p)]
        row["overall"] = overall(row["checks"])
        results.append(row)
    missing = [dict(sku=s, component_id=c, spec_text=split[s][c],
                    check=chk("completeness", FAIL, f"{s}/{c} is in the catalog but missing from the AI report.",
                              expected="reported", reported="missing"))
               for (s, c) in parsed if (s, c) not in seen]
    return dict(items=results, missing=missing, totals=check_totals(report),
                n_spec_components=len(parsed))


def check_totals(report):
    items = report.get("items") or []
    recomputed = {}
    for it in items:
        w = _float(it.get("weight_g"))
        if w is not None:
            recomputed[it.get("category")] = recomputed.get(it.get("category"), 0) + w
    out = []
    ai_tot = report.get("totals_by_category")
    if not isinstance(ai_tot, dict):
        out.append(chk("totals", INC, "AI report has no totals_by_category to verify."))
    else:
        for cat in sorted(set(recomputed) | set(ai_tot), key=str):
            a = _float(ai_tot.get(cat))
            r = recomputed.get(cat, 0.0)
            if a is None:
                out.append(chk("totals", FAIL, f"Category '{cat}' has line items but no reported total.", fnum(r), None))
            elif abs(a - r) > max(0.5, 0.01 * r):
                out.append(chk("totals", FAIL, f"'{cat}': AI total {a:g} g but line items sum to {r:.2f} g.", fnum(r), a))
            else:
                out.append(chk("totals", PASS, f"'{cat}' total matches line items.", fnum(r), a))
    a = _float(report.get("total_weight_g"))
    r = sum(recomputed.values())
    if a is None:
        out.append(chk("totals", INC, "No total_weight_g reported."))
    elif abs(a - r) > max(0.5, 0.01 * r):
        out.append(chk("totals", FAIL, f"Overall: AI total {a:g} g but line items sum to {r:.2f} g.", fnum(r), a))
    else:
        out.append(chk("totals", PASS, "Overall total matches line items.", fnum(r), a))
    return out


def main():
    ap = argparse.ArgumentParser(description="Run checker over AI outputs.")
    ap.add_argument("--source", default="gemini", help="subfolder of data/ai_outputs (gemini, manual, injected)")
    a = ap.parse_args()
    out_dir = ROOT / "data" / "results" / a.source
    out_dir.mkdir(parents=True, exist_ok=True)
    src = ROOT / "data" / "ai_outputs" / a.source
    ids = sorted({f.name.split(".")[0] for f in src.glob("cat_*.json")} |
                 {f.name.split(".")[0] for f in (src / "raw").glob("cat_*.txt")})
    for cid in ids:
        spec = (ROOT / "data" / "catalogs" / cid / "spec.txt").read_text()
        f = src / f"{cid}.json"
        format_error = None
        if f.exists():
            try:
                report = json.loads(f.read_text())
            except json.JSONDecodeError as e:
                format_error = str(e)
        else:
            format_error = "AI response was not valid JSON (raw text in raw/); nothing could be read"
        if format_error:
            # Count it, don't hide it: treat as an empty report, so every component is 'missing'.
            report = {"items": []}
        res = check_catalog(spec, report)
        res["format_error"] = format_error
        (out_dir / f"{cid}.json").write_text(json.dumps(res, indent=1, default=list))
        n_fail = sum(r["overall"] == FAIL for r in res["items"]) + len(res["missing"])
        n_inc = sum(r["overall"] == INC for r in res["items"])
        print(f"{cid}: {len(res['items'])} items, {n_fail} flagged, {n_inc} inconclusive, {len(res['missing'])} missing")


if __name__ == "__main__":
    main()
