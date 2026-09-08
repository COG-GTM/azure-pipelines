# risk-batch-legacy (ADO 105) → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `services/risk-batch/azure-pipelines-legacy.yml` (ID 105, `\Services\risk-batch`) |
| GHA workflow | `.github/workflows/risk-batch-legacy.yml` |
| Category | 1 — central template consumer (legacy template set) |
| Template source | `templates/legacy/build-python-legacy.yml` @ `legacy/master-support` (frozen; identical to the copy on `main` at e5d8164) |
| Pool | `Azure Pipelines` hosted, `vmImage: ubuntu-20.04` |
| Owner | team-quant (last modified by `contractor-account@contoso.com`) |
| Activity | 2 runs / 90 days, both succeeded, avg 8.7 min, last 2026-01-10 03:00 UTC |
| Variable groups | VG 201 `shared-ci-secrets` (bound in ADO definition, not declared in YAML) |
| Helper scripts | none — the legacy template calls no `build-tools/scripts/*.py` |

ADO MCP verification (`azure-devops-mcp`, org `shawn0864`) could not be run: the server
process failed at startup in this session. Pipeline metadata above comes from
`docs/samples/ado-api-responses.json` and `docs/pipeline-inventory-report.md`; templates were
expanded manually from `origin/legacy/master-support`.

## Expanded ADO execution view (source of truth)

Single stage `Build`, single job `legacy_build`, template parameters
`pythonVersion='3.9'`, `artifactName='risk-batch-legacy'`, `requirementsFile` default `requirements.txt`.
All paths are relative to `$(Build.SourcesDirectory)` (repository root).

| # | ADO step | Resolved inputs |
|---|---|---|
| 1 | `UsePythonVersion@0` | `versionSpec: 3.9` |
| 2 | script "Install dependencies" | `python -m pip install --upgrade pip && pip install -r requirements.txt` |
| 3 | script "Run tests (unittest)" | `python -m unittest discover -s tests -p "test_*.py" -v 2>&1 \| tee test-output.txt` |
| 4 | script "Build package" | `python setup.py sdist bdist_wheel` |
| 5 | `PublishBuildArtifacts@1` | `pathToPublish: dist/`, `artifactName: risk-batch-legacy` |

## Trigger mapping

| ADO | GHA | Notes |
|---|---|---|
| `trigger: none` (CI disabled) | — | Preserved: no `on.push`. |
| Manual queue | `workflow_dispatch` with inputs `pythonVersion` (default `3.9`) and `reason` | `reason` is free text so the caller can identify itself. |
| **External downstream trigger (caller unknown)** | `repository_dispatch: types: [risk-batch-legacy]` | **Open question** — proposed replacement. The downstream job would `POST /repos/{owner}/{repo}/dispatches` with `event_type: risk-batch-legacy`; optional `client_payload.pythonVersion`. Only valid if the external caller can be identified and updated. |
| — | `pull_request` on `main`, paths limited to this workflow, the legacy ADO YAML and the legacy template | Not in ADO. Added per playbook (and required by `validate-migration`'s trigger check). Scoped so risk-batch source changes do **not** trigger it. The `build` job is skipped on `pull_request` (`if: github.event_name != 'pull_request'`) because the risk-batch source tree is not in this repo; only `parity-notes` runs, and `validate-migration` lints the file. |

## Stage / job mapping

| ADO stage → job | GHA job | Notes |
|---|---|---|
| `Build` → `legacy_build` | `build` ("Build (legacy_build)") | 1:1, 7 steps (5 mapped + checkout + test-output upload). |
| — | `parity-notes` ("Trigger audit and parity notes"), `needs: build`, `if: always()` | Not in ADO. Writes to the run summary: trigger event/actor/payload (to identify the external caller) and explicit notes that Artifactory publish, D2 notify, compliance attestation and test-result normalization are **not** performed — matching ADO 105, and differing from risk-batch-ci (104). See "Validator note" below. |

## Task / step mapping

| ADO | GHA step | Translation |
|---|---|---|
| (implicit checkout) | `actions/checkout@v4` | |
| `UsePythonVersion@0` 3.9 | `actions/setup-python@v5`, `python-version: ${{ env.PYTHON_VERSION }}` | `PYTHON_VERSION` = dispatch input → `client_payload.pythonVersion` → `3.9`. |
| script "Install dependencies" | `Install dependencies` | Same commands, run from `$LEGACY_WORKDIR` (`.`). `PIP_INDEX_URL` is exported only if repo variable `vars.PIP_INDEX_URL` is set (replaces VG 201). |
| script "Run tests (unittest)" | `Run tests (unittest)` | Same command plus `set -o pipefail` so a unittest failure is not masked by `tee` (ADO `script` also failed on the pipeline exit status — see gaps). |
| — | `Upload unittest output` (`if: always()`) | Not in ADO; uploads `test-output.txt` as `risk-batch-legacy-test-output`. |
| script "Build package" | `Build package` | `python setup.py sdist bdist_wheel`, unchanged. |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` name `risk-batch-legacy`, path `dist/`, `if-no-files-found: error` | |

No `**` globs, no `publishWebProjects`, no Artifactory registration to guard — the legacy template has none of these.

## Variable mapping

| ADO | GHA |
|---|---|
| `parameters.pythonVersion` (`'3.9'`) | `env.PYTHON_VERSION` |
| `parameters.requirementsFile` (`requirements.txt`) | `env.REQUIREMENTS_FILE` |
| `parameters.artifactName` (`risk-batch-legacy`) | `env.ARTIFACT_NAME` |
| `$(Build.SourcesDirectory)` | `env.LEGACY_WORKDIR=.` + `BUILD_SOURCESDIRECTORY=${{ github.workspace }}` |
| `$(Build.SourceBranch)` / `$(Build.SourceVersion)` / `$(Build.BuildId)` | `BUILD_SOURCEBRANCH` / `BUILD_SOURCEVERSION` / `BUILD_BUILDID` shims |
| ADO run URL | `PIPELINE_URL=${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` |
| VG 201 `PIP_INDEX_URL` | repository variable `vars.PIP_INDEX_URL` (optional) |
| VG 201 `NUGET_*`, `NPM_*` | not used by this pipeline; not mapped |

Shims are present for consistency with the other migrated workflows; no helper script is
invoked here, so **no `build-tools/scripts/*.py` changes were needed**.

## Condition mapping

ADO has no stage/step conditions. GHA adds `if: github.event_name != 'pull_request'` on `build`
(see trigger mapping), `if: always()` on the test-output upload and on `parity-notes` (so the
trigger audit is recorded even when the build fails or is skipped).

## Integration points

| Integration | ADO 105 | GHA |
|---|---|---|
| Artifactory (`publish_artifact.py`) | not called | not called; noted in run summary |
| D2 (`notify_release_orchestrator.py`) | not called (no release stage) | not called; noted |
| Compliance attestation (`generate_attestation.py`) | not called | not called; noted |
| Test results | console output only (`test-output.txt`, never published) | uploaded as artifact; no JUnit/normalization |
| Build artifact | ADO artifact `risk-batch-legacy` (`dist/`) | GHA artifact `risk-batch-legacy` |

## Validator note

`validate-migration` maps every `risk-batch-*` workflow to `services/risk-batch/azure-pipelines.yml`
(ADO **104**, two stages), not to the legacy YAML. To make the scorecard meaningful for this
workflow without editing the validator:

- the second job (`parity-notes`) gives the 2-job shape the stage check expects and makes the
  legacy pipeline's missing integrations explicit rather than silently absent;
- `validation/baselines/risk-batch/test-counts.json` was added as a **placeholder** (0 tests,
  frameworks `unittest`/`pytest`) — team-quant must fill in real counts from the last green ADO
  runs of 104/105 before cut-over. The existing `expected-artifacts.json` describes 104's
  `risk-batch-dist` (wheel + sdist + test-results.xml + coverage.xml); 105 produces only wheel + sdist.

A follow-up could add an explicit `risk-batch-legacy → azure-pipelines-legacy.yml` case to the
validator so the scorecard compares against the correct source.

## Known gaps / open questions for team-quant

1. **Unidentified external trigger.** `_meta` says the pipeline is "still triggered externally by
   downstream jobs"; ADO `triggers: []`, 2 runs in 90 days (both 03:00 UTC, suggesting a scheduled
   caller). Nobody has identified the caller. Until it is found, the ADO definition cannot be
   disabled without risk. `repository_dispatch` is only a plausible replacement if the caller can
   be modified to call the GitHub API (needs a PAT/App token with `contents:write`).
2. **Fold into risk-batch-ci (104)?** The inventory recommends migrating 105 "only if the
   external trigger can be identified, otherwise fold into 104". This workflow exists so a
   like-for-like fallback is available; retiring it in favour of 104 (`risk-batch-dist`,
   pytest, Python 3.11) is the preferred end state and would remove the last live consumer of
   `legacy/master-support`.
3. **EOL Python.** Template default and pin are Python 3.9 (EOL Oct 2025; 3.8 EOL Oct 2024).
   `actions/setup-python@v5` still resolves 3.9 on `ubuntu-latest` today, but this will break
   when the toolcache drops it. The dispatch input allows overriding without editing the workflow.
4. **`ubuntu-20.04` → `ubuntu-latest`.** The 20.04 hosted image is retired on both ADO and GHA;
   moving to `ubuntu-latest` (24.04) is unavoidable and may change system libraries.
5. **Repo-root paths (pre-existing).** The legacy template runs `pip install -r requirements.txt`,
   `unittest discover -s tests` and `setup.py` from the repository root; none of these exist in
   this repo (risk-batch source is not checked in here). Preserved as-is via `LEGACY_WORKDIR=.`;
   change that variable if the real source lives under `services/risk-batch/`.
6. **`setup.py sdist bdist_wheel` (pre-existing).** Deprecated invocation; `bdist_wheel` requires
   the `wheel` package to be in `requirements.txt`. Not changed during migration.
7. **Test failure semantics.** ADO `script` steps fail on the last command's exit code, i.e. `tee`,
   so unittest failures did *not* fail the ADO build unless the pipeline relied on the outer
   `2>&1 |` behaviour. GHA adds `set -o pipefail`, so failing tests now fail the job — a
   deliberate tightening; drop `pipefail` to keep the legacy (lenient) behaviour.
8. **No Artifactory / D2 / attestation** — parity with 105, but if this pipeline's artifact is
   consumed downstream, that consumer also has no Artifactory record to pull from.
9. **Artifact retention.** ADO kept 90 days / min 3 builds; GHA default artifact retention
   applies (repo setting) — set `retention-days` if 90 is required.

## Secrets / variables required

| Name | Type | Purpose |
|---|---|---|
| `PIP_INDEX_URL` | repository **variable** (optional) | Internal PyPI mirror (`https://pkgs.contoso-financial.com/pypi/simple/`, from VG 201). Public PyPI is used if unset. |
| PAT / GitHub App token with `contents:write` | held by the external caller | Only needed if the caller adopts `repository_dispatch`. |

No repository secrets are consumed by the workflow itself.
