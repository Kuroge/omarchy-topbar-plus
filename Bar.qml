import QtQuick
import Quickshell
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

  Component.onCompleted: Qt.callLater(findBarPanels)
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

  // Read native tray state for the live interaction regression check.
  function trayState(window) {
    function find(item) {
      if (item.moduleName === "omarchy.tray" && "drawerExtent" in item) return item
      for (const child of item.children || []) {
        const found = find(child)
        if (found) return found
      }
      return null
    }
    const tray = find(window.contentItem)
    if (!tray) return null
    const point = tray.mapToItem(window.contentItem, 0, 0)
    return { x: point.x, y: point.y, height: tray.height,
      slot: tray.trayItemExtent, extent: tray.drawerExtent,
      expanded: tray.expanded, progress: tray.revealProgress,
      manageOpen: tray.managePopupOpen }
  }

  IpcHandler {
    target: "topbar-plus"
    function status(): string {
      return JSON.stringify({ hidden: root.barHidden, position: root.position, debug: root.debug,
        screens: peekControllers.instances.map(p => ({
          name: p.modelData.screen.name, revealed: p.revealed,
          held: p.held, offset: p.offset, hover: p.hoverState,
          engaged: p.engaged, thickness: p.thickness, margin: p.modelData.margins.top,
          layer: root.layerName(p.modelData.WlrLayershell.layer),
          tray: root.trayState(p.modelData)
        })) })
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
        readonly property var hoverState: ({ bar: barHover.hovered, edge: edgeHover.hovered, catching: edge.catching })
        readonly property bool held: barHover.hovered || (edge.catching && edgeHover.hovered)
          || (root.activePopout !== null && root.targetBelongsToWindow(root.activePopout, modelData))
          || root.barDragWindow === modelData || root.barMoveWindow === modelData
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
          if (Style.duration(140) <= 0) {
            offset = target
            settle()
            return
          }
          slide.to = target
          slide.start()
        }

        function settle() {
          if (!revealed) engaged = false
        }

        function park() {
          slide.stop()
          engaged = false
          offset = -thickness
        }

        onRevealedChanged: {
          root.log(screenName + " revealed=" + revealed + " reason=" + revealReason)
          if (!root.barHidden || !enabledHere) return
          if (revealed && !engaged) {
            offset = -thickness
            engaged = true
          }
          slideTo(revealed ? 0 : -thickness)
        }
        onEngagedChanged: root.log(screenName + " placement=" + (engaged ? "peek" : "native"))
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

        HoverHandler {
          id: barHover
          // Observe from an ancestor. A sibling overlay suppresses native
          // widget hover handlers, including the tray drawer, even if passive.
          parent: peek.modelData.contentItem
          blocking: false
          onHoveredChanged: if (hovered && root.barHidden && peek.enabledHere) peek.setRevealed(true, "bar")
        }

        Timer {
          interval: 120
          running: peek.revealed && !peek.held
          onTriggered: if (!peek.held) peek.setRevealed(false, "timer")
        }

        PanelWindow {
          id: edge
          readonly property bool catching: visible && (!peek.revealed || !barHover.hovered)
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
            onHoveredChanged: if (hovered) peek.setRevealed(true, "edge")
          }
        }
      }
    }
  }
}
