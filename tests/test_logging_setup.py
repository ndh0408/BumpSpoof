"""Logging: secret redaction and safe, idempotent setup."""


from core import logging_setup as ls


def test_redact_udid():
    assert "DEADBEEF-1122334455667788" not in ls.redact(
        "connecting to DEADBEEF-1122334455667788 now")


def test_redact_uuid():
    out = ls.redact("pair 12345678-1234-1234-1234-123456789abc done")
    assert "123456789abc" not in out


def test_redact_long_hex():
    assert "deadbeefdeadbeefdead" not in ls.redact("psk=deadbeefdeadbeefdead")


def test_redact_keeps_normal_text():
    assert ls.redact("route 10.5, 106.5 at 40 km/h") == "route 10.5, 106.5 at 40 km/h"


def test_setup_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(ls, "LOG_FILE", str(tmp_path / "logs" / "b.log"))
    monkeypatch.setattr(ls, "_configured", False)
    log1 = ls.setup_logging(console=False)
    n = len(log1.handlers)
    log2 = ls.setup_logging(console=False)
    assert log1 is log2
    assert len(log2.handlers) == n  # not doubled


def test_log_writes_redacted(tmp_path, monkeypatch):
    logdir = tmp_path / "logs"
    monkeypatch.setattr(ls, "LOG_DIR", str(logdir))
    monkeypatch.setattr(ls, "LOG_FILE", str(logdir / "b.log"))
    monkeypatch.setattr(ls, "_configured", False)
    log = ls.setup_logging(console=False)
    log.info("device DEADBEEF-1122334455667788 connected")
    for h in log.handlers:
        h.flush()
    content = (logdir / "b.log").read_text(encoding="utf-8")
    assert "DEADBEEF-1122334455667788" not in content
    assert "device" in content
