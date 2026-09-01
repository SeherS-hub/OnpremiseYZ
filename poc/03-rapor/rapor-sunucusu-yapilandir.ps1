<#
  SSRS Web Service URL + Web Portal URL yapilandirmasi.

  YONETICI PowerShell'de calistirin:
    powershell -NoProfile -ExecutionPolicy Bypass -File ssrs-url-yapilandir.ps1

  Ne yapar: iki sanal dizini ayarlar (ReportServer / Reports), ikisini de
  http://+:80 uzerine rezerve eder, rapor sunucusunu baslatir ve servisi
  yeniden baslatir. Configuration Manager'daki "Apply" dugmelerinin
  yaptigi isin aynisi, ama hatayi gizlemeden.

  Not: Her adimin HRESULT'u basilir. 0 = basarili.
#>
param(
    # Bos birakilirsa makinedeki rapor sunucusu otomatik bulunur.
    # SSRS  -> RS_SSRS   · PBIRS -> RS_PBIRS
    [string]$Instance,
    [string]$Surum,
    [int]$Port = 80,
    # Katalog veritabani yoksa olusturulur. PBIRS ve SSRS ayni makinedeyse
    # farkli isim verin, yoksa birbirlerinin katalogunu ezerler.
    [string]$VeritabaniAdi,
    [string]$SqlSunucu = 'localhost'
)

$ErrorActionPreference = 'Stop'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bu betik YONETICI olarak calistirilmali.'
}

# Instance ve surum verilmediyse WMI'dan bul. PBIRS ve SSRS ayni makinede
# birlikte durabilir; hangisini yapilandirdigimizi acikca yazariz.
if (-not $Instance) {
    $bulunan = @(Get-CimInstance -Namespace 'root\Microsoft\SqlServer\ReportServer' `
                    -ClassName __NAMESPACE -ErrorAction SilentlyContinue |
                 Select-Object -ExpandProperty Name)
    if ($bulunan.Count -eq 0) { throw 'Makinede rapor sunucusu bulunamadi (SSRS de PBIRS de yok).' }
    if ($bulunan.Count -gt 1) {
        Write-Host "Birden fazla rapor sunucusu var: $($bulunan -join ', ')"
        Write-Host "Hangisini yapilandiracaginizi -Instance ile belirtin."
        throw 'Instance belirtilmeli.'
    }
    $Instance = $bulunan[0]
}
if (-not $Surum) {
    $Surum = @(Get-CimInstance -Namespace "root\Microsoft\SqlServer\ReportServer\$Instance" `
                  -ClassName __NAMESPACE -ErrorAction SilentlyContinue |
               Select-Object -ExpandProperty Name | Sort-Object -Descending)[0]
    if (-not $Surum) { throw "Surum namespace'i bulunamadi: $Instance" }
}
Write-Host "Rapor sunucusu: $Instance / $Surum"

$ns  = "root\Microsoft\SqlServer\ReportServer\$Instance\$Surum\Admin"
$cfg = Get-WmiObject -Namespace $ns -Class MSReportServer_ConfigurationSetting |
       Where-Object { $_.InstanceName -eq 'SSRS' -or $true } | Select-Object -First 1
if (-not $cfg) { throw "Yapilandirma nesnesi bulunamadi: $ns" }

Write-Host ''
Write-Host 'Mevcut durum'
Write-Host ('-' * 55)
Write-Host "Initialized       : $($cfg.IsInitialized)"
Write-Host "DatabaseName      : '$($cfg.DatabaseName)'"
Write-Host "DatabaseServer    : '$($cfg.DatabaseServerName)'"
Write-Host "VirtualDir servis : '$($cfg.VirtualDirectoryReportServer)'"
Write-Host "VirtualDir portal : '$($cfg.VirtualDirectoryReportManager)'"
$mevcut = $cfg.ListReservedUrls()
Write-Host "Rezerve URL'ler   : $(if ($mevcut.UrlString) { $mevcut.UrlString -join ' , ' } else { '(yok)' })"

# ---------- katalog veritabani ----------
# Karar YAPILANDIRMAYA degil, veritabaninin GERCEKTEN VAR OLUP OLMADIGINA
# bakarak verilir. Onceki hali yapilandirmadaki ada bakiyordu; veritabani
# elle dusuruldugunde "zaten ayarli" deyip olusturmayi atliyor ve rapor
# sunucusu var olmayan bir katalogda oturum acmaya calisiyordu.
if (-not $VeritabaniAdi) {
    $VeritabaniAdi = if ($cfg.DatabaseName) { $cfg.DatabaseName }
                     elseif ($Instance -eq 'RS_PBIRS') { 'PBIReportServer' }
                     else { 'ReportServer' }
}

if ($true) {
    Write-Host ''
    Write-Host "Katalog veritabani: $SqlSunucu / $VeritabaniAdi"
    Write-Host ('-' * 55)

    $lcid = 1033
    $sqlcmd = 'C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\180\Tools\Binn\SQLCMD.EXE'

    # -I ZORUNLU: rapor sunucusu katalogu indeksli gorunum kullanir ve
    # QUOTED_IDENTIFIER ON ister. sqlcmd varsayilani OFF'tur.
    # Cikti da YUTULMAZ: ilk denemede hatayi gizledigi icin sorunun
    # yetki betiginde oldugu ancak elle kazarak anlasildi.
    function Calistir-SqlBetigi {
        param([string]$Yol, [string]$Etiket)
        $log = [System.IO.Path]::ChangeExtension($Yol, '.log')
        & $sqlcmd -S $SqlSunucu -E -C -I -f 65001 -b -i $Yol -o $log 2>&1 | Out-Null
        $basarili = ($LASTEXITCODE -eq 0)
        if (-not $basarili) {
            Write-Host "HATA   : $Etiket" -ForegroundColor Red
            if (Test-Path $log) {
                Get-Content $log -Encoding Unicode -ErrorAction SilentlyContinue |
                    Where-Object { $_.Trim() } | Select-Object -First 12 |
                    ForEach-Object { Write-Host "         $_" -ForegroundColor Red }
            }
            throw "SQL betigi basarisiz: $Etiket"
        }
        Write-Host "TAMAM  : $Etiket"
    }

    # Veritabani zaten varsa yeniden olusturma denenmez: olusturma betigi
    # kosulsuz CREATE DATABASE icerir ve ikinci kosuda patlar.
    $varMi = & $sqlcmd -S $SqlSunucu -E -C -I -h -1 -W -Q `
        "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'$VeritabaniAdi';"
    if (($varMi | Where-Object { $_ -match '^\s*\d+\s*$' } | Select-Object -First 1).Trim() -eq '0') {
        $olustur = $cfg.GenerateDatabaseCreationScript($VeritabaniAdi, $lcid, $false)
        if ($olustur.HRESULT -ne 0) { throw "Olusturma betigi uretilemedi (HRESULT=$($olustur.HRESULT))" }
        $g1 = Join-Path $env:TEMP 'rs_db_olustur.sql'
        [System.IO.File]::WriteAllText($g1, $olustur.Script, [System.Text.UTF8Encoding]::new($false))
        Calistir-SqlBetigi -Yol $g1 -Etiket 'katalog olusturuldu'
    } else {
        Write-Host "ATLANDI: $VeritabaniAdi zaten var"
    }

    # Katalog tohumlanmis mi? Olusturma betigi -I olmadan calistirilirsa
    # tablolar acilir ama kok klasor ('/') yazilmaz; rapor sunucusu
    # sonra rsItemNotFound ile 500 verir. Erken ve net soyleyelim.
    $kokSayisi = & $sqlcmd -S $SqlSunucu -E -C -I -h -1 -W -d $VeritabaniAdi -Q `
        "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Catalog;"
    $kok = ($kokSayisi | Where-Object { $_ -match '^\s*\d+\s*$' } | Select-Object -First 1)
    if ($kok -and $kok.Trim() -eq '0') {
        throw "Katalog bos ($VeritabaniAdi.dbo.Catalog = 0 satir). Yarim kalmis bir kurulum var. " +
              "Veritabanini dusurup betigi tekrar calistirin."
    }
    Write-Host "TAMAM  : katalog tohumlu ($($kok.Trim()) oge)"

    $servisKimlik = $cfg.WindowsServiceIdentityConfigured
    if (-not $servisKimlik) { throw 'Servis kimligi okunamadi (WindowsServiceIdentityConfigured bos).' }
    Write-Host "Servis kimligi: $servisKimlik"

    # Yetki betigi login'i OLUSTURMAZ; var oldugunu varsayar ve yoksa
    # "SQL Logon must exist!" diye durur. Once sunucu logini acilir.
    $loginBetik = Join-Path $env:TEMP 'rs_login.sql'
    $loginSql = @"
SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'$servisKimlik')
BEGIN
    CREATE LOGIN [$servisKimlik] FROM WINDOWS;
    PRINT 'login olusturuldu: $servisKimlik';
END
ELSE PRINT 'login zaten var: $servisKimlik';
"@
    [System.IO.File]::WriteAllText($loginBetik, $loginSql, [System.Text.UTF8Encoding]::new($false))
    Calistir-SqlBetigi -Yol $loginBetik -Etiket 'sunucu logini'

    # Imza: GenerateDatabaseRightsScript(UserName, DatabaseName, IsRemote, IsWindowsUser)
    # Onceki hali ($true, $false) "uzak sunucu + SQL kullanicisi" demekti;
    # uretilen betik Windows login'i degil SQL login'i ariyor ve var olan
    # hesabi goremeyip "SQL Logon must exist!" ile duruyordu.
    # Dogrusu: yerel sunucu (IsRemote=false), Windows hesabi (IsWindowsUser=true).
    $haklar = $cfg.GenerateDatabaseRightsScript($servisKimlik, $VeritabaniAdi, $false, $true)
    if ($haklar.HRESULT -ne 0) { throw "Yetki betigi uretilemedi (HRESULT=$($haklar.HRESULT))" }
    $g2 = Join-Path $env:TEMP 'rs_db_haklar.sql'
    [System.IO.File]::WriteAllText($g2, $haklar.Script, [System.Text.UTF8Encoding]::new($false))
    Calistir-SqlBetigi -Yol $g2 -Etiket 'servis hesabi yetkileri'

    # 2 = servis hesabi (entegre kimlik dogrulama)
    $bagla = $cfg.SetDatabaseConnection($SqlSunucu, $VeritabaniAdi, 2, '', '')
    if ($bagla.HRESULT -ne 0) { throw "Veritabani baglantisi kurulamadi (HRESULT=$($bagla.HRESULT))" }
    Write-Host "TAMAM  : katalog baglandi ($VeritabaniAdi)"

    $cfg = Get-WmiObject -Namespace $ns -Class MSReportServer_ConfigurationSetting | Select-Object -First 1
}

function Yaz-Sonuc {
    param($Sonuc, [string]$Etiket)
    # "Zaten ayarli / zaten rezerve" hatalari gercek hata degil: betik
    # yeniden calistirildiginda normal. Kirmizi yazmak gereksiz panik yaratiyordu.
    $zararsiz = @(-2147220930, -2147220932)   # UrlAlreadySet, UrlAlreadyReserved
    if ($Sonuc.HRESULT -eq 0) {
        Write-Host "TAMAM  : $Etiket"
    } elseif ($zararsiz -contains $Sonuc.HRESULT) {
        Write-Host "ATLANDI: $Etiket (zaten ayarli)"
    } else {
        $mesaj = if ($Sonuc.ExtendedErrors) { $Sonuc.ExtendedErrors -join ' | ' } else { $Sonuc.Error }
        Write-Host "HATA   : $Etiket  (HRESULT=$($Sonuc.HRESULT)) $mesaj" -ForegroundColor Red
    }
}

$lcid = 1033   # ingilizce hata mesajlari — aranabilir olsun diye

Write-Host ''
Write-Host "Yapilandirma (port $Port)"
Write-Host ('-' * 55)

Yaz-Sonuc $cfg.SetVirtualDirectory('ReportServerWebService', 'ReportServer', $lcid) `
          'sanal dizin: ReportServer (web servisi)'

Yaz-Sonuc $cfg.ReserveURL('ReportServerWebService', "http://+:$Port", $lcid) `
          "URL rezervasyonu: http://+:$Port/ReportServer"

Yaz-Sonuc $cfg.SetVirtualDirectory('ReportServerWebApp', 'Reports', $lcid) `
          'sanal dizin: Reports (web portali)'

Yaz-Sonuc $cfg.ReserveURL('ReportServerWebApp', "http://+:$Port", $lcid) `
          "URL rezervasyonu: http://+:$Port/Reports"

if (-not $cfg.IsInitialized) {
    Yaz-Sonuc $cfg.InitializeReportServer($cfg.InstallationID) 'rapor sunucusu baslatildi (initialize)'
} else {
    Write-Host 'ATLANDI: rapor sunucusu zaten initialize edilmis'
}

Write-Host ''
Write-Host 'Servis yeniden baslatiliyor...'
$servisAdi = if ($Instance -eq 'RS_PBIRS') { 'PowerBIReportServer' } else { 'SQLServerReportingServices' }
Restart-Service -Name $servisAdi -Force
Start-Sleep -Seconds 8

Write-Host ''
Write-Host 'Dogrulama'
Write-Host ('-' * 55)
$cfg2 = Get-WmiObject -Namespace $ns -Class MSReportServer_ConfigurationSetting | Select-Object -First 1
$son = $cfg2.ListReservedUrls()
for ($i = 0; $i -lt $son.Application.Count; $i++) {
    Write-Host "  $($son.Application[$i])  ->  $($son.UrlString[$i])"
}

foreach ($u in "http://localhost:$Port/ReportServer", "http://localhost:$Port/Reports") {
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -UseDefaultCredentials -TimeoutSec 90
        Write-Host "  $u  ->  HTTP $($r.StatusCode)"
    } catch {
        $k = $null; try { $k = $_.Exception.Response.StatusCode.value__ } catch {}
        Write-Host "  $u  ->  $(if ($k) { "HTTP $k" } else { $_.Exception.Message.Split([char]10)[0] })" -ForegroundColor Yellow
    }
}
Write-Host ''
Write-Host 'Ilk istek yavas olabilir (uygulama derleniyor). 200 gorurseniz hazir.'
Write-Host ''
