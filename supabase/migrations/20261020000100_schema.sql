-- =====================================================================
-- Bicoordinate — Supabase sxemasi (v1, prototip asosida)
-- Ishga tushirish: Supabase → SQL Editor → shu faylni to'liq bajaring.
--
-- Asosiy qoidalar:
--   * Rol (student/teacher/admin) faqat admin yoki server tomonidan beriladi.
--   * XP, streak, to'g'ri javoblar, to'lovlar — faqat server funksiyalari orqali.
--     Brauzer bu ustunlarga to'g'ridan-to'g'ri yoza olmaydi.
--   * To'g'ri javoblar (keys) alohida jadvalda, klientga umuman ko'rinmaydi.
--   * Pullik video/jonli dars linklari faqat kursga yozilgan o'quvchiga ochiladi.
--   * To'lov webhook'lari (Payme/Click) va AI baholash — Edge Function'da,
--     service_role kaliti bilan. Bu kalit HECH QACHON frontendga tushmaydi.
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 0. ENUM turlari
-- ---------------------------------------------------------------------
create type public.user_role        as enum ('student', 'teacher', 'admin');
create type public.subject          as enum ('math', 'english');
create type public.cefr_level       as enum ('A1', 'A2', 'B1', 'B2', 'C1', 'C2');
create type public.skill            as enum ('listening', 'reading', 'writing', 'speaking', 'grammar', 'vocabulary', 'math');
create type public.course_status    as enum ('draft', 'review', 'active', 'archived');
create type public.billing_type     as enum ('one_time', 'monthly');
create type public.enroll_status    as enum ('active', 'expired', 'refunded');
create type public.payment_kind     as enum ('course', 'premium');
create type public.payment_status   as enum ('pending', 'paid', 'failed', 'refunded');
create type public.payment_provider as enum ('payme', 'click');
create type public.contract_status  as enum ('unsigned', 'active', 'suspended');
create type public.review_status    as enum ('pending_review', 'approved', 'rejected');
create type public.contest_status   as enum ('draft', 'scheduled', 'live', 'finished');
create type public.integrity_event  as enum ('blur', 'hidden', 'fullscreen_exit', 'paste', 'devtools');
create type public.teacher_event    as enum ('profile_view', 'buy_page_view', 'contact_click');

-- Toshkent bo'yicha "bugun" (kunlik mashq va streak shu sanaga bog'lanadi)
create or replace function public.today_tashkent()
returns date language sql stable
as $$ select (now() at time zone 'Asia/Tashkent')::date $$;

-- ---------------------------------------------------------------------
-- 1. PROFILLAR VA ROLLAR
-- ---------------------------------------------------------------------
create table public.profiles (
  id               uuid primary key references auth.users(id) on delete cascade,
  role             public.user_role not null default 'student',
  full_name        text not null default '',
  avatar_url       text,
  telegram_id      bigint unique,                 -- Telegram login uchun
  english_level    public.cefr_level default 'A1',
  math_grade       smallint check (math_grade between 1 and 11),
  xp               integer not null default 0 check (xp >= 0),
  streak           integer not null default 0,
  last_active_date date,
  created_at       timestamptz not null default now()
);

-- Yangi foydalanuvchi (Google yoki Telegram) → avtomatik profil
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', ''),
    new.raw_user_meta_data ->> 'avatar_url'
  );
  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Rol tekshiruvchi yordamchilar (RLS ichida ishlatiladi)
create or replace function public.my_role()
returns public.user_role language sql stable security definer set search_path = ''
as $$ select role from public.profiles where id = auth.uid() $$;

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = ''
as $$ select coalesce((select role = 'admin' from public.profiles where id = auth.uid()), false) $$;

-- Ustozlar: faqat admin qo'shadi (shartnoma, komissiya)
create table public.teachers (
  id               uuid primary key references public.profiles(id) on delete cascade,
  display_name     text not null,
  bio              text not null default '',
  subject          public.subject not null,
  youtube_channel  text,
  commission_pct   numeric(5,2) not null default 20 check (commission_pct between 0 and 100),
  contract_status  public.contract_status not null default 'unsigned',
  contract_until   date,
  created_by       uuid references public.profiles(id),
  created_at       timestamptz not null default now()
);

-- Admin ustoz qo'shganda profil roli ham 'teacher' bo'ladi
create or replace function public.sync_teacher_role()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  update public.profiles set role = 'teacher' where id = new.id and role = 'student';
  return new;
end $$;

create trigger on_teacher_created
  after insert on public.teachers
  for each row execute function public.sync_teacher_role();

-- ---------------------------------------------------------------------
-- 2. KURSLAR, DARSLAR, VIDEOLAR
-- ---------------------------------------------------------------------
create table public.courses (
  id           uuid primary key default gen_random_uuid(),
  teacher_id   uuid not null references public.teachers(id) on delete cascade,
  title        text not null,
  description  text not null default '',
  subject      public.subject not null,
  level        public.cefr_level,                -- ingliz tili uchun
  grade_from   smallint, grade_to smallint,      -- matematika uchun
  price_uzs    bigint not null check (price_uzs >= 0),
  billing      public.billing_type not null default 'one_time',
  status       public.course_status not null default 'draft',
  created_at   timestamptz not null default now()
);
create index on public.courses (teacher_id);
create index on public.courses (status, subject);

-- Dars ma'lumoti (hammaga ko'rinadi: sarlavha, tartib, sana)
create table public.course_lessons (
  id          uuid primary key default gen_random_uuid(),
  course_id   uuid not null references public.courses(id) on delete cascade,
  position    integer not null,
  title       text not null,
  is_preview  boolean not null default false,   -- bepul ko'rsatiladigan dars
  live_at     timestamptz,                      -- jonli dars bo'lsa
  unique (course_id, position)
);

-- Maxfiy qism: himoyalangan video ID (Bunny/Vimeo) va jonli dars linki.
-- Faqat kursga yozilgan o'quvchi, kurs ustozi va admin o'qiy oladi.
create table public.lesson_secrets (
  lesson_id     uuid primary key references public.course_lessons(id) on delete cascade,
  video_provider text check (video_provider in ('bunny', 'vimeo', 'mux', 'youtube')),
  video_ref     text,
  meeting_url   text
);

-- Bepul videolar (YouTube) — admin qo'shadi
create table public.free_videos (
  id          uuid primary key default gen_random_uuid(),
  youtube_id  text not null unique,
  title       text not null,
  subject     public.subject not null,
  topic       text not null,
  level       public.cefr_level,
  grade       smallint,
  teacher_id  uuid references public.teachers(id) on delete set null,
  added_by    uuid references public.profiles(id),
  created_at  timestamptz not null default now()
);

create table public.video_progress (
  user_id       uuid not null references public.profiles(id) on delete cascade,
  free_video_id uuid references public.free_videos(id) on delete cascade,
  lesson_id     uuid references public.course_lessons(id) on delete cascade,
  progress_pct  smallint not null default 0 check (progress_pct between 0 and 100),
  updated_at    timestamptz not null default now(),
  check ((free_video_id is null) <> (lesson_id is null))
);
create unique index on public.video_progress (user_id, free_video_id) where free_video_id is not null;
create unique index on public.video_progress (user_id, lesson_id) where lesson_id is not null;

-- ---------------------------------------------------------------------
-- 3. TO'LOVLAR, YOZILISHLAR, PREMIUM
-- ---------------------------------------------------------------------
-- Faqat Edge Function (Payme/Click webhook, service_role) yozadi.
create table public.payments (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles(id),
  kind             public.payment_kind not null,
  course_id        uuid references public.courses(id),
  amount_uzs       bigint not null check (amount_uzs > 0),
  commission_uzs   bigint not null default 0,      -- platforma ulushi
  provider         public.payment_provider not null,
  provider_txn_id  text unique,
  status           public.payment_status not null default 'pending',
  created_at       timestamptz not null default now(),
  paid_at          timestamptz,
  check ((kind = 'course') = (course_id is not null))
);
create index on public.payments (course_id);

create table public.enrollments (
  id          uuid primary key default gen_random_uuid(),
  student_id  uuid not null references public.profiles(id) on delete cascade,
  course_id   uuid not null references public.courses(id) on delete cascade,
  payment_id  uuid references public.payments(id),
  status      public.enroll_status not null default 'active',
  starts_at   timestamptz not null default now(),
  expires_at  timestamptz,                       -- oylik kurslar uchun
  unique (student_id, course_id)
);
create index on public.enrollments (course_id);

create table public.premium_subscriptions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  payment_id  uuid references public.payments(id),
  starts_at   timestamptz not null default now(),
  expires_at  timestamptz not null
);
create index on public.premium_subscriptions (user_id, expires_at);

create or replace function public.is_premium(uid uuid default auth.uid())
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.premium_subscriptions
                 where user_id = uid and now() between starts_at and expires_at)
$$;

create or replace function public.is_enrolled(p_course uuid, uid uuid default auth.uid())
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.enrollments
                 where course_id = p_course and student_id = uid and status = 'active'
                   and (expires_at is null or expires_at > now()))
$$;

create or replace function public.owns_course(p_course uuid, uid uuid default auth.uid())
returns boolean language sql stable security definer set search_path = ''
as $$ select exists (select 1 from public.courses where id = p_course and teacher_id = uid) $$;

-- ---------------------------------------------------------------------
-- 4. REYTING (faqat haqiqiy o'quvchi, har ustozga bitta baho)
-- ---------------------------------------------------------------------
create table public.ratings (
  student_id  uuid not null references public.profiles(id) on delete cascade,
  teacher_id  uuid not null references public.teachers(id) on delete cascade,
  stars       smallint not null check (stars between 1 and 5),
  comment     text check (char_length(comment) <= 1000),
  flagged     boolean not null default false,     -- admin moderatsiyasi
  flag_reason text,
  created_at  timestamptz not null default now(),
  primary key (student_id, teacher_id)
);

-- Baho qo'yish huquqi: shu ustozning kursini sotib olgan bo'lishi shart
create or replace function public.can_rate(p_teacher uuid, uid uuid default auth.uid())
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.enrollments e join public.courses c on c.id = e.course_id
    where e.student_id = uid and c.teacher_id = p_teacher and e.status in ('active', 'expired')
  )
$$;

create view public.teacher_ratings with (security_invoker = true) as
  select teacher_id, round(avg(stars)::numeric, 1) as avg_stars, count(*) as votes
  from public.ratings where not flagged group by teacher_id;

-- Ustoz statistikasi uchun hodisalar (profil ko'rish → sotib olish sahifasi)
create table public.teacher_events (
  id          bigint generated always as identity primary key,
  teacher_id  uuid not null references public.teachers(id) on delete cascade,
  viewer_id   uuid references public.profiles(id) on delete set null,
  kind        public.teacher_event not null,
  at          timestamptz not null default now()
);
create index on public.teacher_events (teacher_id, at);

-- ---------------------------------------------------------------------
-- 5. KUNLIK MASHQLAR (AI yaratadi, admin tasdiqlaydi, hammaga bitta to'plam)
-- ---------------------------------------------------------------------
create table public.daily_sets (
  id          uuid primary key default gen_random_uuid(),
  set_date    date not null,
  subject     public.subject not null,
  level       text not null,                    -- 'B1' yoki matematika uchun '7-sinf'
  status      public.review_status not null default 'pending_review',
  model       text,                             -- masalan 'gemini-...'
  reviewed_by uuid references public.profiles(id),
  created_at  timestamptz not null default now(),
  unique (set_date, subject, level)
);

-- Savol (klientga ko'rinadi, javobsiz)
create table public.daily_items (
  id        uuid primary key default gen_random_uuid(),
  set_id    uuid not null references public.daily_sets(id) on delete cascade,
  position  smallint not null,
  skill     public.skill not null,
  prompt    jsonb not null,     -- {"text": "...", "options": ["a","b","c","d"], "audio_url": ...}
  xp        smallint not null default 20,
  unique (set_id, position)
);

-- To'g'ri javob — klientga HECH QACHON ko'rinmaydi (RLS: siyosat yo'q)
create table public.daily_item_keys (
  item_id  uuid primary key references public.daily_items(id) on delete cascade,
  answer   jsonb not null       -- {"choice": 1} yoki {"value": "6"}
);

create table public.attempts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  item_id     uuid not null references public.daily_items(id) on delete cascade,
  answer      jsonb not null,
  is_correct  boolean,
  ai_score    numeric(4,1),      -- writing/speaking: AI bahosi (Edge Function yozadi)
  ai_feedback text,
  xp_awarded  smallint not null default 0,
  created_at  timestamptz not null default now(),
  unique (user_id, item_id)      -- bitta savolga bitta urinish
);

-- ---------------------------------------------------------------------
-- 6. XP DAFTARI, STREAK, REYTING JADVALI
-- ---------------------------------------------------------------------
create table public.xp_events (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references public.profiles(id) on delete cascade,
  amount      integer not null,
  reason      text not null,     -- 'daily_item', 'contest', 'video_complete' ...
  ref_id      uuid,
  created_at  timestamptz not null default now()
);
create index on public.xp_events (user_id, created_at);
create index on public.xp_events (created_at);

create or replace function public.apply_xp()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  update public.profiles set xp = greatest(0, xp + new.amount) where id = new.user_id;
  return new;
end $$;

create trigger on_xp_event
  after insert on public.xp_events
  for each row execute function public.apply_xp();

create or replace function public.touch_streak(uid uuid)
returns void language plpgsql security definer set search_path = ''
as $$
declare d date := public.today_tashkent();
begin
  update public.profiles set
    streak = case when last_active_date = d then streak
                  when last_active_date = d - 1 then streak + 1
                  else 1 end,
    last_active_date = d
  where id = uid;
end $$;

-- Kunlik savolga javob: server tekshiradi, XP beradi. Klient faqat shuni chaqiradi.
-- (writing/speaking bu yerda emas — AI baholaydigan Edge Function orqali)
create or replace function public.submit_daily_answer(p_item uuid, p_answer jsonb)
returns table (is_correct boolean, correct_answer jsonb, xp_awarded integer)
language plpgsql security definer set search_path = ''
as $$
declare
  v_key   jsonb;
  v_xp    smallint;
  v_skill public.skill;
  v_ok    boolean;
  v_set   public.daily_sets%rowtype;
begin
  if auth.uid() is null then raise exception 'login talab qilinadi'; end if;

  select s.* into v_set from public.daily_sets s
    join public.daily_items i on i.set_id = s.id where i.id = p_item;
  if not found or v_set.status <> 'approved' or v_set.set_date <> public.today_tashkent() then
    raise exception 'bu savol bugun uchun ochiq emas';
  end if;

  select i.xp, i.skill, k.answer into v_xp, v_skill, v_key
    from public.daily_items i left join public.daily_item_keys k on k.item_id = i.id
    where i.id = p_item;
  if v_skill in ('writing', 'speaking') then
    raise exception 'writing/speaking AI orqali baholanadi';
  end if;
  if v_key is null then
    raise exception 'savolning javob kaliti yo''q';
  end if;

  v_ok := (p_answer = v_key);

  insert into public.attempts (user_id, item_id, answer, is_correct, xp_awarded)
  values (auth.uid(), p_item, p_answer, v_ok, case when v_ok then v_xp else 0 end);
  -- unique (user_id, item_id) qayta urinishni avtomatik bloklaydi

  if v_ok then
    insert into public.xp_events (user_id, amount, reason, ref_id)
    values (auth.uid(), v_xp, 'daily_item', p_item);
  end if;
  perform public.touch_streak(auth.uid());

  return query select v_ok, v_key, case when v_ok then v_xp::integer else 0 end;
end $$;

-- Haftalik reyting (dushanbadan, Toshkent vaqti). Faqat ism va XP qaytaradi.
create or replace function public.weekly_leaderboard(p_limit int default 50)
returns table (pos bigint, user_id uuid, full_name text, week_xp bigint)
language sql stable security definer set search_path = ''
as $$
  select rank() over (order by sum(x.amount) desc), x.user_id, p.full_name, sum(x.amount)
  from public.xp_events x join public.profiles p on p.id = x.user_id
  where x.created_at >= (date_trunc('week', now() at time zone 'Asia/Tashkent') at time zone 'Asia/Tashkent')
  group by x.user_id, p.full_name
  order by 4 desc
  limit least(p_limit, 100)
$$;

-- ---------------------------------------------------------------------
-- 7. AI LIMITLARI
-- ---------------------------------------------------------------------
create table public.ai_usage (
  user_id  uuid not null references public.profiles(id) on delete cascade,
  day      date not null default public.today_tashkent(),
  kind     text not null check (kind in ('solve', 'writing', 'speaking')),
  count    integer not null default 0,
  primary key (user_id, day, kind)
);

-- Edge Function Gemini'ni chaqirishdan OLDIN shuni chaqiradi; false → rad etadi.
create or replace function public.consume_ai_quota(p_kind text)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare
  v_limit int;
  v_count int;
begin
  if auth.uid() is null then return false; end if;
  v_limit := case p_kind
    when 'solve'    then case when public.is_premium() then 100 else 20 end
    when 'writing'  then case when public.is_premium() then 10  else 3  end
    when 'speaking' then case when public.is_premium() then 10  else 2  end
    else 0 end;

  insert into public.ai_usage as u (user_id, day, kind, count)
  values (auth.uid(), public.today_tashkent(), p_kind, 1)
  on conflict (user_id, day, kind) do update set count = u.count + 1
  returning count into v_count;

  if v_count > v_limit then
    update public.ai_usage set count = count - 1
      where user_id = auth.uid() and day = public.today_tashkent() and kind = p_kind;
    return false;
  end if;
  return true;
end $$;

-- ---------------------------------------------------------------------
-- 8. MUSOBAQA (premium o'quvchilar, individual; ustozlar o'quvchilari o'rni bo'yicha)
-- ---------------------------------------------------------------------
create table public.contests (
  id            uuid primary key default gen_random_uuid(),
  title         text not null,
  subject       public.subject not null,
  level         text not null,
  starts_at     timestamptz not null,
  ends_at       timestamptz not null,
  duration_sec  integer not null check (duration_sec > 0),  -- har ishtirokchiga vaqt
  max_focus_loss smallint not null default 2,               -- shundan oshsa — diskvalifikatsiya
  premium_only  boolean not null default true,
  prizes        jsonb not null default '[]',
  status        public.contest_status not null default 'draft',
  created_by    uuid references public.profiles(id),
  check (ends_at > starts_at)
);

create table public.contest_questions (
  id          uuid primary key default gen_random_uuid(),
  contest_id  uuid not null references public.contests(id) on delete cascade,
  position    smallint not null,
  prompt      jsonb not null,
  points      smallint not null default 1,
  unique (contest_id, position)
);

create table public.contest_keys (
  question_id uuid primary key references public.contest_questions(id) on delete cascade,
  answer      jsonb not null
);

create table public.contest_entries (
  contest_id        uuid not null references public.contests(id) on delete cascade,
  user_id           uuid not null references public.profiles(id) on delete cascade,
  started_at        timestamptz not null default now(),
  finished_at       timestamptz,
  score             integer not null default 0,
  time_ms           integer,
  focus_lost_count  smallint not null default 0,
  disqualified      boolean not null default false,
  primary key (contest_id, user_id)
);

create table public.contest_answers (
  contest_id   uuid not null,
  user_id      uuid not null,
  question_id  uuid not null references public.contest_questions(id) on delete cascade,
  answer       jsonb not null,
  is_correct   boolean not null,
  answered_at  timestamptz not null default now(),
  primary key (contest_id, user_id, question_id),
  foreign key (contest_id, user_id) references public.contest_entries(contest_id, user_id) on delete cascade
);

create table public.contest_integrity_log (
  id          bigint generated always as identity primary key,
  contest_id  uuid not null,
  user_id     uuid not null,
  kind        public.integrity_event not null,
  at          timestamptz not null default now(),
  foreign key (contest_id, user_id) references public.contest_entries(contest_id, user_id) on delete cascade
);

-- Boshlash: premium va vaqt oynasini tekshiradi, savollarni (javobsiz) qaytaradi
create or replace function public.start_contest(p_contest uuid)
returns table (question_id uuid, q_position smallint, prompt jsonb, deadline timestamptz)
language plpgsql security definer set search_path = ''
as $$
declare
  c public.contests%rowtype;
  e public.contest_entries%rowtype;
begin
  select * into c from public.contests where id = p_contest;
  if c.id is null or c.status <> 'live' or now() not between c.starts_at and c.ends_at then
    raise exception 'musobaqa hozir ochiq emas';
  end if;
  if c.premium_only and not public.is_premium() then
    raise exception 'faqat premium obunachilar uchun';
  end if;

  insert into public.contest_entries (contest_id, user_id) values (p_contest, auth.uid())
  on conflict do nothing;
  select * into e from public.contest_entries where contest_id = p_contest and user_id = auth.uid();
  if e.finished_at is not null or e.disqualified then raise exception 'ishtirok yakunlangan'; end if;

  return query
    select q.id, q.position, q.prompt, e.started_at + make_interval(secs => c.duration_sec)
    from public.contest_questions q where q.contest_id = p_contest order by q.position;
end $$;

create or replace function public.submit_contest_answer(p_contest uuid, p_question uuid, p_answer jsonb)
returns void language plpgsql security definer set search_path = ''
as $$
declare
  e public.contest_entries%rowtype;
  v_dur int;
  v_key jsonb;
begin
  select * into e from public.contest_entries where contest_id = p_contest and user_id = auth.uid();
  select duration_sec into v_dur from public.contests where id = p_contest;
  if e.user_id is null or e.finished_at is not null or e.disqualified
     or now() > e.started_at + make_interval(secs => v_dur) then
    raise exception 'javob qabul qilinmaydi';
  end if;
  select k.answer into v_key from public.contest_keys k
    join public.contest_questions q on q.id = k.question_id
    where k.question_id = p_question and q.contest_id = p_contest;
  if v_key is null then raise exception 'savol topilmadi'; end if;

  insert into public.contest_answers (contest_id, user_id, question_id, answer, is_correct)
  values (p_contest, auth.uid(), p_question, p_answer, p_answer = v_key);
  -- primary key qayta javob berishni bloklaydi
end $$;

create or replace function public.finish_contest(p_contest uuid)
returns integer language plpgsql security definer set search_path = ''
as $$
declare v_score int;
begin
  select coalesce(sum(q.points), 0) into v_score
    from public.contest_answers a join public.contest_questions q on q.id = a.question_id
    where a.contest_id = p_contest and a.user_id = auth.uid() and a.is_correct;

  update public.contest_entries set
    finished_at = now(),
    score = v_score,
    time_ms = (extract(epoch from (now() - started_at)) * 1000)::int
  where contest_id = p_contest and user_id = auth.uid() and finished_at is null;
  return v_score;
end $$;

-- Tab almashtirish brauzerda BLOKLANMAYDI — faqat aniqlanadi va jazolanadi.
-- Frontend: visibilitychange / blur / fullscreenchange hodisalarida shuni chaqiradi.
create or replace function public.log_contest_event(p_contest uuid, p_kind public.integrity_event)
returns boolean   -- true = diskvalifikatsiya qilindi
language plpgsql security definer set search_path = ''
as $$
declare v_dq boolean;
begin
  insert into public.contest_integrity_log (contest_id, user_id, kind)
  values (p_contest, auth.uid(), p_kind);

  update public.contest_entries e set
    focus_lost_count = focus_lost_count + 1,
    disqualified = (focus_lost_count + 1) > (select max_focus_loss from public.contests where id = p_contest)
  where e.contest_id = p_contest and e.user_id = auth.uid() and e.finished_at is null
  returning disqualified into v_dq;
  return coalesce(v_dq, false);
end $$;

-- Natijalar: ball ↓, vaqt ↑, diskvalifikatsiya qilinganlar chiqarib tashlanadi
create or replace function public.contest_results(p_contest uuid)
returns table (pos bigint, user_id uuid, full_name text, score int, time_ms int)
language sql stable security definer set search_path = ''
as $$
  select rank() over (order by e.score desc, e.time_ms asc), e.user_id, p.full_name, e.score, e.time_ms
  from public.contest_entries e join public.profiles p on p.id = e.user_id
  join public.contests c on c.id = e.contest_id
  where e.contest_id = p_contest and e.finished_at is not null and not e.disqualified
    and (c.status = 'finished' or public.is_admin())
  order by 1
$$;

-- Ustozlar bo'yicha: top-N ichida qaysi ustozning o'quvchilari ko'p.
-- O'quvchi bir nechta ustozga yozilgan bo'lsa — har biriga hisoblanadi.
create or replace function public.contest_teacher_standings(p_contest uuid, p_top int default 10)
returns table (teacher_id uuid, display_name text, students_in_top bigint, best_pos bigint)
language sql stable security definer set search_path = ''
as $$
  with top as (select * from public.contest_results(p_contest) where pos <= p_top),
       c as (select starts_at from public.contests where id = p_contest)
  select t.id, t.display_name, count(distinct top.user_id), min(top.pos)
  from top
  join public.enrollments e on e.student_id = top.user_id
  join public.courses co on co.id = e.course_id
  join public.teachers t on t.id = co.teacher_id
  cross join c
  where e.starts_at <= c.starts_at and (e.expires_at is null or e.expires_at >= c.starts_at)
  group by t.id, t.display_name
  order by 3 desc, 4 asc
$$;

-- =====================================================================
-- 9. ROW LEVEL SECURITY
-- =====================================================================
alter table public.profiles              enable row level security;
alter table public.teachers              enable row level security;
alter table public.courses               enable row level security;
alter table public.course_lessons        enable row level security;
alter table public.lesson_secrets        enable row level security;
alter table public.free_videos           enable row level security;
alter table public.video_progress        enable row level security;
alter table public.payments              enable row level security;
alter table public.enrollments           enable row level security;
alter table public.premium_subscriptions enable row level security;
alter table public.ratings               enable row level security;
alter table public.teacher_events        enable row level security;
alter table public.daily_sets            enable row level security;
alter table public.daily_items           enable row level security;
alter table public.daily_item_keys       enable row level security;  -- siyosat yo'q = hech kim
alter table public.attempts              enable row level security;
alter table public.xp_events             enable row level security;
alter table public.ai_usage              enable row level security;
alter table public.contests              enable row level security;
alter table public.contest_questions     enable row level security;
alter table public.contest_keys          enable row level security;  -- siyosat yo'q = hech kim
alter table public.contest_entries       enable row level security;
alter table public.contest_answers       enable row level security;
alter table public.contest_integrity_log enable row level security;

-- profiles: o'zini o'qiydi/tahrirlaydi; boshqalarning faqat ismi ko'rinishi uchun public view pastda
create policy "o'z profili" on public.profiles for select using (id = auth.uid() or public.is_admin());
create policy "o'z profilini tahrirlash" on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());
create policy "admin profillarni boshqaradi" on public.profiles for update using (public.is_admin());
-- Muhim: oddiy foydalanuvchi role/xp/streak ni o'zgartira olmasligi uchun ustun darajasida cheklov
revoke update on public.profiles from authenticated, anon;
grant update (full_name, avatar_url, english_level, math_grade) on public.profiles to authenticated;

-- teachers: hamma ko'radi (faol shartnoma), faqat admin yozadi, ustoz bio'sini tahrirlaydi
create policy "faol ustozlar ochiq" on public.teachers for select
  using (contract_status = 'active' or id = auth.uid() or public.is_admin());
create policy "admin ustoz qo'shadi" on public.teachers for insert with check (public.is_admin());
create policy "admin ustozni tahrirlaydi" on public.teachers for update using (public.is_admin());
create policy "ustoz o'z profilini" on public.teachers for update using (id = auth.uid()) with check (id = auth.uid());
revoke update on public.teachers from authenticated;
grant update (display_name, bio, youtube_channel) on public.teachers to authenticated;
-- (admin komissiya/shartnomani service_role yoki admin Edge Function orqali o'zgartiradi)

-- courses: faol kurslar hammaga; ustoz o'zinikini yaratadi (draft/review), faollashtirish — admin
create policy "faol kurslar ochiq" on public.courses for select
  using (status = 'active' or teacher_id = auth.uid() or public.is_admin());
create policy "ustoz kurs yaratadi" on public.courses for insert
  with check (teacher_id = auth.uid() and status in ('draft', 'review'));
create policy "ustoz o'z kursini tahrirlaydi" on public.courses for update
  using (teacher_id = auth.uid() and status in ('draft', 'review'))
  with check (teacher_id = auth.uid() and status in ('draft', 'review'));
create policy "admin kurslarni boshqaradi" on public.courses for all using (public.is_admin()) with check (public.is_admin());

create policy "dars ro'yxati ochiq" on public.course_lessons for select
  using (exists (select 1 from public.courses c where c.id = course_id
                 and (c.status = 'active' or c.teacher_id = auth.uid() or public.is_admin())));
create policy "ustoz darslarini boshqaradi" on public.course_lessons for all
  using (public.owns_course(course_id) or public.is_admin())
  with check (public.owns_course(course_id) or public.is_admin());

create policy "maxfiy link faqat yozilganlarga" on public.lesson_secrets for select
  using (exists (select 1 from public.course_lessons l where l.id = lesson_id
                 and (l.is_preview or public.is_enrolled(l.course_id)
                      or public.owns_course(l.course_id) or public.is_admin())));
create policy "ustoz maxfiy linklarni boshqaradi" on public.lesson_secrets for all
  using (exists (select 1 from public.course_lessons l where l.id = lesson_id
                 and (public.owns_course(l.course_id) or public.is_admin())))
  with check (exists (select 1 from public.course_lessons l where l.id = lesson_id
                 and (public.owns_course(l.course_id) or public.is_admin())));

create policy "bepul videolar ochiq" on public.free_videos for select using (true);
create policy "admin video qo'shadi" on public.free_videos for all using (public.is_admin()) with check (public.is_admin());

create policy "o'z progressi" on public.video_progress for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- payments: o'zi ko'radi; ustoz o'z kurslari bo'yicha; YOZISH faqat service_role (siyosat yo'q)
create policy "o'z to'lovlari" on public.payments for select
  using (user_id = auth.uid() or public.is_admin()
         or (course_id is not null and public.owns_course(course_id)));

create policy "yozilishlarni ko'rish" on public.enrollments for select
  using (student_id = auth.uid() or public.owns_course(course_id) or public.is_admin());

create policy "o'z premiumi" on public.premium_subscriptions for select
  using (user_id = auth.uid() or public.is_admin());

-- ratings: hamma o'qiydi (bayroqlanmaganlar), faqat kurs sotib olgan baho qo'yadi
create policy "baholar ochiq" on public.ratings for select using (not flagged or public.is_admin() or student_id = auth.uid());
create policy "faqat haqiqiy o'quvchi baholaydi" on public.ratings for insert
  with check (student_id = auth.uid() and public.can_rate(teacher_id));
create policy "o'z bahosini o'zgartirish" on public.ratings for update
  using (student_id = auth.uid()) with check (student_id = auth.uid() and public.can_rate(teacher_id));
create policy "admin moderatsiya" on public.ratings for update using (public.is_admin());
revoke update on public.ratings from authenticated;
grant update (stars, comment) on public.ratings to authenticated;
-- (flagged/flag_reason ni admin service_role orqali o'zgartiradi)

create policy "hodisa yozish" on public.teacher_events for insert
  with check (viewer_id is null or viewer_id = auth.uid());
create policy "ustoz o'z statistikasini ko'radi" on public.teacher_events for select
  using (teacher_id = auth.uid() or public.is_admin());

-- daily: tasdiqlangan to'plamlar hammaga; keys — hech kimga
create policy "tasdiqlangan to'plamlar" on public.daily_sets for select
  using (status = 'approved' or public.is_admin());
create policy "admin to'plamni tasdiqlaydi" on public.daily_sets for update using (public.is_admin());
create policy "tasdiqlangan savollar" on public.daily_items for select
  using (exists (select 1 from public.daily_sets s where s.id = set_id
                 and (s.status = 'approved' or public.is_admin())));

create policy "o'z urinishlari" on public.attempts for select using (user_id = auth.uid() or public.is_admin());
create policy "o'z XP tarixi" on public.xp_events for select using (user_id = auth.uid() or public.is_admin());
create policy "o'z AI limiti" on public.ai_usage for select using (user_id = auth.uid() or public.is_admin());

-- contests
create policy "e'lon qilingan musobaqalar" on public.contests for select
  using (status <> 'draft' or public.is_admin());
create policy "admin musobaqani boshqaradi" on public.contests for all using (public.is_admin()) with check (public.is_admin());
-- Savollar to'g'ridan-to'g'ri o'qilmaydi — faqat start_contest() orqali (oldindan ko'rib qo'yishning oldini oladi)
create policy "admin savollarni ko'radi" on public.contest_questions for select using (public.is_admin());
create policy "o'z ishtiroki" on public.contest_entries for select using (user_id = auth.uid() or public.is_admin());
create policy "o'z javoblari" on public.contest_answers for select using (user_id = auth.uid() or public.is_admin());
create policy "admin integrity log" on public.contest_integrity_log for select using (public.is_admin());

-- Ustoz kartochkalari uchun ochiq ko'rinish (faqat ism va avatar)
create view public.public_profiles as
  select id, full_name, avatar_url from public.profiles;
grant select on public.public_profiles to authenticated;

-- Funksiyalar faqat login qilganlarga
revoke execute on function public.submit_daily_answer(uuid, jsonb)            from anon, public;
revoke execute on function public.consume_ai_quota(text)                      from anon, public;
revoke execute on function public.start_contest(uuid)                         from anon, public;
revoke execute on function public.submit_contest_answer(uuid, uuid, jsonb)    from anon, public;
revoke execute on function public.finish_contest(uuid)                        from anon, public;
revoke execute on function public.log_contest_event(uuid, public.integrity_event) from anon, public;
revoke execute on function public.touch_streak(uuid)                          from anon, public, authenticated;
grant  execute on function public.submit_daily_answer(uuid, jsonb)            to authenticated;
grant  execute on function public.consume_ai_quota(text)                      to authenticated;
grant  execute on function public.start_contest(uuid)                         to authenticated;
grant  execute on function public.submit_contest_answer(uuid, uuid, jsonb)    to authenticated;
grant  execute on function public.finish_contest(uuid)                        to authenticated;
grant  execute on function public.log_contest_event(uuid, public.integrity_event) to authenticated;
