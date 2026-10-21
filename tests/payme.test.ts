// Payme Merchant API unit tests
// Har bir test Payme hujjatidagi namunaviy so'rovlar bilan

import md5 from "npm:md5@2.3.0";

const PAYME_KEY = "test_key_12345";
const BASE_URL = "http://localhost:54321/functions/v1/payme-merchant";

function basicAuth(): string {
  return "Basic " + btoa(`Paycom:${PAYME_KEY}`);
}

async function paymeCall(method: string, params: Record<string, unknown>, id: number) {
  const body = JSON.stringify({
    jsonrpc: "2.0",
    method,
    params,
    id,
  });

  return fetch(BASE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: basicAuth(),
    },
    body,
  }).then((r) => r.json());
}

// Test 1: Noto'g'ri auth
Deno.test("Payme: Noto'g'ri auth", async () => {
  const res = await fetch(BASE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Basic " + btoa("Paycom:wrong_key"),
    },
    body: JSON.stringify({ jsonrpc: "2.0", method: "CheckTransaction", id: 1 }),
  }).then((r) => r.json());

  if (res.error?.code !== -32504) {
    throw new Error(`Expected -32504, got ${res.error?.code}`);
  }
});

// Test 2: CheckPerformTransaction — topilmagan to'lov
Deno.test("Payme: CheckPerformTransaction — topilmagan to'lov", async () => {
  const res = await paymeCall("CheckPerformTransaction", {
    account: { merchant_trans_id: "nonexistent_123" },
    amount: 100000,
    time: Date.now(),
  }, 1);

  if (res.error?.code !== -31003) {
    throw new Error(`Expected -31003 (not found), got ${res.error?.code}`);
  }
});

// Test 3: CheckPerformTransaction — summa mos kelmasa
Deno.test("Payme: CheckPerformTransaction — summa mos kelmasa", async () => {
  // Avval yaratish
  const createRes = await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: "test_amount_mismatch" },
    amount: 100000,
    time: Date.now(),
  }, 1);

  if (!createRes.result) {
    throw new Error("CreateTransaction failed");
  }

  // Noto'g'ri summasi bilan tekshirish
  const checkRes = await paymeCall("CheckPerformTransaction", {
    account: { merchant_trans_id: "test_amount_mismatch" },
    amount: 200000, // Noto'g'ri
    time: Date.now(),
  }, 2);

  if (checkRes.error?.code !== -31001) {
    throw new Error(`Expected -31001 (amount mismatch), got ${checkRes.error?.code}`);
  }
});

// Test 4: Idempotency — qayta chaqiruv
Deno.test("Payme: Idempotency — qayta CreateTransaction", async () => {
  const merchantId = `test_idempotent_${Date.now()}`;

  const res1 = await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 50000,
    time: Date.now(),
  }, 1);

  const res2 = await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 50000,
    time: Date.now(),
  }, 2);

  if (res1.result?.transaction !== res2.result?.transaction) {
    throw new Error("Idempotency failed: transactions don't match");
  }
});

// Test 5: PerformTransaction — to'lovni tasdiqla
Deno.test("Payme: PerformTransaction — to'lovni tasdiqla", async () => {
  const merchantId = `test_perform_${Date.now()}`;

  // Create
  const createRes = await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 75000,
    time: Date.now(),
  }, 1);

  if (createRes.result?.state !== 1) {
    throw new Error("Create should return state 1");
  }

  // Perform
  const performRes = await paymeCall("PerformTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 75000,
    time: Date.now(),
  }, 2);

  if (performRes.result?.state !== 2) {
    throw new Error(`Expected state 2, got ${performRes.result?.state}`);
  }
});

// Test 6: CancelTransaction — bekor qilish
Deno.test("Payme: CancelTransaction — to'lovni bekor qilish", async () => {
  const merchantId = `test_cancel_${Date.now()}`;

  // Create
  await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 60000,
    time: Date.now(),
  }, 1);

  // Cancel
  const cancelRes = await paymeCall("CancelTransaction", {
    account: { merchant_trans_id: merchantId },
    reason: 1, // User request
  }, 2);

  if (cancelRes.result?.state !== -1) {
    throw new Error(`Expected state -1, got ${cancelRes.result?.state}`);
  }
});

// Test 7: Allaqachon perform qilingan to'lovni qayta perform qilish
Deno.test("Payme: Double perform — noto'g'ri", async () => {
  const merchantId = `test_double_perform_${Date.now()}`;

  // Create
  await paymeCall("CreateTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 80000,
    time: Date.now(),
  }, 1);

  // First perform
  const perf1 = await paymeCall("PerformTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 80000,
    time: Date.now(),
  }, 2);

  if (perf1.result?.state !== 2) {
    throw new Error("First perform should succeed");
  }

  // Second perform
  const perf2 = await paymeCall("PerformTransaction", {
    account: { merchant_trans_id: merchantId },
    amount: 80000,
    time: Date.now(),
  }, 3);

  // Idempotent bo'lishi kerak (state 2 qaytarsin)
  if (perf2.result?.state !== 2) {
    throw new Error("Second perform should be idempotent");
  }
});

console.log("✅ Payme tests completed");
