// Bicoordinate — Payme Merchant API (Supabase Edge Function)
//
// Hujjat: https://developer.paycom.uz/docs/ru/merchants/
// Metodi: POST JSON-RPC 2.0
// Auth: Basic base64("Paycom:KEY") header
// Parametrlar: method, params (account, amount, time)
// Holatlar: 1=pending, 2=completed, -1=canceled, -2=timeout
// Summa: tiyin'da (100 = 1 so'm)
// Timeout: 12 soat

import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const PAYME_KEY = Deno.env.get("PAYME_KEY") ?? "";

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function rpcError(id: unknown, code: number, msg: string) {
  return json({ jsonrpc: "2.0", id, error: { code, message: msg } }, 400);
}

function rpcReply(id: unknown, result: unknown) {
  return json({ jsonrpc: "2.0", id, result });
}

// Millisekund'dan soat'ga
function hoursAgo(ms: number): number {
  return (Date.now() - ms) / 3600000;
}

// ---------------------------------------------------------------------------
// Payme metodlari
// ---------------------------------------------------------------------------

async function checkPerformTransaction(
  merchantTxnId: string,
  amount: number,
  account: Record<string, unknown>,
  id: unknown
): Promise<Response> {
  // To'lovni tekshirish — mavjud bo'lsa holatini qaytarish
  const { data: payment, error } = await db
    .from("payments")
    .select("id, amount_uzs, course_id, user_id, state, create_time")
    .eq("provider_txn_id", merchantTxnId)
    .eq("provider", "payme")
    .maybeSingle();

  if (error) {
    console.error("payme_query_failed", error);
    return rpcError(id, -32500, "Server error");
  }

  if (!payment) {
    return rpcError(id, -31003, "Transaction not found");
  }

  // Summa tekshiruvi (tiyin'da)
  if (payment.amount_uzs !== amount) {
    return rpcError(id, -31001, "Amount mismatch");
  }

  // Timeout tekshiruvi (12 soat)
  const createTimeMs = (payment.create_time as number) || Date.now();
  if (hoursAgo(createTimeMs) > 12) {
    return rpcReply(id, { state: -2 }); // timeout
  }

  return rpcReply(id, { state: payment.state });
}

async function createTransaction(
  merchantTxnId: string,
  amount: number,
  account: Record<string, unknown>,
  id: unknown
): Promise<Response> {
  // Yangi transaction yaratish (pending holatiga)
  const timeMs = Date.now();
  const { data: existing } = await db
    .from("payments")
    .select("id, state")
    .eq("provider_txn_id", merchantTxnId)
    .eq("provider", "payme")
    .maybeSingle();

  if (existing) {
    // Qayta chaqiruv (idempotent)
    const timeoutHours = hoursAgo(existing.state === 1 ? timeMs : Date.now());
    if (timeoutHours > 12 && existing.state === 1) {
      return rpcReply(id, { state: -2 });
    }
    return rpcReply(id, { state: existing.state, transaction: `${merchantTxnId}` });
  }

  // Yangi payment yaratish
  const { error } = await db.from("payments").insert({
    provider_txn_id: merchantTxnId,
    provider: "payme",
    amount_uzs: amount,
    user_id: null, // merchant_trans_id'dan aniqlash kerak (future)
    kind: "course",
    state: 1, // pending
    create_time: timeMs,
    status: "pending",
  });

  if (error) {
    console.error("payme_create_failed", error);
    return rpcError(id, -32500, "Server error");
  }

  return rpcReply(id, { state: 1, transaction: merchantTxnId });
}

async function performTransaction(
  merchantTxnId: string,
  amount: number,
  account: Record<string, unknown>,
  id: unknown
): Promise<Response> {
  // To'lovni bajarilgan holatiga o'tkazish va enrollment yaratish
  const timeMs = Date.now();
  const { data: payment, error } = await db
    .from("payments")
    .select("id, state, user_id, course_id, create_time")
    .eq("provider_txn_id", merchantTxnId)
    .eq("provider", "payme")
    .maybeSingle();

  if (error) {
    console.error("payme_query_failed", error);
    return rpcError(id, -32500, "Server error");
  }

  if (!payment) {
    return rpcError(id, -31003, "Transaction not found");
  }

  // Summa tekshiruvi
  if ((payment as any).amount_uzs !== amount) {
    return rpcError(id, -31001, "Amount mismatch");
  }

  // Timeout tekshiruvi
  if (hoursAgo((payment as any).create_time || Date.now()) > 12) {
    return rpcReply(id, { state: -2 });
  }

  // Allaqachon bajarilgan bo'lsa
  if ((payment as any).state === 2) {
    return rpcReply(id, { state: 2, transaction: merchantTxnId });
  }

  // State 1 bo'lsa (pending), 2 ga o'tkazish
  if ((payment as any).state !== 1) {
    return rpcError(id, -31006, "Transaction cannot be completed");
  }

  // Update
  const { error: updateErr } = await db
    .from("payments")
    .update({ state: 2, perform_time: timeMs, status: "paid", paid_at: new Date().toISOString() })
    .eq("id", payment.id);

  if (updateErr) {
    console.error("payme_perform_failed", updateErr);
    return rpcError(id, -32500, "Server error");
  }

  // Enrollment yaratish
  if ((payment as any).course_id && (payment as any).user_id) {
    await db.from("enrollments").insert({
      student_id: (payment as any).user_id,
      course_id: (payment as any).course_id,
      payment_id: payment.id,
    }).select("id").maybeSingle();
  }

  return rpcReply(id, { state: 2, transaction: merchantTxnId });
}

async function cancelTransaction(
  merchantTxnId: string,
  reason: number,
  id: unknown
): Promise<Response> {
  // To'lovni bekor qilish
  const timeMs = Date.now();
  const { data: payment } = await db
    .from("payments")
    .select("id, state")
    .eq("provider_txn_id", merchantTxnId)
    .eq("provider", "payme")
    .maybeSingle();

  if (!payment) {
    return rpcError(id, -31003, "Transaction not found");
  }

  // Allaqachon bekor bo'lsa
  if ((payment as any).state === -1) {
    return rpcReply(id, { state: -1, transaction: merchantTxnId });
  }

  // Cancel
  const { error } = await db
    .from("payments")
    .update({ state: -1, cancel_time: timeMs, status: "failed", reason: `Payme canceled: ${reason}` })
    .eq("id", payment.id);

  if (error) {
    console.error("payme_cancel_failed", error);
    return rpcError(id, -32500, "Server error");
  }

  return rpcReply(id, { state: -1, transaction: merchantTxnId });
}

async function checkTransaction(merchantTxnId: string, id: unknown): Promise<Response> {
  const { data: payment } = await db
    .from("payments")
    .select("id, state, create_time")
    .eq("provider_txn_id", merchantTxnId)
    .eq("provider", "payme")
    .maybeSingle();

  if (!payment) {
    return rpcError(id, -31003, "Transaction not found");
  }

  // Timeout tekshiruvi
  if (hoursAgo((payment as any).create_time || Date.now()) > 12) {
    return rpcReply(id, { state: -2 });
  }

  return rpcReply(id, { state: (payment as any).state });
}

async function getStatement(from: number, to: number, id: unknown): Promise<Response> {
  // Kunlik ibrovat (unused bo'lishi mumkin, empty qaytarish)
  return rpcReply(id, { transactions: [] });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  // Basic auth tekshiruvi
  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.startsWith("Basic ")) {
    return rpcError(null, -32504, "Incorrect password");
  }

  const credentials = atob(auth.slice(6)); // "Basic " o'chirib, base64 decompress
  if (credentials !== `Paycom:${PAYME_KEY}`) {
    return rpcError(null, -32504, "Incorrect password");
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return rpcError(null, -32700, "Parse error");
  }

  const method = body.method as string;
  const params = body.params as Record<string, unknown> || {};
  const id = body.id;

  // Metod ro'yxati
  try {
    switch (method) {
      case "CheckPerformTransaction":
        return await checkPerformTransaction(
          String(params.account?.merchant_trans_id || ""),
          Number(params.amount) || 0,
          params.account as Record<string, unknown>,
          id
        );

      case "CreateTransaction":
        return await createTransaction(
          String(params.account?.merchant_trans_id || ""),
          Number(params.amount) || 0,
          params.account as Record<string, unknown>,
          id
        );

      case "PerformTransaction":
        return await performTransaction(
          String(params.account?.merchant_trans_id || ""),
          Number(params.amount) || 0,
          params.account as Record<string, unknown>,
          id
        );

      case "CancelTransaction":
        return await cancelTransaction(
          String(params.account?.merchant_trans_id || ""),
          Number(params.reason) || 0,
          id
        );

      case "CheckTransaction":
        return await checkTransaction(String(params.account?.merchant_trans_id || ""), id);

      case "GetStatement":
        return await getStatement(Number(params.from) || 0, Number(params.to) || 0, id);

      default:
        return rpcError(id, -32601, "Method not found");
    }
  } catch (err) {
    console.error("payme_error", method, String(err));
    return rpcError(id, -32500, "Server error");
  }
});
