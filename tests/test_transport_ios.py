"""iOS transport — module-level helpers and the drop-error regression.

No iPhone is present, so these cover the pure logic and the exception wiring
that the reconnect path depends on (see IOS-001)."""

import asyncio

import pytest

import core.transport.ios as ios


def test_major_parsing():
    assert ios._major("17.5.1") == 17
    assert ios._major("16.0") == 16
    assert ios._major("garbage") == 0
    assert ios._major("") == 0


def test_drop_errors_is_flat_tuple_of_exceptions():
    """Regression for IOS-001: a nested tuple in `except` raises TypeError at
    catch time, which silently killed the DVT rebuild path. Every element must
    be an exception class, so the tuple can be used directly in `except`."""
    assert isinstance(ios._DROP_ERRORS, tuple)
    for exc in ios._DROP_ERRORS:
        assert isinstance(exc, type) and issubclass(exc, BaseException), exc


def test_drop_errors_usable_in_except():
    """Actually exercise it the way _pump does."""
    for err in (OSError("x"), ConnectionResetError("x"), asyncio.TimeoutError()):
        try:
            raise err
        except ios._DROP_ERRORS:
            pass  # must catch without TypeError
        else:
            pytest.fail(f"{type(err).__name__} not caught by _DROP_ERRORS")


def test_transport_available_flag():
    t = ios.IOSTransport()
    # _CORE_OK reflects whether pymobiledevice3 imported; here it should be True.
    assert t.available() == ios._CORE_OK


def test_send_location_false_when_not_running():
    t = ios.IOSTransport()
    # Never connected: no loop/queue, must report the link as not carrying.
    assert t.send_location(10.0, 106.0) is False
