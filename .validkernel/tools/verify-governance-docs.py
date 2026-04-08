#!/usr/bin/env python3
"""
VKG Continuous Governance Gate — Documentation Verification Script

Verifies that VKG governance documentation satisfies the Ring 2
deterministic checkpoint for specification alignment.

This script is callable both in CI and locally.

Usage:
    python .validkernel/tools/verify-governance-docs.py

Exit codes:
    0  All checks PASS
    1  One or more checks FAIL
    2  Usage error
"""

import os
import re
import sys


def read_file(path):
    """Read file contents. Returns None if file does not exist."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  ERROR: Could not read {path}: {e}")
        return None


def file_exists(path):
    return os.path.isfile(path)


def contains(text, pattern):
    """Check if text contains a literal string."""
    return pattern in text


def contains_re(text, pattern):
    """Check if text matches a regex pattern."""
    return bool(re.search(pattern, text))


def get_first_n_lines(text, n):
    """Return the first n lines of text."""
    return "\n".join(text.split("\n")[:n])


class CheckResult:
    def __init__(self, name, passed, evidence, files_inspected):
        self.name = name
        self.passed = passed
        self.evidence = evidence
        self.files_inspected = files_inspected


def detect_repo_type(repo_root):
    """Detect repository type for governance verification scoping.

    Returns one of: 'governance', 'domain', 'application', 'infrastructure', 'observer'.
    Governance repos get full README doctrine checks.
    Non-governance repos get documentation-only checks (no README doctrine).
    """
    # Check for explicit repo-type marker
    repo_type_file = os.path.join(repo_root, ".validkernel", "repo-type.json")
    if os.path.isfile(repo_type_file):
        try:
            with open(repo_type_file, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
                return data.get("repo_type", "domain")
        except Exception:
            pass

    # Heuristic: governance repos contain the VKG spec as source, not just installed copy
    # The governance repo has docs/validkernel/ AND is the canonical spec owner
    # Check if README contains governance-specific content that was authored (not installed)
    readme_path = os.path.join(repo_root, "README.md")
    if os.path.isfile(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_text = f.read()
            # Governance repos have authored governance README content
            if "Governed Environment" in readme_text and "How VKG works" in readme_text:
                return "governance"
        except Exception:
            pass

    # Default: non-governance repo
    return "domain"


# Checks that apply ONLY to governance repos (README doctrine)
GOVERNANCE_ONLY_CHECKS = {1, 2, 3, 4, 14, 15, 16, 17, 18, 19}


def run_checks(repo_root):
    results = []
    repo_type = detect_repo_type(repo_root)

    # File paths
    readme = os.path.join(repo_root, "README.md")
    vkg_spec = os.path.join(repo_root, "docs/validkernel/vkg-spec.md")
    cmd_protocol = os.path.join(repo_root, "docs/validkernel/command-protocol.md")
    cmd_exec_flow = os.path.join(repo_root, "docs/validkernel/command-execution-flow.md")
    cmd_receipts = os.path.join(repo_root, "docs/validkernel/command-receipts.md")
    cmd_registry = os.path.join(repo_root, "docs/validkernel/command-registry.md")
    glossary = os.path.join(repo_root, "docs/validkernel/glossary.md")
    risk_classes = os.path.join(repo_root, "docs/validkernel/risk-classes.md")

    # Read all files
    readme_text = read_file(readme)
    vkg_spec_text = read_file(vkg_spec)
    cmd_protocol_text = read_file(cmd_protocol)
    cmd_exec_flow_text = read_file(cmd_exec_flow)
    cmd_receipts_text = read_file(cmd_receipts)
    cmd_registry_text = read_file(cmd_registry)
    glossary_text = read_file(glossary)
    risk_classes_text = read_file(risk_classes)

    major_files = {
        "vkg-spec.md": vkg_spec_text,
        "command-protocol.md": cmd_protocol_text,
        "command-execution-flow.md": cmd_exec_flow_text,
        "command-receipts.md": cmd_receipts_text,
        "command-registry.md": cmd_registry_text,
    }

    # 1. VKG is defined as governing Governed Environments
    passed = (
        vkg_spec_text is not None
        and contains(vkg_spec_text, "Governed Environment")
        and contains(vkg_spec_text, "A Governed Environment is a system in which commands may be issued, validated, executed, recorded, and verified under VKG governance rules")
        and readme_text is not None
        and contains(readme_text, "Governed Environment")
    )
    results.append(CheckResult(
        "VKG is defined as governing Governed Environments",
        passed,
        "vkg-spec.md defines Governed Environment section; README references Governed Environments" if passed else "Missing Governed Environment definition",
        [vkg_spec, readme],
    ))

    # 2. Git repositories stated as v0.1 reference implementation
    ref_impl = "Git repositories are the reference implementation of VKG in version 0.1"
    passed = (
        vkg_spec_text is not None and contains(vkg_spec_text, ref_impl)
        and readme_text is not None and contains(readme_text, ref_impl)
    )
    results.append(CheckResult(
        "Git repositories are stated as the v0.1 reference implementation",
        passed,
        "Statement found in vkg-spec.md and README.md" if passed else "Missing reference implementation statement",
        [vkg_spec, readme],
    ))

    # 3. Canonical governance loop wording preserved
    loop = "Authority \u2192 Command \u2192 Runtime Gate \u2192 Execution \u2192 Receipt \u2192 Command Registry \u2192 Verification"
    passed = (
        vkg_spec_text is not None and contains(vkg_spec_text, loop)
        and readme_text is not None and contains(readme_text, loop)
    )
    results.append(CheckResult(
        "canonical governance loop wording is preserved",
        passed,
        "Exact loop wording found in vkg-spec.md and README.md" if passed else "Governance loop wording mismatch or missing",
        [vkg_spec, readme],
    ))

    # 4. Risk Class format uses "Risk Class N (RCN)"
    rc_pattern = r"Risk Class \d+ \(RC\d+\)"
    passed = (
        cmd_protocol_text is not None and contains_re(cmd_protocol_text, rc_pattern)
        and readme_text is not None and contains_re(readme_text, rc_pattern)
        and risk_classes_text is not None and contains_re(risk_classes_text, rc_pattern)
    )
    results.append(CheckResult(
        'Risk Class format uses "Risk Class N (RCN)"',
        passed,
        "RC format found in command-protocol.md, README.md, and risk-classes.md" if passed else "Risk Class format missing or incorrect",
        [cmd_protocol, readme, risk_classes],
    ))

    # 5. risk-classes.md exists
    passed = risk_classes_text is not None
    results.append(CheckResult(
        "risk-classes.md exists",
        passed,
        "File exists" if passed else "docs/validkernel/risk-classes.md not found",
        [risk_classes],
    ))

    # 6. glossary.md exists
    passed = glossary_text is not None
    results.append(CheckResult(
        "glossary.md exists",
        passed,
        "File exists" if passed else "docs/validkernel/glossary.md not found",
        [glossary],
    ))

    # 7. Glossary terminology consistently applied
    required_terms = [
        "Authority", "Portable Authority", "Governed Environment",
        "Command", "Command Protocol", "Runtime Gate", "Execution",
        "Receipt", "Command Registry", "Risk Class", "Execution Warrant",
        "Capability Bound", "Validation", "Verification", "State",
        "FAIL_CLOSED",
    ]
    missing_terms = []
    if glossary_text is not None:
        for term in required_terms:
            heading = f"### {term}"
            if not contains(glossary_text, heading):
                missing_terms.append(term)
    passed = glossary_text is not None and len(missing_terms) == 0
    evidence = "All 16 required terms defined" if passed else f"Missing glossary terms: {', '.join(missing_terms)}"
    results.append(CheckResult(
        "glossary terminology is consistently applied",
        passed,
        evidence,
        [glossary],
    ))

    # 8. Glossary defines FAIL_CLOSED with required wording
    fail_closed_def = "If validation fails or system state is uncertain, execution must not proceed."
    passed = glossary_text is not None and contains(glossary_text, fail_closed_def)
    results.append(CheckResult(
        "glossary defines FAIL_CLOSED using the required wording",
        passed,
        "Exact FAIL_CLOSED definition found" if passed else "FAIL_CLOSED definition missing or incorrect",
        [glossary],
    ))

    # 9. Runtime Gate PASS defined as logical execution warrant
    warrant_text = "Runtime Gate PASS functions as the effective execution warrant"
    passed = (
        vkg_spec_text is not None and contains(vkg_spec_text, warrant_text)
        and glossary_text is not None and contains(glossary_text, warrant_text)
    )
    results.append(CheckResult(
        "Runtime Gate PASS is defined as the logical execution warrant",
        passed,
        "Execution warrant definition found in vkg-spec.md and glossary.md" if passed else "Execution warrant definition missing",
        [vkg_spec, glossary],
    ))

    # 10. command-execution-flow.md preserves runtime flow wording
    flow = "Command \u2192 Runtime Gate \u2192 Execution \u2192 Receipt \u2192 Registry Update"
    passed = cmd_exec_flow_text is not None and contains(cmd_exec_flow_text, flow)
    results.append(CheckResult(
        "command-execution-flow.md preserves runtime flow wording exactly",
        passed,
        "Exact flow wording found" if passed else "Runtime flow wording missing or altered",
        [cmd_exec_flow],
    ))

    # 11. Command Registry lifecycle states unchanged
    lifecycle_states = ["ISSUED", "IN_PROGRESS", "EXECUTED", "BLOCKED", "PARTIAL", "SUPERSEDED", "ARCHIVED"]
    missing_states = []
    if cmd_registry_text is not None:
        for state in lifecycle_states:
            if not contains(cmd_registry_text, f"`{state}`"):
                missing_states.append(state)
    passed = cmd_registry_text is not None and len(missing_states) == 0
    evidence = "All 7 lifecycle states present" if passed else f"Missing states: {', '.join(missing_states)}"
    results.append(CheckResult(
        "Command Registry lifecycle states remain unchanged",
        passed,
        evidence,
        [cmd_registry],
    ))

    # 12. Verification defined as existing validation tooling only
    no_new_stage = "Verification does not introduce a new runtime stage, lifecycle state, or execution step"
    passed = (
        vkg_spec_text is not None and contains(vkg_spec_text, no_new_stage)
    )
    results.append(CheckResult(
        "verification is defined as existing validation tooling only",
        passed,
        "Verification scope statement found in vkg-spec.md" if passed else "Verification scope statement missing",
        [vkg_spec],
    ))

    # 13. Each major spec file begins with plain-language summary
    summary_failures = []
    for name, text in major_files.items():
        if text is None:
            summary_failures.append(f"{name}: file not found")
            continue
        # The summary should appear within the first 15 lines (after title, version, metadata)
        first_section = get_first_n_lines(text, 15)
        # A plain-language summary should have substantial prose (>100 chars) before the first ## section
        parts = text.split("\n## ", 1)
        if len(parts) < 2:
            summary_failures.append(f"{name}: no sections found")
            continue
        preamble = parts[0]
        # Strip title/metadata lines, check for substantial text
        lines = preamble.strip().split("\n")
        prose_lines = [l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("**") and not l.startswith("*") and l.strip() != "---"]
        total_prose = " ".join(prose_lines)
        if len(total_prose) < 100:
            summary_failures.append(f"{name}: summary too short ({len(total_prose)} chars)")

    passed = len(summary_failures) == 0
    evidence = "All 5 major spec files have plain-language summaries" if passed else f"Failures: {'; '.join(summary_failures)}"
    results.append(CheckResult(
        "each major spec file begins with a plain-language summary",
        passed,
        evidence,
        [vkg_spec, cmd_protocol, cmd_exec_flow, cmd_receipts, cmd_registry],
    ))

    # 14. README includes diagrams and non-technical explanation
    has_diagrams = (
        readme_text is not None
        and contains(readme_text, "\u250c") and contains(readme_text, "\u2500")  # box-drawing chars
        and contains(readme_text, "\u2192")  # arrow chars
    )
    has_explanation = readme_text is not None and contains(readme_text, "How VKG works")
    passed = has_diagrams and has_explanation
    results.append(CheckResult(
        "README includes diagrams and non-technical explanation",
        passed,
        "Diagrams (box-drawing characters) and 'How VKG works' section found" if passed else "Missing diagrams or non-technical explanation",
        [readme],
    ))

    # 15. README states canonical governance loop exactly
    passed = readme_text is not None and contains(readme_text, loop)
    results.append(CheckResult(
        "README states the canonical governance loop exactly",
        passed,
        "Exact governance loop found in README" if passed else "Governance loop missing from README",
        [readme],
    ))

    # 16. README includes command example with Risk Class
    passed = (
        readme_text is not None
        and contains_re(readme_text, r"Risk Class:\s+Risk Class \d+ \(RC\d+\)")
        and contains(readme_text, "L0 \u2014 GOVERNANCE CONTEXT")
    )
    results.append(CheckResult(
        "README includes a command example with Risk Class",
        passed,
        "Command example with Risk Class field found" if passed else "Command example with Risk Class missing",
        [readme],
    ))

    # 17. README command example includes all required sections and fields
    sections_present = (
        readme_text is not None
        and contains(readme_text, "L0 \u2014 GOVERNANCE CONTEXT")
        and contains(readme_text, "L1 \u2014 MISSION DIRECTIVE")
        and contains(readme_text, "L2 \u2014 DETERMINISTIC COMMIT GATE")
        and contains(readme_text, "L3 \u2014 CAPABILITY BOUND")
    )
    fields_present = (
        readme_text is not None
        and contains(readme_text, "Authority:")
        and contains(readme_text, "Document ID:")
        and contains(readme_text, "Risk Class:")
        and contains(readme_text, "Objective:")
        and contains(readme_text, "Required Outcomes:")
        and contains(readme_text, "Validation Checklist:")
        and contains(readme_text, "TOUCH-ALLOWED:")
        and contains(readme_text, "NO-TOUCH:")
        and contains(readme_text, "ENFORCEMENT MODE:")
    )
    passed = sections_present and fields_present
    results.append(CheckResult(
        "README command example includes all required sections and required fields",
        passed,
        "All 4 sections and required fields present" if passed else "Missing sections or fields in README command example",
        [readme],
    ))

    # 18. Command ring diagram uses L0/L1/L2/L3 structure
    passed = (
        readme_text is not None
        and contains(readme_text, "L0 \u2014 Governance Context")
        and contains(readme_text, "L1 \u2014 Mission Directive")
        and contains(readme_text, "L2 \u2014 Deterministic")
        and contains(readme_text, "L3 \u2014 Capability")
    )
    results.append(CheckResult(
        "command ring diagram uses L0/L1/L2/L3 structure",
        passed,
        "All four rings (L0, L1, L2, L3) found in diagram" if passed else "Ring diagram missing L0/L1/L2/L3 labels",
        [readme],
    ))

    # 19. Diagrams are real diagrams (not placeholders)
    diagram_chars = ["\u250c", "\u2500", "\u2510", "\u2502", "\u2514", "\u2518"]
    has_box_chars = readme_text is not None and all(c in readme_text for c in diagram_chars)
    has_arrow = readme_text is not None and "\u2192" in readme_text
    has_multiple_diagrams = readme_text is not None and readme_text.count("\u250c") >= 3
    passed = has_box_chars and has_arrow and has_multiple_diagrams
    results.append(CheckResult(
        "diagrams are real diagrams",
        passed,
        f"Box-drawing characters present, {readme_text.count(chr(0x250c))} diagram blocks found" if passed else "Diagrams appear to be placeholders or missing",
        [readme],
    ))

    # 20. Documentation remains compatible with tooling
    # Check that governance-tools.md still exists and references the tools
    gov_tools = os.path.join(repo_root, "docs/validkernel/governance-tools.md")
    gov_tools_text = read_file(gov_tools)
    passed = (
        gov_tools_text is not None
        and contains(gov_tools_text, "runtime-gate.py")
        and contains(gov_tools_text, "validate-receipt.py")
        and contains(gov_tools_text, "validate-all-receipts.py")
        and file_exists(os.path.join(repo_root, ".validkernel/tools/runtime-gate.py"))
        and file_exists(os.path.join(repo_root, ".validkernel/tools/validate-receipt.py"))
        and file_exists(os.path.join(repo_root, ".validkernel/tools/validate-all-receipts.py"))
    )
    results.append(CheckResult(
        "documentation remains compatible with tooling",
        passed,
        "governance-tools.md references all tools; all tool files exist" if passed else "Tooling documentation or tool files missing",
        [gov_tools],
    ))

    # 21. No speculative architecture text
    spec_patterns = [
        (r"(?i)future version.*may introduce", "speculative future version language"),
        (r"(?i)will introduce.*governance", "speculative will-introduce language"),
        (r"(?i)planned.*architecture", "speculative planned-architecture language"),
    ]
    # Only check files that were part of the alignment work
    alignment_files = {
        "vkg-spec.md": vkg_spec_text,
        "command-protocol.md": cmd_protocol_text,
        "command-execution-flow.md": cmd_exec_flow_text,
        "command-registry.md": cmd_registry_text,
        "glossary.md": glossary_text,
        "risk-classes.md": risk_classes_text,
        "README.md": readme_text,
    }
    spec_violations = []
    for fname, ftext in alignment_files.items():
        if ftext is None:
            continue
        for pattern, desc in spec_patterns:
            if re.search(pattern, ftext):
                spec_violations.append(f"{fname}: {desc}")
    passed = len(spec_violations) == 0
    evidence = "No speculative architecture text found in governance-critical files" if passed else f"Violations: {'; '.join(spec_violations)}"
    results.append(CheckResult(
        "no speculative architecture text exists",
        passed,
        evidence,
        list(alignment_files.keys()),
    ))

    return results


def main():
    # Determine repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    repo_type = detect_repo_type(repo_root)

    print("=" * 60)
    print("VKG Continuous Governance Gate — Ring 2 Verification")
    print(f"  Repo type: {repo_type}")
    if repo_type != "governance":
        print("  Mode: documentation-only (README doctrine checks skipped)")
    else:
        print("  Mode: full governance doctrine verification")
    print("=" * 60)
    print()

    results = run_checks(repo_root)

    pass_count = 0
    fail_count = 0
    skipped_count = 0

    for i, r in enumerate(results, 1):
        # Skip governance-only checks for non-governance repos
        if repo_type != "governance" and i in GOVERNANCE_ONLY_CHECKS:
            skipped_count += 1
            print(f"  [SKIP] {i:2d}. {r.name}")
            print(f"        Reason: governance-only check (repo type: {repo_type})")
            print()
            continue

        status = "PASS" if r.passed else "FAIL"
        if r.passed:
            pass_count += 1
        else:
            fail_count += 1
        print(f"  [{status}] {i:2d}. {r.name}")
        print(f"        Evidence: {r.evidence}")
        print()

    print("=" * 60)
    print(f"Results: {pass_count} passed, {fail_count} failed, {skipped_count} skipped, {len(results)} total")
    print()

    if fail_count > 0:
        print("GOVERNANCE DOCUMENTATION CHECK FAILED")
        print()
        print("Failing items:")
        for i, r in enumerate(results, 1):
            if repo_type != "governance" and i in GOVERNANCE_ONLY_CHECKS:
                continue
            if not r.passed:
                print(f"  {i}. {r.name}")
                print(f"     {r.evidence}")
        sys.exit(1)
    else:
        print("GOVERNANCE DOCUMENTATION CHECK PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
