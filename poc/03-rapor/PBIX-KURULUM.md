# `SatisDashboardPBI.pbix`

Dashboard sıfırdan `.pbix` olarak üretiliyor — RDL'den dönüştürülmüyor, elle
tuvale yerleştirilmiyor. Üretici: `pbix-uret.js`.

```
node pbix-uret.js
```

Çıktı: `SatisDashboardPBI.pbix` — ~4 KB, SSAS Tabular'a **canlı bağlı**, tek
sayfa 1280×720, 11 görsel. Bağımlılık yok; ZIP paketi betiğin kendi içinde
yazılıyor.

Ortam değişkenleriyle hedef değiştirilebilir:

| Değişken | Varsayılan |
|---|---|
| `POC_SSAS_SUNUCU` | `localhost\TABULAR` |
| `POC_SSAS_MODEL` | `POC_Satis` |
| `POC_AJAN_URL` | `http://localhost:8787/` |

---

## Sayfa düzeni

```
┌─────────────────────────────────────────────────┬──────────┐
│ SATIŞ PERFORMANSI                               │  DÖNEM   │
│ Kaynak: SSAS Tabular · POC_Satis · canlı        │ (slicer) │
├──────────┬──────────┬──────────┬────────────────┤          │
│ NET CİRO │  HEDEF   │  SATIŞ   │    ORTALAMA    │          │
│          │ GERÇ. %  │  ADEDİ   │     SEPET      │          │
├──────────┴──────────┴──────────┴────────────────┤──────────┤
│  Yönetici Asistanına sor →  (köprülü metin)     │          │
├────────────────────────────────────┬────────────┴──────────┤
│  AYLIK CİRO VE HEDEF               │  BÖLGE KIRILIMI       │
│  (kolon: gerçekleşen, çizgi: hedef)│  (tablo)              │
├──────────────────┬─────────────────┴───────────────────────┤
│ ÜRÜN GRUBU ×     │  AYLIK DETAY                            │
│ KANAL (matris)   │  dönem · ciro · hedef · gerç. · Δ · küm.│
└──────────────────┴─────────────────────────────────────────┘
```

Tüm ölçüler modelden geliyor; raporda tek bir DAX tanımı yok. Renkler
`poc-tema.json` paletiyle aynı ama doğrudan görsellere yazılıyor — dosya tema
seçilmeden de doğru görünüyor.

---

## Doğrulama

Rapor PBIRS'e yüklendi ve **tarayıcıda çizdirilerek** doğrulandı; ekran
görüntüsü ve konsol kayıtları Chrome DevTools protokolüyle alındı.

| Denetim | Sonuç |
|---|---|
| OPC/ZIP paketi | geçerli |
| `Version` doğrulaması | `1.22` kabul |
| Bağlantı ayrıştırma | `Data Source=localhost\TABULAR;Initial Catalog=POC_Satis` · Live · Integrated |
| Yerleşim ayrıştırma | 11 görsel, alan bağlarının tamamı çözüldü |
| İstemci çağrıları | `modelsAndExploration` → `conceptualschema` → `querydata`, hepsi 200 |
| Çizim | 11 görselin tamamı veriyle doldu |
| Rakamlar | 892.450.000 TL · %100,6 · 130.600 · 6.833 TL — RDL dashboard'la aynı |

Ayrıştırılan görseller ve bağlandıkları alanlar:

```
slcDonem   slicer                          Donem.Dönem
kpiCiro    card                            Satis.Net Ciro
kpiHedef   card                            Satis.Hedef Gerçekleşme %
kpiAdet    card                            Satis.Satış Adet
kpiSepet   card                            Satis.Ortalama Sepet
grfTrend   lineClusteredColumnComboChart   CiroSerisi.Dönem,
                                           CiroSerisi.Gerçekleşen Ciro, CiroSerisi.Tahmin,
                                           CiroSerisi.Aylık Hedef,
                                           CiroSerisi.Tahmin %80 Üst, CiroSerisi.Tahmin %80 Alt
tblBolge   tableEx                         Bolge.Bölge, Satis.Net Ciro, Satis.Hedef Gerçekleşme %
mtrUrun    pivotTable                      UrunGrubu.Ürün Grubu, Kanal.Kanal, Satis.Net Ciro
tblAy      tableEx                         Donem.Dönem, Satis.Net Ciro, Satis.Hedef,
                                           Satis.Hedef Gerçekleşme %, Satis.Aylık Değişim %,
                                           Satis.Kümülatif Ciro
```

Görsellerin biçim özellikleri (renk, gösterim birimi, düğme aksiyonu) yumuşak
başarısız olur: yanlışsa görsel varsayılanına döner, dosya bozulmaz.

Önizleme: `onizleme/SatisDashboardPBI.png`. Yenilemek için:

```powershell
node tarayici-goruntu.js http://localhost/Reports/powerbi/SatisDashboardPBI `
     onizleme\SatisDashboardPBI.png 18
```

### Doğrulama neden tarayıcıda yapılıyor

`.pbix` sunucu tarafında **çizdirilemiyor** — PBIRS REST v2.0, `PowerBIReport`
için `Render` işlemi sunmuyor (yalnız `Upload`, `CheckDataSourceConnection`,
`AccessToken`). Bu yüzden `tarayici-goruntu.js` headless tarayıcıyı CDP ile
sürüyor: PNG alıyor, konsol hatalarını topluyor ve görsel sayısını sayıyor.
RDL için gerek yok, onu sunucu PNG olarak veriyor.

Betiği yazarken dört tuzağı ölçmek gerekti — dördü de **sessizce yanlış
ölçüm** üretiyordu, hata vermiyordu:

| Tuzak | Belirti | Çözüm |
|---|---|---|
| Rapor tuvali **iframe** içinde (`/powerbi/?id=…`) | üst belgede `visual-container` sayısı 0 → çalışan rapor bozuk sanılıyor | aynı kökenli iframe'ler de taranıyor |
| `--headless=new` ile `--screenshot` çıktı üretmiyor | dosya hiç oluşmuyor, hata da yok | CDP `Page.captureScreenshot` |
| Sabit bekleme sonrası yakalama | yarı dolu sayfa; bir kez iyi önizlemenin üstüne "Loading data…" ekranı yazıldı | `querydata` çağrıları durana kadar yoklama |
| Kırpılmış öğeye tıklama | koordinat DOM'da var ama tıklama arka plana düşüyor, seçim olmuyor | `elementFromPoint` ile noktadaki gerçek öğe doğrulanıyor |

Hazır olma ölçütü için denenip **elenen** iki aday: görsel kabı sayısı
(kaplar boşken de sayılıyor) ve metnin durağanlaşması (boş kartların metni de
durağan). Çalışan ölçüt, her görselin kendi veri çağrısını atması: son
`querydata` yanıtından sonra 3 saniye yenisi gelmiyorsa çizim bitmiştir.

Etkileşimi denemek için `--tikla`:

```powershell
node tarayici-goruntu.js --tikla "2026-01" http://localhost/Reports/powerbi/SatisDashboardPBI secim.png 32
```

Sentetik `.click()` Power BI'da kullanıcı hareketi sayılmıyor; betik CDP
`Input.dispatchMouseEvent` ile gerçek fare olayı gönderiyor.

Aynı iş önce PowerShell `ClientWebSocket` ile yazıldı ve iki yerde kırıldı:
`about:blank`'ten `Page.navigate` ile gezinmek hedefi değiştirip soketi sessizce
koparıyor, ekran görüntüsünün base64'ü ise onlarca çerçeveye bölünüyor ve elle
birleştirmek güvenilir olmadı. Node'un yerleşik `WebSocket`'i ikisini de çözüyor.

### Konsolda kalıcı iki hata — zararsız

Bu PBIRS kurulumunda her raporda görünüyorlar, **çalışan raporda da**:

```
GET /powerbi/libs/scripts/stylelibrary.js → 404
NullInjectorError: No provider for InjectionToken PBICopilotProxy!
```

Dosya kurulumda hiç yok (`Get-ChildItem -Recurse -Filter stylelibrary*` boş
dönüyor), Copilot sağlayıcısı da bu sürümde kayıtlı değil. Teşhis sırasında
bunları suçlamak zaman kaybı; ayırt edici hata mesajını aramak gerekiyor.

### Tahmin serisi eklerken çıkan gerçek hata

Trend görseline tahmin serileri eklendiğinde rapor **hiç çizilmedi** — tuval
"Loading data…"da kaldı ve konsolda şu vardı:

```
TypeError: Cannot read properties of undefined (reading 'visual')
  at g.getInheritParentColors
```

Sunucu tarafı sağlamdı: `RSPowerBI` günlüğünde DAX sorguları çevrilmiş ve
hepsi 200 dönmüştü. Yani hata istemcide, renk çözümlemesinde.

Teşhisin kilidini açan adım, **değişiklikten önceki `.pbix`'i geri yükleyip
denemek** oldu: o çizdi. Böylece "ortam bozuldu" seçeneği elendi ve hata
kesinlikle yapılan değişikte arandı. Sonrasında model ölçüleri yeniden
adlandırılıp tablo yeniden dağıtıldığında aynı görsel yapılandırması sorunsuz
çizdi — belirti, istemcinin `dataPoint` seçicisindeki `metadata` adını o anki
şemada çözememesiyle uyumlu. Ders: **model değişikliğinden sonra `.pbix`'i
yeniden yükleyip sayfayı tazelemek**, ve renk seçicisi eklerken metadata adının
modelde birebir var olduğunu doğrulamak.

---

## `.pbix` paketinin iç yapısı

Canlı bağlantılı bir raporda paket içinde **veri modeli yoktur**; yalnızca
bağlantı tanımı ve yerleşim vardır. Bu yüzden dosya deterministik olarak
üretilebiliyor.

| Parça | Kodlama | İçerik |
|---|---|---|
| `Version` | UTF-16LE, BOM'suz | `1.22` |
| `Connections` | **UTF-8** | SSAS canlı bağlantı tanımı |
| `Report/Layout` | UTF-16LE, BOM'suz | görsel yerleşimi |
| `Report/StaticResources/SharedResources/BaseThemes/CY24SU10.json` | UTF-8 | tema (bkz. aşağısı) |
| `[Content_Types].xml` | UTF-8 | OPC içerik tipleri |

`Settings`, `Metadata`, `SecurityBindings` isteğe bağlı — Power BI Desktop ilk
kaydedişinde kendisi oluşturur.

### Tema kaynak paketi zorunlu

**Bu, tuvalin boş kalmasının sebebiydi.** Sunucu paketi kabul ediyor, yerleşimi
doğru ayrıştırıyor, istemci `modelsAndExploration` çağrısını yapıyor — ve
duruyordu. Ne hata mesajı ne de yükleniyor göstergesi vardı; `exploration-container`
bileşeni bağlanıyor ama içi boş kalıyordu.

Sebep: `Report/Layout` içinde tema yoktu. Gerçek `.pbix` dosyalarında tema
her zaman gömülü bir kaynak paketi olarak gelir; istemci temayı çözemeyince
görselleri hiç çizmiyor. Yalnızca `config.themeCollection`'a bir ad yazmak da
yetmiyor — kaynağın paket içinde gerçekten bulunması gerekiyor.

Gereken üç parça birlikte:

```
Report/Layout
  resourcePackages: [ { resourcePackage: {
      name: 'SharedResources', type: 2, disabled: false,
      items: [ { name: 'CY24SU10', path: 'BaseThemes/CY24SU10.json', type: 202 } ] } } ]
  config.themeCollection: { baseTheme: { name: 'CY24SU10', version: '5.43', type: 2 } }

Report/StaticResources/SharedResources/BaseThemes/CY24SU10.json
  (gecerli bir Power BI tema belgesi — burada poc-tema.json)
```

Tema eklendikten sonra istemci sırayla `resourcePackageItem`, `conceptualschema`
ve `querydata` çağrılarını yapıyor; rapor doluyor.

### İki kodlama tuzağı

Bunlar sessizce başarısız olmaz, ama hata mesajları yanıltıcıdır:

**BOM bırakmak.** `Version` parçasına BOM konursa `PowerBIPackager.ValidateVersion`
sürümü `?1.22` okur ve `'?1.22' is not a valid .pbix file version number` der.
BOM'suz UTF-16LE yazılmalı.

**`Connections`'ı UTF-16 yazmak.** Bu parça tek baytlık okunuyor. UTF-16 yazılırsa
her karakterin ardındaki NUL, `Data Source=localhost\TABULAR` içindeki ters
bölüyü bozar: `Bad JSON escape sequence: \` hatası gelir. UTF-8 olmalı.

---

> **Uyarı:** `stylelibrary.js` için tarayıcı konsolunda görülen 404 zararsız.
> İstemcinin ana sayfası bu dosyayı istiyor, sunucu yalnızca `stylelibrary.min.js`
> sürümünü sunuyor. Rapor bu hatayla birlikte sorunsuz çiziliyor — boş tuvalin
> sebebi bu değildi.

---

## Yükleme

```
.\pbix-yukle.ps1
```

Rapor varsa üzerine yazar, yoksa oluşturur; ardından veri kaynağı bağlantısını
gösterir. Hata durumunda gerçek sebebi `RSPowerBI` logundan okur — portal her
zaman yalnızca `422` döndürüyor, kullanışlı mesaj logda.

Tam döngü:

```
node pbix-uret.js
.\pbix-yukle.ps1
```

Power BI Desktop RS'te açıp değiştirmek de mümkün: dosyayı çift tıkla, düzenle,
**File → Save as → Power BI Report Server**. Desktop kaydettiğinde eksik
parçaları da ekler.

---

## PBIRS'te PBIX alt sistemi

Bu kurulumda `.pbix` yüklemesi başta 422 ile reddediliyordu. Sebep dosya değil,
sunucuydu: **PBIRS'in PowerBI ve Office süreçleri hiç başlamıyordu.**

```
FATAL | Could not start PBIX
        System.Net.HttpListenerException: Access is denied
        at System.Net.HttpListener.AddAllPrefixes()
```

`RSHostingService`, `RSPowerBI.exe` ve `RSOffice.exe` süreçlerini başlatıyor;
bunlar `http://+:80/powerbi/` ve `http://+:80/office/` adreslerini dinlemek
istiyor. Bu iki URL rezervasyonu eksikti. RDL raporları etkilenmediği için
sorun görünmüyordu — PBIX'e geçilene kadar.

Düzeltme (yönetici):

```powershell
netsh http add urlacl url=http://+:80/powerbi/ user="NT SERVICE\PowerBIReportServer"
netsh http add urlacl url=http://+:80/office/  user="NT SERVICE\PowerBIReportServer"
Restart-Service PowerBIReportServer -Force
```

Doğrulama — üç değil beş prefiks kayıtlı olmalı:

```powershell
netsh http show servicestate view=requestq verbose=yes |
    Select-String '^\s*HTTP://' | Sort-Object -Unique
```

`RSPowerBI` ve `RSOffice` süreçleri `Get-Process` çıktısında kalıcı olarak
görünüyorsa alt sistem ayakta demektir.

> Dinleme adresini bulmak için `RSPowerBI.exe.config`'e geçici olarak
> `System.Net.HttpListener` izlemesi eklendi; izlem `AddPrefix(uriPrefix:
> http://+:80/powerbi/)` satırını yazdı. Yapılandırma sonrasında yedeğinden
> geri alındı.

---

## `.pbix`'in yapamadığı

PBIRS REST API'sinde `Model.PowerBIReport` için tanımlı işlemler yalnızca
`Upload`, `CheckDataSourceConnection`, `AccessToken`. **Sunucu tarafında
render/export işlemi yok.**

| İş | RDL | `.pbix` |
|---|---|---|
| Tarayıcıda etkileşimli görüntüleme | ✔ | ✔ (daha iyi) |
| Sunucudan PNG/PDF/CSV render | ✔ | ✘ |
| URL ile parametre/filtre | ✔ | ✔ (`?filter=`) |
| Satır bazında URL action | ✔ temiz | ✔ ama kırılgan |

Bu yüzden **cevap kartı RDL kalıyor**: her cevap tek bir görüntüye basılıp
popup'a, e-postaya ve denetim arşivine konabiliyor. Dashboard'ın işi etkileşim,
o `.pbix`.

---

## Ajana geçiş şeridi — `actionButton` değil, köprülü metin kutusu

Dashboard'ın üstündeki teal şerit bir **düğme değil**. `actionButton` görselinin
web adresi aksiyonu (`vcObjects.visualLink`) bu istemcide çalışmıyor:

- görsel kabına `role="link"` ekleniyor, yani tanım okunuyor;
- ama tıklama hiçbir şey yapmıyor — sentetik tıklama da, gerçek fare olayı da,
  odaklanmış öğede Enter de tetiklemiyor;
- düğmenin kendi metin objesi (`objects.text`) de çizilmiyor, şerit boş görünüyor.

Yerine metin kutusunun **köprülü metin parçası** kullanılıyor. Bu Power BI'ın
birinci sınıf özelliği ve gerçek bir `<a href target="_blank">` üretiyor:

```js
paragraphs: [{
  horizontalTextAlignment: 'center',
  textRuns: [{
    value: 'Yönetici Asistanına sor — sesli veya yazılı  →',
    url: 'http://localhost:8787/',
    textStyle: { fontSize: '11pt', fontWeight: 'bold', color: '#FFFFFF',
                 textDecoration: 'none' }
  }]
}]
```

Şerit görünümü `vcObjects.background` ile veriliyor (teal dolgu, kenarlık ve
başlık kapalı). Doğrulandı: gerçek tıklamada `http://localhost:8787/` yeni
sekmede açılıyor.

> Sentetik `element.click()` ile test etmek yanıltıcı — tarayıcı bunu kullanıcı
> hareketi saymadığı için `target="_blank"` engellenir ve bağlantı bozukmuş gibi
> görünür. CDP `Input.dispatchMouseEvent` ile gerçek tıklama göndermek gerekiyor.

---

## Ajan bağlantısı

Ajanın "Ana dashboard'a git" aksiyonu artık `.pbix` raporuna gidiyor
(`poc/04-ajan-py/sunucu.py`):

```js
cevap.dashboardUrl = AYAR.raporTaban + '/powerbi/SatisDashboardPBI';
```

PBIX raporlarının yolu `/report/` değil **`/powerbi/`** altında. Eski RDL
dashboard `/SatisDashboard` adresinde duruyor; karşılaştırma bitince
silinebilir.
