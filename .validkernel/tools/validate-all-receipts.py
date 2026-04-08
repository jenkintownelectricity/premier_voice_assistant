#!/usr/bin/env python3
"""ValidKernel Batch Receipt Validator v0.1

Discovers and validates all receipt files in .validkernel/receipts/.

Usage:
    python .validkernel/tools/validate-all-receipts.py [--receipts-dir <dir>] [--registry <path>]

Exit codes:
    0 — all receipts valid (or no receipts found)
    1 — one or more receipts invalid
"""

import argparse
import glob
import os
import subprocess
import sys

DEFAULT_RECEIPTS_DIR = ".validkernel/receipts"
DEFAULT_REGISTRY = ".validkernel/registry/command-registry.json"


def main():
    parser = argparse.ArgumentParser(description="Validate all VKG receipts")
    parser.add_argument(
        "--receipts-dir",
        default=DEFAULT_RECEIPTS_DIR,
        help=f"Directory containing receipt files (default: {DEFAULT_RECEIPTS_DIR})",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help=f"Path to command registry (default: {DEFAULT_REGISTRY})",
    )
    args = parser.parse_args()

    # Find validator script relative to this script's location
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    validator = os.path.join(tools_dir, "validate-receipt.py")

    if not os.path.exists(validator):
        print(f"ERROR: Validator not found at {validator}")
        return 1

    # Discover receipts
    pattern = os.path.join(args.receipts_dir, "*.receipt.json")
    receipts = sorted(glob.glob(pattern))

    if not receipts:
        print(f"No receipt files found in {args.receipts_dir}/")
        print("PASS: Nothing to validate.")
        return 0

    print(f"Found {len(receipts)} receipt(s) to validate.\n")

    failed = 0
    passed = 0

    for receipt_path in receipts:
        result = subprocess.run(
            [sys.executable, validator, receipt_path, "--registry", args.registry],
            capture_output=True, text=True,
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")

        if result.returncode != 0:
            failed += 1
        else:
            passed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(receipts)} total")

    if failed > 0:
        print("GOVERNANCE CHECK FAILED")
        return 1
    else:
        print("GOVERNANCE CHECK PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
