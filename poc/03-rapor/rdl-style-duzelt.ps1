<#
  RDL <Style> bloklarini 2016 semasina uydurur:
   1) BorderStyle/BorderColor/BorderWidth (eski, taraf-alt-elemanli bicim)
      -> Border / TopBorder / BottomBorder / LeftBorder / RightBorder
   2) Style alt elemanlarini sema sirasina gore yeniden dizer
#>
param([Parameter(Mandatory=$true)][string]$Path)

$ErrorActionPreference = 'Stop'

$SIRA = @(
  'Border','TopBorder','BottomBorder','LeftBorder','RightBorder',
  'BackgroundColor','BackgroundGradientType','BackgroundGradientEndColor',
  'BackgroundHatchType','BackgroundImage',
  'FontStyle','FontFamily','FontSize','FontWeight','Format','TextDecoration',
  'TextAlign','TextEffect','VerticalAlign','Color','ShadowColor','ShadowOffset',
  'PaddingLeft','PaddingRight','PaddingTop','PaddingBottom','LineHeight',
  'Direction','WritingMode','Language','UnicodeBiDi','Calendar',
  'NumeralLanguage','NumeralVariant'
)
$TARAF = @{ 'Default'='Border'; 'Left'='LeftBorder'; 'Right'='RightBorder';
            'Top'='TopBorder'; 'Bottom'='BottomBorder' }

$xml = New-Object System.Xml.XmlDocument
$xml.PreserveWhitespace = $false
$xml.Load($Path)
$ns = $xml.DocumentElement.NamespaceURI

function Yeni-Eleman([string]$ad) { $xml.CreateElement($ad, $ns) }

$styleler = @($xml.GetElementsByTagName('Style', $ns))
$donusen = 0; $dizilen = 0

foreach ($st in $styleler) {

    # --- 1) eski kenarlik bicimini topla ---
    $kenar = @{}   # hedefAd -> @{ Color=..; Style=..; Width=.. }

    foreach ($eskiAd in @('BorderStyle','BorderColor','BorderWidth')) {
        $eski = @($st.ChildNodes | Where-Object { $_.LocalName -eq $eskiAd })
        foreach ($e in $eski) {
            $ozellik = $eskiAd -replace '^Border',''      # Style | Color | Width
            foreach ($taraf in @($e.ChildNodes)) {
                $hedef = $TARAF[$taraf.LocalName]
                if (-not $hedef) { continue }
                if (-not $kenar.ContainsKey($hedef)) { $kenar[$hedef] = @{} }
                $kenar[$hedef][$ozellik] = $taraf.InnerText
            }
            [void]$st.RemoveChild($e)
            $donusen++
        }
    }

    # mevcut <Border> varsa onu da birlestir
    foreach ($hedefAd in @($TARAF.Values | Select-Object -Unique)) {
        $var = @($st.ChildNodes | Where-Object { $_.LocalName -eq $hedefAd })
        foreach ($v in $var) {
            if (-not $kenar.ContainsKey($hedefAd)) { $kenar[$hedefAd] = @{} }
            foreach ($c in @($v.ChildNodes)) {
                if (-not $kenar[$hedefAd].ContainsKey($c.LocalName)) {
                    $kenar[$hedefAd][$c.LocalName] = $c.InnerText
                }
            }
            [void]$st.RemoveChild($v)
        }
    }

    # yeniden olustur (Color, Style, Width sirasiyla)
    foreach ($hedefAd in $kenar.Keys) {
        $el = Yeni-Eleman $hedefAd
        foreach ($ozellik in @('Color','Style','Width')) {
            if ($kenar[$hedefAd].ContainsKey($ozellik)) {
                $c = Yeni-Eleman $ozellik
                $c.InnerText = $kenar[$hedefAd][$ozellik]
                [void]$el.AppendChild($c)
            }
        }
        if ($el.ChildNodes.Count -gt 0) { [void]$st.AppendChild($el) }
    }

    # --- 2) sema sirasina gore diz ---
    $cocuklar = @($st.ChildNodes)
    $sirali = $cocuklar | Sort-Object @{ Expression = {
        $i = $SIRA.IndexOf($_.LocalName)
        if ($i -lt 0) { 999 } else { $i }
    }}
    $degistiMi = $false
    for ($i = 0; $i -lt $cocuklar.Count; $i++) {
        if ($cocuklar[$i] -ne $sirali[$i]) { $degistiMi = $true; break }
    }
    if ($degistiMi) {
        foreach ($c in $cocuklar) { [void]$st.RemoveChild($c) }
        foreach ($c in $sirali)   { [void]$st.AppendChild($c) }
        $dizilen++
    }
}

$ayar = New-Object System.Xml.XmlWriterSettings
$ayar.Indent = $true
$ayar.IndentChars = '  '
$ayar.Encoding = New-Object System.Text.UTF8Encoding($false)
$w = [System.Xml.XmlWriter]::Create($Path, $ayar)
try { $xml.Save($w) } finally { $w.Close() }

Write-Host "Style blogu       : $($styleler.Count)"
Write-Host "Kenarlik donusumu : $donusen eski eleman"
Write-Host "Yeniden dizilen   : $dizilen blok"
