# Playbook: Migrate one ADO pipeline to GitHub Actions (COG-GTM/azure-pipelines)

## Overview
Migrate a single Azure DevOps pipeline from `COG-GTM/azure-pipelines` to a GitHub Actions
workflow that reuses the composite actions under `.github/actions/` (the pattern established by
the pricing-engine pilot, ADO 101) and passes the repo's `validate-migration` harness at 7/7.
Each run of this playbook owns exactly one pipeline and only the files listed for it in
`docs/migration-parallelization-plan.md`, so several runs can execute in parallel.

## What's Needed From User
- ADO pipeline ID (101–109) — everything else is derived from `docs/pipeline-inventory-report.md` §2.
- Confirmation that any Track A blocker listed for that ID in `docs/migration-parallelization-plan.md` §6 is resolved (or an explicit instruction to proceed anyway).

Only ever create the todo list for the current phase.

<phase name="Context" id="1">
## Context

1. Clone `COG-GTM/azure-pipelines`, `git fetch --no-tags origin '+refs/heads/*:refs/remotes/origin/*'` (the validator resolves templates from `origin/<branch>`).
2. Read `docs/migration-parallelization-plan.md` and find your pipeline's row in §4 (file ownership). Those are the ONLY paths you may create or edit. Note the prior draft PR listed for your pipeline in §7; read its diff for hints but do not reuse its branch.
3. Read `docs/pipeline-inventory-report.md` §2 and §3.1 for your pipeline: YAML path, template branch (`ref:`), owner, migration notes.
4. Read the ADO YAML and every template it references **at the branch it actually consumes** (`git show origin/<ref>:<template path>`), not `main`. Record for each: stage list, step list, integration scripts called (`publish_artifact.py`, `notify_release_orchestrator.py`, `generate_attestation.py`, `generate_metadata.py`, `normalize_test_results.py`) and the exact `--registry/--store` values used.
5. Read the reference implementation: `.github/workflows/pricing-engine-ci.yml`, `.github/actions/{ado-env-shim,build-dotnet,run-tests,release-standard}/action.yml`, `docs/migration/pricing-engine-ci-ado-to-gha-mapping.md`.
6. Check whether a language composite action for your stack already exists in `.github/actions/build-<lang>/`. If it does not and your row in the plan says you own it, you will author it in Phase 2; if another session owns it, stop and report — do not create a duplicate.

<verification>
- The pipeline's ADO YAML and all templates were read at the consuming branch, and the stage/step/integration list is written down
- The exact set of files this session may touch is written down and matches the plan's ownership table
- It is known whether the `build-<lang>` composite action exists or must be authored here
</verification>
</phase>

<phase name="Implement" id="2">
## Implement

1. Create branch `devin/$(date +%s)-<pipeline-name>-gha-migration` from `origin/main`.
2. If you own a new `.github/actions/build-<lang>/action.yml`: mirror the ADO build template's parameters as kebab-case inputs with the same defaults, start with `uses: ./.github/actions/ado-env-shim`, keep the ADO `displayName` text as step names, run tests with a JUnit/TRX logger into `$BUILD_ARTIFACTSTAGINGDIRECTORY/test-results`, upload `${{ runner.temp }}/staging` as the artifact, and finish with `publish_artifact.py --registry Artifactory`. Do not edit any existing action under `.github/actions/`.
3. Create `.github/workflows/<pipeline-name>.yml` with the filename the validator maps (`validate-migration.yml` `case` block): `pricing-engine-ci`, `portfolio-api-ci`, `risk-batch-ci`, `risk-batch-legacy`, `market-sim-ci`, `ops-control-plane-ci`, `frontend-workbench-ci`, `regulatory-reporting-ci`. Header: `# Migrated from: <ado yaml> (ADO pipeline ID <n>)`.
4. Map triggers 1:1: ADO `trigger.branches` → `on.push.branches`; ADO `paths` → `on.push.paths` plus `.github/workflows/<file>` and `.github/actions/**`; add `pull_request` on `main` and `workflow_dispatch`. Cron schedules → `on.schedule` only for build stages (never for report/compute stages — those are Track F).
5. Create **exactly one GHA job per ADO stage**, in the same order, with `needs:` mirroring `dependsOn` and `if:` mirroring `condition`. Deployment stages become a job with `environment: <env>` calling `./.github/actions/release-standard`. Give jobs `name:` equal to the ADO `displayName`.
6. Inline pipelines (108, 109) get no composite action for the build: translate steps directly, but still use `ado-env-shim` and keep the Artifactory / D2 / attestation / test keywords in step names when the ADO source has them.
7. Replace ADO-only syntax: `$(Build.BuildId)` → `$GITHUB_RUN_ID`, `$(Build.SourcesDirectory)` → `$GITHUB_WORKSPACE`, `$(Build.ArtifactStagingDirectory)` → `$BUILD_ARTIFACTSTAGINGDIRECTORY` (set by the shim), `##vso[task.prependpath]` → `echo "<path>" >> "$GITHUB_PATH"`, `PublishBuildArtifacts@1` → `actions/upload-artifact@v4`, `download: current` → `actions/download-artifact@v4`.
8. Use the real integration names on `main` (`Artifactory`, D2, `attestation-database`) even when the consuming branch says `artifact-registry` / `release-orchestrator` / `compliance-store`; list each such rename in the mapping doc.
9. Create or update only your service's baselines under `validation/baselines/<service>/` (`expected-artifacts.json`, `test-counts.json`). Never write `status: provisional` or the words placeholder/provisional — the validator fails those. Measure counts from the scaffold in `services/<service>/` when it is runnable.
10. Write `docs/migration/<pipeline-name>-ado-to-gha-mapping.md`: stage → job table, template step → action step table, ADO variable → shim variable, list of things intentionally not ported and why.

<verification>
- Job count equals the ADO stage count and job order matches
- No file outside the ownership row was created or modified (`git status --porcelain` checked)
- No existing file under `.github/actions/`, `validation/scripts/`, `build-tools/`, or `docs/pipeline-inventory-report.md` was modified
</verification>
</phase>

<phase name="Validate" id="3">
## Validate

1. `actionlint .github/workflows/<pipeline-name>.yml` → zero findings.
2. `python3 -c "import yaml,sys;[yaml.safe_load(open(p)) for p in sys.argv[1:]]" .github/actions/*/action.yml`.
3. `python3 validation/scripts/validate_migration.py --service <service> --ado-pipeline <ado yaml> --gha-workflow .github/workflows/<file> --baselines validation/baselines --repo-root "$PWD"` → 7/7 PASS. If Integration Points fails, fix by making the step that performs the integration carry the keyword (Artifactory, D2, attestation, test) in its name — never by editing the validator.
4. Run the service scaffold locally if the toolchain is installable (`dotnet test`, `mvn test`, `pytest`, `npm test`, `cargo test`, `go test ./...`) and confirm the numbers match `test-counts.json`.
5. For `frontend-workbench` only: start the dev server, open it in the browser, click through the main pages, and record the screen as proof the app still works.
6. Dry-run the integration scripts with the same flags the workflow passes: `mkdir -p /tmp/stg && BUILD_ARTIFACTSTAGINGDIRECTORY=/tmp/stg python3 build-tools/scripts/publish_artifact.py --name x --registry Artifactory --build-id 1` (repeat for notify/attestation scripts used).

<verification>
- actionlint output is empty
- validate_migration.py scorecard shows 7/7 PASS and the table is saved for the PR description
- Every integration script the workflow calls ran locally with the exact flags used in the workflow
</verification>
</phase>

<phase name="Deliver" id="4">
## Deliver

1. Commit with a message containing `feature` (e.g. `feature: migrate <pipeline-name> (ADO <n>) to GitHub Actions`). Never amend.
2. Push and open a PR against `main`. Body: purpose, the 7/7 scorecard table, the ownership row you claimed, integration renames, anything not ported. End the description with the line `Devin-Org: engineering`.
3. Wait for the `validate-migration` check; its PR comment must show 7/7 for your workflow. Fix and push until green.
4. Comment on the superseded draft PR from plan §7 (if any) with a link to your PR; do not close it unless the plan says the tracking owner may.
5. Show the mapping doc and scorecard to the user in the session (attach the file), and report which plan row is now complete so the tracking owner can update `docs/migration-parallelization-plan.md` §8.

<verification>
- PR is open, CI `validate-migration` is green with 7/7 for this workflow
- PR description ends with `Devin-Org: engineering` and the commit message contains `feature`
- Mapping doc was attached to the session and the completed plan row was reported
</verification>
</phase>

## Specifications
- Deliverable: one PR containing `.github/workflows/<pipeline-name>.yml`, `docs/migration/<pipeline-name>-ado-to-gha-mapping.md`, `validation/baselines/<service>/*`, and (only if assigned) one new `.github/actions/build-<lang>/action.yml`.
- `validate_migration.py` reports 100 % (7/7) locally and in CI.
- Every job runs on `ubuntu-latest`; no self-hosted runner labels.
- Every deployment job declares `environment:` and calls `./.github/actions/release-standard`.
- Integration steps use the `main` system names: Artifactory, D2, attestation-database.

## Advice and Pointers
- Read templates at the consuming branch: `master`, `staging/preprod`, `team/frontend-custom`, `legacy/master-support` all differ from `main` (JDK/Python versions, artifact names, retry logic). Port the behaviour the pipeline really has, then note deltas from `main`.
- 104 must carry `staging/preprod`'s `testRetryCount` / `pytest-rerunfailures` loop into the python build action (`--reruns`).
- The validator reads only the caller workflow's `steps`; a `jobs.<id>.uses:` reusable workflow has none and fails stage mapping and integration detection. Use composite actions.
- `env.` context is available in step-level `with:` for composite actions; that is how `ARTIFACT_NAME` reaches the actions.
- The `dev`, `staging`, `dev-frontend`, `staging-frontend` GitHub environments must exist in repo settings before the deploy job can run; ask the user if the run fails with an environment error.

## Forbidden Actions
- Do not edit `docs/pipeline-inventory-report.md`, `validation/scripts/**`, `.github/workflows/validate-migration.yml`, `build-tools/**`, or any file owned by another row of the plan.
- Do not modify or rename an existing composite action; add inputs only through the session that owns it.
- Do not migrate non-build stages (report generation, notebook execution, scenario sweeps, data exports) to GHA — those belong to Track F.
- Do not delete ADO YAML, templates, or branches — that is Track B / Wave 2 work.
- Do not mark baselines provisional or invent counts you did not measure.
