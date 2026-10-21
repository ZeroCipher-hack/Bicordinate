// Bicoordinate — Telegram bot login (Supabase Edge Function)
//
// Oqim:
//   Frontend → Telegram bot link → user approve → callback URL → shu funksiya
//   Hash tekshiruvi: SHA256(sorted param key=value strings)
//   User yaratish/topish, Supabase sessiyasi qaytarish.
//
// Telegram callback'dan: id, first_name, last_name, username, photo_url, auth_date, hash
//
// Secrets: TELEGRAM_BOT_TOKEN (hash tekshirish uchun)
// SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — Supabase o'zi beradi

import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { create } from "npm:jose@5.0.0"; // JWT signing

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const JWT_SECRET = Deno.env.get("JWT_SECRET") ?? SERVICE_KEY.slice(0, 32); // JWT signing secret
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") ?? "";

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

// ---------------------------------------------------------------------------
// Yordamchilar
// ---------------------------------------------------------------------------
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

async function sha256(message: string): Promise<string> {
  const msgBuf = new TextEncoder().encode(message);
  const hashBuf = await crypto.subtle.digest("SHA-256", msgBuf);
  return Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// 1 soatdan eski auth'ni rad etish (replay attack oldini olish)
function isAuthExpired(authDate: number): boolean {
  return Date.now() / 1000 - authDate > 3600;
}

// ---------------------------------------------------------------------------
// Telegram hash tekshiruvi
// ---------------------------------------------------------------------------
async function verifyTelegramHash(params: Record<string, string>): Promise<boolean> {
  // Telegram: hash = SHA256("sorted\ndata\nstring")
  // Keys: id, first_name, last_name, username, photo_url, auth_date (hash harik emas)
  const dataCheckString = Object.keys(params)
    .filter((k) => k !== "hash")
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join("\n");

  const botTokenHash = await sha256(TELEGRAM_BOT_TOKEN);
  const expectedHash = await sha256(dataCheckString.split("").reduce((acc, char, i) => {
    const botByte = botTokenHash.charCodeAt(Math.floor(i / 2));
    const charCode = char.charCodeAt(0);
    return acc + String.fromCharCode(charCode ^ botByte);
  }, "").split("").reduce((acc, char) => {
    const charCode = char.charCodeAt(0);
    return acc + charCode.toString(16).padStart(2, "0");
  }, ""));

  // Deno/Node.js'da qulayroq: crypto.subtle yordamida HMAC
  const keyBuf = new TextEncoder().encode(dataCheckString);
  const keyHash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(TELEGRAM_BOT_TOKEN));
  const hmac = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", keyHash, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    keyBuf,
  );
  const hmacHex = Array.from(new Uint8Array(hmac)).map((b) => b.toString(16).padStart(2, "0")).join("");

  // Telegram o'zining formula'si (HMAC-SHA256)
  return params.hash === hmacHex;
}

// Telegramning hash formula'si (oddiy):
// hash = SHA256(data_check_string), bu yerda:
// data_check_string = "auth_date=...\nfirst_name=...\nid=...\nlast_name=...\nusername=..."
// Lekin server tahlili uchun key = bot_token.encode('utf-8')

async function verifyTelegramHashSimple(params: Record<string, string>): Promise<boolean> {
  const dataCheckString = Object.keys(params)
    .filter((k) => k !== "hash")
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join("\n");

  // HMAC-SHA256(data_check_string, SHA256(bot_token))
  const key = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(TELEGRAM_BOT_TOKEN));
  const msg = new TextEncoder().encode(dataCheckString);
  const hmac = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    msg,
  );
  const hmacHex = Array.from(new Uint8Array(hmac)).map((b) => b.toString(16).padStart(2, "0")).join("");
  return params.hash === hmacHex;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const contentType = req.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) return json({ error: "bad_content_type" }, 400);

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ error: "bad_json" }, 400);
  }

  // Telegram'dan kelgan callback
  const params: Record<string, string> = {};
  for (const key of ["id", "first_name", "last_name", "username", "photo_url", "auth_date", "hash"]) {
    const val = body[key];
    if (typeof val === "string" || typeof val === "number") params[key] = String(val);
  }

  // Paramlarni tekshirish
  if (!params.id || !params.auth_date || !params.hash) {
    return json({ error: "missing_params" }, 400);
  }

  const authDate = parseInt(params.auth_date);
  if (!Number.isFinite(authDate) || isAuthExpired(authDate)) {
    return json({ error: "auth_expired" }, 401);
  }

  // Hash tekshiruvi
  const isValid = await verifyTelegramHashSimple(params);
  if (!isValid) {
    console.error("telegram_hash_invalid", params.id);
    return json({ error: "invalid_signature" }, 401);
  }

  const telegramId = BigInt(params.id);
  const firstName = params.first_name || "User";
  const lastName = params.last_name || "";
  const photoUrl = params.photo_url || null;
  const fullName = `${firstName}${lastName ? " " + lastName : ""}`.trim();

  // 2) User topish yoki yaratish
  const { data: user, error: userErr } = await db
    .from("profiles")
    .select("id")
    .eq("telegram_id", telegramId.toString())
    .maybeSingle();

  let userId = user?.id;

  if (!userId) {
    // Yangi user yaratish uchun Supabase auth'ga yozish kerak (service role'ni ishlatamiz)
    const adminClient = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

    // Email bilan daftarlanish (Telegram'dan email yo'q, fictive email ishlatamiz)
    const fictiveEmail = `telegram_${telegramId}@bicoordinate.local`;
    const { data: authUser, error: authErr } = await adminClient.auth.admin.createUser({
      email: fictiveEmail,
      email_confirm: true,
      user_metadata: {
        full_name: fullName,
        avatar_url: photoUrl,
      },
    });

    if (authErr) {
      // Email allaqachon bor (odd case)
      console.error("auth_create_failed", authErr);
      return json({ error: "user_creation_failed" }, 500);
    }

    userId = authUser?.user?.id;
    if (!userId) return json({ error: "user_creation_failed" }, 500);

    // Profile (trigger avtomatik yaratadi, lekin telegram_id'ni qo'shamiz)
    const { error: profileErr } = await db
      .from("profiles")
      .update({ telegram_id: telegramId.toString() })
      .eq("id", userId);

    if (profileErr) {
      console.error("profile_update_failed", profileErr);
      return json({ error: "profile_update_failed" }, 500);
    }
  }

  // 3) Sessiya yaratish (JWT direct)
  const sessionToken = await generateSessionToken(userId, telegramId);

  return json({
    success: true,
    user_id: userId,
    telegram_id: params.id,
    full_name: fullName,
    email: fictiveEmail,
    session_token: sessionToken, // Frontend saqlashi kerak → Authorization header'ga
  });
});

// JWT yaratish (jose bilan)
async function generateSessionToken(userId: string, telegramId: bigint): Promise<string> {
  const secret = new TextEncoder().encode(JWT_SECRET);
  const jwt = await create(
    { alg: "HS256", typ: "JWT" },
    {
      sub: userId,
      telegram_id: telegramId.toString(),
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60, // 7 kunlik sessiya
    },
    secret,
  );
  return jwt;
}
