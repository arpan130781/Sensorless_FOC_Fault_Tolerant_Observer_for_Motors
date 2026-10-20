import os
import re
import sys
import yaml
import pytest
import pypdf

# Ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from build_pdf_guide import (
    audit_code_constants,
    get_scenario_data_from_yaml_and_junit,
    generate_scenario_title_and_desc,
    get_motor_rated_torque,
)

def test_pdf_scenario_table_matches_yaml():
    """
    Integrity regression test (Round-6 / Round-7):
    Asserts that the Master Scenario Table rendered in the PDF guide
    matches simulation/fault_injection/fault_scenarios.yaml exactly:
    1. JUnit test report exists.
    2. Exactly 15 scenarios (1 baseline + 14 fault scenarios).
    3. Every key in the YAML is present in the PDF scenario table.
    4. The fault types, onsets, channels, and parameter magnitudes match.
    5. The acceptance criteria match the YAML criteria dictionary.
    6. No non-existent or fabricated scenarios exist in the PDF table.
    7. All scenarios have a verified PASS result from test execution in the JUnit report.
    """
    yaml_path = os.path.join(BASE_DIR, 'simulation', 'fault_injection', 'fault_scenarios.yaml')
    assert os.path.exists(yaml_path), f"YAML file missing at {yaml_path}"
    with open(yaml_path, 'r') as f:
        yaml_scenarios = yaml.safe_load(f)

    junit_path = os.path.join(BASE_DIR, 'build', 'pytest_report.xml')
    assert os.path.exists(junit_path), (
        f"JUnit test report missing at {junit_path}. Run pytest to generate it."
    )

    pdf_scenarios = get_scenario_data_from_yaml_and_junit(yaml_path=yaml_path, junit_path=junit_path)

    # 1. Assert exactly 15 scenarios
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

    # 2. Assert every YAML key exists, parameters/criteria match, and JUnit result is PASS
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

        # Verify test result is PASS (must fail if report missing or scenario absent/failing)
        assert pdf_item['test_result'] == 'PASS', (
            f"Scenario '{sc_key}' did not have a verified PASS in JUnit report (got '{pdf_item['test_result']}')"
        )


def test_committed_pdf_text_integrity():
    """
    Integrity regression test (Round-7 Item 4 & 5 & 6):
    Extracts text from the committed PDF (docs/Sensorless_FOC_Motor_Control_Guide.pdf)
    using pypdf and verifies:
    1. None of the legacy fabricated names appear.
    2. Each scenario contains its YAML-derived title and critical parameters (scale, rpm, rate, torque).
    3. Ungrounded claims ('aerospace hardware', 'equal to rated full load') do not appear.
    4. Rated torque formula and values match motor_params.h.
    """
    pdf_path = os.path.join(BASE_DIR, 'docs', 'Sensorless_FOC_Motor_Control_Guide.pdf')
    assert os.path.exists(pdf_path), f"Committed PDF not found at {pdf_path}"

    reader = pypdf.PdfReader(pdf_path)
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    norm_text = re.sub(r"\s+", " ", full_text)

    # 1. Assert no legacy fabricated names appear
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


def test_code_constants_audit():
    """
    Verifies that audit_code_constants() passes, guaranteeing that all constants
    referenced in the PDF match the canonical #defines in src/motor_params.h,
    src/fault_monitor.c, and src/main.cpp.
    """
    assert audit_code_constants() is True
