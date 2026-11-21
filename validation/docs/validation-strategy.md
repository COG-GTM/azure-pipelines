# Migration Validation Strategy

## Overview

When migrating pipelines from ADO to GitHub Actions, each service must pass
validation checks that confirm the migrated workflow produces equivalent results.

## Validation Layers

### 1. Artifact Comparison

Compare build output artifacts:
- File count within 20% tolerance
- Expected file types present
- Artifact size within expected range

Tool: `validation/scripts/compare_artifacts.py`

### 2. Test Count Comparison

Compare test execution results:
- Total test count within 5% tolerance
- Pass rate meets minimum threshold
- No new test failures introduced

Tool: `validation/scripts/compare_test_counts.py`

### 3. Deployment Verification

After migration, verify:
- Deployment targets are identical
- Environment variables match
- Release-orchestrator receives notifications
- Compliance attestations are generated

### 4. Non-Build Workload Review

Pipelines classified as non-build workloads require separate review:
- Determine if they should migrate at all
- Consider alternative compute platforms
- Validate schedule equivalence if migrated

## Baseline Management

Baselines are stored in `validation/baselines/<service>/`.

Each service should have:
- `expected-artifacts.json` — artifact expectations
- `test-counts.json` — test execution expectations

## Running Validation

The scripts need Python 3.9 or newer (`python3` on Ubuntu); `validate_migration.py` needs 3.10 or newer and exits on 3.9.
`validate_migration.py` also needs PyYAML: `sudo apt-get install python3-yaml`, or `pip install pyyaml`
inside a virtual environment (Ubuntu 24.04 refuses a system-wide `pip install`; `python3 -m venv` needs
`sudo apt-get install python3-venv`). The other scripts use only the standard library.

Pipelines that pin templates on other branches (such as risk-batch on `staging/preprod`) need those
branches fetched first, as the validate-migration workflow does:
`git fetch --no-tags origin '+refs/heads/*:refs/remotes/origin/*'`. Without them the validator reads the
checkout's copy of the template.

```bash
# Full migration scorecard for one service (what the validate-migration workflow runs;
# needs a migrated workflow, which main does not have yet). Replace <service> with the
# service the branch migrates, such as pricing-engine or market-sim. For risk-batch-legacy.yml use
# --ado-pipeline services/risk-batch/azure-pipelines-legacy.yml.
python3 validation/scripts/validate_migration.py \
  --service <service> \
  --ado-pipeline services/<service>/azure-pipelines.yml \
  --gha-workflow .github/workflows/<service>-ci.yml \
  --baselines validation/baselines --repo-root .

# Compare artifacts for a single service
python3 validation/scripts/compare_artifacts.py \
  --baseline validation/baselines/pricing-engine/expected-artifacts.json \
  --artifacts /path/to/gha/artifacts

# Compare test counts
python3 validation/scripts/compare_test_counts.py \
  --baseline validation/baselines/pricing-engine/test-counts.json \
  --actual /path/to/gha/test-results.json

# Generate summary report
python3 validation/scripts/summarize_build_results.py \
  --baselines validation/baselines/
```
