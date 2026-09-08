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
| pricing-engine | .NET | central templates → migrated to GHA (`.github/workflows/pricing-engine-ci.yml`) |
| portfolio-api | Java/Maven | central templates (master) |
| risk-batch | Python | central templates (staging/preprod) |
| market-sim | Rust | custom (inline) |
| ops-control-plane | Go | custom (inline) |
| frontend-workbench | Node/React | alt-templates (team/frontend-custom) |
| regulatory-reporting | Python | hybrid (team-overrides + central) |
| notebook-executor | Python | none (non-build workload) |
| scenario-runner | Python | none (non-build workload) |

## Documentation

- [Migration Context](docs/migration-context.md) — background on CI platform evolution
- [Branch Usage Notes](docs/branch-usage-notes.md) — branch inventory and ownership
- [Ownership Gaps](docs/ownership-gaps.md) — services with unclear ownership
- [Demo Scenarios](docs/demo-scenarios.md) — CI migration analysis scenarios
- [Validation Strategy](validation/docs/validation-strategy.md) — migration validation approach
- [Pipeline Inventory Report](docs/pipeline-inventory-report.md) — classification of all 18 pipelines for the ADO → GitHub Actions migration
- [Pricing Engine CI Migration](docs/migration/pricing-engine-ci.md) — pricing-engine ADO-to-GHA mapping and validation

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
