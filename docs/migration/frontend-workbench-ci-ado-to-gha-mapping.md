# frontend-workbench-ci — ADO → GitHub Actions mapping

| | |
|---|---|
| ADO pipeline | `frontend-workbench-ci` (ID 106, `\Services\frontend-workbench`, enabled) |
| ADO YAML | `services/frontend-workbench/azure-pipelines.yml` |
| Category | 2 — alt-template consumer |
| Owner | team-frontend |
| Template ref | `resources.repositories.templates` → `shared-ci-platform` @ `team/frontend-custom` |
| Templates inlined | `alt-templates/frontend/frontend-build.yml`, `alt-templates/frontend/frontend-deploy.yml` (read with `git show origin/team/frontend-custom:<path>`) |
| Variable groups | 201 `shared-ci-secrets` (attached, never referenced by any step), 210 `frontend-cdn-config` |
| GHA workflow | `.github/workflows/frontend-workbench-ci.yml` |
| Baselines | `validation/baselines/frontend-workbench/{expected-artifacts,test-counts}.json` |

ADO MCP verification (`azure-devops-mcp`, org `shawn0864`) was attempted; the server process
exited during initialisation, so `pipeline_get_pipeline` / `pipeline_preview_pipeline_yaml` could
not be used. Templates were expanded manually from the `team/frontend-custom` branch and
cross-checked against `docs/samples/ado-api-responses.json` (definition 106, VG 210,
environments 5/6).

## 1. Triggers

| ADO | GHA | Note |
|---|---|---|
| `trigger.branches.include: [main, feature/*]` | `on.push.branches: [main, 'feature/**']` | **Intentional broadening**: ADO `feature/*` matches one level; GHA `feature/**` also matches `feature/a/b`. |
| `trigger.paths.include: [services/frontend-workbench/**]` | `on.push.paths` + `on.pull_request.paths` | Also includes the workflow file itself so workflow edits are exercised. |
| (none) | `on.pull_request.branches: [main]` | **Addition** per playbook — build only; deploy jobs are gated to `push`. |
| `pool.vmImage: ubuntu-latest` | `runs-on: ubuntu-latest` on every job | |

## 2. Stages → jobs

| ADO stage | Template / job | `dependsOn` | `condition` | GHA job | `needs` | `if` |
|---|---|---|---|---|---|---|
| `Build` ("Build frontend-workbench") | `job: build` → `frontend-build.yml` | — | — | `build` | — | — |
| `Deploy_Dev` ("Deploy to dev") | `frontend-deploy.yml` (env `dev`) → `deployment: deploy_frontend` | `Build` | — | `deploy_dev` | `build` | `github.event_name == 'push'` |
| `Deploy_Staging` ("Deploy to staging") | `frontend-deploy.yml` (env `staging`) | `Deploy_Dev` | `and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))` | `deploy_staging` | `deploy_dev` | `github.event_name == 'push' && github.ref == 'refs/heads/main'` |

`succeeded()` is implicit in GHA `needs` (a job is skipped when a needed job fails). Note that
`frontend-deploy.yml` is a *stages* template, so in ADO each consumer stage actually expands to a
nested stage named `DeployFrontend_<env>`; the 3-stage/3-job count is unchanged.

## 3. Expanded steps (source of truth)

Parameters resolved: `nodeVersion=18.x`, `framework=react`, `enableSSR=true`,
`artifactName=frontend-workbench-bundle`, `cdnPurge=true` (default).

### Build

| # | ADO task / step (resolved) | GHA step |
|---|---|---|
| 0 | (implicit checkout) | `actions/checkout@v4` |
| 1 | `NodeTool@0` `versionSpec: 18.x` | `actions/setup-node@v4` `node-version: '18.x'` |
| 2 | `script: npm ci` | `run: npm ci` |
| 3 | `script: npm run lint` | `run: npm run lint` |
| 4 | `script: npm run build:react` | `run: npm run build:react` |
| 5 | `${{ if eq(parameters.enableSSR, true) }}` → `script: npm run build:ssr` | `run: npm run build:ssr` (condition is compile-time true, so emitted unconditionally) |
| 6 | `script: npm test -- --ci --coverage` | `run: npm test -- --ci --coverage` |
| 7 | `ArchiveFiles@2` `rootFolderOrFile: build/`, `includeRootFolder: false`, `zip`, `archiveFile: $(Build.ArtifactStagingDirectory)/frontend-workbench-bundle.zip` | `mkdir -p "$BUILD_ARTIFACTSTAGINGDIRECTORY" && (cd build && zip -qr ".../frontend-workbench-bundle.zip" .)` |
| 8 | `script: npx lhci autorun --collect.staticDistDir=build/ \|\| true` | identical `run:`; the `\|\| true` is preserved so Lighthouse never fails the build |
| 9 | `PublishBuildArtifacts@1` `pathToPublish: $(Build.ArtifactStagingDirectory)`, `artifactName: frontend-workbench-bundle-$(Build.BuildId)` | `actions/upload-artifact@v4` `name: frontend-workbench-bundle-${{ github.run_id }}`, `path: $BUILD_ARTIFACTSTAGINGDIRECTORY`, `if-no-files-found: error` |

All build steps run with `working-directory: services/frontend-workbench` (see §7, gap 1).

### Deploy (dev, then staging — identical step list)

| # | ADO step (resolved) | GHA step |
|---|---|---|
| 0 | (deployment job — no checkout by default) | `actions/checkout@v4` (added; the playbook requires it first in every job) |
| 1 | `download: current`, `artifact: frontend-workbench-bundle` | `actions/download-artifact@v4` `name: frontend-workbench-bundle-${{ github.run_id }}` → `$BUILD_ARTIFACTSTAGINGDIRECTORY` (see §7, gap 2) |
| 2 | `script` "Upload to CDN" (two `echo`s) | same `echo`s + `test -f <bundle zip>` so a missing bundle fails the job |
| 3 | `${{ if eq(parameters.cdnPurge, true) }}` → `script` "Purge CDN cache" (`echo`) | same `echo` (compile-time true) |
| 4 | `script` "Health check": `curl -sf https://<env>.example.com/health \|\| exit 1` | `curl -sf "$HEALTH_CHECK_URL" \|\| exit 1` with `HEALTH_CHECK_URL = vars.HEALTH_CHECK_URL \|\| 'https://<env>.example.com/health'` |

## 4. Variables

| ADO | GHA |
|---|---|
| `variables.artifactName: frontend-workbench-bundle` | workflow `env.ARTIFACT_NAME` |
| `$(Build.ArtifactStagingDirectory)` | `env.BUILD_ARTIFACTSTAGINGDIRECTORY = ${{ github.workspace }}/staging` (created with `mkdir -p` in build; populated by `download-artifact` in deploy jobs) |
| `$(Build.BuildId)` (artifact suffix) | `${{ github.run_id }}` |
| `variables['Build.SourceBranch']` | `github.ref` |
| `${{ parameters.environment }}` | job `env.DEPLOY_ENVIRONMENT` (`dev` / `staging`) |
| VG 210 `CDN_ENDPOINT` | environment **variable** `vars.CDN_ENDPOINT` (also used as the environment `url`) |
| VG 210 `CDN_STORAGE_ACCOUNT` | environment **variable** `vars.CDN_STORAGE_ACCOUNT` |
| VG 210 `CDN_STORAGE_KEY` (secret) | environment **secret** `secrets.CDN_STORAGE_KEY` |
| VG 210 `CDN_PURGE_API_KEY` (secret) | environment **secret** `secrets.CDN_PURGE_API_KEY` |
| (hardcoded `https://<env>.example.com/health`) | environment variable `vars.HEALTH_CHECK_URL` (new, optional) |
| VG 201 `shared-ci-secrets` | not mapped — no step in the expanded pipeline reads it |

No helper script in `build-tools/scripts/` is invoked by either template, so no ADO env-var shims
(`BUILD_SOURCEBRANCH`, `PIPELINE_URL`, …) are needed and **no helper scripts were changed**.

## 5. Environments

| ADO environment (id) | Checks in ADO | GHA environment | Required repo settings |
|---|---|---|---|
| `dev-frontend` (5) | none | `dev-frontend` | Create environment; add vars/secrets from §4. |
| `staging-frontend` (6) | approval: `team-frontend`, min 1, "Verify SSR bundle and CDN purge before promoting" | `staging-frontend` | Create environment; **Required reviewers → `team-frontend`** (1 approval); optionally restrict deployment branches to `main`; add vars/secrets from §4. |

Settings → Environments → New environment. Environment protection rules are not expressible in
workflow YAML, so the reviewer requirement must be configured by a repo admin before the first
`main` push, otherwise `deploy_staging` runs unapproved.

## 6. Integration points

| Integration | In expanded ADO source? | GHA handling |
|---|---|---|
| Test execution | yes — `npm test -- --ci --coverage` | Same command in `Run tests`. ADO template has **no** `PublishTestResults@2`, so no test-report upload is added (parity). |
| Artifact publish | `PublishBuildArtifacts@1` (ADO pipeline artifacts, not Artifactory) | `actions/upload-artifact@v4`. There is no Artifactory / `register_artifact.py` call in this pipeline. |
| D2 notification | not present in `frontend-build.yml` / `frontend-deploy.yml` | Nothing to migrate. The inventory §5 lists 106 under "D2 Notification (via release stages)", but the alt-templates contain no `notify_d2.py` call — flagged as an inventory discrepancy to confirm with team-frontend. |
| Compliance attestation | not present | Nothing to migrate. |
| CDN upload / purge | `echo`-only in ADO template | `echo`-only preserved; credentials are wired into the job env so real commands can be dropped in without touching workflow plumbing. |

## 7. Known gaps / behavioural differences

1. **Working directory.** The ADO template runs `npm ci` etc. from the repo root, where there is no
   `package.json`; the runnable scaffold (PR #12) lives in `services/frontend-workbench`. The GHA
   build job sets `working-directory: services/frontend-workbench`. `ArchiveFiles@2 rootFolderOrFile: build/`
   therefore resolves to `services/frontend-workbench/build`.
2. **Artifact name mismatch fixed.** ADO publishes `frontend-workbench-bundle-$(Build.BuildId)` but
   the deploy template downloads `frontend-workbench-bundle` (no suffix) — a pre-existing defect that
   would fail `download: current`. GHA uses `frontend-workbench-bundle-${{ github.run_id }}` on both
   sides. (Deviation from strict parity, in favour of a working pipeline.)
3. **CDN upload/purge are still echoes** — exactly as in ADO. `CDN_*` vars/secrets are exposed but unused
   by the echo commands.
4. **Health check URL.** ADO hits `https://dev|staging.example.com/health`, which is a placeholder.
   GHA uses `vars.HEALTH_CHECK_URL` per environment and falls back to the ADO placeholder; until the
   variable is set, `deploy_*` will fail at `Health check` exactly as ADO would.
5. **Lighthouse.** `npx lhci autorun … || true` is preserved verbatim; in a fresh runner `npx`
   downloads `@lhci/cli` on each run. Non-blocking, as before.
6. **`--coverage`** is accepted but ignored by the scaffold's `node --test` runner; no coverage
   artifact exists in either system.
7. **Retention.** ADO kept builds 30 days / min 5; GHA artifacts use the repository default
   (90 days). Set `retention-days` on `upload-artifact` if 30 is required.
8. **`feature/*` → `feature/**`** broadening (see §1).
9. **PR builds** run `build` only; `deploy_dev` (which in ADO ran on every `feature/*` push with no
   gate) is unchanged for pushes.
10. **VG 201 `shared-ci-secrets`** is attached to definition 106 in ADO but never used; not recreated.

## 8. Secrets and variables to configure

| Scope | Name | Type | Source |
|---|---|---|---|
| env `dev-frontend`, `staging-frontend` | `CDN_ENDPOINT` | variable | VG 210 (`https://cdn.contoso-financial.com`) |
| env `dev-frontend`, `staging-frontend` | `CDN_STORAGE_ACCOUNT` | variable | VG 210 (`contosofrontendcdn`) |
| env `dev-frontend`, `staging-frontend` | `CDN_STORAGE_KEY` | secret | VG 210 |
| env `dev-frontend`, `staging-frontend` | `CDN_PURGE_API_KEY` | secret | VG 210 |
| env `dev-frontend`, `staging-frontend` | `HEALTH_CHECK_URL` | variable | new — real health endpoint per environment |

No repository-level secrets are required.

## 9. Baseline measurements

Measured locally (Node 18.20.8, `services/frontend-workbench`):

```
npm ci                       → 0 vulnerabilities
npm run lint                 → pass
npm run build:react          → build/client/bundle.js, build/index.html
npm run build:ssr            → build/ssr/server.js
npm test -- --ci --coverage  → 4 tests, 4 pass, 0 fail (tests/app.test.js)
zip -r bundle.zip . (in build/) → 1 file, 1547 bytes, 3 entries
```

Recorded in `validation/baselines/frontend-workbench/`.
