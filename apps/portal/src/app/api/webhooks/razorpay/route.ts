import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { buildEnriched, verifyRazorpaySignature } from "@/lib/webhooks/razorpay";

export const runtime = "nodejs";

/**
 * Razorpay webhook ingress (D-08: must be publicly reachable).
 * Contract:
 *  - 401 on bad signature / malformed body
 *  - 200 duplicate   -> idempotent no-op (unique dedupe key)
 *  - 200 accepted    -> task enqueued for payment_settlement agent
 * Processing failures after ACK are handled by the WF-5 dead-letter sweeper.
 */
export async function POST(req: NextRequest) {
  const raw = await req.text();
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET;
  if (!secret) return NextResponse.json({ error: "webhook not configured" }, { status: 500 });

  const sig = req.headers.get("x-razorpay-signature") ?? "";
  if (!verifyRazorpaySignature(raw, sig, secret)) {
    return NextResponse.json({ error: "invalid signature" }, { status: 401 });
  }

  const enriched = buildEnriched(raw);
  if (!enriched) {
    return NextResponse.json({ error: "malformed payload" }, { status: 401 });
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  const db = createClient(url, serviceKey, { auth: { persistSession: false } });

  // Idempotent record of delivery
  const ins = await db
    .from("webhook_events")
    .insert({
      provider: enriched.provider,
      event_type: enriched.eventType,
      payload: enriched.payload,
      idempotency_key: enriched.idempotencyKey,
    })
    .select("id")
    .single();

  if (ins.error) {
    const code = (ins.error as { code?: string }).code;
    if (code === "23505") {
      return NextResponse.json({ ok: true, duplicate: true }); // replay → noop
    }
    return NextResponse.json({ error: "storage failed" }, { status: 500 });
  }

  // Enqueue deterministic follow-up work; errors here surface via sweeper
  const enq = await db.rpc("enqueue_agent_task", {
    p_agent_name: "payment_settlement",
    p_task_type: `razorpay_${enriched.eventType}`,
    p_payload: enriched.payload,
    p_dedupe_key: enriched.idempotencyKey + ":task",
  });

  return NextResponse.json({
    ok: true,
    event_id: ins.data?.id ?? null,
    task_enqueued: !enq.error && enq.data != null,
  });
}
