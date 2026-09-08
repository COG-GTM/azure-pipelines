# portfolio-api-ci — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `portfolio-api-ci` (ID **102**) — `services/portfolio-api/azure-pipelines.yml` |
| GHA workflow | `.github/workflows/portfolio-api-ci.yml` |
| Category | 1 — central template consumer (Java 17 / Maven) |
| Template source | `shared-ci-platform` @ **`master`** (legacy template set) |
| Templates inlined | `templates/build/build-java.yml`, `templates/release/release-standard.yml` (both read from `origin/master`) |
| Owner | team-quant (medium confidence — `j.chen@contoso.com`) |
| Runs (90 d) | 31 (29 succeeded / 2 failed), avg 9.8 min |

Behaviour was taken from the `master` templates (what actually runs today). Integration steps are named per the `main` scripts/templates (Artifactory, D2, attestation-database) because those are the scripts that exist in this repo. Every `master` ↔ `main` difference is listed in [Known gaps](#known-gaps--master-vs-main-template-differences).

ADO MCP verification (`pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml`) was attempted but the `azure-devops-mcp` server failed to start in this session; templates were expanded manually from `origin/master`.

## Trigger mapping

| ADO | GHA | Note |
|---|---|---|
| `trigger.branches.include: [main, master]` | `on.push.branches: [main, master]` | Both source branches preserved as requested |
| `trigger.paths.include: services/portfolio-api/**` | `on.push.paths: services/portfolio-api/**` + the workflow file + the three helper scripts it runs | Paths added so workflow/helper edits get CI (ADO only watched the service dir) |
| *(no PR trigger)* | `on.pull_request.branches: [main, master]` (same paths) | **Intentional addition** for earlier feedback. PR runs build + test only; deploy/registration are push-gated |
| *(none)* | `workflow_dispatch` | Manual build-only check: registration and `deploy-staging` are gated on `push`, so a manual run never registers or deploys |
| — | `concurrency` group per ref, cancel-in-progress on PRs only | New; no ADO equivalent |

## Stage → job mapping

| ADO stage / job | GHA job | `needs` | Condition | Environment |
|---|---|---|---|---|
| `Build` / `build` (`build-java.yml@master`) | `build` — "Build portfolio-api" | — | always | — |
| `Release` → `Deploy_staging` / deployment `deploy` (`release-standard.yml@master`) | `deploy-staging` — "Deploy to staging" | `build` | `github.event_name == 'push'` | `staging` |

Note: `release-standard.yml` is a *stages* template, so in ADO the `Release` stage wrapper actually expands to a stage named `Deploy_staging`. GHA has one job for it.

## Step / task mapping

### `build` job (from `templates/build/build-java.yml@master`, parameters: `jdkVersion=17`, `mavenGoal=package`, `mavenOptions=-B -DskipTests=false` (default), `runTests=true` (default), `publishArtifacts=true` (default), `artifactName=portfolio-api-dist`)

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 0 | *(implicit checkout)* | `actions/checkout@v4` | |
| 1 | `JavaToolInstaller@0` `versionSpec=17`, `jdkArchitectureOption=x64`, `jdkSourceOption=PreInstalled` | `Check for Maven project` → `actions/setup-java@v4` with `distribution=temurin`, `java-version=17`; Maven cache is enabled only when `pom.xml` is present | PreInstalled JDK on hosted agent → Temurin from setup-java. Maven dependency cache added when a project is available (no ADO equivalent); the no-source path avoids setup-java's POM lookup |
| 2 | `Maven@4` `mavenPomFile=pom.xml`, `goals=package`, `options=-B -DskipTests=false` | `Check for Maven project` → conditional `run: mvn -f pom.xml $MAVEN_OPTIONS $MAVEN_GOAL` with `working-directory: services/portfolio-api` | Missing source is expected in this repository; the Maven build is skipped until `pom.xml` is present (see gap **G1b**) |
| 3 | `Maven@4` `publishJUnitResults=true`, `testResultsFiles=**/surefire-reports/TEST-*.xml` | `Collect JUnit test results` (`find … -path '*/surefire-reports/TEST-*.xml' -exec cp --parents`, preserving module paths) + `actions/upload-artifact@v4` `portfolio-api-test-results`, both `if: always()` | `**` glob replaced by `find`. No native test tab in GHA — results are an artifact (see G6) |
| 4 | `script` "Stage build artifacts" (`cp target/*.jar|*.war $(Build.ArtifactStagingDirectory)/`) | same `cp` into `$RUNNER_TEMP/staging` with `mkdir -p` first | Runs only when the Maven project is present; `2>/dev/null \|\| true` preserved verbatim |
| 5 | `PublishBuildArtifacts@1` `pathToPublish=$(Build.ArtifactStagingDirectory)`, `artifactName=portfolio-api-dist` | `actions/upload-artifact@v4` `name=portfolio-api-dist`, `path=$RUNNER_TEMP/staging`, `if-no-files-found: error` | Runs only when the Maven project is present; `error` still catches an empty artifact after a build |
| 6 | `script` "Register artifact in artifact-registry" → `publish_artifact.py --registry artifact-registry` | "Register artifact in Artifactory" → `publish_artifact.py --registry Artifactory`, `if: github.event_name == 'push'` and a Maven project is present | Registry name mapped `master`→`main` (gap **G3**). Push-only guard prevents PR builds registering artifacts; the missing-source guard prevents publishing an empty staging directory |

### `deploy-staging` job (from `templates/release/release-standard.yml@master`, parameters: `environment=staging`, `artifactName=portfolio-api-dist`, `deployStrategy=rolling` (default), `requireApproval=false` (default), `notifyReleaseOrchestrator=true` (default))

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 0 | *(deployment job — no checkout by default)* | `actions/checkout@v4` | Needed so `build-tools/scripts/*` exist on the fresh runner |
| 1 | `download: current, artifact: portfolio-api-dist` | `actions/download-artifact@v4` `name=portfolio-api-dist`, `path=$RUNNER_TEMP/staging` | |
| 2 | `script` "Execute deployment" (two `echo`s) | identical `echo`s | Deployment is still a placeholder in ADO (gap **G7**) |
| 3 | `script` "Notify release-orchestrator" → `notify_release_orchestrator.py --status success` | "Notify D2" → same script, same args, `PIPELINE_URL` env added | Display name mapped `master`→`main` (G3) |
| 4 | `script` "Generate compliance attestation" → `generate_attestation.py` | same script, `mkdir -p` of `$RUNNER_TEMP/attestation` first | Fresh runner has no staging dir |
| 5 | *(none — attestation JSON left on agent)* | `actions/upload-artifact@v4` `portfolio-api-staging-attestation` | Added so the attestation record is retrievable |

## Variable mapping

| ADO | GHA |
|---|---|
| `variables.artifactName: portfolio-api-dist` | `env.ARTIFACT_NAME` |
| template param `jdkVersion` | `env.JDK_VERSION` |
| template param `mavenGoal` / `mavenOptions` | `env.MAVEN_GOAL` / `env.MAVEN_OPTIONS` |
| `pool.vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` |
| `$(Build.ArtifactStagingDirectory)` | `${{ runner.temp }}/staging` (build), `${{ runner.temp }}/attestation` (deploy) |
| `$(Build.SourcesDirectory)` | `${{ github.workspace }}` (implicit cwd) |
| `$(Build.BuildId)` | `${{ github.run_id }}` |
| `resources.repositories.templates@master` | eliminated — templates inlined |

### Env-var shims for helper scripts (scripts run unmodified)

| Script | Reads | Shimmed as |
|---|---|---|
| `publish_artifact.py` | `BUILD_SOURCEBRANCH`, `BUILD_SOURCEVERSION`, `AGENT_NAME`, `BUILD_ARTIFACTSTAGINGDIRECTORY` | `github.ref`, `github.sha`, `runner.name`, `runner.temp/staging` |
| `notify_release_orchestrator.py` | `BUILD_REQUESTEDFOR`, `PIPELINE_URL` (new, preferred) / `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`+`SYSTEM_TEAMPROJECT` (fallback) | `github.actor`, `server_url/repository/actions/runs/run_id` |
| `generate_attestation.py` | `BUILD_SOURCEBRANCH`, `BUILD_SOURCEVERSION`, `BUILD_DEFINITIONNAME`, `AGENT_OS`, `BUILD_ARTIFACTSTAGINGDIRECTORY` | `github.ref`, `github.sha`, `github.workflow`, `runner.os`, `runner.temp/attestation` |

## Condition mapping

| ADO | GHA |
|---|---|
| `Release.dependsOn: Build` (implicit `succeeded()`) | `needs: build` (implicit success) |
| `Deploy_staging` — no `condition` (`requireApproval=false`) | `if: github.event_name == 'push'` — **stricter**: PR builds never deploy. Push to `main` *or* `master` still deploys, as in ADO |
| `deployment` job + `environment: staging` | `environment: staging` — approvals/protection rules configured in GitHub environment settings |
| `Maven@4 publishJUnitResults` (publishes even on failure) | `if: always()` on test collection/upload |

## Integration points

| Integration | ADO (`master` template) | GHA |
|---|---|---|
| Artifact registry | `publish_artifact.py --registry artifact-registry` | `--registry Artifactory` (main-branch name), push-only, manifest written to staging dir |
| Release tracking | "Notify release-orchestrator" | "Notify D2" — same script; `PIPELINE_URL` gives a correct GHA run URL instead of an ADO `_build/results` URL |
| Compliance | "Generate compliance attestation" (`compliance-store` naming in `master` era) | same script (writes to `attestation-database`), record uploaded as artifact |
| Test results | ADO test tab | `portfolio-api-test-results` artifact (raw surefire XML) |

## Script changes (backward compatible)

`build-tools/scripts/notify_release_orchestrator.py`: `pipeline_url` now prefers `PIPELINE_URL` when set, else falls back to the existing ADO construction. ADO callers are unaffected (they don't set `PIPELINE_URL`). No other scripts changed — all other ADO variables are shimmed in the workflow.

## Known gaps — `master` vs `main` template differences

| ID | Area | `master` (what runs today) | `main` (canonical) | Migration choice |
|---|---|---|---|---|
| G1 | Maven goal param | `mavenGoal: 'package'` → `mvn package` (no `clean`) | `mavenGoals: 'clean package'` | Kept `package` (master behaviour). Incremental builds on a fresh runner are equivalent; owner may switch to `clean package` |
| G2 | JDK | `jdkVersion` default `'17'`, pipeline passes `17` | default `'17'` | **No difference** in JDK version between branches for this pipeline; only `PreInstalled` → Temurin distribution changes |
| G3 | Integration names | `--registry artifact-registry`, "Notify release-orchestrator", `compliance-store` | `--registry Artifactory`, "Notify D2", `attestation-database` | Used `main` names (the only scripts in the repo). Downstream consumers keyed on registry string `artifact-registry` must be checked |
| G4 | Artifact name | `portfolio-api-dist` (pipeline variable, both branches) | same | No change; inventory §6 flagged artifact-name drift for `build-python` only, not Java |
| G5 | Header/comment drift | "Last reviewed: 2024-04" | none | Cosmetic |

### Other behavioural gaps

| ID | Gap |
|---|---|
| G1b | **POM location.** The template runs `mvn -f pom.xml` from `$(Build.SourcesDirectory)` (repo root). No `pom.xml` exists anywhere in this repo (no portfolio-api source is checked in). The workflow checks `services/portfolio-api/pom.xml` and skips Maven, artifact staging, and deployment when it is absent, so migration validation can run without claiming a build that cannot execute. If the real source is a separate repo or at the root, adjust `SERVICE_DIR` and remove the guard once the source is present. |
| G6 | **Test reporting.** No GHA test tab. Raw surefire XML is uploaded as an artifact; `dorny/test-reporter@v1` could be added. `normalize_test_results.py` is *not* called (the master template doesn't call it either). |
| G7 | **Deployment is a placeholder** (`echo`) in ADO too; no real deploy mechanism is defined. |
| G8 | **Empty artifact now fails after a build.** `if-no-files-found: error` on the dist upload; ADO would publish an empty artifact. Baseline expects 4 files (`.jar`, `.war`, `.xml`) — the `.xml` (e.g. pom) is *not* staged by the template, so the baseline count may already be wrong for ADO. When the repository has no Maven source, the workflow skips the build and artifact upload entirely. |
| G9 | **Test baseline.** `validation/baselines/portfolio-api/test-counts.json` was created as an unconfirmed placeholder (0 tests). team-quant must populate it from a recent ADO run. |
| G10 | **Deploy gating is stricter.** PRs never deploy/notify/attest; ADO would have run `Deploy_staging` for any run (no PR trigger existed, so in practice only pushes). |
| G11 | **Ownership.** team-quant is medium-confidence owner; confirm before cut-over. |

## Secrets required

None. The helper scripts are stubs (print/write JSON). When wired to real endpoints, expect: `ARTIFACTORY_TOKEN`, `D2_API_TOKEN`, `ATTESTATION_DB_TOKEN` — reference as `${{ secrets.* }}`.

## GitHub configuration required

- Environment `staging` (protection rules / reviewers as desired — ADO had `requireApproval=false`, i.e. none).
