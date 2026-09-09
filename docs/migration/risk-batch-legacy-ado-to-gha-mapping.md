# risk-batch-legacy — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `risk-batch-legacy` (ID **105**) |
| ADO YAML | `services/risk-batch/azure-pipelines-legacy.yml` |
| Category | 1 — central template consumer (legacy template) |
| Template ref | `legacy/master-support` (frozen, no owner; consumers: 105 active, 117 dead) |
| Template consumed | `templates/legacy/build-python-legacy.yml@legacy/master-support` |
| Owner | team-quant (medium confidence) — external trigger **unknown** |
| GHA workflow | `.github/workflows/risk-batch-legacy.yml` |
| Inventory recommendation | Migrate as `workflow_dispatch` only if the external trigger can be identified; otherwise fold into `risk-batch-ci` (104) |

Template contents were read with `git show origin/legacy/master-support:templates/legacy/build-python-legacy.yml`
(the file does not exist on `main`). The ADO MCP (`azure-devops-mcp`, org `shawn0864`) could not be reached
during this migration (server failed to start), so the expanded YAML was produced manually from the branch above.

## Expanded ADO execution view (source of truth)

Resolved parameters: `pythonVersion='3.9'`, `requirementsFile='requirements.txt'` (template default),
`artifactName='risk-batch-legacy'`.

| # | ADO step | Task / script | Effective inputs |
|---|---|---|---|
| 0 | (implicit checkout) | — | `self` repo, `pool: ubuntu-20.04` |
| 1 | Use Python 3.9 | `UsePythonVersion@0` | `versionSpec: 3.9` |
| 2 | Install dependencies | `script` | `python -m pip install --upgrade pip && pip install -r requirements.txt` |
| 3 | Run tests (unittest) | `script` | `python -m unittest discover -s tests -p "test_*.py" -v 2>&1 \| tee test-output.txt` |
| 4 | Build package | `script` | `python setup.py sdist bdist_wheel` |
| 5 | Publish artifacts | `PublishBuildArtifacts@1` | `pathToPublish: dist/`, `artifactName: risk-batch-legacy` |

No helper scripts from `build-tools/scripts/` are invoked, so no script changes and no ADO env-var shims are needed.

## Trigger mapping

| ADO | GHA | Note |
|---|---|---|
| `trigger: none` | *(no `push`)* | Preserved — the pipeline never ran on push. |
| External caller (unknown downstream job, 2 runs / 90 d) | `workflow_dispatch` (input `reason`) + `repository_dispatch` (`types: [risk-batch-legacy]`) | The external caller must be identified and re-pointed at the GitHub API (`POST /repos/{owner}/{repo}/dispatches` with `event_type: risk-batch-legacy`, or `POST .../actions/workflows/risk-batch-legacy.yml/dispatches`) before cut-over. |
| — | `pull_request` on `main`, paths `services/risk-batch/**`, this workflow | **Intentional addition** for early CI feedback (playbook requirement; also required by the repo validator). |

## Stage / job mapping

| ADO stage → job | GHA job | `needs` | `if` |
|---|---|---|---|
| `Build` → `legacy_build` | `build` (name `Build`) | — | — |

## Step mapping

| ADO step | GHA step | Translation |
|---|---|---|
| implicit checkout | `actions/checkout@v4` | — |
| — | `Record dispatch context` | **Addition**: writes event name, dispatch `reason` and `client_payload` to the job summary so external runs are traceable. |
| `UsePythonVersion@0` (3.9) | `actions/setup-python@v5` with `python-version: 3.9` | — |
| `Install dependencies` | `run:` same two commands + `pip install wheel` | `wheel` was preinstalled on the ADO hosted image but not in the setup-python toolcache; without it `setup.py bdist_wheel` fails. Output is unchanged. |
| `Run tests (unittest)` | `run:` identical command | Kept verbatim, including `\| tee` (see Known gaps). |
| — | `Upload unittest output` (`if: always()`) | **Addition**: uploads `test-output.txt` as artifact `risk-batch-legacy-test-output`. The legacy template never published it. |
| `Build package` | `run: python setup.py sdist bdist_wheel` | — |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` with `name: risk-batch-legacy`, `path: services/risk-batch/dist/`, `if-no-files-found: error` | — |

## Variable mapping

| ADO | GHA |
|---|---|
| `${{ parameters.pythonVersion }}` = `3.9` | `env.PYTHON_VERSION` |
| `${{ parameters.requirementsFile }}` = `requirements.txt` | `env.REQUIREMENTS_FILE` |
| `${{ parameters.artifactName }}` = `risk-batch-legacy` | `env.ARTIFACT_NAME` |
| `pool.vmImage: ubuntu-20.04` | `runs-on: ubuntu-latest` (20.04 image is retired on both platforms) |
| working directory `$(Build.SourcesDirectory)` | `defaults.run.working-directory: services/risk-batch` (see Known gaps) |

No `$(Build.*)` / `$(System.*)` variables are used by the pipeline or template.

## Condition mapping

None — the ADO pipeline has no stage/job/step conditions.

## Integration points

| Integration | ADO | GHA |
|---|---|---|
| Artifactory (`publish_artifact.py`) | Not called by `build-python-legacy.yml@legacy/master-support` (the inventory §5.1 note "105 via legacy templates" does not hold for this template revision) | Not applicable |
| D2 notification | Not present | Not applicable |
| Compliance attestation | Not present | Not applicable |
| Test results | unittest output to `test-output.txt` only; no `PublishTestResults@2` | Same command; log additionally uploaded as an artifact |
| Build artifacts | `PublishBuildArtifacts@1` → `risk-batch-legacy` | `actions/upload-artifact@v4` → `risk-batch-legacy` |

## Known gaps / behavioural notes

1. **External trigger unknown (blocking for cut-over).** Nothing in the repo or inventory identifies the downstream job that
   starts pipeline 105. Until it is found and re-pointed at `repository_dispatch`/`workflow_dispatch`, the ADO pipeline
   must stay enabled. Fallback per inventory: fold this build into `risk-batch-ci` (104) and delete 105.
2. **Python 3.9 is EOL** (as are the 3.8 defaults elsewhere on `legacy/master-support`). Preserved deliberately; not upgraded.
   `actions/setup-python` still serves 3.9 from the toolcache/`python-versions` manifest, but the runtime itself receives no security fixes.
3. **Test failures do not fail the job** — pre-existing. The ADO script pipes `unittest` through `tee` without `pipefail`,
   so the step exit code is `tee`'s. GHA's default `run` shell (`bash -e {0}`) behaves the same, so parity is preserved.
   Fixing it (`set -o pipefail`, or `shell: bash`) is a one-line change once the owner agrees.
4. **Working directory.** The ADO pipeline ran the template at the repo root, where `requirements.txt`, `tests/` and `setup.py`
   do not exist — the inventory (§5.2) records this as "scripts/source referenced but absent". The GHA workflow runs in
   `services/risk-batch/`, where the runnable scaffold now lives. This is the only way the pipeline can succeed from this repo.
5. **`setup.py sdist bdist_wheel` is deprecated** by setuptools; kept for parity. Emits deprecation warnings only.
6. **`ubuntu-20.04` → `ubuntu-latest`.** The pinned image is retired on both platforms.
7. **Artifact baseline mismatch (pre-existing).** `validation/baselines/risk-batch/expected-artifacts.json` describes the
   `risk-batch-ci` (104) artifact (`risk-batch-dist`, 6 files incl. `test-results.xml`/`coverage.xml`). The legacy pipeline produces
   only a `.whl` and a `.tar.gz` under `risk-batch-legacy`. The baseline was not changed; a legacy-specific baseline would need
   validator routing changes, which are out of scope.
8. **Test baseline added.** `validation/baselines/risk-batch/test-counts.json` did not exist; it is added with the measured
   count (6 tests, `services/risk-batch/tests/test_var.py`) and lists both `unittest` (105) and `pytest` (104) since both pipelines
   exercise the same suite. If the 104 migration adds the same file, keep whichever lands first — the numbers are identical.
9. **Runner drift.** ADO hosted agents carried a large preinstalled toolset; the workflow installs only `pip`, `wheel` and
   `requirements.txt` (currently empty).

## Secrets required

None. The workflow uses only the default `GITHUB_TOKEN` with `contents: read`.
Wiring the external caller will require a token (fine-grained PAT or GitHub App) with `actions: write` /
`contents: write` on this repository, held by the *caller*, not by this workflow.

## Validator expectations (`validate-migration`)

`validate-migration.yml` routes `risk-batch-legacy.yml` → service `risk-batch`, ADO source
`services/risk-batch/azure-pipelines-legacy.yml`. Local run of `validation/scripts/validate_migration.py` against this
workflow: **7/7 PASS** (YAML, triggers, 1/1 stage→job, environment gates, artifact baseline, test baseline, integration
points = Test Results only).
