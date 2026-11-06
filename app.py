"""Demo UI:  streamlit run app.py

Left: raw spec text | Middle: AI's report | Right: checker flags.
Top: evaluation metrics across all catalogs + an example for the demo.
"""
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
RES = ROOT / "data" / "results"
COLORS = {"FAIL": "#d62728", "INCONCLUSIVE": "#e6a700", "PASS": "#2ca02c", "N/A": "#999999"}
ICON = {"FAIL": "🔴", "INCONCLUSIVE": "🟡", "PASS": "🟢", "N/A": "⚪"}

st.set_page_config(page_title="EPR Physics Checker", layout="wide")


def load(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else None


def badge(status):
    return (f"<span style='background:{COLORS[status]};color:white;padding:1px 7px;border-radius:8px;"
            f"font-size:0.75em;font-weight:600'>{status}</span>")


sources = [d.name for d in RES.iterdir() if d.is_dir()] if RES.exists() else []
if not sources:
    st.error("No results yet. Run the pipeline first (see README).")
    st.stop()
default = sources.index("gemini") if "gemini" in sources else 0

st.sidebar.title("EPR Physics Checker")
source = st.sidebar.selectbox("AI output source", sources, index=default,
                              help="gemini = real model output; injected = SYNTHETIC stress test with known errors")
cats = sorted(p.stem for p in (RES / source).glob("cat_*.json"))
catalog = st.sidebar.selectbox("Catalog", cats)
only_flagged = st.sidebar.checkbox("Show only flagged / inconclusive", value=False)
st.sidebar.caption("⚠️ Synthetic catalogs. Category list is a PLACEHOLDER, not official CAA categories.")

st.title("Compliance software checks forms. Ours checks the physics.")
if source == "injected":
    st.warning("Source = **injected**: these are SYNTHETIC reports with deliberately injected errors "
               "(stress test of the checker), not real AI output.")

# ------------------------------------------------------------------ metrics
ev = load(RES / source / "evaluation.json")
if ev:
    c = ev["confusion"]
    m = st.columns(3)
    pct = lambda x: "n/a" if x is None else f"{x:.1%}"
    m[0].metric("AI error rate", pct(ev["ai_error_rate"]), help=f"{ev['ai_wrong']}/{ev['n_line_items']} line items wrong vs ground truth")
    m[1].metric("AI errors caught", c["TP"])
    m[2].metric("Inconclusive", ev["inconclusive"]["total"],
                help=f"{ev['inconclusive']['on_wrong_items']} on wrong items, {ev['inconclusive']['on_right_items']} on right items")
    failed = [t["catalog"] for t in ev["totals"]["per_catalog"] if t.get("format_error") or t.get("ai_returned_items") == 0]
    if failed:
        st.caption(f"⚠️ {len(failed)}/{ev['n_catalogs']} catalogs had no usable AI report ({', '.join(failed)}); "
                   "their components count as missing.")
    with st.expander("Breakdown by error type and by rule"):
        st.table([dict(error_type=k, **v) for k, v in ev["by_error_type"].items()])
        st.table([dict(rule=k, **v) for k, v in ev["by_rule"].items()])
else:
    st.info("Run `python -m epr.evaluate --source %s` for metrics." % source)

res = load(RES / source / f"{catalog}.json")
gt = load(ROOT / "data" / "catalogs" / catalog / "ground_truth.json")
truth = {(s["sku"], c["component_id"]): c for s in gt["skus"] for c in s["components"]} if gt else {}


# ------------------------------------------------------------------ example
def example_score(r):
    fails = {c["rule"] for c in r["checks"] if c["status"] == "FAIL"}
    p = r.get("parsed") or {}
    s = 0
    if "structure" in fails and p.get("has_foil"):
        s += 10
    if "metallized_vs_foil" in fails:
        s += 9
    if "physics_mass" in fails and p.get("has_foil"):
        s += 5
    if "physics_mass" in fails and p.get("geometry", "").endswith("pouch"):
        s += 4
    if "category_validity" in fails:
        s += 2
    if "physics_mass" in fails:
        s += 1
    return s


# Pinned example for the 3-minute demo (a REAL Gemini error, chosen after the run). Falls back to scoring.
EXAMPLE_PIN = {"gemini": ("cat_20", "RLC-1031", "C1")}


def find_example():
    pin = EXAMPLE_PIN.get(source)
    if pin and (RES / source / f"{pin[0]}.json").exists():
        for r in load(RES / source / f"{pin[0]}.json")["items"]:
            if (r["sku"], r["component_id"]) == pin[1:]:
                return (99, pin[0], r)
    best = None
    for f in sorted((RES / source).glob("cat_*.json")):
        for r in load(f)["items"]:
            sc = example_score(r)
            if sc and (best is None or sc > best[0]):
                best = (sc, f.stem, r)
    return best


example = find_example()
if example:
    _, hcat, r = example
    ai = r["ai_item"]
    p = r["parsed"]
    fails = [c for c in r["checks"] if c["status"] == "FAIL"]
    rng = p.get("mass_range_g")
    st.subheader("⭐ Example")
    hc = st.columns([2, 3])
    with hc[0]:
        st.markdown(f"**{hcat} · {r['sku']} / {r['component_id']}**")
        st.info(r["spec_text"])
    with hc[1]:
        mats = ", ".join(str(l.get("material")) for l in ai.get("layers") or [])
        line = f"**AI says:** {ai.get('weight_g')} g, *{ai.get('category')}* ({mats})"
        st.markdown(line)
        if rng:
            st.markdown(f"**Physics says:** ~{p['mass_nominal_g']:.2f} g (plausible {rng[0]:.2f}–{rng[1]:.2f} g)"
                        + (" — and it **contains aluminium foil**" if p.get("has_foil") else ""))
        for c in fails:
            st.markdown(f"{ICON['FAIL']} **{c['rule']}** — {c['explanation']}")
        t = truth.get((r["sku"], r["component_id"])) if hcat == catalog else \
            {(s["sku"], c["component_id"]): c for s in load(ROOT / "data" / "catalogs" / hcat / "ground_truth.json")["skus"]
             for c in s["components"]}.get((r["sku"], r["component_id"]))
        if t:
            st.caption(f"Ground truth (hidden from AI and checker): {t['true_mass_g']:.2f} g, {t['true_category']}")
st.divider()

# ------------------------------------------------------------------ catalog view
st.subheader(f"Catalog {catalog}")
tot = res["totals"]
bad_tot = [c for c in tot if c["status"] != "PASS"]
with st.expander(f"Totals check — {ICON['FAIL'] if any(c['status']=='FAIL' for c in tot) else ICON['PASS']} "
                 f"{len(bad_tot)} issue(s)"):
    for c in tot:
        st.markdown(f"{ICON[c['status']]} {c['explanation']}")

if res["missing"]:
    st.error(f"{len(res['missing'])} component(s) in the catalog are MISSING from the AI report: "
             + ", ".join(f"{m['sku']}/{m['component_id']}" for m in res["missing"]))

h = st.columns([3, 3, 4])
h[0].markdown("#### Spec text (raw)")
h[1].markdown("#### AI report")
h[2].markdown("#### Checker")
for r in res["items"]:
    if only_flagged and r["overall"] == "PASS":
        continue
    cols = st.columns([3, 3, 4])
    with cols[0]:
        st.markdown(f"**{r['sku']} / {r['component_id']}** {badge(r['overall'])}", unsafe_allow_html=True)
        st.caption(r.get("spec_text", "— not in catalog —"))
    with cols[1]:
        ai = r["ai_item"]
        st.markdown(f"**{ai.get('weight_g')} g** · {ai.get('category')}")
        st.caption(" / ".join(
            f"{l.get('material')}"
            + (f" {l['thickness_um']:g}µm" if isinstance(l.get("thickness_um"), (int, float)) else "")
            + (f" {l['grammage_gsm']:g}gsm" if isinstance(l.get("grammage_gsm"), (int, float)) else "")
            + (f" [{l.get('form')}]" if l.get("form") else "")
            for l in ai.get("layers") or []))
    with cols[2]:
        for c in r["checks"]:
            if c["status"] in ("PASS", "N/A") and r["overall"] != "PASS":
                continue
            if r["overall"] == "PASS" and c["rule"] != "physics_mass":
                continue
            st.markdown(f"{ICON[c['status']]} **{c['rule']}**: {c['explanation']}")
    st.markdown("<hr style='margin:4px 0;opacity:0.2'>", unsafe_allow_html=True)
