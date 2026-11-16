import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { validateJoinReturnPath, loginDestination, registrationLoginState } from "../src/utils/joinReturn.js";

const code = "A".repeat(32);
const join = `/join/${code}`;

test("accepts only the exact opaque-code join path", () => {
  assert.equal(validateJoinReturnPath(join), join);
  assert.equal(validateJoinReturnPath(`/join/${"a_-9".repeat(8)}`), `/join/${"a_-9".repeat(8)}`);
  for (const candidate of [null, {}, "https://evil.example/join/" + code, "//evil.example/join/" + code,
    `/join/${code}?next=/admin`, `/join/${code}#section`, `/join/${code}/`, `/join/${code}/extra`,
    `/join/%41${"A".repeat(31)}`, `/%6aoin/${code}`, `/join/${"A".repeat(31)}`,
    `/join/${code}%2f%2fevil.example`, `/join/${code}\n`, `\\evil.example\\join\\${code}`,
    `/JOIN/${code}`]) assert.equal(validateJoinReturnPath(candidate), null, String(candidate));
});

test("only an active Customer returns to join after login", () => {
  assert.equal(loginDestination({ platform_role: "customer", account_status: "active" }, join), join);
  assert.equal(loginDestination({ platform_role: "customer", account_status: "active" }, "//evil.example"), "/customer/dashboard");
  assert.equal(loginDestination({ platform_role: "shop_owner", account_status: "active" }, join), "/shop-owner/dashboard");
  assert.equal(loginDestination({ platform_role: "customer", account_status: "suspended" }, join), "/customer/dashboard");
  assert.equal(loginDestination({ platform_role: "customer", account_status: "active" }, null), "/customer/dashboard");
});

test("Customer registration carries only validated state to login", () => {
  const state = registrationLoginState("customer", join);
  assert.deepEqual(state, { registrationSuccess: true, joinReturnTo: join });
  assert.equal(loginDestination({ platform_role: "customer", account_status: "active" }, state.joinReturnTo), join);
  assert.deepEqual(registrationLoginState("customer", "https://evil.example"), { registrationSuccess: true });
  assert.deepEqual(registrationLoginState("driver", join), { registrationSuccess: true });
});

test("auth pages transport router state while join remains an explicit action", async () => {
  const files = await Promise.all([
    "../src/pages/customer/JoinShop.jsx",
    "../src/pages/auth/LoginPage.jsx",
    "../src/pages/auth/LoginForm.jsx",
    "../src/pages/auth/RegisterPage.jsx",
    "../src/pages/auth/RegistrationForm.jsx",
  ].map(path => readFile(new URL(path, import.meta.url), "utf8")));
  const [joinPage, loginPage, loginForm, registerPage, registrationForm] = files;
  assert.match(joinPage, /to="\/login" state=\{safeJoinReturnTo \? \{ joinReturnTo: safeJoinReturnTo \}/);
  assert.match(joinPage, /to="\/register\/customer" state=\{safeJoinReturnTo \? \{ joinReturnTo: safeJoinReturnTo \}/);
  assert.match(loginPage, /loginDestination\(user, joinReturnTo\)/);
  assert.match(loginForm, /to=\{safeJoinReturnTo \? "\/register\/customer" : "\/register"\}/);
  assert.match(registerPage, /registrationLoginState\(role, joinReturnTo\)/);
  assert.match(registrationForm, /state=\{safeJoinReturnTo \? \{ joinReturnTo: safeJoinReturnTo \}/);
  assert.match(joinPage, /onClick=\{onSubmit\}>\{acting \? "Updating request\.\.\." : "Request to Join"\}/);
  assert.match(joinPage, /getCustomerJoinRequestByCode\(publicCode\)/);
  assert.doesNotMatch(loginPage + loginForm + registerPage + registrationForm, /requestToJoinShop|submitJoinRequest/);
});
