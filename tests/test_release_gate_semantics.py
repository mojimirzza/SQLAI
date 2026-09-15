from pathlib import Path


def test_full_verification_is_strict_about_blocked_checks():
    source = Path("scripts/run_full_verification.py").read_text(encoding="utf-8")
    assert "blocked = \"blocked=0\" not in line" in source
    assert "FULL VERIFICATION: FAIL" in source


def test_release_gate_returns_nonzero_when_blocked():
    source = Path("scripts/run_release_gate.py").read_text(encoding="utf-8")
    assert "if blocked:" in source
    assert "return 2" in source
