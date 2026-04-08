#!/usr/bin/env python3
"""ValidKernel Runtime Gate (VKRT) v0.1

Evaluates whether a governed command is structurally valid and permitted
to proceed before execution.

Usage:
    python .validkernel/tools/runtime-gate.py <command-file> [--json]

Exit codes:
    0 — PASS (command satisfies VKRT structural requirements)
    1 — FAIL (command rejected by VKRT)
    2 — usage error
"""

import argparse
import json
import re
import sys

# Ensure UTF-8 console output (prevents Windows encoding issues)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- Check definitions ---

AUTHORITY_CHECKS = [
    ("Authority", r"(?i)authority\s*:"),
    ("Organization", r"(?i)organization\s*:"),
    ("Document ID", r"(?i)document\s+id\s*:"),
    ("Date", r"(?i)date\s*:"),
    ("Scope", r"(?i)scope\s*:"),
]

RING_CHECKS = [
    ("L0 — Governance Context", r"L0\s*[\-—]+\s*GOVERNANCE\s+CONTEXT"),
    ("Ring 1 — Mission Directive", r"RING\s+1\s*[\-—]+\s*MISSION\s+DIRECTIVE"),
    ("Ring 2 — Deterministic Commit Gate", r"RING\s+2\s*[\-—]+\s*DETERMINISTIC\s+COMMIT\s+GATE"),
    ("Ring 3 — Capability Bound", r"RING\s+3\s*[\-—]+\s*CAPABILITY\s+BOUND"),
    ("End Command", r"END\s+COMMAND"),
]

MISSION_CHECKS = [
    ("Objective", r"(?i)(?:^|\n)\s*objective\b"),
    ("Required Outcomes", r"(?i)required\s+outcomes"),
]

GATE_CHECKS = [
    ("Validation Checklist", r"(?i)validation\s+checklist"),
    ("Gate Rule", r"(?i)gate\s+rule"),
]

CAPABILITY_CHECKS = [
    ("TOUCH-ALLOWED", r"TOUCH-ALLOWED"),
    ("NO-TOUCH", r"NO-TOUCH"),
]


def evaluate_command(content):
    """Evaluate command content against VKRT structural requirements.

    Returns (passed: bool, results: list of (name, group, passed: bool))
    """
    results = []
    all_passed = True

    check_groups = [
        ("Authority / L0", AUTHORITY_CHECKS),
        ("Ring Structure", RING_CHECKS),
        ("Mission", MISSION_CHECKS),
        ("Gate", GATE_CHECKS),
        ("Capability", CAPABILITY_CHECKS),
    ]

    for group_name, checks in check_groups:
        for name, pattern in checks:
            found = bool(re.search(pattern, content))
            results.append((name, group_name, found))
            if not found:
                all_passed = False

    return all_passed, results


def format_text_output(passed, results, filepath):
    """Format human-readable CLI output."""
    lines = []

    if passed:
        lines.append(f"PASS: {filepath}")
        lines.append("  command satisfies VKRT structural requirements")
        lines.append("")
        lines.append(f"  Checks passed: {len(results)}/{len(results)}")
    else:
        failures = [(name, group) for name, group, ok in results if not ok]
        lines.append(f"FAIL: {filepath}")
        lines.append("  command rejected by VKRT")
        for name, group in failures:
            lines.append(f"  - missing {name} ({group})")
        lines.append("")
        passed_count = sum(1 for _, _, ok in results if ok)
        lines.append(f"  Checks passed: {passed_count}/{len(results)}")

    return "\n".join(lines)


def format_json_output(passed, results, filepath):
    """Format structured JSON output."""
    output = {
        "file": filepath,
        "gate_result": "PASS" if passed else "FAIL",
        "checks_passed": sum(1 for _, _, ok in results if ok),
        "checks_total": len(results),
        "results": [
            {"name": name, "group": group, "passed": ok}
            for name, group, ok in results
        ],
    }
    if not passed:
        output["failures"] = [
            {"name": name, "group": group}
            for name, group, ok in results
            if not ok
        ]
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="VKRT — ValidKernel Runtime Gate: pre-execution command validator"
    )
    parser.add_argument("command_file", help="Path to the command file to evaluate")
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Emit structured JSON output",
    )
    args = parser.parse_args()

    # Load command file
    try:
        with open(args.command_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"FAIL: command file not found: {args.command_file}")
        return 1
    except (IOError, OSError) as e:
        print(f"FAIL: cannot read command file: {e}")
        return 1

    if not content.strip():
        print(f"FAIL: command file is empty: {args.command_file}")
        return 1

    # Evaluate
    passed, results = evaluate_command(content)

    # Output
    if args.json_output:
        print(format_json_output(passed, results, args.command_file))
    else:
        print(format_text_output(passed, results, args.command_file))

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
