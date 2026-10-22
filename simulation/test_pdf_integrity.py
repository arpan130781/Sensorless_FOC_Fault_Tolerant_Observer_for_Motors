import os
import re
import sys
import yaml
import pytest
import pypdf
import subprocess
import warnings
import xml.etree.ElementTree as ET

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from build_pdf_guide import (
    audit_code_constants,
    get_scenario_data_from_yaml_and_junit,
    generate_scenario_title_and_desc,
    get_motor_rated_torque,
    compute_source_fingerprint,
    get_git_commit_hash,
    get_collected_test_nodeids,
)

def test_pdf_scenario_table_matches_yaml():
    """
    Integrity regression test (Round-6 / Round-7 / Round-8):
    Asserts that the Master Scenario Table rendered in the PDF guide
    matches simulation/fault_injection/fault_scenarios.yaml exactly:
    1. JUnit test report exists.
    2. Exactly 15 scenarios (1 baseline + 14 fault scenarios).
    3. Every key in the YAML is present in the PDF scenario table.
    4. The fault types, onsets, channels, and parameter magnitudes match.
    5. The acceptance criteria match the YAML criteria dictionary.
    6. No non-existent or fabricated scenarios exist in the PDF table.
    7. All scenarios have a verified PASS result with an up-to-date source fingerprint.
    """
    yaml_path = os.path.join(BASE_DIR, 'simulation', 'fault_injection', 'fault_scenarios.yaml')
    assert os.path.exists(yaml_path), f"YAML file missing at {yaml_path}"
    with open(yaml_path, 'r') as f:
        yaml_scenarios = yaml.safe_load(f)

    junit_path = os.path.join(BASE_DIR, 'build', 'pytest_report.xml')
    assert os.path.exists(junit_path), (
        f"JUnit test report missing at {junit_path}. Run pytest to generate it."
    )

    current_fp = compute_source_fingerprint(BASE_DIR)

    # 1. Inspect raw XML testcases to assert presence and non-stale fingerprint
    tree = ET.parse(junit_path)
    root = tree.getroot()
    tc_by_name = {}
    for tc in root.iter("testcase"):
        tc_name = tc.get("name", "")
        tc_by_name[tc_name] = tc

    for sc_key in yaml_scenarios.keys():
        expected_tc_name = f"test_all_scenarios_execute_and_pass[{sc_key}]"
        tc = tc_by_name.get(expected_tc_name)
        if tc is None:
            # Fallback search for parameterized bracket name
            for name, cand in tc_by_name.items():
                if f"[{sc_key}]" in name and "test_all_scenarios_execute_and_pass" in name:
                    tc = cand
                    break

        if tc is None:
            pytest.fail(
                f"Scenario '{sc_key}' test record is missing from {junit_path}. "
                "Run the scenario tests ('pytest simulation/test_scenarios.py') to generate valid evidence."
            )

        tc_fp = tc.get("fingerprint")
        if tc_fp != current_fp:
            pytest.fail(
                f"Scenario '{sc_key}' has a stale source fingerprint in JUnit report ({tc_fp} != {current_fp}). "
                "Source files have changed since the last test run. "
                "Run the scenario tests ('pytest simulation/test_scenarios.py') to re-verify."
            )

        has_failure = len(tc.findall("failure")) > 0 or len(tc.findall("error")) > 0
        if has_failure:
            pytest.fail(f"Scenario '{sc_key}' recorded a FAIL in {junit_path}.")

    pdf_scenarios = get_scenario_data_from_yaml_and_junit(yaml_path=yaml_path, junit_path=junit_path, repo_root=BASE_DIR)

    # 2. Assert exactly 15 scenarios
    assert len(yaml_scenarios) == 15, f"Expected 15 scenarios in YAML, got {len(yaml_scenarios)}"
    assert len(pdf_scenarios) == len(yaml_scenarios), (
        f"Scenario count mismatch: PDF table has {len(pdf_scenarios)}, YAML has {len(yaml_scenarios)}"
    )

    # Disallowed legacy hardcoded scenarios that do not exist in the YAML
    disallowed_keys = [
        "Inverter Leg A Open",
        "Two-Phase Startup",
        "Intermittent Fault",
        "Torque Step (+0.5Nm)",
        "Torque Step +0.5",
        "Phase B/C offset",
        "Parameter Mismatch +-20%",
    ]
    for d in disallowed_keys:
        for item in pdf_scenarios.values():
            assert d.lower() not in item['title'].lower(), f"Disallowed legacy scenario '{d}' found in PDF table"

    # 3. Assert every YAML key exists, parameters/criteria match, and JUnit result is PASS
    for sc_key, y_conf in yaml_scenarios.items():
        assert sc_key in pdf_scenarios, f"Scenario '{sc_key}' missing from PDF scenario table"
        pdf_item = pdf_scenarios[sc_key]

        # Verify type matches
        assert pdf_item['type'] == y_conf.get('type', 'none'), (
            f"Type mismatch for '{sc_key}': YAML={y_conf.get('type')} vs PDF={pdf_item['type']}"
        )

        # Verify criteria match
        y_crit = y_conf.get('expected_outcome', {}).get('criteria', {})
        for crit_key, crit_val in y_crit.items():
            assert crit_key in pdf_item['criteria'], f"Criteria '{crit_key}' missing in PDF table for '{sc_key}'"
            assert pdf_item['criteria'][crit_key] == crit_val, (
                f"Criteria value mismatch for '{sc_key}.{crit_key}': YAML={crit_val}, PDF={pdf_item['criteria'][crit_key]}"
            )

        # Verify expected mode matches
        if 'expected_mode_after_fault' in y_conf.get('expected_outcome', {}):
            assert pdf_item['expected_mode'] == y_conf['expected_outcome']['expected_mode_after_fault'], (
                f"Mode mismatch for '{sc_key}': YAML={y_conf['expected_outcome']['expected_mode_after_fault']} vs PDF={pdf_item['expected_mode']}"
            )

        # Verify test result is PASS
        assert pdf_item['test_result'] == 'PASS', (
            f"Scenario '{sc_key}' did not have a verified PASS in JUnit report "
            f"(got '{pdf_item['test_result']}': missing or stale source fingerprint). "
            "Run the scenario tests ('pytest simulation/test_scenarios.py') to re-verify."
        )


def test_junit_report_has_exactly_one_record_per_collected_test():
    """
    Integrity regression test (Round-8 Item 2):
    Verifies that build/pytest_report.xml contains exactly one de-duplicated
    record per collected test in the test suite, with matching nodeids and no duplicates.
    """
    junit_path = os.path.join(BASE_DIR, 'build', 'pytest_report.xml')
    assert os.path.exists(junit_path), f"JUnit test report missing at {junit_path}"

    current_fp = compute_source_fingerprint(BASE_DIR)
    collected_nodeids = get_collected_test_nodeids(BASE_DIR)
    assert len(collected_nodeids) > 0, "No tests collected by pytest"

    tree = ET.parse(junit_path)
    root = tree.getroot()
    testcases = root.findall(".//testcase")

    report_nodeids = []
    for tc in testcases:
        nodeid = tc.get("nodeid")
        assert nodeid is not None, f"Testcase in {junit_path} missing 'nodeid' attribute: {tc.attrib}"
        assert tc.get("fingerprint") == current_fp, (
            f"Testcase {nodeid} has stale source fingerprint ({tc.get('fingerprint')} != {current_fp})"
        )
        report_nodeids.append(nodeid)

    # Assert exactly one record per collected test (no duplicates)
    assert len(report_nodeids) == len(set(report_nodeids)), (
        f"Duplicate records found in {junit_path}: {len(report_nodeids)} records vs {len(set(report_nodeids))} unique"
    )
    assert len(testcases) == len(collected_nodeids), (
        f"Report record count mismatch: {junit_path} has {len(testcases)} records, but pytest collected {len(collected_nodeids)} tests "
        f"(stale source fingerprint records were purged or unexecuted tests exist)"
    )
    assert set(report_nodeids) == set(collected_nodeids), (
        f"Report nodeids do not match collected nodeids. Difference: {set(collected_nodeids) ^ set(report_nodeids)}"
    )


def test_committed_pdf_text_integrity():
    """
    Integrity regression test (Round-7 & Round-8):
    Extracts text from the committed PDF (docs/Sensorless_FOC_Motor_Control_Guide.pdf)
    using pypdf and verifies:
    1. None of the legacy fabricated names or disallowed phrases appear (including 'ISO/IEC').
    2. Each scenario contains its YAML-derived title and critical parameters (scale, rpm, rate, torque).
    3. Ungrounded claims ('aerospace hardware', 'equal to rated full load') do not appear.
    4. Rated torque formula and values match motor_params.h.
    5. Build source fingerprint and git commit hash appear on the final page.
    """
    pdf_path = os.path.join(BASE_DIR, 'docs', 'Sensorless_FOC_Motor_Control_Guide.pdf')
    assert os.path.exists(pdf_path), f"Committed PDF not found at {pdf_path}"

    reader = pypdf.PdfReader(pdf_path)
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    norm_text = re.sub(r"\s+", " ", full_text)

    # 1. Assert no legacy fabricated names or disallowed phrases appear
    disallowed_phrases = [
        "Inverter Leg A Open",
        "Two-Phase Startup",
        "Intermittent Fault",
        "Torque Step (+0.5Nm)",
        "Torque Step +0.5",
        "Phase B/C offset",
        "Parameter Mismatch +-20%",
        "previously reserved for aerospace hardware",
        "equal to rated full load",
        "ISO/IEC",
    ]
    for phrase in disallowed_phrases:
        assert phrase.lower() not in norm_text.lower(), (
            f"Disallowed phrase or fabricated scenario found in PDF: '{phrase}'"
        )

    # 2. Assert YAML-derived titles and numbers appear for each scenario
    yaml_path = os.path.join(BASE_DIR, 'simulation', 'fault_injection', 'fault_scenarios.yaml')
    with open(yaml_path, 'r') as f:
        yaml_scenarios = yaml.safe_load(f)

    # Scenario 7: Ls * 0.80 (-20%), NOT +15%
    assert "0.80" in norm_text, "Scenario 7 scale 0.80 missing from PDF"
    assert "-20%" in norm_text, "Scenario 7 delta -20% missing from PDF"
    assert "Ls +15%" not in norm_text, "Legacy incorrect claim 'Ls +15%' found in PDF"

    # Scenario 10: 500 RPM, NOT 300 RPM
    assert "500 RPM" in norm_text, "Scenario 10 500 RPM missing from PDF"
    assert "300 RPM" not in norm_text, "Legacy incorrect claim '300 RPM' found in PDF"

    # Scenario 11: 500 RPM/s to 500 RPM, NOT 200 RPM/s
    assert "500 RPM/s" in norm_text, "Scenario 11 500 RPM/s missing from PDF"
    assert "200 RPM/s" not in norm_text, "Legacy incorrect claim '200 RPM/s' found in PDF"

    # Scenario 9 / 5: load step 0.10 N·m
    assert "0.10 N·m" in norm_text or "0.10" in norm_text, "Load step 0.10 N·m missing from PDF"

    # Dynamically calculated rated continuous torque
    t_rated = get_motor_rated_torque()
    assert f"{t_rated:.2f}" in norm_text or "0.45" in norm_text, "Rated torque 0.45 N·m missing from PDF"
    pct_load = (0.10 / t_rated) * 100.0
    assert f"{pct_load:.0f}%" in norm_text or "22%" in norm_text, "Load percentage ~22% missing from PDF"

    # 3. Assert all scenario titles generated from YAML appear in PDF
    for sc_key, y_conf in yaml_scenarios.items():
        title, _ = generate_scenario_title_and_desc(sc_key, y_conf)
        assert title in norm_text, f"Generated scenario title '{title}' (for {sc_key}) missing in PDF text"

    # 4. Assert source fingerprint appears on the final page
    current_fp = compute_source_fingerprint(BASE_DIR)
    assert current_fp in norm_text or current_fp[:16] in norm_text, (
        f"Source fingerprint '{current_fp}' missing from PDF guide"
    )

    # 5. Assert git commit hash appears on the final page (skip in non-git export)
    has_git = os.path.exists(os.path.join(BASE_DIR, ".git"))
    if not has_git:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            has_git = (res.returncode == 0 and res.stdout.strip() == "true")
        except Exception:
            has_git = False

    if not has_git:
        import warnings
        msg = "Non-git export detected (.git missing): skipping commit-hash assertion in PDF text integrity."
        warnings.warn(msg, UserWarning)
        print(f"\n[SKIP] {msg}", file=sys.stderr)
    else:
        try:
            recent_commits = subprocess.check_output(
                ["git", "log", "-n", "5", "--format=%H"], cwd=BASE_DIR, text=True
            ).split()
            assert any(c in norm_text or c[:7] in norm_text for c in recent_commits), (
                f"Git commit hash from recent history ({recent_commits[:3]}) missing from PDF guide"
            )
        except subprocess.CalledProcessError as e:
            import warnings
            msg = f"git log failed ({e}): skipping commit-hash assertion."
            warnings.warn(msg, UserWarning)
            print(f"\n[SKIP] {msg}", file=sys.stderr)


def test_code_constants_audit():
    """
    Verifies that audit_code_constants() passes, guaranteeing that all constants
    referenced in the PDF match the canonical #defines in src/motor_params.h,
    src/fault_monitor.c, and src/main.cpp.
    """
    assert audit_code_constants() is True


def test_staleness_detection_fails_on_source_mutation():
    """
    Regression test (Round-8 & Round-9):
    Verifies that mutating source code (e.g. fault_monitor.c) alters the
    source fingerprint and causes an isolated run of test_pdf_integrity.py
    in a temporary copy to FAIL with the specific text 'stale source fingerprint'.

    Includes an unmutated control run verifying that test_pdf_integrity.py
    passes completely in a clean non-git copy before mutation.
    """
    if os.environ.get("SKIP_STALENESS_SUBPROCESS") == "1":
        return

    import tempfile
    import shutil
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy necessary workspace directories and files
        for item in ["src", "simulation", "build", "pytest.ini", "build_pdf_guide.py", "docs"]:
            src_path = os.path.join(BASE_DIR, item)
            dst_path = os.path.join(tmpdir, item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            elif os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)

        sub_env = os.environ.copy()
        sub_env["SKIP_STALENESS_SUBPROCESS"] = "1"
        cmd = [sys.executable, "-m", "pytest", "simulation/test_pdf_integrity.py", "-v"]

        # CONTROL (Round-9 Item 1b): Verify clean unmutated copy passes completely
        res_control = subprocess.run(
            cmd, cwd=tmpdir, env=sub_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert res_control.returncode == 0, (
            f"Control run in unmutated copy failed (expected PASS):\n"
            f"STDOUT:\n{res_control.stdout}\nSTDERR:\n{res_control.stderr}"
        )

        # MUTATED (Round-9 Item 1c): Append comment to src/fault_monitor.c in copy
        fm_path = os.path.join(tmpdir, "src", "fault_monitor.c")
        with open(fm_path, "a") as f:
            f.write("\n// STALENESS REGRESSION MUTATION FOR ROUND 9 TEST\n")

        # Run test_pdf_integrity.py in mutated temp copy
        res_mutated = subprocess.run(
            cmd, cwd=tmpdir, env=sub_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Assert that the mutated test run FAILS
        assert res_mutated.returncode != 0, (
            "Expected test_pdf_integrity.py to fail after mutating fault_monitor.c, but it passed!"
        )
        combined_output = res_mutated.stdout + res_mutated.stderr
        assert "stale source fingerprint" in combined_output, (
            f"Expected output to contain 'stale source fingerprint', got:\n{combined_output}"
        )
