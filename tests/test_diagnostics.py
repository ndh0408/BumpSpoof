"""Doctor / self-check — runs without network, never raises."""

from core import diagnostics as dg


def test_runs_without_network():
    checks = dg.run_diagnostics(check_network=False)
    names = [c.name for c in checks]
    assert "Python" in names
    assert any("pymobiledevice3" in n for n in names)
    for c in checks:
        assert c.status in (dg.PASS, dg.WARN, dg.FAIL)


def test_python_check_reflects_version():
    checks = dg.run_diagnostics(check_network=False)
    py = next(c for c in checks if c.name == "Python")
    import sys
    if sys.version_info[:2] >= (3, 13):
        assert py.status == dg.PASS
    elif sys.version_info[:2] == (3, 12):
        assert py.status == dg.WARN


def test_summary_and_report_render():
    checks = dg.run_diagnostics(check_network=False)
    assert isinstance(dg.summary(checks), str)
    report = dg.format_report(checks)
    assert "Python" in report


def test_appdir_check_present():
    checks = dg.run_diagnostics(check_network=False)
    assert any(c.name == "Thư mục dữ liệu" for c in checks)


def test_main_returns_exit_code():
    # network off path is exercised via run_diagnostics; main() may probe network
    # but must still return an int and not raise.
    rc = dg.main([])
    assert rc in (0, 1)
