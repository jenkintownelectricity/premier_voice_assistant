#!/usr/bin/env python3
"""
install-vkg.py — VKG Installer

Installs the ValidKernel Governance kernel from the current repository
into a target repository. Deterministic, fail-closed, standard library only.

Usage:
    python .validkernel/tools/install-vkg.py \
        --target-repo /path/to/target \
        [--force] \
        [--initialize-authority] \
        [--initialize-registry] \
        [--create-install-receipt]
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTALL_COMMAND_ID = "L0-CMD-VKG-INSTALL-001"

# Kernel paths to copy (relative to source repo root)
KERNEL_COPY_PATHS = [
    "docs/validkernel/",
    ".validkernel/",
    ".github/workflows/vkg-governance-check.yml",
]

# Directories that must exist in the target after install
REQUIRED_TARGET_DIRS = [
    "docs/validkernel",
    ".validkernel/authority",
    ".validkernel/registry",
    ".validkernel/receipts",
    ".validkernel/tools",
    ".github/workflows",
]

# Files that must exist in the target after install (post-install validation)
REQUIRED_POST_INSTALL = [
    "docs/validkernel/vkg-spec.md",
    "docs/validkernel/command-protocol.md",
    ".validkernel/tools/runtime-gate.py",
    ".validkernel/tools/validate-receipt.py",
    ".github/workflows/vkg-governance-check.yml",
]

# Paths that should not be copied to the target (installer itself, source-specific)
EXCLUDE_FROM_COPY = [
    ".validkernel/receipts/",
    ".validkernel/registry/",
    ".validkernel/authority/",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fail(msg):
    """Print FAIL message and exit with code 1."""
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg):
    print(f"  {msg}")


def is_git_repo(path):
    """Check if path is a git repository."""
    return os.path.isdir(os.path.join(path, ".git"))


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def copy_file_utf8(src, dst):
    """Copy a file preserving UTF-8 text safely. Binary files are copied as-is."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except (UnicodeDecodeError, ValueError):
        shutil.copy2(src, dst)


def should_exclude(rel_path):
    """Check if a relative path should be excluded from copying."""
    for excl in EXCLUDE_FROM_COPY:
        if rel_path.startswith(excl):
            return True
    return False


def collect_kernel_files(source_root):
    """Collect all files from kernel paths, respecting exclusions."""
    files = []
    for kpath in KERNEL_COPY_PATHS:
        full = os.path.join(source_root, kpath)
        if kpath.endswith("/"):
            # Directory — walk recursively
            if not os.path.isdir(full):
                fail(f"Required kernel source path missing: {kpath}")
            for dirpath, _dirnames, filenames in os.walk(full):
                for fname in filenames:
                    abs_path = os.path.join(dirpath, fname)
                    rel = os.path.relpath(abs_path, source_root)
                    if not should_exclude(rel):
                        files.append(rel)
        else:
            # Single file
            if not os.path.isfile(full):
                fail(f"Required kernel source path missing: {kpath}")
            files.append(kpath)
    return files


def check_overwrite_conflicts(target_root, files):
    """Return list of files that already exist in the target."""
    conflicts = []
    for rel in files:
        dst = os.path.join(target_root, rel)
        if os.path.exists(dst):
            conflicts.append(rel)
    return conflicts


# ---------------------------------------------------------------------------
# Main installer logic
# ---------------------------------------------------------------------------

def install(args):
    source_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    target_root = os.path.abspath(args.target_repo)

    print(f"VKG Installer")
    print(f"  Source: {source_root}")
    print(f"  Target: {target_root}")
    print()

    # --- Validate target ---
    if not os.path.isdir(target_root):
        fail(f"Target repo does not exist: {target_root}")

    if not is_git_repo(target_root):
        fail(f"Target path is not a git repository: {target_root}")

    # --- Collect files ---
    files = collect_kernel_files(source_root)
    info(f"Collected {len(files)} kernel file(s) to install.")

    # --- Check overwrite conflicts ---
    conflicts = check_overwrite_conflicts(target_root, files)
    if conflicts and not args.force:
        print()
        print("FAIL: Install would overwrite existing governance files.")
        print("  Conflicting files:")
        for c in conflicts:
            print(f"    - {c}")
        print()
        print("  Use --force to overwrite.")
        sys.exit(1)

    # --- Copy files ---
    copied = 0
    for rel in files:
        src = os.path.join(source_root, rel)
        dst = os.path.join(target_root, rel)
        copy_file_utf8(src, dst)
        copied += 1
    info(f"Copied {copied} file(s).")

    # --- Ensure required directories exist ---
    for d in REQUIRED_TARGET_DIRS:
        os.makedirs(os.path.join(target_root, d), exist_ok=True)

    # --- Authority handling ---
    authority_path = os.path.join(target_root, ".validkernel/authority/authority.json")
    authority_exists = os.path.exists(authority_path)

    if not authority_exists:
        if args.initialize_authority:
            authority_data = {
                "authority_version": "0.1",
                "authority_id": "VKG-AUTH-001",
                "authority_name": "",
                "organization": "",
                "governance_scope": "",
                "contact": ""
            }
            os.makedirs(os.path.dirname(authority_path), exist_ok=True)
            with open(authority_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(authority_data, f, indent=2)
                f.write("\n")
            info("Initialized authority.json (blank template).")
        else:
            info("No authority.json in target. Use --initialize-authority to create one.")
    else:
        if args.force and args.initialize_authority:
            info("authority.json already exists — overwritten (--force).")
            authority_data = {
                "authority_version": "0.1",
                "authority_id": "VKG-AUTH-001",
                "authority_name": "",
                "organization": "",
                "governance_scope": "",
                "contact": ""
            }
            with open(authority_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(authority_data, f, indent=2)
                f.write("\n")
        else:
            info("authority.json already exists — preserved.")

    # --- Registry handling ---
    registry_path = os.path.join(target_root, ".validkernel/registry/command-registry.json")
    registry_exists = os.path.exists(registry_path)
    target_name = os.path.basename(target_root)

    if not registry_exists:
        if args.initialize_registry:
            registry_data = {
                "registry_version": "0.1",
                "repository": target_name,
                "last_updated": utc_now_iso(),
                "commands": []
            }
            os.makedirs(os.path.dirname(registry_path), exist_ok=True)
            with open(registry_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(registry_data, f, indent=2)
                f.write("\n")
            info("Initialized command-registry.json.")
        else:
            info("No command-registry.json in target. Use --initialize-registry to create one.")
    else:
        if args.force and args.initialize_registry:
            registry_data = {
                "registry_version": "0.1",
                "repository": target_name,
                "last_updated": utc_now_iso(),
                "commands": []
            }
            with open(registry_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(registry_data, f, indent=2)
                f.write("\n")
            info("command-registry.json overwritten (--force).")
        else:
            info("command-registry.json already exists — preserved.")

    # --- Install receipt ---
    if args.create_install_receipt:
        receipt_path = os.path.join(
            target_root,
            f".validkernel/receipts/{INSTALL_COMMAND_ID}.receipt.json"
        )
        os.makedirs(os.path.dirname(receipt_path), exist_ok=True)
        now = utc_now_iso()
        receipt = {
            "receipt_version": "0.1",
            "command_id": INSTALL_COMMAND_ID,
            "authority": "",
            "organization": "",
            "issued_at": now[:10],
            "executed_at": now,
            "repository": target_name,
            "branch": "",
            "commit_hash": "",
            "status": "EXECUTED",
            "gate_result": "PASS",
            "files_changed": files,
            "summary": f"VKG kernel installed from source into {target_name}.",
            "blocked_reason": "",
            "next_action": "Configure authority.json and verify governance CI.",
            "signer": "agent",
            "signature_status": "UNSIGNED"
        }
        with open(receipt_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(receipt, f, indent=2)
            f.write("\n")
        info(f"Created install receipt: {INSTALL_COMMAND_ID}.receipt.json")

        # Update registry if it exists
        if os.path.exists(registry_path):
            with open(registry_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
            # Remove existing entry for this command if present
            reg["commands"] = [
                c for c in reg.get("commands", [])
                if c.get("command_id") != INSTALL_COMMAND_ID
            ]
            reg["commands"].append({
                "command_id": INSTALL_COMMAND_ID,
                "title": "VKG kernel installation",
                "authority": "",
                "organization": "",
                "date_issued": now[:10],
                "repository": target_name,
                "branch": "",
                "commit_hash": "",
                "status": "EXECUTED",
                "gate_result": "PASS",
                "receipt_path": f".validkernel/receipts/{INSTALL_COMMAND_ID}.receipt.json",
                "receipt_status": "CREATED",
                "supersedes": "",
                "superseded_by": "",
                "next_action": "Configure authority.json and verify governance CI.",
                "last_updated": now
            })
            reg["last_updated"] = now
            with open(registry_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(reg, f, indent=2)
                f.write("\n")
            info("Updated command-registry.json with install entry.")

    # --- Post-install validation ---
    print()
    missing = []
    for req in REQUIRED_POST_INSTALL:
        full = os.path.join(target_root, req)
        if not os.path.exists(full):
            missing.append(req)

    if missing:
        print("FAIL: Post-install validation failed.")
        print("  Missing required artifacts:")
        for m in missing:
            print(f"    - {m}")
        sys.exit(1)

    print(f"PASS: VKG kernel installed successfully into {target_root}")
    print(f"  Files installed: {copied}")
    print(f"  Post-install checks: {len(REQUIRED_POST_INSTALL)}/{len(REQUIRED_POST_INSTALL)} passed")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Install the ValidKernel Governance kernel into a target repository."
    )
    parser.add_argument(
        "--target-repo",
        required=True,
        help="Path to the target git repository."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing governance files in the target."
    )
    parser.add_argument(
        "--initialize-authority",
        action="store_true",
        default=False,
        help="Create a blank authority.json in the target if none exists."
    )
    parser.add_argument(
        "--initialize-registry",
        action="store_true",
        default=False,
        help="Create an empty command-registry.json in the target if none exists."
    )
    parser.add_argument(
        "--create-install-receipt",
        action="store_true",
        default=False,
        help="Create an install receipt in the target after successful install."
    )
    args = parser.parse_args()
    sys.exit(install(args))


if __name__ == "__main__":
    main()
