-- =====================================================================
-- 003: Kunlik mashq generatori — admin tekshiruvi uchun ruxsatlar + cron
-- =====================================================================

-- Admin tasdiqlashdan oldin to'g'ri javoblarni ko'rishi va tuzatishi kerak
create policy "admin javoblarni ko'radi" on public.daily_item_keys for select using (public.is_admin());
create policy "admin javoblarni tuzatadi" on public.daily_item_keys for update using (public.is_admin()) with check (public.is_admin());
create policy "admin savollarni tuzatadi" on public.daily_items for update using (public.is_admin()) with check (public.is_admin());
create policy "admin savolni o'chiradi" on public.daily_items for delete using (public.is_admin());
create policy "admin to'plamni o'chiradi" on public.daily_sets for delete using (public.is_admin());

-- Tasdiqlaganda kim tasdiqlaganini avtomatik yozish
create or replace function public.stamp_daily_review()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  if new.status is distinct from old.status and new.status in ('approved', 'rejected') then
    new.reviewed_by := auth.uid();
  end if;
  return new;
end $$;

create trigger on_daily_review
  before update on public.daily_sets
  for each row execute function public.stamp_daily_review();

-- ---------------------------------------------------------------------
-- Cron: Toshkent 18:00–20:55 (UTC 13:00–15:55) har 5 daqiqada.
-- Har chaqiruv ertangi kun uchun bitta yetishmayotgan to'plamni yaratadi.
-- 12 ta nishon → ~1 soatda tayyor; xato bo'lsa keyingi chaqiruv qayta urinadi.
--
-- OLDIN (bir marta, SQL Editor'da, qiymatlarni o'zingiznikiga almashtiring):
--   select vault.create_secret('https://<PROJECT-REF>.supabase.co', 'project_url');
--   select vault.create_secret('<CRON_SECRET bilan bir xil uzun tasodifiy satr>', 'cron_secret');
-- ---------------------------------------------------------------------
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'daily-generate',
  '*/5 13-15 * * *',
  $$
  select net.http_post(
    url     := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/daily-generate',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'cron_secret')
    ),
    body    := '{}'::jsonb,
    timeout_milliseconds := 120000
  );
  $$
);

-- Admin panel uchun: ertangi to'plamlar holati
create or replace view public.daily_review_queue with (security_invoker = true) as
  select s.id, s.set_date, s.subject, s.level, s.status, s.model, s.created_at,
         count(i.id) as items
  from public.daily_sets s left join public.daily_items i on i.set_id = s.id
  where s.set_date >= public.today_tashkent()
  group by s.id
  order by s.set_date, s.subject, s.level;
