# Oilaviy shifokorlik testi — full-stack platforma

Oilaviy shifokorlik mutaxassisligi testi: **backend** (FastAPI + SQLAlchemy +
SQLite) va **frontend** (ikki SPA — o‘quvchi sayti va admin panel). 1005 ta
savol bazaga yuklanadi, har bir urinishda 20 ta savol beriladi, baholash serverda
bajariladi.

## Ishga tushirish

```bat
start.bat
```

Skript bo‘sh portni topadi, bazani va savol bankini avtomatik yaratadi, serverni
tayyor bo‘lishini kutib keyin brauzerni ochadi:

| Manzil | Vazifasi |
|---|---|
| <http://127.0.0.1:8000/> | o‘quvchi sayti (FastAPI) |
| <http://127.0.0.1:8000/admin> | admin panelga o‘tadi (Django Unfold, 8001-port) |
| <http://127.0.0.1:8001/admin/> | Django Unfold admin paneli |
| <http://127.0.0.1:8000/api/docs> | Swagger API hujjati |

### Admin panel (Django Unfold)

Boshqaruv paneli **Django + django-unfold** bilan qilingan va `admin_site/`
papkasida yashaydi. U FastAPI bilan **bitta SQLite faylni** (`data/app.db`)
ulashadi, shuning uchun paneldagi o‘zgarishlar o‘quvchi saytida darhol ko‘rinadi.

- Parollar `pbkdf2_sha256$260000$…` formatida saqlanadi — ikkala ilova ham
  shu formatni yoza va tekshiradi, demak parol ikki tarafdan ham bir xil ishlaydi.
- Admin panel o‘ziga xos portda (8001) ishlaydi; 8000-portdagi `/admin` undaga
  yo‘naltiradi. Panel ichida **“← O‘quvchi saytiga qaytish”** tugmasi har bir
  sahifada bor.
- Panel boshqa qurilmada ochilganda `127.0.0.1` ishlamaydi, shuning uchun
  `STUDENT_SITE_URL` ni LAN manzilga qo‘ying (masalan `http://192.168.1.5:8000/`).

Panelni qo‘lda ishga tushirish:

```bash
python admin_site/manage.py migrate            # Django'ning o'z jadvallari
python admin_site/manage.py collectstatic --noinput --clear
python admin_site/manage.py runserver 0.0.0.0:8001
```

> **`collectstatic` har doim bajarilishi shart.** Panel uslublarini WhiteNoise
> beradi va u faqat yig‘ilgan fayllarni topadi; `DEBUG` o‘chiq bo‘lganda
> `runserver` statik fayllarni o‘zi bermaydi. Yig‘ilmagan bo‘lsa, panel
> to‘liq uslubsiz (oddiy matn) chiqadi. `start.bat` buni avtomatik qiladi.

Tekshirish skriptlari (ikkala server ishga tushganda):

```bash
python tools/check_admin.py         # login, sahifalar, orqaga tugma
python tools/check_admin_assets.py  # uslublar yuklanganmi, izoh sizib chiqdimi
python tools/check_password_sync.py  # parol almashuvi ikki app orasida
```

### Telefon va planshetdan ochish

`start.bat` serverini `0.0.0.0` da ishga tushiradi, shuning uchun **shu Wi-Fi
tarmog‘idagi** boshqa qurilmalar saytni ochishi mumkin. Oynada chiqadigan
manzilni to‘g‘ridan-to‘g‘ri telefon brauzeriga kiriting:

```
Telefon/planshetda  http://192.168.x.x:8000/
```

Shartlar:
- Qurilmalar **bir xil Wi-Fi** tarmog‘ida bo‘lishi kerak.
- Kompyuterning antivirus yoki Windows Firewall’ida Python’ga kirishga ruxsat
  berilishi kerak (odatda `start.bat` birinchi ishga tushganda so‘raydi).
- Faqat shu kompyuterdan foydalanmoqchi bo‘lsangiz, `start.bat` ichida
  `HOST=127.0.0.1` qilib qo‘ying.

Bu mahalliy tarmoq (LAN) uchun. Butun dunyoga ochish uchun quyidagi
[Serverga joylash](#serverga-yuklash-docker--nginx) bo‘limiga qarang.

Demo hisoblar:

| Rol | E-pochta | Parol |
|---|---|---|
| admin | `admin@osh.uz` | `admin12345` |
| teacher | `teacher@osh.uz` | `teacher12345` |

Qo‘shimcha: `python -m pip install -r requirements.txt` va keyin
`python -m uvicorn server.main:app --reload --port 8000`.

## Serverga yukash (Docker + nginx)

Eng tez yo‘l — Docker Compose. Backend va nginx konteyner sifatida ishlaydi,
ma’lumotlar bazasi `data/` papkasida saqlanadi.

### 1. Tayyorlik

Serverda Docker o‘rnatilgan bo‘lishi kerak (Ubuntu/Debian):

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
```

### 2. Fayllarni yuborish

Lokal mashinadan (bu yerga — loyiha papkasi) tar arxiv yaratib, serverga yuklang:

```bash
# serverga
mkdir -p ~/osh-test && cd ~/osh-test
```

# Serverga yuklangan fayllar ro'yxati (README bo'limi 2).
Keyin `scp` yoki hosting panelining fayl yuklash oynasidan quyidagilarni
yuqtoring: `server/`, `web/`, `build/`, `tools/`, `deploy/`,
`Dockerfile`, `docker-compose.yml`, `requirements.txt`, `.dockerignore`.

Ikonkalar `web/assets/icons/` ichida — ular `favicon.ico`, `favicon.svg` va
PWA manifest fayllarini o‘z ichida olib yuradi, alohida yuklash shart emas.

### 3. Sozlamalarni to‘ldirish

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
```

`.env` faylini tahrirlang:

| Kalit | Nima uchun |
|---|---|
| `SECRET_KEY` | Token imzosi — tasodifiy uzun qiymat qo‘ying |
| `DEFAULT_ADMIN_PASSWORD` | Kuchli, kamida 12 belgi |
| `DEFAULT_TEACHER_PASSWORD` | Kuchli, kamida 12 belgi |
| `ALLOW_REGISTRATION` | Guruh ro‘yxatdan o‘tganini to‘xtatish uchun `false` |
| `CORS_ORIGINS` | Bo‘sh qoldiring — nginx frontend va API bitta manzildan beradi |

`ENVIRONMENT=production` qo‘ying. Bu rejimda standart `SECRET_KEY` yoki kuchsiz
parollar bo‘lsa, server ishga tushmaydi va xatoni ko‘rsatadi.

### 4. Ishga tushirish

```bash
docker compose up -d --build
docker compose logs -f app        # birinchi ishga tushirishda savollar import qilinadi
```

Sayt `http://SERVER_IP` manzilida ochiladi. API faqat `127.0.0.1:8000` ga
bog‘langan, shuning uchun tashqi kirish faqat nginx orqali.

### 5. Domen va HTTPS

Domeningiz oldida `A` yozuvi kerak. Keyin:

```bash
DOMAIN=test.osh.uz docker compose up -d nginx
sudo apt install -y certbot
sudo certbot certonly --standalone -d test.osh.uz
sudo cp /etc/letsencrypt/live/test.osh.uz/fullchain.pem deploy/certs/
sudo cp /etc/letsencrypt/live/test.osh.uz/privkey.pem   deploy/certs/
docker compose restart nginx
```

Endi `https://test.osh.uz` ishlaydi va HTTP avtomatik HTTPS ga yo‘naltiriladi.

### 6. Yangilash va zaxira

```bash
git pull                       # yoki fayllarni qayta yuklash
docker compose up -d --build   # kod yangilandi

cp data/app.db ~/backup-$(date +%F).db   # zaxira
```

### Docker’siz (systemd)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # tahrlang
set -a && . ./.env && set +a
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

`/etc/systemd/system/osh.service` fayli:

```ini
[Unit]
Description=OSH Test Platform
After=network.target

[Service]
User=osh
WorkingDirectory=/opt/osh-test
EnvironmentFile=/opt/osh-test/.env
ExecStart=/opt/osh-test/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now osh
```

### Xavfsizlik eslatmalari

- Standart parol (`admin12345`) bilan hech qachon internetga ochmang.
- `data/app.db` fayli barcha o‘quvchi javoblari va natijalarini saqlaydi —
  uni Git’ga qo‘shmang (`.gitignore` allaqachon bloklagan).
- Registratsiyani yopish uchun `ALLOW_REGISTRATION=false` qiling yoki admin
  panelidan sozlang.

## Tuzilma

```
server/
  main.py               FastAPI ilovasi, routerlar, statik fayllar
  core/                 config, SQLAlchemy sessiyasi, parol/JWT
  models/entities.py    Jadvalar: User, Question, Exam, Attempt, Answer, ...

## Backend

**Autentifikatsiya** — PBKDF2-HMAC-SHA256 parol hash, o‘z-implementatsiya qilingan
JWT (HS256). Rollar: `student` (o‘qish), `teacher` (kontent), `admin` (to‘liq
huquq). Registratsiya panelidan yopilishi mumkin.

**API marshrutlari** (prefix `/api`):

| Metod | Yo‘l | Kim uchun |
|---|---|---|
| POST | `/auth/register` · `/auth/login` | ommaviy |
| GET | `/auth/me` | kirgan |
| GET/POST/PATCH/DELETE | `/admin/users`, `/admin/users/{id}` | admin |
| GET | `/questions` (qidiruv, filtr, sahifa), `/questions/topics` | kirgan |
| POST/PATCH/DELETE | `/questions`, `/questions/{id}` | admin/teacher |
| POST | `/questions/import` | admin/teacher |
| GET/POST/PATCH/DELETE | `/exams`, `/exams/{id}` | o‘qish / admin |
| POST | `/attempts/start` · `/{id}/submit` · `/{id}/abandon` | kirgan |
| GET | `/attempts/active` · `/history` · `/{id}` · `/{id}/timer` | kirgan |
| GET | `/admin/stats` · `/admin/settings` · `/admin/audit` | admin/teacher |
| POST | `/admin/questions/reset-answers` | admin |

**Baholash mantiqi** — variant tartibi serverda aralashtiriladi va urinishda
saqlanadi (`attempt.option_order`). Topshirishda mijoz yuborgan indeks shu
tartib orqali asl variant indeksiga aylantiriladi, shuning uchun aralashgan
test ham to‘g‘ri tekshiriladi. Javob hech qachon brauzerda saqlanmaydi.

**Statistika** — o‘rtacha ball, o‘tish ulushi, ball taqsimoti (5 ta interval),
14 kunlik faollik, mavzu va qiyinchilik kesimida to‘g‘rilik, eng qiyin 10 ta
savol, reyting.

## Frontend

**O‘quvchi sayti**: login/registratsiya, testlar ro‘yxati (bo‘lim va rejim
tanlash), imtihon runneri (timer, savol navigatsiyasi, belgilash, javobni
ko‘rsatish), natija sahifasi (ball halqasi, savollar bo‘yicha ko‘rib chiqish),
tarix va profil. Yarim qolgan urinish ro‘yxat sahifasida ko‘rsatilmaydi.

### Testlar bo‘limlarga bo‘linishi

1005 ta savol `questions_per_block` (20 ta) bo‘yicha bo‘limlarga bo‘linadi:
`ceil(1005 / 20) = 51` ta bo‘lim, oxirgisi 5 ta savol bilan. Har bir bo‘lim
alohida kartada turadi va kartadagi **Boshlash** tugmasi orqali dialogsiz,
bir zumda boshlanadi.

Savollar bazadagi tartibda barqaror saqlanadi va bo‘lim kesiladi — ya'ni
1-bo‘lim har doim bir xil 20 ta savol beradi. Aralashish faqat **tanlangan
bo‘lim ichida** qo‘llaniladi, shuning uchun o‘quvchi 7-bo‘limni qayta ish
tog‘lasa ham bir xil savollar keladi va butun bank qamrab olinadi.

Bo‘limlarni imtihonga qo‘shish/qayta bog‘lash:

```bash
python tools/link_all_questions.py --dry-run   # avval ko‘rish
python tools/link_all_questions.py             # qo‘llash
python tools/check_blocks.py                   # 51 bo‘limni tekshirish
```

> **Muhim:** 1005 savolning 456 tasida javob kaliti bor, 549 tasida esa yo‘q.
> Javobsiz savollar bo‘limga kiradi va o‘quvchiga ko‘rsatiladi, lekin baho
> hisobiga **kirmaydi** (`grade_attempt` faqat `answer_index` bor savollarni
> `gradable` ga qo‘shadi) — ya'ni noto‘g‘ri javob uchun jazo berilmaydi.

### Javob kalitlarini import qilish

Shifokor tomonidan berilgan javoblar fayli
(`Текстовый документ.txt`, 1005 ta javob) bazadagi kalitlar bilan
solishtiriladi va tasdiqlanganlar yoziladi:

```bash
python tools/import_answers.py --dry-run   # avval rejalashtirishni ko‘rish
python tools/import_answers.py             # qo‘llash
python tools/answer_coverage.py            # qaysi savollar hali javobsiz
python tools/check_grading.py              # baholash to‘g‘riligini tekshirish
python tools/check_page_signatures.py      # sahifa parametrlari routerga mosmi
```

**Ishga tushirilgan natija: 338 javob tasdiqlandi, 0 ta o‘zgarish.** Ya'ni
berilgan fayldagi har bir javob bazadagi mavjud kalit bilan **to‘liq mos** —
bu lotin qismining to‘g‘ri bog‘langanini tasdiqlaydi.

Faylni o‘zgartirish uchun `--answers` argumenti beriladi (odatdagi manzil:
`c:\Users\asad2\Downloads\Текстовый документ.txt_Parsing.uz.txt`):

```bash
python tools/import_answers.py --answers "C:\...\boshqa_javoblar.txt" --dry-run
```

Javoblarni **faqat** shu yo‘l bilan yoziladi — savol matri, variantlar, bo‘lim
bog‘lanishlari va urinishlar (attempts) hech qachon o‘zgartirilmaydi.

Qolgan 667 ta yozilmadi, sabablari bilan (`--report data/skipped.json`):

| Sabab | Soni | Tushuntirish |
|---|---|---|
| question not in bank | 645 | javob faylining 363–1005 qismi **boshqa savol to‘plami** (Apgar, Cherezda, Rovsing shakli savollar bankda ham, Word faylda ham yo‘q — tekshiruv: 643 tadan **0** tasi Word faylda topildi) |
| question ambiguous | 12 | matn bir nechta savolga o‘xshash |
| question has no options | 8 | savol variantlarisiz |
| answer matches no option | 2 | javob variantlardan biriga mos emas |

Baza **Word faylidagi savollar bilan bir xil**: 1005 savoldan 998 tasi Word
faylida aynan topiladi. Shu sababli savollar **almashtirilmadi** — o‘zgartirilgan
bo‘lsa, imtihon boshqa to‘plamga aylanib ketardi.

Ikkala yozish sharti bajarilishi kerak, aks holda javob yozilmaydi:
savol matni bitta savolni aniq ko‘rsatishi **va** javob matni aynan bitta
variantni tanlashi. Noto‘g‘ri javob yo‘q javobdan ko‘ra xavfliroq.

Boshqa muhim topildi: `answer_all` ("barcha javoblar to‘g‘ri") belgisi
`exam_engine.py` da har qanday javobni to‘g‘ri deb hisoblaydigan xatoga olib
kelar edi — endi bu variant ro‘yxatdan topilib shu bilan solishtiriladi.
Bazadagi bitta savol (`"barcha j avoblar to‘g‘ri"` — xato yozilgan) shuning uchun
oddiy `answer_index` ga o‘tkazildi.

**Admin panel**: statistik dashboard, savol banki (qidiruv, filtr, yaratish,
tahrirlash, import), imtihonlar (sozlamalar, nashr), foydalanuvchilar (rol,
bloklash, parol), analitika (grafiklar), tizim sozlamalari, amal tarixi.

Ikkalasi ham build-siz ishlaydi: ES modullari, hash-router, `fetch` wrapper.

## Ma’lumot holati

`tools/build_dataset.py` PDF’dagi 997 ta savolni (hammasi 4 ta variantli) va
TXT’dagi javoblarni birlashtiradi.

- **456** savolning javobi aniq bir variantga bog‘landi
- **549** savolning javobi manba TXT’da o‘sha raqam ostida yozilmagan: kirill
  qismida javob matnlari siljigan (masalan 363-savolning o‘rnida «Юрак
  астмасида адреналин…» javobi turibdi). Bu ma’lumot nuqsoni — noto‘g‘ri javob
  berish xavfi borligi uchun avtomatik tiklanmadi.

Bu savollar o‘quvchi saytida **ballga hisoblanmaydi** va interfeysda
«javobsiz» deb belgilanadi. Administrator `Questions` sahifasidan ularni
tahrirlab javob qo‘yishi yoki o‘chirishi mumkin.

Qolgan savollar ro‘yxati: `build/unresolved.json`.

## Tibbiy ogohlantirish

Javoblar tibbiy adabiyotdan olingan. Bu tizim tibbiy tavsiya berish uchun
mo‘ljallanmagan; tashxis va davolash qarorlari faqat malakali shifokor tomonidan,
klinik ko‘rikuv asosida qabul qilinadi.


  schemas/              Pydantic so‘rov/javob modellari
  api/                  routes_auth, routes_users, routes_questions,
                        routes_exams, routes_attempts, routes_admin, deps
  services/             exam_engine (savol tanlash + baholash), analytics,
                        settings, audit, seed

web/
  index.html            o‘quvchi SPA (login → testlar → runner → natija)
  admin.html            admin SPA (dashboard, savollar, imtihon, user, analitika)
  css/                  base.css, app.css, admin.css
  js/lib/api.js         fetch wrapper, token saqlash, toast, DOM helper
  js/pages/             auth, tests, runner, results, profile
  js/admin/             dashboard, questions, exams, users, analytics,
                        settings, audit

tools/
  build_dataset.py      PDF + TXT → build/questions.json
  js_balance.py         JS fayl muvozanatini tekshiruvchi yordamchi
data/app.db             SQLite bazasi (avtomatik yaratiladi)

