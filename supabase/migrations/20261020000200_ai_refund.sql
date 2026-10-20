-- AI so'rovi xato bilan tugasa (Gemini band, timeout, noto'g'ri javob) limitni qaytarish.
-- Faqat Edge Function (service_role) chaqira oladi.
create or replace function public.refund_ai_quota(p_user uuid, p_kind text)
returns void language sql security definer set search_path = ''
as $$
  update public.ai_usage set count = greatest(0, count - 1)
  where user_id = p_user and day = public.today_tashkent() and kind = p_kind
$$;

revoke execute on function public.refund_ai_quota(uuid, text) from public, anon, authenticated;
grant  execute on function public.refund_ai_quota(uuid, text) to service_role;
