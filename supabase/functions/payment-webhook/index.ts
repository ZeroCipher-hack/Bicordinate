// Bicoordinate — Payme va Click to'lov webhook'lari (Supabase Edge Function)
//
// Payme: POST {"id":"...", "method":"CheckTransaction" | "ConfirmTransaction", ...}
//        Imzo: X-Auth header HMAC-SHA256(SECRET:body)
// Click: POST form data — merchant_trans_id, status, ...
//        Imzo: sign = MD5(click_trans_id + secret + sign_time + state + amount + action + merchant_trans_id)

import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import md5 from "npm:md5@2.3.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const PAYME_SECRET = Deno.env.get("PAYME_SECRET") ?? "";
const CLICK_SECRET = Deno.env.get("CLICK_SECRET") ?? "";

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

// ---------------------------------------------------------------------------
// Yordamchilar
// ---------------------------------------------------------------------------
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

async function sha256(secret: string, message: string): Promise<string> {
  const key = new TextEncoder().encode(secret);
  const msg = new TextEncoder().encode(message);
  const sig = await crypto.subtle.sign("HMAC", await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]), msg);
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function md5Hash(message: string): string {
  return md5(message);
}

// ---------------------------------------------------------------------------
// PAYME
// ---------------------------------------------------------------------------
type PaymeMethod = "CheckTransaction" | "ConfirmTransaction" | "GetStatement";
interface PaymeRequest {
  id?: string;
  jsonrpc?: string;
  method?: PaymeMethod;
  params?: {
    account?: { [key: string]: string };
    amount?: number;
    time?: number;
  };
}

async function handlePayme(body: PaymeRequest, auth: string): Promise<Response> {
  // 1) Imzo tekshiruvi
  const bodyStr = JSON.stringify(body);
  const expectedAuth = await sha256(PAYME_SECRET, bodyStr);
  if (auth !== expectedAuth) return json({ error: { code: -32504, message: "Invalid signature" } }, 401);

  const method = body.method ?? "";
  const params = body.params ?? {};
  const txnId = body.id ?? "";

  // Payme qaytarishi (JSON-RPC)
  function reply(result: unknown = {}) {
    return json({ jsonrpc: "2.0", id: body.id, result });
  }
  function err(code: number, msg: string) {
    return json({ jsonrpc: "2.0", id: body.id, error: { code, message: msg } });
  }

  if (!txnId) return err(-32700, "Invalid Request");

  // 2) CheckTransaction — to'lovni tekshirish
  if (method === "CheckTransaction") {
    const { data: payment } = await db.from("payments")
      .select("id, amount_uzs, course_id, user_id, status")
      .eq("provider_txn_id", txnId)
      .maybeSingle();

    if (!payment) return err(-31001, "Transaction not found");
    if (payment.status === "paid") return reply({ state: 4, type: "payment" }); // 4 = tugatilgan
    return reply({ state: 1, type: "payment" }); // 1 = pending
  }

  // 3) ConfirmTransaction — tasdiqlash (to'lov muvaffaqiyatli)
  if (method === "ConfirmTransaction") {
    const { data: payment, error: getErr } = await db.from("payments")
      .select("id, amount_uzs, course_id, user_id, status")
      .eq("provider_txn_id", txnId)
      .maybeSingle();

    if (getErr || !payment) return err(-31001, "Transaction not found");
    if (payment.status === "paid") return reply({ state: 4, type: "payment" });

    // Transaction'ni yozish
    const { error: updateErr } = await db.from("payments")
      .update({ status: "paid", paid_at: new Date().toISOString() })
      .eq("id", payment.id);

    if (updateErr) {
      console.error("payment_update_failed", updateErr);
      return err(-32500, "Server error");
    }

    // Yozilish yaratish (course_id bo'lsa)
    if (payment.course_id) {
      const { error: enrollErr } = await db.from("enrollments")
        .insert({ student_id: payment.user_id, course_id: payment.course_id, payment_id: payment.id })
        .select("id")
        .maybeSingle();

      if (enrollErr && !enrollErr.message.includes("duplicate")) {
        console.error("enrollment_failed", enrollErr);
        return err(-32500, "Server error");
      }
    }

    return reply({ state: 4, type: "payment" });
  }

  return err(-32601, "Method not found");
}

// ---------------------------------------------------------------------------
// CLICK
// ---------------------------------------------------------------------------
async function handleClick(formData: Record<string, string>): Promise<Response> {
  const merchant_trans_id = formData.merchant_trans_id ?? "";
  const click_trans_id = formData.click_trans_id ?? "";
  const sign_string = formData.sign_string ?? "";
  const amount = formData.amount ?? "0";
  const action = formData.action ?? "";
  const status = formData.status ?? "";
  const sign_time = formData.sign_time ?? "";

  // 1) Imzo tekshiruvi: MD5(click_trans_id:CLICK_SECRET:sign_time:status:amount:action:merchant_trans_id)
  const msg = `${click_trans_id}:${CLICK_SECRET}:${sign_time}:${status}:${amount}:${action}:${merchant_trans_id}`;
  const expectedSign = md5Hash(msg);
  if (sign_string !== expectedSign) {
    return json({ error: "Sign mismatch", error_code: 1 }, 401);
  }

  const txnId = merchant_trans_id;
  const amountNum = parseFloat(amount) * 100; // to'iqlari

  // Click status: 0=pending, 1=completed, -1=canceled
  const clickStatus = parseInt(status);

  // 2) Transaction'ni tekshirish
  const { data: payment, error: getErr } = await db.from("payments")
    .select("id, amount_uzs, course_id, user_id, status")
    .eq("provider_txn_id", txnId)
    .maybeSingle();

  if (getErr) {
    console.error("payment_query_failed", getErr);
    return json({ error: "Server error", error_code: -1 }, 500);
  }
  if (!payment) {
    return json({ error: "Order not found", error_code: -1 }, 404);
  }

  // Amount'ni tekshirish (1% xato bilan)
  const diff = Math.abs(payment.amount_uzs - amountNum);
  if (diff > payment.amount_uzs * 0.01) {
    return json({ error: "Amount mismatch", error_code: 1 }, 400);
  }

  // 3) Status bo'yicha harakat qilish
  if (clickStatus === 1 || action === "confirm") {
    // Tasdiqlash
    if (payment.status === "paid") return json({ error: "Order already paid", error_code: 0 }, 200); // idempotent

    const { error: updateErr } = await db.from("payments")
      .update({ status: "paid", paid_at: new Date().toISOString() })
      .eq("id", payment.id);

    if (updateErr) {
      console.error("payment_update_failed", updateErr);
      return json({ error: "Update failed", error_code: -1 }, 500);
    }

    // Yozilish
    if (payment.course_id) {
      await db.from("enrollments")
        .insert({ student_id: payment.user_id, course_id: payment.course_id, payment_id: payment.id })
        .select("id")
        .maybeSingle();
    }
    return json({ error: null, error_code: 0 }, 200);
  } else if (clickStatus === -1 || action === "cancel") {
    // Bekor qilish
    if (payment.status === "refunded" || payment.status === "failed") {
      return json({ error: null, error_code: 0 }, 200); // idempotent
    }
    await db.from("payments").update({ status: "failed" }).eq("id", payment.id);
    return json({ error: null, error_code: 0 }, 200);
  }

  // action = "prepare" — provisional hold, ignore
  return json({ error: null, error_code: 0 }, 200);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const contentType = req.headers.get("Content-Type") ?? "";
  const path = new URL(req.url).pathname;

  // Payme: /payment-webhook/payme
  if (path.includes("payme")) {
    if (!contentType.includes("application/json")) return json({ error: "bad_content_type" }, 400);
    const auth = req.headers.get("X-Auth") ?? "";
    const body = await req.json();
    return handlePayme(body, auth);
  }

  // Click: /payment-webhook/click
  if (path.includes("click")) {
    if (!contentType.includes("application/x-www-form-urlencoded")) return json({ error: "bad_content_type" }, 400);
    const formStr = await req.text();
    const form: Record<string, string> = {};
    new URLSearchParams(formStr).forEach((v, k) => {
      form[k] = v;
    });
    return handleClick(form);
  }

  return json({ error: "not_found" }, 404);
});
