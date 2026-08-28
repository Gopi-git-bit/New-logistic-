import { describe, expect, it } from "vitest";
import crypto from "node:crypto";
import {
  buildEnriched,
  classifyRazorpayEvent,
  verifyRazorpaySignature,
} from "./razorpay";

const SECRET = "whsec_test_m4";

function signed(body: string, secret = SECRET) {
  const sig = crypto.createHmac("sha256", secret).update(body).digest("hex");
  return { body, sig };
}

describe("verifyRazorpaySignature", () => {
  it("accepts a valid signature", () => {
    const { body, sig } = signed('{"id":"evt_1"}');
    expect(verifyRazorpaySignature(body, sig, SECRET)).toBe(true);
  });

  it("rejects tampered body", () => {
    const { sig } = signed('{"id":"evt_1"}');
    expect(verifyRazorpaySignature('{"id":"evt_2"}', sig, SECRET)).toBe(false);
  });

  it("rejects wrong secret", () => {
    const { body, sig } = signed('{"id":"evt_1"}', "other");
    expect(verifyRazorpaySignature(body, sig, SECRET)).toBe(false);
  });

  it("rejects empty signature", () => {
    expect(verifyRazorpaySignature('{"id":"e"}', "", SECRET)).toBe(false);
  });
});

describe("classifyRazorpayEvent", () => {
  it("maps known events", () => {
    expect(classifyRazorpayEvent("payment.captured")).toBe("payment.captured");
    expect(classifyRazorpayEvent("payment.failed")).toBe("payment.failed");
    expect(classifyRazorpayEvent("refund.processed")).toBe("refund.processed");
  });
  it("maps unknown safely", () => {
    expect(classifyRazorpayEvent("weird.thing")).toBe("unknown");
    expect(classifyRazorpayEvent(undefined)).toBe("unknown");
  });
});

describe("buildEnriched", () => {
  const valid = JSON.stringify({
    id: "evt_ABC123",
    event: "payment.captured",
    payload: { payment: { entity: { id: "pay_X" } } },
  });

  it("extracts idempotency key and payment id", () => {
    const e = buildEnriched(valid)!;
    expect(e.idempotencyKey).toBe("rzp:evt_ABC123");
    expect(e.eventType).toBe("payment.captured");
    expect(e.payload.payment_id).toBe("pay_X");
  });

  it("nulls malformed json / missing id", () => {
    expect(buildEnriched("{not json")).toBeNull();
    expect(buildEnriched(JSON.stringify({ event: "x" }))).toBeNull();
  });
});
