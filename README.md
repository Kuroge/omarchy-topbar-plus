# Omarchy Top Bar Plus

Hide your top bar with the usual Omarchy toggle. Touch the top two logical pixels of
a screen to slide that screen's bar back over your windows. Move away and it slides out.

Top Bar Plus runs inside Omarchy's existing Quickshell process and inherits the
installed bar. Your widgets, layout, colors, fonts, background, menus and
popouts remain native. Hover never changes the saved hidden preference or
reserves desktop space. A normally visible bar behaves as usual.

It is based on [Omarchy Top Bar Peek](https://github.com/WhiteHades/omarchy-topbar-peek)
by WhiteHades, adapted to Omarchy 4.5.

## Requirements

Tested on:

| Component | Version |
|---|---|
| Omarchy | 4.5.0 |
| Hyprland | 0.56.2 |
| Quickshell | 0.3.2 |

There are no extra runtime dependencies. The optional live regression check
uses Python 3 and `python-evdev` with access to `/dev/uinput`.

## Install

```sh
omarchy plugin add https://github.com/Kuroge/omarchy-topbar-plus --enable --yes
```

Use **Super + Shift + Space** to toggle the bar. While hidden, hover at the
top edge of a screen. The bar stays open over its widgets and while one of its
popouts is open. After leaving, it waits 120 ms and slides out over 140 ms using
the same `OutCubic` easing and duration as Omarchy's popup cards. Animations
follow `omarchy toggle animations`.

This behavior applies to top bars only. Other bar positions retain their stock
behavior. Each screen gets its own reveal trigger. Sizing stays in Qt/Wayland
logical coordinates, so each output applies its own scale.

Update or return to the stock bar:

```sh
omarchy plugin update io.github.kuroge.topbar-plus --yes
omarchy bar use omarchy.bar
# Optional, after switching back:
omarchy plugin remove io.github.kuroge.topbar-plus --yes
```

## Apps with their own top bar

Some fullscreen apps, such as the RDPchy remote desktop client, slide down
their own bar from the top edge. Tag their windows `no-bar-peek` with a
Hyprland window rule, for example in `~/.config/hypr/hyprland.lua`:

```lua
o.window("^com\\.freerdp\\.client\\.sdl3$", { tag = "+no-bar-peek" })
```

While a tagged window is fullscreen or maximized on a screen's active
workspace, that screen's bar does not peek and its edge trigger takes no
pointer input, so the edge belongs to the app. A peeking bar slides out when
that happens. Out of fullscreen, and for untagged fullscreen windows, the bar
peeks as usual.

## Known limitations

- The QML inheritance and panel discovery use **internal bar implementation
  details**, not a promised stable Omarchy API. Omarchy updates may require a
  plugin update.
- Hyprland sends no event when a tag changes. A tag added by hand to a window
  that is already fullscreen takes effect at the next window event, such as a
  fullscreen change, a window opening or closing, or a workspace switch. Tags
  set by a window rule apply when the window opens.

## How it works

`Bar.qml` inherits `qs.plugins.bar.Bar`. It finds that bar's native panel
windows and adds, per screen, a two-pixel Wayland edge trigger on the overlay
layer plus a passive hover observer on the widgets' shared parent, so native
hover handlers, including the tray drawer, keep receiving pointer events.

In Omarchy 4.5 each native panel is a transparent surface as tall as its screen
that parks a full screen height above it while hidden. At rest the plugin leaves
that native placement and layer untouched, so nothing of the bar stays above
your windows. On reveal it takes over the panel's top margin and layer: it moves
the bar to one bar thickness above the edge, promotes it to the overlay layer
and slides it in. When the bar has slid out, it hands margin and layer back to
the native bar. The stock bar keeps `ExclusionMode.Ignore` because its
`barHidden` state stays true, so no space is reserved. A panel recreated for a
monitor that reconnects, such as an OLED that drops off DisplayPort when it
wakes up, can keep the normal exclusion mode while hidden; the plugin holds it
at `ExclusionMode.Ignore` while the bar is hidden. No polling process,
extra daemon, copied widget implementation, packaged-file edit, or Hyprland
rule is needed.

Omarchy clears the bar's input region while a fullscreen window is on its
screen, so the invisible strip cannot take that window's clicks. While peeking
over a fullscreen window, the plugin gives the visible strip its input back and
restores the native empty region once the bar has slid out.

Hyprland tells a surface that moved under a resting pointer only on the next
pointer motion. Two cases would otherwise make the bar slide out and straight
back in: leaving the edge before the slide-in ends, and closing a popout whose
full-screen layer keeps the pointer while it fades out. The bar is held while
sliding in and while a closed popout fades. Afterwards, if the bar still has not
seen the pointer, the plugin runs `hyprctl eval` once to warp the pointer onto
its own position, so Hyprland picks the surface under it again.

To find tagged fullscreen windows the plugin runs `hyprctl clients -j` when
Hyprland reports a window or workspace event, instead of reading Quickshell's
window list. That list never drops a window whose refresh answer arrives after
it closed, so a client that leaves fullscreen right before closing can linger
there as fullscreen until the shell restarts.

Once the pointer enters the bar below the trigger, the trigger releases input.
Popouts hold the bar until dismissed so you can move into them without losing
their anchor.

## Status and debug logging

```sh
omarchy shell topbar-plus status
omarchy shell topbar-plus setDebug true
journalctl --user --since "-5min" -o short-precise | grep topbar-plus
omarchy shell topbar-plus setDebug false
```

`status` prints the per-screen state as JSON. Debug logging is off by default
and resets when the shell restarts. While on, it logs reveals and hides with
their cause, hold changes, margin and layer hand-overs, the native panel's
fullscreen and exclusion state, and screens being added or removed.

## Verify or develop

```sh
omarchy plugin validate .
python check.py
python check.py --monitor DP-1
python check.py --reconnect DP-2
python check.py --appearance
```

Run the check from an active Hyprland session with Top Bar Plus selected and
the bar at the top. Install the check dependency with
`omarchy pkg add python-evdev` if needed. Your session must have write access
to `/dev/uinput` for its temporary test pointer. Compositor pointer warps alone
do not deliver motion within a surface, so interaction checks use actual input
events. Leave the pointer idle during the check: it stops when the pointer
moves.

It moves the pointer, opens and closes the clock and tray management popouts,
and toggles the bar. It checks edge reveal, widget hover, overlay placement,
the native park at rest, unchanged window geometry and monitor reserved space,
popup retention, hide, and normal pinned visibility. It also checks native tray
expansion, movement across app icons, right-click management, and collapse in
both hidden and pinned modes. Tray checks report a skip when there are no
drawer items. On each screen it also opens a temporary `foot` window, makes it
fullscreen and checks that the peeking bar takes input there and hands it back.
It repeats that with the window tagged `no-bar-peek`, fullscreen and maximized,
and checks that the edge neither reveals the bar nor takes the pointer, and that
a peeking bar slides out when a tagged window goes fullscreen. It also leaves
fullscreen and closes a tagged window straight away several times, as a remote
desktop client does, and checks that the edge reveals the bar again and that
the suppression matches what Hyprland reports.
Afterwards it closes the check windows, refocuses your window, closes any
popout and restores the pointer and the hidden preference; each cleanup step
runs even if another fails.

`--monitor` checks a single output, for mixed-DPI testing. `--reconnect`
turns the outputs off for 20 seconds, as an idle daemon would, then checks that
output once it has disconnected and come back; it fails if the output never
disconnects. `--appearance`
repeats the check with every bar background (`opaque`, `glassy`, `none`) with
the desktop wallpaper enabled and disabled, then restores both settings.
Changing the background reloads Hyprland when the glassy blur toggles.

When working on a local copy, install it and restart the shell, because plugin
hot-reload can retain cached QML:

```sh
rsync -a --delete-excluded --include=manifest.json --include=Bar.qml --include=LICENSE \
  --exclude='*' ./ ~/.config/omarchy/plugins/io.github.kuroge.topbar-plus/
omarchy restart shell
```

## Credits and license

Top Bar Plus started from [Omarchy Top Bar Peek](https://github.com/WhiteHades/omarchy-topbar-peek)
by WhiteHades, whose history this repository keeps. The screenshots and demo in
`media/` and `preview.png` come from that project.
[ericvrp's autohide plugin](https://github.com/ericvrp/omarchy-bar-autohide)
was a reference for the original edge trigger and hover observer.

Released under the [MIT License](LICENSE), keeping the original copyright notices.
