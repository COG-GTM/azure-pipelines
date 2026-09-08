# risk-batch-ci — ADO → GitHub Actions mapping

- **ADO pipeline:** `services/risk-batch/azure-pipelines.yml` (ID **104**, `risk-batch-ci`)
- **Category:** 1 — Central Template Consumer
- **Template source:** `shared-ci-platform` @ **`staging/preprod`** (templates read with `git show origin/staging/preprod:<path>`)
- **Owner:** team-quant (high confidence)
- **Target workflow:** `.github/workflows/risk-batch-ci.yml`
- **Inventory risk flags:** retry logic exists only on `staging/preprod`; `services/risk-batch/requirements.txt` absent from repo; unreferenced local fork `pipeline-fragments/build-python-local.yml`.

ADO MCP verification (`pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml`) could not be performed — the `azure-devops-mcp` server failed to start in this session. Templates were expanded manually from `origin/staging/preprod`.

## Templates inlined

| Template (`@templates`, ref `staging/preprod`) | Parameters passed | Effective values (defaults resolved) |
|---|---|---|
| `templates/build/build-python.yml` | `pythonVersion: '3.11'`, `requirementsFile: services/risk-batch/requirements.txt`, `artifactName: $(artifactName)` | `runTests=true`, `testFramework=pytest`, `publishArtifacts=true`, `enableLinting=true`, **`testRetryCount=3`** |
| `templates/test/run-tests.yml` | `testFramework: 'pytest'` | `testResultsDir=$(Build.ArtifactStagingDirectory)/test-results`, `publishResults=true`, `failOnTestFailure=true` |
| `templates/release/release-standard.yml` | `environment: 'dev'`, `artifactName: $(artifactName)` | `deployStrategy=rolling`, `requireApproval=false` (no branch condition emitted), `notifyReleaseOrchestrator=true` |

`staging/preprod` vs `main` for `build-python.yml`: only `staging/preprod` has the `testRetryCount` parameter, installs `pytest-rerunfailures`, wraps pytest in an `until … MAX_RETRY` loop with `--reruns 2 --reruns-delay 5`, and adds the "Stamp preprod validation marker" step. All of these are ported.

## Trigger mapping

| ADO | GHA | Notes |
|---|---|---|
| `trigger.branches.include: [main]` | `on.push.branches: [main]` | |
| `trigger.paths.include: [services/risk-batch/**]` | `on.push.paths: ['services/risk-batch/**']` | Same scope. The workflow file itself is intentionally **not** in `paths` (see Known gaps — source missing). |
| (none) | `on.pull_request` on `main`, same paths | Added per migration standard for earlier CI feedback. Deploy is push-only, artifact registration is push-only. |
| (none) | `workflow_dispatch` | Added for manual runs. |
| `pool.vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` | |

## Stage → job mapping

| ADO stage / job | GHA job | `needs` | `if` | `environment` |
|---|---|---|---|---|
| `Build` / `build` ("Build risk-batch") | `build` ("Build risk-batch") | — | — | — |
| `Release` → `Deploy_dev` / `deployment: deploy` ("Deploy to dev") | `deploy-dev` ("Deploy to dev") | `build` | `github.event_name == 'push' && github.ref == 'refs/heads/main'` | `dev` |

## Step mapping — `build` job

| # | ADO step (template) | GHA step | Translation |
|---|---|---|---|
| 1 | implicit checkout | `actions/checkout@v4` | |
| 2 | `UsePythonVersion@0` versionSpec 3.11 (build-python) | `actions/setup-python@v5` `python-version: 3.11` | |
| 3 | *(implicit on ADO agent)* | `Create artifact staging directory` (`mkdir -p`) | `$(Build.ArtifactStagingDirectory)` does not pre-exist on GHA runners. |
| 4 | script `Install dependencies` | `Install dependencies` | Identical commands; `$REQUIREMENTS_FILE` env. |
| 5 | script `Run linting checks` (`enableLinting` default true) | `Run linting checks` | Identical (`flake8 src/ --max-line-length=120`, `black --check src/`). |
| 6 | script `Run tests with coverage (retry-enabled)` | `Run tests with coverage (retry-enabled)` | Retry loop ported verbatim: `pytest-rerunfailures --reruns 2 --reruns-delay 5` inside, `until` loop up to `TEST_RETRY_COUNT=3` outside with `sleep 10`. Output to `$BUILD_ARTIFACTSTAGINGDIRECTORY/test-results.xml` and `coverage.xml`. |
| 7 | `PublishTestResults@2` JUnit, `condition: always()` | `Publish test results (build)` — `actions/upload-artifact@v4`, `if: always()` | No native GHA test tab (see Known gaps). |
| 8 | script `Build distribution` | `Build distribution` | `python setup.py sdist bdist_wheel` + copy to staging `dist/`. |
| 9 | `PublishBuildArtifacts@1` pathToPublish staging, artifactName `risk-batch-dist` | `Upload artifacts` — `actions/upload-artifact@v4` name `risk-batch-dist` | Uploads whole staging dir (dist/, test-results.xml, coverage.xml) — matches `validation/baselines/risk-batch/expected-artifacts.json`. |
| 10 | script `Register artifact in artifact-registry` (`publish_artifact.py`) | `Register artifact in Artifactory (artifact-registry)` | **Guarded `if: github.event_name == 'push'`.** Script unmodified; ADO vars shimmed via env. `--build-id $(Build.BuildId)` → `$BUILD_BUILDID` (= `github.run_id`). |
| 11 | script `Stamp preprod validation marker` (staging/preprod only) | `Stamp preprod validation marker` | Writes `preprod-stamp.txt` to staging **after** artifact upload, as in ADO (so it is not in the artifact — preserved). |
| 12 | script `Create test results directory` (run-tests) | `Create test results directory` | |
| 13 | script `Run pytest` (run-tests, `testFramework=pytest`) | `Run pytest` | Second, non-retrying pytest pass writing `test-results/results.xml --tb=short`. Pre-existing duplication preserved. |
| 14 | `PublishTestResults@2` `**/*.xml`, `failTaskOnFailedTests: true`, `always()` | `Publish test results (run-tests)` — upload-artifact, `if: always()` | |
| 15 | script `Normalize test results` (`normalize_test_results.py`), `always()` | `Normalize test results`, `if: always()` | Input dir `test-results/`, output `normalized-results.json`. |

## Step mapping — `deploy-dev` job

| # | ADO step (release-standard.yml) | GHA step | Translation |
|---|---|---|---|
| 1 | implicit checkout (`deployment` jobs do not check out by default, but scripts live in `$(Build.SourcesDirectory)`) | `actions/checkout@v4` | Needed so `build-tools/scripts/*.py` are present. |
| 2 | *(implicit)* | `Create artifact staging directory` | Fresh runner; `generate_attestation.py` writes to `BUILD_ARTIFACTSTAGINGDIRECTORY`. |
| 3 | `download: current` artifact `risk-batch-dist` | `actions/download-artifact@v4` → `${{ runner.temp }}/artifacts/risk-batch-dist` | |
| 4 | script `Execute deployment` | `Execute deployment` | `echo` only — same as ADO. |
| 5 | script `Notify release-orchestrator` (`notify_release_orchestrator.py`) | `Notify release-orchestrator (D2)` | `PIPELINE_URL` env supplies the GHA run URL (script change below). |
| 6 | script `Generate compliance attestation` (`generate_attestation.py`) | `Generate compliance attestation` | ADO vars shimmed via env. |
| 7 | *(none)* | `Upload deployment attestation` (`if: always()`) | Addition: attestation JSON was previously left on agent disk only. |

## Variable mapping

| ADO | GHA | Where |
|---|---|---|
| `$(artifactName)` = `risk-batch-dist` | `env.ARTIFACT_NAME` | top-level `env` |
| `$(templates_branch)` = `staging/preprod` | — (templates inlined; `resources.repositories` eliminated) | header comment |
| `${{ parameters.pythonVersion }}` | `env.PYTHON_VERSION` | |
| `${{ parameters.requirementsFile }}` | `env.REQUIREMENTS_FILE` | |
| `${{ parameters.testRetryCount }}` (3) | `env.TEST_RETRY_COUNT` | |
| `$(Build.ArtifactStagingDirectory)` | `env.BUILD_ARTIFACTSTAGINGDIRECTORY` = `${{ github.workspace }}/.staging` | also read directly by `publish_artifact.py` / `generate_attestation.py` |
| `$(Build.SourcesDirectory)` | `${{ github.workspace }}` (cwd) | |
| `$(Build.BuildId)` | `BUILD_BUILDID` = `${{ github.run_id }}` | |
| `$(Build.SourceBranch)` | `BUILD_SOURCEBRANCH` = `${{ github.ref }}` | |
| `$(Build.SourceVersion)` | `BUILD_SOURCEVERSION` = `${{ github.sha }}` | |
| `$(Build.DefinitionName)` | `BUILD_DEFINITIONNAME` = `${{ github.workflow }}` | |
| `$(Build.RequestedFor)` | `BUILD_REQUESTEDFOR` = `${{ github.actor }}` | |
| `$(Agent.Name)` / `$(Agent.OS)` | `AGENT_NAME` = `${{ runner.name }}` / `AGENT_OS` = `${{ runner.os }}` | step-level `env` on the helper-script steps (`runner` context is not available in workflow/job `env`) |
| `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` + `SYSTEM_TEAMPROJECT` + `/_build/results?buildId=` | `PIPELINE_URL` = `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` | |

## Condition mapping

| ADO | GHA |
|---|---|
| `dependsOn: Build` | `needs: build` |
| `condition: always()` (PublishTestResults, Normalize) | `if: always()` |
| `${{ if eq(parameters.runTests, true) }}` / `enableLinting` / `publishArtifacts` / `notifyReleaseOrchestrator` — all true | steps emitted unconditionally |
| `requireApproval=false` → no stage condition (ADO deploy ran on every Build success) | `if: github.event_name == 'push' && github.ref == 'refs/heads/main'` — equivalent in practice since `main` was the only ADO trigger; prevents deploy on the new PR trigger |
| `deployment` job `environment: dev` | `environment: dev` (create GitHub environment `dev`; add protection rules if ADO `dev` had approvals — the release template did not encode any) |

## Integration points

| Integration | ADO | GHA handling |
|---|---|---|
| Artifactory / artifact-registry (`publish_artifact.py --registry artifact-registry`) | Build stage, every run | `Register artifact in Artifactory (artifact-registry)`, push-only. Writes `risk-batch-dist-manifest.json` into staging (after artifact upload, as in ADO). |
| D2 / release-orchestrator notification (`notify_release_orchestrator.py`) | Deploy stage | `Notify release-orchestrator (D2)`; `PIPELINE_URL` → correct GHA run link. |
| Compliance attestation (`generate_attestation.py`) | Deploy stage | `Generate compliance attestation` + artifact `risk-batch-dev-attestation`. |
| Test results (`PublishTestResults@2` ×2, `normalize_test_results.py`) | Build stage | Uploaded as artifacts `risk-batch-build-test-results`, `risk-batch-test-results`; normalize step retained. |

## Helper-script changes (backward compatible)

- `build-tools/scripts/notify_release_orchestrator.py`: `pipeline_url` now prefers `PIPELINE_URL` when set and otherwise falls back to the original ADO `CollectionUri + Project + /_build/results?buildId=` construction. ADO callers are unaffected.
- No other script changes; all remaining ADO variables are shimmed via the workflow `env:` block.

## Known gaps / behavioural differences

1. **Service source is not in this repo.** `services/risk-batch/` contains only pipeline YAML — no `requirements.txt`, `src/`, `tests/`, or `setup.py` (inventory §5). The workflow is a faithful translation but will fail at `Install dependencies` until the source lands (or the ADO-side implicit checkout is identified). For this reason the workflow file is not added to its own `paths:` filter, so it does not run on this PR.
2. **Duplicate test execution** — `build-python.yml` (retry-enabled, with coverage) and `run-tests.yml` (plain) both run pytest. Preserved as-is; the owner may want to drop `run-tests.yml` on cut-over.
3. **Test results UI** — `PublishTestResults@2` has no GHA equivalent; JUnit XML is uploaded as artifacts. `dorny/test-reporter@v1` could be added later.
4. **`test-counts.json` baseline is a placeholder** (`expected_total_tests: 0`). The validator requires the file; real counts must come from ADO run history for pipeline 104.
5. **Working directory** — ADO ran `flake8 src/`, `pytest tests/`, `setup.py` from the repo root while `requirements.txt` is under `services/risk-batch/`. Ported verbatim; confirm the actual layout with team-quant.
6. **`preprod-stamp.txt` and `risk-batch-dist-manifest.json`** are written after `Upload artifacts`, so they are not part of `risk-batch-dist` — same as ADO.
7. **Local fork `services/risk-batch/pipeline-fragments/build-python-local.yml`** — unreferenced by any pipeline in any branch (inventory §5). Its retry loop (`retryCount=3`, `--timeout=300`, 60-min timeout, artifact `risk-batch-local-build`) differs from the central template's. **Not migrated**; recommend deleting after cut-over.
8. **`risk-batch-legacy` (ADO 105)** is out of scope for this workflow.
9. Deploy runs only on `push` to `main`; ADO had no PR trigger so this is not a regression.

## Secrets required

None today — `publish_artifact.py`, `notify_release_orchestrator.py`, and `generate_attestation.py` are stubs that write local JSON. When the real Artifactory / release-orchestrator / attestation integrations are wired, add the corresponding repository or `dev`-environment secrets and reference them via `${{ secrets.* }}`.

## Setup prerequisites

- Create GitHub environment `dev` (mirror any ADO `dev` environment approvals/checks).
- Populate `validation/baselines/risk-batch/test-counts.json` with real numbers.
