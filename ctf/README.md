# BICO CTF

Maktab o'quvchilari uchun yakka tartibli CTF: **50 masala, 3435 ball**. Hammasi brauzerda:
ism + PIN bilan kirish, **terminal**, **savollar** (kim yechgani va first blood bilan), jonli **reyting**.

| Sahifa | Manzil |
|---|---|
| Kirish | `/` |
| Terminal | `/terminal` |
| Savollar | `/challenges` |
| Reyting | `/scoreboard` |

Masalalar: Linux 31, Crypto 11, Web 4, Forensics 3, Machine 1, Misc 1. Linux masalalari jamoa o'tgan konspekt bo'yicha
(`ls`, `cat`, `head/tail`, `grep`, `find`, `chmod`, wildcard, `alias`, STDOUT/STDERR, `/etc/passwd`, `/etc/shadow`).
Flag formati: `BICO{...}`. Hint har biri 10 ball.

## Ishga tushirish (server)

Kerak: Linux, Docker, Python 3.10+.

```bash
cd ctf
pip install pillow pyyaml aiohttp
python3 build.py                              # masalalar, app/challenges.json, shell fayllari
python3 check.py                              # 50 masalaning hammasi yechilishini tekshiradi

docker build -t bico-shell app/shell          # o'quvchi terminali (har kimga alohida konteyner)
docker compose --env-file .flags.env up -d --build   # 4 ta web masala (8001-8004) + machine (2222)

CTF_START=2026-10-26T10:00:00+05:00 CTF_END=2026-10-26T13:00:00+05:00 python3 app/server.py
```

Sayt: `http://SERVER:8080`. O'quvchilar bir tarmoqda bo'lsa, shu manzilni berasiz.
`CTF_START`/`CTF_END` ixtiyoriy (berilmasa musobaqa doim ochiq). Boshlanishdan oldin savollar yashirin.

| O'zgaruvchi | Standart | Ma'nosi |
|---|---|---|
| `PORT` | 8080 | sayt porti |
| `TERM_MODE` | `docker` | `docker` — har o'quvchiga izolyatsiyalangan konteyner. `local` — **faqat sinov uchun**, serverning o'zida shell ochadi |
| `MAX_TERMS` | 40 | bir vaqtdagi terminallar soni chegarasi |
| `TERM_IDLE` | 1800 | kiritishsiz terminal necha soniyadan keyin yopiladi |
| `CTF_DATA` | `app/data` | SQLite bazasi |

Konteyner cheklovlari: tarmoqsiz, 128 MB RAM, 0.5 CPU, 64 jarayon, faqat o'qish uchun fayl tizimi, `cap-drop ALL`.

**Docker'ga kirish huquqi = root huquqi.** `server.py` ni alohida, kerakli narsasiz mashinada yuriting
va `0.0.0.0:8080` ni maktab tarmog'idan tashqariga chiqarmang.

## Machine masalasi (SSH, 150 ball)

Veb sahifada (Savollar bo'limida) parol xeshi va foydalanuvchi nomi **to'g'ridan-to'g'ri matn** sifatida ko'rinadi — veb
hujum shart emas. O'quvchi `john` bilan xeshni buzadi, `ssh operator@SERVER_IP -p 2222` orqali kiradi, `cat user.txt`.

- Bitta umumiy konteyner — hamma shu SSH'ga ulanadi. `operator` foydalanuvchisida `sudo` yo'q, boshqa foydalanuvchi
  yo'q, shuning uchun boshqa birovning ishiga aralasha olmaydi, lekin **hamma bir xil parolni biladi va bir xil
  terminalda ishlaydi** — bir vaqtning o'zida bir nechta o'quvchi kirsa, `ls`/`who` orqali bir-birini ko'radi.
- Portni almashtirish kerak bo'lsa: `docker-compose.yml` dagi `2222:22` ni o'zgartiring va e'londa shuni yozing.
- Bu konteyner boshqalaridan farqli — `sshd` ishlashi uchun ba'zi Linux imkoniyatlari (`SETUID`, `CHOWN`...) kerak,
  `--network none` qila olmaymiz (SSH kirish uchun tarmoq shart). Shuning uchun uni **alohida, kam ishonch bilan**
  qarang: boshqa konteynerlarga qaraganda xavfliroq.

## Boshqaruv

```bash
python3 app/server.py reset-pin "Ism" 1234     # PIN unutilsa
python3 app/server.py delete-user "Ism"
python3 app/test_smoke.py                      # API + terminal avtomatik testi (TERM_MODE=local)
```

## Qoidalar va himoya

- Flaglar bazada va `challenges.json` da faqat SHA-256 xeshi; mijozga hech qachon chiqmaydi. Hint matni ochilmaguncha yuborilmaydi.
- Xato flag: daqiqada 15 tadan ko'p emas; yuborishlar orasida 1 soniya. Kirish urinishlari ham cheklangan.
- First blood = masalani birinchi to'g'ri yuborgan; reyting: ball (hint ayiriladi), teng bo'lsa — oxirgi yechimi ertaroq turgan yuqorida.
- Ism: 2–20 belgi. PIN: 4 raqam (PBKDF2 bilan xeshlanadi).

## Musobaqadan oldin — majburiy

- [ ] **Repo private.** `build.py` ichida flaglar ochiq turibdi.
- [ ] `check.py` va `test_smoke.py` — hammasi OK.
- [ ] `docker build` va **haqiqiy Docker rejimida** bitta terminalni sinab ko'ring (bu muhitda sinalmagan, faqat `local` rejim sinalgan).
- [ ] Nol tajribali kishiga 3–4 masalani yechtirib ko'ring.
- [ ] 24 ta terminalni bir vaqtda oching: server CPU/RAM'ga dosh beradimi (har biri ~30–130 MB).
- [ ] **Flag almashinuvi:** flaglar hamma uchun bir xil. Bitta xonada, nazorat ostida o'tkazing yoki g'oliblardan "qanday yechding?" deb so'rang.
- [ ] Web masalalar uchun `app/server.py` va compose bir mashinada: portlar 8001–8004 ochiq bo'lsin.

## Yechimlar (organizatorlar uchun)

Har bir masalaning hinti — to'g'ri buyruq. Umumiy: Web — `/robots.txt`, cookie `role`=base64(`admin`), login `admin'--`, `/note/17`.
Crypto — CyberChef; RSA e=3: butun kub ildizi; `l_shadow`: `unshadow` + `john`, parol `iloveyou`.
`grep -r BICO .` ko'p Linux masalalarni bir zarbada yechadi — bu konspektdagi bilim, ballar shunga moslangan.
