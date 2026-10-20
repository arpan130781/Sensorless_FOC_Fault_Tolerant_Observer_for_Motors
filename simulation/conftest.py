"""
pytest configuration and hooks for sensorless-foc-pio simulation test suite.
Ensures cumulative test reporting in build/pytest_report.xml so running subsets of tests
does not overwrite or wipe out verified scenario evidence from prior runs,
and ensures test_pdf_integrity.py runs after scenario tests have executed and recorded evidence.
"""
import os
import xml.etree.ElementTree as ET
import pytest

_SESSION_CASES = {}

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
    for tc in _SESSION_CASES.values():
        suite.append(tc)
    tree = ET.ElementTree(root)
    tree.write(report_path, encoding="utf-8", xml_declaration=True)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    root_dir = str(session.config.rootpath)
    report_path = os.path.join(root_dir, "build", "pytest_report.xml")
    if os.path.exists(report_path):
        try:
            tree = ET.parse(report_path)
            for tc in tree.findall(".//testcase"):
                key = (tc.get("classname", ""), tc.get("name", ""))
                _SESSION_CASES[key] = tc
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
        parts = report.nodeid.split("::")
        fname = parts[0].replace("/", ".").replace(".py", "")
        test_name = parts[-1]
        classname = ".".join(parts[:-1]) if len(parts) > 1 else fname

        tc = ET.Element("testcase", classname=classname, name=test_name, time=f"{report.duration:.3f}")
        if report.failed:
            ET.SubElement(tc, "failure", message=str(report.longrepr or "Test failed"))
        elif report.skipped:
            ET.SubElement(tc, "skipped")
        _SESSION_CASES[(classname, test_name)] = tc


def pytest_runtest_setup(item):
    if "test_pdf_integrity.py" in item.nodeid:
        root_dir = str(item.session.config.rootpath)
        _write_xml_report(root_dir)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    root_dir = str(session.config.rootpath)
    _write_xml_report(root_dir)
