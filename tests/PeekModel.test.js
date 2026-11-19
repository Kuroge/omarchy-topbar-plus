const test = require("node:test")
const assert = require("node:assert/strict")
const model = require("../PeekModel.js")

const TAG = "no-bar-peek"

function client(fullscreen, tags, workspace = 3) {
  return { fullscreen, tags, workspace: { id: workspace, name: String(workspace) } }
}

test("a tag from a rule or set by hand both count", () => {
  assert.ok(model.hasTag(["no-bar-peek*"], TAG))
  assert.ok(model.hasTag(["terminal*", "no-bar-peek"], TAG))
  assert.ok(!model.hasTag(["no-bar-peek-other"], TAG))
  assert.ok(!model.hasTag(undefined, TAG))
})

test("only a fullscreen or maximized tagged client suppresses the peek", () => {
  assert.ok(model.suppressesPeek(client(2, [TAG]), TAG))
  assert.ok(model.suppressesPeek(client(1, [TAG + "*"]), TAG))
  assert.ok(!model.suppressesPeek(client(0, [TAG]), TAG))
  assert.ok(!model.suppressesPeek(client(2, ["terminal*"]), TAG))
  assert.ok(!model.suppressesPeek({ fullscreen: 2, tags: [TAG] }, TAG))
  assert.ok(!model.suppressesPeek({ tags: [TAG], workspace: { id: 1 } }, TAG))
  assert.ok(!model.suppressesPeek(null, TAG))
})

test("suppressed workspaces are sorted and unique", () => {
  const clients = [
    client(2, [TAG], 12), client(1, [TAG], 3), client(1, [TAG + "*"], 3),
    client(0, [TAG], 5), client(2, [], 7),
  ]
  assert.deepEqual(model.suppressedWorkspaces(clients, TAG), [3, 12])
  assert.deepEqual(model.suppressedWorkspaces([], TAG), [])
  assert.deepEqual(model.suppressedWorkspaces(null, TAG), [])
})

test("workspace lists compare by content", () => {
  assert.ok(model.sameIds([1, 11], [1, 11]))
  assert.ok(!model.sameIds([1], [1, 11]))
  assert.ok(!model.sameIds([11, 1], [1, 11]))
  assert.ok(model.sameIds([], []))
})

test("the pointer is on the bar only within its slid-in strip", () => {
  const screen = { x: 1920, y: 0, width: 2560 }
  assert.ok(model.pointerOnBar({ x: 2000, y: 0 }, screen, 26, 0))
  assert.ok(model.pointerOnBar({ x: 2000, y: 25 }, screen, 26, 0))
  assert.ok(!model.pointerOnBar({ x: 2000, y: 26 }, screen, 26, 0))
  assert.ok(!model.pointerOnBar({ x: 2000, y: 10 }, screen, 26, -20))
  assert.ok(!model.pointerOnBar({ x: 100, y: 0 }, screen, 26, 0))
})

test("layer and exclusion names fall back to the raw value", () => {
  assert.equal(model.layerName(3), "overlay")
  assert.equal(model.layerName(9), "9")
  assert.equal(model.exclusionName(1), "ignore")
})
