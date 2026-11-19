import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.plugins.bar as Native
import qs.Ui

// Inherit the installed bar: widgets, theme, popouts, IPC and hidden-state IO
// stay Omarchy-owned. Only the top-edge window placement changes.
Native.Bar {
  id: root

  // BarPanel is an inline component in the native bar. Its Variants expose
  // the windows without copying the bar or reaching into the shell host.
  property var nativeBarVariants: null
  readonly property var peekWindows: nativeBarVariants ? nativeBarVariants.instances : []

  property bool debug: false

  function log(message) {
    if (debug) console.log("[topbar-plus] " + message)
  }

  function layerName(layer) {
    return ["background", "bottom", "top", "overlay"][layer] ?? String(layer)
  }

  function exclusionName(mode) {
    return ["normal", "ignore", "auto"][mode] ?? String(mode)
  }

  function screenNames(windows) {
    return Array.from(windows || [], w => w && w.screen ? w.screen.name : "?").join(", ")
  }

  function findBarPanels() {
    for (const child of root.data) {
      if (child === peekControllers) continue
      if (!("instances" in child)) continue
      for (const instance of child.instances) {
        if (instance && "contentItem" in instance && "screen" in instance
            && !("ghostScreen" in instance)) {
          nativeBarVariants = child
          log("bar panels found: " + screenNames(child.instances))
          return
        }
      }
    }
    log("bar panels not found")
  }

  // Windows with this Hyprland tag draw their own top-edge bar while fullscreen
  // or maximized, so the bar leaves that edge to them.
  readonly property string peekSuppressingTag: "no-bar-peek"

  // Workspaces holding a fullscreen or maximized window with that tag.
  property var suppressedWorkspaces: []
  property bool clientsQueryPending: false

  function suppressesPeek(client) {
    if (!client || !client.workspace || !(Number(client.fullscreen) > 0)) return false
    // Tags set by a window rule carry a trailing asterisk.
    return Array.from(client.tags || []).some(tag => tag === peekSuppressingTag || tag === peekSuppressingTag + "*")
  }

  // Ask Hyprland itself. Quickshell's toplevel list never drops a window whose
  // refresh answer arrives after it closed, so a closed fullscreen window can
  // linger there with its old state until the shell restarts.
  function queryClients() {
    if (clientsQuery.running) clientsQueryPending = true
    else clientsQuery.running = true
  }

  Process {
    id: clientsQuery
    command: ["hyprctl", "clients", "-j"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          const ids = JSON.parse(text).filter(c => root.suppressesPeek(c)).map(c => c.workspace.id)
          ids.sort((a, b) => a - b)
          if (JSON.stringify(ids) !== JSON.stringify(root.suppressedWorkspaces)) {
            root.suppressedWorkspaces = ids
            root.log("suppressed workspaces: [" + ids.join(", ") + "]")
          }
        } catch (error) {
          root.log("clients query failed: " + error)
        }
      }
    }
    onExited: (code, status) => {
      if (!root.clientsQueryPending) return
      root.clientsQueryPending = false
      Qt.callLater(root.queryClients)
    }
  }

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      const name = event ? String(event.name) : ""
      if (["fullscreen", "openwindow", "closewindow", "movewindowv2", "workspacev2",
           "monitoraddedv2", "configreloaded"].includes(name))
        root.queryClients()
    }
  }

  Component.onCompleted: {
    Qt.callLater(findBarPanels)
    queryClients()
  }
  Connections {
    target: Quickshell
    function onScreensChanged() {
      root.log("screens changed: " + Array.from(Quickshell.screens, s => s.name).join(", "))
      Qt.callLater(root.findBarPanels)
    }
  }

  Connections {
    target: root
    function onBarHiddenChanged() { root.log("barHidden=" + root.barHidden) }
    function onActivePopoutChanged() { root.log("activePopout=" + (root.activePopout ? String(root.activePopout) : "none")) }
  }

  // Read native widget geometry and tray state for the live regression check.
  function moduleRect(window, moduleName) {
    function find(item) {
      if (item.moduleName === moduleName) return item
      for (const child of item.children || []) {
        const found = find(child)
        if (found) return found
      }
      return null
    }
    const item = find(window.contentItem)
    if (!item) return null
    const point = item.mapToItem(window.contentItem, 0, 0)
    return { x: point.x, y: point.y, w: item.width, h: item.height }
  }

  function trayState(window) {
    function find(item) {
      if (item.moduleName === "omarchy.tray" && "drawerExtent" in item) return item
      for (const child of item.children || []) {
        const found = find(child)
        if (found) return found
      }
      return null
    }
    function findChevron(item) {
      if ("bar" in item && (item.text === "" || item.text === "")) return item
      for (const child of item.children || []) {
        const found = findChevron(child)
        if (found) return found
      }
      return null
    }
    const tray = find(window.contentItem)
    if (!tray) return null
    const point = tray.mapToItem(window.contentItem, 0, 0)
    const chevron = findChevron(tray)
    const chevronPoint = chevron ? chevron.mapToItem(window.contentItem, 0, 0) : null
    return { x: point.x, y: point.y, height: tray.height,
      slot: tray.trayItemExtent, extent: tray.drawerExtent,
      fixedAtStart: tray.fixedAtStart,
      chevron: chevron ? { x: chevronPoint.x, y: chevronPoint.y, w: chevron.width, h: chevron.height } : null,
      expanded: tray.expanded, progress: tray.revealProgress,
      manageOpen: tray.managePopupOpen }
  }

  IpcHandler {
    target: "topbar-plus"
    function status(): string {
      return JSON.stringify({ hidden: root.barHidden, position: root.position, debug: root.debug,
        suppressedWorkspaces: root.suppressedWorkspaces,
        popout: root.activePopout !== null,
        screens: peekControllers.instances.map(p => ({
          name: p.modelData.screen.name, revealed: p.revealed,
          held: p.held, offset: p.offset, hover: p.hoverState,
          engaged: p.engaged, thickness: p.thickness, margin: p.modelData.margins.top,
          underFullscreen: p.modelData.underFullscreen === true, fullscreenInput: p.fullscreenInput,
          suppressed: p.suppressed,
          exclusionMode: root.exclusionName(p.modelData.exclusionMode),
          popout: root.activePopout !== null && root.targetBelongsToWindow(root.activePopout, p.modelData),
          layer: root.layerName(p.modelData.WlrLayershell.layer),
          hides: p.hideCount, clock: root.moduleRect(p.modelData, "omarchy.clock"),
          tray: root.trayState(p.modelData)
        })) })
    }
    function probe(): string {
      for (const p of peekControllers.instances) p.probeLeave("ipc")
      return "probing " + peekControllers.instances.length
    }
    function nudge(): string {
      for (const p of peekControllers.instances) p.nudgePointer("ipc")
      return "nudging " + peekControllers.instances.length
    }
    function setDebug(enabled: bool): string {
      root.debug = enabled
      root.log("debug enabled; panels: " + root.screenNames(root.peekWindows))
      return enabled ? "debug on" : "debug off"
    }
  }

  Variants {
    id: peekControllers
    model: root.peekWindows

    delegate: Component {
      Item {
        id: peek
        required property var modelData
        readonly property string screenName: modelData && modelData.screen ? modelData.screen.name : "?"
        property bool ready: false
        Component.onCompleted: {
          Qt.callLater(() => ready = true)
          root.log(screenName + " controller created")
        }
        Component.onDestruction: root.log(screenName + " controller destroyed")
        readonly property bool enabledHere: root.position === "top"
        property bool revealed: false
        property string revealReason: ""
        property int hideCount: 0
        // Hover handlers are gone first while a controller is destroyed.
        readonly property bool barHovered: barHover ? barHover.hovered : false
        readonly property bool edgeHovered: edgeHover ? edgeHover.hovered : false
        readonly property var hoverState: ({ bar: barHovered, edge: edgeHovered, catching: edge ? edge.catching : false })
        readonly property bool popoutHere: root.activePopout !== null
          && root.targetBelongsToWindow(root.activePopout, modelData)
        // Sliding in, the bar is still on its way under a pointer that left the edge.
        property bool slidingIn: false
        readonly property bool held: barHovered || (!!edge && edge.catching && edgeHovered)
          || popoutHere || slidingIn || popoutGrace.running
          || root.barDragWindow === modelData || root.barMoveWindow === modelData
        readonly property bool suppressed: {
          const monitor = modelData && modelData.screen ? Hyprland.monitorFor(modelData.screen) : null
          const workspace = monitor ? monitor.activeWorkspace : null
          return !!workspace && root.suppressedWorkspaces.includes(workspace.id)
        }
        onSuppressedChanged: {
          root.log(screenName + " suppressed=" + suppressed)
          if (suppressed) setRevealed(false, "suppressed")
        }
        readonly property int thickness: modelData && "thickness" in modelData ? modelData.thickness : root.barSize
        // While engaged this controller owns the bar's margin and layer. At rest
        // the native BarPanel parks its full-screen surface off screen on its
        // usual layer, so no transparent overlay stays above the windows.
        property bool engaged: false
        property real offset: -thickness

        function setRevealed(value, reason) {
          if (revealed === value) return
          revealReason = reason
          revealed = value
        }

        function slideTo(target) {
          slide.stop()
          slidingIn = target === 0
          if (Style.duration(140) <= 0) {
            offset = target
            settle()
            return
          }
          slide.to = target
          slide.start()
        }

        function settle() {
          slidingIn = false
          if (!revealed) engaged = false
          else if (!barHovered && !edgeHovered) nudgePointer("slide-in ended")
        }

        function park() {
          slide.stop()
          slidingIn = false
          engaged = false
          offset = -thickness
        }

        onRevealedChanged: {
          root.log(screenName + " revealed=" + revealed + " reason=" + revealReason)
          if (!revealed) hideCount++
          if (!root.barHidden || !enabledHere) return
          if (revealed && !engaged) {
            offset = -thickness
            engaged = true
          }
          slideTo(revealed ? 0 : -thickness)
        }
        onEngagedChanged: root.log(screenName + " placement=" + (engaged ? "peek" : "native"))

        // Hyprland tells a surface that moved under a resting pointer, or that
        // a closed popout uncovered, only on the next motion. Warping the
        // pointer onto its own position makes it pick the surface again, so the
        // bar learns it is hovered instead of hiding and bouncing back.
        Process {
          id: pointerNudge
          onExited: (code, status) => root.log(peek.screenName + " nudge exited code=" + code)
          command: ["hyprctl", "eval",
            "local p = hl.get_cursor_pos(); if p then hl.dispatch(hl.dsp.cursor.move({ x = p.x, y = p.y })) end"]
        }

        function nudgePointer(reason) {
          root.log(screenName + " pointer nudge: " + reason)
          if (!pointerNudge.running) pointerNudge.running = true
        }

        // A closed popout's full-screen layer stays mapped, taking the pointer,
        // while its card fades out. Hold the bar until it is gone, then nudge.
        Timer {
          id: popoutGrace
          interval: Style.duration(120) + 80
          onTriggered: {
            if (peek.revealed && peek.engaged && !peek.barHovered) peek.nudgePointer("popout closed")
          }
        }

        onPopoutHereChanged: {
          if (popoutHere) popoutGrace.stop()
          else if (revealed && engaged) popoutGrace.restart()
        }
        onHeldChanged: {
          if (!root.debug) return
          root.log(screenName + " held=" + held
            + " bar=" + (barHover ? barHover.hovered : null)
            + " edge=" + (edgeHover ? edgeHover.hovered : null)
            + " catching=" + (edge ? edge.catching : null)
            + " popout=" + (root.activePopout !== null))
        }

        NumberAnimation {
          id: slide
          target: peek
          property: "offset"
          // Same duration and easing as Omarchy's PopupCard.
          duration: Style.duration(140)
          easing.type: Easing.OutCubic
          onFinished: peek.settle()
        }

        Connections {
          target: root
          function onBarHiddenChanged() {
            peek.setRevealed(false, "barHidden")
            peek.park()
          }
          function onPositionChanged() {
            peek.setRevealed(false, "position")
            peek.park()
          }
        }

        Connections {
          target: peek.modelData
          ignoreUnknownSignals: true
          function onUnderFullscreenChanged() { root.log(peek.screenName + " underFullscreen=" + peek.modelData.underFullscreen) }
          function onExclusionModeChanged() { root.log(peek.screenName + " exclusionMode=" + root.exclusionName(peek.modelData.exclusionMode)) }
        }

        Connections {
          target: peek.modelData ? peek.modelData.WlrLayershell : null
          ignoreUnknownSignals: true
          function onLayerChanged() { root.log(peek.screenName + " layer=" + root.layerName(peek.modelData.WlrLayershell.layer)) }
        }

        Binding {
          target: peek.modelData
          property: "margins.top"
          value: Math.round(peek.offset)
          when: peek.ready && peek.enabledHere && root.barHidden && peek.engaged
          restoreMode: Binding.RestoreBindingOrValue
        }

        Binding {
          target: peek.modelData.WlrLayershell
          property: "layer"
          value: WlrLayer.Overlay
          when: peek.ready && peek.enabledHere && root.barHidden && peek.engaged
          restoreMode: Binding.RestoreBindingOrValue
        }

        // A hidden bar reserves no space. A panel recreated for a monitor that
        // reconnected can keep the normal exclusion mode while hidden, which
        // pushes tiled windows down whenever the bar peeks.
        Binding {
          target: peek.modelData
          property: "exclusionMode"
          value: ExclusionMode.Ignore
          when: peek.ready && peek.enabledHere && root.barHidden
          restoreMode: Binding.RestoreBindingOrValue
        }

        // Under a fullscreen window the native bar takes no input, so its
        // invisible strip cannot steal clicks from the window. While peeking it
        // is visible on the overlay layer, so give the strip its input back.
        readonly property bool fullscreenInput: ready && enabledHere && root.barHidden && engaged
          && modelData.underFullscreen === true && modelData.dragActive !== true && !suppressed
        onFullscreenInputChanged: root.log(screenName + " mask=" + (fullscreenInput ? "peek" : "native"))

        Region {
          id: peekInputRegion
          width: peek.modelData ? peek.modelData.width : 0
          height: peek.thickness
        }

        Binding {
          target: peek.modelData
          property: "mask"
          value: peekInputRegion
          when: peek.fullscreenInput
          restoreMode: Binding.RestoreBindingOrValue
        }

        HoverHandler {
          id: barHover
          // Observe from an ancestor. A sibling overlay suppresses native
          // widget hover handlers, including the tray drawer, even if passive.
          parent: peek.modelData.contentItem
          blocking: false
          onHoveredChanged: {
            if (hovered && root.barHidden && peek.enabledHere && !peek.suppressed) peek.setRevealed(true, "bar")
            if (!hovered && peek.engaged) peek.probeLeave("leave")
          }
        }

        function probeLeave(reason) {
          if (!root.debug) return
          root.log(screenName + " probe start: " + reason + " running=" + leaveProbe.running)
          if (!leaveProbe.running) leaveProbe.running = true
        }

        // Debug only: where the pointer really is when the bar reports a leave.
        Process {
          id: leaveProbe
          onExited: (code, status) => root.log(peek.screenName + " probe exited code=" + code)
          command: ["hyprctl", "cursorpos", "-j"]
          stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
              let inside = "?"
              try {
                const p = JSON.parse(text)
                const screen = peek.modelData.screen
                inside = p.x >= screen.x && p.x < screen.x + screen.width
                  && p.y >= screen.y && p.y < screen.y + peek.thickness + Math.round(peek.offset)
              } catch (error) {}
              root.log(peek.screenName + " bar leave: cursor=" + text.replace(/\s+/g, "") + " insideBar=" + inside
                + " offset=" + Math.round(peek.offset) + " tooltip=" + root.tooltipShown
                + " popout=" + (root.activePopout !== null))
            }
          }
        }

        Timer {
          interval: 120
          running: peek.revealed && !peek.held
          onTriggered: if (!peek.held) peek.setRevealed(false, "timer")
        }

        PanelWindow {
          id: edge
          // While suppressed the edge stays mapped but takes no input, so the
          // pointer reaches the window's own bar whatever the overlay order.
          readonly property bool catching: visible && !peek.suppressed && (!peek.revealed || !peek.barHovered)
          onCatchingChanged: root.log(peek.screenName + " edge catching=" + catching)
          onVisibleChanged: root.log(peek.screenName + " edge visible=" + visible)
          screen: peek.modelData.screen
          visible: peek.ready && peek.enabledHere && root.barHidden && !edgeRemap.remapping
          color: "transparent"
          implicitHeight: 2
          anchors { top: true; left: true; right: true }
          exclusionMode: ExclusionMode.Ignore
          // Hand input back after the pointer enters the bar. Clearing the
          // mask at animation end alone may not generate a new pointer enter.
          mask: Region { width: edge.catching ? edge.width : 0; height: 2 }
          WlrLayershell.namespace: "omarchy-topbar-plus-edge"
          WlrLayershell.layer: WlrLayer.Overlay
          WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

          ScreenMoveRemap { id: edgeRemap; window: edge }

          HoverHandler {
            id: edgeHover
            onHoveredChanged: if (hovered && !peek.suppressed) peek.setRevealed(true, "edge")
          }
        }
      }
    }
  }
}
