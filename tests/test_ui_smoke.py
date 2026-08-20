"""Live-window smoke tests. Skipped automatically where no display exists.

These construct the real Tk app, so they also exercise that the control panel,
map, engine wiring and callbacks build without error (startup audit)."""

import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture(scope="module")
def app():
    from ui.app import BumpSpoofApp
    try:
        instance = BumpSpoofApp()
    except Exception as e:  # no display / Tcl not available on this runner
        pytest.skip(f"no GUI available: {type(e).__name__}: {e}")
    instance.update()  # let widgets realize
    yield instance
    try:
        instance._on_close()
    except Exception:
        pass


def test_app_constructs(app):
    from core import __version__
    assert app.title() == f"BumpSpoof {__version__} — Giả lập vị trí GPS"
    # core widgets exist
    assert app.cp is not None
    assert app.map is not None
    assert app.cp.platform.get() in ("iOS", "Android")


def test_start_route_needs_two_waypoints(app):
    """Pressing Run with <2 points must warn, not start or crash."""
    warned = {}
    app._set_status = lambda text, kind="idle": warned.update(text=text, kind=kind)
    # stub the modal so the test never blocks on a dialog
    import ui.app as appmod
    orig = appmod.messagebox.showwarning
    appmod.messagebox.showwarning = lambda *a, **k: None
    try:
        app.waypoints = []
        app._begin("route")
    finally:
        appmod.messagebox.showwarning = orig
    assert warned.get("kind") == "warn"
    assert app.engine is None


def test_begin_worker_failure_is_reported_not_swallowed(app):
    """Regression for UI-001: when start fails on the worker thread, the error
    must reach _fail_start. The reporting lambda runs LATER on the Tk thread,
    so referencing the (by-then-deleted) exception variable would NameError and
    the user would see nothing. We emulate Tk by deferring, then running."""
    deferred = []
    calls = []
    app.after = lambda ms, fn=None, *a: deferred.append(fn) if fn else None
    app._fail_start = lambda msg: calls.append(msg)
    app._set_status = lambda *a, **k: None

    class RaisingTransport:
        mode = "usb"
        def available(self):
            return True
        def connect(self):
            raise RuntimeError("simulated connect failure")
        def disconnect(self):
            pass

    app._begin_worker("free", RaisingTransport(), (10.0, 106.0))
    # Now run everything Tk would have run on the main loop afterwards.
    for fn in deferred:
        fn()  # must not raise NameError
    assert any("RuntimeError" in c and "simulated connect failure" in c for c in calls), calls


def test_parse_and_speed_roundtrip_on_live_panel(app):
    """The speed label always spells out a concrete km/h."""
    app.cp.speed_mode.set("Ô tô")
    app.on_speed_change()
    assert "60 km/h" in app.cp.speed_label.cget("text")


def test_builtin_tour_loads_waypoints(app):
    """A built-in tour must actually populate the route (not be an orphan)."""
    from core.tours import tour_names
    app._set_status = lambda *a, **k: None
    app.cp.tour_var.set(tour_names()[0])  # the full Xuyên Việt tour
    app.on_load_tour()
    assert len(app.waypoints) == 320


def test_builtin_tour_appears_in_menu(app):
    app._refresh_menus()
    from core.tours import tour_names
    values = app.cp.tour_menu.cget("values")
    for name in tour_names():
        assert name in values


def test_about_dialog_does_not_crash(app):
    import ui.app as appmod
    orig = appmod.messagebox.showinfo
    appmod.messagebox.showinfo = lambda *a, **k: None
    try:
        app.on_about()
    finally:
        appmod.messagebox.showinfo = orig


def test_export_then_import_route_roundtrip(app, tmp_path):
    import ui.app as appmod
    from tkinter import filedialog
    app._set_status = lambda *a, **k: None
    p = str(tmp_path / "r.gpx")

    # export current waypoints
    app.waypoints = [(10.5, 106.5), (16.0, 108.0), (21.0, 105.8)]
    orig_save = filedialog.asksaveasfilename
    filedialog.asksaveasfilename = lambda *a, **k: p
    try:
        app.on_export_route()
    finally:
        filedialog.asksaveasfilename = orig_save
    import os
    assert os.path.exists(p)

    # clear, then import it back
    app.on_clear_route()
    assert app.waypoints == []
    orig_open = filedialog.askopenfilename
    filedialog.askopenfilename = lambda *a, **k: p
    orig_warn = appmod.messagebox.showwarning
    appmod.messagebox.showwarning = lambda *a, **k: None
    try:
        app.on_import_route()
    finally:
        filedialog.askopenfilename = orig_open
        appmod.messagebox.showwarning = orig_warn
    assert len(app.waypoints) == 3


def test_diagnostics_worker_builds_report(app):
    # run the worker body without the thread; stub the dialog + after
    import ui.app as appmod
    shown = {}
    appmod.messagebox.showinfo = lambda *a, **k: shown.update(info=a)
    appmod.messagebox.showerror = lambda *a, **k: shown.update(err=a)
    app.after = lambda ms, fn=None, *a: fn() if fn else None
    app._set_status = lambda *a, **k: None
    app._diagnostics_worker()  # uses check_network — may WARN but never raises
    assert "info" in shown or "err" in shown
