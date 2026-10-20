# Bicoordinate

Matematika va ingliz tili bo'yicha AI ustoz platformasi: video darslar, ustozlarning pullik kurslari,
AI yordamida misol yechish, har kuni darajaga mos AI mashqlar, Writing/Speaking baholash va premium musobaqalar.

## Tuzilma

```
supabase/
  migrations/
    20261020000100_schema.sql           # jadvallar, rollar, RLS, XP, musobaqa
    20261020000200_ai_refund.sql        # AI xatosida limitni qaytarish
    20261020000300_daily_generator.sql  # admin tekshiruvi + pg_cron
    20261020000400_ai_grading.sql       # Writing/Speaking natijasini yozish
  functions/
    ai-solve/        # "AI yechib ber" — matn yoki rasm
    daily-generate/  # kunlik mashq generatori (cron)
    ai-grade/        # Writing va Speaking baholash
tests/
  smoke.sh           # deploy'dan keyingi umumiy tekshiruv
```

## Rollar

| Rol | Kim beradi | Imkoniyatlar |
|---|---|---|
| student | avtomatik (Google / Telegram login) | darslar, kunlik mashq, AI, kurs sotib olish, baho qo'yish (faqat sotib olgan ustozga) |
| teacher | admin `teachers` jadvaliga qo'shganda | kurs yaratish (admin tasdig'i bilan), statistika, o'z o'quvchilari |
| admin | SQL orqali qo'lda | ustozlar, kurslar, kunlik mashqlarni tasdiqlash, musobaqalar |

## Xavfsizlik tamoyillari

- Rol, XP, streak, to'lovlar va to'g'ri javoblarni brauzer o'zgartira olmaydi — faqat server funksiyalari.
- To'g'ri javoblar (`daily_item_keys`, `contest_keys`) klientga umuman ko'rinmaydi.
- Pullik video va jonli dars linklari (`lesson_secrets`) faqat kursga yozilganlarga ochiladi.
- Gemini kaliti faqat Edge Function secrets'da. `service_role` kaliti hech qachon frontendga tushmaydi.
- Ovoz yozuvlari saqlanmaydi — faqat transkript va baho.

## O'rnatish

```bash
npx supabase login
npx supabase link --project-ref <PROJECT_REF>
npx supabase db push

npx supabase secrets set \
  GEMINI_API_KEY=... \
  GEMINI_MODEL=<AI Studio'dagi model ID> \
  ALLOWED_ORIGINS=http://localhost:5173,https://<sayt> \
  CRON_SECRET=<uzun tasodifiy satr>

npx supabase functions deploy ai-solve
npx supabase functions deploy ai-grade
npx supabase functions deploy daily-generate --no-verify-jwt
```

Cron uchun SQL Editor'da (bir marta):

```sql
select vault.create_secret('https://<PROJECT_REF>.supabase.co', 'project_url');
select vault.create_secret('<CRON_SECRET bilan bir xil>', 'cron_secret');
```

Birinchi admin:

```sql
update profiles set role = 'admin' where id = '<user id>';
```

## Tekshirish

```bash
export SUPABASE_URL=https://<PROJECT_REF>.supabase.co
export SUPABASE_ANON_KEY=...
export TEST_EMAIL=... TEST_PASSWORD=...
export AUDIO_FILE=./javob.webm   # ixtiyoriy
bash tests/smoke.sh
```

## Eslatmalar

- Gemini bepul tarifi faqat demo uchun: limitlar kichik va yuborilgan ma'lumot Google mahsulotlarini yaxshilashda
  ishlatilishi mumkin. Haqiqiy o'quvchilar (ayniqsa bolalar) bilan ishlashdan oldin pullik tarifga o'ting.
- Musobaqada tab almashtirishni brauzer bloklay olmaydi — u aniqlanadi va `max_focus_loss` dan oshsa diskvalifikatsiya qilinadi.

## Holat

- [x] Ma'lumotlar bazasi sxemasi va RLS
- [x] AI yechish, kunlik mashq generatori, Writing/Speaking baholash
- [ ] Payme / Click webhook
- [ ] Telegram login
- [ ] Frontend (dashboard: o'quvchi, ustoz, admin)
