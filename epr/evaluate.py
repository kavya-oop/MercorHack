"""Evaluate the CHECKER (not just the AI) against ground truth.

Step 1: label every line item as actually right/wrong by comparing the AI
        report with ground_truth.json (this is the ONLY module, besides the
        generator and injector, that reads ground truth).
Step 2: compare checker verdicts to those labels -> TP/FP/FN/TN, precision,
        recall, per-error-type breakdown. INCONCLUSIVE is reported separately.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import materials, categories
from .checker import ai_families, ai_al_forms, FAIL, INC, PASS
from .units import UNIT_CONFUSIONS

ROOT = Path(__file__).resolve().parent.parent
TOL = json.load(open(ROOT / "config" / "tolerances.json"))

# which checker rule is *designed* to catch which error type
TARGET_RULES = {
    "missing": {"completeness"}, "duplicate": {"completeness"}, "extra": {"completeness"},
    "weight_error": {"physics_mass", "unit_sanity"}, "unit_error": {"unit_sanity"},
    "category_error": {"category_validity"}, "structure_error": {"structure"},
    "metal_form_error": {"metallized_vs_foil"},
}


def label_item(ai, gt):
    """Return list of error types for an AI item vs its ground-truth component."""
    errs = []
    try:
        w = float(ai.get("weight_g"))
    except (TypeError, ValueError):
        w = None
    t = gt["true_mass_g"]
    if w is None or abs(w / t - 1) > TOL["ground_truth_weight_rel"]:
        errs.append("weight_error")
        if w:
            r = w / t
            if any(abs(r / f - 1) < TOL["unit_error_match_rel"] or abs(r * f - 1) < TOL["unit_error_match_rel"]
                   for f in UNIT_CONFUSIONS.values()):
                errs.append("unit_error")
    if ai.get("category") != gt["true_category"]:
        errs.append("category_error")
    sig = categories.significant_families(gt["family_fractions"])
    fams, _ = ai_families(ai)
    if any(f not in fams for f in sig):
        errs.append("structure_error")
    kinds = {l["kind"] for l in gt["layers"] if l["material"] == "ALUMINUM"}
    forms = ai_al_forms(ai)
    gt_foil, gt_met = "foil" in kinds, "metallization" in kinds
    if gt["geometry"] in ("sheet", "flat_pouch", "standup_pouch", "side_gusset_bag"):
        # wrong FORM of aluminium (an omitted Al layer entirely is a structure_error instead)
        if (gt_foil and forms and "foil" not in forms) or (gt_met and not gt_foil and "foil" in forms) or \
           (not gt_foil and not gt_met and "foil" in forms):
            errs.append("metal_form_error")
    return errs


def evaluate(source):
    rows = []
    totals_rows = []
    for gt_f in sorted((ROOT / "data" / "catalogs").glob("cat_*/ground_truth.json")):
        cid = gt_f.parent.name
        res_f = ROOT / "data" / "results" / source / f"{cid}.json"
        if not res_f.exists():
            continue
        gt = json.loads(gt_f.read_text())
        res = json.loads(res_f.read_text())
        truth = {(s["sku"], c["component_id"]): c for s in gt["skus"] for c in s["components"]}
        seen = set()
        for r in res["items"]:
            key = (r["sku"], r["component_id"])
            fired = {c["rule"] for c in r["checks"] if c["status"] == FAIL}
            inc_rules = {c["rule"] for c in r["checks"] if c["status"] == INC}
            if key not in truth:
                errs, tags = ["extra"], []
            elif key in seen:
                errs, tags = ["duplicate"], truth[key]["tags"]
            else:
                seen.add(key)
                errs, tags = label_item(r["ai_item"], truth[key]), truth[key]["tags"]
            rows.append(dict(catalog=cid, sku=r["sku"], component_id=r["component_id"], errors=errs,
                             wrong=bool(errs), verdict=r["overall"], fired=sorted(fired),
                             inconclusive_rules=sorted(inc_rules), tags=tags,
                             ai_weight=r["ai_item"].get("weight_g"),
                             true_weight=truth.get(key, {}).get("true_mass_g"),
                             ai_category=r["ai_item"].get("category"),
                             true_category=truth.get(key, {}).get("true_category")))
        missing_flagged = {(m["sku"], m["component_id"]) for m in res["missing"]}
        for key, c in truth.items():
            if key not in seen:
                rows.append(dict(catalog=cid, sku=key[0], component_id=key[1], errors=["missing"], wrong=True,
                                 verdict=FAIL if key in missing_flagged else PASS,
                                 fired=["completeness"] if key in missing_flagged else [],
                                 inconclusive_rules=[], tags=c["tags"], ai_weight=None,
                                 true_weight=c["true_mass_g"], ai_category=None, true_category=c["true_category"]))
        # totals: truth = AI totals internally consistent? plus AI total vs real total
        tot_fail = any(c["status"] == FAIL for c in res["totals"])
        try:
            ai_total = float(json.loads((ROOT / "data" / "ai_outputs" / source / f"{cid}.json").read_text())
                             .get("total_weight_g"))
        except (TypeError, ValueError, FileNotFoundError):
            ai_total = None
        totals_rows.append(dict(catalog=cid, checker_totals_flag=tot_fail, format_error=res.get("format_error"),
                                ai_returned_items=len(res["items"]),
                                ai_total_g=ai_total, true_total_g=gt["total_weight_g"],
                                ai_total_rel_error=(ai_total / gt["total_weight_g"] - 1) if ai_total else None))
    return summarize(rows, totals_rows, source)


def summarize(rows, totals_rows, source):
    n = len(rows)
    wrong = [r for r in rows if r["wrong"]]
    conc = [r for r in rows if r["verdict"] != INC]
    TP = sum(r["wrong"] and r["verdict"] == FAIL for r in conc)
    FP = sum((not r["wrong"]) and r["verdict"] == FAIL for r in conc)
    FN = sum(r["wrong"] and r["verdict"] == PASS for r in conc)
    TN = sum((not r["wrong"]) and r["verdict"] == PASS for r in conc)
    inc_wrong = sum(r["wrong"] and r["verdict"] == INC for r in rows)
    inc_right = sum((not r["wrong"]) and r["verdict"] == INC for r in rows)
    by_type = {}
    for et, rules in TARGET_RULES.items():
        rs = [r for r in rows if et in r["errors"]]
        if not rs:
            continue
        by_type[et] = dict(
            count=len(rs),
            caught_by_target_rule=sum(bool(rules & set(r["fired"])) for r in rs),
            caught_by_any_rule=sum(r["verdict"] == FAIL for r in rs),
            inconclusive=sum(r["verdict"] == INC for r in rs),
            missed=sum(r["verdict"] == PASS for r in rs))
    by_rule = {}
    for r in rows:
        for rule in r["fired"]:
            d = by_rule.setdefault(rule, dict(fired=0, on_wrong_items=0))
            d["fired"] += 1
            d["on_wrong_items"] += r["wrong"]
    by_tag = defaultdict(lambda: [0, 0])
    for r in rows:
        for t in r["tags"]:
            by_tag[t][0] += 1
            by_tag[t][1] += r["wrong"]
    prec = TP / (TP + FP) if TP + FP else None
    rec = TP / (TP + FN) if TP + FN else None
    out = dict(
        source=source, n_line_items=n, n_catalogs=len(totals_rows),
        ai_wrong=len(wrong), ai_error_rate=len(wrong) / n if n else None,
        confusion=dict(TP=TP, FP=FP, FN=FN, TN=TN),
        inconclusive=dict(total=inc_wrong + inc_right, on_wrong_items=inc_wrong, on_right_items=inc_right),
        precision=prec, recall=rec,
        recall_counting_inconclusive_as_missed=TP / (TP + FN + inc_wrong) if TP + FN + inc_wrong else None,
        by_error_type=by_type, by_rule=by_rule,
        ai_error_rate_by_tag={t: dict(n=a, wrong=b, rate=b / a) for t, (a, b) in sorted(by_tag.items())},
        totals=dict(catalogs_with_totals_flag=sum(t["checker_totals_flag"] for t in totals_rows),
                    per_catalog=totals_rows),
        false_positives=[r for r in rows if not r["wrong"] and r["verdict"] == FAIL],
        false_negatives=[r for r in rows if r["wrong"] and r["verdict"] == PASS],
        rows=rows)
    return out


def fmt_pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def report_md(e):
    c = e["confusion"]
    L = [f"# Checker evaluation — source: `{e['source']}`", "",
         f"- Catalogs: {e['n_catalogs']}, line items (incl. missing/extra): {e['n_line_items']}",
         f"- **AI error rate:** {e['ai_wrong']}/{e['n_line_items']} = {fmt_pct(e['ai_error_rate'])}",
         f"- **Checker precision:** {fmt_pct(e['precision'])}   **recall:** {fmt_pct(e['recall'])} "
         f"(recall if inconclusive counted as missed: {fmt_pct(e['recall_counting_inconclusive_as_missed'])})",
         f"- Confusion (conclusive items only): TP={c['TP']} FP={c['FP']} FN={c['FN']} TN={c['TN']}",
         f"- **Inconclusive:** {e['inconclusive']['total']} items "
         f"({e['inconclusive']['on_wrong_items']} actually wrong, {e['inconclusive']['on_right_items']} actually right)",
         f"- Catalogs where totals check fired: {e['totals']['catalogs_with_totals_flag']}/{e['n_catalogs']}",
         f"- Catalogs where the AI returned invalid JSON: "
         f"{[t['catalog'] for t in e['totals']['per_catalog'] if t.get('format_error')] or 'none'}",
         f"- Catalogs where the AI returned zero items: "
         f"{[t['catalog'] for t in e['totals']['per_catalog'] if not t.get('format_error') and t.get('ai_returned_items') == 0] or 'none'}", "",
         "## By error type", "", "| error type | count | caught by target rule | caught by any rule | inconclusive | missed |",
         "|---|---|---|---|---|---|"]
    for k, v in e["by_error_type"].items():
        L.append(f"| {k} | {v['count']} | {v['caught_by_target_rule']} | {v['caught_by_any_rule']} | {v['inconclusive']} | {v['missed']} |")
    L += ["", "## By rule (how often it fired, and how often on truly-wrong items)", "", "| rule | fired | on wrong items |", "|---|---|---|"]
    for k, v in sorted(e["by_rule"].items()):
        L.append(f"| {k} | {v['fired']} | {v['on_wrong_items']} |")
    L += ["", "## AI error rate by hard-case tag", "", "| tag | n | wrong | rate |", "|---|---|---|---|"]
    for k, v in e["ai_error_rate_by_tag"].items():
        L.append(f"| {k} | {v['n']} | {v['wrong']} | {fmt_pct(v['rate'])} |")
    L += ["", f"## False negatives ({len(e['false_negatives'])}) — first 15", ""]
    for r in e["false_negatives"][:15]:
        L.append(f"- {r['catalog']} {r['sku']}/{r['component_id']}: errors={r['errors']}, AI {r['ai_weight']} g vs true "
                 f"{r['true_weight']} g; AI cat '{r['ai_category']}' vs '{r['true_category']}'")
    L += ["", f"## False positives ({len(e['false_positives'])}) — first 15", ""]
    for r in e["false_positives"][:15]:
        L.append(f"- {r['catalog']} {r['sku']}/{r['component_id']}: fired={r['fired']}, AI {r['ai_weight']} g vs true {r['true_weight']} g")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="gemini")
    a = ap.parse_args()
    e = evaluate(a.source)
    d = ROOT / "data" / "results" / a.source
    (d / "evaluation.json").write_text(json.dumps(e, indent=1, default=list))
    md = report_md(e)
    (d / "evaluation.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
