# ===================================================================
#  RDL -> PBIRS
#  Rapor varsa tanimini uzerine yazar, yoksa olusturur.
#    .\rdl-yukle.ps1                      # CevapKarti
#    .\rdl-yukle.ps1 -Ad SatisDashboard
#
#  NEDEN SOAP, NEDEN REST DEGIL: REST v2.0 gecersiz bir RDL'e BOS
#  GOVDELI 500 doner — hangi elemanin nerede yanlis oldugu kaybolur.
#  SOAP (ReportService2010.SetItemDefinition) ise sema hatasini tam
#  metniyle soyler: "element X has invalid child element Y. List of
#  possible elements expected: ...". RDL 2016 semasi siki siralidir,
#  bu mesaj olmadan hata aramak korebe oyunu.
#
#  Not: RDL'in kendi ConnectString'i gomulu ve IntegratedSecurity
#  oldugu icin yukleme sonrasi kimlik ayari gerekmiyor.
# ===================================================================
param(
  [string]$Sunucu = 'http://localhost/ReportServer',
  [string]$Ad     = 'CevapKarti',
  [string]$Dosya,
  [string]$Klasor = '/'
)
$ErrorActionPreference = 'Stop'
if (-not $Dosya) { $Dosya = Join-Path $PSScriptRoot "$Ad.rdl" }
if (-not (Test-Path $Dosya)) { throw "Dosya yok: $Dosya" }

$rs  = New-WebServiceProxy -Uri "$Sunucu/ReportService2010.asmx?wsdl" -UseDefaultCredential
$def = [IO.File]::ReadAllBytes($Dosya)
$yol = if ($Klasor -eq '/') { "/$Ad" } else { "$Klasor/$Ad" }

$var = $null
try { $var = $rs.GetItemType($yol) } catch { $var = 'Unknown' }

try {
  if ($var -eq 'Report') {
    $uyari = $rs.SetItemDefinition($yol, $def, $null)
    Write-Host "  guncellendi  $yol"
  } else {
    $uyari = $rs.CreateCatalogItem('Report', $Ad, $Klasor, $true, $def, $null, [ref]$null)
    Write-Host "  olusturuldu  $yol"
  }
} catch {
  $m = $_.Exception.Message
  # Sema hatasinin okunur kismi "Details:" ile baslar.
  $i = $m.IndexOf('Details:')
  Write-Host '  HATA'
  if ($i -ge 0) { Write-Host ('  ' + $m.Substring($i)) } else { Write-Host ('  ' + $m) }
  exit 1
}

foreach ($u in @($uyari)) {
  if ($u) { Write-Host ("  UYARI  $($u.Code) :: $($u.Message)") }
}
Write-Host "  adres        $($Sunucu)?$yol&rs:Command=Render"
