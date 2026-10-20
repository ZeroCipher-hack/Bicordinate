// Bicoordinate — kunlik mashq generatori (Supabase Edge Function, Deno)
//
// Qanday ishlaydi:
//   * pg_cron har 5 daqiqada (Toshkent 18:00–20:55) shu funksiyani chaqiradi.
//   * Har chaqiruvda ERTANGI kun uchun hali yaratilmagan BITTA nishonni (fan + daraja) oladi,
//     Gemini'dan savollar so'raydi, to'g'ri javoblarni MUSTAQIL tekshiradi,
//     o'tganlarini "pending_review" holatida bazaga yozadi. Admin tasdiqlagach o'quvchilarga ochiladi.
//   * Bitta chaqiruv = bitta nishon: Google bepul limitiga sig'adi, xato bo'lsa keyingi chaqiruv qayta urinadi.
//   * Admin panel aniq nishonni qayta yaratishi mumkin: POST {subject, level, date?, force: true}
//
// Tekshirish (AI'ga ishonmaymiz):
//   * Ingliz tili test savollari: ikkinchi, mustaqil Gemini chaqiruvi javobni bilmasdan yechadi.
//     Javoblar mos kelmasa — savol tashlanadi.
//   * Matematika: tenglama bo'lsa, javob tenglamaga qo'yib KOD bilan tekshiriladi;
//     aks holda mustaqil qayta yechish. Mos kelmasa — tashlanadi.
//   * Variantlar server tomonda aralashtiriladi (AI to'g'ri javobni ko'pincha bir joyga qo'yadi).
//
// Secrets: GEMINI_API_KEY, GEMINI_MODEL, CRON_SECRET
// Supabase o'zi beradi: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";
const GEMINI_MODEL = Deno.env.get("GEMINI_MODEL") ?? "";
const CRON_SECRET = Deno.env.get("CRON_SECRET") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

// ---------------------------------------------------------------------------
// Nishonlar: har kuni shularning har biri uchun bitta to'plam
// ---------------------------------------------------------------------------
type Target = { subject: "english" | "math"; level: string };
const TARGETS: Target[] = [
  ...["A1", "A2", "B1", "B2", "C1"].map((level) => ({ subject: "english" as const, level })),
  ...[5, 6, 7, 8, 9, 10, 11].map((g) => ({ subject: "math" as const, level: `${g}-sinf` })),
];

// Bitta to'plamda nechta savol qoladi (generatsiyada zaxira bilan ko'proq so'raladi)
const KEEP = { listening: 2, reading: 2, grammar: 2, vocabulary: 2, math: 5 };
const XP = { mcq: 20, writing: 60, speaking: 60, math: 10 };

// ---------------------------------------------------------------------------
// Yordamchilar
// ---------------------------------------------------------------------------
const TASHKENT_OFFSET_MS = 5 * 60 * 60 * 1000; // UTC+5, yozgi vaqt yo'q

function tashkentDate(addDays = 0): string {
  const d = new Date(Date.now() + TASHKENT_OFFSET_MS + addDays * 86_400_000);
  return d.toISOString().slice(0, 10);
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function safeEqual(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function shuffleMcq(options: string[], correct: number): { options: string[]; correct: number } {
  const idx = options.map((_, i) => i);
  for (let i = idx.length - 1; i > 0; i--) {
    const j = crypto.getRandomValues(new Uint32Array(1))[0] % (i + 1);
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return { options: idx.map((i) => options[i]), correct: idx.indexOf(correct) };
}

function validMcq(q: unknown): q is Mcq {
  const m = q as Mcq;
  return !!m && typeof m.text === "string" && m.text.length > 0 &&
    Array.isArray(m.options) && m.options.length === 4 &&
    m.options.every((o) => typeof o === "string" && o.length > 0) &&
    new Set(m.options.map((o) => o.trim().toLowerCase())).size === 4 &&
    Number.isInteger(m.correct) && m.correct >= 0 && m.correct < 4;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Gemini chaqiruvi (429/503 da 2 marta qayta urinadi)
// ---------------------------------------------------------------------------
async function gemini<T>(system: string, user: string, schema: unknown, temperature: number): Promise<T> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(GEMINI_MODEL)}:generateContent`;
  for (let attempt = 0; attempt < 3; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45_000);
    try {
      const res = await fetch(url, {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: system }] },
          contents: [{ role: "user", parts: [{ text: user }] }],
          generationConfig: { temperature, maxOutputTokens: 8192, responseMimeType: "application/json", responseSchema: schema },
        }),
      });
      if (res.status === 429 || res.status === 503) {
        await sleep(8_000 * (attempt + 1));
        continue;
      }
      if (!res.ok) throw new Error(`gemini ${res.status}: ${(await res.text()).slice(0, 300)}`);
      const g = await res.json();
      const raw = g?.candidates?.[0]?.content?.parts?.[0]?.text;
      return JSON.parse(raw) as T;
    } finally {
      clearTimeout(timer);
    }
  }
  throw new Error("gemini_busy");
}

// ---------------------------------------------------------------------------
// Matematika: xavfsiz ifoda hisoblagich (eval YO'Q). + - * / ^ ( ) sonlar va x
// ---------------------------------------------------------------------------
function evaluate(expr: string, x: number): number {
  const src = expr.replace(/\s+/g, "").replace(/[×·]/g, "*").replace(/[÷:]/g, "/").replace(/[−–]/g, "-");
  let pos = 0;
  const peek = () => src[pos];
  const eat = (c: string) => { if (src[pos] === c) { pos++; return true; } return false; };

  function primary(): number {
    if (eat("(")) { const v = sum(); if (!eat(")")) throw new Error("')' yo'q"); return v; }
    if (peek() === "x" || peek() === "X") { pos++; return x; }
    const m = /^\d+(\.\d+)?/.exec(src.slice(pos));
    if (!m) throw new Error(`kutilmagan belgi: ${peek()}`);
    pos += m[0].length;
    return parseFloat(m[0]);
  }
  function implicit(): number {               // 3x, 2(x+1) kabi yozuvlar
    let v = primary();
    while (peek() === "x" || peek() === "X" || peek() === "(") v *= primary();
    return v;
  }
  function power(): number {
    const base = implicit();
    return eat("^") ? Math.pow(base, unary()) : base;
  }
  function unary(): number {
    if (eat("-")) return -unary();
    if (eat("+")) return unary();
    return power();
  }
  function product(): number {
    let v = unary();
    for (;;) {
      if (eat("*")) v *= unary();
      else if (eat("/")) v /= unary();
      else return v;
    }
  }
  function sum(): number {
    let v = product();
    for (;;) {
      if (eat("+")) v += product();
      else if (eat("-")) v -= product();
      else return v;
    }
  }
  const v = sum();
  if (pos !== src.length) throw new Error("ifoda oxirigacha o'qilmadi");
  return v;
}

function checkEquation(equation: string, answer: number): boolean | null {
  const sides = equation.split("=");
  if (sides.length !== 2) return null;
  try {
    const l = evaluate(sides[0], answer), r = evaluate(sides[1], answer);
    if (!Number.isFinite(l) || !Number.isFinite(r)) return null;
    return Math.abs(l - r) < 1e-6 * Math.max(1, Math.abs(l), Math.abs(r));
  } catch {
    return null; // tahlil qilib bo'lmadi → mustaqil yechishga yuboriladi
  }
}

// ---------------------------------------------------------------------------
// Ingliz tili
// ---------------------------------------------------------------------------
type Mcq = { text: string; options: string[]; correct: number };
type EnglishGen = {
  listening: { transcript: string; questions: Mcq[] };
  reading: { title: string; passage: string; questions: Mcq[] };
  grammar: Mcq[];
  vocabulary: Mcq[];
  writing: { task: string; min_words: number };
  speaking: { task: string; seconds: number };
};

const MCQ_SCHEMA = {
  type: "OBJECT",
  properties: {
    text: { type: "STRING" },
    options: { type: "ARRAY", items: { type: "STRING" } },
    correct: { type: "INTEGER" },
  },
  required: ["text", "options", "correct"],
};

const ENGLISH_SCHEMA = {
  type: "OBJECT",
  properties: {
    listening: { type: "OBJECT", properties: { transcript: { type: "STRING" }, questions: { type: "ARRAY", items: MCQ_SCHEMA } }, required: ["transcript", "questions"] },
    reading: { type: "OBJECT", properties: { title: { type: "STRING" }, passage: { type: "STRING" }, questions: { type: "ARRAY", items: MCQ_SCHEMA } }, required: ["title", "passage", "questions"] },
    grammar: { type: "ARRAY", items: MCQ_SCHEMA },
    vocabulary: { type: "ARRAY", items: MCQ_SCHEMA },
    writing: { type: "OBJECT", properties: { task: { type: "STRING" }, min_words: { type: "INTEGER" } }, required: ["task", "min_words"] },
    speaking: { type: "OBJECT", properties: { task: { type: "STRING" }, seconds: { type: "INTEGER" } }, required: ["task", "seconds"] },
  },
  required: ["listening", "reading", "grammar", "vocabulary", "writing", "speaking"],
};

const ENGLISH_SYSTEM = `You write daily English practice for Uzbek school students on the Bicoordinate platform.
Rules:
- Match the CEFR level exactly. Content must be age-appropriate (10–18), friendly and interesting; prefer topics familiar in Uzbekistan (cities, food, school, sport, technology, nature) mixed with global topics.
- Every multiple-choice question has exactly 4 distinct options and exactly ONE correct answer; "correct" is its 0-based index. Distractors must be clearly wrong for a careful student, not trick questions.
- No politics, religion, violence, dating or brand names.
- Listening: a natural dialogue or monologue transcript (it will be read aloud by text-to-speech).
- Reading questions must be answerable only from the passage.`;

function englishUserPrompt(level: string, date: string): string {
  const len: Record<string, string> = { A1: "60–80", A2: "80–110", B1: "120–160", B2: "170–220", C1: "230–280" };
  return `Level: ${level}. Date: ${date} (use it to vary topics; do not mention it).
Create:
- listening: transcript of ${len[level] ?? "120–160"} words + 3 questions
- reading: a title, a passage of ${len[level] ?? "120–160"} words + 3 questions
- grammar: 3 questions testing a ${level} grammar point (one sentence with a gap each)
- vocabulary: 3 questions (meaning, synonym or collocation at ${level})
- writing: one task suitable for ${level} with min_words
- speaking: one 1-minute speaking prompt with seconds = 60`;
}

const VERIFY_SCHEMA = {
  type: "OBJECT",
  properties: { answers: { type: "ARRAY", items: { type: "OBJECT", properties: { id: { type: "STRING" }, choice: { type: "INTEGER" } }, required: ["id", "choice"] } } },
  required: ["answers"],
};

async function verifyMcqs(context: string, items: { id: string; q: Mcq }[]): Promise<Set<string>> {
  if (items.length === 0) return new Set();
  const listing = items.map(({ id, q }) => `${id}: ${q.text}\n${q.options.map((o, i) => `  ${i}) ${o}`).join("\n")}`).join("\n\n");
  const res = await gemini<{ answers: { id: string; choice: number }[] }>(
    "You are a careful English examiner. Answer each multiple-choice question. Return the 0-based index of the single best option for every id.",
    `${context}\n\nQuestions:\n${listing}`,
    VERIFY_SCHEMA,
    0,
  );
  const byId = new Map(res.answers.map((a) => [a.id, a.choice]));
  return new Set(items.filter(({ id, q }) => byId.get(id) === q.correct).map(({ id }) => id));
}

type ItemRow = { skill: string; prompt: Record<string, unknown>; key: Record<string, unknown> | null; xp: number };

async function buildEnglish(level: string, date: string): Promise<ItemRow[]> {
  const gen = await gemini<EnglishGen>(ENGLISH_SYSTEM, englishUserPrompt(level, date), ENGLISH_SCHEMA, 0.9);

  const pools: Record<"listening" | "reading" | "grammar" | "vocabulary", Mcq[]> = {
    listening: (gen.listening?.questions ?? []).filter(validMcq),
    reading: (gen.reading?.questions ?? []).filter(validMcq),
    grammar: (gen.grammar ?? []).filter(validMcq),
    vocabulary: (gen.vocabulary ?? []).filter(validMcq),
  };
  const tagged = (Object.keys(pools) as (keyof typeof pools)[])
    .flatMap((skill) => pools[skill].map((q, i) => ({ id: `${skill[0].toUpperCase()}${i}`, skill, q })));

  const context = `LISTENING TRANSCRIPT:\n${gen.listening?.transcript ?? ""}\n\nREADING PASSAGE (${gen.reading?.title ?? ""}):\n${gen.reading?.passage ?? ""}`;
  const passed = await verifyMcqs(context, tagged.map(({ id, q }) => ({ id, q })));

  const rows: ItemRow[] = [];
  for (const skill of ["listening", "reading", "grammar", "vocabulary"] as const) {
    const ok = tagged.filter((t) => t.skill === skill && passed.has(t.id)).slice(0, KEEP[skill]);
    if (ok.length < KEEP[skill]) throw new Error(`${level}: ${skill} bo'yicha tekshiruvdan o'tgan savol yetmadi (${ok.length}/${KEEP[skill]})`);
    for (const t of ok) {
      const s = shuffleMcq(t.q.options, t.q.correct);
      const prompt: Record<string, unknown> = { type: "mcq", text: t.q.text, options: s.options };
      if (skill === "listening") prompt.transcript = gen.listening.transcript; // frontend TTS bilan o'qiydi
      if (skill === "reading") { prompt.title = gen.reading.title; prompt.passage = gen.reading.passage; }
      rows.push({ skill, prompt, key: { choice: s.correct }, xp: XP.mcq });
    }
  }
  if (!gen.writing?.task || !gen.speaking?.task) throw new Error(`${level}: writing/speaking topshirig'i yo'q`);
  rows.push({ skill: "writing", prompt: { type: "writing", task: gen.writing.task, min_words: Math.max(30, gen.writing.min_words | 0) }, key: null, xp: XP.writing });
  rows.push({ skill: "speaking", prompt: { type: "speaking", task: gen.speaking.task, seconds: 60 }, key: null, xp: XP.speaking });
  return rows;
}

// ---------------------------------------------------------------------------
// Matematika
// ---------------------------------------------------------------------------
type MathGen = { problems: { text: string; answer: number; equation?: string; topic: string }[] };

const MATH_SCHEMA = {
  type: "OBJECT",
  properties: {
    problems: {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: {
          text: { type: "STRING" },
          answer: { type: "NUMBER" },
          equation: { type: "STRING" },
          topic: { type: "STRING" },
        },
        required: ["text", "answer", "topic"],
      },
    },
  },
  required: ["problems"],
};

const MATH_SYSTEM = `Sen O'zbekiston maktab dasturi bo'yicha matematika masalalari tuzasan (Bicoordinate platformasi).
Qoidalar:
- Masala matni o'zbek tilida (lotin yozuvi), aniq va bir ma'noli.
- Har masalaning javobi BITTA son: butun yoki ko'pi bilan 2 xonali o'nli kasr. Javob birligini matnda ko'rsat ("sm da", "so'mda").
- Agar masala bitta noma'lumli tenglamaga keltirilsa, "equation" maydoniga uni x orqali yoz (faqat sonlar, x, + - * / ^ ( ) va bitta =), masalan "3*x-7=11". Aks holda equation bo'sh qolsin.
- Qiyinlik: sinf darajasiga mos, oson → o'rtacha → qiyin tartibida.
- Matnli masalalarda O'zbekistonga yaqin vaziyatlar (bozor, maktab, sayohat, sport).`;

async function buildMath(level: string, date: string): Promise<ItemRow[]> {
  const gen = await gemini<MathGen>(MATH_SYSTEM, `Sinf: ${level}. Sana: ${date} (mavzularni xilma-xil qilish uchun; matnda tilga olma).\n8 ta masala tuz: kamida 3 tasi tenglama bilan.`, MATH_SCHEMA, 0.9);
  const problems = (gen.problems ?? []).filter((p) =>
    typeof p.text === "string" && p.text.length > 0 && Number.isFinite(p.answer) && Math.abs(p.answer) < 1e9 &&
    Math.round(p.answer * 100) === p.answer * 100,
  );

  const verified: typeof problems = [];
  const needSolve: { id: string; p: (typeof problems)[number] }[] = [];
  problems.forEach((p, i) => {
    const eq = p.equation?.trim();
    const res = eq ? checkEquation(eq, p.answer) : null;
    if (res === true) verified.push(p);
    else if (res === null) needSolve.push({ id: `M${i}`, p });
    // res === false → javob tenglamani qanoatlantirmaydi → tashlanadi
  });

  if (verified.length < KEEP.math && needSolve.length > 0) {
    const res = await gemini<{ answers: { id: string; value: number }[] }>(
      "Sen diqqatli matematika o'qituvchisisan. Har masalani mustaqil yech va faqat yakuniy sonli javobni qaytar.",
      needSolve.map(({ id, p }) => `${id}: ${p.text}`).join("\n\n"),
      { type: "OBJECT", properties: { answers: { type: "ARRAY", items: { type: "OBJECT", properties: { id: { type: "STRING" }, value: { type: "NUMBER" } }, required: ["id", "value"] } } }, required: ["answers"] },
      0,
    );
    const byId = new Map(res.answers.map((a) => [a.id, a.value]));
    for (const { id, p } of needSolve) {
      const v = byId.get(id);
      if (typeof v === "number" && Math.abs(v - p.answer) < 1e-6) verified.push(p);
    }
  }

  // Asl tartibni saqlash (oson → qiyin)
  const ordered = problems.filter((p) => verified.includes(p)).slice(0, KEEP.math);
  if (ordered.length < KEEP.math) throw new Error(`${level}: tekshiruvdan o'tgan masala yetmadi (${ordered.length}/${KEEP.math})`);

  return ordered.map((p) => ({
    skill: "math",
    prompt: { type: "number", text: p.text, topic: p.topic },
    key: { value: p.answer },   // frontend {"value": <son>} yuboradi
    xp: XP.math,
  }));
}

// ---------------------------------------------------------------------------
// Bazaga yozish
// ---------------------------------------------------------------------------
async function saveSet(t: Target, date: string, rows: ItemRow[], force: boolean) {
  const { data: existing } = await db.from("daily_sets")
    .select("id, status").eq("set_date", date).eq("subject", t.subject).eq("level", t.level).maybeSingle();

  if (existing && existing.status === "approved" && !force) return { skipped: "already_approved" };
  if (existing) {
    const { error } = await db.from("daily_sets").delete().eq("id", existing.id); // itemlar va keys cascade bilan o'chadi
    if (error) throw error;
  }

  const { data: set, error: setErr } = await db.from("daily_sets")
    .insert({ set_date: date, subject: t.subject, level: t.level, status: "pending_review", model: GEMINI_MODEL })
    .select("id").single();
  if (setErr) throw setErr;

  const { data: items, error: itemErr } = await db.from("daily_items")
    .insert(rows.map((r, i) => ({ set_id: set.id, position: i + 1, skill: r.skill, prompt: r.prompt, xp: r.xp })))
    .select("id, position");
  if (itemErr) throw itemErr;

  const keys = items
    .map((it) => ({ item_id: it.id, answer: rows[it.position - 1].key }))
    .filter((k) => k.answer !== null);
  if (keys.length) {
    const { error: keyErr } = await db.from("daily_item_keys").insert(keys);
    if (keyErr) throw keyErr;
  }
  return { set_id: set.id, items: rows.length };
}

// ---------------------------------------------------------------------------
// Kirish nuqtasi
// ---------------------------------------------------------------------------
async function isAdminRequest(req: Request): Promise<boolean> {
  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return false;
  const userClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: auth } }, auth: { persistSession: false },
  });
  const { data } = await userClient.auth.getUser();
  if (!data?.user) return false;
  const { data: prof } = await db.from("profiles").select("role").eq("id", data.user.id).single();
  return prof?.role === "admin";
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (!GEMINI_API_KEY || !GEMINI_MODEL) return json({ error: "server_not_configured" }, 500);

  const fromCron = safeEqual(req.headers.get("x-cron-secret") ?? "", CRON_SECRET);
  const fromAdmin = !fromCron && await isAdminRequest(req);
  if (!fromCron && !fromAdmin) return json({ error: "forbidden" }, 403);

  let body: { subject?: string; level?: string; date?: string; force?: boolean } = {};
  try { body = await req.json(); } catch { /* bo'sh body — cron */ }

  const date = fromAdmin && body.date && /^\d{4}-\d{2}-\d{2}$/.test(body.date) ? body.date : tashkentDate(1);

  let target: Target | undefined;
  if (fromAdmin && body.subject && body.level) {
    target = TARGETS.find((t) => t.subject === body.subject && t.level === body.level);
    if (!target) return json({ error: "unknown_target" }, 400);
  } else {
    const { data: done } = await db.from("daily_sets").select("subject, level").eq("set_date", date);
    const have = new Set((done ?? []).map((d) => `${d.subject}|${d.level}`));
    target = TARGETS.find((t) => !have.has(`${t.subject}|${t.level}`));
    if (!target) return json({ status: "all_done", date });
  }

  try {
    const rows = target.subject === "english" ? await buildEnglish(target.level, date) : await buildMath(target.level, date);
    const saved = await saveSet(target, date, rows, fromAdmin && body.force === true);
    return json({ status: "ok", date, target, ...saved });
  } catch (e) {
    console.error("daily_generate_failed", target, String(e));
    // Cron 5 daqiqadan keyin shu nishonni qayta urinadi
    return json({ status: "failed", date, target, error: String(e).slice(0, 300) }, 502);
  }
});
