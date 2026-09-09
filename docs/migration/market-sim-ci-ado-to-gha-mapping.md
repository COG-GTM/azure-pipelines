# market-sim-ci ADO to GitHub Actions mapping

## Header

| Field | Value |
| --- | --- |
| Pipeline name | market-sim-ci |
| ADO ID | 108 |
| Source YAML | `services/market-sim/azure-pipelines.yml` |
| Category | 4 (custom inline) |
| Template ref | none (inline) |
| Owner | team-quant? (low confidence); contact `r.nakamura@contoso.com` per inventory §4 |
| Pool | `ubuntu-latest` |

## Trigger mapping

| ADO | GitHub Actions | Notes |
| --- | --- | --- |
| `trigger.branches.include [main]` | `on.push.branches [main]` | Direct mapping |
| `trigger.paths.include services/market-sim/**` | `on.push.paths [services/market-sim/**, .github/workflows/market-sim-ci.yml]` | The workflow file itself is an intentional addition |
| None | `on.pull_request` for `main`, with the same paths | Intentional addition; ADO had no PR trigger |
| None | `workflow_dispatch` | Intentional addition |
| None | `concurrency` group `market-sim-ci-${{ github.ref }}` | Added with `cancel-in-progress` for PRs only |

## Stage/job mapping

| ADO stage/job | GitHub Actions job | Mapping |
| --- | --- | --- |
| Stage `Build` / job `build_rust` | `build` | Name `Build market-sim`; `timeout-minutes: 30`; `defaults.run.working-directory: services/market-sim` |
| Stage `Deploy` / job `deploy` | `deploy` | `needs: build` |

## Task/step mapping

| ADO step | GitHub Actions step | Mapping |
| --- | --- | --- |
| Implicit ADO checkout in `build_rust` | `actions/checkout@v4` in `build` | Checkout is explicit in GHA |
| Install Rust | `Install Rust` | Rustup script kept verbatim; `##vso[task.prependpath]$HOME/.cargo/bin` becomes `echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"`; working directory is reset to `${{ github.workspace }}` |
| `cargo fetch` | `cargo fetch` | Runs in `services/market-sim` |
| `cargo clippy -- -D warnings` | `cargo clippy -- -D warnings` | Runs in `services/market-sim` |
| `cargo build --release` | `cargo build --release` | Runs in `services/market-sim` |
| `cargo test -- --test-threads=1` | `cargo test -- --test-threads=1` | Runs in `services/market-sim` |
| Stage binary | `Stage binary` | `$(Build.ArtifactStagingDirectory)` becomes `$RUNNER_TEMP/staging`; `mkdir -p` was added because the directory does not pre-exist on GHA runners |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` | Artifact name `market-sim-binary`; path `${{ runner.temp }}/staging`; `if-no-files-found: error` |
| Implicit ADO checkout in `deploy` | `actions/checkout@v4` in `deploy` | Checkout is explicit in GHA |
| Deploy to cluster echo | `Deploy to cluster` | Identical `run:` step |

## Variable mapping

| ADO | GitHub Actions |
| --- | --- |
| `CARGO_TERM_COLOR=always` | Top-level `env: CARGO_TERM_COLOR: always` |
| `RUST_BACKTRACE=1` | Top-level `env: RUST_BACKTRACE: 1` |
| `$(Build.ArtifactStagingDirectory)` | `$RUNNER_TEMP/staging` |

## Condition mapping

| ADO | GitHub Actions | Notes |
| --- | --- | --- |
| `and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))` | `needs: build` plus `if: github.event_name == 'push' && github.ref == 'refs/heads/main'` | `needs` implies success. The push-only guard is an intentional tightening so PR runs never reach deploy. |

## Integration points

- **Artifactory:** Not used by this pipeline; there is no `publish_artifact.py` call.
- **D2:** The pipeline explicitly bypasses D2 (`managed outside D2`); there is no `notify_release_orchestrator.py` call.
- **Compliance attestation:** None.
- **Test results:** ADO never used `PublishTestResults@2`; GHA relies on the `cargo test` exit code only, as ADO did.
- **Helper scripts:** No scripts in `build-tools/scripts/` are called; no script changes are needed.

## Validation baselines

The new `validation/baselines/market-sim/{expected-artifacts.json,test-counts.json}` baselines were measured from a real local run on 2026-09-09:

- One artifact file: `market-sim`, a release ELF, 473168 bytes; `expected_file_types` is `[""]` (extensionless, matching `compare_artifacts.py` suffix scanning); size bounds 0.1–20 MB. No artifact metadata for pipeline 108 exists in the ADO API dump, so this is a local measurement of the #12 scaffold, not an ADO run — re-measure against a real ADO run when one is available.
- Four tests, all in `src/lib.rs` unit tests; bin unittests 0; doctests 0.
- Framework: `cargo test`.

These baselines are required by the repository's `validate-migration` scorecard.

## Known gaps / open decisions

- The Deploy stage is an `echo` only. The real deploy mechanism to the compute cluster is undocumented and must be confirmed with team-quant before relying on the GHA deploy job.
- The ACR service connection `ContainerRegistry-ACR` (`contosofinancial.azurecr.io`) is bound to pipeline 108 per the API dump, but the YAML has no Docker step. No Docker step was added; verify whether the binding is stale or an ADO-side non-YAML step.
- `templates/build/build-rust.yml` exists but is unused by 108; it was intentionally not inlined.
- The rustup install script was kept verbatim although `ubuntu-latest` ships Rust; it still works (`rustup -y` updates in place).
- `--test-threads=1` was preserved.
- No GHA `environment:` is used because the ADO Deploy is a plain job, not a deployment job with an environment.
- Azure DevOps MCP (`azure-devops-mcp`, org `shawn0864`) failed to start in this session, so `pipeline_preview_pipeline_yaml` could not be used. The mapping fell back to manual reading; this is trivial here because there are no templates.

## Secrets required

None; no secrets are referenced by the workflow.
