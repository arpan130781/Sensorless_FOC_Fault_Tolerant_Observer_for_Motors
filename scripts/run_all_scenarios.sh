#!/bin/bash
make lib
scenarios=$(grep '^[a-zA-Z0-9_]*:' simulation/fault_injection/fault_scenarios.yaml | tr -d ':')

FAILED=0
echo "Running standard scenarios..."
for sc in $scenarios; do
    echo "---------------------------------------------------------"
    echo "Running $sc..."
    if ! ${PYTHON:-.venv/bin/python3} simulation/harness/sil_runner.py --scenario "$sc" --no-plot; then
        echo "Scenario $sc FAILED!"
        FAILED=$((FAILED + 1))
    fi
done

echo "---------------------------------------------------------"
echo "Running sensor-fault robustness sweep (target: >=90% acceptable outcomes per group)..."
if ! ${PYTHON:-.venv/bin/python3} scripts/isolation_sweep.py --phases 4; then
    echo "Sweep did not meet the target."
    FAILED=$((FAILED + 1))
fi

if [ $FAILED -gt 0 ]; then
    echo "$FAILED scenarios/tests failed."
    exit 1
fi
echo "All scenarios pass!"
