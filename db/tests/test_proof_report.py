"""Prevent green proofs from hiding skipped or missing database integration."""

import xml.etree.ElementTree as ET

import pytest

from db.scripts.check_proof_report import REQUIRED, verify_report


def report(tmp_path, proof="operations"):
    suite = ET.Element("testsuite")
    for module, count in REQUIRED[proof].items():
        for index in range(count):
            ET.SubElement(
                suite, "testcase", classname=f"api.tests.{module}", name=f"case_{index}"
            )
    return suite, tmp_path / "report.xml"


@pytest.mark.parametrize("proof,total", [("operations", 60), ("governance", 12)])
def test_successful_integration_groups_are_required(tmp_path, proof, total):
    suite, path = report(tmp_path, proof)
    ET.ElementTree(suite).write(path)
    assert verify_report(path, proof) == (total, total)


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_any_unsuccessful_case_rejects_the_proof(tmp_path, outcome):
    suite, path = report(tmp_path)
    ET.SubElement(suite[0], outcome)
    ET.ElementTree(suite).write(path)
    with pytest.raises(ValueError):
        verify_report(path, "operations")


def test_unit_successes_cannot_replace_missing_integration(tmp_path):
    suite, path = report(tmp_path)
    suite.remove(suite[0])
    for index in range(100):
        ET.SubElement(
            suite, "testcase", classname="api.tests.test_mock", name=f"mock_{index}"
        )
    ET.ElementTree(suite).write(path)
    with pytest.raises(ValueError):
        verify_report(path, "operations")


def test_duplicate_cases_cannot_fill_the_required_count(tmp_path):
    suite, path = report(tmp_path)
    suite[1].attrib.update(suite[0].attrib)
    ET.ElementTree(suite).write(path)
    with pytest.raises(ValueError):
        verify_report(path, "operations")
