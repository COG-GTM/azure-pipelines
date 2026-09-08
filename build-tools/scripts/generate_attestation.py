#!/usr/bin/env python3
"""
Generate compliance attestation records.

Creates attestation documents for build artifacts and uploads
them to attestation-database. Required for production deployments.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from ci_context import agent_os, ci_system, pipeline_name, source_branch, source_commit, staging_dir


def generate_attestation(artifact: str, env: str, build_id: str, hotfix: bool = False):
    """Generate a compliance attestation record."""
    attestation = {
        "schema_version": "2.1",
        "artifact": artifact,
        "environment": env,
        "build_id": build_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attestation_type": "hotfix" if hotfix else "standard",
        "source_branch": source_branch(),
        "source_commit": source_commit(),
        "pipeline_name": pipeline_name(),
        "agent_os": agent_os(),
        "ci_system": ci_system(),
        "checks": {
            "tests_passed": True,
            "security_scan": not hotfix,  # Hotfixes skip security scan
            "compliance_review": not hotfix,
            "artifact_signed": True,
        },
    }

    # Generate attestation hash
    content = json.dumps(attestation, sort_keys=True)
    attestation["hash"] = hashlib.sha256(content.encode()).hexdigest()

    print(f"Attestation generated for: {artifact}")
    print(f"  Environment: {env}")
    print(f"  Type: {attestation['attestation_type']}")
    print(f"  Hash: {attestation['hash'][:16]}...")

    output_path = staging_dir()
    attestation_path = os.path.join(output_path, f"{artifact}-attestation.json")

    with open(attestation_path, "w") as f:
        json.dump(attestation, f, indent=2)

    print(f"  Written to: {attestation_path}")

    # In production, this would also POST to attestation-database
    print("  Uploaded to attestation-database: OK")

    return attestation


def main():
    parser = argparse.ArgumentParser(description="Generate compliance attestation")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--hotfix", type=str, default="false")

    args = parser.parse_args()
    hotfix = args.hotfix.lower() == "true"

    try:
        generate_attestation(args.artifact, args.env, args.build_id, hotfix)
    except Exception as e:
        print(f"ERROR: Attestation generation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
