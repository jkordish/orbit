import assert from "node:assert/strict";
import test from "node:test";
import { greet } from "./main.js";

test("greets a name", () => {
  assert.equal(greet("Mac"), "Hello, Mac!");
});
