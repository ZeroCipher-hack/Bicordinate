// Bicoordinate — Telegram bot login (Supabase Edge Function)
//
// Oqim:
//   Frontend → Telegram bot link → user approve → callback URL → shu funksiya
//   Hash tekshiruvi: SHA256(sorted param key=value strings)
//   User yaratish, magic link yaratish, verifyOtp bilan sessiya.
//
// Telegram callback'dan: id, first_name, last_name, username, photo_url, auth_date, hash
//
// Secrets: TELEGRAM_BOT_TOKEN (hash tekshirish uchun)
// SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — Supabase o'zi beradi

import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") ?? "";

const adminClient = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });
const anonClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: false } });

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

async function sha256(message: string): Promise<string> {
  const msgBuf = new TextEncoder().encode(message);
  const hashBuf = await crypto.subtle.digest("SHA-256", msgBuf);
  return Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function isAuthExpired(authDate: number): boolean {
  return Date.now() / 1000 - authDate > 3600;
}

// Telegram hash tekshiruvi: HMAC-SHA256(dataCheckString, SHA256(botToken))
async function verifyTelegramHash(params: Record<string, string>): Promise<boolean> {
  const dataCheckString = Object.keys(params)
    .filter((k) => k !== "hash")
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join("\n");

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

  if (!params.id || !params.auth_date || !params.hash) {
    return json({ error: "missing_params" }, 400);
  }

  const authDate = parseInt(params.auth_date);
  if (!Number.isFinite(authDate) || isAuthExpired(authDate)) {
    return json({ error: "auth_expired" }, 401);
  }

  // Hash tekshiruvi
  const isValid = await verifyTelegramHash(params);
  if (!isValid) {
    console.error("telegram_hash_invalid", params.id);
    return json({ error: "invalid_signature" }, 401);
  }

  const telegramId = params.id;
  const firstName = params.first_name || "User";
  const lastName = params.last_name || "";
  const photoUrl = params.photo_url || null;
  const fullName = `${firstName}${lastName ? " " + lastName : ""}`.trim();
  const fictiveEmail = `telegram_${telegramId}.invalid`; // .invalid domenini ishlat

  // User topish
  let { data: existingProfile } = await adminClient
    .from("profiles")
    .select("id")
    .eq("telegram_id", telegramId)
    .maybeSingle();

  let userId = existingProfile?.id;

  // Yangi user yaratish
  if (!userId) {
    const { data: authUser, error: authErr } = await adminClient.auth.admin.createUser({
      email: fictiveEmail,
      email_confirm: true,
      user_metadata: {
        full_name: fullName,
        avatar_url: photoUrl,
      },
    });

    if (authErr) {
      console.error("telegram_create_user_failed", authErr);
      return json({ error: "user_creation_failed" }, 500);
    }

    userId = authUser?.user?.id;
    if (!userId) return json({ error: "user_creation_failed" }, 500);

    // Profile'ga telegram_id qo'shish
    const { error: updateErr } = await adminClient
      .from("profiles")
      .update({ telegram_id: telegramId })
      .eq("id", userId);

    if (updateErr) {
      console.error("telegram_update_profile_failed", updateErr);
      return json({ error: "profile_update_failed" }, 500);
    }
  }

  // Magic link yaratish
  const { data: linkData, error: linkErr } = await adminClient.auth.admin.generateLink({
    type: "magiclink",
    email: fictiveEmail,
    options: { redirectTo: `${new URL(req.url).origin}/auth/callback` },
  });

  if (linkErr) {
    console.error("telegram_magiclink_failed", linkErr);
    return json({ error: "link_generation_failed" }, 500);
  }

  // Link'dan OTP'ni shakllash (frontend → verifyOtp)
  // Link: https://.../#access_token=...&type=magiclink&...
  // O'rniga: token'ni direct qaytarish (frontend'da fetch bilan)
  const actionLink = linkData?.properties?.action_link || "";
  const tokenMatch = actionLink.match(/access_token=([^&]+)/);
  const token = tokenMatch?.[1] || "";

  if (!token) {
    console.error("telegram_token_extraction_failed");
    return json({ error: "token_extraction_failed" }, 500);
  }

  // Frontend: token'ni localStorage'ga saqlaydi
  return json({
    success: true,
    user_id: userId,
    telegram_id: telegramId,
    full_name: fullName,
    access_token: token, // Frontend → `setSession({ access_token: '...', refresh_token: '...' })`
    type: "magiclink",
  });
}
