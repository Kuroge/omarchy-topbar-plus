#!/usr/bin/env python3
"""Live regression check. Moves the pointer and opens/closes the clock popup."""
import json
import argparse
import pathlib
import subprocess
import sys
import time

from evdev import UInput, ecodes

EDGE_NAMESPACE = "omarchy-topbar-plus-edge"
TOP_LEVEL = "2"
OVERLAY_LEVEL = "3"


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def state():
    return json.loads(run("omarchy", "shell", "topbar-plus", "status"))


def move(x, y, pointer=None):
    run("hyprctl", "eval", f"hl.dispatch(hl.dsp.cursor.move({{ x = {x}, y = {y} }}))")
    if pointer is not None:
        # A compositor warp inside one surface does not send a Qt motion event.
        pointer.write(ecodes.EV_REL, ecodes.REL_X, 1)
        pointer.syn()


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        current = state()
        if predicate(current):
            return current
        time.sleep(0.02)
    raise AssertionError(f"Timed out: {current}")


def geometry():
    clients = json.loads(run("hyprctl", "clients", "-j"))
    monitors = json.loads(run("hyprctl", "monitors", "-j"))
    return ({c["address"]: (c["at"], c["size"]) for c in clients},
            {m["name"]: m["reserved"] for m in monitors})


def bar_layers(name):
    levels = json.loads(run("hyprctl", "layers", "-j"))[name]["levels"]
    return {level: [w for w in surfaces if w["namespace"] == "omarchy-bar"]
            for level, surfaces in levels.items()}


def assert_parked(monitor):
    # At rest the native bar keeps its own layer and parks its full-screen
    # surface off screen; nothing of it may stay over the windows.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        layers = bar_layers(monitor["name"])
        top = layers.get(TOP_LEVEL, [])
        if (not layers.get(OVERLAY_LEVEL) and top
                and all(w["y"] + w["h"] <= monitor["y"] for w in top)):
            return
        time.sleep(0.02)
    raise AssertionError((monitor["name"], "bar is not parked natively", layers))


def close_popouts():
    # Toggling the clock closes it, or switches any other popout, including
    # tray management, to the clock so the next toggle closes it.
    for _ in range(3):
        if not state()["popout"]:
            return
        run("omarchy", "shell", "omarchy.clock", "toggle")
        time.sleep(0.3)
    if state()["popout"]:
        raise AssertionError("A popout is still open")


def cleanup(*steps):
    failures = []
    for step in steps:
        try:
            step()
        except Exception as error:
            failures.append(error)
            print(f"CLEANUP FAILED: {error!r}", file=sys.stderr)
    return failures


def check_tray(monitor, pointer):
    def panel(s):
        return next(p for p in s["screens"] if p["name"] == monitor["name"])

    tray = panel(state())["tray"]
    if not tray or tray["extent"] == 0:
        print(f"SKIP {monitor['name']}: no native tray drawer items")
        return
    assert tray["chevron"], "Native tray chevron not found"
    x, y = monitor["x"], monitor["y"]
    row = y + round(tray["y"] + tray["height"] / 2)

    def chevron_x():
        chevron = panel(state())["tray"]["chevron"]
        return x + round(chevron["x"] + chevron["w"] / 2)

    def open_drawer():
        move(chevron_x(), row, pointer)
        wait_for(lambda s: panel(s)["tray"]["progress"] == 1)

    def collapse():
        move(x + 100, row, pointer)
        wait_for(lambda s: panel(s)["tray"]["progress"] == 0)

    collapse()
    # Enter the collapsed chevron, then traverse the revealed app icons. The
    # drawer opens between the chevron and the pinned icons, pushing the
    # chevron away from the fixed edge.
    open_drawer()
    opened = panel(state())["tray"]
    chevron = opened["chevron"]
    drawer_start = (chevron["x"] - opened["extent"] if opened["fixedAtStart"]
                    else chevron["x"] + chevron["w"])
    for offset in range(0, round(opened["extent"]), round(opened["slot"])):
        move(x + round(drawer_start + offset + opened["slot"] / 2), row, pointer)
        time.sleep(0.2)
        current = state()
        assert panel(current)["tray"]["expanded"], "Native tray lost hover over app icons"
        assert not current["hidden"] or panel(current)["revealed"], "Tray hover lost the bar"
    collapse()
    # Right-click the chevron to exercise native button and popup delivery.
    for opening in [True, False]:
        open_drawer()
        move(chevron_x(), row, pointer)
        time.sleep(0.1)
        pointer.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
        pointer.syn()
        pointer.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 0)
        pointer.syn()
        wait_for(lambda s: panel(s)["tray"]["manageOpen"] == opening)
        if opening:
            move(x + 100, y + 200, pointer)
            time.sleep(0.4)
            current = state()
            assert not current["hidden"] or panel(current)["revealed"], "Tray popup lost the bar"
    collapse()
    print(f"PASS {monitor['name']}: tray hover, icons, right-click popup, collapse")

def check(monitor_name=None):
    assert state()["position"] == "top", "Set the bar to top before running"
    flag = pathlib.Path.home() / ".local/state/omarchy/toggles/bar-off"
    was_hidden = flag.exists()
    cursor = json.loads(run("hyprctl", "cursorpos", "-j"))
    monitors = json.loads(run("hyprctl", "monitors", "-j"))
    if monitor_name:
        monitors = [m for m in monitors if m["name"] == monitor_name]
        assert monitors, f"Monitor not found: {monitor_name}"
    pointer = UInput({ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                      ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]},
                     name="topbar-plus-check")
    time.sleep(0.3)

    def point(x, y):
        move(x, y, pointer)

    try:
        # 'on' sets the bar-off flag, which hides the bar.
        run("omarchy", "toggle", "bar", "on")
        wait_for(lambda s: s["hidden"])
        for monitor in monitors:
            name = monitor["name"]
            x, y = monitor["x"] + 100, monitor["y"]

            def panel(s):
                return next(p for p in s["screens"] if p["name"] == name)

            point(x, y + 200)
            wait_for(lambda s: not panel(s)["revealed"] and not panel(s)["engaged"])
            assert_parked(monitor)
            hidden_offset = panel(state())["offset"]
            assert hidden_offset == -panel(state())["thickness"], "Peek does not start at the bar thickness"
            before = geometry()
            point(x, y)
            wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"])
            assert flag.exists(), "Hover changed the user's hidden preference"
            assert geometry() == before, "Hover changed client geometry or reserved space"
            # QML animation completion precedes the compositor's frame commit,
            # especially on a headless output. Check the committed placement.
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                layers = json.loads(run("hyprctl", "layers", "-j"))[name]["levels"][OVERLAY_LEVEL]
                if any(w["namespace"] == "omarchy-bar" and w["y"] == y for w in layers):
                    break
                time.sleep(0.02)
            else:
                raise AssertionError((name, "bar did not reach the overlay edge", layers, state(), run("hyprctl", "cursorpos", "-j")))
            physical_width = monitor["height"] if monitor["transform"] % 2 else monitor["width"]
            logical_width = round(physical_width / monitor["scale"])
            for namespace in ["omarchy-bar", EDGE_NAMESPACE]:
                surface = next(w for w in layers if w["namespace"] == namespace)
                assert (surface["x"], surface["y"], surface["w"]) == (
                    monitor["x"], y, logical_width), ("Scaled surface mismatch", surface)
            for pointer_y in [y + 12, y, y + 12]:
                point(x, pointer_y)
                time.sleep(0.4)
                actual = json.loads(run("hyprctl", "cursorpos", "-j"))
                assert abs(actual["x"] - x) <= 2 and actual["y"] == pointer_y, "Pointer moved during the check; retry while idle"
                assert panel(state())["revealed"], "Crossing onto widgets hid the bar"
            # Re-enter around the hide timer's deadline; a queued timeout
            # must not override a fresh hover event.
            for _ in range(3):
                point(x, y + 40)
                time.sleep(0.08)
                point(x, y + 12)
                time.sleep(0.2)
                assert panel(state())["revealed"], "Re-entry lost to a hide timeout"
            check_tray(monitor, pointer)
            point(x, y + 200)
            wait_for(lambda s: not panel(s)["revealed"] and not panel(s)["engaged"]
                     and panel(s)["offset"] == hidden_offset)
            assert_parked(monitor)
            assert geometry() == before, "Hiding changed client geometry or reserved space"
            print(f"PASS {name}: edge, widget hover, overlay, hide, native park, unchanged geometry")

        if not monitor_name:
            # Every screen's clock registers omarchy.clock and only the first
            # one answers, opening the popup on its own screen. Find it first.
            all_monitors = json.loads(run("hyprctl", "monitors", "-j"))
            close_popouts()
            run("omarchy", "shell", "omarchy.clock", "toggle")
            wait_for(lambda s: s["popout"])
            owner = next((p["name"] for p in state()["screens"] if p["popout"]), None)
            assert owner, "Clock popup belongs to no bar window"
            close_popouts()
            clock_monitor = next(m for m in all_monitors if m["name"] == owner)

            def clock_panel(s):
                return next(p for p in s["screens"] if p["name"] == owner)

            point(clock_monitor["x"] + 100, clock_monitor["y"])
            wait_for(lambda s: clock_panel(s)["revealed"])
            run("omarchy", "shell", "omarchy.clock", "toggle")
            wait_for(lambda s: clock_panel(s)["popout"])
            point(clock_monitor["x"] + 100, clock_monitor["y"] + 100)
            time.sleep(0.4)
            current = clock_panel(state())
            assert current["revealed"] and current["held"], ("Clock popup did not hold the bar open", current)
            run("omarchy", "shell", "omarchy.clock", "toggle")
            wait_for(lambda s: not s["popout"] and all(not p["revealed"] for p in s["screens"]))
            print("PASS native popup holds the bar open and releases it on close")
        run("omarchy", "toggle", "bar", "off")
        wait_for(lambda s: not s["hidden"]
                 and all(not p["engaged"] and p["margin"] == 0 for p in s["screens"]))
        time.sleep(0.4)
        assert not state()["hidden"], "Pinned bar unexpectedly hid"
        print("PASS normal visible toggle stays pinned")
        for monitor in monitors:
            check_tray(monitor, pointer)
    finally:
        failures = cleanup(
            close_popouts,
            lambda: run("omarchy", "toggle", "bar", "on" if was_hidden else "off"),
            pointer.close,
            lambda: move(cursor["x"], cursor["y"]),
        )
        if failures and sys.exc_info()[0] is None:
            raise failures[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monitor", help="check only this output, for mixed-DPI testing")
    parser.add_argument("--appearance", action="store_true",
                        help="also check every bar background with desktop background enabled/disabled")
    args = parser.parse_args()
    if not args.appearance:
        check(args.monitor)
    else:
        config = json.loads((pathlib.Path.home() / ".config/omarchy/shell.json").read_text())
        background = run("omarchy", "bar", "background")
        wallpaper_enabled = "omarchy.background" not in (config.get("disabledPlugins") or [])
        try:
            for wallpaper in [True, False]:
                run("omarchy", "plugin", "enable" if wallpaper else "disable", "omarchy.background")
                for bar_background in ["opaque", "glassy", "none"]:
                    run("omarchy", "bar", "background", bar_background)
                    time.sleep(0.5)
                    print(f"CHECK wallpaper={wallpaper}, background={bar_background}", flush=True)
                    check(args.monitor)
        finally:
            cleanup(
                lambda: run("omarchy", "bar", "background", background),
                lambda: run("omarchy", "plugin", "enable" if wallpaper_enabled else "disable",
                            "omarchy.background"),
            )
