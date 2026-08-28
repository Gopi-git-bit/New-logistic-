/**
 * Razorpay webhook utilities (M4).
 * Pure functions — unit-tested with vitest.
 */

import crypto from "node:crypto";

/** Constant-time HMAC-SHA256 verification of `X-Razorpay-Signature`. */
export function verifyRazorpaySignature(
  rawBody: string,
  signature: string,
  secret: string
): boolean {
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(signature ?? "", "utf8");
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

export type RazorpayEvent =
  | "payment.authorized"
  | "payment.captured"
  | "payment.failed"
  | "refund.processed"
  | "unknown";

export function classifyRazorpayEvent(eventType: string | undefined): RazorpayEvent {
  switch (eventType) {
    case "payment.authorized":
    case "payment.captured":
      return eventType;
    case "payment.failed":
      return "payment.failed";
    case "refund.processed":
      return "refund.processed";
    default:
      return "unknown";
  }
}

export interface EnrichedWebhook {
  idempotencyKey: string;
  provider: string;
  eventType: RazorpayEvent;
  payload: Record<string, unknown>;
}

/** Shape an incoming request into what the dedupe/enqueue layer expects. */
export function buildEnriched(rawBody: string): EnrichedWebhook | null {
  let parsed: any;
  try {
    parsed = JSON.parse(rawBody);
  } catch {
    return null;
  }
  const eventId = typeof parsed?.id === "string" ? parsed.id : null; // razorpay event id
  if (!eventId) return null;

  const entity =
    typeof parsed?.payload?.payment?.entity === "object" ? parsed.payload.payment.entity : {};

  return {
    provider: "razorpay",
    eventType: classifyRazorpayEvent(parsed.event),
    idempotencyKey: `rzp:${eventId}`,
    payload: { event: parsed.event ?? null, payment_id: entity.id ?? null },
  };
}
