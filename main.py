"""Person C — I/O harness. Run with: python main.py

Reads input/EC_*.json, calls the three agents in order, verifies, writes
output/output/EC_*.json, and appends one line per case to logging/trace.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.coordinator import coordinate_case
from src.agents.verifier import verify_case
from src.shared.data_loader import get_data_store

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output" / "output"
TRACE_PATH = ROOT / "logging" / "trace.jsonl"


def run_case(case_path: Path, store, trace_lines: list[str]) -> dict | None:
    case = json.loads(case_path.read_text(encoding="utf-8"))

    output, fulfillment, payment = coordinate_case(case)

    trace_lines.append(json.dumps({
        "case_id": case["case_id"], "step": "fulfillment_agent", "output": fulfillment,
    }))

    trace_lines.append(json.dumps({
        "case_id": case["case_id"], "step": "payment_agent", "output": payment,
    }))

    trace_lines.append(json.dumps({
        "case_id": case["case_id"], "step": "coordinator", "output": output,
    }))

    problems = verify_case(output, store)
    trace_lines.append(json.dumps({
        "case_id": case["case_id"], "step": "verifier", "problems": problems,
    }))

    if problems:
        print(f"[{case['case_id']}] FAILED verification: {problems}")
        return None

    return output


def main() -> None:
    store = get_data_store()
    trace_lines: list[str] = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    case_paths = sorted(INPUT_DIR.glob("EC_*.json"))
    print(f"Found {len(case_paths)} input cases")

    ok, failed = 0, 0
    for case_path in case_paths:
        output = run_case(case_path, store, trace_lines)
        if output is None:
            failed += 1
            continue
        out_path = OUTPUT_DIR / case_path.name
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        ok += 1

    TRACE_PATH.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
    print(f"Done: {ok} written, {failed} failed verification.")


if __name__ == "__main__":
    main()
