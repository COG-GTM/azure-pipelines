# risk-batch-ci — ADO to GitHub Actions mapping

## Overview

| Field | Value |
|---|---|
| Pipeline | `risk-batch-ci` |
| ADO pipeline ID | 104 |
| ADO definition | `services/risk-batch/azure-pipelines.yml` |
| Category | 1 — Central Template Consumer |
| Owner | `team-quant` |
| Template branch | `staging/preprod` |
| GHA workflow | `.github/workflows/risk-batch-ci.yml` |

The Azure DevOps MCP verification was attempted, but the `azure-devops-mcp`
server failed to start. The templates were therefore expanded manually with:

```text
git show origin/staging/preprod:templates/build/build-python.yml
git show origin/staging/preprod:templates/test/run-tests.yml
git show origin/staging/preprod:templates/release/release-standard.yml
```

The workflow intentionally inlines the three central templates rather than
depending on a remote reusable workflow. The local
`services/risk-batch/pipeline-fragments/build-python-local.yml` fork is not
referenced by this ADO pipeline and is intentionally not migrated.

## Trigger mapping

| ADO trigger | GHA trigger | Notes |
|---|---|---|
| `trigger.branches.include: [main]` | `push.branches: [main]` | Preserved. |
| `trigger.paths.include: [services/risk-batch/**]` | Same service path plus workflow and helper-script paths | The workflow and `build-tools/scripts/**` paths are intentional additions so changes to the migrated workflow or its helper scripts validate. |
| No pull-request trigger | `pull_request.branches: [main]` with the same three paths | Intentional addition for pre-merge feedback; deployment and Artifactory registration remain guarded. |
| No manual trigger | `workflow_dispatch` | Intentional addition for controlled manual runs. |

The workflow uses `concurrency.group: risk-batch-ci-${{ github.ref }}` and
cancels in-progress runs only for pull requests.

## Variable mapping

| ADO variable or expression | GHA mapping | Scope / notes |
|---|---|---|
| `$(artifactName)` | `ARTIFACT_NAME: risk-batch-dist` | Top-level `env`. |
| `pythonVersion` | `PYTHON_VERSION: '3.11'` | Top-level `env`. |
| `requirementsFile` | `REQUIREMENTS_FILE: services/risk-batch/requirements.txt` | Top-level `env`; installed through `$GITHUB_WORKSPACE`. |
| `testRetryCount` | `TEST_RETRY_COUNT: '3'` | Top-level `env`. |
| `$(Build.SourceBranch)` | `BUILD_SOURCEBRANCH: ${{ github.ref }}` | ADO-compatible helper-script shim. |
| `$(Build.SourceVersion)` | `BUILD_SOURCEVERSION: ${{ github.sha }}` | ADO-compatible helper-script shim. |
| `$(Build.BuildId)` | `BUILD_BUILDID: ${{ github.run_id }}` | ADO-compatible helper-script shim. |
| `$(Build.DefinitionName)` | `BUILD_DEFINITIONNAME: ${{ github.workflow }}` | ADO-compatible helper-script shim. |
| `$(Build.RequestedFor)` | `BUILD_REQUESTEDFOR: ${{ github.actor }}` | ADO-compatible helper-script shim. |
| ADO pipeline result URL | `PIPELINE_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` | Used by `notify_release_orchestrator.py`. |
| `$(Build.ArtifactStagingDirectory)` | `$RUNNER_TEMP/staging` | The first step after checkout in each job creates it and writes `BUILD_ARTIFACTSTAGINGDIRECTORY` to `$GITHUB_ENV`; later `run:` steps use `$BUILD_ARTIFACTSTAGINGDIRECTORY` and action inputs use `${{ env.BUILD_ARTIFACTSTAGINGDIRECTORY }}`. |
| `$(Build.SourcesDirectory)` | `$GITHUB_WORKSPACE` | Build job runs from `services/risk-batch`; root-relative files use this explicit path. |
| `$(Agent.Name)` | `AGENT_NAME: ${{ runner.name }}` | Step-level env on `publish_artifact.py`; `runner.*` is not used in workflow/job env. |
| `$(Agent.OS)` | `AGENT_OS: ${{ runner.os }}` | Step-level env on `generate_attestation.py`; `runner.*` is not used in workflow/job env. |

## Stage to job mapping

| ADO stage / job | GHA job | `needs` | Condition | Environment |
|---|---|---|---|---|
| `Build` / `build` (`Build risk-batch`) | `build` (`Build risk-batch`) | — | — | — |
| `Release` / `Deploy_dev` (`deployment: deploy`) | `deploy-dev` (`Deploy to dev`) | `build` | `github.event_name != 'pull_request' && github.ref == 'refs/heads/main'` | `dev` |

## Step-by-step task mapping — build job

The ADO build template commands were repository-root-oriented. The GHA build
job uses `defaults.run.working-directory: services/risk-batch` because that is
where this repository's Python source, tests, packaging files, and requirements
live. Root-relative requirements and helper scripts use `$GITHUB_WORKSPACE`.

| # | ADO task / step | GHA step | Inputs translated |
|---:|---|---|---|
| 1 | Source checkout (implicit ADO behavior) | `actions/checkout@v4` | Explicit checkout. |
| 2 | ADO agent staging directory | `Create artifact staging directory` | `mkdir -p "$RUNNER_TEMP/staging"` and append `BUILD_ARTIFACTSTAGINGDIRECTORY` to `$GITHUB_ENV`. |
| 3 | `UsePythonVersion@0` (`build-python.yml`) | `actions/setup-python@v5` | `python-version: ${{ env.PYTHON_VERSION }}` → `3.11`. |
| 4 | `Install dependencies` (`build-python.yml`) | `Install dependencies` | Upgrade `pip setuptools wheel`; install `$GITHUB_WORKSPACE/$REQUIREMENTS_FILE`. |
| 5 | `Run linting checks` (`build-python.yml`) | `Run linting checks` | Install `flake8 black mypy`; run `flake8 src/ --max-line-length=120` and `black --check src/`. |
| 6 | `Run tests with coverage (retry-enabled)` (`build-python.yml`) | Same named GHA step | Install pytest tooling; write `test-results.xml` and `coverage.xml`; preserve inner `--reruns 2 --reruns-delay 5` and outer `TEST_RETRY_COUNT=3` loop. |
| 7 | `PublishTestResults@2` (`build-python.yml`) | `Publish test results (build)` / `actions/upload-artifact@v4` | `always()`; upload the single JUnit XML because GHA has no native test tab. |
| 8 | `Build distribution` (`build-python.yml`) | `Build distribution` | `python setup.py sdist bdist_wheel`; copy `dist/` into staging. |
| 9 | `PublishBuildArtifacts@1` (`build-python.yml`) | `Upload artifacts` / `actions/upload-artifact@v4` | Name `risk-batch-dist`; upload the full staging directory before steps 10 and 11. |
| 10 | `Register artifact in artifact-registry` (`build-python.yml`) | `Register artifact in Artifactory (artifact-registry)` | Push-only; call `publish_artifact.py` with `--registry artifact-registry`, `$BUILD_BUILDID`, and step-level `AGENT_NAME`. |
| 11 | `Stamp preprod validation marker` (`build-python.yml`) | `Stamp preprod validation marker` | Write the build ID to `preprod-stamp.txt`. |
| 12 | `Create test results directory` (`run-tests.yml`) | `Create test results directory` | `mkdir -p "$BUILD_ARTIFACTSTAGINGDIRECTORY/test-results"`. |
| 13 | `Run pytest` (`run-tests.yml`) | `Run pytest` | Second, non-retrying pass to `test-results/results.xml` with `--tb=short`; duplication is preserved. |
| 14 | `PublishTestResults@2` (`run-tests.yml`) | `Publish test results (run-tests)` / `actions/upload-artifact@v4` | `always()`; upload the test-results directory. |
| 15 | `Normalize test results` (`run-tests.yml`) | `Normalize test results` | `always()`; call `normalize_test_results.py` with the staging input and output paths. |

## Step-by-step task mapping — deploy-dev job

| # | ADO task / step | GHA step | Inputs translated |
|---:|---|---|---|
| 1 | Deployment job source access | `actions/checkout@v4` | ADO deployment jobs do not check out source by default, although the release template calls `$(Build.SourcesDirectory)/build-tools/scripts`; GHA checks out explicitly. |
| 2 | Fresh agent staging | `Create artifact staging directory` | Create `$RUNNER_TEMP/staging` and export `BUILD_ARTIFACTSTAGINGDIRECTORY` through `$GITHUB_ENV`. |
| 3 | `download: current`, artifact `risk-batch-dist` | `actions/download-artifact@v4` | Download to `${{ runner.temp }}/artifacts/risk-batch-dist`. |
| 4 | `Execute deployment` (`release-standard.yml`) | `Execute deployment` | Echo artifact name and `Strategy: rolling`. |
| 5 | `Notify release-orchestrator` (`release-standard.yml`) | `Notify release-orchestrator (D2)` | `--service "$ARTIFACT_NAME" --env dev --build-id "$BUILD_BUILDID" --status success`. |
| 6 | `Generate compliance attestation` (`release-standard.yml`) | `Generate compliance attestation` | Call `generate_attestation.py`; step-level `AGENT_OS`. |
| 7 | No ADO publish step | `Upload deployment attestation` | `always()` upload of staging outputs so files that previously remained on ADO agent disk are retrievable. |

## Condition mapping

| ADO condition / behavior | GHA condition / behavior |
|---|---|
| Release `dependsOn: Build` | `deploy-dev.needs: build`. |
| ADO release template has `requireApproval=false`, so it emits no stage condition | `deploy-dev` runs only when the event is not a pull request and the ref is `refs/heads/main`; this covers main pushes and manual main runs while excluding the intentional PR trigger. |
| `condition: always()` on build test publication | `if: always()` on `Publish test results (build)`. |
| `condition: always()` on run-tests publication and normalization | `if: always()` on both corresponding GHA steps. |
| ADO template booleans `runTests`, `publishArtifacts`, `enableLinting`, and `notifyReleaseOrchestrator` resolve true | Their GHA steps are emitted unconditionally. |
| ADO artifact registration runs after build | `Register artifact in Artifactory (artifact-registry)` is guarded with `if: github.event_name == 'push'`. |

## Integration points

| Integration | ADO behavior | GHA handling |
|---|---|---|
| Artifactory / `artifact-registry` | `publish_artifact.py` registers the build artifact | Push-only GHA step named for Artifactory and `artifact-registry`; current stub writes a manifest. |
| D2 / `release-orchestrator` | Release-stage deployment notification | `Notify release-orchestrator (D2)` calls the helper with `PIPELINE_URL` set to the GHA run URL. |
| `attestation-database` | Release-stage compliance record | `generate_attestation.py` writes the attestation; the output is uploaded as `risk-batch-dev-attestation`. |
| Test results | Two `PublishTestResults@2` tasks plus normalization | JUnit XML is uploaded as `risk-batch-build-test-results` and `risk-batch-test-results`; normalization remains in the build job. |

## Template resolution notes

The ADO pipeline pins `shared-ci-platform` at `staging/preprod`, so that branch
is the source of truth for this migration rather than `main`. Its
`build-python.yml` contains the retry logic and preprod stamp that this
workflow preserves: `pytest-rerunfailures` retries each test and the outer
whole-suite loop retries up to three times. Those behaviors exist only on
`staging/preprod`.

The service-local
`services/risk-batch/pipeline-fragments/build-python-local.yml` is an
unreferenced fork. Inventory §5.2, “Unreferenced templates,” lists it among
templates with zero consumers, so it is ignored rather than migrated.

## Known gaps / intentional deviations

- `pytest-junitxml` was dropped because the package does not exist on PyPI
  (404); pytest includes JUnit XML output natively.
- The build job uses `working-directory: services/risk-batch` instead of the
  template's repository-root assumption. Root-relative requirements and helper
  scripts are addressed explicitly with `$GITHUB_WORKSPACE`.
- The duplicate pytest pass is preserved: the coverage/retry pass comes from
  `build-python.yml`, and the plain pass comes from `run-tests.yml`.
- ADO deployment jobs do not check out source by default, despite the release
  template calling `$(Build.SourcesDirectory)/build-tools/scripts`; GHA
  checks out explicitly.
- GHA has no native test-results tab equivalent to `PublishTestResults@2`.
  The JUnit outputs are uploaded as artifacts; `dorny/test-reporter` is an
  optional future addition.
- The deploy condition intentionally excludes pull requests and requires
  `refs/heads/main`; this is needed because the GHA workflow adds a
  pull-request trigger while the ADO pipeline only triggered on main pushes.
- The ADO pipeline references `release-standard.yml` (a `stages:` template)
  under `jobs:`. This ADO-side schema issue is preserved in the mapping and
  is not fixable in this GHA change.
- `validation/baselines/risk-batch/expected-artifacts.json` expects 6 files and
  1–20 MB, which does not match the scaffold's measured output of 4 files at
  approximately 24 KB. The mismatch is flagged here and the baseline is not
  changed.
- The GitHub `dev` environment must exist. GitHub may auto-create it when the
  workflow first references it, but it will have no protection rules unless
  configured separately.
- No secrets are referenced by the stub scripts today. When real endpoints are
  wired, the ADO variable groups
  `artifact-registry-credentials`
  (`ARTIFACT_REGISTRY_URL` / `ARTIFACT_REGISTRY_TOKEN`),
  `compliance-store-credentials`, and the `AzureSubscription-Dev` service
  connection should become repository or environment secrets. Azure service
  connection authentication should use an appropriate OIDC design.

## Helper script changes

`build-tools/scripts/notify_release_orchestrator.py` now prefers the
`PIPELINE_URL` environment variable when it is set and non-empty. If it is
unset or empty, it falls back to the existing ADO construction from
`SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`, `SYSTEM_TEAMPROJECT`, and
`/_build/results?buildId=`. This keeps existing ADO callers backward
compatible while allowing the GHA deployment to link to its run.
