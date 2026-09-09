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
import subprocess
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


_TEMPLATE_RE = re.compile(r"template:\s*([^\s@]+)(?:@\w+)?", re.IGNORECASE)


def _template_repository_ref(raw: str) -> str:
    """Get the template repository ref from an ADO pipeline."""
    if yaml:
        try:
            doc = yaml.safe_load(raw) or {}
            repositories = (doc.get("resources") or {}).get("repositories") or []
            refs = {
                repository.get("repository"): repository.get("ref", "main")
                for repository in repositories
                if isinstance(repository, dict)
            }
            ref = refs.get("templates") or next(iter(refs.values()), "main")
            return str(ref or "main")
        except yaml.YAMLError:
            pass

    match = re.search(r"\bref:\s*['\"]?([^'\"\s]+)", raw)
    return match.group(1) if match else "main"


def _template_paths(raw: str) -> list[str]:
    """Extract unique template paths in declaration order."""
    return list(dict.fromkeys(_TEMPLATE_RE.findall(raw)))


def _git_show_template(path: str, ref: str, repo_root: str) -> str | None:
    """Resolve a template from a remote ref or local checkout."""
    normalized_ref = ref
    if normalized_ref.startswith("refs/heads/"):
        normalized_ref = normalized_ref.removeprefix("refs/heads/")
    refs = [normalized_ref]
    if not normalized_ref.startswith("origin/"):
        refs.insert(0, f"origin/{normalized_ref}")

    for candidate_ref in refs:
        result = subprocess.run(
            ["git", "show", f"{candidate_ref}:{path}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout

    local_path = Path(repo_root) / path
    try:
        return local_path.read_text()
    except OSError:
        return None


def _expand_ado_source_details(
    ado_path: str,
    repo_root: str,
) -> tuple[str, list[str], list[str]]:
    """Expand an ADO pipeline and one level of referenced templates."""
    source_path = Path(ado_path)
    if not source_path.is_absolute():
        source_path = Path(repo_root) / source_path
    try:
        raw = source_path.read_text()
    except OSError:
        return "", [], [f"{ado_path}@unknown"]

    ref = _template_repository_ref(raw)
    chunks = [f"# ADO source: {ado_path}\n{raw}"]
    resolved: list[str] = []
    unresolved: list[str] = []
    seen: set[tuple[str, str]] = set()
    current = [(path, raw) for path in _template_paths(raw)]

    for depth in range(2):
        next_templates: list[tuple[str, str]] = []
        for template_path, parent_text in current:
            key = (template_path, ref)
            if key in seen:
                continue
            seen.add(key)
            content = _git_show_template(template_path, ref, repo_root)
            label = f"{template_path}@{ref}"
            if content is None:
                unresolved.append(label)
                chunks.append(f"\n# ADO template unresolved: {label}")
                continue
            resolved.append(label)
            chunks.append(f"\n# ADO template resolved: {label}\n{content}")
            if depth == 0:
                next_templates.extend(
                    (nested_path, content)
                    for nested_path in _template_paths(content)
                )
        current = next_templates

    return "\n".join(chunks), resolved, unresolved


def _expand_ado_source(ado_path: str, repo_root: str) -> str:
    """Return the ADO pipeline text with referenced templates expanded."""
    expanded, _, _ = _expand_ado_source_details(ado_path, repo_root)
    return expanded


def _expansion_metadata(expanded_source: str) -> tuple[list[str], list[str]]:
    """Extract template resolution metadata embedded in expanded source."""
    resolved = re.findall(
        r"^# ADO template resolved: (.+)$", expanded_source, re.MULTILINE
    )
    unresolved = re.findall(
        r"^# ADO template unresolved: (.+)$", expanded_source, re.MULTILINE
    )
    return list(dict.fromkeys(resolved)), list(dict.fromkeys(unresolved))


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
            "raw_steps": steps,
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
    expected = baseline.get("expected_file_count")
    types = baseline.get("expected_file_types", [])
    issues = _baseline_issues(baseline, "artifacts")
    if not isinstance(expected, (int, float)) or expected <= 0:
        issues.append("expected_file_count is missing or not positive")
    if issues:
        return {
            "passed": False,
            "detail": "; ".join(issues),
            "baseline": baseline,
        }
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
    expected = baseline.get("expected_total_tests")
    framework = baseline.get("frameworks", [])
    issues = _baseline_issues(baseline, "tests")
    if not isinstance(expected, (int, float)) or expected <= 0:
        issues.append("expected_total_tests is missing or not positive")
    if issues:
        return {
            "passed": False,
            "detail": "; ".join(issues),
            "baseline": baseline,
        }
    return {
        "passed": True,
        "detail": f"Baseline: {expected} tests ({', '.join(framework)})",
        "baseline": baseline,
    }


def _baseline_issues(baseline: dict, kind: str) -> list[str]:
    """Return reasons a baseline is not trustworthy."""
    issues = []
    status = baseline.get("status")
    if isinstance(status, str) and status.lower() in {
        "provisional",
        "placeholder",
        "unconfirmed",
        "tbd",
    }:
        issues.append(
            f"Baseline is marked {status.lower()} — measure a real run and replace"
        )

    def find_notes(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key.lower() in {"note", "_note", "notes"}:
                    if isinstance(nested, str) and re.search(
                        r"placeholder|provisional", nested, re.IGNORECASE
                    ):
                        issues.append(
                            "Baseline note contains placeholder/provisional text — "
                            "measure a real run and replace"
                        )
                find_notes(nested)
        elif isinstance(value, list):
            for nested in value:
                find_notes(nested)

    find_notes(baseline)
    return list(dict.fromkeys(issues))


_ADO_INTEGRATION_PATTERNS = {
    "Artifactory": re.compile(r"artifactory|artifact-registry|publish_artifact", re.IGNORECASE),
    "D2 Notification": re.compile(r"\bd2\b|notify_d2|notify", re.IGNORECASE),
    "Compliance Attestation": re.compile(r"attestation|compliance", re.IGNORECASE),
    "Test Results": re.compile(
        r"pytest|unittest|dotnet test|mvn.*test|surefire|npm test|cargo test|go test|"
        r"PublishTestResults|jest",
        re.IGNORECASE,
    ),
}
_GHA_NEGATIVE_STEP = re.compile(
    r"not applicable|n/a|absent|not migrated|none in ado|no [a-z ]*integration|"
    r"not present|skipped",
    re.IGNORECASE,
)


def check_integration_points(gha_workflow_doc: dict, ado_source_text: str) -> dict:
    """Verify only integration points required by the expanded ADO source."""
    gha_jobs = _extract_gha_jobs(gha_workflow_doc)
    required = [
        name
        for name, pattern in _ADO_INTEGRATION_PATTERNS.items()
        if pattern.search(ado_source_text or "")
    ]
    not_applicable = [
        name for name in _ADO_INTEGRATION_PATTERNS if name not in required
    ]
    detected = []
    for point, pattern in _ADO_INTEGRATION_PATTERNS.items():
        for job in gha_jobs:
            for step in job.get("raw_steps", []):
                if not isinstance(step, dict):
                    continue
                name = str(step.get("name", ""))
                if _GHA_NEGATIVE_STEP.search(name):
                    continue
                step_text = " ".join(
                    str(step.get(key, ""))
                    for key in ("name", "run", "uses")
                )
                step_pattern = re.compile(r"test", re.IGNORECASE) if point == "Test Results" else pattern
                if step_pattern.search(step_text):
                    detected.append(point)
                    break
            if point in detected:
                break
    found = [point for point in required if point in detected]
    missing = [point for point in required if point not in found]
    required_text = ", ".join(required) or "none"
    found_text = ", ".join(found) or "none"
    missing_text = ", ".join(missing) or "none"
    not_applicable_text = ", ".join(not_applicable) or "none"
    return {
        "passed": len(missing) == 0,
        "detail": (
            f"Required (from ADO): {required_text}; Found: {found_text}; "
            f"Missing: {missing_text}; Not applicable: {not_applicable_text}"
        ),
        "found": found,
        "missing": missing,
        "required": required,
        "not_applicable": not_applicable,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    service: str,
    ado_path: str,
    gha_path: str,
    baselines_dir: str,
    repo_root: str | None = None,
) -> str:
    """Generate a full Markdown validation report."""
    repo_root = repo_root or os.getcwd()
    gha_doc = _load_yaml(gha_path)
    ado_doc = _load_yaml(ado_path)
    ado_source_text = _expand_ado_source(ado_path, repo_root)
    resolved_templates, unresolved_templates = _expansion_metadata(ado_source_text)

    gha_jobs = _extract_gha_jobs(gha_doc)
    ado_stages = _extract_ado_stages(ado_doc)

    checks = {
        "YAML Syntax": check_yaml_syntax(gha_path),
        "Trigger Configuration": check_triggers(gha_doc),
        "Stage → Job Mapping": check_job_mapping(ado_stages, gha_jobs),
        "Environment Gates": check_environment_gates(gha_jobs),
        "Artifact Baseline": check_baseline_artifacts(baselines_dir, service),
        "Test Baseline": check_baseline_tests(baselines_dir, service),
        "Integration Points": check_integration_points(gha_doc, ado_source_text),
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

    lines.append("### ADO source expansion")
    lines.append("")
    lines.append("- Resolved templates:")
    if resolved_templates:
        lines.extend(f"  - {template}" for template in resolved_templates)
    else:
        lines.append("  - None")
    lines.append("- Unresolved templates:")
    if unresolved_templates:
        lines.extend(f"  - {template}" for template in unresolved_templates)
    else:
        lines.append("  - None")
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
    if int_check.get("found") or int_check.get("not_applicable"):
        lines.append("### Integration Points Verified")
        lines.append("")
        for p in int_check["found"]:
            lines.append(f"- {p}")
        for p in int_check.get("not_applicable", []):
            lines.append(f"- {p} (not in ADO source — not required)")
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
    parser.add_argument("--repo-root", default=os.getcwd(), help="Repository root")

    args = parser.parse_args()

    report = generate_report(
        service=args.service,
        ado_path=args.ado_pipeline,
        gha_path=args.gha_workflow,
        baselines_dir=args.baselines,
        repo_root=args.repo_root,
    )

    output_text = report
    if args.format == "json":
        gha_doc = _load_yaml(args.gha_workflow)
        ado_doc = _load_yaml(args.ado_pipeline)
        ado_source_text = _expand_ado_source(args.ado_pipeline, args.repo_root)
        resolved_templates, unresolved_templates = _expansion_metadata(ado_source_text)
        gha_jobs = _extract_gha_jobs(gha_doc)
        ado_stages = _extract_ado_stages(ado_doc)
        checks = {
            "yaml_syntax": check_yaml_syntax(args.gha_workflow),
            "triggers": check_triggers(gha_doc),
            "stage_mapping": check_job_mapping(ado_stages, gha_jobs),
            "environment_gates": check_environment_gates(gha_jobs),
            "artifact_baseline": check_baseline_artifacts(args.baselines, args.service),
            "test_baseline": check_baseline_tests(args.baselines, args.service),
            "integration_points": check_integration_points(gha_doc, ado_source_text),
        }
        passed = sum(1 for c in checks.values() if c["passed"])
        total = len(checks)
        output_text = json.dumps({
            "service": args.service,
            "score": int((passed / total) * 100),
            "passed": passed,
            "total": total,
            "ado_source_expansion": {
                "resolved_templates": resolved_templates,
                "unresolved_templates": unresolved_templates,
            },
            "checks": checks,
        }, indent=2)

    print(output_text)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_text)


if __name__ == "__main__":
    main()
