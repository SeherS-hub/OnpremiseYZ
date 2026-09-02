@echo off
rem Tum testleri sirayla kosar. Sinir testi CALISAN ajan gerektirir.
cd /d "%~dp0"
set PY=C:\Python312\python.exe
if not exist "%PY%" set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ===== ALTIN KUME =====
"%PY%" test\altin_kume.py
if errorlevel 1 goto :hata

echo.
echo ===== TAHMIN BIRIM TESTI =====
"%PY%" test\tahmin_testi.py
if errorlevel 1 goto :hata

echo.
echo ===== ESANLAM KAPSAMASI =====
"%PY%" test\esanlam_testi.py
if errorlevel 1 goto :hata

echo.
echo ===== SINIR DAVRANISI (kesif) =====
"%PY%" test\sinir_testi.py
goto :son

:hata
echo.
echo   TEST BASARISIZ
exit /b 1

:son
echo.
echo   Tum testler tamam.
