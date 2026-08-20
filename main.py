"""BumpSpoof — entry point.

    py -3.13 main.py            # launch the app
    py -3.13 main.py --doctor   # print a system self-check and exit
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None) -> int:
    """Launch the desktop app (or run the doctor). Returns an exit code."""
    argv = sys.argv[1:] if argv is None else argv

    # Windows consoles default to a legacy code page that mangles Vietnamese
    # and emoji; force UTF-8 so --doctor output is readable.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    if "--doctor" in argv or "doctor" in argv:
        from core.diagnostics import main as doctor_main
        return doctor_main()
    if "--version" in argv or "-V" in argv:
        from core import __version__
        print(f"BumpSpoof {__version__}")
        return 0

    from core import __version__
    from core.logging_setup import setup_logging
    log = setup_logging()
    log.info("BumpSpoof %s khởi động (Python %s)", __version__,
             ".".join(map(str, sys.version_info[:3])))
    try:
        from ui.app import BumpSpoofApp
        BumpSpoofApp().mainloop()
    except Exception:
        log.exception("Lỗi không bắt được ở vòng đời app")
        raise
    finally:
        log.info("BumpSpoof thoát")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
