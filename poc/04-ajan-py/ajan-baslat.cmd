@echo off
rem ===================================================================
rem  POC Yonetici Asistani - Python baslatma sarmalayicisi
rem  Zamanlanmis gorev bunu cagirir. Elle de calistirilabilir.
rem ===================================================================

cd /d "%~dp0"

rem --- yapilandirma ---
set POC_SSAS_SUNUCU=localhost\TABULAR
set POC_SSAS_MODEL=POC_Satis
set POC_SQL_SUNUCU=localhost
set POC_SQL_DB=POC_SatisYZ
set POC_PORT=8787
set POC_RAPOR_PORTAL=http://localhost/Reports
set POC_RAPOR_SUNUCU=http://localhost/ReportServer

rem Turkce cikti icin sart: Python'un varsayilan konsol kod sayfasi
rem "Kapali Devre" gibi metinleri bozuyor.
set PYTHONIOENCODING=utf-8

rem Biçimbilim: kural (varsayilan) veya zeyrek.
rem Zeyrek nltk korpusu gerektirir; olculdu, kapsamaya katkisi yok.
set POC_DILBILGISI=kural

rem Python tam yolla cagriliyor. PATH'e guvenmek riskli: Microsoft Store
rem saplamasi (WindowsApps\python.exe, 0 bayt) PATH'i golgeleyip
rem "Python bulunamadi" hatasi veriyor.
set PY=C:\Python312\python.exe
if not exist "%PY%" set PY=python

if not exist "denetim" mkdir "denetim"

rem --- log dosyasi 5 MB'i gecerse arsivle ---
set LOG=denetim\ajan.log
if exist "%LOG%" (
    for %%A in ("%LOG%") do if %%~zA GTR 5242880 (
        move /y "%LOG%" "%LOG%.1" >nul
    )
)

echo. >> "%LOG%"
echo ==== baslatildi %DATE% %TIME% ==== >> "%LOG%"
"%PY%" sunucu.py >> "%LOG%" 2>&1
