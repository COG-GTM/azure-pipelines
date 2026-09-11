# market-sim ADO-to-GHA Mapping

Source: `services/market-sim/azure-pipelines.yml` (ADO pipeline ID 108, Track C, Wave 0).
Target: `.github/workflows/market-sim-ci.yml`.

The ADO pipeline is inline YAML: it references no shared templates and no `resources.repositories`
ref, so there is no consuming-branch drift to account for. `templates/build/build-rust.yml` on
`main` has zero consumers and was intentionally not used.

## Stage → job mapping

| ADO stage | `dependsOn` / `condition` | GHA job | `needs` / `if` |
| --- | --- | --- | --- |
| `Build` — "Build market-sim" (job `build_rust`, `timeoutInMinutes: 30`) | — | `build`, named `Build market-sim`, `timeout-minutes: 30` | — |
| `Deploy` — "Deploy market-sim" (job `deploy`) | `Build`; `and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))` | `deploy`, named `Deploy market-sim` | `needs: build`; `if: github.ref == 'refs/heads/main'` (`succeeded()` is implied by `needs`) |

## Step → step mapping

| ADO step (`displayName`) | GHA step |
| --- | --- |
| implicit checkout | `Check out source` (`actions/checkout@v4`) |
| — | `Set ADO compatibility variables` (inline copy of the `ado-env-shim` variable list; see below) |
| `Install Rust` (rustup + `##vso[task.prependpath]$HOME/.cargo/bin`) | `Install Rust` (rustup + `echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"`) |
| `Fetch dependencies` (`cargo fetch`) | `Fetch dependencies` |
| `Lint with clippy` (`cargo clippy -- -D warnings`) | `Lint with clippy` |
| `Build release binary` (`cargo build --release`) | `Build release binary` |
| `Run tests` (`cargo test -- --test-threads=1`) | `Run tests` |
| `Stage binary` (`cp … $(Build.ArtifactStagingDirectory)/`) | `Stage binary` (`cp … "$BUILD_ARTIFACTSTAGINGDIRECTORY/"`) |
| `Publish market-sim binary` (`PublishBuildArtifacts@1`, `artifactName: market-sim-binary`) | `Publish market-sim binary` (`actions/upload-artifact@v4`, `name: market-sim-binary`, `path: ${{ runner.temp }}/staging`) |
| `Deploy to cluster` (two `echo` lines) | `Deploy to cluster (managed outside D2)` (same two `echo` lines) |

`workingDirectory: services/market-sim` on every cargo step became `defaults.run.working-directory`
on the `build` job; the shim and rustup steps override it back to `${{ github.workspace }}`.

## Triggers

| ADO | GHA |
| --- | --- |
| `trigger.branches.include: [main]` | `on.push.branches: [main]` |
| `trigger.paths.include: [services/market-sim/**]` | `on.push.paths` + `.github/workflows/market-sim-ci.yml` + `.github/actions/**` |
| (none) | `on.pull_request.branches: [main]` with the same paths — added per migration standard |
| (none) | `on.workflow_dispatch` — added per migration standard |

## ADO variable → GHA mapping

`.github/actions/ado-env-shim` does not exist on `main` yet (it lands with PR #21), and this
migration must not touch `.github/actions/**`, so the same variable list is set inline in the
`Set ADO compatibility variables` step. When the shim merges, that step can be replaced by
`uses: ./.github/actions/ado-env-shim` with no behaviour change.

| ADO variable / macro | GHA value |
| --- | --- |
| `$(Build.ArtifactStagingDirectory)` | `$BUILD_ARTIFACTSTAGINGDIRECTORY` = `$RUNNER_TEMP/staging` |
| `$(Build.SourcesDirectory)` | `$BUILD_SOURCESDIRECTORY` = `$GITHUB_WORKSPACE` |
| `$(Build.BuildId)` | `$BUILD_BUILDID` = `$GITHUB_RUN_ID` |
| `variables['Build.SourceBranch']` | `github.ref` |
| `##vso[task.prependpath]<p>` | `echo "<p>" >> "$GITHUB_PATH"` |
| `pool.vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` |
| `variables.CARGO_TERM_COLOR`, `variables.RUST_BACKTRACE` | workflow-level `env` |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` |

## Integration points

| System | ADO 108 | GHA |
| --- | --- | --- |
| Artifactory (`publish_artifact.py`) | not called | not called (nothing to rename) |
| D2 (`notify_release_orchestrator.py`) | not called — deploy step explicitly says "managed outside D2" | not called; the echo text is preserved so the validator sees the D2 keyword the ADO source carries |
| attestation-database (`generate_attestation.py`) | not called | not called |
| Test results | `cargo test` to console only (no `PublishTestResults@2`) | `cargo test` to console only |

No integration renames apply: the pipeline never referenced `artifact-registry`,
`release-orchestrator`, or `compliance-store`.

## Baselines

`validation/baselines/market-sim/` was measured locally from the scaffold in `services/market-sim/`:
`cargo test -- --test-threads=1` → 1 suite (lib unittests), 4 tests passed, 0 bin/doc tests;
`cargo build --release` → one extensionless binary `market-sim`, 473 168 bytes.

## Intentionally not ported

| Item | Reason |
| --- | --- |
| **ACR container push** (`ContainerRegistry-ACR` / `contosofinancial.azurecr.io` bound to 108) | Track A blocker **A4** is unresolved. The ADO YAML contains no docker step; the binding is either stale or served by an ADO-side step not in YAML. Nothing container-related was added. Revisit once A4 answers whether the binding is dead. |
| Real deploy to the compute cluster | The ADO `Deploy` stage is two `echo` lines; the real mechanism is undocumented (inventory §3.1/§4). Ported verbatim as an echo. Confirm with team-quant (`r.nakamura@contoso.com`). |
| `environment:` + `release-standard` on the deploy job | 108 has no ADO environment binding, is not a `deployment:` job, and deliberately bypasses D2, so wrapping it in `release-standard` (which notifies D2 and writes an attestation) would add integrations the pipeline never had. `release-standard` is also not on `main` yet. |
| JUnit test-result upload | ADO 108 has no `PublishTestResults@2`; stable `cargo test` has no JUnit reporter, so none was invented. |
| `templates/build/build-rust.yml` | Unused by 108 (zero consumers); porting it is out of scope for this row. |
