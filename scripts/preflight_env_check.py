#!/usr/bin/env python3
"""
HIVE215 Preflight Environment Check

Validates that all required environment variables are set before
service startup. Fails closed on missing critical variables.

Usage:
    python scripts/preflight_env_check.py
    python scripts/preflight_env_check.py --service-type web
    python scripts/preflight_env_check.py --service-type worker
"""

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CheckResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


@dataclass
class EnvCheck:
    variable: str
    required_for: list[str]  # ["web", "worker", "both"]
    result: CheckResult
    value_present: bool
    message: str


# Required environment variables by service type
WEB_REQUIRED = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
]

WORKER_REQUIRED = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "DEEPGRAM_API_KEY",
]

# At least one TTS key required for worker
WORKER_TTS_KEYS = [
    "CARTESIA_API_KEY",
    "ELEVENLABS_API_KEY",
]

# Optional but recommended
OPTIONAL_VARS = {
    "web": [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "FAST_BRAIN_URL",
    ],
    "worker": [
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "FAST_BRAIN_URL",
        "DEFAULT_SKILL",
    ],
}


def check_env(service_type: str) -> list[EnvCheck]:
    """Check environment variables for a given service type."""
    checks: list[EnvCheck] = []

    # Determine required vars
    if service_type == "worker":
        required = WORKER_REQUIRED
    else:
        required = WEB_REQUIRED

    # Check required vars
    for var in required:
        value = os.environ.get(var)
        if value and value.strip():
            checks.append(EnvCheck(
                variable=var,
                required_for=[service_type],
                result=CheckResult.PASS,
                value_present=True,
                message=f"{var} is set ({len(value)} chars)",
            ))
        else:
            checks.append(EnvCheck(
                variable=var,
                required_for=[service_type],
                result=CheckResult.FAIL,
                value_present=False,
                message=f"{var} is MISSING -- required for {service_type} service",
            ))

    # Check TTS keys for worker (at least one required)
    if service_type == "worker":
        tts_found = False
        for var in WORKER_TTS_KEYS:
            value = os.environ.get(var)
            if value and value.strip():
                tts_found = True
                checks.append(EnvCheck(
                    variable=var,
                    required_for=["worker"],
                    result=CheckResult.PASS,
                    value_present=True,
                    message=f"{var} is set",
                ))
            else:
                checks.append(EnvCheck(
                    variable=var,
                    required_for=["worker"],
                    result=CheckResult.WARN,
                    value_present=False,
                    message=f"{var} is not set",
                ))

        if not tts_found:
            checks.append(EnvCheck(
                variable="TTS_KEY (any)",
                required_for=["worker"],
                result=CheckResult.FAIL,
                value_present=False,
                message="No TTS API key found -- at least one of "
                        + ", ".join(WORKER_TTS_KEYS) + " is required",
            ))

    # Check optional vars
    for var in OPTIONAL_VARS.get(service_type, []):
        value = os.environ.get(var)
        if value and value.strip():
            checks.append(EnvCheck(
                variable=var,
                required_for=[service_type],
                result=CheckResult.PASS,
                value_present=True,
                message=f"{var} is set",
            ))
        else:
            checks.append(EnvCheck(
                variable=var,
                required_for=[service_type],
                result=CheckResult.WARN,
                value_present=False,
                message=f"{var} is not set (optional but recommended)",
            ))

    return checks


def main() -> int:
    """Run preflight check and return exit code."""
    service_type = os.environ.get("SERVICE_TYPE", "web")

    # Allow override via CLI arg
    if len(sys.argv) > 2 and sys.argv[1] == "--service-type":
        service_type = sys.argv[2]

    print(f"HIVE215 Preflight Environment Check")
    print(f"Service Type: {service_type}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    checks = check_env(service_type)
    failures = [c for c in checks if c.result == CheckResult.FAIL]
    warnings = [c for c in checks if c.result == CheckResult.WARN]
    passes = [c for c in checks if c.result == CheckResult.PASS]

    for check in checks:
        icon = {"pass": "OK", "fail": "FAIL", "warn": "WARN"}[check.result.value]
        print(f"  [{icon:4s}] {check.message}")

    print("=" * 60)
    print(f"Results: {len(passes)} passed, {len(warnings)} warnings, {len(failures)} failures")

    if failures:
        print("\nFAIL CLOSED: Missing required environment variables.")
        print("The service will not start until all required variables are set.")
        return 1

    if warnings:
        print("\nWARNINGS: Some optional variables are not set.")
        print("The service will start but some features may be unavailable.")

    print("\nPreflight check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
