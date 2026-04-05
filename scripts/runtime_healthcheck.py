#!/usr/bin/env python3
"""
HIVE215 Runtime Health Check

Hits the /health endpoint and validates the response.

Usage:
    python scripts/runtime_healthcheck.py
    python scripts/runtime_healthcheck.py --url https://your-app.railway.app/health
    python scripts/runtime_healthcheck.py --url http://localhost:8000/health --timeout 5
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional


DEFAULT_URL = "http://localhost:8000/health"
DEFAULT_TIMEOUT = 10


def check_health(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Check the health endpoint and return a structured result.
    """
    result = {
        "url": url,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "healthy": False,
        "status_code": None,
        "latency_ms": None,
        "response_body": None,
        "error": None,
    }

    start = time.monotonic()
    try:
        req = Request(url, method="GET")
        req.add_header("User-Agent", "HIVE215-HealthCheck/1.0")
        with urlopen(req, timeout=timeout) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result["status_code"] = resp.status
            result["latency_ms"] = elapsed_ms
            body = resp.read().decode("utf-8")
            result["response_body"] = body

            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict) and parsed.get("status") == "healthy":
                    result["healthy"] = True
                elif isinstance(parsed, dict):
                    result["healthy"] = False
                    result["error"] = f"status field is '{parsed.get('status')}', expected 'healthy'"
            except json.JSONDecodeError:
                result["healthy"] = resp.status == 200
    except HTTPError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["status_code"] = e.code
        result["latency_ms"] = elapsed_ms
        result["error"] = f"HTTP {e.code}: {e.reason}"
    except URLError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["latency_ms"] = elapsed_ms
        result["error"] = f"Connection error: {e.reason}"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["latency_ms"] = elapsed_ms
        result["error"] = f"Unexpected error: {e}"

    return result


def main() -> int:
    """Run health check and return exit code."""
    url = DEFAULT_URL
    timeout = DEFAULT_TIMEOUT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif args[i] == "--timeout" and i + 1 < len(args):
            timeout = int(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"HIVE215 Runtime Health Check")
    print(f"URL: {url}")
    print(f"Timeout: {timeout}s")
    print("=" * 60)

    result = check_health(url, timeout)

    print(f"  Status Code: {result['status_code']}")
    print(f"  Latency: {result['latency_ms']}ms")
    print(f"  Healthy: {result['healthy']}")
    if result["error"]:
        print(f"  Error: {result['error']}")

    print("=" * 60)

    if result["healthy"]:
        print("Health check PASSED.")
        return 0
    else:
        print("Health check FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
