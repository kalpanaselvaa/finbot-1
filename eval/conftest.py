import pytest


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed
    if total == 0:
        return
    pct = passed / total * 100
    terminalreporter.write_sep(
        "=",
        f"FinBot Eval: {passed}/{total} passed ({pct:.0f}%)",
        green=pct == 100,
        yellow=0 < pct < 100,
        red=pct == 0,
    )
