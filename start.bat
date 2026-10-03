@echo off
REM Oilaviy shifokorlik testi - backend + frontend.
REM Bitta buyruq bilan serverni ishga tushiradi va brauzerni ochadi.

setlocal
cd /d "%~dp0"

set PORT=8000
REM Django Unfold admin paneli alohida portda ishlaydi va /admin undaga
REM yo'naltiradi. Ikkalasi bitta SQLite faylni (data\app.db) ulashadi.
set ADMIN_PORT=8001
REM 0.0.0.0 bilan boshqa qurilmalar (telefon, planshet) ham saytni ochadi.
REM Faqat shu kompyuterdan foydalanmoqchi bo'lsangiz 127.0.0.1 qo'ying.
set HOST=0.0.0.0

where python >nul 2>nul
if errorlevel 1 (
  echo [XATO] Python topilmadi. Python 3.11+ va pip kerak.
  exit /b 1
)

REM -- .env fayli bo'lsa, undagi sozlamalarni yuklaymiz ------------------------
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if not "%%a"=="" set "%%a=%%b"
  )
)

REM -- Odatdagi port band bo'lsa, bo'sh portni topamiz -------------------------
:find_port
netstat -ano -p tcp | findstr /R /C:"LISTENING" | findstr /R /C:":%PORT% " >nul 2>nul
if errorlevel 1 goto port_ready
set /a PORT+=1
if %PORT% GTR 8020 (
  echo [XATO] 8000-8020 portlari band. Boshqa portni bo'sh qiling.
  exit /b 1
)
goto find_port

:port_ready
set URL=http://127.0.0.1:%PORT%
REM Admin panel havolasi boshqa qurilmadan ochilganda 127.0.0.1 ishlamaydi,
REM shuning uchun LAN manzilini oldindan bilamiz.
set LANIP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
  if not defined LANIP set LANIP=%%a
)
set LANIP=%LANIP: =%
if defined LANIP (
  set ADMIN_URL=http://%LANIP%:%ADMIN_PORT%/admin/
) else (
  set ADMIN_URL=http://127.0.0.1:%ADMIN_PORT%/admin/
)
echo.
echo ============================================
echo  Oilaviy shifokorlik testi platformasi
echo ============================================
echo  Bu qurilmada  : %URL%/
echo  Admin panel   : %URL%/admin   ^(Django Unfold, %ADMIN_PORT%-port^)
echo  API hujjati   : %URL%/api/docs
echo.
REM -- Boshqa qurilmalar uchun Wi-Fi orqali ochiladigan manzil ---------------
if defined LANIP (
  echo  Telefon/planshetda ^
    http://%LANIP%:%PORT%/
  echo  ^(Wi-Fi tarmog'ida, shu internet yoki internet bilan bog'laning^)
  echo.
)
if exist ".env" (
  echo  Kirish: .env faylidagi DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD
) else (
  echo  Kirish ma'lumotlari:
  echo    admin@osh.uz    / admin12345
  echo    teacher@osh.uz  / teacher12345
  echo.
  echo  ESLATMA: internetga joylashdan oldin .env faylini yarating.
)
echo.
echo  To'xtatish uchun bu oynani Ctrl+C bilan yoping.
echo ============================================
echo.

REM -- Birinchi ishga tushirishda savollarni import qilamiz --------------------
if not exist "data\app.db" (
  echo [1/2] Bazadagi savol banki tayyorlanmoqda...
  python -c "from server.core.database import init_db; from server.services.seed import seed_if_empty; init_db(); seed_if_empty(); print('  bazalar yaratildi')"
  if errorlevel 1 (
    echo [XATO] Bazani tayyorlashda xatolik.
    exit /b 1
  )
  echo [2/2] Savollar import qilinmoqda...
  echo       (avval: python tools\build_dataset.py)
)

REM -- Django Unfold admin panelini fonda ishga tushiramiz ------------------------
if not exist "admin_site\manage.py" (
  echo [XATO] admin_site\manage.py topilmadi. Django paneli o'rnatilmagan.
  exit /b 1
)
REM Unfold statik fayllarini yig'amiz. Bu har doim bajariladi: WhiteNoise
REM faqat shu yig'ilgan fayllarni beradi va yangilangan Unfold versiyasi
REM yangi fayl qo'shishi mumkin. Aks holda panel uslubsiz (404) chiqadi.
python admin_site\manage.py collectstatic --noinput --clear >nul 2>nul
if errorlevel 1 (
  echo [XATO] Statik fayllarni yig'ib bo'lmadi.
) else (
  if not exist "data\django-static\admin_custom.css" (
    echo [XATO] admin_custom.css yig'ilmadi - panel uslubsiz chiqadi.
  )
)

REM O'quvchi saytining havolasi Django kontekstiga uzatiladi: shu orqali
REM "O'quvchi saytiga qaytish" tugmasi to'g'ri manzilni ko'rsatadi.
set STUDENT_SITE_URL=http://127.0.0.1:%PORT%/
set DJANGO_ADMIN_URL=http://127.0.0.1:%ADMIN_PORT%/admin/

start "OSH admin" /b python admin_site\manage.py runserver %HOST%:%ADMIN_PORT% --noreload

set /a AWAITED=0
:wait_admin
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%ADMIN_PORT%/login/' -TimeoutSec 2) | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto admin_ready
set /a AWAITED+=1
if %AWAITED% GTR 30 (
  echo [XATO] Django admin paneli javob bermadi. %ADMIN_PORT%-port band bo'lishi mumkin.
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_admin

:admin_ready
start "OSH server" /b python -m uvicorn server.main:app --host %HOST% --port %PORT%

set /a WAITED=0
:wait_server
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%URL%/api/health' -TimeoutSec 2) | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto server_ready
set /a WAITED+=1
if %WAITED% GTR 30 (
  echo [XATO] Server 60 soniyada javob bermadi. Yuqoridagi xatolarni tekshiring.
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_server

:server_ready
start "" %URL%/admin
start "" %URL%/

echo.
echo Server tayyor: %URL%
echo Admin panel  : %ADMIN_URL%
echo Bu oynani yopish serverni to'xtatadi.
echo.
pause
