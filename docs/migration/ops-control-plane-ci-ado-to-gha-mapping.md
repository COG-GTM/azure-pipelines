# ops-control-plane-ci: ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | 109 `ops-control-plane-ci` — `services/ops-control-plane/azure-pipelines.yml` |
| GHA workflow | `.github/workflows/ops-control-plane-ci.yml` |
| Owner | platform-team |
| Track / wave | C (inline build), Wave 0 |
| Template source | none — inline YAML, no `resources.repositories`, no `template:` references (central `templates/build-go.yml` is unused by this pipeline) |
| Composite actions | none. The build is translated step-for-step; `ado-env-shim` is not on `main` yet, so the ADO variables are exported inline in a `run` step |
| Plan ownership row | `.github/workflows/ops-control-plane-ci.yml`, `docs/migration/ops-control-plane-ci-*.md`, `validation/baselines/ops-control-plane/` |
| Supersedes | draft PR #13 (input only; this PR is a fresh branch from `origin/main`) |

## Triggers

| ADO | GHA |
|---|---|
| `trigger.branches.include: [main]` | `on.push.branches: [main]` |
| `trigger.paths.include: services/ops-control-plane/**` | `on.push.paths` — same path plus `.github/workflows/ops-control-plane-ci.yml` and `.github/actions/**` |
| (none) | `on.pull_request.branches: [main]` with the same paths (added for PR feedback) |
| (none) | `on.workflow_dispatch` |

## Stage → job

| # | ADO stage (`displayName`) | ADO job | GHA job id | GHA `name` | `needs` | `if` | `environment` |
|---|---|---|---|---|---|---|---|
| 1 | `Build` (`Build ops-control-plane`) | `build_go` (`Go build and test`) | `build` | `Build ops-control-plane` | — | — | — |

1 ADO stage → 1 GHA job, same order. No deployment stage exists in the ADO YAML, so no
`environment:` job and no `release-standard` call.

## Step → step

| ADO step (`displayName`) | ADO task / script | GHA step | GHA implementation |
|---|---|---|---|
| (implicit checkout) | `checkout: self` | `Check out source` | `actions/checkout@v4` |
| (none) | — | `Set ADO compatibility variables` | inline `run` exporting the same variables `.github/actions/ado-env-shim` sets (`BUILD_*`, `AGENT_*`, `SYSTEM_*`) plus `GOPATH`/`GOBIN`; creates `$RUNNER_TEMP/staging` |
| `Install Go 1.22` | `GoTool@0` `version: '1.22'` | `Install Go 1.22` | `actions/setup-go@v5` `go-version: 1.22`, `cache-dependency-path: services/ops-control-plane/go.sum` |
| `Download modules` | `go mod download && go mod verify` | `Download modules` | same script |
| `Vet` | `go vet ./...` | `Vet` | same script |
| `Run tests` | `go test ./... -v -coverprofile=coverage.out` | `Run tests` | same script |
| `Build binary` | `CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(Build.ArtifactStagingDirectory)/ops-control-plane ./cmd/server` | `Build binary` | same script with `$BUILD_ARTIFACTSTAGINGDIRECTORY` |
| `Publish binary` | `PublishBuildArtifacts@1` `pathToPublish: $(Build.ArtifactStagingDirectory)`, `artifactName: ops-control-plane-binary` | `Publish binary` | `actions/upload-artifact@v4` `name: ops-control-plane-binary`, `path: ${{ runner.temp }}/staging`, `if-no-files-found: error` |

`workingDirectory: $(modulePath)` on every ADO script → `defaults.run.working-directory: services/ops-control-plane`
on the job (the shim step overrides it back to `${{ github.workspace }}`).

## ADO variables → GHA

| ADO | GHA |
|---|---|
| `pool.vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` |
| `variables.modulePath` | `env.MODULE_PATH` / `defaults.run.working-directory` |
| `variables.GOPATH: $(system.defaultWorkingDirectory)/go` | `GOPATH=$GITHUB_WORKSPACE/go` (exported by the shim step) |
| `variables.GOBIN: $(GOPATH)/bin` | `GOBIN=$GITHUB_WORKSPACE/go/bin` (exported by the shim step) |
| `$(Build.ArtifactStagingDirectory)` | `$BUILD_ARTIFACTSTAGINGDIRECTORY` = `$RUNNER_TEMP/staging` |
| `$(Build.BuildId)` | `$BUILD_BUILDID` = `$GITHUB_RUN_ID` |
| `$(Build.SourcesDirectory)` | `$BUILD_SOURCESDIRECTORY` = `$GITHUB_WORKSPACE` |
| `GoTool@0` | `actions/setup-go@v5` |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` |

## Integration points

The inline ADO YAML calls none of the `build-tools/` integration scripts (`publish_artifact.py`,
`notify_release_orchestrator.py`, `generate_attestation.py`, `generate_metadata.py`,
`normalize_test_results.py`). Therefore:

- Artifactory, D2, attestation-database: **not required** and not added (the validator reports them
  "not in ADO source — not required").
- Test Results: required (`go test`) and satisfied by the `Run tests` step.
- No `artifact-registry` / `release-orchestrator` / `compliance-store` → `main` renames apply
  because no branch-resolved template is consumed.

## Intentionally not ported

| Item | Reason |
|---|---|
| Kubernetes deploy via VG 211 `ops-infra-credentials` (`k8s.internal…:6443` token) | **Track A blocker A4 is unresolved.** The binding is attached to ADO pipeline 109 but no step in the YAML uses it; it is either dead or consumed by an ADO-side classic release. No `kubectl` deploy job, GH environment, or secret is created. Once A4 is answered: if dead → drop the binding in ADO; if live → add a `deploy` job with `environment:` + `./.github/actions/release-standard` in a follow-up PR. |
| ACR service connection `ContainerRegistry-ACR` | Bound per the API dump but the YAML has no docker step (inventory §5.1). Same A4 disposition. |
| Variable group `shared-ci-secrets` (VG 201) | Package-feed credentials; `go mod download` here has no private module dependencies (`go.sum` verifies with the public proxy), so no secret is needed. |
| `coverage.out` upload | ADO never published it (no `PublishCodeCoverageResults`); the file is produced by `Run tests` for parity but not uploaded. |

## Baselines

`validation/baselines/ops-control-plane/` — measured locally on `main` from the scaffold in
`services/ops-control-plane/`:

- `test-counts.json`: 7 tests (`TestRegistryOperations` + 6 subtests), 1 suite, 38.3 % total
  statement coverage.
- `expected-artifacts.json`: 1 extensionless static binary `ops-control-plane`, 5,980,322 bytes.
