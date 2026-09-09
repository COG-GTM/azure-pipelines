# ops-control-plane-ci — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `ops-control-plane-ci` (ID 109) |
| ADO YAML | `services/ops-control-plane/azure-pipelines.yml` |
| Category | 4 — Custom inline (Go 1.22), no shared templates |
| Template ref | none (inline); `resources.repositories` absent, no `template:` references |
| Owner | platform-team (high confidence) |
| Pool | `Azure Pipelines` hosted, `ubuntu-latest` |
| Run history | 25 runs (24 succeeded / 1 failed), 7.8 min avg, last run 2026-03-13 |
| GHA workflow | `.github/workflows/ops-control-plane-ci.yml` |

ADO MCP verification (`pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml` on org `shawn0864`) was attempted but the
`azure-devops-mcp` server failed to start in this session. Because the pipeline is fully inline there is nothing to expand;
the YAML in the repo was used as the source of truth.

## 1. Trigger mapping

| ADO | GHA | Notes |
|---|---|---|
| `trigger.branches.include: [main]` | `on.push.branches: [main]` | 1:1 |
| `trigger.paths.include: [services/ops-control-plane/**]` | `on.push.paths: ['services/ops-control-plane/**', '.github/workflows/ops-control-plane-ci.yml']` | Service path 1:1; **workflow's own path added** so workflow-only changes exercise the build |
| *(no `pr:` block)* | `on.pull_request` (branches `main`, same paths) | **Intentional addition** — earlier CI feedback on PRs |
| *(manual run via ADO UI)* | `on.workflow_dispatch` | Preserves ability to run manually |

## 2. Stage → job mapping

| ADO stage / job | GHA job | `runs-on` | `needs` |
|---|---|---|---|
| `Build` / `build_go` ("Go build and test") | `build` ("Build ops-control-plane") | `ubuntu-latest` | — |

There is exactly one stage in ADO and one job in GHA. No deployment job is created (see §6).

## 3. Step / task mapping

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 0 | *(implicit checkout)* | `actions/checkout@v4` | ADO checks out `self` automatically; GHA needs it explicitly |
| 1 | `GoTool@0` `version: '1.22'` | `actions/setup-go@v5` `go-version: 1.22`, `cache-dependency-path: services/ops-control-plane/go.sum` | Module cache is a GHA addition (setup-go default); no behavioural change |
| 2 | `script` "Download modules": `go mod download && go mod verify` | `run` "Download modules" | Identical commands |
| 3 | `script` "Vet": `go vet ./...` | `run` "Vet" | Identical |
| 4 | `script` "Run tests": `go test ./... -v -coverprofile=coverage.out` | `run` "Run tests" | Identical |
| — | *(none)* | `actions/upload-artifact@v4` "Upload coverage profile" (`if: always()`) | **Addition** — ADO discards `coverage.out`; GHA keeps it as `ops-control-plane-coverage` |
| 5 | `script` "Build binary": `CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(Build.ArtifactStagingDirectory)/ops-control-plane ./cmd/server` | `run` "Build binary" with `mkdir -p "$STAGING_DIR"` then the same build command targeting `$STAGING_DIR/ops-control-plane` | `Build.ArtifactStagingDirectory` is pre-created on ADO agents; GHA needs `mkdir -p` |
| 6 | `PublishBuildArtifacts@1` `pathToPublish: $(Build.ArtifactStagingDirectory)`, `artifactName: ops-control-plane-binary` | `actions/upload-artifact@v4` `name: ops-control-plane-binary`, `path: ${{ env.STAGING_DIR }}`, `if-no-files-found: error` | Same artifact name; download via `actions/download-artifact` or run UI |

All ADO `workingDirectory: $(modulePath)` inputs are covered by the job-level `defaults.run.working-directory: services/ops-control-plane`.

## 4. Variable mapping

| ADO variable | GHA | Notes |
|---|---|---|
| `modulePath: services/ops-control-plane` | `env.MODULE_PATH` + `defaults.run.working-directory` | GHA `defaults` cannot reference `env`, so the path is literal there |
| `GOPATH: $(system.defaultWorkingDirectory)/go` | *(dropped)* | `actions/setup-go` manages `GOPATH`; the ADO value was never referenced by any step |
| `GOBIN: $(GOPATH)/bin` | *(dropped)* | Same — unused by any step |
| `$(Build.ArtifactStagingDirectory)` | `env.STAGING_DIR = ${{ github.workspace }}/staging` | Created with `mkdir -p` in the build step |
| `$(Build.SourceBranch)` | `env.BUILD_SOURCEBRANCH = ${{ github.ref }}` | Shim only; no script consumes it |
| `$(Build.SourceVersion)` | `env.BUILD_SOURCEVERSION = ${{ github.sha }}` | Shim only |
| `$(Build.BuildId)` | `env.BUILD_BUILDID = ${{ github.run_id }}` | Shim only |
| *(ADO `_build/results?buildId=` URL)* | `env.PIPELINE_URL = ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` | Provided for parity with other migrated workflows |

## 5. Condition mapping

The ADO pipeline has no `condition:` on any stage, job or step. The only GHA condition added is `if: always()` on the
coverage-profile upload so the profile is captured when tests fail.

## 6. Integration points

| Integration | ADO | GHA |
|---|---|---|
| Build artifact | `PublishBuildArtifacts@1` → `ops-control-plane-binary` | `actions/upload-artifact@v4` → `ops-control-plane-binary` |
| Test results | none (`go test -v` output to log only, no `PublishTestResults@2`) | Same; log only. Coverage profile additionally uploaded |
| Artifactory / `publish_artifact.py` | not used | not applicable |
| D2 release orchestrator notification | not used | not applicable |
| Compliance attestation | not used | not applicable |
| **VG 211 `ops-infra-credentials`** (K8s token, `k8s.internal…:6443`) | Bound to pipeline 109 in the ADO API dump, but **no step in the YAML references any of its variables** and there is no `deployment` job | **Not migrated.** No deploy job was invented. Either (a) the binding is dead, or (b) an ADO-side *classic release* definition consumes the `ops-control-plane-binary` artifact and this VG. **Decision needed from platform-team** — see "Open decisions" |
| ACR `ContainerRegistry-ACR` service connection | Bound per API dump; no `Docker@2` step in YAML | Not migrated; same stale-or-external question as above |
| VG 201 `shared-ci-secrets` (package feeds) | Bound; `go mod download` uses the public proxy, no `GOPRIVATE`/`GOPROXY` override in YAML | Not needed; no secret referenced |

## 7. Known gaps / behavioural differences

- **`on.pull_request` and `workflow_dispatch` added** — the ADO pipeline only ran on `main` pushes.
- **Coverage artifact added** — `coverage.out` was produced but discarded in ADO.
- **`GOPATH`/`GOBIN` variables dropped** — unused in ADO; `actions/setup-go` sets its own `GOPATH`.
- **Go patch version** — `GoTool@0` with `1.22` and `actions/setup-go@v5` with `1.22` both resolve to the latest 1.22.x; identical semantics. `go.mod` declares `go 1.22`.
- **Module cache** — `setup-go` caches `~/go/pkg/mod` keyed on `go.sum`; ADO had no cache. Build output is unaffected.
- **Post-build consumer** — if a classic ADO release currently downloads `ops-control-plane-binary`, it will not see GHA
  artifacts. That consumer must be identified before the ADO pipeline is disabled.

## 8. Secrets required

None. The workflow uses no `${{ secrets.* }}` references; `GITHUB_TOKEN` (default, `contents: read`) suffices for
checkout and artifact upload.

## 9. Helper script changes

None required. The pipeline calls no `build-tools/scripts/*` helper.

## 10. Validation baselines

`validate-migration` requires `validation/baselines/<service>/{expected-artifacts.json,test-counts.json}`. Both were
added for `ops-control-plane`, measured from a local run of the exact ADO commands on `main`:

- Artifact: 1 file (`ops-control-plane`, static ELF, 5.98 MB) → range 4–12 MB.
- Tests: `TestRegistryOperations` with 6 subtests = 7 `go test -v` entries, 100 % pass; total statement coverage 38.3 %
  (100 % in `internal/controls`, 0 % in `cmd/server`).

## Open decisions

1. **`ops-infra-credentials` / ACR bindings** — platform-team to confirm whether a classic release consumes the artifact.
   If yes, a follow-up GHA deploy job (with a `ops-infra` GitHub environment and `KUBE_TOKEN` secret) is needed before
   the ADO pipeline is retired. If no, remove both bindings in ADO.
2. **Coverage upload** — keep as a GHA-only improvement or drop for strict parity.
