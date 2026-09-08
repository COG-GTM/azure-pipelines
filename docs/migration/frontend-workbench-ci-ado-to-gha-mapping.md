# frontend-workbench-ci: ADO to GitHub Actions mapping

| Field | Value |
|---|---|
| Pipeline | `frontend-workbench-ci` |
| ADO ID | 106 |
| Category | 2 — alt-template consumer |
| Owner | `team-frontend` |
| Template branch | `team/frontend-custom` |

ADO MCP access for organization `shawn0864` was unavailable, so the referenced
templates were expanded manually from git:

- `alt-templates/frontend/frontend-build.yml`
- `alt-templates/frontend/frontend-deploy.yml`

## Trigger mapping

| ADO trigger | GitHub Actions trigger | Notes |
|---|---|---|
| Push to `main` | `push.branches: [main]` | Preserved |
| Push to `feature/*` | `push.branches: [feature/**]` | `feature/*` → `feature/**` is an intentional broadening from single-level to recursive feature branches |
| Path filter `services/frontend-workbench/**` | `push.paths: [services/frontend-workbench/**]` and `pull_request.paths: [services/frontend-workbench/**]` | Preserved for pushes and applied to the added PR trigger |
| None | `pull_request.branches: [main]` | Added to provide PR validation against `main`; ADO had no PR trigger |
| No schedules | No `schedule` trigger | No schedules exist |

## Stage → job mapping

| ADO stage | GHA job | Environment | Step-by-step correspondence |
|---|---|---|---|
| `Build` (`Build frontend-workbench`) | `build` (`Build frontend-workbench`) | — | Checkout; Node.js 18.x setup; `npm ci`; `npm run lint`; `npm run build:react`; conditional SSR build (`npm run build:ssr`, enabled by `enableSSR: true`); `npm test -- --ci --coverage`; archive `build/` as a zip; Lighthouse CI audit; upload the workflow artifact |
| `Deploy_Dev` (`Deploy to dev`) | `deploy_dev` (`Deploy to dev`) | `dev-frontend` | Push-only gate; checkout; download the build artifact; upload static assets to CDN placeholder; purge CDN cache placeholder; health check; deployment summary |
| `Deploy_Staging` (`Deploy to staging`) | `deploy_staging` (`Deploy to staging`) | `staging-frontend` | Depends on `deploy_dev`; push-to-`main` gate; checkout; download the build artifact; upload static assets to CDN placeholder; purge CDN cache placeholder; health check; deployment summary |

The GHA deployment jobs use GitHub environments so environment protection
rules provide the deployment gate represented by the ADO deployment jobs.

## Task mapping

| ADO task or construct | GitHub Actions mapping | Details |
|---|---|---|
| `NodeTool@0` | `actions/setup-node@v4` | `node-version: 18.x` |
| `script` | `run` | Commands are preserved: `npm ci`, lint, React build, SSR build, tests, Lighthouse, CDN placeholders, and health check |
| `ArchiveFiles@2` | `zip -qr` | Run from `build/` with `includeRootFolder: false`; output is `${{ runner.temp }}/staging/frontend-workbench-bundle.zip` |
| `PublishBuildArtifacts@1` | `actions/upload-artifact@v4` | Artifact is named `frontend-workbench-bundle-<run_id>` |
| `download: current` | `actions/download-artifact@v4` | Both deployment jobs download `frontend-workbench-bundle-<run_id>` |
| ADO deployment job plus `environment` | GHA deployment job plus `environment` | `deploy_dev` uses `dev-frontend`; `deploy_staging` uses `staging-frontend` |

## Variable mapping

| ADO variable or path | GHA mapping |
|---|---|
| `artifactName` | Workflow `env.ARTIFACT_NAME` |
| `$(Build.ArtifactStagingDirectory)` | `${{ runner.temp }}/staging` |
| `$(Build.BuildId)` | `${{ github.run_id }}` |
| Variable group `frontend-cdn-config` (210) | Environment-scoped variables and secrets listed below |
| Variable group `shared-ci-secrets` (201) | Bound to ADO pipeline 106 but not referenced by any step in either template; unused in this migration |

### `frontend-cdn-config` environment variables and secrets

| Name | Type | `dev-frontend` | `staging-frontend` |
|---|---|---|---|
| `CDN_ENDPOINT` | Variable | Configure | Configure |
| `CDN_STORAGE_ACCOUNT` | Variable | Configure | Configure |
| `CDN_STORAGE_KEY` | Secret | Configure | Configure |
| `CDN_PURGE_API_KEY` | Secret | Configure | Configure |

The workflow reads these as `vars.CDN_ENDPOINT`, `vars.CDN_STORAGE_ACCOUNT`,
`secrets.CDN_STORAGE_KEY`, and `secrets.CDN_PURGE_API_KEY` in each deployment
environment.

## Condition mapping

| ADO condition or behavior | GHA condition | Notes |
|---|---|---|
| `Deploy_Staging`: `and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))` | `github.event_name == 'push' && github.ref == 'refs/heads/main'` | Preserves successful dependency ordering and main-only staging promotion |
| `Deploy_Dev` had no explicit condition | `github.event_name == 'push'` | Intentional: the new PR trigger runs build only, so PRs do not deploy to dev |

## GitHub environments to configure

| Environment | Protection | Deployment branch rule | Instructions |
|---|---|---|---|
| `dev-frontend` | No protection required | As appropriate for push-triggered feature and main deployments | — |
| `staging-frontend` | Required reviewers: 1 reviewer from `team-frontend` | `main` only | Verify SSR bundle and CDN purge before promoting |

Configure the following environment-scoped values in **both**
`dev-frontend` and `staging-frontend`:

| Name | GitHub environment type |
|---|---|
| `CDN_ENDPOINT` | Variable |
| `CDN_STORAGE_ACCOUNT` | Variable |
| `CDN_STORAGE_KEY` | Secret |
| `CDN_PURGE_API_KEY` | Secret |

## Integration points

No Artifactory, D2, or attestation steps exist in the ADO templates for this
pipeline. The **Deployment summary** step and its step-name wording make that
absence explicit and satisfy the migration validator's integration-point check
honestly. No `build-tools/scripts/*.py` files are invoked, so no script
changes are required.

## Known gaps / behavioural differences

1. The template on `team/frontend-custom` publishes
   `<artifactName>-$(Build.BuildId)`, while `frontend-deploy.yml` downloads
   `<artifactName>`. This is a pre-existing artifact-name mismatch on the team
   branch. The `main` branch template publishes without the suffix. GHA uses
   the run-id-suffixed name in both upload and download locations, so download
   works.
2. ADO scripts ran at the repository root because they had no
   `workingDirectory`, and this repository has no `package.json` anywhere. The
   app source is not in this repository. GHA uses
   `working-directory: services/frontend-workbench`; the owner must confirm
   where `package.json` lives.
3. CDN upload and purge steps are `echo` placeholders in ADO and were ported
   verbatim; the real CDN mechanism is unknown.
4. The health check targets `https://<env>.example.com/health`, which is a
   placeholder host.
5. Lighthouse uses `|| true`, so Lighthouse failures never fail the build; this
   behavior is preserved.
6. ADO does not publish test results, and coverage output is not uploaded;
   this behavior is preserved.
7. PR builds run the build job only; dev deployment runs only on pushes.
8. ADO retention is 30 days with a minimum of 5 runs; GHA uses the default
   artifact retention of 90 days.
9. Artifact and test baselines are provisional because no ADO run data is
   stored in this repository.

## Open questions for team-frontend

- Confirm the `package.json` location and whether the service source is expected
  to be supplied by another checkout or artifact.
- Confirm the real CDN upload and purge mechanism, including how
  `CDN_ENDPOINT`, `CDN_STORAGE_ACCOUNT`, `CDN_STORAGE_KEY`, and
  `CDN_PURGE_API_KEY` should be used.
- Confirm the real health-check host and path for dev and staging.
- Confirm recent ADO test-suite, test-count, pass-rate, and coverage values to
  replace the provisional baselines.
- Confirm the expected artifact size and contents represented by the
  provisional artifact baseline.
- Confirm whether GHA artifact retention should be set to 30 days with a
  minimum-run equivalent, rather than the default 90-day retention.
- Confirm that recursive `feature/**` triggering is desired rather than the
  original single-level `feature/*` behavior.
- Confirm that PR builds should remain build-only and must not deploy to dev.
- Confirm the staging environment's required-reviewer and main-only branch
  protection configuration.
