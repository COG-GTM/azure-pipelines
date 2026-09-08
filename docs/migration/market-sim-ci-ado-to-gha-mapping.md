# market-sim-ci — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `market-sim-ci` (ID 108), `services/market-sim/azure-pipelines.yml` |
| GHA workflow | `.github/workflows/market-sim-ci.yml` |
| Category | 4 — Custom inline (no shared templates; `templates/build/build-rust.yml` exists but is unused) |
| Owner | team-quant (low confidence — YAML header says `team-quant?`) |
| Pool | Microsoft-hosted `ubuntu-latest` → `runs-on: ubuntu-latest` |
| Templates inlined | none |
| Helper scripts | none (no `build-tools/scripts/*.py` used, so no script changes in this migration) |
| ADO MCP check | `azure-devops-mcp` org `shawn0864` does not host this pipeline; migration done from repo YAML + `docs/pipeline-inventory-report.md` (18 runs / 90 d, 16 succeeded, 2 failed, avg 23.4 min). |

## Trigger mapping

| ADO | GHA | Note |
|---|---|---|
| `trigger.branches.include: [main]` | `on.push.branches: [main]` | identical |
| `trigger.paths.include: [services/market-sim/**]` | `on.push.paths: ['services/market-sim/**']` | identical |
| (no PR trigger) | `on.pull_request.branches: [main]`, same paths | **Added** — earlier CI feedback. Deploy job is guarded to `push` so PRs never deploy. |
| — | — | The workflow file itself is *not* in `paths`; editing the workflow does not trigger a build (the Rust sources are not in this repo, so a self-triggered run would fail). Owner may add `.github/workflows/market-sim-ci.yml` to `paths` once the source lives alongside. |

## Variable mapping

| ADO | GHA |
|---|---|
| `CARGO_TERM_COLOR: 'always'` | workflow `env.CARGO_TERM_COLOR: always` |
| `RUST_BACKTRACE: 1` | workflow `env.RUST_BACKTRACE: 1` |
| `$(Build.ArtifactStagingDirectory)` | `${{ runner.temp }}/staging`, exposed as `BUILD_ARTIFACTSTAGINGDIRECTORY`; created with `mkdir -p` (fresh runner) |
| `##vso[task.prependpath]$HOME/.cargo/bin` | `echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"` |

## Stage / job mapping

| ADO stage → job | GHA job | `needs` | Condition |
|---|---|---|---|
| `Build` / `build_rust` ("Rust build", `timeoutInMinutes: 30`) | `build` ("Build market-sim", `timeout-minutes: 30`) | — | always |
| `Deploy` / `deploy` (`dependsOn: Build`, `and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))`) | `deploy` ("Deploy market-sim") | `build` | `github.event_name == 'push' && github.ref == 'refs/heads/main'` (`needs` supplies `succeeded()`) |

## Step / task mapping

| # | ADO step (`displayName`) | ADO task | GHA step | Translation |
|---|---|---|---|---|
| 0 | (implicit checkout) | — | `actions/checkout@v4` | first step in both jobs |
| 1 | Install Rust | `script` | `Install Rust` | identical rustup command; `##vso[task.prependpath]` → `$GITHUB_PATH` |
| — | — | — | `Verify Rust project is present` | **Added**: fails fast with an explicit `::error::` if `services/market-sim/Cargo.toml` is absent (sources are not in this repo — known gap 3). |
| 2 | Fetch dependencies | `script`, `workingDirectory: services/market-sim` | `Fetch dependencies` | `working-directory:` |
| 3 | Lint with clippy | `script` | `Lint with clippy` | `cargo clippy -- -D warnings` unchanged |
| 4 | Build release binary | `script` | `Build release binary` | `cargo build --release` unchanged |
| 5 | Run tests | `script` | `Run tests` | `cargo test -- --test-threads=1` unchanged |
| 6 | Stage binary | `script` | `Stage binary` | `mkdir -p` staging dir then `cp target/release/market-sim` |
| 7 | Publish market-sim binary | `PublishBuildArtifacts@1` (`artifactName: market-sim-binary`) | `actions/upload-artifact@v4` (`name: market-sim-binary`, `if-no-files-found: error`) | pipeline artifact; ADO had no Artifactory registration |
| — | — | — | `Migration parity notes …` | **Added**: writes to `$GITHUB_STEP_SUMMARY` the integrations this pipeline intentionally lacks (Artifactory, D2, attestation) and the ACR binding note. No side effects. |
| 8 | Deploy to cluster | `script` (two `echo`s) | `Deploy to cluster (echo only — managed outside D2)` | replicated verbatim |

## Condition mapping

| ADO | GHA |
|---|---|
| `succeeded()` (stage) | implicit via `needs: build` |
| `eq(variables['Build.SourceBranch'], 'refs/heads/main')` | `github.ref == 'refs/heads/main'` |
| (ADO has no PR builds) | `github.event_name == 'push'` added so the new `pull_request` trigger cannot reach `deploy` |

## Integration points

| Integration | ADO behaviour | GHA behaviour |
|---|---|---|
| Artifactory | not used (`PublishBuildArtifacts@1` only) | not used; `actions/upload-artifact@v4` |
| D2 release notification | not used — deploy is "managed outside D2" | not used; same echo |
| Compliance attestation | not generated | not generated |
| `ContainerRegistry-ACR` service connection | bound to pipeline 108 in the ADO API dump; **no docker/ACR step in YAML** | no ACR login or push. Treated as a **possibly stale binding**. |
| Test results | `cargo test` console output only, no `PublishTestResults@2` | same; no test-report artifact (pre-existing gap preserved) |

## Secrets required

None. The workflow uses no `${{ secrets.* }}`. If the ACR binding turns out to be live (e.g. an ADO-side or classic-release docker push), `ACR_USERNAME`/`ACR_PASSWORD` (or OIDC to `contosofinancial.azurecr.io`) would need to be added along with the missing docker step.

## Validation baselines

`validation/baselines/market-sim/{expected-artifacts.json,test-counts.json}` were added so `validate-migration` can score this workflow. Both are marked `"status": "provisional"`: the Rust sources are not in this repository and the ADO API dump carries no test counts, so `expected_total_tests` is `0` and the artifact baseline is inferred from the YAML (one `market-sim` binary). team-quant must replace them with numbers from a real ADO run.

## Known gaps / open questions for the owner

1. **Real deploy mechanism unknown.** The ADO Deploy stage is two `echo` lines. Whatever actually ships `market-sim` to the compute cluster is outside this pipeline (and outside D2). Confirm the mechanism before ADO 108 is switched off; if it is a classic release consuming the `market-sim-binary` artifact, a GHA equivalent (or artifact hand-off) is needed.
2. **`ContainerRegistry-ACR` binding.** Bound in ADO but unused in YAML. Confirm dead before dropping; if live, the docker build/push step is missing from both ADO YAML and this workflow.
3. **Rust sources not in this repo.** `services/market-sim/` contains only the pipeline YAML, so this workflow cannot be exercised here; first real run must happen where `Cargo.toml` lives.
4. **Owner confidence low.** `team-quant?` in the YAML header; inventory lists team-quant. Confirm ownership.
5. **No test reporting.** Neither ADO nor GHA publishes structured test results; preserved as-is. Optional follow-up: `cargo test -- -Z unstable-options --format junit` or `cargo-nextest` + `dorny/test-reporter`.
6. **Toolchain drift.** Both pipelines install `stable` at run time (no `rust-toolchain.toml`), so builds are not reproducible across toolchain releases. Pre-existing; preserved.
7. **PR trigger added.** Intentional divergence from ADO; deploy remains push-to-main only.
