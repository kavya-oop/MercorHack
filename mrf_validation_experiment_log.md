# Material Recovery Facility (MRF) AI Verification Experiment Log

This document records experimental test cases for verifying LLM/Vision model sorting outputs against our deterministic physical and thermodynamic validation engine.

---

## Executive Summary

| Total Test Cases | Model Passes | Model Failures Caught | Primary Error Types Identified |
| :--- | :--- | :--- | :--- |
| **0** | 0 | 0 | *e.g., Hidden Inclusion, Thermal Delta Violation* |

---

## Summary Results Table

| ID | Item Description | Input Metadata Summary | LLM Proposed Route | True Validator Route | Verification Status | Violation Type |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| `TC-01` | *e.g., Black 3D print with brass insert* | `PLA`, `brass insert`, `45g` | *Clean PLA Extrusion* | *Metal Rec. / Contamination* | 🔴 **FAIL** | *Hidden Metal Inclusion* |
| `TC-02` | | | | | 🟢 **PASS** | *None* |
| `TC-03` | | | | | 🔴 **FAIL** | |
| `TC-04` | | | | | 🔴 **FAIL** | |
| `TC-05` | | | | | 🟢 **PASS** | *None* |

---

## Detailed Test Case Breakdown

### Test Case `TC-01`: [Insert Item Name/Title]

#### 1. Input Test Data (JSON Payload)
```json
{
  "item_id": "TC-01",
  "description": "",
  "metadata": {
    "primary_material": "",
    "secondary_materials": [],
    "has_metal_inclusion": false,
    "composite_blend": false,
    "weight_grams": 0,
    "max_dimension_mm": 0,
    "glass_transition_temp_c": 0,
    "melt_temp_c": 0
  }
}
```

#### 2. LLM / Vision Model Output
* **Model Used:** `[e.g., Claude 3.5 Sonnet / GPT-4o]`
* **Prompt/Query Date:** `[YYYY-MM-DD]`
* **Raw Model Route Output:**
  ```json
  {
    "proposed_destination": "",
    "stage_checkpoints": {
      "stage_1_trommel": "",
      "stage_2_magnetic": "",
      "stage_3_eddy_current": "",
      "stage_4_optical_nir": ""
    },
    "model_confidence": 0.0,
    "reasoning": ""
  }
  ```

#### 3. Deterministic Validator Output
* **True Target Route:** `[Insert Ground Truth Bin]`
* **Validation Status:** `[PASS / FAIL]`
* **Checkpoints Evaluated:**
  - [ ] Stage 1 (Trommel Screen Size Check): `[PASS / FAIL]`
  - [ ] Stage 2 (Ferrous Metal Check): `[PASS / FAIL]`
  - [ ] Stage 3 (Eddy-Current Non-Ferrous Check): `[PASS / FAIL]`
  - [ ] Stage 4 (Optical NIR & Polymer Compatibility Check): `[PASS / FAIL]`
* **Rule Engine Flags:**
  > *`[Insert diagnostic error or success output from Python validator]`*

---

### Test Case `TC-02`: [Insert Item Name/Title]

#### 1. Input Test Data (JSON Payload)
```json
{
  "item_id": "TC-02",
  "description": "",
  "metadata": {
    "primary_material": "",
    "secondary_materials": [],
    "has_metal_inclusion": false,
    "composite_blend": false,
    "weight_grams": 0,
    "max_dimension_mm": 0,
    "glass_transition_temp_c": 0,
    "melt_temp_c": 0
  }
}
```

#### 2. LLM / Vision Model Output
* **Model Used:** `[e.g., Claude 3.5 Sonnet / GPT-4o]`
* **Prompt/Query Date:** `[YYYY-MM-DD]`
* **Raw Model Route Output:**
  ```json
  {
    "proposed_destination": "",
    "stage_checkpoints": {
      "stage_1_trommel": "",
      "stage_2_magnetic": "",
      "stage_3_eddy_current": "",
      "stage_4_optical_nir": ""
    },
    "model_confidence": 0.0,
    "reasoning": ""
  }
  ```

#### 3. Deterministic Validator Output
* **True Target Route:** `[Insert Ground Truth Bin]`
* **Validation Status:** `[PASS / FAIL]`
* **Checkpoints Evaluated:**
  - [ ] Stage 1 (Trommel Screen Size Check): `[PASS / FAIL]`
  - [ ] Stage 2 (Ferrous Metal Check): `[PASS / FAIL]`
  - [ ] Stage 3 (Eddy-Current Non-Ferrous Check): `[PASS / FAIL]`
  - [ ] Stage 4 (Optical NIR & Polymer Compatibility Check): `[PASS / FAIL]`
* **Rule Engine Flags:**
  > *`[Insert diagnostic error or success output from Python validator]`*

---

## Cumulative Batch Contamination Tracker

This section tracks the stateful batch accumulator as items are processed sequentially.

* **Target Batch:** Clean PLA Filament Reclamation Stream
* **Maximum Allowed Contamination Threshold:** $1.5\%$ by weight

| Item ID | Weight (g) | Contaminant Weight (g) | Cumulative Contamination (%) | Batch Status |
| :---: | :---: | :---: | :---: | :---: |
| `TC-01` | 45 | 5 | 11.1% | 🔴 **BATCH REJECTED (CASCADE OVERRIDE)** |
| `TC-02` | | | | |
| `TC-03` | | | | |

---

## Key Findings & Failure Modes Captured

1. **Surface-Level Classification Hallucinations:**
   * *Observation:* 
2. **Thermal Degradation / Poly-Blend Oversights:**
   * *Observation:*
3. **Downstream Batch Cascade Vulnerabilities:**
   * *Observation:*