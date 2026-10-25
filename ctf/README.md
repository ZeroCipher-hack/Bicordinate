# BICO CTF — boshlovchilar uchun

**Linux** kategoriyasi jamoa o'tgan konspekt bo'yicha (ls, cat, head/tail, grep, find, chmod, wildcard, alias, /etc/shadow).
Har masala alohida `uy.tar.gz` — o'yinchi o'z Kali'sida ochib, haqiqiy buyruqlar bilan yechadi, server kerak emas.
Birinchi navbatda shu kategoriya o'ynaladi; Web/Crypto/Forensics — keyingi bosqich.

22 ta masala, 1935 ball. Jeopardy format, flag: `BICO{...}`. Platforma: CTFd.

| Kategoriya | Masala | Ball |
|---|---|---|
| Misc | Xush kelibsiz | 10 |
| Linux | Ko'rinmas fayl (`ls -la`) | 25 |
| Linux | Boshi va oxiri (`head`/`tail`) | 50 |
| Linux | Igna ichida pichoq (`grep -r`) | 50 |
| Linux | Salom qayerda? (`find -name`) | 75 |
| Linux | Og'ir fayl (`find -size`) | 75 |
| Linux | Bo'sh qo'l (`find -empty`) | 50 |
| Linux | Qulf (`chmod`) | 100 |
| Linux | Qorong'u xona (papka `--x`) | 100 |
| Linux | Alias sehri (`source`, `alias`) | 50 |
| Linux | Bitta katta harf (wildcard) | 75 |
| Linux | Parol buzish (`/etc/shadow`, `john`) | 200 |
| Web | Robot nima deydi? (robots.txt) | 50 |
| Web | Mehmon va admin (cookie) | 100 |
| Web | Admin paroli yo'q (SQLi) | 150 |
| Web | Boshqaning eslatmasi (IDOR) | 150 |
| Crypto | Yuliy Sezar | 50 |
| Crypto | Piyoz (base64 → hex → rot13) | 75 |
| Crypto | Bitta bayt (XOR) | 100 |
| Crypto | Kichik kalit (RSA e=3) | 200 |
| Forensics | Oddiy rasm (`strings`) | 50 |
| Forensics | Ukol ostida (log) | 150 |

Har masalada 1-2 ta hint (har biri 10 ball turadi).

## Ishga tushirish

```bash
cd ctf
pip install pillow pyyaml
python3 build.py                  # fayllar, challenge.yml va .flags.env yaratadi
python3 check.py                  # har bir masala yechilishini tekshiradi — hammasi OK bo'lsin

cp .env.example .env              # parollarni o'zgartiring!
docker compose --env-file .env --env-file .flags.env up -d --build
```

CTFd: `http://SERVER:8000` — birinchi kirishda admin akkaunt va musobaqa sozlamalarini kiriting
(**Teams mode** ni yoqing, jamoalarni o'yinchilarning o'zi yaratadi yoki siz oldindan qo'shasiz).
Web masalalar: 8001–8004 portlar.

## Masalalarni CTFd'ga yuklash

```bash
pip install ctfcli
cd challenges && ctf init          # CTFd URL va admin token (Settings → Access Tokens)
for d in */*/; do ctf challenge install "$d"; done
```

`build.py` ichidagi `HOST` ni server manzilingizga almashtirib, qayta ishga tushiring — web masalalarning
`connection_info` shundan olinadi.

## Musobaqadan oldin — majburiy

- [ ] **Repo private bo'lsin.** `build.py` ichida barcha flaglar ochiq turibdi. O'yinchilar ko'rsa — o'yin tugadi.
- [ ] `check.py` — hammasi `OK`.
- [ ] Firewall: faqat 8000–8004 ochiq; `db` va `cache` portlari tashqariga chiqmagan (compose'da shunday).
- [ ] Bir odam masalalarni nol tajribali ko'z bilan sinab ko'rsin (o'zingiz emas — siz javobni bilasiz).
- [ ] Vaqt: 3–4 soat, boshlanish/tugash CTFd → Admin → Config → Time.
- [ ] Flaglarni almashtirmoqchi bo'lsangiz — `build.py` dagi `FLAGS` ni tahrirlab, qayta `build.py`, `docker compose up -d`, va CTFd'dagi flaglarni yangilang.

## Yechimlar (organizatorlar uchun)

- **robots**: `/robots.txt` → `/s3cr3t-panel-7731`
- **cookie**: `role` cookie base64(`guest`) → base64(`admin`) = `YWRtaW4=`, `/admin`
- **sqli**: login `admin'--`, parol bo'sh
- **idor**: `/note/17`
- **caesar**: shift 7 (qavs ichi), `CyberChef → ROT7`
- **layers**: base64 → hex → rot13
- **xor**: kalit `0x5a`
- **rsa**: `e=3`, `m³ < n` → butun kub ildizi
- **strings**: `strings manzara.png | grep BICO`
- **Linux**: har bir masala tavsifidagi hint — to'g'ri buyruq. `l_shadow`: `unshadow` + `john`, parol `iloveyou`.
  `grep -r BICO .` ko'p Linux masalalarni bir zarbada yechadi — bu zaiflik emas, konspektdagi bilim; ball qiymatlari shunga moslangan.
- **logs**: `grep -v -E '"(Mozilla|curl)/' access.log` → User-Agent base64
