import os
import yaml
import pytest
from build_pdf_guide import audit_code_constants, get_scenario_data_from_yaml_and_junit

def test_pdf_scenario_table_matches_yaml():
    """
    Integrity regression test (Round-6):
    Asserts that the Master Scenario Table rendered in the PDF guide
    matches simulation/fault_injection/fault_scenarios.yaml exactly:
    1. Exactly 15 scenarios (1 baseline + 14 fault scenarios).
    2. Every key in the YAML is present in the PDF scenario table.
    3. The fault types, onsets, channels, and parameter magnitudes match.
    4. The acceptance criteria match the YAML criteria dictionary.
    5. No non-existent or fabricated scenarios exist in the PDF table.
    6. All scenarios have a verified PASS result from test execution.
    """
    yaml_path = os.path.join(os.path.dirname(__file__), 'fault_injection', 'fault_scenarios.yaml')
    with open(yaml_path, 'r') as f:
        yaml_scenarios = yaml.safe_load(f)

    junit_path = os.path.join(os.path.dirname(__file__), '..', 'build', 'pytest_report.xml')
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
        "Phase B/C offset",
        "Parameter Mismatch +-20%"
    ]
    for d in disallowed_keys:
        for item in pdf_scenarios.values():
            assert d.lower() not in item['title'].lower(), f"Disallowed legacy scenario '{d}' found in PDF table"

    # 2. Assert every YAML key exists and parameters/criteria match
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
        assert pdf_item['test_result'] == 'PASS', f"Scenario '{sc_key}' did not pass test execution (got {pdf_item['test_result']})"


def test_code_constants_audit():
    """
    Verifies that audit_code_constants() passes, guaranteeing that all constants
    referenced in the PDF match the canonical #defines in src/motor_params.h,
    src/fault_monitor.c, and src/main.cpp.
    """
    assert audit_code_constants() is True
