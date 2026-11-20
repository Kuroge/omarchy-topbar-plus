# Changelog

**English** · [Español](CHANGELOG.es.md)

All notable changes to Omarchy Top Bar Plus. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-11-20

First public release.

### Changed

- The peek suppression asks Hyprland for its windows only on window events,
  not on every workspace switch or monitor return.
- Restructured `Bar.qml` like the native bar: inline components for the
  per-screen peek, the edge trigger and the debug probe, and the pure logic in
  `PeekModel.js`.
- Debug-only log handlers do no work while debug logging is off.
- `check.py` runs named checks from one list, with `--only` and `--repeat`,
  and checks its prerequisites first, stopping with the fix for whatever is
  missing.
- README and changelog in English and Spanish, with an own logo, screenshot
  and demo.

### Added

- Unit tests for `PeekModel.js`: `node --test tests/`.
- `check.py --reconnect` keeps a tagged fullscreen window open across the
  reconnect.

### Fixed

- No `TypeError` in the shell log when the plugin is added, updated or reloaded.

### Removed

- The manual `probe` and `nudge` IPC calls. The automatic leave probe still
  logs while debug logging is on.
- The screenshots and demo inherited from Top Bar Peek.

## [0.2.1] - 2026-11-19

### Fixed

- A closed fullscreen window could linger in Quickshell's window list and keep
  the bar from peeking on its screen until the shell restarted. The suppression
  now comes from `hyprctl clients -j`.

## [0.2.0] - 2026-11-18

### Added

- Windows tagged `no-bar-peek` that are fullscreen or maximized keep the top
  edge for their own bar: the bar does not peek there, a peeking bar slides
  out, and the edge trigger takes no pointer input.

## [0.1.0] - 2026-11-18

First version as Top Bar Plus, adapted from Top Bar Peek to Omarchy 4.5.

### Added

- Own plugin id, `io.github.kuroge.topbar-plus`, so it can sit next to Top
  Bar Peek.
- `omarchy shell topbar-plus status` and opt-in debug logging with
  `setDebug`.

### Fixed

- No transparent full-screen overlay stays above the windows at rest: the
  native bar keeps its own placement and layer until the bar peeks.
- The bar takes input while peeking over a fullscreen window.
- No flicker on a fast entry from the edge, when resting against the edge or
  after closing a popout over the bar.
- No reserved space, and no windows pushed down, after a monitor reconnects.
- No error when a monitor's panel goes away.

[0.3.0]: https://github.com/Kuroge/omarchy-topbar-plus/releases/tag/v0.3.0
