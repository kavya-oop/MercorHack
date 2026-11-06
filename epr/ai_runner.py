"""Send each catalog to an LLM in a FRESH, stateless request.

Isolation guarantees:
  * One HTTP request per catalog; no conversation history is sent or kept.
  * The request contains ONLY the task instructions (below) and spec.txt.
    ground_truth.json and the checker code are never read by this module.

Config (env vars or .env):
  EPR_PROVIDER = gemini (default)
  EPR_MODEL    = gemini-3.5-flash-lite (default)
  GEMINI_API_KEY

Manual mode: run `python -m epr.ai_runner --print-prompt cat_01` to get the
exact prompt, paste it into a NEW chat in any AI tool, and save the JSON reply
to data/ai_outputs/manual/cat_01.json. Then run the checker with
`--source manual`.
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

from . import categories

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


INSTRUCTIONS = """You are preparing a packaging Extended Producer Responsibility (EPR) report.

Read the packaging specification catalog below. For EVERY SKU and EVERY packaging
component (component IDs look like C1, C2, ...), report:
  - the materials/layers,
  - the material category (choose exactly one from the list below),
  - the packaging component's weight in grams (the packaging itself, NOT the product).

Compute weights from the spec: area x thickness x density for films/foils/rigid walls,
area x grammage for paper/coatings/adhesives, or the stated part weight when given.
Pouch and bag dimensions are per face (two faces); add gusset panels where given.

CATEGORY LIST (placeholder list for this exercise):
{categories}

CATEGORY RULES:
  - A material family counts as "significant" if it is >= 5% of the component's mass.
  - Vacuum metallization is ignored for category purposes; adhesives/coatings count only if >= 5%.
  - One significant family -> the matching mono-material category (rigid or flexible as appropriate;
    paper -> "Paper/paperboard"; any aluminium-only part -> "Aluminum").
  - Several significant families: if paper is > 50% of mass -> "Paper-based multi-material";
    otherwise flexible -> "Multi-material flexible laminate", rigid -> "Multi-material rigid".
  - Polyethylene rigid parts use "HDPE rigid".

Return ONLY JSON with this exact shape:
{{
  "items": [
    {{"sku": "ABC-1234", "component_id": "C1", "component": "short name",
      "layers": [{{"material": "PET", "form": "film|foil|metallization|paper|coating|adhesive|wall",
                   "thickness_um": 12.0, "grammage_gsm": null}}],
      "category": "<one category from the list>",
      "weight_g": 0.0}}
  ],
  "totals_by_category": {{"<category>": 0.0}},
  "total_weight_g": 0.0
}}

CATALOG:
"""


def build_prompt(spec_text):
    cats = "\n".join(f"  - {c}" for c in categories.CATEGORIES)
    return INSTRUCTIONS.format(categories=cats) + spec_text


def call_gemini(prompt, model, key, retries=6):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    delay = 15
    for attempt in range(retries):
        r = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                          json=body, timeout=600)
        if r.status_code in (429, 500, 503):
            print(f"   HTTP {r.status_code}; retrying in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        r.raise_for_status()
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts), data
    raise RuntimeError("Gemini: too many retries")


def extract_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    return json.loads(text)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("catalogs", nargs="*", help="catalog ids (default: all)")
    ap.add_argument("--print-prompt", action="store_true", help="manual mode: print prompt and exit")
    ap.add_argument("--force", action="store_true", help="re-run even if output exists")
    a = ap.parse_args()
    ids = a.catalogs or sorted(p.name for p in (ROOT / "data" / "catalogs").glob("cat_*"))
    provider = os.environ.get("EPR_PROVIDER", "gemini")
    model = os.environ.get("EPR_MODEL", "gemini-3.5-flash-lite")
    if a.print_prompt:
        for cid in ids:
            print(build_prompt((ROOT / "data" / "catalogs" / cid / "spec.txt").read_text()))
        return
    if provider != "gemini":
        raise SystemExit(f"Provider '{provider}' not implemented; use manual mode (--print-prompt).")
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set (use .env) - or use manual mode.")
    out = ROOT / "data" / "ai_outputs" / "gemini"
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        if (out / f"{cid}.json").exists() and not a.force:
            print(f"{cid}: exists, skipping")
            continue
        prompt = build_prompt((ROOT / "data" / "catalogs" / cid / "spec.txt").read_text())
        t0 = time.time()
        print(f"{cid}: calling {model} (fresh request) ...", flush=True)
        try:
            text, full = call_gemini(prompt, model, key)
        except (RuntimeError, requests.RequestException) as e:
            print(f"   FAILED: {e} - skipping; re-run later to fill gaps", flush=True)
            continue
        (raw / f"{cid}.txt").write_text(text)
        (raw / f"{cid}.meta.json").write_text(json.dumps(
            dict(model=model, provider=provider, seconds=round(time.time() - t0, 1),
                 usage=full.get("usageMetadata"), prompt_chars=len(prompt)), indent=2))
        try:
            parsed = extract_json(text)
            (out / f"{cid}.json").write_text(json.dumps(parsed, indent=1))
            print(f"   ok: {len(parsed.get('items', []))} items in {time.time() - t0:.0f}s")
        except json.JSONDecodeError as e:
            print(f"   WARNING: response was not valid JSON ({e}); raw text saved in {raw}")
        time.sleep(4)  # be gentle with free-tier rate limits


if __name__ == "__main__":
    main()
