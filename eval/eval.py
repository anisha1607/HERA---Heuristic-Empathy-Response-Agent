from __future__ import annotations
import json
import os
from typing import Any, Dict, List

import requests

REFUSAL_PHRASE = "I am an empathy coach"

# OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
# JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("LLAMA_MODEL", "llama3.1:8b-instruct"))
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))

def call_app(situation: str) -> Dict[str, Any]:
    resp = requests.post("http://localhost:8000/chat", json={"situation": situation}, timeout=180)
    resp.raise_for_status()
    return resp.json()

def deterministic_refusal_check(expected_refusal: bool, response_text: str) -> bool:
    if expected_refusal:
        return REFUSAL_PHRASE.lower() in response_text.lower()
    return REFUSAL_PHRASE.lower() not in response_text.lower()

def deterministic_structure_check(response_text: str) -> bool:
    lower = response_text.lower()
    return all(tag in lower for tag in ["a)", "b)", "c)", "d)"])

def judge_with_groq(golden: str, actual: str) -> Dict[str, Any]:
    prompt = f"""You are a strict evaluator. Compare ACTUAL to GOLDEN.
Return ONLY valid JSON with keys: golden_match, empathy, notes.

Rubric:
- golden_match: 1 (very different/wrong) to 5 (very close: same intent + same A-D structure)
- empathy: 1 (judgmental/harsh) to 5 (high empathy, NVC-aligned, non-judgment)

GOLDEN:
{golden}

ACTUAL:
{actual}
""".strip()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"golden_match": 1, "empathy": 1, "notes": "Missing GROQ_API_KEY for judge."}

    url = f"{GROQ_BASE_URL}/chat/completions"
    payload = {
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": "You are an evaluator. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 250,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=180)
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(text)
    except Exception:
        return {"golden_match": 1, "empathy": 1, "notes": f"Non-JSON judge output: {text[:160]}"}

# def judge_with_ollama(golden: str, actual: str) -> Dict[str, Any]:
#     prompt = f"""You are a strict evaluator. Compare ACTUAL to GOLDEN.
# Return ONLY valid JSON with keys: golden_match, empathy, notes.

# Rubric:
# - golden_match: 1 (very different/wrong) to 5 (very close: same intent + same A-D structure)
# - empathy: 1 (judgmental/harsh) to 5 (high empathy, NVC-aligned, non-judgment)

# GOLDEN:
# {golden}

# ACTUAL:
# {actual}
# """.strip()

#     url = f"{GROQ_BASE_URL}/api/chat"
#     payload = {
#         "model": JUDGE_MODEL,
#         "messages": [
#             {"role": "system", "content": "You are an evaluator. Output JSON only."},
#             {"role": "user", "content": prompt},
#         ],
#         "options": {"temperature": 0.0, "num_predict": 250},
#         "stream": False,
#     }
#     resp = requests.post(url, json=payload, timeout=180)
#     resp.raise_for_status()
#     text = resp.json()["message"]["content"].strip()

#     try:
#         return json.loads(text)
#     except Exception:
#         return {"golden_match": 1, "empathy": 1, "notes": f"Non-JSON judge output: {text[:160]}"}

def main():
    cases = json.loads(open("eval/test_cases.json", "r", encoding="utf-8").read())

    totals = {}
    det_pass = {}
    struct_pass = 0
    judge_golden: List[int] = []
    judge_empathy: List[int] = []

    print("Running eval...\n")
    for c in cases:
        cat = c["category"]
        totals[cat] = totals.get(cat, 0) + 1
        det_pass[cat] = det_pass.get(cat, 0)

        out = call_app(c["situation"])
        resp = out["response"]

        det_ok = deterministic_refusal_check(c["expected_refusal"], resp)
        if det_ok:
            det_pass[cat] += 1

        if cat == "in_domain" and not c["expected_refusal"]:
            if deterministic_structure_check(resp):
                struct_pass += 1

        # MaaJ: run on in-domain cases (golden present)
        if cat == "in_domain" and not c["expected_refusal"]:
            j = judge_with_groq(c["golden"], resp)
            judge_golden.append(int(j.get("golden_match", 1)))
            judge_empathy.append(int(j.get("empathy", 1)))

        print(f"{c['id']} | {cat} | refused={out['refused']} | guard={out['guard_label']}({out['guard_confidence']:.2f}) | det_ok={det_ok}")

    print("\n=== PASS RATES (Deterministic) ===")
    for cat, total in totals.items():
        print(f"{cat}: {det_pass[cat]}/{total} = {det_pass[cat]/total:.2%}")

    if totals.get("in_domain", 0) > 0:
        print(f"Structure (in_domain): {struct_pass}/{totals['in_domain']} = {struct_pass/totals['in_domain']:.2%}")

    if judge_golden:
        avg_g = sum(judge_golden)/len(judge_golden)
        avg_e = sum(judge_empathy)/len(judge_empathy)
        print(f"\nMaaJ avg golden_match: {avg_g:.2f}/5 over {len(judge_golden)} cases")
        print(f"MaaJ avg empathy:      {avg_e:.2f}/5 over {len(judge_empathy)} cases")

if __name__ == "__main__":
    main()
