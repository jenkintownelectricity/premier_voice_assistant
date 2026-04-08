#!/usr/bin/env python3
"""ValidKernel Receipt Validator v0.1

Validates a command receipt against VKG v0.1 requirements.

Usage:
    python .validkernel/tools/validate-receipt.py <receipt-path> [--registry <registry-path>]

Exit codes:
    0 — valid receipt
    1 — invalid receipt
    2 — usage error
"""

import argparse
import json
import os
import sys

REQUIRED_FIELDS = [
    "receipt_version",
    "command_id",
    "authority",
    "organization",
    "issued_at",
    "executed_at",
    "repository",
    "branch",
    "commit_hash",
    "status",
    "gate_result",
    "files_changed",
    "summary",
    "blocked_reason",
    "next_action",
    "signer",
    "signature_status",
]

VALID_STATUS = {"EXECUTED", "BLOCKED", "PARTIAL", "SUPERSEDED"}
VALID_GATE_RESULT = {"PASS", "FAIL", "NOT_EVALUATED"}

DEFAULT_REGISTRY = ".validkernel/registry/command-registry.json"


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def validate_receipt(receipt_path, registry_path):
    errors = []

    # Load receipt
    try:
        receipt = load_json(receipt_path)
    except FileNotFoundError:
        print(f"FAIL: Receipt file not found: {receipt_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"FAIL: Receipt is not valid JSON: {e}")
        return 1

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in receipt:
            errors.append(f"Missing required field: {field}")

    # Check status value
    status = receipt.get("status", "")
    if status and status not in VALID_STATUS:
        errors.append(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUS))}")

    # Check gate_result value
    gate_result = receipt.get("gate_result", "")
    if gate_result and gate_result not in VALID_GATE_RESULT:
        errors.append(f"Invalid gate_result '{gate_result}'. Must be one of: {', '.join(sorted(VALID_GATE_RESULT))}")

    # Check files_changed is a list
    files_changed = receipt.get("files_changed")
    if files_changed is not None and not isinstance(files_changed, list):
        errors.append("files_changed must be a list")

    # Registry cross-checks
    command_id = receipt.get("command_id", "")
    registry = None
    if os.path.exists(registry_path):
        try:
            registry = load_json(registry_path)
        except (json.JSONDecodeError, FileNotFoundError):
            errors.append(f"Registry file exists but cannot be parsed: {registry_path}")

    if registry and command_id:
        commands = registry.get("commands", [])
        entry = None
        for cmd in commands:
            if cmd.get("command_id") == command_id:
                entry = cmd
                break

        if entry is None:
            errors.append(f"command_id '{command_id}' not found in registry")
        else:
            # Check branch agreement
            receipt_branch = receipt.get("branch", "")
            registry_branch = entry.get("branch", "")
            if receipt_branch and registry_branch and receipt_branch != registry_branch:
                errors.append(
                    f"Branch mismatch: receipt='{receipt_branch}', registry='{registry_branch}'"
                )

            # Check commit_hash agreement
            receipt_commit = receipt.get("commit_hash", "")
            registry_commit = entry.get("commit_hash", "")
            if receipt_commit and registry_commit and receipt_commit != registry_commit:
                errors.append(
                    f"Commit hash mismatch: receipt='{receipt_commit}', registry='{registry_commit}'"
                )

            # Check receipt_path in registry matches actual path
            registry_receipt_path = entry.get("receipt_path", "")
            if registry_receipt_path:
                actual_basename = os.path.basename(receipt_path)
                registry_basename = os.path.basename(registry_receipt_path)
                if actual_basename != registry_basename:
                    errors.append(
                        f"Receipt path mismatch: actual='{actual_basename}', registry='{registry_basename}'"
                    )
    elif not os.path.exists(registry_path):
        errors.append(f"Registry not found at: {registry_path}")

    # Report results
    if errors:
        print(f"FAIL: {receipt_path}")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print(f"PASS: {receipt_path}")
        print(f"  command_id: {command_id}")
        print(f"  status: {status}")
        print(f"  gate_result: {gate_result}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Validate a VKG command receipt")
    parser.add_argument("receipt", help="Path to the receipt JSON file")
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help=f"Path to command registry (default: {DEFAULT_REGISTRY})",
    )
    args = parser.parse_args()

    sys.exit(validate_receipt(args.receipt, args.registry))


if __name__ == "__main__":
    main()
