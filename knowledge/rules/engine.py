"""
Runtime Validation Engine for Construction Assembly Knowledge Graphs.

Provides the core framework for registering, executing, and reporting on
domain-specific validation rules. Implements fail-closed semantics: if a
rule cannot be evaluated due to missing data, it FAILS rather than passes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RuleCategory(str, Enum):
    """Categories that classify what aspect of the assembly a rule validates."""
    CONTINUITY = "continuity"
    COMPATIBILITY = "compatibility"
    SEQUENCING = "sequencing"
    SUPPORT = "support"
    CODE_REFERENCE = "code_reference"


class Severity(str, Enum):
    """How critical a rule violation is."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ValidationRule:
    """
    A single validation rule that can be evaluated against a graph or subgraph.

    Attributes:
        rule_id:              Unique identifier (e.g. ``ROOF-001``).
        rule_version:         Semver string for the rule definition.
        rule_source:          Citation or standard the rule derives from.
        category:             One of the ``RuleCategory`` values.
        severity:             How critical a failure is.
        trigger_condition:    Human-readable description of when the rule
                              should fire.
        required_inputs:      List of data keys the rule needs to evaluate.
        evaluation_logic:     Callable ``(context: dict) -> bool``. Returns
                              ``True`` when the assembly **passes** the rule.
        pass_criteria:        Human-readable description of what constitutes
                              a pass.
        fail_criteria:        Human-readable description of what constitutes
                              a failure.
        fail_closed_behavior: What happens when required data is missing.
        escalation_behavior:  When/how to escalate to a human reviewer.
        error_message_template: Python format-string for the failure message.
    """

    rule_id: str
    rule_version: str
    rule_source: str
    category: RuleCategory
    severity: Severity
    trigger_condition: str
    required_inputs: List[str]
    evaluation_logic: Callable[[Dict[str, Any]], bool]
    pass_criteria: str
    fail_criteria: str
    fail_closed_behavior: str = "Rule fails when required data is missing."
    escalation_behavior: str = "Flag for human review when confidence is low."
    error_message_template: str = "Validation failed for rule {rule_id}."


@dataclass
class ValidationResult:
    """Outcome produced by running a single ``ValidationRule``."""

    rule_id: str
    passed: bool
    severity: Severity
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    requires_human_review: bool = False


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ValidationEngine:
    """
    Registers and executes ``ValidationRule`` instances against a context
    dictionary that represents a graph or subgraph of an assembly.

    Key behaviours:
        * **Fail-closed** -- if a rule's required inputs are missing the rule
          is recorded as *failed* with ``requires_human_review=True``.
        * **Evidence attachment** -- callers can supply an ``evidence`` dict
          inside the context under the key ``"_evidence"``; the engine copies
          it into each result.
        * **Escalation** -- rules whose ``escalation_behavior`` contains
          ``"always"`` automatically set ``requires_human_review=True``.
    """

    def __init__(self) -> None:
        self._rules: Dict[str, ValidationRule] = {}
        self._category_index: Dict[RuleCategory, Set[str]] = {
            cat: set() for cat in RuleCategory
        }

    # -- registration -------------------------------------------------------

    def register(self, rule: ValidationRule) -> None:
        """Register a rule with the engine (replaces existing by rule_id)."""
        self._rules[rule.rule_id] = rule
        self._category_index[rule.category].add(rule.rule_id)

    def register_many(self, rules: List[ValidationRule]) -> None:
        """Register a batch of rules."""
        for rule in rules:
            self.register(rule)

    # -- querying -----------------------------------------------------------

    @property
    def rule_ids(self) -> List[str]:
        return list(self._rules.keys())

    def rules_by_category(self, category: RuleCategory) -> List[ValidationRule]:
        return [
            self._rules[rid]
            for rid in sorted(self._category_index.get(category, set()))
        ]

    # -- execution ----------------------------------------------------------

    def evaluate(
        self,
        context: Dict[str, Any],
        *,
        rule_ids: Optional[List[str]] = None,
        categories: Optional[List[RuleCategory]] = None,
    ) -> List[ValidationResult]:
        """
        Run rules against *context* and return structured results.

        Parameters:
            context:    Dict representing the graph/subgraph data. Include
                        ``"_evidence"`` key for citation attachment.
            rule_ids:   If provided, only run these specific rules.
            categories: If provided, only run rules in these categories.

        Returns:
            List of ``ValidationResult`` objects (one per evaluated rule).
        """
        evidence_base = context.get("_evidence", {})
        results: List[ValidationResult] = []

        candidates = self._select_rules(rule_ids, categories)

        for rule in candidates:
            result = self._run_single(rule, context, evidence_base)
            results.append(result)

        return results

    # -- internals ----------------------------------------------------------

    def _select_rules(
        self,
        rule_ids: Optional[List[str]],
        categories: Optional[List[RuleCategory]],
    ) -> List[ValidationRule]:
        """Filter rules by explicit ids or categories."""
        if rule_ids is not None:
            return [
                self._rules[rid]
                for rid in rule_ids
                if rid in self._rules
            ]
        if categories is not None:
            ids: Set[str] = set()
            for cat in categories:
                ids |= self._category_index.get(cat, set())
            return [self._rules[rid] for rid in sorted(ids)]
        return list(self._rules.values())

    def _run_single(
        self,
        rule: ValidationRule,
        context: Dict[str, Any],
        evidence_base: Dict[str, Any],
    ) -> ValidationResult:
        """
        Execute one rule with fail-closed semantics.

        If any ``required_inputs`` are absent from *context* the rule is
        treated as **failed** and flagged for human review.
        """
        # 1. Check required inputs -- fail-closed on missing data
        missing = [k for k in rule.required_inputs if k not in context]
        if missing:
            return ValidationResult(
                rule_id=rule.rule_id,
                passed=False,
                severity=rule.severity,
                message=(
                    f"FAIL-CLOSED: Rule {rule.rule_id} could not evaluate. "
                    f"Missing required inputs: {missing}. "
                    f"{rule.fail_closed_behavior}"
                ),
                evidence={"missing_inputs": missing, **evidence_base},
                requires_human_review=True,
            )

        # 2. Run the evaluation logic -- catch exceptions as failures
        try:
            passed = rule.evaluation_logic(context)
        except Exception as exc:
            logger.exception("Rule %s raised an exception", rule.rule_id)
            return ValidationResult(
                rule_id=rule.rule_id,
                passed=False,
                severity=rule.severity,
                message=(
                    f"FAIL-CLOSED: Rule {rule.rule_id} raised an exception: "
                    f"{exc}. {rule.fail_closed_behavior}"
                ),
                evidence={"exception": str(exc), **evidence_base},
                requires_human_review=True,
            )

        # 3. Build the result
        if passed:
            message = rule.pass_criteria
        else:
            message = rule.error_message_template.format(
                rule_id=rule.rule_id, **context
            )

        needs_review = (
            not passed
            and "always" in rule.escalation_behavior.lower()
        )

        return ValidationResult(
            rule_id=rule.rule_id,
            passed=passed,
            severity=rule.severity,
            message=message,
            evidence=evidence_base,
            requires_human_review=needs_review,
        )
