# ===================================================================
#  SatisDashboardPBI.pbix -> PBIRS
#  Rapor varsa uzerine yazar, yoksa olusturur.
#    .\pbix-yukle.ps1
# ===================================================================
param(
  [string]$Portal = 'http://localhost/Reports',
  [string]$Ad     = 'SatisDashboardPBI',
  [string]$Dosya  = "$PSScriptRoot\SatisDashboardPBI.pbix"
)
$ErrorActionPreference = 'Stop'
$api  = "$Portal/api/v2.0"
$yol  = "/$Ad"

if (-not (Test-Path $Dosya)) { throw "Dosya yok: $Dosya  (once: node pbix-uret.js)" }

$b64   = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Dosya))
$govde = @{
  '@odata.type' = '#Model.PowerBIReport'
  ContentType   = ''
  Content       = $b64
  Name          = $Ad
  Path          = $yol
} | ConvertTo-Json -Compress

$mevcut = (Invoke-RestMethod "$api/CatalogItems" -UseDefaultCredentials).value |
          Where-Object { $_.Path -eq $yol } | Select-Object -First 1

try {
  if ($mevcut) {
    Invoke-RestMethod "$api/PowerBIReports($($mevcut.Id))" -Method Put -UseDefaultCredentials `
      -ContentType 'application/json' -Body $govde | Out-Null
    $id = $mevcut.Id
    Write-Host "  guncellendi  Id=$id"
  } else {
    $y  = Invoke-RestMethod "$api/CatalogItems" -Method Post -UseDefaultCredentials `
            -ContentType 'application/json' -Body $govde
    $id = $y.Id
    Write-Host "  olusturuldu  Id=$id"
  }
} catch {
  Write-Host "  HATA: $($_.Exception.Message)"
  # Gercek sebep her zaman PBIX surecinin logunda; portal yalnizca 422 doner.
  $l = Get-ChildItem 'C:\Program Files\Microsoft Power BI Report Server\PBIRS\LogFiles' `
         -Filter 'RSPowerBI*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Get-Content $l.FullName -Tail 30 | Select-String 'Exception:|Failure in' |
    Select-Object -First 3 | ForEach-Object { Write-Host ("  " + $_.Line.Trim()) }
  exit 1
}

$ds = Invoke-RestMethod "$api/PowerBIReports($id)/DataSources" -UseDefaultCredentials
foreach ($d in $ds.value) {
  Write-Host "  baglanti     $($d.ConnectionString)"
  Write-Host "  tur          $($d.DataModelDataSource.Type) / $($d.DataModelDataSource.AuthType)"
}
Write-Host "  adres        $Portal/powerbi/$Ad"
