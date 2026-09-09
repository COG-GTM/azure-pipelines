# portfolio-api-canary — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `portfolio-api-canary` (ADO ID **103**) |
| ADO YAML | `services/portfolio-api/azure-pipelines-canary.yml` |
| GHA workflow | `.github/workflows/portfolio-api-canary.yml` |
| Category | 1 — central template consumer (manual A/B of template branches) |
| Stack | Java 17 / Maven |
| Pool | `ubuntu-latest` (hosted) → `runs-on: ubuntu-latest` |
| Owner | team-quant (medium confidence, `j.chen@contoso.com`) |
| Run history | 5 runs, 5 succeeded, avg 8.5 min, last run 2026-02-28 with `templateBranch=staging/preprod` (`docs/samples/ado-api-responses.json`) |
| Variable groups | VG 201 `shared-ci-secrets` bound in ADO; **no expanded step reads any of its variables** |

> **Recommendation: retire this pipeline.** The inventory (§3 row 103, §6, §7 step 4) records that
> 103 exists only to A/B `templates/build/build-java.yml` across four template branches via a
> runtime parameter. Once `master`, `staging/preprod` and `staging/release-hardening` are
> consolidated onto `main`, the selector has one value and this workflow duplicates
> `portfolio-api-ci`. The workflow in this PR keeps the canary usable during the transition only;
> the alternative the inventory offers (a `workflow_dispatch` pinning a reusable-workflow `@ref`)
> is not possible yet because no reusable Java workflow exists on any branch.

## 1. Template resolution (all four selectable branches)

The ADO file declares four repository resources (`templates_main`, `templates_master`,
`templates_preprod`, `templates_hardened`) and uses compile-time
`${{ if eq(parameters.templateBranch, '<branch>') }}` blocks so exactly one
`templates/build/build-java.yml@<resource>` is expanded, always with
`jdkVersion: '17'` and `artifactName: $(artifactName)` (= `portfolio-api-canary`).

Each copy was read with `git show origin/<branch>:templates/build/build-java.yml`.
`master`, `staging/preprod` and `staging/release-hardening` are **byte-identical** to each other.
Versus `main` they differ only as follows:

| Aspect | `main` | `master` / `staging/preprod` / `staging/release-hardening` |
|---|---|---|
| Header | `— maintained by shared-ci-platform team` | `Maintained by: …` / `Last reviewed: 2024-04` |
| Goals parameter | `mavenGoals`, default **`clean package`** | `mavenGoal`, default **`package`** |
| `Maven@4` displayName / goals | `Maven clean package` | `Maven package` |
| `publish_artifact.py --registry` | **`Artifactory`** | **`artifact-registry`** |
| Register step displayName | `Register artifact in Artifactory` | `Register artifact in artifact-registry` |
| Everything else (`JavaToolInstaller@0`, `mavenOptions -B -DskipTests=false`, `publishJUnitResults`, `testResultsFiles '**/surefire-reports/TEST-*.xml'`, stage-artifacts script, `PublishBuildArtifacts@1`) | identical | identical |

The canary passes neither goals parameter, so each branch's default applies. The
`build-tools/scripts/publish_artifact.py` copies on the three non-`main` branches differ from
`main` only in docstring/comment wording (`Artifactory` → `artifact-registry`); behaviour is the
same. The script is executed from the **consuming** checkout (`$(Build.SourcesDirectory)`), i.e.
the `main` copy in this repo, on every branch selection — the GHA workflow does the same.

### Resolved step list per branch (source of truth for the workflow)

| # | ADO step (`main`) | ADO step (other three branches) |
|---|---|---|
| 1 | `JavaToolInstaller@0` versionSpec `17`, x64, PreInstalled | same |
| 2 | `Maven@4` pom `pom.xml`, goals `clean package`, options `-B -DskipTests=false`, publishJUnitResults `true`, `**/surefire-reports/TEST-*.xml` | goals `package` |
| 3 | script `Stage build artifacts`: `cp target/*.jar $(Build.ArtifactStagingDirectory)/ \|\| true`, same for `*.war` | same |
| 4 | `PublishBuildArtifacts@1` pathToPublish `$(Build.ArtifactStagingDirectory)`, artifactName `portfolio-api-canary` | same |
| 5 | script `python $(Build.SourcesDirectory)/build-tools/scripts/publish_artifact.py --name portfolio-api-canary --registry Artifactory --build-id $(Build.BuildId)` | `--registry artifact-registry` |

`build-java.yml` on every branch has **no** D2 notification and **no** compliance attestation
step — those live in `templates/release/*.yml`, which the canary never references.

## 2. Trigger mapping

| ADO | GHA | Notes |
|---|---|---|
| `trigger: none` | — | No push trigger in either system. |
| `parameters.templateBranch` (string, default `main`, values `main`/`master`/`staging/preprod`/`staging/release-hardening`) | `on.workflow_dispatch.inputs.template_branch` (`type: choice`, same default and options) | 1:1. |
| — | `on.pull_request` (`branches: [main]`, paths: `services/portfolio-api/**` excluding the ADO YAMLs, this workflow, `templates/build/build-java.yml`, `build-tools/scripts/publish_artifact.py`) | **Intentional addition** per migration policy. PR runs always resolve to the `main` template branch and never register artifacts. |
| VG 201 `shared-ci-secrets` | not mapped | No step in the expanded pipeline reads it; nothing to configure. |

## 3. Stage / job mapping

| ADO stage → job | GHA job | `needs` | Condition |
|---|---|---|---|
| `Build` (`Build portfolio-api (canary - ${{ parameters.templateBranch }})`) → `build` | `build` (`Build portfolio-api (canary - ${{ inputs.template_branch \|\| 'main' }})`) | — | — |

Compile-time template selection becomes the runtime step `Resolve template branch`, which
emits `maven_goals` and `registry` outputs; every branch-specific value downstream reads these
outputs. An unknown value fails the job (cannot happen via the `choice` input; guards manual
`gh workflow run` misuse).

## 4. Task / step mapping

| # | ADO task / step | GHA step | Translation notes |
|---|---|---|---|
| 0 | implicit `checkout: self` | `actions/checkout@v4` | |
| — | `${{ if eq(parameters.templateBranch, …) }}` | `Resolve template branch` (`case` on `$TEMPLATE_BRANCH`) | `main` → `clean package` / `Artifactory`; others → `package` / `artifact-registry`. |
| 1 | `JavaToolInstaller@0` (17, x64, PreInstalled) | `actions/setup-java@v4` `distribution: temurin`, `java-version: 17`, `architecture: x64` | Hosted ADO images preinstall Temurin/Microsoft OpenJDK; Temurin chosen. No Maven cache (ADO had none). |
| 2 | `Maven@4` | `mvn -f pom.xml -B -DskipTests=false <goals>` with `working-directory: services/portfolio-api` | See gap 1 for the pom location. |
| 2b | `Maven@4.publishJUnitResults` + `**/surefire-reports/TEST-*.xml` | `Collect JUnit test results` (`find … -path '*/surefire-reports/TEST-*.xml' -exec cp --parents`) + `actions/upload-artifact@v4` (`if: always()`) | `find` replaces `**` (no globstar in GHA bash). `cp --parents` keeps module paths so multi-module reports cannot overwrite each other. No native test tab in GHA (gap 3). |
| 3 | script `Stage build artifacts` | `Stage build artifacts` (`mkdir -p "$RUNNER_TEMP/staging"` then identical `cp … \|\| true` lines) | `$(Build.ArtifactStagingDirectory)` → `$RUNNER_TEMP/staging`; `mkdir -p` because GHA runners have no pre-created staging dir. Tolerant `\|\| true` preserved. |
| 4 | `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` `name: portfolio-api-canary`, `path: ${{ runner.temp }}/staging`, `if-no-files-found: warn` | `warn` mirrors ADO, which uploads an empty staging directory without failing. |
| 5 | script `Register artifact in Artifactory` / `…artifact-registry` | `Register artifact in <registry>` — same `publish_artifact.py` invocation, `--registry` from the resolved output | `if: github.event_name != 'pull_request'` so PR builds never register. `mkdir -p` on the staging dir before the script writes its manifest. |
| — | — | `Write canary run summary` (`$GITHUB_STEP_SUMMARY`) | Canary-specific: records the branch/goals/registry exercised, replacing the ADO stage display name as the place this information was visible. |

## 5. Variable mapping

| ADO | GHA |
|---|---|
| `variables.artifactName` = `portfolio-api-canary` | `env.ARTIFACT_NAME` |
| `variables.templates_branch` = `${{ parameters.templateBranch }}` | `env.TEMPLATE_BRANCH` = `${{ inputs.template_branch \|\| 'main' }}` |
| template param `jdkVersion: '17'` | `env.JDK_VERSION` |
| template param `mavenOptions` default | `env.MAVEN_OPTIONS` = `-B -DskipTests=false` |
| template param `mavenGoals`/`mavenGoal` default | `steps.template.outputs.maven_goals` |
| `--registry` literal per branch | `steps.template.outputs.registry` |
| `$(Build.ArtifactStagingDirectory)` | `${{ runner.temp }}/staging` (also shimmed as `BUILD_ARTIFACTSTAGINGDIRECTORY`) |
| `$(Build.SourcesDirectory)` | `$GITHUB_WORKSPACE` |
| `$(Build.BuildId)` | `${{ github.run_id }}` (shimmed as `BUILD_BUILDID`) |
| `$(Build.SourceBranch)` | `${{ github.ref }}` (shimmed as `BUILD_SOURCEBRANCH`) |
| `$(Build.SourceVersion)` | `${{ github.sha }}` (shimmed as `BUILD_SOURCEVERSION`) |
| `$(Agent.Name)` | `${{ runner.name }}` (shimmed as `AGENT_NAME`) |
| ADO build URL | `PIPELINE_URL` = `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` (forward-compatibility; `publish_artifact.py` does not build URLs today) |

## 6. Condition mapping

| ADO | GHA |
|---|---|
| `${{ if eq(parameters.templateBranch, 'main') }}` … (×4, compile time) | `case "$TEMPLATE_BRANCH"` in `Resolve template branch` (runtime) |
| `${{ if eq(parameters.publishArtifacts, true) }}` (default `true`, never overridden) | steps 3–5 always present |
| `publishJUnitResults: ${{ parameters.runTests }}` (default `true`) | test-result steps always present, `if: always()` |
| — | `if: github.event_name != 'pull_request'` on registry registration (new guard) |

## 7. Integration points

| System | ADO | GHA |
|---|---|---|
| Artifactory / artifact-registry | `publish_artifact.py --registry Artifactory` (`main`) or `--registry artifact-registry` (others); script is a stub that writes `<name>-manifest.json` into the staging dir | Same script, same arguments (registry from resolved branch), env shims listed in §5, guarded to non-PR events. Manifest is written **after** `Upload artifacts` runs, exactly as in ADO (the manifest is not part of the uploaded artifact in either system). |
| D2 (release orchestrator) | not used by `build-java.yml` on any branch | not applicable |
| attestation-database / compliance | not used by `build-java.yml` on any branch | not applicable |
| Test results | ADO Tests tab via `publishJUnitResults` | JUnit XML uploaded as `portfolio-api-canary-test-results-<run_id>` artifact |
| VG 201 `shared-ci-secrets` | bound to the definition, unused | nothing configured |

## 8. Helper scripts

`build-tools/scripts/publish_artifact.py` (only script reached) reads `BUILD_SOURCEBRANCH`,
`BUILD_SOURCEVERSION`, `AGENT_NAME`, `BUILD_ARTIFACTSTAGINGDIRECTORY`. All are shimmed in the
workflow; it does not construct ADO URLs. **No script changes are required** for this pipeline.

## 9. Known gaps and behavioural differences

1. **pom location.** Every `build-java.yml` copy runs `mvn -f pom.xml` at the checkout root, but
   this repository has no root `pom.xml`; the portfolio-api Maven project (added by PR #12) lives
   in `services/portfolio-api`. The workflow runs Maven, test collection and artifact staging with
   `working-directory: services/portfolio-api`. If ADO 103 really built at the root it depended on
   a checkout not represented in this repo (inventory §5.2 "scripts/source referenced but absent").
2. **Template drift is snapshotted.** The workflow reproduces the four branches' `build-java.yml`
   as they exist today. Future edits to a template branch are not picked up automatically — the
   two-value table in §1 must be re-checked, or (preferred) the canary retired.
3. **Test reporting.** No GHA equivalent of the ADO Tests tab; JUnit XML is uploaded as an
   artifact. `dorny/test-reporter` could be added later if a rendered report is wanted.
4. **`upload-artifact` with an empty staging dir** warns instead of silently succeeding as
   `PublishBuildArtifacts@1` did. Same outcome (green build), more visible.
5. **Retention.** ADO retention rule for 103 is 14 days / min 3 builds; GHA uses the repository
   default (90 days). Not a regression.
6. **Runner selection.** `vmImage: ubuntu-latest` is a moving target in both systems; the Java
   toolchain is pinned by `setup-java`, not the image.
7. **Concurrency.** Added `concurrency` keyed on ref + template branch (cancel-in-progress for PRs
   only). ADO had no equivalent; dispatches of different branches still run in parallel as before.

## 10. Secrets required

None. `publish_artifact.py` is a stub with no network calls, and no expanded step reads VG 201.
If the real Artifactory publish path is wired in later it will need `ARTIFACT_REGISTRY_URL` /
`ARTIFACT_REGISTRY_TOKEN` (VG 205 names) as repository secrets.

## 11. Validation

- `validate-migration` routing: `portfolio-api-canary` → service `portfolio-api`,
  ADO source `services/portfolio-api/azure-pipelines-canary.yml` (one `case` arm added to
  `.github/workflows/validate-migration.yml`; validator logic untouched).
- `validation/baselines/portfolio-api/test-counts.json` added from a real run of the scaffold
  (`mvn -B -DskipTests=false clean package`, JDK 17.0.20, Maven 3.6.3): 1 suite, 5 tests,
  0 failures. `expected-artifacts.json` already existed (team-quant, 2024-04-10).
- ADO MCP (`azure-devops-mcp`) could not be initialised in this session; run history and
  definition metadata were taken from `docs/samples/ado-api-responses.json` instead.
