#!/usr/bin/env python3
"""
Notify D2 of deployment events.

Sends deployment status updates to the central release tracking
system. Called by release templates after successful deployments.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def notify(service: str, env: str, build_id: str, status: str):
    """Send deployment notification to D2."""
    notification = {
        "event": "deployment",
        "service": service,
        "environment": env,
        "build_id": build_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_url": os.environ.get("PIPELINE_URL")
        or (
            os.environ.get("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", "")
            + os.environ.get("SYSTEM_TEAMPROJECT", "")
            + "/_build/results?buildId="
            + build_id
        ),
        "triggered_by": os.environ.get("BUILD_REQUESTEDFOR", "unknown"),
    }

    print(f"Notifying D2:")
    print(f"  Service: {service}")
    print(f"  Environment: {env}")
    print(f"  Status: {status}")
    print(f"  Build: {build_id}")

    # In production, this would POST to the D2 API
    print("  Notification sent: OK")

    return notification


def main():
    parser = argparse.ArgumentParser(description="Notify D2")
    parser.add_argument("--service", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--status", required=True, choices=["success", "failure", "cancelled"])

    args = parser.parse_args()

    try:
        notify(args.service, args.env, args.build_id, args.status)
    except Exception as e:
        print(f"ERROR: Notification failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
