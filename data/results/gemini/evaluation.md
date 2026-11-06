# Checker evaluation — source: `gemini`

- Catalogs: 20, line items (incl. missing/extra): 1348
- **AI error rate:** 755/1348 = 56.0%
- **Checker precision:** 99.8%   **recall:** 88.4% (recall if inconclusive counted as missed: 85.4%)
- Confusion (conclusive items only): TP=645 FP=1 FN=85 TN=585
- **Inconclusive:** 32 items (25 actually wrong, 7 actually right)
- Catalogs where totals check fired: 17/20
- Catalogs where the AI returned invalid JSON: ['cat_14']
- Catalogs where the AI returned zero items: ['cat_03', 'cat_12']

## By error type

| error type | count | caught by target rule | caught by any rule | inconclusive | missed |
|---|---|---|---|---|---|
| missing | 227 | 227 | 227 | 0 | 0 |
| weight_error | 478 | 361 | 369 | 24 | 85 |
| unit_error | 8 | 6 | 6 | 2 | 0 |
| category_error | 125 | 118 | 118 | 7 | 0 |

## By rule (how often it fired, and how often on truly-wrong items)

| rule | fired | on wrong items |
|---|---|---|
| category_validity | 118 | 118 |
| completeness | 227 | 227 |
| physics_mass | 362 | 361 |
| structure | 23 | 23 |
| unit_sanity | 6 | 6 |

## AI error rate by hard-case tag

| tag | n | wrong | rate |
|---|---|---|---|
| adhesive | 244 | 216 | 88.5% |
| ambiguous | 43 | 36 | 83.7% |
| capacity-trap | 62 | 13 | 21.0% |
| coating | 174 | 134 | 77.0% |
| foil | 101 | 92 | 91.1% |
| grammage | 328 | 169 | 51.5% |
| gusset | 95 | 87 | 91.6% |
| laminate | 244 | 216 | 88.5% |
| metallized | 103 | 89 | 86.4% |
| multilayer-rigid | 21 | 21 | 100.0% |
| rigid | 235 | 154 | 65.5% |
| sheet | 459 | 267 | 58.2% |
| stated-weight | 378 | 95 | 25.1% |
| two-faced | 276 | 239 | 86.6% |

## False negatives (85) — first 15

- cat_01 AJR-1071/C3: errors=['weight_error'], AI 0.3618 g vs true 0.3274 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_01 RTM-1800/C1: errors=['weight_error'], AI 21.46275 g vs true 23.9775 g; AI cat 'PET rigid' vs 'PET rigid'
- cat_01 BAH-1060/C2: errors=['weight_error'], AI 0.8667 g vs true 0.7844 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_02 JSV-6318/C2: errors=['weight_error'], AI 0.99 g vs true 0.8732 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_02 SLC-5268/C1: errors=['weight_error'], AI 30.51 g vs true 35.256 g; AI cat 'PS rigid' vs 'PS rigid'
- cat_02 SLC-5268/C3: errors=['weight_error'], AI 0.22 g vs true 0.1981 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_02 TSP-2351/C1: errors=['weight_error'], AI 2.91 g vs true 2.5559 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_02 NET-9289/C1: errors=['weight_error'], AI 7.37 g vs true 8.5951 g; AI cat 'Multi-material flexible laminate' vs 'Multi-material flexible laminate'
- cat_02 CVK-1424/C3: errors=['weight_error'], AI 0.54 g vs true 0.4846 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_02 WTK-2489/C2: errors=['weight_error'], AI 0.38 g vs true 0.4282 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_02 RTN-2531/C2: errors=['weight_error'], AI 1.76 g vs true 1.5896 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_04 CTL-5121/C2: errors=['weight_error'], AI 1.29 g vs true 1.4467 g; AI cat 'PVC rigid' vs 'PVC rigid'
- cat_04 BMH-9746/C2: errors=['weight_error'], AI 13.15 g vs true 15.3588 g; AI cat 'PE flexible' vs 'PE flexible'
- cat_04 GPL-1707/C3: errors=['weight_error'], AI 0.38 g vs true 0.3439 g; AI cat 'PP flexible' vs 'PP flexible'
- cat_05 NLP-3805/C1: errors=['weight_error'], AI 12.865 g vs true 14.4213 g; AI cat 'PET rigid' vs 'PET rigid'

## False positives (1) — first 15

- cat_15 HLM-7463/C2: fired=['physics_mass'], AI 1.048 g vs true 1.1513 g
