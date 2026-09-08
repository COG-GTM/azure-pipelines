# ADO Pipeline Inventory & Migration Classification

**Organization / project:** contoso-financial / shared-ci-platform
**ADO API snapshot:** 2026-03-17 (`docs/samples/ado-api-responses.json`)
**Repository state:** `main` @ `023c69b` plus 7 long-lived template branches
**Report date:** 2026-09-08

## How this inventory was built

| Source | What it contributed |
|---|---|
| `build_definitions` (18) | Pipeline IDs, YAML path, queue status, pool, triggers, variable groups, retention, `_meta.owner_team` / `last_modified_by` |
| `build_runs_summary` (18) | 90-day run counts, success/failure, average duration, last run |
| `variable_groups` (10), `service_connections` (5), `environments` (6), `agent_pools` (4) | Downstream systems each pipeline touches |
| Pipeline YAML on `main` | Actual steps, template references (`resources.repositories[].ref`), scripts invoked |
| `git diff main origin/<branch>` for all 7 template branches | Template drift and which branch each consumer really resolves against |
| `build-tools/**/*.py` | Which external systems the shared scripts call (Artifactory, D2, attestation-database) |

Every YAML entrypoint registered in ADO is in the repo, and every pipeline-shaped YAML in the repo is registered in ADO with one exception (`archive/old-release-workflow.yml`, see §3.3).

---

## 1. Summary

| Classification | Count | Pipelines |
|---|---|---|
| **Migrate** to GitHub Actions | 8 | 101, 102, 103, 104, 105, 106, 108, 109 |
| **Do not migrate** (non-build workload) | 7 | 107, 110, 111, 112, 113, 114, 115 |
| **Dead** (exclude entirely) | 3 | 116, 117, 118 |
| Total registered in ADO | 18 | |

Key flags (detail in §4 and §5):

- **5 pipelines with no confirmed owner**, 4 of them still active: `pricing-engine-ci` (101), `notebook-executor-nightly` (110), `scenario-runner-weekly` (111), `bulk-reprocess-trades` (115), `onetime-data-migration` (116).
- **Integration naming drift across branches.** `main` was renamed to use the real system names (Artifactory, D2, attestation-database) in PR #2; all 7 template branches still reference the old names (`artifact-registry`, `release-orchestrator`, `compliance-store`). ADO variable groups (`artifact-registry-credentials`, `compliance-store-credentials`) also use the old names. Any pipeline that resolves templates from a non-`main` branch (102, 104, 105, 106, 107) runs the *old* scripts.
- **7 of 18 pipelines invoke scripts or source that do not exist in this repository** (`adhoc/scripts/*.py`, `services/scenario-runner/src/*`, `services/notebook-executor/notebooks/`, `services/regulatory-reporting/src/*`, `services/*/requirements.txt`). Those pipelines depend on a separate checkout or an ADO-side artifact that the API dump does not show.
- **Two self-hosted pools carry all non-build load**: `linux-build-workers` (110, 113, 114) and `high-memory-pool` (111, 112). Nothing that must migrate to GHA depends on a self-hosted pool.

---

## 2. Pipeline inventory

Run statistics are the 90-day window ending 2026-03-17.

| ID | Pipeline | YAML | Status | Pool | Trigger | 90d runs (ok/fail) | Avg min | Last run | Owner (`_meta`) | Template ref |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | pricing-engine-ci | `services/pricing-engine/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main`, `release/*` | 47 (44/2) | 7.5 | 2026-03-14 | **unknown** | `main` |
| 102 | portfolio-api-ci | `services/portfolio-api/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main`, `master` | 31 (29/2) | 9.8 | 2026-03-12 | team-quant | `master` |
| 103 | portfolio-api-canary | `services/portfolio-api/azure-pipelines-canary.yml` | enabled | Azure Pipelines | manual (param) | 5 (5/0) | 8.5 | 2026-02-28 | team-quant | `main` / `master` / `staging/preprod` / `staging/release-hardening` |
| 104 | risk-batch-ci | `services/risk-batch/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main` | 38 (35/3) | 13.7 | 2026-03-15 | team-quant | `staging/preprod` |
| 105 | risk-batch-legacy | `services/risk-batch/azure-pipelines-legacy.yml` | enabled | Azure Pipelines | none (external) | 2 (2/0) | 8.7 | 2026-01-10 | team-quant | `legacy/master-support` |
| 106 | frontend-workbench-ci | `services/frontend-workbench/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main`, `feature/*` | 62 (58/3) | 12.3 | 2026-03-16 | team-frontend | `team/frontend-custom` |
| 107 | regulatory-reporting-ci | `services/regulatory-reporting/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main` + cron weekdays 06:00 | 65 (61/4) | 82.4 | 2026-03-17 | team-reporting | `team/reporting-hotfix` |
| 108 | market-sim-ci | `services/market-sim/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main` | 18 (16/2) | 23.4 | 2026-03-08 | team-quant | none (inline) |
| 109 | ops-control-plane-ci | `services/ops-control-plane/azure-pipelines.yml` | enabled | Azure Pipelines | CI `main` | 25 (24/1) | 7.8 | 2026-03-13 | platform-team | none (inline) |
| 110 | notebook-executor-nightly | `services/notebook-executor/azure-pipelines.yml` | enabled | linux-build-workers | cron daily 02:00 | 90 (72/0, 18 partial) | 165.2 | 2026-03-17 | **unknown** | none |
| 111 | scenario-runner-weekly | `services/scenario-runner/azure-pipelines.yml` | enabled | high-memory-pool | cron Fri 22:00 + manual | 13 (11/2) | 228.1 | 2026-03-14 | **unknown** | none |
| 112 | var-scenario-sweep-nightly | `night-jobs/compute/var-scenario-sweep.yml` | enabled | high-memory-pool | cron weekdays 01:00 | 65 (60/5) | 172.2 | 2026-03-17 | team-quant | none |
| 113 | daily-positions-export | `night-jobs/business/daily-positions-export.yml` | enabled | linux-build-workers | cron weekdays 23:00 | 65 (63/2) | 75.5 | 2026-03-16 | team-reporting | none |
| 114 | attestation-backfill-weekly | `night-jobs/compliance/attestation-backfill.yml` | enabled | linux-build-workers | cron Sun 03:00 | 13 (13/0) | 93.3 | 2026-03-16 | shared-ci-platform | none |
| 115 | bulk-reprocess-trades | `adhoc/bulk-reprocess-trades.yml` | enabled | Azure Pipelines | manual (params) | 3 (3/0) | 325.1 | 2026-02-25 | **unknown** | none |
| 116 | onetime-data-migration | `adhoc/onetime-data-migration.yml` | **paused** | Azure Pipelines | manual | 0 (1 run total, 2024-08-20) | 222.8 | 2024-08-20 | **unknown** | none |
| 117 | old-pricing-pipeline | `deprecated/old-pricing-pipeline.yml` | **disabled** | Azure Pipelines | none | 0 | — | 2023-06-15 | none | `legacy/master-support` |
| 118 | batch-runner-v1 | `deprecated/batch-runner-v1.yml` | **disabled** | Azure Pipelines | none | 0 | — | 2023-02-01 (failed) | none | none |

---

## 3. Classification

### 3.1 Migrate (8)

Software build/test/deploy pipelines running on the hosted pool. Each maps to a GHA workflow on `ubuntu-latest`; template consumers become callers of reusable workflows.

| ID | Pipeline | Why it is a build | Migration notes |
|---|---|---|---|
| 101 | pricing-engine-ci | `build-dotnet.yml` → `run-tests.yml` → `release-standard.yml` (dev). Only consumer already on `main`. Runnable .NET 8 scaffold exists in-repo with baselines in `validation/baselines/pricing-engine/`. | **Pilot candidate.** Blocked on ownership (§4). Uses Artifactory publish + D2 notify + attestation. |
| 102 | portfolio-api-ci | `build-java.yml` + `release-standard.yml` (staging) from `master`. | Consumes `master`, which is the *old* template set (see §6). Migrate against `main` semantics after confirming JDK/artifact name diffs are acceptable. Triggers on both `main` and `master` source branches. |
| 103 | portfolio-api-canary | Same Java build; exists only to A/B four template branches via a runtime parameter. | Migrate as a `workflow_dispatch` that pins a reusable-workflow `@ref`, or **retire** once template branches are consolidated — its only purpose is testing branch drift. |
| 104 | risk-batch-ci | `build-python.yml` + `run-tests.yml` + `release-standard.yml` (dev) from `staging/preprod`. | Depends on retry logic (`testRetryCount`, `pytest-rerunfailures`) that exists *only* on `staging/preprod`. Port retry into the canonical Python workflow before cut-over. Has an unreferenced local fork `pipeline-fragments/build-python-local.yml`. |
| 105 | risk-batch-legacy | `build-python-legacy.yml` (Python 3.9, unittest) from frozen `legacy/master-support`. `trigger: none` but `_meta` says "still triggered externally by downstream jobs"; 2 runs in 90 days. | Migrate as `workflow_dispatch` **only if** the external trigger can be identified. Otherwise fold into 104. Python 3.8/3.9 defaults are EOL. |
| 106 | frontend-workbench-ci | `frontend-build.yml` + `frontend-deploy.yml` (dev, staging) from `team/frontend-custom`. | Alt-templates are owned by the same team as the service — cleanest consolidation. Deploys to CDN via `frontend-cdn-config`; two GH environments needed (`dev-frontend`, `staging-frontend` with 1 team-frontend approver). |
| 108 | market-sim-ci | Inline Rust (rustup, clippy, build, test, publish). Deploys to a compute cluster "managed outside D2". | Direct translation. Central `build-rust.yml` exists but is unused. Deploy stage is an `echo` — confirm the real deploy mechanism before migrating. Uses `##vso[task.prependpath]`. Uses ACR service connection per API dump although YAML has no docker step. |
| 109 | ops-control-plane-ci | Inline Go 1.22 (mod verify, vet, test, static build, publish). | Direct translation. Central `build-go.yml` unused. `ops-infra-credentials` (K8s token) is attached but YAML has no deploy step — either dead binding or an ADO-side classic release consumes the artifact. |

### 3.2 Do not migrate — non-build workloads (7)

These use ADO agents as scheduled compute, ETL, or compliance automation. Moving them to GHA hosted runners is not possible (self-hosted network access, 3–8 h runtimes, 128 GB RAM) and moving them to GHA self-hosted runners only relocates the misuse. Each needs an owner decision and a target platform (K8s CronJob / Azure Container Instances / batch scheduler / existing night-jobs infrastructure).

| ID | Pipeline | Workload | Pool / runtime | Why not GHA |
|---|---|---|---|---|
| 107 | regulatory-reporting-ci | Compliance reporting: `team-build-custom.yml` wrapper, then `generate_reports.py`, `generate_metadata.py --store attestation-database`, `generate_attestation.py --env prod`. Runs weekdays 06:00 *and* on CI. 365-day retention. Bound to `prod` environment (2 approvers, business-hours gate, exclusive lock). | hosted, 82 min avg | Produces regulatory reports, not a deployable. **Split recommended:** the `ComplianceBuild` stage is a Python build and can move to GHA; the `GenerateReports` stage is a scheduled compliance job with prod-environment gates and audit retention and should move with 114 to the compliance job platform. Do not migrate as a single workflow. |
| 110 | notebook-executor-nightly | Executes every `*.ipynb` under `services/notebook-executor/notebooks/` with papermill; converts to HTML. | linux-build-workers, 165 min avg, 180 min timeout | Nightly compute; 18/90 runs partially succeeded (`##vso[task.logissue]` warnings swallow notebook failures). No owner. Notebooks directory is **not in this repo**. |
| 111 | scenario-runner-weekly | Monte Carlo (`run_scenarios.py`, default 10k scenarios) + aggregate. | high-memory-pool, 228 min avg, 360 min timeout | HPC-style compute; needs 128 GB / 32 cores and `compute-cluster` network. No owner. `services/scenario-runner/src/` is **not in this repo**. |
| 112 | var-scenario-sweep-nightly | 50k VaR scenarios at 95/99/99.9 %, upload to data-warehouse. | high-memory-pool, 172 min avg, 240 min timeout | Same as 111. Writes to `/tmp/var-results/` on the agent and uses `pipeline.startTime` expression. |
| 113 | daily-positions-export | pyodbc extract from positions-db → parquet → Excel summary → distribute to team-reporting/team-quant. | linux-build-workers, 75 min avg | ETL/report distribution. Needs positions-db + internal SMTP. Candidate for the existing night-jobs scheduler. |
| 114 | attestation-backfill-weekly | Scan attestation-database for 30-day gaps, regenerate, record metadata. 365-day retention. | linux-build-workers, 93 min avg | Compliance automation that *writes* to the system of record (`--dry-run false`). Must stay under compliance ownership and audit retention; pair with 107's report stage. |
| 115 | bulk-reprocess-trades | Manual, parameterised reprocessing of trade data by date range/type. 8 h timeout. | hosted, 325 min avg, 3 runs in 90 days | Operational data job, not a build. `adhoc/scripts/reprocess_trades.py` is **not in this repo**. No owner. Convert to a runbook/job on the data platform. |

### 3.3 Dead (3) — exclude from migration

| ID | Pipeline | Evidence | Action |
|---|---|---|---|
| 116 | onetime-data-migration | `queueStatus: paused`; 1 run ever (2024-08-20); YAML header says it "should have been deleted". Still holds `positions-db-credentials` (VG 213). Invokes `adhoc/scripts/migrate_data.py`, which does not exist. | Delete definition, remove VG 213 binding. |
| 117 | old-pricing-pipeline | `disabled`; 0 runs in 90 days; last run 2023-06-15; replaced by 101. References `legacy/master-support`. | Delete definition. Removes one of two consumers of `legacy/master-support`. |
| 118 | batch-runner-v1 | `disabled`; 0 runs; last run 2023-02-01 **failed**; Python 3.8; mixed build + compute. Replaced by 104 + 112. | Delete definition. |

Also dead but not registered in ADO (no definition, no runs): `archive/old-release-workflow.yml` (single `echo` step, archived Q3 2022). Delete with the above.

---

## 4. Ownership flags

Owner data comes from `_meta.owner_team` / `_meta.last_modified_by` in the API dump, YAML header comments, and `docs/ownership-gaps.md`. Anything below `high` confidence should be confirmed before a workflow is written.

| ID | Pipeline | Owner | Confidence | Last modified by | Flag |
|---|---|---|---|---|---|
| 101 | pricing-engine-ci | unknown (shared-ci-platform best-effort) | none | `contractor-account@contoso.com` | **Blocker for the pilot.** Original team disbanded; contractor engagement ended. No one to sign off artifact/test parity. |
| 110 | notebook-executor-nightly | unknown | none | `unknown-service-account@contoso.com` | Runs every night, 18 % partial failures, nobody claims it. YAML comment says "used by the quant team". Propose: team-quant confirms or job is switched off after a 30-day notice. |
| 111 | scenario-runner-weekly | unknown ("appears to be team-quant") | none | `unknown-service-account@contoso.com` | Manually re-run with custom params, so someone uses it — find them via ADO run `requestedFor` history. |
| 115 | bulk-reprocess-trades | unknown | none | `unknown-service-account@contoso.com` | Touches trade data with `internal-network-credentials`. Unowned write access to production data is a control gap independent of migration. |
| 116 | onetime-data-migration | unknown | none | `unknown-service-account@contoso.com` | Dead; delete rather than find an owner. |
| 102 / 103 | portfolio-api-ci / canary | team-quant | medium | `j.chen@contoso.com` | team-quant uses the service but may not own the codebase. |
| 108 | market-sim-ci | team-quant? | low | `r.nakamura@contoso.com` | Built independently; deploy target ("compute cluster, outside D2") undocumented. |
| 105 | risk-batch-legacy | team-quant | medium | `contractor-account@contoso.com` | Owner known, but the *external trigger* that still runs it is not. |
| 114 | attestation-backfill-weekly | shared-ci-platform? | medium | `k.johnson@contoso.com` | A CI platform team owning a compliance backfill that writes to the attestation system of record is itself a flag — should sit with team-reporting/compliance. |
| 113 | daily-positions-export | team-reporting? | medium | `l.garcia@contoso.com` | Consistent with 107's owner. |
| 104, 106, 107, 109, 112 | — | team-quant, team-frontend, team-reporting, platform-team, team-quant | high | — | No action. |

Template branch ownership: `staging/release-hardening` has **no owner and no confirmed consumer** (only reachable via canary 103 parameter); `team/quant-experiments` has an owner (team-quant) but **no consumer at all**; `legacy/master-support` has **no owner** and two consumers (105 active, 117 dead).

Scripts with no pipeline and no owner: `build-tools/scripts/send_daily_pnl_summary.py` and `build-tools/scripts/refresh_client_portfolio_cache.py` are business-ops scripts whose own docstrings say they should not be in this repo. No YAML in any branch invokes them. Either they run from an ADO classic (non-YAML) definition not in this dump, from cron on an agent, or they are dead. Confirm before the agents are decommissioned.

---

## 5. Downstream-tooling risks

### 5.1 Systems reached from pipelines

| System | Reached via | Pipelines | Risk |
|---|---|---|---|
| **Artifactory** | `build-tools/scripts/publish_artifact.py`, called from `build-dotnet.yml`, `build-java.yml`, `build-python.yml`, `publish-helpers.yml` with `--registry artifact-registry` | 101, 102, 104 (and 105/117 via legacy templates) | Script is a stub (prints, writes a manifest). The real publish path is not in-repo. Credentials in VG 205 `artifact-registry-credentials` (`ARTIFACT_REGISTRY_URL`, `ARTIFACT_REGISTRY_TOKEN`) — name does not match the system. Branch copies of the script still say `artifact-registry`. |
| **D2** (deployment tracking) | `build-tools/scripts/notify_release_orchestrator.py`, called from `release-standard.yml`, `release-prod.yml`, `release-notify.yml` | 101, 102, 104, 106 (via release stages); 108 explicitly bypasses it | Downstream release tracking will lose events for any service migrated without re-implementing the notify step. `market-sim` already deploys outside D2 — unknown whether D2 consumers depend on completeness. `validation-strategy.md` still calls it "release-orchestrator". |
| **attestation-database** (compliance system of record) | `build-tools/scripts/generate_attestation.py` (release-standard, release-prod, release-hotfix, publish-helpers, 107) and `build-tools/compliance/generate_metadata.py` (team-build-custom, 107, 114) | 101, 102, 104, 107, 114 | Regulatory. VG 206 is named `compliance-store-credentials` (`COMPLIANCE_STORE_URL`, `COMPLIANCE_STORE_TOKEN`, `COMPLIANCE_STORE_CERT_THUMBPRINT`). On all 7 non-`main` branches the templates pass `--store compliance-store`; on `main` they pass `attestation-database`. If these are distinct endpoints, 107 (on `team/reporting-hotfix`) is writing to a different store than 114 (on `main`). **Must be resolved before any compliance workflow moves.** Also uses `##vso`-free scripts but requires cert thumbprint auth that has no GHA analogue without a self-hosted runner or OIDC redesign. |
| Azure (ARM) | Service connections `AzureSubscription-Dev/Staging/Prod` (SPN + secret) | 101, 104, 106 (dev); 102, 106 (staging); 107 (prod) | Move to OIDC federated credentials per environment. `AzureSubscription-Prod` is used only by the non-build 107. |
| ACR `contosofinancial.azurecr.io` | `ContainerRegistry-ACR` | 108, 109 | Neither YAML contains a docker step — binding is either stale or used by an ADO-side step not in YAML. Verify before dropping. |
| Kubernetes `k8s.internal…:6443` | VG 211 `ops-infra-credentials` | 109 | Same: bound but unused in YAML. |
| CDN storage / purge | VG 210 `frontend-cdn-config`, `frontend-deploy.yml` | 106 | Two secret keys per environment; straightforward GH environment secrets. |
| data-warehouse | VG 212, `upload_results.py` | 112 | Non-build only. |
| positions-db | VG 213, pyodbc | 113, 116 | Non-build / dead only. Delete 116 binding. |
| internal SMTP / distribution | `distribute_report.py`, `REPORTING_SMTP_SERVER` | 113, 107 | Non-build only. |
| Package feeds (NuGet/PyPI/npm) | VG 201 `shared-ci-secrets` | 101–107, 109 | Org-level secrets; low risk. |
| `GitHub-SourceMirror` PAT connection | — | none | Unused; delete. |
| `windows-build-workers` pool | — | none in YAML | Legacy, half offline, `isLegacy: true`. Nothing in this dump uses it; decommission after checking for classic definitions. |

### 5.2 Structural risks

| Risk | Affected | Detail |
|---|---|---|
| **Scripts/source referenced but absent from repo** | 107, 110, 111, 115, 116; 104 (`services/risk-batch/requirements.txt`), 107 (`services/regulatory-reporting/requirements.txt`) | The pipelines cannot be reproduced from this repo alone. Either a second repo is checked out implicitly, or ADO-side settings inject it. Confirms these are not self-contained builds. |
| **Template naming drift between `main` and every branch** | 102, 104, 105, 106, 107 | `main` differs from each branch in 21–23 files, mostly the integration renames from PR #2 plus the pricing-engine scaffold. Consumers on branches therefore run *older* `build-dotnet`/`build-java`/`build-python` and older scripts. `main` is not a safe "source of truth" for what those pipelines actually execute; diff the consuming branch when writing each workflow. |
| **ADO-only syntax** | 108, 110 (`##vso[...]`); 112, 113 (`$[format(..., pipeline.startTime)]`); 101, 102, 104, 106, 107 (`deployment:` jobs with `strategy: runOnce`); all (`PublishBuildArtifacts@1`, `$(Build.*)`) | Mechanical but must be handled per workflow. |
| **Environment gates without GHA equivalents** | 107 (`prod`: business-hours Mon–Thu 09:00–16:00 ET, exclusive lock); `preprod` (unused: business hours Mon–Fri) | GHA has required reviewers and `concurrency`, but no native business-hours check. Only a non-build pipeline is affected. |
| **Retention** | 107, 114 (365 days, min 50/52) | GHA artifact max is 90 days on hosted plans; audit retention must move to external storage. |
| **`release-hotfix.yml` bypasses gates** | none today | Template exists on `main`, generates attestation with `--hotfix true`, no approval. Do not port to GHA as-is. |
| **Unreferenced templates** | `build-rust.yml`, `build-go.yml`, `build-node.yml` (main), `release-hotfix.yml`, `release-preprod.yml`, `release-prod.yml`, `release-old.yml`, all 4 `alt-templates/data-science/*`, `pipeline-fragments/build-python-local.yml`, `build-tools/yaml/common-setup.yml` | 13 templates with zero consumers in any branch. Do not migrate; delete after the branch consolidation. |

---

## 6. Template branch matrix

`git diff --stat main origin/<branch>` (excluding `docs/`, `validation/`, `.github/`, pricing-engine source). Every branch also lacks PR #2's integration renames and the pricing-engine scaffold.

| Branch | Owner | Consumers | Template-specific drift vs `main` | Disposition |
|---|---|---|---|---|
| `main` | shared-ci-platform | 101, 103 (param) | canonical | Source for reusable workflows |
| `master` | shared-ci-platform | 102, 103 (param) | `build-dotnet` 6.0.x; `build-python` 3.10, linting off, artifact `python-package`; `build-java` older | Merge nothing; retarget 102 to `main` semantics after verifying artifact name change is acceptable to downstream consumers |
| `staging/preprod` | team-quant (assumed) | 104, 103 (param) | `build-python` +`testRetryCount`, `pytest-rerunfailures` retry loop, preprod stamp file | **Port retry logic to canonical Python workflow**, then delete |
| `staging/release-hardening` | unknown | 103 (param) only | `release-standard` `requireApproval: true`, pre-deploy `compare_build_outputs.py`, health-check retry | No real consumer. Evaluate for adoption as the standard release workflow; otherwise delete |
| `team/frontend-custom` | team-frontend | 106 | `frontend-build` +Lighthouse CI, artifact `-$(Build.BuildId)`; `build-node` Node 18, +SSR, +Storybook | Becomes the frontend reusable workflow directly (same owner) |
| `team/quant-experiments` | team-quant | **none** | `build-python` +conda, +GPU pool, +timeout param | No consumer; harvest conda option if wanted, then delete |
| `team/reporting-hotfix` | team-reporting | 107 | `team-build-custom` +audit trail, +pre-build `generate_metadata.py --store compliance-store` | Non-build consumer; carry to the compliance job platform, not GHA. Resolve `compliance-store` vs `attestation-database` first |
| `legacy/master-support` | none | 105 (active), 117 (dead) | `build-dotnet` 6.0.x; `build-python` 3.8, linting off, artifact `python-legacy-dist`; FROZEN banners | Delete after 105 is folded into 104 and 117 is removed |

---

## 7. Recommended sequencing

1. **Resolve blockers that do not need code**: confirm owner for 101; identify 105's external trigger; confirm whether `compliance-store` and `attestation-database` are the same endpoint; confirm ACR/K8s bindings on 108/109 are dead.
2. **Delete dead**: 116, 117, 118, `archive/old-release-workflow.yml`, `GitHub-SourceMirror`, VG 213 binding on 116. Audit `windows-build-workers` for classic definitions, then decommission.
3. **Pilot**: 101 (only `main` consumer, scaffold + baselines exist, `validate-migration` workflow already gates `.github/workflows/**`). Then 109 and 108 (inline, no template dependency).
4. **Consolidate templates**: port `staging/preprod` retry into canonical Python; publish reusable workflows for dotnet/java/python/node; migrate 104, 102, 106; retire 103 and the `master`, `staging/*`, `team/quant-experiments`, `legacy/master-support` branches.
5. **Fold 105** into 104 as `workflow_dispatch` or delete.
6. **Non-build track (separate programme, not GHA)**: 110–115 and the report stage of 107 move to a scheduled-compute platform with the same internal network reach; 107's build stage moves to GHA. Owners for 110, 111, 115 must be found first — recommend a 30-day "claim or switch off" notice for 110 and 115.
