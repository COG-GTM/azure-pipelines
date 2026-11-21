# Shared CI Platform — Enterprise Pipeline Repository

This repository contains the shared CI/CD platform configuration for the organization.
It includes build templates, release workflows, helper scripts, and service pipeline
definitions used across all engineering teams.

> **Note**: This repository has evolved organically over several years and contains
> significant technical debt including template drift, duplicate logic, and non-build
> workloads running on CI infrastructure.

## Repository Structure

```
templates/          Central shared build, test, and release templates
alt-templates/      Team-maintained alternative templates
build-tools/        Shared helper scripts and YAML fragments
services/           Per-service CI pipeline definitions
night-jobs/         Scheduled operational workloads
adhoc/              One-off operational pipelines
deprecated/         Old pipelines kept for reference
archive/            Archived configurations
validation/         Migration validation baselines and scripts
docs/               Platform documentation
upstream-reference/ Original upstream examples (preserved for reference)
```

## Template Architecture

Templates are organized into several areas:

- **Central templates** (`templates/build/`, `templates/test/`, `templates/release/`) — canonical shared templates maintained by the shared-ci-platform team
- **Language setup** (`templates/language/`) — language-specific environment setup
- **Legacy templates** (`templates/legacy/`) — older template versions still in use
- **Alternative templates** (`alt-templates/`) — team-maintained forks for specialized needs
- **Build tool helpers** (`build-tools/yaml/`) — shared YAML fragments

## Branch Model

Templates are consumed via branch references. Multiple long-lived branches exist
with divergent template logic:

| Branch | Purpose |
|--------|---------|
| `main` | Canonical shared templates |
| `master` | Legacy default branch (pre-rename) |
| `staging/preprod` | Staging environment modifications |
| `staging/release-hardening` | Release workflow hardening |
| `team/frontend-custom` | Frontend team customizations |
| `team/quant-experiments` | Quant team experimental changes |
| `team/reporting-hotfix` | Compliance workflow patches |
| `legacy/master-support` | Frozen compatibility branch |

See [docs/branch-usage-notes.md](docs/branch-usage-notes.md) for details.

## Services

| Service | Stack | Template Source |
|---------|-------|-----------------|
| pricing-engine | .NET | central templates |
| portfolio-api | Java/Maven | central templates (master) |
| risk-batch | Python | central templates (staging/preprod) |
| market-sim | Rust | custom (inline) |
| ops-control-plane | Go | custom (inline) |
| frontend-workbench | Node/React | alt-templates (team/frontend-custom) |
| regulatory-reporting | Python | hybrid (team-overrides + central) |
| notebook-executor | Python | none (non-build workload) |
| scenario-runner | Python | none (non-build workload) |

## Quickstart

There is no top-level build. Each runnable scaffold under `services/` builds on its own;
the other pipelines are ADO YAML only. Checked on a clean Ubuntu 24.04 machine.

| Tool | Version | Used by |
|------|---------|---------|
| .NET SDK | 8.0 | pricing-engine |
| JDK + Maven | JDK 17 or newer (`JAVA_HOME` must point at a full JDK), Maven 3.8+ | portfolio-api |
| Python | 3.10+ (`python3`; Ubuntu has no `python` command), PyYAML for `validate_migration.py` (`sudo apt-get install python3-yaml`, or `pip install pyyaml` in a venv) | risk-batch, validation scripts |
| Rust/Cargo | 1.78 or newer (the lockfile is version 4; Ubuntu 24.04's apt `cargo` 1.75 fails, install with [rustup](https://rustup.rs)), plus a C linker (`sudo apt-get install build-essential`) | market-sim |
| Go | 1.22+ | ops-control-plane |
| Node.js + npm | Node 18.1+ or 20 (`npm test` fails on 18.0, which lacks `--test`, and on Node 22+); Ubuntu's apt `nodejs` has no `npm`, so also `sudo apt-get install npm` or use nvm | frontend-workbench |

| Service | Command (from `services/<name>/`) |
|---------|-----------------------------------|
| pricing-engine | `dotnet test PricingEngine.sln`, then `dotnet run --project src/PricingEngine` (http://localhost:5000/api/pricing/health) |
| portfolio-api | `mvn -B -DskipTests=false package` |
| risk-batch | `python3 -m unittest discover -s tests -p "test_*.py" -v` |
| market-sim | `cargo run --release` |
| ops-control-plane | `go run ./cmd/server` (port `PORT`, default 8080; check `/healthz`) |
| frontend-workbench | `npm ci && npm run lint && npm test` (CI's `--ci --coverage` flags are ignored; no coverage report is produced) |

To run the migration validator locally against a migrated workflow (from the repo root; `main` has no
`*-ci.yml` workflows yet, so run it on a migration branch that adds one). Replace `<service>` with the
service that branch migrates, such as `pricing-engine` or `market-sim`. The legacy risk-batch workflow
is the exception: `.github/workflows/risk-batch-legacy.yml` is checked against
`services/risk-batch/azure-pipelines-legacy.yml`.

```bash
sudo apt-get install python3-yaml   # Ubuntu 24.04 blocks a system-wide `pip install`
# or: sudo apt-get install python3-venv && python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml
# Pipelines pin templates on other branches (e.g. risk-batch on staging/preprod); fetch them as CI does,
# or the validator reads the checkout's copy instead.
git fetch --no-tags origin '+refs/heads/*:refs/remotes/origin/*'
python3 validation/scripts/validate_migration.py \
  --service <service> \
  --ado-pipeline services/<service>/azure-pipelines.yml \
  --gha-workflow .github/workflows/<service>-ci.yml \
  --baselines validation/baselines --repo-root .
```

Artifact baselines exist for pricing-engine, portfolio-api and risk-batch; only pricing-engine has a
test-count baseline. So portfolio-api and risk-batch fail the Test Baseline check, and other services
fail both baseline checks (market-sim scores 5/7).

## Documentation

- [Migration Context](docs/migration-context.md) — background on CI platform evolution
- [Branch Usage Notes](docs/branch-usage-notes.md) — branch inventory and ownership
- [Ownership Gaps](docs/ownership-gaps.md) — services with unclear ownership
- [Demo Scenarios](docs/demo-scenarios.md) — CI migration analysis scenarios
- [Validation Strategy](validation/docs/validation-strategy.md) — migration validation approach
- [Pipeline Inventory Report](docs/pipeline-inventory-report.md) — classification of all 18 pipelines for the ADO → GitHub Actions migration

## Migration Validation

Every PR that adds or changes a file under `.github/workflows/` runs the
`validate-migration` workflow, which lints the workflow with `actionlint`,
compares it against the source ADO pipeline (`validation/scripts/validate_migration.py`),
and posts a scorecard comment on the PR. `services/pricing-engine/` contains a
runnable .NET 8 scaffold so a migrated `pricing-engine-ci` workflow produces a real
build, test run and artifacts.

## Integration Points

- **Artifactory** — central artifact tracking system
- **D2** — deployment tracking and coordination
- **attestation-database** — regulatory compliance metadata and attestations
