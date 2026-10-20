"""
pytest configuration and hooks for sensorless-foc-pio simulation test suite.
Ensures cumulative test reporting in build/pytest_report.xml with source fingerprinting
and de-duplication keyed strictly by full test nodeid.
"""
import os
import sys
import xml.etree.ElementTree as ET
import pytest

# Ensure repo root is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from build_pdf_guide import compute_source_fingerprint, normalise_testcase_nodeid, get_nodeid_from_testcase

_SESSION_CASES = {}
_CURRENT_FINGERPRINT = None


def _write_xml_report(root_dir):
    os.makedirs(os.path.join(root_dir, "build"), exist_ok=True)
    report_path = os.path.join(root_dir, "build", "pytest_report.xml")
    root = ET.Element("testsuites", name="pytest tests")
    suite = ET.SubElement(
        root,
        "testsuite",
        name="pytest",
        errors="0",
        failures=str(sum(1 for tc in _SESSION_CASES.values() if tc.find("failure") is not None)),
        skipped=str(sum(1 for tc in _SESSION_CASES.values() if tc.find("skipped") is not None)),
        tests=str(len(_SESSION_CASES)),
    )
    for nodeid in sorted(_SESSION_CASES.keys()):
        suite.append(_SESSION_CASES[nodeid])
    tree = ET.ElementTree(root)
    tree.write(report_path, encoding="utf-8", xml_declaration=True)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    global _CURRENT_FINGERPRINT
    root_dir = str(session.config.rootpath)
    _CURRENT_FINGERPRINT = compute_source_fingerprint(root_dir)
    report_path = os.path.join(root_dir, "build", "pytest_report.xml")
    if os.path.exists(report_path):
        try:
            tree = ET.parse(report_path)
            for tc in tree.findall(".//testcase"):
                nodeid = get_nodeid_from_testcase(tc)
                classname, name = normalise_testcase_nodeid(nodeid)
                tc.set("nodeid", nodeid)
                tc.set("classname", classname)
                tc.set("name", name)
                fp = tc.get("fingerprint")

                # Drop merged records whose fingerprint differs from the current one
                if fp == _CURRENT_FINGERPRINT:
                    _SESSION_CASES[nodeid] = tc
                else:
                    # Dropped because fingerprint is stale or missing!
                    pass
        except Exception:
            pass


def pytest_collection_modifyitems(session, config, items):
    # Ensure test_pdf_integrity.py runs after scenario tests have executed
    pdf_items = [it for it in items if "test_pdf_integrity.py" in it.nodeid]
    other_items = [it for it in items if "test_pdf_integrity.py" not in it.nodeid]
    items[:] = other_items + pdf_items


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
    if report.when == "call":
        nodeid = report.nodeid
        classname, name = normalise_testcase_nodeid(nodeid)

        tc = ET.Element(
            "testcase",
            classname=classname,
            name=name,
            nodeid=nodeid,
            time=f"{report.duration:.3f}",
            fingerprint=_CURRENT_FINGERPRINT,
        )
        if report.failed:
            ET.SubElement(tc, "failure", message=str(report.longrepr or "Test failed"))
        elif report.skipped:
            ET.SubElement(tc, "skipped")
        _SESSION_CASES[nodeid] = tc


def pytest_runtest_setup(item):
    if "test_pdf_integrity.py" in item.nodeid:
        root_dir = str(item.session.config.rootpath)
        _write_xml_report(root_dir)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    root_dir = str(session.config.rootpath)
    _write_xml_report(root_dir)
