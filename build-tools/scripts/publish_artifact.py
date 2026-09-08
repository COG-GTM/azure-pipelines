#!/usr/bin/env python3
"""
Publish build artifacts to Artifactory.

Used by CI templates to register build outputs in the central
artifact tracking system. Called at the end of build pipelines.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from ci_context import agent_name, ci_system, source_branch, source_commit, staging_dir


def publish_artifact(name: str, registry: str, build_id: str, metadata: dict = None):
    """Register an artifact in the artifact registry."""
    payload = {
        "artifact_name": name,
        "registry": registry,
        "build_id": build_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_branch": source_branch(),
        "source_commit": source_commit(),
        "agent_name": agent_name(),
        "ci_system": ci_system(),
        "metadata": metadata or {},
    }

    print(f"Registering artifact: {name}")
    print(f"  Registry: {registry}")
    print(f"  Build ID: {build_id}")
    print(f"  Branch: {payload['source_branch']}")
    print(f"  Commit: {payload['source_commit']}")

    # In a real environment, this would POST to the Artifactory API
    output_path = staging_dir()
    manifest_path = os.path.join(output_path, f"{name}-manifest.json")

    with open(manifest_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  Manifest written to: {manifest_path}")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Publish artifact to registry")
    parser.add_argument("--name", required=True, help="Artifact name")
    parser.add_argument("--registry", required=True, help="Target registry")
    parser.add_argument("--build-id", required=True, help="Build ID")
    parser.add_argument("--metadata", type=json.loads, default=None, help="Additional metadata (JSON)")

    args = parser.parse_args()

    try:
        publish_artifact(args.name, args.registry, args.build_id, args.metadata)
        print("Artifact registration successful.")
    except Exception as e:
        print(f"ERROR: Failed to register artifact: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
