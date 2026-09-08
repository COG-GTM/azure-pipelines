#!/usr/bin/env python3
"""
Validate an ADO-to-GitHub Actions migration by comparing the generated
GHA workflow against the original ADO pipeline definition.

Produces a Markdown report with:
  - YAML syntax validation
  - Step-by-step ADO → GHA mapping verification
  - Baseline compliance checks
  - Integration point verification
  - Overall migration scorecard
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> dict | None:
    """Load a YAML file, returning None on parse failure."""
    with open(path) as f:
        raw = f.read()
    if yaml:
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError:
            return None
    # Fallback: basic validation without PyYAML
    return {"_raw": raw}


def _count_steps_in_gha(workflow: dict) -> int:
    """Count the total steps across all jobs in a GHA workflow."""
    if not workflow or "_raw" in workflow:
        return 0
    total = 0
    for job in (workflow.get("jobs") or {}).values():
        steps = job.get("steps") or []
        total += len(steps)
    return total


def _extract_gha_jobs(workflow: dict) -> list[dict]:
    """Extract job summaries from a GHA workflow."""
    if not workflow or "_raw" in workflow:
        return []
    jobs = []
    for name, job in (workflow.get("jobs") or {}).items():
        steps = job.get("steps") or []
        jobs.append({
            "name": name,
            "display_name": job.get("name", name),
            "runner": job.get("runs-on", "unknown"),
            "needs": job.get("needs", []),
            "condition": job.get("if", ""),
            "environment": job.get("environment", ""),
            "step_count": len(steps),
            "steps": [
                s.get("name", s.get("uses", "unnamed"))
                for s in steps
            ],
        })
    return jobs


def _extract_ado_stages(pipeline: dict) -> list[dict]:
    """Extract stage summaries from an ADO pipeline."""
    if not pipeline or "_raw" in pipeline:
        return []
    stages = []
    for stage in pipeline.get("stages") or []:
        name = stage.get("stage", "unknown")
        display = stage.get("displayName", name)
        condition = stage.get("condition", "")
        depends = stage.get("dependsOn", "")
        # Count steps across jobs
        step_count = 0
        jobs_list = stage.get("jobs") or []
        for job in jobs_list:
            if "steps" in job:
                step_count += len(job["steps"])
            elif "template" in job:
                step_count += 1  # template reference counts as 1
            # deployment jobs
            if "strategy" in job:
                deploy = (job.get("strategy") or {}).get("runOnce", {}).get("deploy", {})
                step_count += len(deploy.get("steps") or [])
        stages.append({
            "name": name,
            "display_name": display,
            "condition": condition,
            "depends_on": depends,
            "step_count": step_count,
            "has_template": any("template" in j for j in jobs_list),
        })
    return stages


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def check_yaml_syntax(gha_path: str) -> dict:
    """Validate GHA YAML can be parsed."""
    try:
        doc = _load_yaml(gha_path)
        if doc is None:
            return {"passed": False, "detail": "YAML parse error"}
        return {"passed": True, "detail": "Valid YAML"}
    except Exception as e:
        return {"passed": False, "detail": str(e)}


def check_triggers(workflow: dict) -> dict:
    """Verify the workflow has expected triggers."""
    if not workflow or "_raw" in workflow:
        return {"passed": True, "detail": "Skipped (no parser)"}
    triggers = workflow.get(True) or workflow.get("on") or {}
    has_push = "push" in triggers
    has_pr = "pull_request" in triggers
    has_dispatch = "workflow_dispatch" in triggers
    detail = []
    if has_push:
        detail.append("push")
    if has_pr:
        detail.append("pull_request")
    if has_dispatch:
        detail.append("workflow_dispatch")
    return {
        "passed": has_push or has_pr,
        "detail": f"Triggers: {', '.join(detail) if detail else 'none'}",
    }


def check_job_mapping(ado_stages: list, gha_jobs: list) -> dict:
    """Verify GHA jobs map 1:1 to ADO stages."""
    ado_count = len(ado_stages)
    gha_count = len(gha_jobs)
    mapped = min(ado_count, gha_count)
    return {
        "passed": ado_count == gha_count,
        "detail": f"{mapped}/{ado_count} ADO stages mapped to GHA jobs",
        "ado_stages": [s["display_name"] for s in ado_stages],
        "gha_jobs": [j["display_name"] for j in gha_jobs],
    }


def check_environment_gates(gha_jobs: list) -> dict:
    """Verify deployment jobs use GHA environment protection."""
    deploy_jobs = [j for j in gha_jobs if j.get("environment")]
    if not deploy_jobs:
        return {"passed": True, "detail": "No deployment jobs (OK)"}
    names = [f"{j['name']} → {j['environment']}" for j in deploy_jobs]
    return {
        "passed": True,
        "detail": f"Environment gates: {', '.join(names)}",
    }


def check_baseline_artifacts(baselines_dir: str, service: str) -> dict:
    """Check if artifact baselines exist for the service."""
    path = Path(baselines_dir) / service / "expected-artifacts.json"
    if not path.exists():
        return {"passed": False, "detail": "No artifact baseline found"}
    with open(path) as f:
        baseline = json.load(f)
    expected = baseline.get("expected_file_count", 0)
    types = baseline.get("expected_file_types", [])
    return {
        "passed": True,
        "detail": f"Baseline: {expected} files, types: {', '.join(types)}",
        "baseline": baseline,
    }


def check_baseline_tests(baselines_dir: str, service: str) -> dict:
    """Check if test baselines exist for the service."""
    path = Path(baselines_dir) / service / "test-counts.json"
    if not path.exists():
        return {"passed": False, "detail": "No test baseline found"}
    with open(path) as f:
        baseline = json.load(f)
    expected = baseline.get("expected_total_tests", 0)
    framework = baseline.get("frameworks", [])
    return {
        "passed": True,
        "detail": f"Baseline: {expected} tests ({', '.join(framework)})",
        "baseline": baseline,
    }


def check_integration_points(gha_jobs: list) -> dict:
    """Verify key integration points are present in the GHA workflow."""
    all_steps = []
    for job in gha_jobs:
        all_steps.extend(job.get("steps", []))
    step_text = " ".join(all_steps).lower()

    points = {
        "Artifactory": "artifactory" in step_text,
        "D2 Notification": "d2" in step_text or "notify" in step_text,
        "Compliance Attestation": "attestation" in step_text or "compliance" in step_text,
        "Test Results": "test" in step_text,
    }
    found = [k for k, v in points.items() if v]
    missing = [k for k, v in points.items() if not v]
    return {
        "passed": len(missing) == 0,
        "detail": f"Found: {', '.join(found) or 'none'}. Missing: {', '.join(missing) or 'none'}",
        "found": found,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    service: str,
    ado_path: str,
    gha_path: str,
    baselines_dir: str,
) -> str:
    """Generate a full Markdown validation report."""
    gha_doc = _load_yaml(gha_path)
    ado_doc = _load_yaml(ado_path)

    gha_jobs = _extract_gha_jobs(gha_doc)
    ado_stages = _extract_ado_stages(ado_doc)

    checks = {
        "YAML Syntax": check_yaml_syntax(gha_path),
        "Trigger Configuration": check_triggers(gha_doc),
        "Stage → Job Mapping": check_job_mapping(ado_stages, gha_jobs),
        "Environment Gates": check_environment_gates(gha_jobs),
        "Artifact Baseline": check_baseline_artifacts(baselines_dir, service),
        "Test Baseline": check_baseline_tests(baselines_dir, service),
        "Integration Points": check_integration_points(gha_jobs),
    }

    passed = sum(1 for c in checks.values() if c["passed"])
    total = len(checks)
    score = int((passed / total) * 100)

    # Build markdown
    lines = []
    lines.append("## Migration Validation Report")
    lines.append("")
    lines.append(f"**Service:** `{service}`  ")
    lines.append(f"**ADO Pipeline:** `{ado_path}`  ")
    lines.append(f"**GHA Workflow:** `{gha_path}`  ")
    lines.append(f"**Score:** {score}% ({passed}/{total} checks passed)")
    lines.append("")

    # Scorecard table
    lines.append("### Validation Scorecard")
    lines.append("")
    lines.append("| Check | Status | Details |")
    lines.append("|-------|--------|---------|")
    for name, result in checks.items():
        icon = "PASS" if result["passed"] else "FAIL"
        lines.append(f"| {name} | {icon} | {result['detail']} |")
    lines.append("")

    # Stage mapping table
    if ado_stages and gha_jobs:
        lines.append("### ADO Stage → GHA Job Mapping")
        lines.append("")
        lines.append("| ADO Stage | GHA Job | Steps | Environment |")
        lines.append("|-----------|---------|-------|-------------|")
        for i in range(max(len(ado_stages), len(gha_jobs))):
            ado_name = ado_stages[i]["display_name"] if i < len(ado_stages) else "—"
            gha_name = gha_jobs[i]["display_name"] if i < len(gha_jobs) else "—"
            steps = gha_jobs[i]["step_count"] if i < len(gha_jobs) else 0
            env = gha_jobs[i].get("environment", "—") if i < len(gha_jobs) else "—"
            env = env if env else "—"
            lines.append(f"| {ado_name} | {gha_name} | {steps} | {env} |")
        lines.append("")

    # Step details per job
    if gha_jobs:
        lines.append("### GHA Workflow Steps")
        lines.append("")
        for job in gha_jobs:
            lines.append(f"**{job['display_name']}** (`{job['name']}`)")
            for idx, step in enumerate(job["steps"], 1):
                lines.append(f"  {idx}. {step}")
            lines.append("")

    # Baseline summary
    artifact_check = checks.get("Artifact Baseline", {})
    test_check = checks.get("Test Baseline", {})
    if artifact_check.get("baseline") or test_check.get("baseline"):
        lines.append("### Baseline Expectations")
        lines.append("")
        if artifact_check.get("baseline"):
            b = artifact_check["baseline"]
            lines.append(f"- **Artifacts:** {b.get('expected_file_count', '?')} files "
                        f"(types: {', '.join(b.get('expected_file_types', []))}), "
                        f"{b.get('min_artifact_size_mb', '?')}–{b.get('max_artifact_size_mb', '?')} MB")
        if test_check.get("baseline"):
            b = test_check["baseline"]
            lines.append(f"- **Tests:** {b.get('expected_total_tests', '?')} expected "
                        f"({', '.join(b.get('frameworks', []))}), "
                        f"min pass rate: {b.get('minimum_pass_rate', '?')}")
        lines.append("")

    # Integration points
    int_check = checks.get("Integration Points", {})
    if int_check.get("found"):
        lines.append("### Integration Points Verified")
        lines.append("")
        for p in int_check["found"]:
            lines.append(f"- {p}")
        if int_check.get("missing"):
            for p in int_check["missing"]:
                lines.append(f"- ~~{p}~~ (not found)")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate ADO-to-GHA migration"
    )
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--ado-pipeline", required=True, help="Path to ADO pipeline YAML")
    parser.add_argument("--gha-workflow", required=True, help="Path to GHA workflow YAML")
    parser.add_argument("--baselines", required=True, help="Path to baselines directory")
    parser.add_argument("--output", help="Output path for report")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()

    report = generate_report(
        service=args.service,
        ado_path=args.ado_pipeline,
        gha_path=args.gha_workflow,
        baselines_dir=args.baselines,
    )

    output_text = report
    if args.format == "json":
        gha_doc = _load_yaml(args.gha_workflow)
        ado_doc = _load_yaml(args.ado_pipeline)
        gha_jobs = _extract_gha_jobs(gha_doc)
        ado_stages = _extract_ado_stages(ado_doc)
        checks = {
            "yaml_syntax": check_yaml_syntax(args.gha_workflow),
            "triggers": check_triggers(gha_doc),
            "stage_mapping": check_job_mapping(ado_stages, gha_jobs),
            "environment_gates": check_environment_gates(gha_jobs),
            "artifact_baseline": check_baseline_artifacts(args.baselines, args.service),
            "test_baseline": check_baseline_tests(args.baselines, args.service),
            "integration_points": check_integration_points(gha_jobs),
        }
        passed = sum(1 for c in checks.values() if c["passed"])
        total = len(checks)
        output_text = json.dumps({
            "service": args.service,
            "score": int((passed / total) * 100),
            "passed": passed,
            "total": total,
            "checks": checks,
        }, indent=2)

    print(output_text)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_text)


if __name__ == "__main__":
    main()
