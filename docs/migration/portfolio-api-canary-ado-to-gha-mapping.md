# portfolio-api-canary — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline ID | 103 |
| ADO YAML | `services/portfolio-api/azure-pipelines-canary.yml` |
| GHA workflow | `.github/workflows/portfolio-api-canary.yml` |
| Category | 1 — Central template consumer (`templates/build/build-java.yml`, branch chosen at queue time) |
| Owner | team-quant (`j.chen@contoso.com`, last modifier) |
| Pool | `Azure Pipelines` hosted, `ubuntu-latest` → `runs-on: ubuntu-latest` |
| Runs (90 d) | 5, all succeeded, avg 8.5 min; last run 2026-02-28 with `templateBranch=staging/preprod` |
| Variable groups | 201 `shared-ci-secrets` (attached in ADO, not referenced by any step in the expanded YAML) |

> ## Recommendation: retire this pipeline
> `portfolio-api-canary` exists **only** to A/B-test `build-java.yml` across four long-lived template
> branches before team-quant commits to one. The inventory (`docs/pipeline-inventory-report.md`
> §3.1, §6, §7 step 4) recommends retiring it once the template branches are consolidated onto `main`.
> This workflow is a faithful port so the canary keeps working during the transition, but it should be
> **deleted as soon as `master`, `staging/preprod` and `staging/release-hardening` are removed** — at
> that point the variant selector has exactly one value and the workflow duplicates `portfolio-api-ci`.

## 1. Expanded ADO execution view (source of truth)

The pipeline has one stage (`Build`) with one job (`build`). Exactly one of four
`${{ if eq(parameters.templateBranch, …) }}` blocks is compiled in, each including
`templates/build/build-java.yml@<branch>` with `jdkVersion: '17'`, `artifactName: $(artifactName)`.
All other template parameters take the template defaults **from that branch**.

Resolved steps (`main` variant):

| # | ADO task | Resolved inputs |
|---|---|---|
| 1 | `JavaToolInstaller@0` — "Install JDK 17" | `versionSpec: 17`, `jdkArchitectureOption: x64`, `jdkSourceOption: PreInstalled` |
| 2 | `Maven@4` — "Maven clean package" | `mavenPomFile: pom.xml`, `goals: clean package`, `options: -B -DskipTests=false`, `publishJUnitResults: true`, `testResultsFiles: **/surefire-reports/TEST-*.xml` |
| 3 | `script` — "Stage build artifacts" | `cp target/*.jar $(Build.ArtifactStagingDirectory)/ \|\| true`; same for `*.war` |
| 4 | `PublishBuildArtifacts@1` — "Upload artifacts" | `pathToPublish: $(Build.ArtifactStagingDirectory)`, `artifactName: portfolio-api-canary` |
| 5 | `script` — "Register artifact in Artifactory" | `python build-tools/scripts/publish_artifact.py --name portfolio-api-canary --registry Artifactory --build-id $(Build.BuildId)` |

### 1.1 Per-branch template differences (`git show origin/<branch>:templates/build/build-java.yml`)

`master`, `staging/preprod` and `staging/release-hardening` copies of `build-java.yml` are
**byte-identical to each other**. Versus `main` they differ in exactly two behavioural respects:

| Aspect | `main` | `master` / `staging/preprod` / `staging/release-hardening` | Behaviour change? |
|---|---|---|---|
| Maven goals parameter | `mavenGoals`, default `clean package` | `mavenGoal`, default `package` | **Yes** — no `clean`; incremental `target/` is reused |
| Artifact registry name | `--registry Artifactory` (step "Register artifact in Artifactory") | `--registry artifact-registry` (step "Register artifact in artifact-registry") | **Yes** — different `registry` value written into the manifest / sent to the registry |
| Header comments | one line | three lines (`Last reviewed: 2024-04`) | No |
| Everything else (JDK step, Maven options, JUnit glob, staging, upload) | — | identical | No |

`publish_artifact.py` also differs across branches, but only in docstring/comment text
(`Artifactory` vs `artifact-registry`) — and in any case the ADO template runs the copy from the
**pipeline's own checkout** (`$(Build.SourcesDirectory)`), i.e. from `main`, not from the template
branch. The GHA workflow therefore always uses `build-tools/scripts/publish_artifact.py` from the
checked-out ref, exactly as ADO does.

The canary parameter therefore boils down to two knobs, implemented in the `Resolve template variant`
step:

```
main                                              → maven_goals="clean package"  registry="Artifactory"
master | staging/preprod | staging/release-hardening → maven_goals="package"        registry="artifact-registry"
```

### 1.2 ADO MCP verification

`azure-devops-mcp` (`pipeline_get_pipeline` 103) could not be reached in this session (server process
exited on start-up). Verification fell back to `docs/samples/ado-api-responses.json`
(`build_definitions[2]`, `build_runs_summary[2]`) plus manual template expansion from the four branches.

## 2. Trigger mapping

| ADO | GHA | Note |
|---|---|---|
| `trigger: none` + runtime `parameters.templateBranch` (string, 4 `values`) | `on.workflow_dispatch.inputs.template_variant` (`type: choice`, same four options, default `main`) | 1:1 |
| — | `on.pull_request` (`main`; paths: `services/portfolio-api/**` excluding the ADO YAMLs) | **Intentional addition** (playbook rule). On PRs the variant is always `main` and artifact registration is skipped. Deliberately *not* triggered by template/workflow edits: the Maven sources are not in this repo (gap 2), so such a run can only fail. Use `workflow_dispatch` to exercise the canary. |

## 3. Stage → job mapping

| ADO stage / job | GHA job | `needs` | Condition |
|---|---|---|---|
| `Build` / `build` — "Build portfolio-api (canary - ${{ parameters.templateBranch }})" | `build` — "Build portfolio-api (canary - ${{ inputs.template_variant \|\| 'main' }})" | — | — |

## 4. Task → step mapping

| # | ADO task | GHA step | Translation notes |
|---|---|---|---|
| — | (implicit checkout) | `actions/checkout@v4` | |
| — | compile-time `${{ if eq(parameters.templateBranch, …) }}` | `Resolve template variant` (`run`, outputs `maven_goals`, `registry`) | Runtime `case` replaces compile-time template selection. Unknown value fails the job. |
| 1 | `JavaToolInstaller@0` (PreInstalled 17 x64) | `actions/setup-java@v4` `distribution: temurin`, `java-version: 17`, `architecture: x64` | ADO "PreInstalled" is whatever JDK 17 the hosted image ships (Temurin on ubuntu-latest). No Maven cache, matching ADO. |
| 2 | `Maven@4` | `mvn -f pom.xml -B -DskipTests=false <goals>` | `goals` is variant-specific (§1.1). Maven is preinstalled on `ubuntu-latest` as on ADO hosted agents. |
| 2 | `Maven@4` `publishJUnitResults: true`, `testResultsFiles: **/surefire-reports/TEST-*.xml` | `Collect JUnit test results` (`find . -path '*/surefire-reports/TEST-*.xml'`) + `Upload JUnit test results` (`actions/upload-artifact@v4`, `if: always()`) | `**` glob → `find` (GHA bash has no globstar). GHA has no native test tab — results are an artifact. |
| 3 | `script` "Stage build artifacts" | `Stage build artifacts` | Adds `mkdir -p "$STAGING_DIR"` (fresh runner). Same `\|\| true` semantics. |
| 4 | `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` `name: portfolio-api-canary`, `path: ${{ runner.temp }}/staging`, `if-no-files-found: warn` | ADO uploads an empty folder without failing; `warn` preserves that. |
| 5 | `script` "Register artifact in Artifactory" | `Register artifact in Artifactory (<registry>)` — `python3 build-tools/scripts/publish_artifact.py --registry <variant registry>` | `if: github.event_name != 'pull_request'`. Env shims below. `--registry` is variant-specific (§1.1). |
| — | — | `Canary summary (…)` writes `$GITHUB_STEP_SUMMARY` | **Not in ADO.** Records variant / goals / registry and states explicitly that `build-java.yml` has no D2 notification and no compliance attestation step. Informational only. |

## 5. Variable mapping

| ADO | GHA |
|---|---|
| `variables.artifactName: portfolio-api-canary` | `env.ARTIFACT_NAME` |
| `variables.templates_branch: ${{ parameters.templateBranch }}` | `env.TEMPLATE_VARIANT: ${{ inputs.template_variant \|\| 'main' }}` |
| template param `jdkVersion: '17'` | `env.JDK_VERSION` |
| template param `mavenOptions` default | `env.MAVEN_OPTIONS` |
| template param `mavenGoals`/`mavenGoal` default (per branch) | `steps.variant.outputs.maven_goals` |
| `$(Build.ArtifactStagingDirectory)` | `${{ runner.temp }}/staging` (step-level; `runner` context is unavailable in workflow/job `env`) |
| `$(Build.BuildId)` | `${{ github.run_id }}` |
| `$(Build.SourcesDirectory)` | `${{ github.workspace }}` (implicit cwd) |

### 5.1 Env shims for `publish_artifact.py` (step "Register artifact …")

The script is **unchanged**; it reads these ADO-named variables, which the step sets:

| Script reads | Shimmed to |
|---|---|
| `BUILD_SOURCEBRANCH` | `${{ github.ref }}` |
| `BUILD_SOURCEVERSION` | `${{ github.sha }}` |
| `AGENT_NAME` | `${{ runner.name }}` |
| `BUILD_ARTIFACTSTAGINGDIRECTORY` | `${{ runner.temp }}/staging` (manifest `portfolio-api-canary-manifest.json` written here) |
| `PIPELINE_URL` *(not read today)* | `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` — provided so the script picks it up if/when `PIPELINE_URL` support lands from the other migrations |

## 6. Condition mapping

| ADO | GHA |
|---|---|
| `${{ if eq(parameters.templateBranch, 'main') }}` … (×4, compile-time) | `case "$TEMPLATE_VARIANT"` in `Resolve template variant` (runtime) |
| `${{ if eq(parameters.publishArtifacts, true) }}` (default `true`) | Always included (steps 3–5 unconditional, except the PR guard on registration) |
| — | `if: github.event_name != 'pull_request'` on artifact registration (**new**, playbook rule) |
| — | `if: always()` on JUnit collection/upload and on the summary step |

## 7. Integration points

| Integration | ADO (`build-java.yml`) | GHA |
|---|---|---|
| Artifactory | `publish_artifact.py --registry Artifactory` (or `artifact-registry` on non-`main` branches) | Same script, same argument per variant; push/dispatch only |
| D2 / release orchestrator notification | **none** — lives in `release-standard.yml`, not consumed by the canary | none (stated in summary step) |
| Compliance attestation | **none** — lives in `release-standard.yml` | none (stated in summary step) |
| Test results | Maven@4 built-in JUnit publish (ADO Tests tab) | `portfolio-api-canary-test-results` artifact |

## 8. Known gaps / behavioural differences

1. **Retire, don't maintain** — see the recommendation box above. The workflow duplicates
   `portfolio-api-ci` except for the two-knob variant switch.
2. **No Java source in this repo.** `pom.xml` / `src/` for portfolio-api are not in `azure-pipelines`;
   ADO must be checking out the service source from elsewhere (5 successful runs). Until the source
   location is confirmed, the Maven step will fail in this repo (confirmed on the migration PR:
   `No file ... matched to [**/pom.xml]`). The `pull_request` trigger is therefore scoped to
   `services/portfolio-api/**` source changes only.
3. **Test results have no native viewer** in GHA; they are uploaded as an artifact. Consider
   `dorny/test-reporter@v1` if a Checks-tab view is wanted.
4. **`PreInstalled` JDK → Temurin.** ADO used whichever JDK 17 the hosted image ships;
   `setup-java` pins Temurin 17. Vendor could differ from the ADO image.
5. **JUnit report layout**: reports are collected with `cp --parents`, so multi-module builds keep
   `<module>/target/surefire-reports/TEST-*.xml` paths instead of colliding in one flat directory.
6. **Variant is a runtime switch, not the real template branch.** ADO compiled the template from the
   selected branch; GHA emulates the two observed differences. If a template branch changes in a way
   that is not `mavenGoal`/registry, the workflow must be updated (or — preferably — the branch
   consolidated). The three non-`main` branches are identical today, so they share one `case` arm.
7. **Artifact registration is skipped on PRs** (new guard). ADO had no PR trigger, so this is not a
   regression, but dispatch runs on non-default branches *do* register, as ADO did.
8. **Manifest not in the uploaded artifact.** As in ADO, `publish_artifact.py` writes
   `portfolio-api-canary-manifest.json` into the staging dir *after* `Upload artifacts` ran, so it is
   not part of the uploaded artifact. Preserved as-is (pre-existing ordering).
9. **`shared-ci-secrets` (VG 201)** is attached to the ADO definition but no expanded step reads any
   variable from it. Nothing was mapped; confirm with team-quant that this binding is dead.
10. **Test baseline is a placeholder.** `validation/baselines/portfolio-api/test-counts.json` was
    added with `expected_total_tests: 0` because no surefire output exists in-repo; team-quant should
    fill in real counts from the last ADO run.
11. **Validator routing.** `.github/workflows/validate-migration.yml` gained a
    `portfolio-api-canary)` case so the scorecard compares this workflow against
    `azure-pipelines-canary.yml` (no validator *logic* changed).

## 9. Secrets required

None. `publish_artifact.py` is a stub that writes a local manifest; when the real Artifactory publish
path is wired in, the registry credentials (ADO VG 205 `artifact-registry-credentials`:
`ARTIFACT_REGISTRY_URL`, `ARTIFACT_REGISTRY_TOKEN`) will need to become repository secrets and be
passed to the "Register artifact" step via `${{ secrets.* }}`.

## 10. Helper script changes

None. All ADO-specific variables consumed by `publish_artifact.py` are shimmed in the workflow
(§5.1), keeping the script byte-identical for the ADO pipelines that still call it.
