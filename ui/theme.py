"""theme.py — shared colors and small style helpers."""

# palette
BG_PANEL = "#1a1b1e"
DIVIDER = "gray25"
MUTED = "gray55"
ACCENT = "#4fc3f7"
GREEN = "#2d8c3c"
GREEN_HOVER = "#3aad4e"
RED = "#c0392b"
RED_HOVER = "#e74c3c"
AMBER = "#e0a92e"
GRAY_BTN = "gray30"
GRAY_BTN_HOVER = "gray38"

# status text colors keyed by "kind"
STATUS_COLORS = {
    "idle": MUTED,
    "info": ACCENT,
    "ok": "#4caf50",
    "warn": AMBER,
    "error": "#ff5252",
    "done": "#4caf50",
}


def status_color(kind: str) -> str:
    return STATUS_COLORS.get(kind, MUTED)
