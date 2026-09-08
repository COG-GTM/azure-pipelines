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

## Open items

- Owner is unknown (§4 of the inventory); ownership remains a blocker.
- Artifactory, D2, and attestation scripts are stubs. Real credentials (VG 205/206 → GitHub secrets) are not wired.
- `test-counts.json` says 187 tests, but the scaffold has approximately 38; refresh the baseline.
- `release/*` triggers are preserved.

## Setup prerequisites

Create the GitHub `dev` environment and reproduce the required approval rules. Add the Artifactory, D2, and attestation credentials as GitHub secrets when the integrations are implemented.

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
