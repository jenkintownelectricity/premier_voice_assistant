#!/usr/bin/env python3
"""
HIVE215 Post-Deploy Verification

Verifies that all services are running correctly after deployment.

Usage:
    python scripts/deploy_verify.py
    python scripts/deploy_verify.py --web-url https://web.railway.app
    python scripts/deploy_verify.py --web-url https://web.railway.app --fast-brain-url https://fast-brain.modal.run
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional


def check_endpoint(name: str, url: str, timeout: int = 10) -> dict:
    """Check a single endpoint."""
    result = {
        "name": name,
        "url": url,
        "healthy": False,
        "status_code": None,
        "latency_ms": None,
        "error": None,
    }

    start = time.monotonic()
    try:
        req = Request(url, method="GET")
        req.add_header("User-Agent", "HIVE215-DeployVerify/1.0")
        with urlopen(req, timeout=timeout) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result["status_code"] = resp.status
            result["latency_ms"] = elapsed_ms
            result["healthy"] = 200 <= resp.status < 300
    except HTTPError as e:
        result["status_code"] = e.code
        result["latency_ms"] = int((time.monotonic() - start) * 1000)
        result["error"] = f"HTTP {e.code}: {e.reason}"
    except URLError as e:
        result["latency_ms"] = int((time.monotonic() - start) * 1000)
        result["error"] = f"Connection error: {e.reason}"
    except Exception as e:
        result["latency_ms"] = int((time.monotonic() - start) * 1000)
        result["error"] = f"Unexpected error: {e}"

    return result


def main() -> int:
    """Run post-deploy verification."""
    web_url: Optional[str] = None
    fast_brain_url: Optional[str] = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--web-url" and i + 1 < len(args):
            web_url = args[i + 1]
            i += 2
        elif args[i] == "--fast-brain-url" and i + 1 < len(args):
            fast_brain_url = args[i + 1]
            i += 2
        else:
            i += 1

    print("HIVE215 Post-Deploy Verification")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    checks: list[dict] = []

    # Check web service
    if web_url:
        health_url = web_url.rstrip("/") + "/health"
        result = check_endpoint("Web Service Health", health_url)
        checks.append(result)
        icon = "OK" if result["healthy"] else "FAIL"
        print(f"  [{icon:4s}] {result['name']}: status={result['status_code']} latency={result['latency_ms']}ms")
        if result["error"]:
            print(f"         Error: {result['error']}")
    else:
        print("  [SKIP] Web Service Health: --web-url not provided")

    # Check Fast Brain
    if fast_brain_url:
        health_url = fast_brain_url.rstrip("/") + "/health"
        result = check_endpoint("Fast Brain Health", health_url)
        checks.append(result)
        icon = "OK" if result["healthy"] else "FAIL"
        print(f"  [{icon:4s}] {result['name']}: status={result['status_code']} latency={result['latency_ms']}ms")
        if result["error"]:
            print(f"         Error: {result['error']}")

        # Check skills endpoint
        skills_url = fast_brain_url.rstrip("/") + "/v1/skills"
        result = check_endpoint("Fast Brain Skills", skills_url)
        checks.append(result)
        icon = "OK" if result["healthy"] else "FAIL"
        print(f"  [{icon:4s}] {result['name']}: status={result['status_code']} latency={result['latency_ms']}ms")
        if result["error"]:
            print(f"         Error: {result['error']}")
    else:
        print("  [SKIP] Fast Brain: --fast-brain-url not provided")

    print("=" * 60)

    failures = [c for c in checks if not c["healthy"]]
    if not checks:
        print("No endpoints checked. Provide --web-url and/or --fast-brain-url.")
        return 1

    if failures:
        print(f"VERIFICATION FAILED: {len(failures)}/{len(checks)} endpoints unhealthy")
        return 1

    print(f"VERIFICATION PASSED: {len(checks)}/{len(checks)} endpoints healthy")

    # Write verification receipt
    receipt = {
        "receipt_type": "deploy_verification",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "all_healthy": len(failures) == 0,
    }
    try:
        receipt_path = "9_receipts/deploy/deploy_verification_receipt.json"
        with open(receipt_path, "w") as f:
            json.dump(receipt, f, indent=2)
        print(f"Verification receipt written to {receipt_path}")
    except OSError:
        pass  # Non-critical if receipt dir doesn't exist

    return 0


if __name__ == "__main__":
    sys.exit(main())
