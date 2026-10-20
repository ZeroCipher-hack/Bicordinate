-- =====================================================================
-- 004: Writing / Speaking baholash natijasini yozish (faqat ai-grade Edge Function)
-- Bitta tranzaksiyada: urinish + XP + streak. Qayta topshirish unique bilan bloklanadi.
-- =====================================================================

create or replace function public.record_ai_attempt(
  p_user     uuid,
  p_item     uuid,
  p_answer   jsonb,
  p_score    numeric,
  p_feedback jsonb,
  p_xp       integer
)
returns void language plpgsql security definer set search_path = ''
as $$
declare v_max smallint;
begin
  select xp into v_max from public.daily_items where id = p_item;
  if v_max is null then raise exception 'savol topilmadi'; end if;

  insert into public.attempts (user_id, item_id, answer, is_correct, ai_score, ai_feedback, xp_awarded)
  values (p_user, p_item, p_answer, null, p_score, p_feedback::text, least(greatest(p_xp, 0), v_max));

  if p_xp > 0 then
    insert into public.xp_events (user_id, amount, reason, ref_id)
    values (p_user, least(p_xp, v_max), 'ai_graded', p_item);
  end if;
  perform public.touch_streak(p_user);
end $$;

revoke execute on function public.record_ai_attempt(uuid, uuid, jsonb, numeric, jsonb, integer) from public, anon, authenticated;
grant  execute on function public.record_ai_attempt(uuid, uuid, jsonb, numeric, jsonb, integer) to service_role;


-- TUZATISH: submit_daily_answer kaliti yo'q savolni (writing/speaking) rad etmay,
-- 0 ball bilan yozib qo'yardi va o'quvchining AI baholash imkonini yopib qo'yardi.
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
