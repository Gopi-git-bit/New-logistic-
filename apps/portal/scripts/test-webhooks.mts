/**
 * Dependency-free test runner (mirrors razorpay.test.ts) executed via
 *   node --experimental-strip-types scripts/test-webhooks.mts
 */
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { buildEnriched, classifyRazorpayEvent, verifyRazorpaySignature } from "../src/lib/webhooks/razorpay.ts";

const SECRET = "whsec_test_m4";
let passed = 0;

function t(name: string, fn: () => void) {
  try {
    fn();
    passed++;
    console.log("PASS", name);
  } catch (e) {
    console.error("FAIL", name, String(e));
    process.exitCode = 1;
  }
}

const signed = (body: string, secret = SECRET) => ({
  body,
  sig: crypto.createHmac("sha256", secret).update(body).digest("hex"),
});

t("accepts valid signature", () => {
  const { body, sig } = signed('{"id":"evt_1"}');
  assert.equal(verifyRazorpaySignature(body, sig, SECRET), true);
});
t("rejects tampered body", () => {
  const { sig } = signed('{"id":"evt_1"}');
  assert.equal(verifyRazorpaySignature('{"id":"evt_2"}', sig, SECRET), false);
});
t("rejects wrong secret", () => {
  const { body, sig } = signed('{"id":"evt_1"}', "other");
  assert.equal(verifyRazorpaySignature(body, sig, SECRET), false);
});
t("rejects empty signature", () => {
  assert.equal(verifyRazorpaySignature('{"id":"e"}', "", SECRET), false);
});

t("classifies known events", () => {
  assert.equal(classifyRazorpayEvent("payment.captured"), "payment.captured");
  assert.equal(classifyRazorpayEvent("payment.failed"), "payment.failed");
  assert.equal(classifyRazorpayEvent("refund.processed"), "refund.processed");
});
t("classifies unknown safely", () => {
  assert.equal(classifyRazorpayEvent("weird.thing"), "unknown");
  assert.equal(classifyRazorpayEvent(undefined), "unknown");
});

t("buildEnriched extracts key/payment id", () => {
  const e = buildEnriched(
    JSON.stringify({ id: "evt_ABC123", event: "payment.captured",
      payload: { payment: { entity: { id: "pay_X" } } } }),
  )!;
  assert.equal(e.idempotencyKey, "rzp:evt_ABC123");
  assert.equal(e.eventType, "payment.captured");
  assert.equal(e.payload.payment_id, "pay_X");
});
t("buildEnriched nulls bad input", () => {
  assert.equal(buildEnriched("{not json"), null);
  assert.equal(buildEnriched(JSON.stringify({ event: "x" })), null);
});

console.log(`\n${passed}/8 webhook util tests passed`);
