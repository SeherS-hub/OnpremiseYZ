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
    [string]$Server   = 'localhost\TABULAR',
    [string]$TmslFile = (Join-Path $PSScriptRoot 'SatisModel.tmsl.json'),
    [string]$Database = 'POC_Satis',
    [string]$Tablo    = '',   # verilirse yalnız o tablo işlenir (tablo düzeyi TMSL)
    [switch]$SadeceIsle       # modeli yeniden dağıtmadan yalnızca veri tazele
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

# Veriyi yükle. -Tablo verildiyse yalnız o tablo: tek tablo eklerken
# tum modeli islemek hem gereksiz hem de uzun.
if ($Tablo) {
    $hedef = "{ ""database"": ""$Database"", ""table"": ""$Tablo"" }"
    $etiket = "tablo islendi (full refresh · $Tablo)"
} else {
    $hedef = "{ ""database"": ""$Database"" }"
    $etiket = 'veri islendi (full refresh)'
}
$refresh = @"
{
  "refresh": {
    "type": "full",
    "objects": [ $hedef ]
  }
}
"@
Calistir-Xmla -Sunucu $Server -Komut $refresh -Etiket $etiket

# Doğrulama: model gözatıcısı ile bir DAX çalıştır. (Eskiden burada
# 04-ajan/lib/dax-sorgu.ps1 çağrılıyordu; Node sürümü emekliye
# ayrılınca o dosya kalmadı, doğrulama adımı sessizce kırılmıştı.)
Write-Host ''
Write-Host 'Dogrulama'
Write-Host ('-' * 50)
$dax = if ($Tablo) {
    "EVALUATE ROW ( ""Satir"", COUNTROWS ( '$Tablo' ) )"
} else {
    'EVALUATE ROW ( "Satir", COUNTROWS ( Satis ), "NetCiro", [Net Ciro], "EnYuksekAy", [En Yüksek Ay] )'
}
# DAX'i DOSYADAN geciriyoruz: PowerShell, native exe argumaninin icindeki
# cift tirnaklari yiyor ve sorgu bozuluyor. Bu tuzaga bu depoda birkac kez
# dusuldu; kalici cozum dosya.
$gecici = Join-Path $env:TEMP ('poc_dogrula_' + $PID + '.dax')
[IO.File]::WriteAllText($gecici, $dax, (New-Object Text.UTF8Encoding $false))
$gozat = Join-Path $PSScriptRoot '..\04-ajan-py\araclar\model_gozat.py'
$py = if (Test-Path 'C:\Python312\python.exe') { 'C:\Python312\python.exe' } else { 'python' }
try {
    & $py $gozat --sunucu $Server --model $Database --dax-dosya $gecici
} finally {
    Remove-Item $gecici -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host 'Bitti.'
Write-Host ''
