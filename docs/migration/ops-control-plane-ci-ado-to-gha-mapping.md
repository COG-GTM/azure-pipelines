# ops-control-plane-ci — ADO → GitHub Actions mapping

- **ADO pipeline:** `ops-control-plane-ci` (ID 109), `services/ops-control-plane/azure-pipelines.yml`
- **Category:** 4 — Custom inline (no shared or alt templates; central `templates/build/build-go.yml` is unused)
- **Pool:** `Azure Pipelines` hosted, `ubuntu-latest`
- **Owner:** platform-team (high confidence, `docs/ownership-gaps.md`)
- **90-day history:** 25 runs (24 ok / 1 failed), 7.8 min avg, last run 2026-03-13 (build 98100)
- **Target workflow:** `.github/workflows/ops-control-plane-ci.yml`
- **Template resolution:** not required — nothing to inline. The playbook's ADO MCP verification (`pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml`) could not be attempted: the `azure-devops-mcp` server failed to start in this session. Pipeline metadata was taken from `docs/samples/ado-api-responses.json` and `docs/pipeline-inventory-report.md` instead.

## Trigger mapping

| ADO | GHA | Notes |
|---|---|---|
| `trigger.branches.include: [main]` | `on.push.branches: [main]` | Same |
| `trigger.paths.include: [services/ops-control-plane/**]` | `on.push.paths: services/ops-control-plane/**` + the workflow file itself | Workflow path added so workflow edits are exercised |
| (none) | `on.pull_request.branches: [main]` with the same paths | **Intentional addition** — ADO had no PR validation |
| (none) | `workflow_dispatch` | Intentional addition for manual re-runs |
| (none) | `concurrency` group per ref, cancel-in-progress on PRs only | Intentional addition |

## Stage / job mapping

| ADO stage → job | GHA job | `needs` | Condition |
|---|---|---|---|
| `Build` → `build_go` ("Go build and test") | `build` ("Build ops-control-plane") | — | none (same as ADO) |

There is exactly one stage and one job in ADO; the workflow has exactly one job. No deploy stage exists in the ADO YAML and **none was invented** (see "Dead bindings" below).

## Step / task mapping

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 0 | (implicit checkout) | `actions/checkout@v4` | ADO checks out `self` implicitly |
| 1 | `GoTool@0` `version: '1.22'` | `actions/setup-go@v5` `go-version: '1.22'` | `cache-dependency-path: services/ops-control-plane/go.sum` so the module cache key is scoped to this module |
| 2 | `script: go mod download && go mod verify` (`workingDirectory: $(modulePath)`) | `run: go mod download; go mod verify` | Job-level `defaults.run.working-directory: services/ops-control-plane` replaces per-step `workingDirectory` |
| 3 | `script: go vet ./...` | `run: go vet ./...` | Identical |
| 4 | `script: go test ./... -v -coverprofile=coverage.out` | `run: go test ./... -v -coverprofile=coverage.out` | Identical. `coverage.out` is written to the module dir and — as in ADO — **not** published |
| 5 | `script: CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(Build.ArtifactStagingDirectory)/ops-control-plane ./cmd/server` | Same command with `$BUILD_ARTIFACTSTAGINGDIRECTORY`, preceded by `mkdir -p` | ADO pre-creates the staging dir; GHA runners do not, hence `mkdir -p` |
| 6 | `PublishBuildArtifacts@1` `pathToPublish: $(Build.ArtifactStagingDirectory)`, `artifactName: ops-control-plane-binary` | `actions/upload-artifact@v4` `name: ops-control-plane-binary`, `path: ${{ runner.temp }}/staging`, `if-no-files-found: error` | Artifact name preserved |
| — | (none) | `Integration notes (...)` — `if: always()`, writes to `$GITHUB_STEP_SUMMARY` | **Not an ADO step.** Records that Artifactory / D2 / attestation integrations do not exist in pipeline 109 so the run summary (and the `validate-migration` integration-point check) makes that explicit rather than silently reporting them as missing. Remove if the team prefers a strictly step-for-step workflow. |

Every mapped step in the workflow carries a `# --- mapped from: ... ---` comment.

## Variable mapping

| ADO variable | GHA | Notes |
|---|---|---|
| `GOPATH: $(system.defaultWorkingDirectory)/go` | `env.GOPATH: ${{ github.workspace }}/go` | Same relative layout |
| `GOBIN: $(GOPATH)/bin` | `env.GOBIN: ${{ github.workspace }}/go/bin` | GHA `env` cannot self-reference, so expanded literally |
| `modulePath: services/ops-control-plane` | `env.MODULE_PATH` + `defaults.run.working-directory` | |
| `$(Build.ArtifactStagingDirectory)` | step-level `env.BUILD_ARTIFACTSTAGINGDIRECTORY: ${{ runner.temp }}/staging` on "Build binary" | Shim keeps the build command byte-for-byte equivalent |
| Variable group `shared-ci-secrets` (VG 201) | none | Not referenced by any step in the YAML — nothing to map |
| Variable group `ops-infra-credentials` (VG 211) | none | See "Dead bindings" |

No `$(Build.SourceBranch)` / `$(Build.BuildId)` / URL-constructing helper scripts are used by this pipeline, so no further ADO→GHA env shims and **no `build-tools/scripts/*.py` changes** were needed.

## Condition mapping

The ADO pipeline has no `condition:` expressions. The only `if:` in the workflow is `if: always()` on the informational summary step.

## Integration points

| Integration | ADO pipeline 109 | GHA workflow |
|---|---|---|
| Artifactory registration (`publish_artifact.py`) | Not used | Not added |
| D2 / release-orchestrator notification | Not used | Not added |
| Compliance attestation (`generate_attestation.py`) | Not used | Not added |
| Test results (`PublishTestResults@2`) | Not used — `go test -v` output is only in the log | Same; `coverage.out` not uploaded (parity). Optional follow-up: upload `coverage.out` / add `gotestsum` JUnit output |
| Build artifact | `PublishBuildArtifacts@1` → `ops-control-plane-binary` | `actions/upload-artifact@v4` → `ops-control-plane-binary` |

## Dead bindings (documented, not migrated)

The ADO API dump (`docs/samples/ado-api-responses.json`) shows two resources attached to definition 109 that its YAML never references:

| Binding | Contents | Assessment |
|---|---|---|
| Variable group 211 `ops-infra-credentials` | `K8S_CLUSTER_URL=https://k8s.internal.contoso-financial.com:6443`, `K8S_SERVICE_ACCOUNT_TOKEN` (secret), `K8S_NAMESPACE=ops-platform` | No step reads these. Either a stale binding, or an ADO **classic release** (not in this repo) consumes the `ops-control-plane-binary` artifact and deploys to the `ops-platform` namespace. |
| Service connection `ContainerRegistry-ACR` (`contosofinancial.azurecr.io`) | Docker registry SPN | No `Docker@2` / `docker` step in the YAML. Same two possibilities as above. |

No deploy job was created. If a classic release exists, it will lose its artifact source when the ADO pipeline is retired and must be replaced by a GHA deploy job (`environment:` with protection rules, `secrets.K8S_SERVICE_ACCOUNT_TOKEN`, OIDC to ACR) in a follow-up owned by platform-team.

## Known gaps / behavioral differences

1. **Go source is not in this repository.** `services/ops-control-plane/` contains only `azure-pipelines.yml` — no `go.mod`, `go.sum`, or `cmd/server`. The workflow is a faithful translation but its first real run will fail at `actions/setup-go` (missing `go.sum` for cache) / `go mod download` until the module is present. This is also why the validation baselines under `validation/baselines/ops-control-plane/` are marked provisional with unmeasured test counts.
2. **Dead bindings** (above) — a hidden ADO-side deploy may exist.
3. **Retention:** ADO kept builds 30 days / min 5. `upload-artifact@v4` uses the repository default (90 days) unless `retention-days` is set.
4. **PR trigger added** — the ADO pipeline only ran on `main` pushes. PR runs produce and upload an artifact too (no Artifactory registration exists to guard).
5. **Extra summary step** — one informational step that has no ADO counterpart (see step table).
6. **Test visibility:** no test-results viewer in either system; parity preserved.

## Secrets required

None. The workflow uses only `GITHUB_TOKEN` defaults (`permissions: contents: read`). If the deploy follow-up is implemented, `K8S_SERVICE_ACCOUNT_TOKEN` (from VG 211) and ACR credentials / OIDC federation would be needed.

## Helper script changes

None. `build-tools/scripts/*.py` are not invoked by this pipeline.

## Validation

```sh
actionlint .github/workflows/ops-control-plane-ci.yml
python3 validation/scripts/validate_migration.py \
  --service ops-control-plane \
  --ado-pipeline services/ops-control-plane/azure-pipelines.yml \
  --gha-workflow .github/workflows/ops-control-plane-ci.yml \
  --baselines validation/baselines
```

## Open questions for platform-team

- Is there an ADO classic release consuming `ops-control-plane-binary` (VG 211 / ACR bindings)? If yes, what does it deploy and where?
- Where does the Go module live? It must be added to (or the path filter pointed at) this repository before the workflow can go green.
- Confirm real test count / binary size for the provisional baselines.
- Should `coverage.out` be uploaded as an artifact now that it is cheap to do so?
- Is 90-day artifact retention acceptable, or should `retention-days: 30` be set to match ADO?
