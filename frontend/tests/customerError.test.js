import { test } from "node:test";
import assert from "node:assert/strict";
import { customerErrorMessage } from "../src/utils/customerError.js";

const response = (status, detail) => ({ response: { status, data: { detail } } });
for (const [status, expected] of [[401, /sign in again/], [403, /role and business approval/], [404, /not found/]]) {
  test(`safe guidance for HTTP ${status}`, () => {
    const message = customerErrorMessage(response(status, "private diagnostic"));
    assert.match(message, expected);
    assert.ok(!message.includes("private diagnostic"));
  });
}
test("duplicate and debt conflicts stay actionable", () => {
  assert.equal(customerErrorMessage(response(409, "Credit limit cannot be below outstanding debt")), "Credit limit cannot be below outstanding debt");
});
test("validation details identify the field", () => {
  assert.equal(customerErrorMessage(response(422, [{ loc: ["body", "phone"], msg: "Invalid mobile number" }])), "phone: Invalid mobile number");
});
for (const detail of [null, {}, [{ loc: null }], [null]]) {
  test(`malformed validation error ${JSON.stringify(detail)} is safe`, () => {
    assert.match(customerErrorMessage(response(422, detail)), /Check your entries/);
  });
}
for (const status of [500, 502, 503]) {
  test(`HTTP ${status} diagnostics are not exposed`, () => {
    const message = customerErrorMessage(response(status, "SQL password=private-diagnostic"));
    assert.ok(!message.includes("private-diagnostic"));
    assert.match(message, /Refresh customer data/);
  });
}
test("network failures explain uncertain save status", () => {
  assert.match(customerErrorMessage(new Error("network failure")), /Unable to confirm changes/);
  assert.match(customerErrorMessage(undefined), /Unable to confirm changes/);
});
