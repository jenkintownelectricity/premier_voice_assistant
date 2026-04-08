#!/usr/bin/env python3
"""ValidKernel Governance Record Updater v0.1

Creates or updates VKG receipt and registry entries after a governed command completes.

Usage:
    python .validkernel/tools/update-governance-record.py \
        --command-id L0-CMD-EXAMPLE-001 \
        --title "Example Command" \
        --status EXECUTED \
        --gate-result PASS \
        --summary "Example completed."

Exit codes:
    0 — success
    1 — error
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

TEMPLATE_PATH = "docs/validkernel/templates/command-receipt.template.json"
RECEIPTS_DIR = ".validkernel/receipts"
REGISTRY_PATH = ".validkernel/registry/command-registry.json"


def get_git_branch():
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_repo_name():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return os.path.basename(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def create_or_update_receipt(args):
    receipt_path = os.path.join(RECEIPTS_DIR, f"{args.command_id}.receipt.json")

    # Load existing receipt or template
    if os.path.exists(receipt_path):
        receipt = load_json(receipt_path)
        print(f"Updating existing receipt: {receipt_path}")
    elif os.path.exists(TEMPLATE_PATH):
        receipt = load_json(TEMPLATE_PATH)
        print(f"Creating new receipt from template: {receipt_path}")
    else:
        receipt = {}
        print(f"Creating new receipt (no template found): {receipt_path}")

    # Populate fields
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt["receipt_version"] = "0.1"
    receipt["command_id"] = args.command_id
    receipt["repository"] = get_repo_name()
    receipt["branch"] = get_git_branch()
    receipt["commit_hash"] = get_git_commit()
    receipt["executed_at"] = now

    if args.authority:
        receipt["authority"] = args.authority
    if args.organization:
        receipt["organization"] = args.organization
    if args.date_issued:
        receipt["issued_at"] = args.date_issued
    if args.status:
        receipt["status"] = args.status
    if args.gate_result:
        receipt["gate_result"] = args.gate_result
    if args.summary:
        receipt["summary"] = args.summary
    if args.blocked_reason is not None:
        receipt["blocked_reason"] = args.blocked_reason
    if args.next_action is not None:
        receipt["next_action"] = args.next_action

    # Set defaults for optional fields if creating new
    receipt.setdefault("signer", "agent")
    receipt.setdefault("signature_status", "REPO_VERIFIED")
    receipt.setdefault("files_changed", [])
    receipt.setdefault("blocked_reason", "")
    receipt.setdefault("next_action", "")

    write_json(receipt_path, receipt)
    print(f"Receipt written: {receipt_path}")
    return receipt_path


def update_registry(args, receipt_path):
    # Load or create registry
    if os.path.exists(REGISTRY_PATH):
        registry = load_json(REGISTRY_PATH)
    else:
        registry = {
            "registry_version": "0.1",
            "repository": get_repo_name(),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commands": [],
        }

    commands = registry.get("commands", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Find existing entry
    existing = None
    for cmd in commands:
        if cmd.get("command_id") == args.command_id:
            existing = cmd
            break

    if existing:
        print(f"Updating existing registry entry: {args.command_id}")
        entry = existing
    else:
        print(f"Appending new registry entry: {args.command_id}")
        entry = {}
        commands.append(entry)

    # Populate entry fields
    entry["command_id"] = args.command_id
    if args.title:
        entry["title"] = args.title
    if args.authority:
        entry["authority"] = args.authority
    if args.organization:
        entry["organization"] = args.organization
    if args.date_issued:
        entry["date_issued"] = args.date_issued

    entry["repository"] = get_repo_name()
    entry["branch"] = get_git_branch()
    entry["commit_hash"] = get_git_commit()

    if args.status:
        entry["status"] = args.status
    if args.gate_result:
        entry["gate_result"] = args.gate_result

    entry["receipt_path"] = receipt_path
    entry.setdefault("receipt_status", "REPO_VERIFIED")

    if args.supersedes is not None:
        entry["supersedes"] = args.supersedes
        # Update the superseded entry
        for cmd in commands:
            if cmd.get("command_id") == args.supersedes:
                cmd["superseded_by"] = args.command_id
                cmd["status"] = "SUPERSEDED"
                break

    if args.superseded_by is not None:
        entry["superseded_by"] = args.superseded_by

    entry.setdefault("supersedes", "")
    entry.setdefault("superseded_by", "")

    if args.next_action is not None:
        entry["next_action"] = args.next_action
    entry.setdefault("next_action", "")

    entry["last_updated"] = now

    # Update registry metadata
    registry["last_updated"] = now
    registry["commands"] = commands

    write_json(REGISTRY_PATH, registry)
    print(f"Registry updated: {REGISTRY_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Create or update VKG receipt and registry entries"
    )
    parser.add_argument("--command-id", required=True, help="Command ID")
    parser.add_argument("--title", default="", help="Command title")
    parser.add_argument("--authority", default="Armand Lefebvre", help="Authority name")
    parser.add_argument(
        "--organization",
        default="Lefebvre Design Solutions LLC",
        help="Organization name",
    )
    parser.add_argument("--date-issued", default="", help="Date issued (YYYY-MM-DD)")
    parser.add_argument(
        "--status",
        choices=["EXECUTED", "BLOCKED", "PARTIAL", "SUPERSEDED"],
        default="EXECUTED",
        help="Execution status",
    )
    parser.add_argument(
        "--gate-result",
        choices=["PASS", "FAIL", "NOT_EVALUATED"],
        default="PASS",
        help="Gate result",
    )
    parser.add_argument("--summary", default="", help="Execution summary")
    parser.add_argument("--blocked-reason", default="", help="Reason if blocked")
    parser.add_argument("--next-action", default="", help="Recommended next action")
    parser.add_argument("--supersedes", default=None, help="Command ID this supersedes")
    parser.add_argument(
        "--superseded-by", default=None, help="Command ID that supersedes this"
    )

    args = parser.parse_args()

    try:
        receipt_path = create_or_update_receipt(args)
        update_registry(args, receipt_path)
        print(f"\nDone. Receipt and registry updated for {args.command_id}.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
