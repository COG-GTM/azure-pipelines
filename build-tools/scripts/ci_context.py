"""Resolve common CI context values from Azure DevOps or GitHub Actions."""

import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def source_branch() -> str:
    return _env("BUILD_SOURCEBRANCH", _env("GITHUB_REF", "unknown"))


def source_commit() -> str:
    return _env("BUILD_SOURCEVERSION", _env("GITHUB_SHA", "unknown"))


def agent_name() -> str:
    return _env("AGENT_NAME", _env("RUNNER_NAME", "unknown"))


def pipeline_name() -> str:
    return _env("BUILD_DEFINITIONNAME", _env("GITHUB_WORKFLOW", "unknown"))


def agent_os() -> str:
    return _env("AGENT_OS", _env("RUNNER_OS", "unknown"))


def requested_for() -> str:
    return _env("BUILD_REQUESTEDFOR", _env("GITHUB_ACTOR", "unknown"))


def run_url(build_id: str = "") -> str:
    collection = os.environ.get("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI")
    project = os.environ.get("SYSTEM_TEAMPROJECT")
    ado_build_id = os.environ.get("BUILD_BUILDID") or build_id
    if collection and project and ado_build_id:
        return f"{collection}{project}/_build/results?buildId={ado_build_id}"

    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repository and run_id:
        return f"{server}/{repository}/actions/runs/{run_id}"

    return ""


def staging_dir() -> str:
    return _env(
        "BUILD_ARTIFACTSTAGINGDIRECTORY",
        _env("RUNNER_TEMP", "/tmp"),
    )


def ci_system() -> str:
    if os.environ.get("TF_BUILD"):
        return "azure-devops"
    if os.environ.get("GITHUB_ACTIONS"):
        return "github-actions"
    return "unknown"
