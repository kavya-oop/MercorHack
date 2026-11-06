# Checker evaluation — source: `injected`

- Catalogs: 20, line items (incl. missing/extra): 1449
- **AI error rate:** 513/1449 = 35.4%
- **Checker precision:** 100.0%   **recall:** 96.2% (recall if inconclusive counted as missed: 94.7%)
- Confusion (conclusive items only): TP=486 FP=0 FN=19 TN=903
- **Inconclusive:** 41 items (8 actually wrong, 33 actually right)
- Catalogs where totals check fired: 9/20
- Catalogs where the AI returned invalid JSON: none
- Catalogs where the AI returned zero items: none

## By error type

| error type | count | caught by target rule | caught by any rule | inconclusive | missed |
|---|---|---|---|---|---|
| missing | 53 | 53 | 53 | 0 | 0 |
| duplicate | 56 | 56 | 56 | 0 | 0 |
| extra | 45 | 45 | 45 | 0 | 0 |
| weight_error | 239 | 212 | 214 | 6 | 19 |
| unit_error | 108 | 106 | 106 | 2 | 0 |
| category_error | 131 | 128 | 128 | 3 | 0 |
| structure_error | 8 | 7 | 7 | 1 | 0 |
| metal_form_error | 6 | 6 | 6 | 0 | 0 |

## By rule (how often it fired, and how often on truly-wrong items)

| rule | fired | on wrong items |
|---|---|---|
| category_validity | 128 | 128 |
| completeness | 154 | 154 |
| metallized_vs_foil | 6 | 6 |
| physics_mass | 212 | 212 |
| structure | 14 | 14 |
| unit_sanity | 106 | 106 |

## AI error rate by hard-case tag

| tag | n | wrong | rate |
|---|---|---|---|
| adhesive | 255 | 80 | 31.4% |
| ambiguous | 47 | 14 | 29.8% |
| capacity-trap | 62 | 21 | 33.9% |
| coating | 182 | 65 | 35.7% |
| foil | 107 | 39 | 36.4% |
| grammage | 345 | 117 | 33.9% |
| gusset | 99 | 30 | 30.3% |
| laminate | 255 | 80 | 31.4% |
| metallized | 108 | 33 | 30.6% |
| multilayer-rigid | 21 | 6 | 28.6% |
| rigid | 248 | 81 | 32.7% |
| sheet | 477 | 163 | 34.2% |
| stated-weight | 391 | 134 | 34.3% |
| two-faced | 288 | 90 | 31.2% |

## False negatives (19) — first 15

- cat_03 JCR-5039/C1: errors=['weight_error'], AI 52.097 g vs true 46.2863 g; AI cat 'HDPE rigid' vs 'HDPE rigid'
- cat_03 JKG-5287/C1: errors=['weight_error'], AI 6.11 g vs true 5.4246 g; AI cat 'PE flexible' vs 'PE flexible'
- cat_05 JRR-2442/C1: errors=['weight_error'], AI 21.225 g vs true 18.2011 g; AI cat 'PP rigid' vs 'PP rigid'
- cat_06 KCJ-1955/C1: errors=['weight_error'], AI 2.814 g vs true 3.2131 g; AI cat 'PE flexible' vs 'PE flexible'
- cat_08 RCC-9990/C2: errors=['weight_error'], AI 7.991 g vs true 6.8606 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_12 WWT-9770/C1: errors=['weight_error'], AI 8.242 g vs true 9.3711 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_13 EMF-9560/C2: errors=['weight_error'], AI 1.059 g vs true 0.9313 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_13 JPW-6718/C1: errors=['weight_error'], AI 17.644 g vs true 15.5958 g; AI cat 'PET rigid' vs 'PET rigid'
- cat_13 APW-8932/C2: errors=['weight_error'], AI 11.853 g vs true 13.8313 g; AI cat 'PE flexible' vs 'PE flexible'
- cat_14 RRG-8748/C1: errors=['weight_error'], AI 7.229 g vs true 8.3787 g; AI cat 'Aluminum' vs 'Aluminum'
- cat_15 DLS-2845/C1: errors=['weight_error'], AI 18.46 g vs true 16.384 g; AI cat 'PET rigid' vs 'PET rigid'
- cat_16 SEF-7323/C1: errors=['weight_error'], AI 48.824 g vs true 57.1036 g; AI cat 'Multi-material rigid' vs 'Multi-material rigid'
- cat_17 FMG-3019/C2: errors=['weight_error'], AI 1.591 g vs true 1.3705 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_17 BSF-9796/C1: errors=['weight_error'], AI 1.603 g vs true 1.8407 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_18 MTG-2102/C3: errors=['weight_error'], AI 0.316 g vs true 0.3634 g; AI cat 'PP flexible' vs 'PP flexible'

## False positives (0) — first 15

