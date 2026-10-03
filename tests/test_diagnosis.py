from reconcile_skill.diagnosis import diagnose_missing_patterns


def test_diagnosis_separates_fact_and_hypothesis():
    diagnostics = diagnose_missing_patterns(
        [
            {"reconciliation_key": "a1", "status": "CANCELLED", "region": "East"},
            {"reconciliation_key": "a2", "status": "CANCELLED", "region": "West"},
            {"reconciliation_key": "a3", "status": "CANCELLED", "region": "East"},
        ]
    )
    status = next(item for item in diagnostics if item["column"] == "status")
    assert status["fact"] == "3 of 3 missing records have status=CANCELLED."
    assert "may" in status["hypothesis"]
    assert "Hypothesis only" in status["note"]
