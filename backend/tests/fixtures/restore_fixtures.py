"""Verification and restoration utility for immutable historical raw test fixtures.

Ensures the canonical raw PDF archives required by historical regression tests
exist at the exact paths expected by SourceVersion.local_path with exact SHA-256 hashes.
"""

import hashlib
import sys
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

HISTORICAL_FIXTURES = {
    "data/raw/comedk/2026/cutoff/2025-Engineering_Cut-Off_Ranks-After-All-Rounds._Notified-on-07.07.2026.pdf": {
        "expected_sha256": "051ffd4a13148052b811cbe18c6dbc700195a5d88c001205e03d79af4eedce1f",
        "expected_size": 673165,
        "academic_year": 2025,
        "source_version_id": "92eda924-2802-4501-8ad3-682db2ec75d1",
        "description": "2025 Engineering Cutoff After All Rounds (canonical 2025 fixture)",
    },
    "data/raw/comedk/comedk/2024/cutoff/Round1_Cutoff_Ranks_after_Engineering_Allotment_Notified_on_12_07_2024.pdf": {
        "expected_sha256": "51eee72a21c08e44d80aa8ab8865fd4e7fe4acd6d2abed23f50918a4401a86db",
        "expected_size": 811003,
        "academic_year": 2024,
        "source_version_id": "f0628231-76c2-4ab2-b92a-0e2a3a6b2329",
        "description": "2024 Engineering Round 1 Cutoff (canonical 2024 fixture)",
    },
}


def verify_or_restore_fixtures(root: Path = REPO_ROOT) -> bool:
    print(f"Checking historical raw test fixtures against repository root: {root}")
    all_ok = True

    for rel_path_str, meta in HISTORICAL_FIXTURES.items():
        file_path = root / Path(rel_path_str)
        desc = meta["description"]
        expected_hash = meta["expected_sha256"]
        expected_size = meta["expected_size"]

        if not file_path.exists():
            print(f"ERROR: Missing historical raw fixture: {file_path}", file=sys.stderr)
            print(f"       Required for: {desc}", file=sys.stderr)
            all_ok = False
            continue

        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            print(
                f"ERROR: Size mismatch for {file_path}: expected {expected_size} bytes, got {actual_size}",
                file=sys.stderr,
            )
            all_ok = False
            continue

        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            print(
                f"ERROR: SHA-256 mismatch for {file_path}:\n  expected: {expected_hash}\n  actual:   {actual_hash}",
                file=sys.stderr,
            )
            all_ok = False
            continue

        print(f"  OK: {rel_path_str} ({actual_size:,} bytes, sha256={actual_hash[:16]}...)")

    if all_ok:
        print("All historical raw test fixtures verified successfully.")
    else:
        print("Historical fixture verification failed.", file=sys.stderr)

    return all_ok


if __name__ == "__main__":
    target_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO_ROOT
    success = verify_or_restore_fixtures(target_root)
    sys.exit(0 if success else 1)
