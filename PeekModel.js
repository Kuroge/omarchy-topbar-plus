// Pure peek logic, shared by Bar.qml and the node tests in tests/.

var layerNames = ["background", "bottom", "top", "overlay"]
var exclusionNames = ["normal", "ignore", "auto"]

function layerName(layer) {
  return layerNames[layer] ?? String(layer)
}

function exclusionName(mode) {
  return exclusionNames[mode] ?? String(mode)
}

// Tags set by a window rule carry a trailing asterisk.
function hasTag(tags, tag) {
  return Array.from(tags || []).some(t => t === tag || t === tag + "*")
}

// A fullscreen or maximized Hyprland client carrying the tag draws its own
// top-edge bar. `client` is an entry of `hyprctl clients -j`.
function suppressesPeek(client, tag) {
  return !!client && !!client.workspace && Number(client.fullscreen) > 0 && hasTag(client.tags, tag)
}

// Sorted, unique ids of the workspaces holding such a client.
function suppressedWorkspaces(clients, tag) {
  var ids = (clients || []).filter(c => suppressesPeek(c, tag)).map(c => c.workspace.id)
  return Array.from(new Set(ids)).sort((a, b) => a - b)
}

function sameIds(a, b) {
  return a.length === b.length && a.every((id, i) => id === b[i])
}

// Whether a global pointer position lies on a top bar slid to `offset`.
function pointerOnBar(cursor, screen, thickness, offset) {
  return cursor.x >= screen.x && cursor.x < screen.x + screen.width
    && cursor.y >= screen.y && cursor.y < screen.y + thickness + Math.round(offset)
}

if (typeof module !== "undefined") {
  module.exports = {
    layerName: layerName,
    exclusionName: exclusionName,
    hasTag: hasTag,
    suppressesPeek: suppressesPeek,
    suppressedWorkspaces: suppressedWorkspaces,
    sameIds: sameIds,
    pointerOnBar: pointerOnBar,
  }
}
