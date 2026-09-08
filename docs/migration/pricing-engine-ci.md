# Pricing Engine CI Migration

- **Source pipeline:** `services/pricing-engine/azure-pipelines.yml`
- **Template reference:** `main` @ `e5d8164`
- **Target workflow:** `.github/workflows/pricing-engine-ci.yml`
- **Inventory classification:** Migrate / pilot
- **Pipeline ID:** 101
- **Owner:** unknown — blocker noted

## Mapping

| ADO concept | GitHub Actions equivalent |
|---|---|
| Trigger: `main`, `release/*`, service path | `push` on `main`, `release/**` with service, workflow, and helper-script paths |
| Pull request trigger | `pull_request` on `main` with the same paths |
| Manual trigger | `workflow_dispatch` |
| Pool: `ubuntu-latest` | `runs-on: ubuntu-latest` |
| `buildConfiguration` / `artifactName` / .NET version / solution | Workflow-level `env` |

| ADO stage | GHA job |
|---|---|
| Build | `build` — checkout, `UseDotNet@2` → `setup-dotnet@v4`, `NuGetToolInstaller@1` and `NuGetCommand@2` → `dotnet restore`, `DotNetCoreCLI@2 build` → `dotnet build`, `DotNetCoreCLI@2 publish` → `dotnet publish`, `PublishBuildArtifacts@1` → `upload-artifact`, and artifact registration script |
| Test | `test` — checkout, setup .NET, test execution, normalization, and test-result artifact upload |
| Deploy_Dev | `deploy-dev` — `deployment:` with `runOnce` → `environment: dev`, `download: current` → `download-artifact`, deployment, D2 notification, attestation, and attestation artifact upload |

The ADO `testFramework: generic` path does not execute a framework-specific test command; its Test stage only publishes and normalizes results. The migrated workflow runs the solution tests once in `test`.

## Verified run

PR #3, run `34270151695`: build and test were green. The drop contained 9 files: `PricingEngine.dll`, `PricingEngine.pdb`, `PricingEngine.deps.json`, `PricingEngine.runtimeconfig.json`, `PricingEngine.staticwebassets.endpoints.json`, `PricingEngine` (apphost), `appsettings.json`, `web.config`, and `pricing-engine-drop-manifest.json`. The test artifact contained `coverage.cobertura.xml`; 36/36 xunit tests passed.

`compare_artifacts.py` reported FAIL for 9 vs 12 files, 0.11 MB vs 5–50 MB, and no `.xml` in the drop. `compare_test_counts.py` reported FAIL for count (36 vs 187) but PASS for pass rate. Both reflect baselines dated 2024-08-15 from the original service rather than the in-repo scaffold. The comparison steps are informational and `continue-on-error` until baselines are refreshed against a real ADO run. `deploy-dev` was not exercised because it runs only on pushes to `main`.

## Environment variable mapping

| ADO variable | GHA equivalent used by `ci_context.py` |
|---|---|
| `BUILD_SOURCEBRANCH` | `GITHUB_REF` |
| `BUILD_SOURCEVERSION` | `GITHUB_SHA` |
| `AGENT_NAME` | `RUNNER_NAME` |
| `BUILD_DEFINITIONNAME` | `GITHUB_WORKFLOW` |
| `AGENT_OS` | `RUNNER_OS` |
| `BUILD_REQUESTEDFOR` | `GITHUB_ACTOR` |
| `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` + `SYSTEM_TEAMPROJECT` + `BUILD_BUILDID` | `GITHUB_SERVER_URL` + `GITHUB_REPOSITORY` + `GITHUB_RUN_ID` |
| `BUILD_ARTIFACTSTAGINGDIRECTORY` | `RUNNER_TEMP` |
| `TF_BUILD` | `GITHUB_ACTIONS` |

## Intentional deviations

- Tests run once in `test` instead of in Build. The build template ran tests in Build, while the ADO Test stage with `testFramework: generic` executes no tests and only publishes/normalizes.
- `NuGetToolInstaller@1` and `NuGetCommand@2` are replaced by `dotnet restore`.
- The workflow emits VSTest TRX results instead of JUnit; `normalize_test_results.py` now supports TRX.
- `PublishTestResults@2` has no native GHA equivalent; results are uploaded as an artifact.
- ADO `environment: dev` approvals must be recreated as a protected GitHub environment named `dev`.
- `Build.BuildId` maps to `github.run_id`.
- Triggers are a superset of ADO: `pull_request` is added because the Azure Repos pipeline had no `pr:` trigger and PR validation there is a branch policy. Paths are widened to include the workflow file and `build-tools/scripts/**`.
- GHA uses `release/**` rather than ADO `release/*`; `release/*` would not match nested refs, so `**` is the deliberate superset.

## Open items

- Owner is unknown (§4 of the inventory); ownership remains a blocker.
- Artifactory, D2, and attestation scripts are stubs. Real credentials (VG 205/206 → GitHub secrets) are not wired.
- `test-counts.json` says 187 tests, but the scaffold has approximately 38; refresh the baseline.

## Setup prerequisites

No GitHub environment named `dev` exists in `COG-GTM/azure-pipelines` yet. GitHub Actions will auto-create it unprotected on the first deployment, so configure protection rules and reviewers before the first push to `main` if the ADO `dev` environment had approvals. Add the Artifactory, D2, and attestation credentials as GitHub secrets when the integrations are implemented.

## Validation

The `validate-migration` workflow runs on pull requests changing `.github/workflows/` and validates actionlint, migration parity, and the scorecard. Locally:

```sh
actionlint .github/workflows/pricing-engine-ci.yml
python3 validation/scripts/validate_migration.py \
  --service pricing-engine \
  --ado-pipeline services/pricing-engine/azure-pipelines.yml \
  --gha-workflow .github/workflows/pricing-engine-ci.yml \
  --baselines validation/baselines
```
