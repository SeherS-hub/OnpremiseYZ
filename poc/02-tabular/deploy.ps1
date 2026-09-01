<#
  Tabular modeli SSAS'a dağıt ve işle (process).

  TMSL, XMLA uç noktası üzerinden gönderilir — SSMS'in "XMLA sorgusu"
  penceresinin yaptığı işin aynısı, betikle.

  Kullanım:
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy.ps1 -Server SUNUCU\TABULAR

  Ön koşul: SSAS **Tabular mod** kurulu ve çalışıyor olmalı, çalıştıran
  kullanıcı SSAS üzerinde sunucu yöneticisi olmalı.
#>
param(
    [string]$Server   = 'localhost',
    [string]$TmslFile = (Join-Path $PSScriptRoot 'SatisOzet.tmsl.json'),
    [string]$Database = 'POC_SatisOzet',
    [switch]$SadeceIsle    # modeli yeniden dağıtmadan yalnızca veri tazele
)

$ErrorActionPreference = 'Stop'

function Yukle-Adomd {
    $adaylar = @(
        'C:\Program Files\Microsoft.NET\ADOMD.NET\170\Microsoft.AnalysisServices.AdomdClient.dll',
        'C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll',
        'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE\Microsoft.AnalysisServices.AdomdClient.dll'
    )
    $dll = $adaylar | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $dll) { throw 'ADOMD.NET istemcisi bulunamadi. SSMS kurulu olmali.' }
    Add-Type -Path $dll
    Write-Host "ADOMD  : $dll"
}

function Calistir-Xmla {
    param([string]$Sunucu, [string]$Katalog, [string]$Komut, [string]$Etiket)

    $cs = "Data Source=$Sunucu;Integrated Security=SSPI;"
    if ($Katalog) { $cs = "Data Source=$Sunucu;Catalog=$Katalog;Integrated Security=SSPI;" }

    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($cs)
    try {
        $conn.Open()
        $cmd = $conn.CreateCommand()
        $cmd.CommandText    = $Komut
        $cmd.CommandTimeout = 600
        [void]$cmd.ExecuteNonQuery()
        Write-Host "TAMAM  : $Etiket"
    }
    finally {
        if ($conn.State -eq 'Open') { $conn.Close() }
    }
}

Write-Host ''
Write-Host 'Tabular model dagitimi'
Write-Host ('-' * 50)
Write-Host "Sunucu : $Server"
Write-Host "Model  : $Database"

Yukle-Adomd

if (-not $SadeceIsle) {
    if (-not (Test-Path $TmslFile)) { throw "TMSL dosyasi bulunamadi: $TmslFile" }
    $tmsl = Get-Content -Path $TmslFile -Raw -Encoding UTF8

    # Ön kontrol: JSON gecerli mi
    try { $null = $tmsl | ConvertFrom-Json }
    catch { throw "TMSL gecerli JSON degil: $($_.Exception.Message)" }

    Write-Host "TMSL   : $TmslFile ($([math]::Round($tmsl.Length/1kb,1)) KB)"
    Calistir-Xmla -Sunucu $Server -Komut $tmsl -Etiket 'model olusturuldu / guncellendi (createOrReplace)'
}

# Veriyi yükle
$refresh = @"
{
  "refresh": {
    "type": "full",
    "objects": [ { "database": "$Database" } ]
  }
}
"@
Calistir-Xmla -Sunucu $Server -Komut $refresh -Etiket 'veri islendi (full refresh)'

# Doğrulama: satır sayısı ve bir ölçü
Write-Host ''
Write-Host 'Dogrulama'
Write-Host ('-' * 50)
$dogrulamaDax = 'EVALUATE ROW ( "Satir", COUNTROWS ( SatisOzet ), "NetCiro", [Net Ciro], "EnYuksekAy", [En Yüksek Ay] )'
$gecici = Join-Path $env:TEMP ('poc_dogrula_' + $PID + '.dax')
$dogrulamaDax | Out-File -FilePath $gecici -Encoding utf8
try {
    & (Join-Path $PSScriptRoot '..\04-ajan\lib\dax-sorgu.ps1') -Server $Server -Database $Database -QueryFile $gecici
} finally {
    Remove-Item $gecici -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host 'Bitti. Ajani su sekilde SSAS moduna alabilirsiniz:'
Write-Host "  $env:POC_SSAS_SUNUCU = '$Server'"
Write-Host '  $env:POC_MOTOR = "dax"'
Write-Host '  node sunucu.js'
Write-Host ''
