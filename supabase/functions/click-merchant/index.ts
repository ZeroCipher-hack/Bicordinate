// Bicoordinate — Click Merchant API (Supabase Edge Function)
//
// Hujjat: https://click.uz/en/developers/
// Metodi: POST form-data
// Action: 0=prepare, 1=complete
// Imzo: MD5(click_trans_id + CLICK_SECRET + sign_time + [merchant_prepare_id] + amount + action + merchant_trans_id)
// Javoblar: merchant_prepare_id (prepare), merchant_confirm_id (complete)
// Xato: -4 (not found), -9 (invalid)

import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import md5 from "npm:md5@2.3.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const CLICK_SECRET = Deno.env.get("CLICK_SECRET") ?? "";

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function clickReply(data: Record<string, unknown>) {
  const resp: Record<string, unknown> = {
    success: true,
    error_code: 0,
    ...data,
  };
  return json(resp);
}

function clickError(code: number, msg: string) {
  return json({ success: false, error_code: code, error: msg });
}

// Click preparation state
const preparations = new Map<string, { merchant_prepare_id: string; merchant_trans_id: string; time: number }>();

// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const contentType = req.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/x-www-form-urlencoded")) {
    return json({ error: "bad_content_type" }, 400);
  }

  const formStr = await req.text();
  const params: Record<string, string> = {};
  new URLSearchParams(formStr).forEach((v, k) => {
    params[k] = v;
  });

  const click_trans_id = params.click_trans_id || "";
  const merchant_trans_id = params.merchant_trans_id || "";
  const merchant_prepare_id = params.merchant_prepare_id || "";
  const amount = params.amount || "0";
  const action = parseInt(params.action || "0");
  const sign_time = params.sign_time || "";
  const sign_string = params.sign_string || "";

  if (!click_trans_id || !merchant_trans_id || !amount || !sign_time) {
    return clickError(-9, "Invalid parameters");
  }

  // Prepare: action=0
  if (action === 0) {
    // Imzo tekshiruvi: MD5(click_trans_id + CLICK_SECRET + sign_time + merchant_trans_id)
    const msg = `${click_trans_id}${CLICK_SECRET}${sign_time}${merchant_trans_id}`;
    const expectedSign = md5(msg);

    if (sign_string !== expectedSign) {
      console.error("click_prepare_sign_mismatch", { click_trans_id, expectedSign, sign_string });
      return clickError(-9, "Sign mismatch");
    }

    // To'lovni tekshirish
    const { data: payment } = await db
      .from("payments")
      .select("id, amount_uzs, state")
      .eq("provider_txn_id", merchant_trans_id)
      .eq("provider", "click")
      .maybeSingle();

    if (!payment) {
      return clickError(-4, "Order not found");
    }

    const amountNum = parseFloat(amount) * 100; // to'iqlari
    if ((payment as any).amount_uzs !== amountNum) {
      return clickError(-9, "Amount mismatch");
    }

    // Preparation holatini saqlash (memory'da, yoki DB'da)
    const prep_id = `prep_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    preparations.set(merchant_trans_id, { merchant_prepare_id: prep_id, merchant_trans_id, time: Date.now() });

    return clickReply({ merchant_prepare_id: prep_id });
  }

  // Complete: action=1
  if (action === 1) {
    // Imzo tekshiruvi: MD5(click_trans_id + CLICK_SECRET + sign_time + merchant_prepare_id + amount + action + merchant_trans_id)
    const msg = `${click_trans_id}${CLICK_SECRET}${sign_time}${merchant_prepare_id}${amount}${action}${merchant_trans_id}`;
    const expectedSign = md5(msg);

    if (sign_string !== expectedSign) {
      console.error("click_complete_sign_mismatch", { click_trans_id, expectedSign, sign_string });
      return clickError(-9, "Sign mismatch");
    }

    // Preparation tekshiruvi
    const prep = preparations.get(merchant_trans_id);
    if (!prep || prep.merchant_prepare_id !== merchant_prepare_id) {
      return clickError(-9, "Preparation not found or mismatch");
    }

    // 30 daqiqaning ichida bo'lishi kerak
    if (Date.now() - prep.time > 30 * 60 * 1000) {
      preparations.delete(merchant_trans_id);
      return clickError(-9, "Preparation expired");
    }

    // To'lovni yangilash
    const { data: payment } = await db
      .from("payments")
      .select("id, amount_uzs, user_id, course_id, state")
      .eq("provider_txn_id", merchant_trans_id)
      .eq("provider", "click")
      .maybeSingle();

    if (!payment) {
      return clickError(-4, "Order not found");
    }

    const amountNum = parseFloat(amount) * 100;
    if ((payment as any).amount_uzs !== amountNum) {
      return clickError(-9, "Amount mismatch");
    }

    // Allaqachon to'langan bo'lsa
    if ((payment as any).state === 1) {
      return clickReply({ merchant_confirm_id: merchant_prepare_id }); // idempotent
    }

    // Update
    const { error: updateErr } = await db
      .from("payments")
      .update({ state: 1, status: "paid", paid_at: new Date().toISOString() })
      .eq("id", payment.id);

    if (updateErr) {
      console.error("click_complete_failed", updateErr);
      return clickError(-9, "Update failed");
    }

    // Enrollment
    if ((payment as any).course_id && (payment as any).user_id) {
      await db.from("enrollments").insert({
        student_id: (payment as any).user_id,
        course_id: (payment as any).course_id,
        payment_id: payment.id,
      }).select("id").maybeSingle();
    }

    preparations.delete(merchant_trans_id);
    return clickReply({ merchant_confirm_id: merchant_prepare_id });
  }

  return clickError(-9, "Invalid action");
});
