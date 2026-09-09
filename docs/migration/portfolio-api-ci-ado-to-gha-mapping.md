# portfolio-api-ci — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `portfolio-api-ci` (ADO ID **102**) |
| ADO YAML | `services/portfolio-api/azure-pipelines.yml` |
| Category | 1 — central template consumer |
| Template repo / ref | `shared-ci-platform` @ **`master`** (legacy template set; templates read with `git show origin/master:<path>`) |
| Templates consumed | `templates/build/build-java.yml`, `templates/release/release-standard.yml` |
| Pool | `ubuntu-latest` (hosted) → `runs-on: ubuntu-latest` |
| Owner | team-quant (medium confidence — `j.chen@contoso.com`) |
| GHA workflow | `.github/workflows/portfolio-api-ci.yml` |
| Inventory risk flags | Consumes `master` (old integration names `artifact-registry` / `release-orchestrator` / `compliance-store`); §5 downstream-tooling risks for Artifactory, D2 and attestation-database apply; `AzureSubscription-Staging` service connection |

Behaviour (JDK, Maven goal, artifact name, release steps) follows the `master` templates the pipeline actually
runs. Integration *names* follow `main` (Artifactory / D2 / attestation-database) because the helper scripts on
`main` are the only ones in the repo (see [Known gaps](#known-gaps)).

ADO MCP verification (`pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml` for ID 102) was attempted but the
`azure-devops-mcp` server does not start in this environment, so templates were expanded manually from `origin/master`.

## 1. Trigger mapping

| ADO | GHA | Note |
|---|---|---|
| `trigger.branches.include: [main, master]` | `on.push.branches: [main, master]` | Both source branches preserved. |
| `trigger.paths.include: [services/portfolio-api/**]` | `on.push.paths` + same list under `on.pull_request.paths` | **Intentional additions:** the three helper scripts the workflow runs and the workflow file itself, so changes to them are exercised. |
| *(none)* | `on.pull_request.branches: [main, master]` | **Added** — ADO pipeline had no PR trigger. PR runs build/test/upload only; registration and deploy are push-only. |
| *(none)* | `workflow_dispatch` | Added for manual re-runs. |
| *(none)* | `concurrency` group per ref, cancel-in-progress on PRs | Added. |

## 2. Variables

| ADO | GHA (`env:`) | Source |
|---|---|---|
| `variables.artifactName: portfolio-api-dist` | `ARTIFACT_NAME: portfolio-api-dist` | pipeline |
| `parameters.jdkVersion: '17'` | `JDK_VERSION: '17'` | pipeline → template |
| `parameters.mavenGoal: 'package'` | `MAVEN_GOAL: package` | pipeline → template (`master` name is `mavenGoal`) |
| `parameters.mavenOptions` (default `-B -DskipTests=false`) | `MAVEN_OPTIONS: -B -DskipTests=false` | template default |
| `parameters.runTests` / `publishArtifacts` (default `true`) | steps always present | template default |
| `parameters.environment: staging` | literal `staging` in deploy job | pipeline |
| `deployStrategy` (default `rolling`), `requireApproval` (default `false`), `notifyReleaseOrchestrator` (default `true`) | literal `rolling`; no branch condition; Notify step present | template defaults |
| `mavenPomFile: pom.xml` (relative to `$(Build.SourcesDirectory)`) | `working-directory: services/portfolio-api` + `mvn -f pom.xml` | see gap G1 |

## 3. Stage → job mapping

| ADO stage | ADO job | GHA job | `needs` | `if` | `environment` |
|---|---|---|---|---|---|
| `Build` — "Build portfolio-api" | `build` (steps from `build-java.yml@master`) | `build` — "Build portfolio-api" | — | — | — |
| `Release` — "Release to staging" → expands to `Deploy_staging` — "Deploy to staging" | `deployment: deploy` (runOnce) | `deploy-staging` — "Deploy to staging" | `build` | `github.event_name == 'push'` | `staging` |

## 4. Step / task mapping

### Build job (`templates/build/build-java.yml@master`)

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 1 | *(implicit checkout)* | `actions/checkout@v4` | |
| 2 | `JavaToolInstaller@0` versionSpec=17, x64, PreInstalled | `actions/setup-java@v4` distribution=temurin, java-version=17, `cache: maven` | Hosted agents' pre-installed JDK ≈ Temurin. Maven cache is an addition (no behavioural change). |
| 3 | `Maven@4` mavenPomFile=pom.xml, goals=package, options=`-B -DskipTests=false` | `mvn -f pom.xml $MAVEN_OPTIONS $MAVEN_GOAL` in `services/portfolio-api` | Same goal/options; see G1 for the working directory. |
| 4 | `Maven@4` publishJUnitResults=true, testResultsFiles=`**/surefire-reports/TEST-*.xml` | `Collect JUnit test results` (`find … -path '*/surefire-reports/TEST-*.xml'`, `if: always()`) + `actions/upload-artifact@v4` `portfolio-api-test-results` (`if: always()`) | `**` replaced with `find` (globstar is off in GHA bash). No native test tab in GHA — results are an artifact. `dorny/test-reporter@v1` can be layered on later (needs `checks: write`). |
| 5 | `script` "Stage build artifacts" (`cp target/*.jar\|*.war $(Build.ArtifactStagingDirectory)/`) | same `cp` into `${{ runner.temp }}/staging` after `mkdir -p` | `$(Build.ArtifactStagingDirectory)` → `${{ runner.temp }}/staging`. |
| 6 | `PublishBuildArtifacts@1` pathToPublish=staging dir, artifactName=`portfolio-api-dist` | `actions/upload-artifact@v4` name=`portfolio-api-dist`, `if-no-files-found: error` | Stricter than ADO (which would publish an empty folder) — an empty dist now fails the build. |
| 7 | `script` "Register artifact in artifact-registry" → `publish_artifact.py --registry artifact-registry` | `Register artifact in Artifactory` → `publish_artifact.py --registry Artifactory`, **`if: github.event_name == 'push'`** | Registry name follows `main` (G3). Guarded so PR builds never register. Env shims: `BUILD_SOURCEBRANCH`, `BUILD_SOURCEVERSION`, `AGENT_NAME`, `BUILD_ARTIFACTSTAGINGDIRECTORY`. |

### Deploy job (`templates/release/release-standard.yml@master`, `Deploy_staging`)

| # | ADO step | GHA step | Translation |
|---|---|---|---|
| 1 | *(deployment jobs do not checkout by default; scripts referenced via `$(Build.SourcesDirectory)`)* | `actions/checkout@v4` | Needed so the helper scripts exist on the fresh runner. |
| 2 | `download: current, artifact: portfolio-api-dist` | `actions/download-artifact@v4` name=`portfolio-api-dist` → `${{ runner.temp }}/staging` | |
| 3 | `script` "Execute deployment" (echo name/strategy) | `Execute deployment` (same echoes + `ls`) | Placeholder in ADO as well — no real deploy mechanism exists in either. |
| 4 | `script` "Notify release-orchestrator" → `notify_release_orchestrator.py --status success` | `Notify D2` → same script/args | Env shims `BUILD_REQUESTEDFOR`, **`PIPELINE_URL`** (see §7). |
| 5 | `script` "Generate compliance attestation" → `generate_attestation.py` | `Generate compliance attestation` → same script/args, preceded by `mkdir -p` | Fresh runner: staging dir must exist. Env shims `BUILD_SOURCEBRANCH`, `BUILD_SOURCEVERSION`, `BUILD_DEFINITIONNAME`, `AGENT_OS`, `BUILD_ARTIFACTSTAGINGDIRECTORY`. |
| 6 | *(none — attestation JSON stayed on the agent)* | `actions/upload-artifact@v4` `portfolio-api-staging-attestation` | Added so the attestation record is retained with the run. |

## 5. Condition mapping

| ADO | GHA | Note |
|---|---|---|
| `Release.dependsOn: Build` | `deploy-staging.needs: build` | |
| `Deploy_staging` has **no** `condition` (`requireApproval=false`) — ran on every successful build of `main`/`master` | `if: github.event_name == 'push'` | Equivalent for the ADO trigger set (ADO never ran on PRs). The guard only excludes the newly added PR/dispatch runs. |
| `${{ if eq(parameters.publishArtifacts, true) }}` (true) | steps present unconditionally | |
| `${{ if eq(parameters.notifyReleaseOrchestrator, true) }}` (true) | `Notify D2` step present unconditionally | |
| `deployment` job `environment: staging` | `environment: staging` | Create the `staging` GitHub environment; ADO had **no** approval gate, so add reviewers only if desired. |

## 6. ADO variable → GHA shim reference (as used)

| ADO env var read by scripts | GHA value |
|---|---|
| `BUILD_SOURCEBRANCH` | `${{ github.ref }}` |
| `BUILD_SOURCEVERSION` | `${{ github.sha }}` |
| `BUILD_BUILDID` (`--build-id`) | `${{ github.run_id }}` |
| `BUILD_ARTIFACTSTAGINGDIRECTORY` | `${{ runner.temp }}/staging` (build) / `${{ runner.temp }}/attestation` (deploy) |
| `BUILD_SOURCESDIRECTORY` | `${{ github.workspace }}` (implicit cwd) |
| `AGENT_NAME` | `${{ runner.name }}` |
| `AGENT_OS` | `${{ runner.os }}` |
| `BUILD_REQUESTEDFOR` | `${{ github.actor }}` |
| `BUILD_DEFINITIONNAME` | `${{ github.workflow }}` |
| `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` + `SYSTEM_TEAMPROJECT` + `/_build/results?buildId=` | replaced by `PIPELINE_URL=${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` |

## 7. Integration points

| System | ADO (`master` templates) | GHA | Handling |
|---|---|---|---|
| **Artifactory** | `publish_artifact.py --registry artifact-registry` in build | `--registry Artifactory`, push-only | Script is a stub (writes `<name>-manifest.json` into the staging dir). Credentials VG 205 `artifact-registry-credentials` are not consumed by the stub; when the real publish path lands, add `ARTIFACT_REGISTRY_URL`/`ARTIFACT_REGISTRY_TOKEN` as repo secrets. |
| **D2** (release tracking) | `notify_release_orchestrator.py` in deploy | same, with `PIPELINE_URL` | **Script updated (backward compatible):** `pipeline_url` now prefers `PIPELINE_URL` when set and otherwise builds the ADO `_build/results` URL exactly as before, so ADO callers are unaffected. |
| **attestation-database** (compliance) | `generate_attestation.py` in deploy (`master` templates elsewhere say `compliance-store`; this script has no `--store` flag) | same, `mkdir -p` first, JSON uploaded as artifact | Stub; the real store needs VG 206 `compliance-store-credentials` (URL/token/cert thumbprint). Cert-thumbprint auth has no hosted-runner analogue — needs OIDC or a self-hosted runner before real writes. |
| Azure (`AzureSubscription-Staging`) | bound to the ADO project; not used by any YAML step | not configured | Deploy is an `echo`; wire OIDC federated credentials for `staging` when a real deploy exists. |
| Test results | `Maven@4 publishJUnitResults` → ADO Tests tab | artifact `portfolio-api-test-results` | No native GHA viewer (G5). |

## 8. Known gaps / behavioural differences

| ID | Gap | Impact / decision |
|---|---|---|
| **G1** | `master` `build-java.yml` runs `Maven@4` with `mavenPomFile: pom.xml` relative to the repo root; the repo has no root POM — the only POM is `services/portfolio-api/pom.xml` (runnable scaffold from PR #12). In ADO this step would have failed as written unless the real service checkout differed. | GHA runs Maven in `services/portfolio-api`. Confirm with team-quant that this matches the real service layout. |
| **G2** | **`master` vs `main` template drift (`build-java.yml`):** `master` parameter `mavenGoal` default `package`; `main` renamed to `mavenGoals` default `clean package`. JDK default is `17` on both. Artifact name comes from the pipeline (`portfolio-api-dist`) on both, so no artifact-name change. | Workflow keeps the `master` behaviour (`package`, no `clean`). Moving to `main` semantics = `MAVEN_GOAL: clean package`; harmless on a fresh runner. |
| **G3** | **Integration names:** `master` says `--registry artifact-registry` / "Notify release-orchestrator"; `main` says `Artifactory` / "Notify D2" (same script names on both). | Workflow uses `main` names per inventory guidance. If downstream consumers key on the literal registry string `artifact-registry`, change the `--registry` argument. |
| **G4** | `release-standard.yml` is byte-identical between `master` and `main` except the display name "Notify release-orchestrator" → "Notify D2". | No behavioural gap. |
| **G5** | ADO Tests tab vs. GHA artifact upload of surefire XML. | Optionally add `dorny/test-reporter@v1` (`checks: write`). |
| **G6** | `validation/baselines/portfolio-api/expected-artifacts.json` (team-quant, 2024-04) expects 4 files incl. a `.war`, 15–80 MB. The scaffold produces one ~8 KB `portfolio-api-0.1.0.jar`. | Baseline describes the real service, not the in-repo scaffold; left unchanged for team-quant to reconcile. |
| **G7** | New `validation/baselines/portfolio-api/test-counts.json` is measured from the scaffold (1 suite, 5 tests, 100 % pass). | Replace with real-service numbers at cut-over. |
| **G8** | `if-no-files-found: error` on the dist upload is stricter than `PublishBuildArtifacts@1`. | Intentional — an empty dist should fail. |
| **G9** | Hosted-agent "PreInstalled" JDK → Temurin 17 via `setup-java`. | Same major version; vendor may differ from the ADO image. |
| **G10** | ADO ran only on `push`; GHA additionally runs build/test on PRs and `workflow_dispatch`. Registration/deploy/notify/attestation are push-only. | Intentional. |

## 9. Secrets / configuration required in GitHub

| Item | Needed now? | Notes |
|---|---|---|
| GitHub environment `staging` | **Yes** | Referenced by `deploy-staging`. No approval in ADO; add protection rules if wanted. |
| `ARTIFACT_REGISTRY_URL`, `ARTIFACT_REGISTRY_TOKEN` (VG 205) | Not yet | Stub script doesn't read them. |
| `COMPLIANCE_STORE_URL`, `COMPLIANCE_STORE_TOKEN`, `COMPLIANCE_STORE_CERT_THUMBPRINT` (VG 206) | Not yet | Stub script doesn't read them; cert auth needs redesign. |
| Azure OIDC federated credential for `staging` (`AzureSubscription-Staging`) | Not yet | Deploy is a placeholder. |

No secrets are hardcoded; `permissions: contents: read` only.

## 10. Files in this migration

- `.github/workflows/portfolio-api-ci.yml` — new workflow
- `docs/migration/portfolio-api-ci-ado-to-gha-mapping.md` — this document
- `build-tools/scripts/notify_release_orchestrator.py` — `PIPELINE_URL` support (backward compatible)
- `validation/baselines/portfolio-api/test-counts.json` — measured test baseline required by the `validate-migration` scorecard

ADO YAML under `services/`, `templates/` and `alt-templates/` is unchanged.
