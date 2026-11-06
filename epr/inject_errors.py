"""SYNTHETIC STRESS TEST: build fake 'AI reports' with known, injected errors.

This is NOT AI output. It exists because a real model's mistakes may not cover
every error type, and we want to measure the checker's recall per error type
on a controlled set. Results are always reported separately from real AI runs
(source = 'injected').

Every report starts from ground truth with small +/-4 % weight noise (still
'correct' under the +/-10 % labelling rule), then each component gets at most
one injected error with probability P_ERROR.
"""
import json
import random
from pathlib import Path

from . import categories, materials
from .physics import Layer, layer_areal_mass, family_mass_fractions

ROOT = Path(__file__).resolve().parent.parent
P_ERROR = 0.35
ERROR_TYPES = ["oz_g", "kg_g", "weight_gross", "weight_subtle", "drop_foil", "met_as_foil", "foil_as_met",
               "wrong_category", "invalid_category", "missing", "duplicate", "extra", "drop_layer"]

FORM = {"film": "film", "foil": "foil", "metallization": "metallization", "paper": "paper",
        "coating": "coating", "adhesive": "adhesive", "wall": "wall"}


def to_ai_layers(layers):
    return [dict(material=l["material"].title() if l["material"] in ("ALUMINUM", "PAPER", "ADHESIVE", "COATING") else l["material"],
                 form=FORM[l["kind"]], thickness_um=l["thickness_um"], grammage_gsm=l["grammage_gsm"]) for l in layers]


def recompute(comp, layers):
    """Mass + placeholder category for a modified layer list (flexible/rigid with area)."""
    ls = [Layer(**l) for l in layers]
    area = comp["area_m2"]
    m = area * sum(layer_areal_mass(l) for l in ls)
    return m, categories.assign(comp["format"], family_mass_fractions(area, ls))


def make_report(gt, rng):
    items, log = [], []
    for s in gt["skus"]:
        for c in s["components"]:
            base = dict(sku=s["sku"], component_id=c["component_id"], component=c["component_type"],
                        layers=to_ai_layers(c["layers"]), category=c["true_category"],
                        weight_g=round(c["true_mass_g"] * rng.uniform(0.96, 1.04), 3))
            et = None
            if rng.random() < P_ERROR:
                choices = list(ERROR_TYPES)
                kinds = {l["kind"] for l in c["layers"]}
                if "foil" not in kinds or c["area_m2"] is None:
                    choices = [x for x in choices if x not in ("drop_foil", "foil_as_met")]
                if "metallization" not in kinds or c["area_m2"] is None:
                    choices.remove("met_as_foil")
                if len([l for l in c["layers"] if l["kind"] in ("film", "foil", "paper", "wall")]) < 2 or c["area_m2"] is None:
                    choices.remove("drop_layer")
                et = rng.choice(choices)
            it = dict(base)
            if et == "oz_g":
                it["weight_g"] = round(base["weight_g"] * rng.choice([28.3495, 1 / 28.3495]), 4)
            elif et == "kg_g":
                it["weight_g"] = round(base["weight_g"] * rng.choice([1000, 0.001]), 5)
            elif et == "weight_gross":
                it["weight_g"] = round(base["weight_g"] * rng.choice([rng.uniform(0.4, 0.7), rng.uniform(1.4, 2.5)]), 3)
            elif et == "weight_subtle":
                it["weight_g"] = round(c["true_mass_g"] * rng.choice([rng.uniform(0.82, 0.88), rng.uniform(1.12, 1.18)]), 3)
            elif et == "drop_foil":
                layers = [l for l in c["layers"] if l["kind"] != "foil"]
                m, cat = recompute(c, layers)
                it.update(layers=to_ai_layers(layers), weight_g=round(m, 3), category=cat)
            elif et == "met_as_foil":
                layers = [dict(l, kind="foil", thickness_um=7.0) if l["kind"] == "metallization" else l for l in c["layers"]]
                m, cat = recompute(c, layers)
                it.update(layers=to_ai_layers(layers), weight_g=round(m, 3), category=cat)
            elif et == "foil_as_met":
                layers = [dict(l, kind="metallization", thickness_um=0.04) if l["kind"] == "foil" else l for l in c["layers"]]
                m, cat = recompute(c, layers)
                it.update(layers=to_ai_layers(layers), weight_g=round(m, 3), category=cat)
            elif et == "drop_layer":
                webs = [i for i, l in enumerate(c["layers"]) if l["kind"] in ("film", "paper", "wall")]
                drop = rng.choice(webs)
                layers = [l for i, l in enumerate(c["layers"]) if i != drop]
                m, cat = recompute(c, layers)
                it.update(layers=to_ai_layers(layers), weight_g=round(m, 3), category=cat)
            elif et == "wrong_category":
                it["category"] = rng.choice([x for x in categories.CATEGORIES if x != c["true_category"]])
            elif et == "invalid_category":
                it["category"] = rng.choice(["Plastic", "Flexible plastic", "Mixed", "Metal"])
            if et == "missing":
                log.append(dict(sku=s["sku"], component_id=c["component_id"], injected=et))
                continue
            items.append(it)
            if et == "duplicate":
                items.append(dict(it))
            if et == "extra":
                items.append(dict(it, sku="ZZZ-" + str(rng.randrange(1000, 9999))))
            log.append(dict(sku=s["sku"], component_id=c["component_id"], injected=et))
    totals = {}
    for it in items:
        totals[it["category"]] = round(totals.get(it["category"], 0) + it["weight_g"], 3)
    total = round(sum(totals.values()), 3)
    tot_err = None
    if rng.random() < 0.3 and totals:
        k = rng.choice(list(totals))
        totals[k] = round(totals[k] * rng.uniform(1.15, 1.5), 3)
        tot_err = k
    return dict(items=items, totals_by_category=totals, total_weight_g=total), \
        dict(log=log, totals_error_injected_in=tot_err)


def main():
    rng = random.Random(7)
    out = ROOT / "data" / "ai_outputs" / "injected"
    out.mkdir(parents=True, exist_ok=True)
    for gt_f in sorted((ROOT / "data" / "catalogs").glob("cat_*/ground_truth.json")):
        gt = json.loads(gt_f.read_text())
        rep, log = make_report(gt, rng)
        (out / f"{gt['catalog_id']}.json").write_text(json.dumps(rep, indent=1))
        (out / f"{gt['catalog_id']}.injection_log.json").write_text(json.dumps(log, indent=1))
    print(f"wrote synthetic error-injected reports to {out}")


if __name__ == "__main__":
    main()
