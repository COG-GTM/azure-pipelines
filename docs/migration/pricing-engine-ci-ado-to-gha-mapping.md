# Pricing Engine ADO-to-GHA Mapping

| ADO stage or template step | GitHub Actions job or composite-action step |
| --- | --- |
| `Build` stage | `build` job, named `Build pricing-engine` |
| `build-dotnet.yml` / Install .NET SDK | `build-dotnet` / `Install .NET SDK` |
| `build-dotnet.yml` / Restore NuGet packages | `build-dotnet` / `Restore NuGet packages` |
| `build-dotnet.yml` / Build solution | `build-dotnet` / `Build solution` |
| `build-dotnet.yml` / Run unit tests | `build-dotnet` / `Run unit tests` |
| `build-dotnet.yml` / Publish artifacts | `build-dotnet` / `Publish artifacts` |
| `build-dotnet.yml` / Upload build artifacts | `build-dotnet` / `Upload build artifacts` |
| `build-dotnet.yml` / Register artifact in Artifactory | `build-dotnet` / `Register artifact in Artifactory` |
| `Test` stage | `test` job, named `Run tests` |
| `run-tests.yml` / Create test results directory | `run-tests` / `Create test results directory` |
| `run-tests.yml` / Publish test results | `run-tests` / `Publish test results` |
| `run-tests.yml` / Normalize test results | `run-tests` / `Normalize test results` |
| `Deploy_Dev` stage and `deployment: runOnce` | `deploy_dev` job with `environment: dev` |
| `release-standard.yml` / Download artifact | `release-standard` / `Download artifact` |
| `release-standard.yml` / Execute deployment | `release-standard` / `Execute deployment` |
| `release-standard.yml` / Notify D2 | `release-standard` / `Notify D2` |
| `release-standard.yml` / Generate compliance attestation | `release-standard` / `Generate compliance attestation` |

## ADO variable mapping

| ADO variable | GHA environment-shim value |
| --- | --- |
| `BUILD_SOURCEBRANCH` | `GITHUB_REF` |
| `BUILD_SOURCEVERSION` | `GITHUB_SHA` |
| `BUILD_BUILDID` | `GITHUB_RUN_ID` |
| `BUILD_DEFINITIONNAME` | `GITHUB_WORKFLOW` |
| `BUILD_REPOSITORY_NAME` | `GITHUB_REPOSITORY` |
| `BUILD_REQUESTEDFOR` | `GITHUB_ACTOR` |
| `BUILD_SOURCESDIRECTORY` | `GITHUB_WORKSPACE` |
| `BUILD_ARTIFACTSTAGINGDIRECTORY` | `$RUNNER_TEMP/staging` |
| `AGENT_NAME` | `RUNNER_NAME` |
| `AGENT_OS` | `RUNNER_OS` |
| `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` | `$GITHUB_SERVER_URL/` |
| `SYSTEM_TEAMPROJECT` | `GITHUB_REPOSITORY` |

NuGetToolInstaller and NuGetCommand are collapsed into `dotnet restore`.
PublishTestResults@2 is represented by test-result artifact upload.
The ADO deployment `runOnce` strategy is represented by a job with `environment:`.
