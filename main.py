"""Person C — I/O harness. Run with: python main.py

Reads input/EC_*.json, calls the three agents in order, verifies, writes
output/output/EC_*.json, and appends one line per case to logging/trace.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from src.agents.coordinator import coordinate_case
from src.agents.verifier import verify_case
from src.shared.data_loader import get_data_store
from src.shared.config import (
    FRAMEWORK,
    MODEL_NAME,
    MODEL_PARAM_SIZE,
    MODEL_PROVIDER,
    POLICY_VERSION,
    RUNTIME,
)

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output" / "output"
TRACE_PATH = ROOT / "logging" / "trace.jsonl"
METADATA_PATH = ROOT / "logging" / "metadata.json"
SUBMISSION_ZIP_PATH = ROOT / "output" / "output.zip"
EXPECTED_CASE_NAMES = tuple(f"EC_{index:03d}.json" for index in range(1, 51))


def run_case(case_path: Path, store, trace_lines: list[str]) -> dict | None:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    expected_case_id = case_path.stem
    if case.get("case_id") != expected_case_id:
        raise ValueError(
            f"{case_path.name}: case_id must be {expected_case_id!r}, got {case.get('case_id')!r}"
        )
    if case.get("policy_version") != POLICY_VERSION:
        raise ValueError(
            f"{case_path.name}: unsupported policy_version {case.get('policy_version')!r}"
        )

    output, fulfillment, payment = coordinate_case(case)

    problems = verify_case(output, store)
    trace_lines.append(
        json.dumps(
            {
                "case_id": case["case_id"],
                "steps": [
                    {"agent": "fulfillment_agent", "output": fulfillment},
                    {"agent": "payment_agent", "output": payment},
                    {"agent": "coordinator", "output": output},
                    {"agent": "verifier", "problems": problems},
                ],
            },
            ensure_ascii=False,
        )
    )

    if problems:
        print(f"[{case['case_id']}] FAILED verification: {problems}")
        return None

    return output


def _write_metadata() -> None:
    metadata = {
        "model": MODEL_NAME,
        "provider": MODEL_PROVIDER,
        "parameter_size": MODEL_PARAM_SIZE,
        "framework": FRAMEWORK,
        "runtime": RUNTIME,
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_submission_zip(output_paths: list[Path]) -> None:
    with ZipFile(SUBMISSION_ZIP_PATH, "w", compression=ZIP_DEFLATED) as archive:
        for output_path in output_paths:
            archive.write(output_path, arcname=f"output/{output_path.name}")


def main() -> None:
    store = get_data_store()
    trace_lines: list[str] = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    case_paths = sorted(INPUT_DIR.glob("EC_*.json"))
    actual_case_names = tuple(path.name for path in case_paths)
    if actual_case_names != EXPECTED_CASE_NAMES:
        missing = sorted(set(EXPECTED_CASE_NAMES) - set(actual_case_names))
        extra = sorted(set(actual_case_names) - set(EXPECTED_CASE_NAMES))
        raise RuntimeError(f"input set mismatch: missing={missing}, extra={extra}")
    print(f"Found {len(case_paths)} input cases")

    ok, failed = 0, 0
    generated_outputs: list[tuple[Path, dict]] = []
    for case_path in case_paths:
        output = run_case(case_path, store, trace_lines)
        if output is None:
            failed += 1
            continue
        generated_outputs.append((OUTPUT_DIR / case_path.name, output))
        ok += 1

    TRACE_PATH.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
    _write_metadata()

    if failed or ok != len(EXPECTED_CASE_NAMES):
        raise RuntimeError(
            f"refusing to write submission: {ok} passed, {failed} failed verification"
        )

    unexpected_entries = sorted(
        path.name
        for path in OUTPUT_DIR.iterdir()
        if path.name not in EXPECTED_CASE_NAMES
    )
    if unexpected_entries:
        raise RuntimeError(f"unexpected entries in output directory: {unexpected_entries}")

    output_paths: list[Path] = []
    for out_path, output in generated_outputs:
        out_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        output_paths.append(out_path)

    final_names = tuple(path.name for path in sorted(OUTPUT_DIR.glob("EC_*.json")))
    if final_names != EXPECTED_CASE_NAMES:
        raise RuntimeError(f"output set mismatch after write: {final_names}")

    _write_submission_zip(output_paths)
    print(f"Done: {ok} written, {failed} failed verification.")
    print(f"Submission zip: {SUBMISSION_ZIP_PATH}")


if __name__ == "__main__":
    main()
