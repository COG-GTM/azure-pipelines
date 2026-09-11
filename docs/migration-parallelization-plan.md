# Migration Parallelization Plan

Single source of truth for running the ADO → GitHub Actions migration as many parallel Devin
sessions. Classification comes from `docs/pipeline-inventory-report.md` (do **not** edit that file
from migration sessions). This file has exactly one owner (the tracking owner, §8); every other
session reports completions to that owner instead of editing this file.

## 1. Approach: pilot, then playbook fan-out

1. **Pilot (done in this PR):** ADO 101 `pricing-engine-ci` migrated with shared composite actions
   under `.github/actions/` and a caller workflow that passes `validate-migration` 7/7.
2. **Playbook:** `docs/migration/playbook-migrate-ado-pipeline.md` (also registered as a Devin
   playbook) turns the pilot into a repeatable per-pipeline procedure parameterised by ADO ID.
3. **Fan-out:** one playbook run per pipeline, each confined to the ownership row in §4.

Composite actions (not `jobs.<id>.uses` reusable workflows) are the shared pattern because the
validator only inspects caller-visible job steps; a reusable-workflow job has none and fails stage
mapping and integration detection.

## 2. Tracks

| Track | Scope | Code? | Sessions |
|---|---|---|---|
| A | Blocker investigations (§6) | No | 1 |
| B | Retire 116/117/118, `archive/old-release-workflow.yml`, `GitHub-SourceMirror`, 13 unreferenced templates (§5.2 of inventory) | Deletes only | 1 |
| C | Inline builds 108, 109 | Yes | 2 (one per pipeline) |
| D | Pilot 101 + shared actions | Yes | 1 (this PR) |
| E | Template consumers 102 (java), 104 (python), 106 (node) | Yes | 3 (one per language) |
| F | Rehome 110–115 + 107 `GenerateReports` to scheduled compute; 107 `ComplianceBuild` → GHA | Design + code outside `.github/workflows/` | 1–2 |

## 3. Waves

| Wave | Runs in parallel | Gate to start |
|---|---|---|
| 0 | A, B, C(108), C(109), D | none — D merged first is preferred but C does not depend on D |
| 1 | E(102), E(104), E(106), F | D merged (shared actions exist); A results for 101 owner and compliance endpoint |
| 2 | fold 105 into 104's workflow; retire 103; delete branches `master`, `staging/*`, `team/quant-experiments`, `legacy/master-support` | all Wave 1 PRs merged; A confirmed 105's external trigger |

## 4. File ownership (one owner per row; nothing outside your row)

| Session | Creates / edits | Never touches |
|---|---|---|
| D — 101 (this PR) | `.github/actions/ado-env-shim/`, `.github/actions/build-dotnet/`, `.github/actions/run-tests/`, `.github/actions/release-standard/`, `.github/workflows/pricing-engine-ci.yml`, `docs/migration/pricing-engine-ci-*.md`, `docs/migration/playbook-*.md`, this file | everything else |
| C — 108 | `.github/workflows/market-sim-ci.yml`, `docs/migration/market-sim-ci-*.md`, `validation/baselines/market-sim/` | `.github/actions/**` |
| C — 109 | `.github/workflows/ops-control-plane-ci.yml`, `docs/migration/ops-control-plane-ci-*.md`, `validation/baselines/ops-control-plane/` | `.github/actions/**` |
| E — 102 java | `.github/actions/build-java/`, `.github/workflows/portfolio-api-ci.yml`, `docs/migration/portfolio-api-ci-*.md`, `validation/baselines/portfolio-api/` | other `.github/actions/*` |
| E — 104 python | `.github/actions/build-python/`, `.github/workflows/risk-batch-ci.yml`, `docs/migration/risk-batch-ci-*.md`, `validation/baselines/risk-batch/` | other `.github/actions/*` |
| E — 106 node | `.github/actions/build-node/`, `.github/workflows/frontend-workbench-ci.yml`, `docs/migration/frontend-workbench-ci-*.md`, `validation/baselines/frontend-workbench/` | other `.github/actions/*` |
| Wave 2 — 105 | `.github/workflows/risk-batch-ci.yml` (add legacy job/inputs), `validation/baselines/risk-batch/` | starts only after 104 merged |
| Wave 2 — 103 | `services/portfolio-api/azure-pipelines-canary.yml` (delete), `docs/migration/portfolio-api-canary-*.md` | `.github/workflows/**` |
| B | `deprecated/`, `adhoc/`, `archive/`, the 13 templates in inventory §5.2, `README.md` template table rows for deleted files | `services/**`, `.github/**` |
| F | `docs/migration/rehome-*.md`, new `scheduled-jobs/**` (K8s CronJob / ACI manifests), `.github/workflows/regulatory-reporting-ci.yml` (ComplianceBuild only) | `services/**` ADO YAML until owners confirm |
| A | `docs/migration/blockers.md` only | all code |
| Tracking owner | this file (§8 status), closing superseded PRs | pipeline files |

Shared, edit-locked after this PR merges: `.github/actions/{ado-env-shim,run-tests,release-standard}`,
`validation/scripts/**`, `.github/workflows/validate-migration.yml`, `build-tools/**`,
`docs/pipeline-inventory-report.md`. Changes to any of these go through a dedicated PR by the
tracking owner, never inside a pipeline migration PR.

## 5. Serialization constraints

- One owner per language composite action (`build-java`, `build-python`, `build-node`); a session
  that finds its action missing and unowned stops and reports instead of creating it.
- Shared shim (`ado-env-shim`) and `release-standard` land in Wave 0 (this PR) before any Track E
  session starts; Track E consumes them read-only.
- `compliance-store` vs `attestation-database` (Track A) must be resolved before 107 or 114 move.
- 105 is externally triggered (`trigger: none`); it is folded into 104 only after A identifies the
  caller, and 104 itself must first port `staging/preprod`'s `testRetryCount` / `pytest-rerunfailures`.
- Track B deletions merge only after `validate-migration` no longer references the deleted templates
  (it fetches all branches; nothing on `main` should reference §5.2 templates).
- Only the tracking owner edits this file.

## 6. Blockers (Track A; results go in `docs/migration/blockers.md`)

| # | Question | Blocks |
|---|---|---|
| A1 | Owner of 101 `pricing-engine-ci` (inventory: unknown) | merging D past dev gate |
| A2 | What triggers 105 `risk-batch-legacy` externally | Wave 2 fold |
| A3 | Is `compliance-store` the same endpoint as `attestation-database` | 107, 114 (Track F) |
| A4 | Are the ACR binding on 108 and K8s binding on 109 dead | C — drop bindings vs port them |
| A5 | Owners of 110, 111, 115 | Track F scheduling decisions |

## 7. Disposition of existing draft PRs (#13–#20)

These were one-shot attempts made before the pilot pattern existed. They are inputs, not merge
candidates: each new playbook run reads the corresponding diff, then opens a fresh PR from `main`.

| PR | Pipeline | Why superseded |
|---|---|---|
| #20 | 101 | duplicate of this PR, no composite actions |
| #19 | 104 | edits shared `build-tools/scripts/notify_release_orchestrator.py` (collides with #16); no retry port |
| #18 | 106 | no shared actions; re-run via playbook |
| #17 | 103 | edits `.github/workflows/validate-migration.yml` (shared, edit-locked); 103 is a Wave 2 retire |
| #16 | 102 | edits `build-tools/scripts/notify_release_orchestrator.py` (collides with #19) |
| #15 | 105 | premature — 105 folds into 104 in Wave 2 |
| #14 | 108 | acceptable base; re-validate against this plan's ownership row and reopen |
| #13 | 109 | acceptable base; re-validate against this plan's ownership row and reopen |

The tracking owner closes each draft when the replacing PR merges.

## 8. Status (tracking owner only)

| Pipeline | Track | Status | PR |
|---|---|---|---|
| 101 pricing-engine-ci | D | migrated, 7/7 | this PR |
| 102 portfolio-api-ci | E | not started | |
| 103 portfolio-api-canary | Wave 2 retire | not started | |
| 104 risk-batch-ci | E | not started | |
| 105 risk-batch-legacy | Wave 2 fold | not started | |
| 106 frontend-workbench-ci | E | not started | |
| 107 regulatory-reporting | F | not started | |
| 108 market-sim-ci | C | migrated, 7/7 (ACR push not ported, A4 open) | #23 |
| 109 ops-control-plane-ci | C | migrated, 7/7 (K8s deploy not ported, A4 open) | #22 |
| 110–115 | F | not started | |
| 116–118 | B | not started | |
