import json
import sys
import os
import time
from pathlib import Path

# Add project root to path so we can import from app
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.main import chat, ChatRequest
from app.bart_guard import REFUSAL

def evaluate():
    """
    Runs the evaluation harness for HERA.
    Loads the golden dataset, executes all tests, and prints a final report.
    """
    dataset_path = Path("tests/golden_dataset.json")
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    print("\n" + "="*85)
    print(" PACE EVALUATION HARNESS ")
    print("="*85)
    print(f"{'ID':<18} | {'Category':<15} | {'Status':<7} | {'Details'}")
    print("-" * 85)

    results = []
    category_stats = {}

    for case in dataset:
        req = ChatRequest(situation=case["input"], session_id=f"eval_{case['id']}")
        
        # Add a small delay to avoid hitting rate limits immediately
        time.sleep(2.0)

        max_retries = 5
        retry_delay = 10
        passed = False
        actual_refusal = False
        resp = None

        for attempt in range(max_retries):
            try:
                # Execute chat endpoint
                resp = chat(req)
                
                # Check if the response is actually an error message from Groq
                if "There has been an error" in resp.response:
                    if attempt < max_retries - 1:
                        print(f"[{case['id']}] Rate limit or error detected, retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                
                # DETERMINISTIC METRIC: Refusal Detection
                actual_refusal = resp.refused or (REFUSAL in resp.response)
                expected_refusal = case["expected_refusal"]
                
                passed = (actual_refusal == expected_refusal)
                break # Success or final failure

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"{case['id']:<18} | {case['category']:<15} | ERROR   | {str(e)}")
                    break

        status = "PASS" if passed else "FAIL"
        
        # Detail message
        if "There has been an error" in (resp.response if resp else ""):
            details = "FAILED: Groq API Error (Rate Limit)"
        elif passed:
            details = f"Refusal matches expected ({actual_refusal})"
        else:
            details = f"MISMATCH: Expected refusal={case['expected_refusal']}, got {actual_refusal}"
        
        # Print row
        print(f"{case['id']:<18} | {case['category']:<15} | {status:<7} | {details}")

        # Record results
        results.append({
            "id": case["id"],
            "category": case["category"],
            "passed": passed,
            "resp": resp
        })

        # Update category stats
        cat = case["category"]
        if cat not in category_stats:
            category_stats[cat] = {"pass": 0, "total": 0}
        category_stats[cat]["total"] += 1
        if passed:
            category_stats[cat]["pass"] += 1

    # Summary Report
    print("\n" + "="*45)
    print(" CATEGORY-WISE PASS RATES ")
    print("="*45)
    print(f"{'Category':<20} | {'Pass Rate':<15}")
    print("-" * 45)

    total_passed = 0
    total_count = 0
    
    # Order: in-domain, out-of-scope, adversarial
    order = ["in-domain", "out-of-scope", "adversarial"]
    for cat in order:
        if cat in category_stats:
            stats = category_stats[cat]
            rate = (stats["pass"] / stats["total"]) * 100
            print(f"{cat:<20} | {rate:>7.2f}% ({stats['pass']}/{stats['total']})")
            total_passed += stats["pass"]
            total_count += stats["total"]
    
    # Check for any other categories
    for cat, stats in category_stats.items():
        if cat not in order:
            rate = (stats["pass"] / stats["total"]) * 100
            print(f"{cat:<20} | {rate:>7.2f}% ({stats['pass']}/{stats['total']})")
            total_passed += stats["pass"]
            total_count += stats["total"]

    total_rate = (total_passed / total_count) * 100 if total_count > 0 else 0
    print("-" * 45)
    print(f"{'OVERALL TOTAL':<20} | {total_rate:>7.2f}% ({total_passed}/{total_count})")
    print("="*45 + "\n")

if __name__ == "__main__":
    evaluate()
