#!/usr/bin/env python3
"""
Normalize test results from different frameworks into a common format.

Accepts JUnit XML, pytest JSON, or Jest JSON output and converts
to a unified schema for cross-service test reporting.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


TRX_NAMESPACE = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"


def parse_junit_xml(filepath: str) -> dict:
    """Parse JUnit XML test results."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    suites = root.findall(".//testsuite")
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    for suite in suites:
        total_tests += int(suite.get("tests", 0))
        total_failures += int(suite.get("failures", 0))
        total_errors += int(suite.get("errors", 0))
        total_skipped += int(suite.get("skipped", 0))

    return {
        "total": total_tests,
        "passed": total_tests - total_failures - total_errors - total_skipped,
        "failed": total_failures + total_errors,
        "skipped": total_skipped,
    }


def parse_trx(filepath: str) -> dict:
    """Parse TRX test results from the Visual Studio test schema."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    counters = root.find(f".//{{{TRX_NAMESPACE}}}Counters")
    if counters is None:
        raise ValueError("TRX file does not contain a Counters element")

    total = int(counters.get("total", 0))
    failed = sum(
        int(counters.get(attribute, 0))
        for attribute in ("failed", "error", "timeout", "aborted")
    )
    skipped = sum(
        int(counters.get(attribute, 0))
        for attribute in ("notExecuted", "inconclusive")
    )

    return {
        "total": total,
        "passed": int(counters.get("passed", 0)),
        "failed": failed,
        "skipped": skipped,
    }


def normalize_results(input_dir: str, output_path: str):
    """Scan input directory and normalize all test result files."""
    results = []
    input_path = Path(input_dir)

    for f in input_path.rglob("*.xml"):
        try:
            parsed = parse_junit_xml(str(f))
            parsed["source"] = str(f.name)
            parsed["format"] = "junit-xml"
            results.append(parsed)
        except Exception as e:
            print(f"WARNING: Could not parse {f}: {e}")

    for f in input_path.rglob("*.trx"):
        try:
            parsed = parse_trx(str(f))
            parsed["source"] = str(f.name)
            parsed["format"] = "trx"
            results.append(parsed)
        except Exception as e:
            print(f"WARNING: Could not parse {f}: {e}")

    summary = {
        "total_suites": len(results),
        "total_tests": sum(r["total"] for r in results),
        "total_passed": sum(r["passed"] for r in results),
        "total_failed": sum(r["failed"] for r in results),
        "total_skipped": sum(r["skipped"] for r in results),
        "suites": results,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Normalized {len(results)} test result files")
    print(f"  Total tests: {summary['total_tests']}")
    print(f"  Passed: {summary['total_passed']}")
    print(f"  Failed: {summary['total_failed']}")
    print(f"  Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Normalize test results")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()
    normalize_results(args.input_dir, args.output)


if __name__ == "__main__":
    main()
