# Physics-checked EPR packaging report verifier

**Compliance software checks forms. Ours checks the physics.**

Mercor Hack Day: *"How do you verify an AI's output?"* (field: Materials Science & Engineering)

Seven US states (CA, CO, ME, MD, MN, OR, WA) have packaging Extended Producer
Responsibility laws: producers report packaging weight by material category to a
PRO (mostly Circular Action Alliance), and fees follow from that data. This project
asks an LLM to turn messy packaging spec sheets into an EPR report, then verifies
that report with **materials physics**: dimensions × thickness × density (or
grammage), layer structure, foil vs. metallization, and unit sanity.

> ⚠️ **Everything here is synthetic or placeholder.** The catalogs are generated test data
> (not real products). The material category list is a **simplified placeholder**, *not*
> the official CAA or state categories. See [Limitations](#known-limitations).

---

## Pipeline

```
generator ──► spec.txt ──────────────► AI (fresh call per catalog) ──► AI report JSON
    │                    │                                                 │
    └► ground_truth.json │                                                 │
       (hidden)          └──► checker (parses RAW text itself) ◄───────────┘
            │                          │
            └──────► evaluate ◄────────┘   (labels AI items with ground truth,
                                              then scores the CHECKER's flags)
```

| Step | Command | Output |
|---|---|---|
| 0. Setup | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env` (then add your key) | |
| 1. Tests | `.venv/bin/python -m pytest -q` | 28 tests with hand-computed expected values |
| 2. Generate catalogs | `.venv/bin/python -m epr.generator --n 20` | `data/catalogs/cat_XX/{spec.txt, ground_truth.json}` |
| 3a. Run AI (API) | `.venv/bin/python -m epr.ai_runner` | `data/ai_outputs/gemini/cat_XX.json` (+ `raw/`) |
| 3b. Run AI (manual) | `.venv/bin/python -m epr.ai_runner --print-prompt cat_01` → paste into a **new** chat → save reply as `data/ai_outputs/manual/cat_01.json` | |
| 4. Check | `.venv/bin/python -m epr.checker --source gemini` (or `manual`) | `data/results/<source>/cat_XX.json` |
| 5. Evaluate | `.venv/bin/python -m epr.evaluate --source gemini` | `data/results/<source>/evaluation.{md,json}` |
| 6. Stress test (optional) | `.venv/bin/python -m epr.inject_errors && .venv/bin/python -m epr.checker --source injected && .venv/bin/python -m epr.evaluate --source injected` | synthetic reports with known errors |
| 7. Demo | `.venv/bin/streamlit run app.py` | local web UI |

`./run_all.sh` runs steps 1–6.

**AI config** (`.env`, git-ignored): `GEMINI_API_KEY`, `EPR_PROVIDER=gemini`,
`EPR_MODEL=gemini-3.5-flash-lite`. Each catalog is one stateless `generateContent`
request containing only the task instructions + `spec.txt` (temperature 0, JSON
response mode). The AI never sees `ground_truth.json` or checker code.

---

## Code map

| File | What it does |
|---|---|
| `epr/units.py` | Unit conversions with sources (inch, oz, lb exact; mil; gauge; lb/3000 ft²). |
| `epr/materials.py` | Loads `config/materials.csv`; maps free-text names (BOPET, VMPET, aluminium…) to canonical materials. |
| `epr/physics.py` | Areal mass (µm × g/cm³ = g/m²), pouch/bag/sheet geometry, mass and mass **range**. |
| `epr/categories.py` | Placeholder category rules (from `config/categories.json`). |
| `epr/generator.py` | Synthetic catalogs + ground truth. |
| `epr/spec_parser.py` | **Checker's own parser** of raw spec text → layers, dimensions, mass range, or "uncertain". |
| `epr/checker.py` | Rules a–g. |
| `epr/ai_runner.py` | Fresh LLM call per catalog; manual mode. |
| `epr/evaluate.py` | Ground-truth labelling + scoring the checker's flags (caught / false alarms / missed). |
| `epr/inject_errors.py` | Synthetic error-injected reports for stress testing. |
| `app.py` | Streamlit demo. |

---

## The checker (rules)

Every flag records **rule, status (PASS/FAIL/INCONCLUSIVE/N/A), expected, reported, plain-English explanation**.

| Rule | What it does |
|---|---|
| a. completeness | Each catalog SKU/component appears exactly once; flags missing, duplicate, invented items. Uses the checker's own split of the spec text. |
| b. unit_sanity | If a weight is outside the physics range, test whether reported/expected ≈ 28.35 (oz↔g), 1000 (kg/mg↔g), 25.4 (in↔mm), 453.6 (lb↔g), 645.16 (in²↔mm²), 10 (cm↔mm), within ±12 %. |
| c. physics_mass | Independently parse dimensions, layers, thickness/grammage → plausible mass **range** using density ranges and tolerances; flag weights outside it, with ratio to nominal. |
| d. structure | Every material family ≥ 5 % of mass in the spec must appear in the AI's layers; aluminium foil can't be omitted; multi-material spec can't get a mono category. |
| e. metallized_vs_foil | Metallized film reported as foil (or vice versa). Physics rule: an Al layer ≥ 1 µm is foil; vacuum metallization is ~10–100 nm. |
| f. category_validity | Category must be in the placeholder list **and** equal what the placeholder rules give for the parsed materials. |
| g. totals | Recompute per-category and overall totals from line items; compare with the AI's totals (±max(0.5 g, 1 %)). |

**Inconclusive, not guessed:** if the checker's parser can't read something with confidence (number
without a unit, no dimensions, unknown material, unparseable adhesive), rules b, c, d and f return
INCONCLUSIVE. Foil-presence and metallized/foil checks still use the raw wording when they can.

### Physics, assumptions, tolerances

- Areal mass: `g/m² = thickness[µm] × density[g/cm³]`; paper, coatings, adhesives: grammage directly.
- Geometry (dimension pairs are always **W × H**; seals assumed inside stated dims):
  - flat pouch / sachet: `2·W·H`; stand-up pouch: `2·W·H + W·G` (G = unfolded bottom-gusset depth);
    side-gusset bag: `2·W·H + 2·G·H`; single sheet (wrap, lid, label, carton blank): `W·H`;
  - rigid: surface area × wall thickness × density, or stated part weight.
- Metallization: 10–100 nm Al (an **unsourced engineering bound**; mass < 0.3 g/m², so results don't depend on it).
- Tolerances (`config/tolerances.json`, **engineering assumptions, not standards**): dimensions ±2 %,
  film thickness ±10 %, grammage ±5 %, coat weights ±25 %, stated weights ±10 %, unit-factor match ±12 %.
- Ground-truth labelling: an AI weight is "correct" if within ±10 % of true mass; category must match
  exactly; all significant material families must be present; aluminium form must match.

### Material property table (`config/materials.csv`)

Densities are **ranges**, each with a source and a verification status. Checked during this build:

| Material | Range g/cm³ | Source | Status |
|---|---|---|---|
| PET | 1.370–1.455 | Wikipedia "Polyethylene terephthalate" (amorphous 1.370, single crystal 1.455) | ✅ — **your suggested 1.33 lower bound is not supported by this source** |
| PP | 0.895–0.93 | Wikipedia "Polypropylene" | ✅ (wider than 0.90–0.91) |
| LDPE / LLDPE | 0.910–0.940 / 0.915–0.925 | Wikipedia "Polyethylene" | ✅ |
| HDPE | 0.941–0.97 | Wikipedia "Polyethylene" (≥ 0.941) | ⚠️ upper bound 0.97 **not confirmed** |
| PS | 0.96–1.05 | Wikipedia "Polystyrene" | ✅ (wider than 1.04–1.05) |
| rigid PVC | 1.30–1.45 | Wikipedia "Polyvinyl chloride" | ✅ |
| PA6 | 1.084–1.14 | Wikipedia "Nylon 6" | 🚩 **conflicting** (1.084 marked "citation needed" vs 1.14) — confirm with a datasheet |
| EVOH | 1.14–1.21 | Kuraray EVAL product table (27/32/44 mol % ethylene) | ✅ |
| Aluminium | 2.69–2.71 | Wikipedia "Aluminium" (2.699 at 20 °C) | ✅ (±0.01 band is my allowance) |
| Steel | 7.75–8.05 | Wikipedia "Steel" | ✅ |
| Soda-lime glass | 2.50–2.53 | Wikipedia "Soda–lime glass" (2.52 container, 2.53 flat) | ⚠️ 2.50 lower bound not confirmed |

Wikipedia is a secondary source: fine for a demo, but for real use replace it with resin datasheets or a handbook.
"Nominal" densities (used only for ground truth) are typical values I chose inside each range.

**Unit factors:** inch = 25.4 mm, avoirdupois oz = 28.349523125 g, lb = 453.59237 g (exact legal
definitions); mil = 0.001 in. **Film "gauge" (100 ga = 1 mil) is a North-American industry
convention, not independently sourced here.** Sheet-metal gauge is a different system and isn't supported.

### Placeholder categories (`config/categories.json`)

`PET rigid, HDPE rigid, PP rigid, PS rigid, PVC rigid, PE flexible, PP flexible, PET flexible,
Multi-material flexible laminate, Multi-material rigid, Paper/paperboard, Paper-based multi-material,
Aluminum, Steel, Glass`

Rule (also invented): material families ≥ 5 % of mass are "significant"; metallization ignored;
one significant family → mono category; several → paper-based if paper > 50 %, else multi-material.
**This is NOT the CAA list.** Swap the JSON for the official, state-specific list and rules before real use.

---

## Synthetic catalogs (hard cases included)

20 catalogs, 15–40 SKUs each, 1–4 components per SKU (~1,350 components). The hard cases:
multilayer laminates (PET/foil/PE, PET/met-PET/PE, paper/PE/foil/PE, BOPP/met-BOPP, PE/met-PE);
metallized vs foil; paper and board by g/m² **and** lb/3000 ft²; two-faced pouches with bottom/side gussets;
mixed units (µm, micron, µ, mil, ga, gsm, g/m², oz, lb, kg, in, ", mm, cm, cm², in², mm²);
adhesives and lacquers by coat weight; HDPE/EVOH/HDPE barrier bottles; glass jars with "16 oz capacity"
(a volume) next to a part weight in oz; product net weights in SKU headers (not packaging weight);
and ~3 % deliberately under-specified sheets (a unit removed) where the right answer is "inconclusive".

Ground truth is computed in `epr/generator.py` (`finalize`) with nominal densities through the same
`epr/physics.py` functions the tests cover. Components where a material sits within ±2 points of the
5 % threshold are resampled, so every ground-truth category is unambiguous.

---

## Results

Full reports: `data/results/gemini/evaluation.md` (real model) and
`data/results/injected/evaluation.md` (synthetic stress test). Run of 2026-11-06, model
`gemini-3.5-flash-lite`, temperature 0, one fresh request per catalog.

### Real AI (Gemini 3.5 Flash-Lite), 20 catalogs, 1,348 line items

| Metric | Value |
|---|---|
| Catalogs with no usable report | **3 / 20**: `cat_03` and `cat_12` returned `{"items": []}`; `cat_14` returned invalid JSON. Counted as 227 *missing* items, not hidden. |
| AI error rate (all catalogs) | 755 / 1,348 = **56.0 %** |
| AI error rate (17 catalogs it answered) | 528 / 1,121 = **47.1 %** (478 weight errors, 125 category errors, 8 unit-factor errors) |
| AI total weight vs. truth (answered catalogs) | between −41 % and +28 %; 16 of 17 under-reported |
| Checker on Gemini's errors | **645 caught, 1 false alarm, 85 missed** (585 correct items correctly passed) |
| Inconclusive | 32 items (25 actually wrong, 7 actually right) |
| Totals check fired | 17 / 20 catalogs |

- **All 85 false negatives** are weight errors between 10 % and 20 % (the largest is 19.8 %) that land
  inside the physics tolerance band. This is the tolerance tradeoff in limitation 5.
- **The 1 false positive** (cat_15 HLM-7463/C2) is a real AI conversion mistake: it converted
  60 lb/3000 ft² paper to 88.8 g/m² (correct: 97.6 g/m²). The weight ends up 9 % low, which counts as
  "correct" under the ±10 % rule but is outside the ±5 % grammage band. It is scored as a false alarm anyway.
- Error rate by hard case (answered + empty catalogs): foil 91 %, gusset 92 %, laminate 89 %, metallized 86 %,
  HDPE/EVOH multilayer 100 %, while stated-weight parts were 25 %. Gemini handles "copy a number"
  well and "compute a laminate" badly.
- What Gemini did **not** do in this run: drop a foil layer, or swap metallized for foil. Those rules
  are therefore only exercised by the stress test below.

### Demo example (real Gemini output)

`cat_20 · RLC-1031 / C1`: stand-up pouch, 40 lb kraft paper / 15 g/m² PE / 8 µm Al foil / 100 µm LLDPE,
138 × 187 mm faces + 51 mm gusset. **Gemini: 4.19 g, "Paper-based multi-material".
Physics: 9.9–13.1 g (nominal 11.45 g), and by mass the pouch is 33 % paper, 55 % PE, 11 % aluminium,
so under the placeholder rules it is a multi-material flexible laminate, not paper-based.**
It looks like paper but is mostly plastic by mass, and the checker sees that from the spec text alone.

### Synthetic stress test (injected errors, NOT AI output)

1,449 items, 35 % with one injected error each. **486 errors caught, 0 false alarms, 19 missed**,
41 inconclusive. Every missing / duplicate / extra / unit-factor / category / metallized-vs-foil
injection was caught (or marked inconclusive). All 19 misses are deliberately "subtle" 12–18 % weight
errors. An earlier version had 59 false alarms here: 57 from a ±3 % stated-weight band (now ±10 %) and 2 from a
bug where an unparseable foil token made the metallized/foil check say "no foil in spec" (fixed:
it now falls back to the raw wording).

---

## Known limitations

1. **Synthetic data.** Real spec sheets are messier (PDFs, tables, missing data, supplier jargon).
2. **Parser/generator share an author.** The parser was written knowing the generator's phrasing
   templates, so its near-perfect parse rate on this data is **optimistic**. On real sheets, expect
   more INCONCLUSIVE results (that's the intended failure mode, but it hasn't been tested on real data).
3. **Shared physics module.** Ground truth and the checker both use `epr/physics.py`. A physics bug
   would hit both. Mitigated by 28 tests with hand-computed values, but not eliminated.
4. **Placeholder categories.** The checker verifies physical plausibility, completeness and internal
   consistency, **not legal correctness** of categories.
5. **Tolerances drive false alarms vs misses.** Physics ranges are about ±15 % wide (thickness ±10 %, density spread,
   dimensions ±2 %), so AI weight errors of roughly 10–18 % can pass (false negatives). Tighter
   tolerances would catch them but flag correct items when real films are off-gauge. Stated weights
   use ±10 % on purpose (an earlier ±3 % produced 57 false positives on the stress test).
6. **Rigid parts** are modelled as surface area × average wall thickness, which is a simplification.
7. **Stress-test numbers are synthetic.** They measure how many of each error type the checker catches on controlled errors; they
   are not a claim about any AI's error rate.
8. **Coatings/inks/tin layer** masses are only included where the spec gives a coat weight; the tinplate tin layer is ignored.
