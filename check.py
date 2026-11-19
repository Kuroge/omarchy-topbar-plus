#!/usr/bin/env python3
"""Live regression check for Top Bar Plus.

Moves a temporary pointer, opens popouts and temporary foot windows, toggles
the bar, and restores all of it afterwards.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

try:
    from evdev import UInput, ecodes
except ImportError:
    sys.exit("python-evdev is missing. Install it with: omarchy pkg add python-evdev")

BAR_NAMESPACE = "omarchy-bar"
EDGE_NAMESPACE = "omarchy-topbar-plus-edge"
TOP_LEVEL = "2"
OVERLAY_LEVEL = "3"
CHECK_APP_ID = "topbar-plus-check"
PEEK_SUPPRESSING_TAG = "no-bar-peek"
BAR_OFF_FLAG = pathlib.Path.home() / ".local/state/omarchy/toggles/bar-off"


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def hypr(query):
    return json.loads(run("hyprctl", query, "-j") or "{}")


def dispatch(expression):
    run("hyprctl", "eval", f"hl.dispatch({expression})")


def warp(x, y):
    dispatch(f"hl.dsp.cursor.move({{ x = {x}, y = {y} }})")


def state():
    return json.loads(run("omarchy", "shell", "topbar-plus", "status"))


def poll(probe, timeout=3, interval=0.02, failure="Timed out"):
    # Return probe()'s first truthy result. Past the timeout, fail with
    # `failure` (called if it is a function), or return the falsy result if
    # `failure` is None.
    deadline = time.monotonic() + timeout
    while not (result := probe()):
        if time.monotonic() >= deadline:
            if failure is None:
                return result
            raise AssertionError(failure() if callable(failure) else failure)
        time.sleep(interval)
    return result


def wait_for(predicate, timeout=3):
    last = {}

    def probe():
        last["state"] = state()
        return last["state"] if predicate(last["state"]) else None

    return poll(probe, timeout, failure=lambda: f"Timed out: {last['state']}")


def cleanup(*steps):
    failures = []
    for step in steps:
        try:
            step()
        except Exception as error:
            failures.append(error)
            print(f"CLEANUP FAILED: {error!r}", file=sys.stderr)
    return failures


def geometry():
    return ({c["address"]: (c["at"], c["size"]) for c in hypr("clients")},
            {m["name"]: m["reserved"] for m in hypr("monitors")})


def focus_window(window):
    if window.get("address"):
        dispatch(f'hl.dsp.focus({{ window = "address:{window["address"]}" }})')


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


def set_fullscreen(window, mode, action="set"):
    dispatch(f'hl.dsp.window.fullscreen({{ mode = "{mode}", action = "{action}", '
             f'window = "address:{window["address"]}" }})')


def expected_suppressed():
    # Hyprland's own view: screens whose active workspace holds a tagged
    # fullscreen or maximized window.
    workspaces = {c["workspace"]["id"] for c in hypr("clients")
                  if c["fullscreen"] > 0 and any(t.rstrip("*") == PEEK_SUPPRESSING_TAG for t in c["tags"])}
    return {m["name"]: m["activeWorkspace"]["id"] in workspaces for m in hypr("monitors")}


def assert_suppression_matches_hyprland():
    expected = expected_suppressed()
    wait_for(lambda s: all(p["suppressed"] == expected[p["name"]] for p in s["screens"]))


class Pointer:
    """A temporary uinput mouse. Compositor warps alone do not deliver motion
    within a surface, so interaction checks use real input events."""

    def __init__(self):
        self.device = UInput({ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                              ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}, name=CHECK_APP_ID)
        time.sleep(0.3)

    def move(self, x, y):
        warp(x, y)
        self.device.write(ecodes.EV_REL, ecodes.REL_X, 1)
        self.device.syn()

    def click(self, button=ecodes.BTN_LEFT):
        for value in (1, 0):
            self.device.write(ecodes.EV_KEY, button, value)
            self.device.syn()

    def close(self):
        self.device.close()


class Screen:
    """One monitor, its panel in the plugin status, and pointer moves relative
    to its top-left corner."""

    def __init__(self, monitor, pointer):
        self.monitor = monitor
        self.name = monitor["name"]
        self.x, self.y = monitor["x"], monitor["y"]
        self.pointer = pointer

    def panel(self, current=None):
        return next(p for p in (current or state())["screens"] if p["name"] == self.name)

    def wait(self, predicate, timeout=3):
        return self.panel(wait_for(lambda s: predicate(self.panel(s)), timeout))

    def point(self, dx=100, dy=0):
        self.pointer.move(self.x + dx, self.y + dy)

    def settle(self, dx=100, dy=0, seconds=0.4):
        self.point(dx, dy)
        time.sleep(seconds)
        return self.panel()

    def reveal(self):
        self.point()
        return self.wait(lambda p: p["offset"] == 0 and p["revealed"])

    def rest_hidden(self):
        self.point(dy=200)
        self.wait(lambda p: not p["revealed"] and not p["engaged"])

    def levels(self):
        return hypr("layers")[self.name]["levels"]

    def bar_layers(self):
        return {level: [w for w in surfaces if w["namespace"] == BAR_NAMESPACE]
                for level, surfaces in self.levels().items()}

    def assert_parked(self):
        # At rest the native bar keeps its own layer and parks its full-screen
        # surface off screen; nothing of it may stay over the windows.
        def parked():
            layers = self.bar_layers()
            top = layers.get(TOP_LEVEL, [])
            return not layers.get(OVERLAY_LEVEL) and top and all(w["y"] + w["h"] <= self.y for w in top)

        poll(parked, failure=lambda: (self.name, "bar is not parked natively", self.bar_layers()))

    def wait_overlay(self):
        # QML animation completion precedes the compositor's frame commit.
        # Check the committed placement.
        def overlay():
            layers = self.levels().get(OVERLAY_LEVEL, [])
            return layers if any(w["namespace"] == BAR_NAMESPACE and w["y"] == self.y for w in layers) else None

        return poll(overlay, failure=lambda: (self.name, "bar did not reach the overlay edge",
                                              state(), hypr("cursorpos")))


class CheckWindows:
    """Temporary foot windows for the fullscreen checks."""

    def __init__(self):
        self.processes = []

    @staticmethod
    def listed():
        return [c for c in hypr("clients") if c["class"] == CHECK_APP_ID]

    def open(self, screen, tag=None):
        dispatch(f'hl.dsp.focus({{ monitor = "{screen.name}" }})')
        self.processes.append(subprocess.Popen(
            ["foot", f"--app-id={CHECK_APP_ID}", "sleep", "600"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        window = poll(lambda: next(iter(self.listed()), None), timeout=5, interval=0.05,
                      failure="Check window did not open")
        assert window["monitor"] == screen.monitor["id"], ("Check window opened on another monitor", window)
        if tag:
            dispatch(f'hl.dsp.window.tag({{ tag = "+{tag}", window = "address:{window["address"]}" }})')
            poll(lambda: tag in next(iter(self.listed()), {}).get("tags", []), interval=0.05,
                 failure=("Check window was not tagged", tag))
        return window

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)
        self.processes.clear()
        poll(lambda: not self.listed(), interval=0.05, failure="Check window is still open")


def check_tray(screen):
    tray = screen.panel()["tray"]
    if not tray or tray["extent"] == 0:
        print(f"SKIP {screen.name}: no native tray drawer items")
        return
    assert tray["chevron"], "Native tray chevron not found"
    pointer = screen.pointer
    row = screen.y + round(tray["y"] + tray["height"] / 2)

    def chevron_x():
        chevron = screen.panel()["tray"]["chevron"]
        return screen.x + round(chevron["x"] + chevron["w"] / 2)

    def open_drawer():
        pointer.move(chevron_x(), row)
        screen.wait(lambda p: p["tray"]["progress"] == 1)

    def collapse():
        pointer.move(screen.x + 100, row)
        screen.wait(lambda p: p["tray"]["progress"] == 0)

    def bar_kept(current):
        return not current["hidden"] or screen.panel(current)["revealed"]

    collapse()
    # Enter the collapsed chevron, then traverse the revealed app icons. The
    # drawer opens between the chevron and the pinned icons, pushing the
    # chevron away from the fixed edge.
    open_drawer()
    opened = screen.panel()["tray"]
    chevron = opened["chevron"]
    drawer_start = (chevron["x"] - opened["extent"] if opened["fixedAtStart"]
                    else chevron["x"] + chevron["w"])
    for offset in range(0, round(opened["extent"]), round(opened["slot"])):
        pointer.move(screen.x + round(drawer_start + offset + opened["slot"] / 2), row)
        time.sleep(0.2)
        current = state()
        tray_now = screen.panel(current)["tray"]
        assert tray_now["expanded"], ("Native tray lost hover over app icons", offset, opened, tray_now,
                                      hypr("cursorpos"))
        assert bar_kept(current), "Tray hover lost the bar"
    collapse()
    # Right-click the chevron to exercise native button and popup delivery.
    for opening in [True, False]:
        open_drawer()
        pointer.move(chevron_x(), row)
        time.sleep(0.1)
        pointer.click(ecodes.BTN_RIGHT)
        screen.wait(lambda p: p["tray"]["manageOpen"] == opening)
        if opening:
            screen.point(dy=200)
            time.sleep(0.4)
            assert bar_kept(state()), "Tray popup lost the bar"
    collapse()
    print(f"PASS {screen.name}: tray hover, icons, right-click popup, collapse")


def check_peek(screen, windows):
    screen.rest_hidden()
    screen.assert_parked()
    hidden_offset = screen.panel()["offset"]
    assert hidden_offset == -screen.panel()["thickness"], "Peek does not start at the bar thickness"
    before = geometry()
    screen.reveal()
    assert BAR_OFF_FLAG.exists(), "Hover changed the user's hidden preference"
    assert geometry() == before, "Hover changed client geometry or reserved space"
    layers = screen.wait_overlay()
    monitor = screen.monitor
    physical_width = monitor["height"] if monitor["transform"] % 2 else monitor["width"]
    logical_width = round(physical_width / monitor["scale"])
    for namespace in [BAR_NAMESPACE, EDGE_NAMESPACE]:
        surface = next(w for w in layers if w["namespace"] == namespace)
        assert (surface["x"], surface["y"], surface["w"]) == (screen.x, screen.y, logical_width), (
            "Scaled surface mismatch", surface)
    for dy in [12, 0, 12]:
        current = screen.settle(dy=dy)
        cursor = hypr("cursorpos")
        assert abs(cursor["x"] - (screen.x + 100)) <= 2 and cursor["y"] == screen.y + dy, (
            "Pointer moved during the check; retry while idle")
        assert current["revealed"], "Crossing onto widgets hid the bar"
    # Re-enter around the hide timer's deadline; a queued timeout must not
    # override a fresh hover event.
    for _ in range(3):
        screen.point(dy=40)
        time.sleep(0.08)
        assert screen.settle(dy=12, seconds=0.2)["revealed"], "Re-entry lost to a hide timeout"
    check_tray(screen)
    screen.point(dy=200)
    screen.wait(lambda p: not p["revealed"] and not p["engaged"] and p["offset"] == hidden_offset)
    screen.assert_parked()
    assert geometry() == before, "Hiding changed client geometry or reserved space"
    print(f"PASS {screen.name}: edge, widget hover, overlay, hide, native park, unchanged geometry")


def check_fast_entry(screen, windows):
    # Leaving the edge for the widgets before the slide-in ends must not hide
    # the bar, even though the pointer then rests where the bar arrives.
    screen.rest_hidden()
    hides = screen.panel()["hides"]
    screen.point()
    screen.wait(lambda p: p["revealed"])
    current = screen.settle(dy=12, seconds=0.6)
    assert current["hides"] == hides and current["revealed"], ("Fast entry hid the bar", current)
    screen.rest_hidden()
    print(f"PASS {screen.name}: fast entry from the edge keeps the bar")


def check_edge_rest(screen, windows):
    # A pointer pushed against the top edge rests inside both the edge trigger
    # and the bar. The bar must stay revealed without bouncing.
    for dy in [0, 1]:
        screen.rest_hidden()
        hides = screen.panel()["hides"]
        screen.point(dy=dy)
        screen.wait(lambda p: p["revealed"])
        time.sleep(1)
        current = screen.panel()
        assert current["hides"] == hides and current["revealed"], (f"Resting at y={dy} hid the bar", current)
    screen.rest_hidden()
    print(f"PASS {screen.name}: resting against the top edge keeps the bar")


def check_popout_rest(screen, windows):
    # Closing a popout with the pointer resting on the bar must not make the
    # bar slide out and straight back in.
    clock = screen.panel()["clock"]
    if not clock:
        print(f"SKIP {screen.name}: no native clock widget")
        return
    screen.rest_hidden()
    screen.reveal()
    screen.wait_overlay()
    screen.point(round(clock["x"] + clock["w"] / 2), round(clock["y"] + clock["h"] / 2))
    screen.wait(lambda p: p["hover"]["bar"])
    screen.pointer.click()
    screen.wait(lambda p: p["popout"])
    time.sleep(0.4)
    hides = screen.panel()["hides"]
    screen.pointer.click()
    screen.wait(lambda p: not p["popout"])
    time.sleep(0.6)
    current = screen.panel()
    assert current["hides"] == hides and current["revealed"], ("Closing a popout over the bar hid it", current)
    screen.rest_hidden()
    print(f"PASS {screen.name}: closing a popout over the bar keeps it steady")


def check_fullscreen(screen, windows):
    screen.rest_hidden()
    window = windows.open(screen)
    set_fullscreen(window, "fullscreen")
    screen.wait(lambda p: p["underFullscreen"])
    assert not screen.panel()["suppressed"], "An untagged fullscreen window suppressed the peek"
    screen.wait(lambda p: not p["fullscreenInput"])
    before = geometry()
    screen.point()
    screen.wait(lambda p: p["offset"] == 0 and p["revealed"] and p["fullscreenInput"])
    screen.wait_overlay()
    screen.point(dy=12)
    screen.wait(lambda p: p["hover"]["bar"])
    time.sleep(0.4)
    assert screen.panel()["revealed"], "Fullscreen bar lost the pointer over its widgets"
    check_tray(screen)
    screen.point(dy=200)
    screen.wait(lambda p: not p["revealed"] and not p["engaged"] and not p["fullscreenInput"])
    screen.assert_parked()
    assert geometry() == before, "Fullscreen peek changed client geometry or reserved space"
    windows.close()
    screen.wait(lambda p: not p["underFullscreen"])
    print(f"PASS {screen.name}: fullscreen peek takes input, tray works, input returns on hide")


def check_suppressed(screen, windows):
    # A tagged fullscreen or maximized window draws its own top-edge bar: the
    # edge must neither reveal the bar nor take the pointer.
    for mode in ["fullscreen", "maximized"]:
        screen.rest_hidden()
        window = windows.open(screen, PEEK_SUPPRESSING_TAG)
        set_fullscreen(window, mode)
        screen.wait(lambda p: p["suppressed"] and not p["hover"]["catching"])
        before = geometry()
        for dy in [0, 1]:
            current = screen.settle(dy=dy)
            assert not current["revealed"] and not current["engaged"], (f"Tagged {mode} window let the bar peek", current)
            assert not current["hover"]["edge"], (f"Edge took the pointer over a tagged {mode} window", current)
        screen.assert_parked()
        assert geometry() == before, "Suppressed edge changed client geometry or reserved space"
        screen.rest_hidden()
        windows.close()
        screen.wait(lambda p: not p["suppressed"])
        print(f"PASS {screen.name}: tagged {mode} window keeps the edge, no peek, edge takes no pointer")


def check_suppressed_peeking(screen, windows):
    # A tagged window going fullscreen under a peeking bar hides the bar.
    screen.rest_hidden()
    window = windows.open(screen, PEEK_SUPPRESSING_TAG)
    assert not screen.panel()["suppressed"], "A tagged window out of fullscreen suppressed the peek"
    screen.reveal()
    screen.point(dy=12)
    screen.wait(lambda p: p["hover"]["bar"])
    set_fullscreen(window, "fullscreen")
    screen.wait(lambda p: p["suppressed"] and not p["revealed"] and not p["engaged"]
                and not p["hover"]["catching"])
    for dy in [12, 0]:
        current = screen.settle(dy=dy)
        assert not current["revealed"] and not current["hover"]["edge"], ("Bar came back over a tagged window", current)
    screen.assert_parked()
    screen.rest_hidden()
    windows.close()
    screen.wait(lambda p: not p["suppressed"])
    print(f"PASS {screen.name}: tagged window going fullscreen hides the peeking bar")


def check_suppressed_close(screen, windows, rounds=3):
    # A remote desktop client leaves fullscreen right before it closes. The
    # suppression must follow Hyprland, not a window list that kept the closed
    # window, and the edge must reveal the bar again.
    screen.rest_hidden()
    for _ in range(rounds):
        window = windows.open(screen, PEEK_SUPPRESSING_TAG)
        set_fullscreen(window, "fullscreen")
        screen.wait(lambda p: p["suppressed"])
        set_fullscreen(window, "fullscreen", "unset")
        windows.close()
        screen.wait(lambda p: not p["suppressed"] and p["hover"]["catching"])
        assert_suppression_matches_hyprland()
    screen.reveal()
    screen.rest_hidden()
    print(f"PASS {screen.name}: closing a tagged window right after fullscreen ({rounds}x) gives the edge back")


def check_clock(screens):
    # Every screen's clock registers omarchy.clock and only the first one
    # answers, opening the popup on its own screen. Find that screen first.
    close_popouts()
    run("omarchy", "shell", "omarchy.clock", "toggle")
    wait_for(lambda s: s["popout"])
    owner = next((p["name"] for p in state()["screens"] if p["popout"]), None)
    assert owner, "Clock popup belongs to no bar window"
    close_popouts()
    screen = next((s for s in screens if s.name == owner), None)
    if not screen:
        print(f"SKIP clock popup: it opens on {owner}, which is not being checked")
        return
    screen.point()
    screen.wait(lambda p: p["revealed"])
    run("omarchy", "shell", "omarchy.clock", "toggle")
    screen.wait(lambda p: p["popout"])
    current = screen.settle(dy=100)
    assert current["revealed"] and current["held"], ("Clock popup did not hold the bar open", current)
    run("omarchy", "shell", "omarchy.clock", "toggle")
    wait_for(lambda s: not s["popout"] and all(not p["revealed"] for p in s["screens"]))
    print("PASS native popup holds the bar open and releases it on close")


def check_pinned(screens):
    run("omarchy", "toggle", "bar", "off")
    wait_for(lambda s: not s["hidden"] and all(not p["engaged"] and p["margin"] == 0 for p in s["screens"]))
    time.sleep(0.4)
    assert not state()["hidden"], "Pinned bar unexpectedly hid"
    print("PASS normal visible toggle stays pinned")
    for screen in screens:
        check_tray(screen)


# In running order. Screen checks run on every checked screen; pinned last,
# since it leaves the bar pinned.
SCREEN_CHECKS = {
    "peek": check_peek,
    "fast-entry": check_fast_entry,
    "edge-rest": check_edge_rest,
    "popout-rest": check_popout_rest,
    "fullscreen": check_fullscreen,
    "suppressed": check_suppressed,
    "suppressed-peeking": check_suppressed_peeking,
    "suppressed-close": check_suppressed_close,
}
GLOBAL_CHECKS = {"clock": check_clock, "pinned": check_pinned}
CHECK_NAMES = [*SCREEN_CHECKS, *GLOBAL_CHECKS]


def preflight():
    # Fail early, with the fix, on what the checks need.
    problems = []
    if not os.access("/dev/uinput", os.W_OK):
        problems.append("Cannot write /dev/uinput, needed for the test pointer. Grant access until the "
                        "next reboot with: sudo setfacl -m u:$USER:rw /dev/uinput")
    if not shutil.which("foot"):
        problems.append("foot is missing, needed for the fullscreen windows: omarchy pkg add foot")
    try:
        lua = run("hyprctl", "eval", "return")
    except (OSError, subprocess.CalledProcessError) as error:
        lua = str(error)
    if lua != "ok":
        problems.append(f"hyprctl eval does not run Lua ({lua!r}). The check needs Hyprland 0.56 or newer.")
    try:
        position = state()["position"]
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        problems.append("Top Bar Plus does not answer `omarchy shell topbar-plus status`. Select it with: "
                        "omarchy bar use io.github.kuroge.topbar-plus")
    else:
        if position != "top":
            problems.append(f"The bar is at the {position}; Top Bar Plus only peeks a top bar. Move it to the top.")
    if problems:
        sys.exit("Cannot run the check:\n- " + "\n- ".join(problems))


def check(monitor_name=None, only=None, repeat=1):
    was_hidden = BAR_OFF_FLAG.exists()
    cursor = hypr("cursorpos")
    focused = hypr("activewindow")
    monitors = hypr("monitors")
    if monitor_name:
        monitors = [m for m in monitors if m["name"] == monitor_name]
        assert monitors, f"Monitor not found: {monitor_name}"
    names = [name for name in CHECK_NAMES if not only or name in only]
    windows = CheckWindows()
    pointer = Pointer()
    screens = [Screen(m, pointer) for m in monitors]
    try:
        for _ in range(repeat):
            # 'on' sets the bar-off flag, which hides the bar.
            run("omarchy", "toggle", "bar", "on")
            wait_for(lambda s: s["hidden"])
            for name in names:
                if name in SCREEN_CHECKS:
                    for screen in screens:
                        SCREEN_CHECKS[name](screen, windows)
                else:
                    GLOBAL_CHECKS[name](screens)
    finally:
        failures = cleanup(
            windows.close,
            lambda: focus_window(focused),
            close_popouts,
            lambda: run("omarchy", "toggle", "bar", "on" if was_hidden else "off"),
            pointer.close,
            lambda: warp(cursor["x"], cursor["y"]),
        )
        if failures and sys.exc_info()[0] is None:
            raise failures[0]


def reconnect(name):
    # Turning the outputs off is what the idle daemon does. Some monitors, like
    # an OLED that drops off DisplayPort, disconnect and come back as new outputs.
    def present():
        return any(m["name"] == name for m in hypr("monitors"))

    def panel_back():
        try:
            return any(p["name"] == name for p in state()["screens"])
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return False

    assert present(), f"Monitor not found: {name}"
    dispatch('hl.dsp.dpms({ action = "disable" })')
    try:
        # A short blank does not let such a monitor reach the standby that drops it.
        time.sleep(20)
    finally:
        dispatch('hl.dsp.dpms({ action = "enable" })')
    # Such a monitor drops off as it wakes up; wait for that, then for its return.
    dropped = poll(lambda: not present(), timeout=8, interval=0.1, failure=None)
    poll(present, timeout=30, interval=0.2, failure=f"{name} did not come back")
    poll(panel_back, timeout=15, interval=0.2, failure=None)
    time.sleep(3)
    assert dropped, f"{name} did not disconnect while the outputs were off"
    print(f"RECONNECTED {name}: outputs off and on again")


def check_reconnect(name):
    # A tagged fullscreen window that outlives its monitor's reconnection must
    # keep the suppression in step with Hyprland.
    monitor = next((m for m in hypr("monitors") if m["name"] == name), None)
    assert monitor, f"Monitor not found: {name}"
    focused = hypr("activewindow")
    windows = CheckWindows()
    screen = Screen(monitor, pointer=None)
    try:
        window = windows.open(screen, PEEK_SUPPRESSING_TAG)
        set_fullscreen(window, "fullscreen")
        screen.wait(lambda p: p["suppressed"])
        reconnect(name)
        assert_suppression_matches_hyprland()
        print(f"PASS {name}: suppression matches Hyprland after the reconnect")
    finally:
        cleanup(windows.close, lambda: focus_window(focused))


def check_names(value):
    names = [name.strip() for name in value.split(",") if name.strip()]
    unknown = [name for name in names if name not in CHECK_NAMES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown checks: {', '.join(unknown)}; choose from {', '.join(CHECK_NAMES)}")
    return names


def check_appearance(monitor_name, only, repeat):
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
                check(monitor_name, only, repeat)
    finally:
        cleanup(
            lambda: run("omarchy", "bar", "background", background),
            lambda: run("omarchy", "plugin", "enable" if wallpaper_enabled else "disable", "omarchy.background"),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monitor", help="check only this output, for mixed-DPI testing")
    parser.add_argument("--reconnect", metavar="MONITOR",
                        help="turn the outputs off and on first, then check this output")
    parser.add_argument("--appearance", action="store_true",
                        help="also check every bar background with desktop background enabled/disabled")
    parser.add_argument("--only", type=check_names, metavar="CHECKS",
                        help=f"comma-separated checks to run: {', '.join(CHECK_NAMES)}")
    parser.add_argument("--repeat", type=int, default=1, metavar="N",
                        help="run the selected checks N times, to catch intermittent failures")
    args = parser.parse_args()
    preflight()
    if args.reconnect:
        check_reconnect(args.reconnect)
        args.monitor = args.reconnect
    if args.appearance:
        check_appearance(args.monitor, args.only, args.repeat)
    else:
        check(args.monitor, args.only, args.repeat)
