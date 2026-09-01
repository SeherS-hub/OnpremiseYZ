<#
  POC Yönetici Asistanı — kalıcı çalıştırma (Zamanlanmış Görev)

  Neden servis değil de görev: Python süreci Windows servis denetim
  mesajlarına cevap vermez; sc.exe ile doğrudan servis yapılırsa
  "zamanında cevap vermedi" hatası alınır. Gerçek servis için NSSM gibi
  bir sarmalayıcı ikili gerekir. Zamanlanmış görev aynı sonucu (açılışta
  başla, çökerse yeniden başlat) dış bağımlılık olmadan verir.

  KİMLİK — S4U, bilerek:
  Görev önce etkileşimli oturumda koşuyordu ve konsolu paylaştığı için
  başka bir sürece gönderilen Ctrl+C ajanı da düşürüyordu (logda ^C).
  S4U parolasız, etkileşimsiz oturum verir; konsol paylaşımı biter.
  Kullanıcının kimliğiyle koşmaya devam eder — SQL ve SSAS'a Windows
  kimlik doğrulamasıyla bağlandığı için bu şart.

  Kullanım:
    .\gorev-kur.ps1            # kur (veya güncelle)
    .\gorev-kur.ps1 -Durum     # durumu göster
    .\gorev-kur.ps1 -Baslat    # şimdi başlat
    .\gorev-kur.ps1 -Durdur    # durdur
    .\gorev-kur.ps1 -Kaldir    # görevi sil
#>
param(
    [switch]$Durum,
    [switch]$Baslat,
    [switch]$Durdur,
    [switch]$Kaldir
)

$ErrorActionPreference = 'Stop'

$GorevAdi = 'POC-YoneticiAsistani'
$Dizin    = $PSScriptRoot
$Cmd      = Join-Path $Dizin 'ajan-baslat.cmd'
$Port     = 8787

function Gorev { Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue }

function PortDurumu {
    $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($c) { "dinleniyor (PID $($c[0].OwningProcess))" } else { 'kapali' }
}

function DurumGoster {
    $g = Gorev
    Write-Host ''
    if (-not $g) { Write-Host "  Gorev yok: $GorevAdi"; Write-Host ''; return }
    Write-Host "  Gorev   : $GorevAdi"
    Write-Host "  Durum   : $($g.State)"
    Write-Host "  Kimlik  : $($g.Principal.UserId)  logon=$($g.Principal.LogonType)"
    Write-Host "  Eylem   : $($g.Actions[0].Arguments)"
    Write-Host "  Port    : $Port — $(PortDurumu)"
    try {
        $s = Invoke-RestMethod "http://localhost:$Port/api/saglik" -TimeoutSec 5
        Write-Host "  Saglik  : $($s.calismaZamani) · SSAS $($s.ssas.erisim) · $($s.metrikSayisi) metrik"
    } catch {
        Write-Host "  Saglik  : ulasilamiyor"
    }
    Write-Host ''
}

if ($Durum)  { DurumGoster; return }
if ($Baslat) { Start-ScheduledTask -TaskName $GorevAdi; DurumGoster; return }
if ($Durdur) {
    Stop-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*sunucu.py*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    DurumGoster; return
}
if ($Kaldir) {
    Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  Gorev kaldirildi: $GorevAdi"
    return
}

# ---- kurulum ----
if (-not (Test-Path $Cmd)) { throw "Baslatma betigi yok: $Cmd" }

$eylem = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument "/c `"$Cmd`"" -WorkingDirectory $Dizin
$tetik = New-ScheduledTaskTrigger -AtLogOn
$kimlik = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Limited
$ayar = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable

Register-ScheduledTask -TaskName $GorevAdi -Action $eylem -Trigger $tetik `
    -Principal $kimlik -Settings $ayar -Force | Out-Null

Write-Host ''
Write-Host "  Kuruldu: $GorevAdi"
Write-Host "  Acilista baslar, cokerse 1 dk arayla 3 kez yeniden dener."
DurumGoster
