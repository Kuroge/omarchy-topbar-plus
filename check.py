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


def wait_overlay(monitor):
    # QML animation completion precedes the compositor's frame commit,
    # especially on a headless output. Check the committed placement.
    name, y = monitor["name"], monitor["y"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        layers = json.loads(run("hyprctl", "layers", "-j"))[name]["levels"][OVERLAY_LEVEL]
        if any(w["namespace"] == "omarchy-bar" and w["y"] == y for w in layers):
            return layers
        time.sleep(0.02)
    raise AssertionError((name, "bar did not reach the overlay edge", layers, state(),
                          run("hyprctl", "cursorpos", "-j")))


def reconnect(name):
    # Turning the outputs off is what the idle daemon does. Some monitors, like
    # an OLED that drops off DisplayPort, disconnect and come back as new outputs.
    def present():
        return any(m["name"] == name for m in json.loads(run("hyprctl", "monitors", "-j")))

    assert present(), f"Monitor not found: {name}"
    dispatch('hl.dsp.dpms({ action = "disable" })')
    try:
        # A short blank does not let such a monitor reach the standby that drops it.
        time.sleep(20)
    finally:
        dispatch('hl.dsp.dpms({ action = "enable" })')
    # Such a monitor drops off as it wakes up; wait for that, then for its return.
    dropped = False
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and not dropped:
        dropped = not present()
        time.sleep(0.1)
    deadline = time.monotonic() + 30
    while not present() and time.monotonic() < deadline:
        time.sleep(0.2)
    assert present(), f"{name} did not come back"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if any(p["name"] == name for p in state()["screens"]):
                break
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    time.sleep(3)
    assert dropped, f"{name} did not disconnect while the outputs were off"
    print(f"RECONNECTED {name}: outputs off and on again")


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


CHECK_APP_ID = "topbar-plus-check"
PEEK_SUPPRESSING_TAG = "no-bar-peek"


def dispatch(expression):
    run("hyprctl", "eval", f"hl.dispatch({expression})")


def check_windows():
    return [c for c in json.loads(run("hyprctl", "clients", "-j"))
            if c["class"] == CHECK_APP_ID]


def close_check_windows(processes):
    for process in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
    deadline = time.monotonic() + 3
    while check_windows() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not check_windows(), "Check window is still open"


def open_check_window(monitor, processes, tag=None):
    dispatch(f'hl.dsp.focus({{ monitor = "{monitor["name"]}" }})')
    processes.append(subprocess.Popen(
        ["foot", f"--app-id={CHECK_APP_ID}", "sleep", "600"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    deadline = time.monotonic() + 5
    while not check_windows() and time.monotonic() < deadline:
        time.sleep(0.05)
    window = next(iter(check_windows()), None)
    assert window, "Check window did not open"
    assert window["monitor"] == monitor["id"], ("Check window opened on another monitor", window)
    if tag:
        dispatch(f'hl.dsp.window.tag({{ tag = "+{tag}", window = "address:{window["address"]}" }})')
        deadline = time.monotonic() + 3
        while tag not in next(iter(check_windows()), {}).get("tags", []) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert tag in next(iter(check_windows()), {}).get("tags", []), ("Check window was not tagged", tag)
    return window


def set_fullscreen(window, mode):
    dispatch(f'hl.dsp.window.fullscreen({{ mode = "{mode}", action = "set", '
             f'window = "address:{window["address"]}" }})')


def check_fullscreen(monitor, pointer, processes):
    name = monitor["name"]
    x, y = monitor["x"] + 100, monitor["y"]
    panel = screen_panel(name)

    rest_hidden(monitor, pointer)
    window = open_check_window(monitor, processes)
    set_fullscreen(window, "fullscreen")
    wait_for(lambda s: panel(s)["underFullscreen"])
    assert not panel(state())["suppressed"], "An untagged fullscreen window suppressed the peek"
    wait_for(lambda s: not panel(s)["fullscreenInput"])
    before = geometry()
    move(x, y, pointer)
    wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"]
             and panel(s)["fullscreenInput"])
    wait_overlay(monitor)
    move(x, y + 12, pointer)
    wait_for(lambda s: panel(s)["hover"]["bar"])
    time.sleep(0.4)
    assert panel(state())["revealed"], "Fullscreen bar lost the pointer over its widgets"
    check_tray(monitor, pointer)
    move(x, y + 200, pointer)
    wait_for(lambda s: not panel(s)["revealed"] and not panel(s)["engaged"]
             and not panel(s)["fullscreenInput"])
    assert_parked(monitor)
    assert geometry() == before, "Fullscreen peek changed client geometry or reserved space"
    close_check_windows(processes)
    wait_for(lambda s: not panel(s)["underFullscreen"])
    print(f"PASS {name}: fullscreen peek takes input, tray works, input returns on hide")


def check_suppressed(monitor, pointer, processes, mode):
    # A tagged fullscreen or maximized window draws its own top-edge bar: the
    # edge must neither reveal the bar nor take the pointer.
    name = monitor["name"]
    x, y = monitor["x"] + 100, monitor["y"]
    panel = screen_panel(name)

    rest_hidden(monitor, pointer)
    window = open_check_window(monitor, processes, PEEK_SUPPRESSING_TAG)
    set_fullscreen(window, mode)
    wait_for(lambda s: panel(s)["suppressed"] and not panel(s)["hover"]["catching"])
    before = geometry()
    for pointer_y in [y, y + 1]:
        move(x, pointer_y, pointer)
        time.sleep(0.4)
        current = panel(state())
        assert not current["revealed"] and not current["engaged"], (f"Tagged {mode} window let the bar peek", current)
        assert not current["hover"]["edge"], (f"Edge took the pointer over a tagged {mode} window", current)
    assert_parked(monitor)
    assert geometry() == before, "Suppressed edge changed client geometry or reserved space"
    rest_hidden(monitor, pointer)
    close_check_windows(processes)
    wait_for(lambda s: not panel(s)["suppressed"])
    print(f"PASS {name}: tagged {mode} window keeps the edge, no peek, edge takes no pointer")


def check_suppressed_while_peeking(monitor, pointer, processes):
    # A tagged window going fullscreen under a peeking bar hides the bar.
    name = monitor["name"]
    x, y = monitor["x"] + 100, monitor["y"]
    panel = screen_panel(name)

    rest_hidden(monitor, pointer)
    window = open_check_window(monitor, processes, PEEK_SUPPRESSING_TAG)
    assert not panel(state())["suppressed"], "A tagged window out of fullscreen suppressed the peek"
    move(x, y, pointer)
    wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"])
    move(x, y + 12, pointer)
    wait_for(lambda s: panel(s)["hover"]["bar"])
    set_fullscreen(window, "fullscreen")
    wait_for(lambda s: panel(s)["suppressed"] and not panel(s)["revealed"]
             and not panel(s)["engaged"] and not panel(s)["hover"]["catching"])
    for pointer_y in [y + 12, y]:
        move(x, pointer_y, pointer)
        time.sleep(0.4)
        current = panel(state())
        assert not current["revealed"] and not current["hover"]["edge"], ("Bar came back over a tagged window", current)
    assert_parked(monitor)
    rest_hidden(monitor, pointer)
    close_check_windows(processes)
    wait_for(lambda s: not panel(s)["suppressed"])
    print(f"PASS {name}: tagged window going fullscreen hides the peeking bar")


def click(pointer, button=ecodes.BTN_LEFT):
    pointer.write(ecodes.EV_KEY, button, 1)
    pointer.syn()
    pointer.write(ecodes.EV_KEY, button, 0)
    pointer.syn()


def screen_panel(name):
    return lambda s: next(p for p in s["screens"] if p["name"] == name)


def rest_hidden(monitor, pointer):
    panel = screen_panel(monitor["name"])
    move(monitor["x"] + 100, monitor["y"] + 200, pointer)
    wait_for(lambda s: not panel(s)["revealed"] and not panel(s)["engaged"])


def check_fast_entry(monitor, pointer):
    # Leaving the edge for the widgets before the slide-in ends must not hide
    # the bar, even though the pointer then rests where the bar arrives.
    name = monitor["name"]
    panel = screen_panel(name)
    x, y = monitor["x"] + 100, monitor["y"]
    rest_hidden(monitor, pointer)
    hides = panel(state())["hides"]
    move(x, y, pointer)
    wait_for(lambda s: panel(s)["revealed"])
    move(x, y + 12, pointer)
    time.sleep(0.6)
    current = panel(state())
    assert current["hides"] == hides and current["revealed"], ("Fast entry hid the bar", current)
    rest_hidden(monitor, pointer)
    print(f"PASS {name}: fast entry from the edge keeps the bar")


def check_edge_rest(monitor, pointer):
    # A pointer pushed against the top edge rests inside both the edge trigger
    # and the bar. The bar must stay revealed without bouncing.
    name = monitor["name"]
    panel = screen_panel(name)
    x, y = monitor["x"] + 100, monitor["y"]
    for pointer_y in [y, y + 1]:
        rest_hidden(monitor, pointer)
        hides = panel(state())["hides"]
        move(x, pointer_y, pointer)
        wait_for(lambda s: panel(s)["revealed"])
        time.sleep(1)
        current = panel(state())
        assert current["hides"] == hides and current["revealed"], (
            f"Resting at y={pointer_y - y} hid the bar", current)
    rest_hidden(monitor, pointer)
    print(f"PASS {name}: resting against the top edge keeps the bar")


def check_popout_rest(monitor, pointer):
    # Closing a popout with the pointer resting on the bar must not make the
    # bar slide out and straight back in.
    name = monitor["name"]
    panel = screen_panel(name)
    clock = panel(state())["clock"]
    if not clock:
        print(f"SKIP {name}: no native clock widget")
        return
    x, y = monitor["x"], monitor["y"]
    clock_x = x + round(clock["x"] + clock["w"] / 2)
    clock_y = y + round(clock["y"] + clock["h"] / 2)
    rest_hidden(monitor, pointer)
    move(x + 100, y, pointer)
    wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"])
    wait_overlay(monitor)
    move(clock_x, clock_y, pointer)
    wait_for(lambda s: panel(s)["hover"]["bar"])
    click(pointer)
    wait_for(lambda s: panel(s)["popout"])
    time.sleep(0.4)
    hides = panel(state())["hides"]
    click(pointer)
    wait_for(lambda s: not panel(s)["popout"])
    time.sleep(0.6)
    current = panel(state())
    assert current["hides"] == hides and current["revealed"], ("Closing a popout over the bar hid it", current)
    rest_hidden(monitor, pointer)
    print(f"PASS {name}: closing a popout over the bar keeps it steady")


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
    focused = json.loads(run("hyprctl", "activewindow", "-j") or "{}")
    processes = []
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
            layers = wait_overlay(monitor)
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

        for monitor in monitors:
            check_fast_entry(monitor, pointer)
            check_edge_rest(monitor, pointer)
            check_popout_rest(monitor, pointer)

        for monitor in monitors:
            check_fullscreen(monitor, pointer, processes)
            for mode in ["fullscreen", "maximized"]:
                check_suppressed(monitor, pointer, processes, mode)
            check_suppressed_while_peeking(monitor, pointer, processes)

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
            lambda: close_check_windows(processes),
            lambda: focused.get("address") and dispatch(
                f'hl.dsp.focus({{ window = "address:{focused["address"]}" }})'),
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
    parser.add_argument("--reconnect", metavar="MONITOR",
                        help="turn the outputs off and on first, then check this output")
    parser.add_argument("--appearance", action="store_true",
                        help="also check every bar background with desktop background enabled/disabled")
    args = parser.parse_args()
    if args.reconnect:
        reconnect(args.reconnect)
        args.monitor = args.reconnect
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
