-- =====================================================================
-- 005: To'lov holatlarini to'liq tekshirish (Payme va Click)
-- Payme: state 1=pending, 2=completed, -1=canceled, -2=timeout
-- Click: state 0=pending, 1=completed, -1=canceled
-- =====================================================================

alter table public.payments add column if not exists
  state        smallint not null default 0,  -- 0=pending, 1=completed, -1=canceled, -2=timeout (Payme) yoki -9 (Click xato)
  create_time  bigint,                        -- Payme: unix ms
  perform_time bigint,                        -- Tasdiqlanish vaqti (unix ms)
  cancel_time  bigint,                        -- Bekor qilish vaqti (unix ms)
  reason       text;                          -- Bekor qilish sababi

create index on public.payments (state, created_at);
create index on public.payments (provider, provider_txn_id, state);
