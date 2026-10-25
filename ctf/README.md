# BICO CTF — boshlovchilar uchun

**Linux** kategoriyasi jamoa o'tgan konspekt bo'yicha (ls, cat, head/tail, grep, find, chmod, wildcard, alias, /etc/shadow).
Har masala alohida `uy.tar.gz` — o'yinchi o'z Kali'sida ochib, haqiqiy buyruqlar bilan yechadi, server kerak emas.
Linux (20 ta) — asosiy qism. Crypto/Forensics fayl bilan yechiladi; faqat 4 ta Web masala serverni talab qiladi.

50 ta masala, 3435 ball. **Yakka tartib**: har o'quvchi o'zi uchun o'ynaydi. Jeopardy format, flag: `BICO{...}`. Platforma: CTFd.

| Kategoriya | Masala | Ball |
|---|---|---|
| Misc | Xush kelibsiz | 10 |
| Linux | 237-qator | 25 |
| Linux | Bo'sh joy | 25 |
| Linux | G'alati alias | 25 |
| Linux | Ko'rinmas fayl | 25 |
| Linux | Oxirgi 50 | 25 |
| Linux | Qaysi distro? | 25 |
| Linux | A harfi va PDF | 50 |
| Linux | Alias sehri | 50 |
| Linux | Bo'sh qo'l | 50 |
| Linux | Boshi va oxiri | 50 |
| Linux | Eng yangi | 50 |
| Linux | Eski buyruqlar | 50 |
| Linux | Igna ichida pichoq | 50 |
| Linux | Ikki so'z | 50 |
| Linux | Ishga tushmaydi | 50 |
| Linux | Katta-kichik harf | 50 |
| Linux | Raqamli nom | 50 |
| Linux | Yashirin ichida yashirin | 50 |
| Linux | Bitta katta harf | 75 |
| Linux | Fayl emas, papka | 75 |
| Linux | Havola | 75 |
| Linux | Kim kira oladi? | 75 |
| Linux | Og'ir fayl | 75 |
| Linux | Qaysi guruh? | 75 |
| Linux | Salom qayerda? | 75 |
| Linux | Shovqin | 75 |
| Linux | Teskari shovqin | 75 |
| Linux | Qorong'u xona | 100 |
| Linux | Qulf | 100 |
| Linux | Uch shart | 100 |
| Linux | Parol buzish | 200 |
| Crypto | Hex | 25 |
| Crypto | Base... nechta? | 50 |
| Crypto | Nol va bir | 50 |
| Crypto | Nuqta va tire | 50 |
| Crypto | Rot... 47 | 50 |
| Crypto | Teskari alifbo | 50 |
| Crypto | Yuliy Sezar | 50 |
| Crypto | Piyoz | 75 |
| Crypto | Bitta bayt | 100 |
| Crypto | Vijener | 100 |
| Crypto | Kichik kalit | 200 |
| Forensics | Matryoshka | 50 |
| Forensics | Oddiy rasm | 50 |
| Forensics | Ukol ostida | 150 |
| Web | Robot nima deydi? | 50 |
| Web | Mehmon va admin | 100 |
| Web | Admin paroli yo'q | 150 |
| Web | Boshqaning eslatmasi | 150 |

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
(**User mode** ni tanlang — jamoasiz, har kim o'z hisobida).
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
- [ ] **Flag almashinuvi.** Flaglar hamma uchun bir xil — bitta odam yechib guruhga yuborsa, hamma ko'chiradi. Yakka musobaqada bu jiddiy. Chora: musobaqani bitta xonada/nazorat ostida o'tkazing, yoki yakuniy reytingdan keyin og'zaki "qanday yechding?" so'rang.
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
