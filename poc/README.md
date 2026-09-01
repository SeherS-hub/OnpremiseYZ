# PoC · Kapalı Devre Yönetici Asistanı

Uçtan uca çalışan bir kanıtlama: **SQL Server → SSAS Tabular semantik model → RS dashboard → rapordan action ile ajan → sesli/metin soru-cevap.**

Bu dizin, `docs/kapali-devre-yonetici-asistani.md` spesifikasyonunun somut, çalıştırılabilir küçük kardeşidir. Spek "nasıl yapılır" diyor; burası "işte yapıldı" diyor.

| Doküman | İçerik |
|---|---|
| **Bu dosya** | Ne kuruldu, nasıl çalıştırılır, nasıl gösterilir |
| [`04-ajan-py/README.md`](04-ajan-py/README.md) | **Python portu** — çalışan sürüm bu. Ölçülen kazanç: cevap ~750 ms → ~20 ms |
| [`UYGULAMA-PLANI.md`](UYGULAMA-PLANI.md) | Adım adım kurulum + **her adımın testi** + gerçek ortama taşıma koşulları |
| [`GERCEK-ORTAMA-GECIS.md`](GERCEK-ORTAMA-GECIS.md) | PoC'den kurumsal kuruluma: sözleşme üretimi, RLS, dağıtım, yerel STT |
| [`../docs/kapali-devre-yonetici-asistani.md`](../docs/kapali-devre-yonetici-asistani.md) | Spesifikasyon — 21 bölüm, mimari kararlar, risk kaydı, uçtan uca değerlendirme |

---

## 0 · Bu makinedeki durum

30.08.2026 itibarıyla:

| Bileşen | Durum | Not |
|---|---|---|
| SQL Server 2025 Developer (MSSQLSERVER) | **çalışıyor** | sysadmin erişimi var |
| SSMS 22 | var | ADOMD.NET istemcisi de onunla geldi |
| **Python 3.12** (`C:\Python312`) | **kuruldu** | ajan bununla koşuyor · `pythonnet`, `pyadomd`, `pyodbc` |
| **SSAS Tabular** (`localhost\TABULAR`, MSAS17) | **çalışıyor · TEK analitik kaynak** | `POC_Satis` · yıldız şema · 14 ölçü |
| **PBIRS** (`RS_PBIRS`, V15) | **çalışıyor · üç rapor yüklü** | `/SatisDashboardPBI` (.pbix) · `/SatisDashboard` (RDL) · `/CevapKarti` |
| Node.js | var ama **kullanılmıyor** | ajanın Node sürümü emekliye ayrıldı |

**Durum özeti: zincirin tamamı ayakta ve doğrulandı.**

| Doğrulama | Sonuç |
|---|---|
| Altın soru kümesi (SSAS/DAX) | 19/19 |
| Ajan cevap süresi | **~20 ms** (kalıcı SSAS bağlantısı) |
| Rapor render (CSV + PDF) | HTTP 200 · gerçek veri |
| Raporlar | ikisi de PBIRS'te, sıfır uyarıyla yüklü |
| Rapor → ajan tam döngü | çalışıyor (`?soru=2026-08 döneminde hedefi tuttuk mu?` → %80,9, hedef tutmamış) |

---

## 0.1 · Hızlı başlangıç

Her şey kurulu. Kullanmak için tek yapılacak, ajanı başlatmak:

```powershell
cd C:\work\OnpremiseYZ\poc\04-ajan-py
$env:POC_SSAS_SUNUCU = "localhost\TABULAR"
python sunucu.py
```

Sonra iki adres:

| Ne | Adres |
|---|---|
| Dashboard | `http://localhost/Reports` → **SatisDashboard** |
| Asistan | `http://localhost:8787` |
| Cevap kartı (infografik) | `http://localhost/Reports` → **CevapKarti** |

### Asıl çıktı: cevap kartı

**Soru sorulduğu anda — yazıyla ya da sesle — PBIRS infografik kartı ekranın üstünde katman olarak açılır.** Sayfanın altında değil, ayrı sekmede değil: cevabın kendisi budur.

```
 ┌─ CEVAP KARTI // #16 ────── [Ana dashboard'a git →] [PBIRS'te aç] [Yeni soru] [×] ─┐
 │  ▎ Model kapsamındaki 10 dönem içinde en yüksek net ciro 2025-12 döneminde        │
 │  ▎ gerçekleşti.                                                                   │
 │  > CEVAPLANDI                                     ||||||||||||.....               │
 │  103,7 mn TL                                      guven 73% / 2417 ms / 1 satir   │
 │  2025-12                                                                          │
 │  ─────────────────────────────────────────────────────────────────────────────────│
 │  01 // CEVAP        [ sonucun kendi grafiği — yatay bar ]                          │
 │  02 // TREND        [ aynı metrik, 10 dönem ]   03 // HEDEF [ yeşil/kırmızı ]      │
 │  Net Ciro · onaylı v3 · Semantik model · POC_Satis                                │
 └───────────────────────────────────────────────────────────────────────────────────┘
```

**Kartta soru yok.** En üstte açıklama cümlesi duruyor — cyan, yarı kalın, solunda vurgu çubuğuyla. Cümle kendi başına anlaşılır olacak şekilde kuruluyor, çünkü soru görünmüyor.

**Rakam kartta yalnızca bir kez var:** dev puntoyla, hero alanında. Bunun için ajan iki ayrı metin üretiyor:

| Alan | İçerik | Nerede kullanılır |
|---|---|---|
| `Cevap` | Rakamı içeren tam cümle | Arayüz, sesli okuma, denetim kaydı |
| `Aciklama` | **Rakamsız**, kendi başına anlaşılır cümle | Cevap kartı |

`Aciklama` içeriği duruma göre değişir:

| Soru tipi | Açıklama |
|---|---|
| Tek değer | *"2026 Mart ayı net ciro. İade ve iskontolar düşülmüş, KDV hariç satış tutarı."* |
| Uç değer | *"Model kapsamındaki 10 dönem içinde en yüksek net ciro 2025 Aralık ayında gerçekleşti."* |
| Yorumlanabilir (hedef, değişim) | *"2026 Temmuz ayı hedef gerçekleşme. Hedef tutmuş — gerçekleşme hedefin üzerinde."* |
| Kırılım | *"Tüm dönemler · Net Ciro, ürün grubu kırılımı. 3 satır; başta Beyaz Eşya."* |

### Cevap cümlesinin dili

Cevaplar teknik kod yerine düz Türkçe kurulur — *"Mart ayı net ciro şudur"* biçiminde:

```
soru   Mart ayı net ciro
cevap  2026 Mart ayı net ciro 91,9 mn TL.

soru   Temmuz ayında hedefi tuttuk mu?
cevap  2026 Temmuz ayı hedef gerçekleşme 102,9%. Hedef tutmuş — gerçekleşme hedefin üzerinde.

soru   Son 10 ayın ortalama aylık cirosu ne?
cevap  2025 Kasım – 2026 Ağustos dönemi ortalama aylık ciro 89,2 mn TL.

soru   En yüksek ciro hangi ayda oldu?
cevap  Model kapsamındaki 10 dönem içinde en yüksek net ciro 2025 Aralık ayında gerçekleşti: 103,7 mn TL.
```

Dönem kodu (`2026-03`) cümleye girmeden okunur biçime çevrilir; aralıklarda `ayı` eki düşer (*2025 Kasım – 2026 Ağustos dönemi*), yer bildiren eklerde çift ek oluşmaz (*2025 Aralık ayında*, "ayı döneminde" değil). Ölçü adının sonundaki `%` cümlede kırpılır, yoksa *"hedef gerçekleşme % 102,9%"* gibi çift işaret çıkıyordu.

Grafik 01'in veri etiketi de **yalnızca çok satırlı sonuçlarda** görünür: tek satırda rakam zaten yukarıda, tekrar etmesin; çok satırda ise değer ekseni gizli olduğu için tek sayı kaynağı odur.

**Üç grafik:**

| # | Grafik | İçerik |
|---|---|---|
| 01 | **CEVAP** | Sorunun kendi sonuç kümesi — cevabın kendisi |
| 02 | **TREND** | Aynı metriğin 10 dönem boyunca seyri. Hangi metrik sorulduysa grafik onu gösterir: metrik kodu denetim kaydındaki spesifikasyon JSON'undan `JSON_VALUE` ile okunur, birim de ona göre seçilir |
| 03 | **HEDEF GERÇEKLEŞME %** | Dönem bazında; hedefi tutan aylar yeşil, altında kalanlar kırmızı |

Kartın altında tek satır künye kaldı — metrik, kaynak, motor ve (varsa) yapılan varsayım. Metrik tanımı, cevap cümlesi ve üretilen sorgu bloğu kaldırıldı: onlar arkadaki sayfada zaten var, kartta gürültü yapıyordu.

> **Not:** "Son 3 yıl" karşılaştırması bu veriyle mümkün değil — model 10 dönem içeriyor (2025-11 … 2026-08). Trend mevcut 10 dönem üzerinden kuruldu; kaynak veri genişlerse sorgu değişmeden daha uzun seri gösterir.

Katmandaki aksiyonlar:

| Düğme | Ne yapar |
|---|---|
| **Ana dashboard'a git →** | `SatisDashboard` raporunu açar — karttan dashboard'a geçiş |
| **PBIRS'te aç** | Kartı PBIRS portalinde tam sayfa açar (yazdırma, dışa aktarma, paylaşma) |
| **Yeni soru** | Katmanı kapatır, soru kutusuna odaklanır |
| **× / Esc / dışına tık** | Kapatır |

Katman **netleştirme sorularında açılmaz** — orada kullanıcının sayfadaki seçeneklerden birini seçmesi gerekiyor. Kapsam dışı ve yetkisiz retlerde açılır: kartın kırmızı rozeti ve gerekçesi, demoda anlatılmak istenen şeyin ta kendisi.

Metin cevabı ve künyesi arkadaki sayfada durmaya devam eder; katman kapatılınca oradadır.

### Soru ekranı — sunum için sadeleştirildi

Ekran CEO'ya gösterilecek şekilde kuruldu: başlık, soru kutusu, beş örnek soru, cevap. Başka hiçbir şey görünmüyor.

Teknik kanıt **silinmedi, öne çıkmıyor**: cevabın altındaki tek satırlık *"Teknik detay"* bağlantısı açıldığında işlem zinciri, metrik tanımı ve sahibi, sonuç kümesi tablosu, üretilen DAX/SQL, sorgu spesifikasyonu JSON'u ve ses uyarısı geliyor. Demoda *"bu sayı nereden geldi"* sorusu geldiğinde tek tıkla açılır.

Cevabın altında görünen künye tek satır: metrik · dönem · güven. Varsayım yapıldıysa altına amber renkte bir satır daha eklenir — bunun görünmesi gerekiyor.

Sağlık göstergesi başlıkta küçük bir noktaya indi: yeşil ise `12 onaylı metrik · 10 dönem` yazar, kırmızı ise neyin çevrimdışı olduğunu söyler.

**Ses:** cevap otomatik okunur, 🔊 düğmesiyle açılıp kapanır. Türkçe ses varsa açıkça o seçilir — tarayıcı ses listesini gecikmeli yüklediği için liste hazır olana kadar beklenir.

**Zincir:** cevap → denetim kaydı (`KayitId`) → kart. Yanıt, kayıt yazılana kadar bekler (~200 ms). Bilinçli: ekranda gördüğünüz her kartın arkasında kalıcı bir denetim kaydı var, kart onu okuyor. Ayrı besleme yok.

Ajan çalışmıyorken rapor yine açılır, ama üstündeki "sor" bağlantıları boş sayfaya gider.

Kapatmak için `python` penceresinde <kbd>Ctrl</kbd>+<kbd>C</kbd>. SQL Server, SSAS ve SSRS Windows servisi olarak arka planda durur, ayrıca başlatmak gerekmez.

### Ajanı kalıcı hale getirme (kuruldu)

Ajan artık **oturum açıldığında kendiliğinden başlıyor** — `POC-YoneticiAsistani` adlı zamanlanmış görev olarak.

```powershell
cd C:\work\OnpremiseYZ\poc\04-ajan-py
.\gorev-kur.ps1 -Durum     # gorev + port durumu
.\gorev-kur.ps1 -Baslat    # simdi baslat
.\gorev-kur.ps1 -Durdur    # durdur
.\gorev-kur.ps1 -Kaldir    # gorevi tamamen sil
.\gorev-kur.ps1            # yeniden kur / guncelle
```

**Neden Windows servisi değil de zamanlanmış görev:** Python süreci, servis denetim mesajlarına cevap vermez; `sc create` ile doğrudan servis yapılırsa Windows *"zamanında cevap vermedi"* hatası verir. Gerçek servis için WinSW ya da NSSM gibi bir sarmalayıcı ikili indirmek gerekir. Zamanlanmış görev aynı sonucu (açılışta başla, çökerse 3 kez yeniden dene) dış bağımlılık olmadan veriyor ve projenin sıfır-bağımlılık ilkesini bozmuyor. Kaydı için yönetici hakkı da gerekmedi.

Görev, **oturum açan kullanıcının kimliğiyle** çalışır — SQL ve SSAS'a Windows kimlik doğrulamasıyla bağlandığı için bu şart. SYSTEM olarak çalıştırılsaydı makine hesabına yetki vermek gerekirdi.

Yapılandırma `ajan-baslat.cmd` içindedir (SSAS sunucusu, port, motor). Çalışma günlüğü `denetim/ajan.log`; 5 MB'ı geçince `ajan.onceki.log` olarak arşivlenir.

> Makine yeniden başlatıldığında görev **oturum açılışında** tetiklenir, açılışta değil. Kimse giriş yapmadan da ayakta olması gerekiyorsa görevi `-AtStartup` tetikleyicisine ve SYSTEM kimliğine çevirmek gerekir; o durumda `NT AUTHORITY\SYSTEM` için SQL ve SSAS'ta okuma yetkisi açılmalıdır.

---

## 1 · Akış

```
   [1] SQL Server                    [2] SSAS Tabular              [4] Ajan (Python)
   POC_SatisYZ                       POC_SatisOzet                 :8787
   ├── SatisOzet      (10 kayıt) ───► SatisOzet tablosu ─────┐      ├── anlam sözleşmesi
   ├── FactSatisDetay (600 kayıt)     14 DAX ölçüsü          │      ├── planlayıcı  (NL → spec)
   ├── Dim* (bölge/ürün/kanal/dönem)                         │      ├── derleyici   (spec → DAX | SQL)
   └── vw_SatisOzet / vw_SatisDetay                          ├─────►├── yürütücü
              │                                              │      ├── yorumlayıcı
              │                                              │      └── denetim kaydı
              ▼                                              │              ▲
   [3] Report Server                                         │              │
   SatisDashboard.rdl                                        │        [5] Tarayıcı
   ├── KPI şeridi                                            │        ├── metin girişi
   ├── aylık trend grafiği                                   │        ├── 🎤 ses (Web Speech)
   ├── bölge tablosu · ürün×kanal matrisi                    │        └── 🔊 cevabı okuma
   └── her satırda "sor →" action ───────────────────────────┘
       (?soru=... ile ajanı hazır açar)
```

Kritik tasarım kararı, spekteki ile aynı: **model SQL/DAX yazmaz, sorgu spesifikasyonu üretir.** Aynı spesifikasyon iki farklı hedefe derlenir — SSAS varsa DAX, yoksa T-SQL. Ajanın üst katmanları bunu bilmez.

---

## 1.0 · Tek analitik kaynak: SSAS

Önceden melez bir yapı vardı: ajan özet soruları SSAS'a, kırılım sorularını SQL'e gönderiyordu; dashboard ise tamamen SQL okuyordu. Aynı metrik iki ayrı yerde tanımlıydı — bir DAX ölçüsü değişse dashboard eski SQL ifadesini kullanmaya devam edecekti. Bu, spesifikasyonun uyardığı **iki doğruluk kaynağı** durumuydu.

Şimdi tek kaynak var:

```
                    ┌──────────────────────────────┐
                    │   SSAS TABULAR · POC_Satis   │   ← TEK analitik kaynak
                    │   yıldız şema · 14 ölçü      │
                    │   Satis(600) · SatisOzet(10) │
                    │   Donem · Bolge · UrunGrubu  │
                    │   · Kanal                    │
                    └───────▲──────────────▲───────┘
                       DAX  │              │  DAX (OLEDB-MD)
                    ┌───────┴──────┐  ┌────┴─────────────┐
                    │     AJAN     │  │  SatisDashboard  │
                    └───────┬──────┘  └──────────────────┘
                            │ cevap + trend + hedef serileri
                            ▼
                    ┌──────────────────────────────┐
                    │  SQL · denetim.AjanKayit     │  ← uygulamanın kendi kaydı
                    └───────────────▲──────────────┘
                                    │
                            ┌───────┴──────┐
                            │  CevapKarti  │
                            └──────────────┘
```

| Bileşen | Okuduğu yer |
|---|---|
| Ajan | **yalnızca SSAS** — SQL yedeği yok |
| SatisDashboard | **yalnızca SSAS** (OLEDB-MD sağlayıcısı, DAX sorguları) |
| CevapKarti | **yalnızca denetim kaydı** — üç grafiğin verisini ajan SSAS'tan çekip cevapla birlikte yazar |
| SQL Server | modelin besleme kaynağı + denetim kaydı deposu. Hiçbir rapor iş verisi için SQL'e gitmez |

**SSAS erişilemezse ajan SQL'e düşmez**, cevap vermeyi reddeder. Düşseydi aynı soru iki farklı ölçü tanımından cevaplanabilir, sayılar sessizce ayrışırdı — tek kaynak ilkesi bunu yasaklar.

**Cevap kartı neden denetim kaydından okuyor:** kart bir denetim artefaktıdır, cevabın verildiği *andaki* değerleri göstermelidir. Model yarın değişse bile kart geçmişi doğru anlatır. Sayılar yine SSAS'tan gelir — ajan onları cevabı üretirken çeker.

---

## 1.1 · Teknoloji yığını — hangi katmanda hangi dil

Verinin üstündeki her katmanın kendi dili var. Hangi işin nerede yapıldığını bilmek, bu mimaride "modeli değiştirince ne bozulur" sorusunun cevabıdır.

### Veri katmanı — SQL Server 2025 Developer

| Ne | Nasıl |
|---|---|
| Şema, tablolar, görünümler | **T-SQL** DDL |
| Detay dağıtımı | `CROSS JOIN` + deterministik ağırlık (rastgelelik yok, tekrarlanabilir) |
| Pencere fonksiyonları | `LAG() OVER`, `SUM() OVER (ROWS UNBOUNDED PRECEDING)` — aylık değişim ve kümülatif |
| Ajanla veri alışverişi | `FOR JSON PATH` — sonuç JSON olarak döner, sütun adı ayrıştırmaya gerek kalmaz |
| Denetim kaydı yazımı | `OPENJSON ... WITH` — ajan tek JSON gönderir, prosedür şredler. Metin birleştirme yok → enjeksiyon yüzeyi yok |
| Rapor içi metrik çözümleme | `JSON_VALUE(Spesifikasyon, '$.metrikler[0]')` — cevap kartı, sorunun metriğini böyle öğrenir |
| Bağlantı | **sqlcmd** (ODBC Driver 18), `-f 65001` UTF-8, `-u` Unicode çıktı |

### Semantik katman — SSAS Tabular (MSAS17, uyumluluk seviyesi 1600)

| Ne | Dil / teknoloji |
|---|---|
| Model tanımı ve dağıtımı | **TMSL** (Tabular Model Scripting Language) — JSON tabanlı; `createOrReplace` ve `refresh` komutları |
| Ölçüler ve hesaplanmış kolonlar | **DAX** — 14 ölçü, 2 hesaplanmış kolon |
| Sorgulama | **DAX** — `EVALUATE`, `SUMMARIZECOLUMNS`, `ROW`, `CALCULATE`, `TOPN`, `FILTER` |
| Protokol | **XMLA**, **ADOMD.NET** istemcisi üzerinden (`Microsoft.AnalysisServices.AdomdClient`) |
| Kaynak bağlantısı | **MSOLEDBSQL** provider veri kaynağı, `impersonateServiceAccount` |

Neden M (Power Query) değil: on-prem SSAS, M tabanlı yapılandırılmış veri kaynağını reddediyor (*"only supported in Power BI services"*). Klasik provider + `query` tipi bölüm kullanıldı.

Zaman zekâsı (`DATEADD` vb.) neden kullanılmadı: model 10 satırlık, bitişik olmayan aylık bir seri. Bu boyutta zaman zekâsı fonksiyonları yanlış sonuç verir; `Dönem Sıra` hesaplanmış kolonu üzerinden sıra tabanlı karşılaştırma doğru olandır.

### Ajan — Python 3.12

| Katman | Dosya | Ne yapar |
|---|---|---|
| Anlam sözleşmesi | `lib/sozlesme.py` | 12 metrik, 5 boyut, eşanlamlı sözlüğü. **Kod değil yapılandırma** — veri yönetişiminin sahipliğinde |
| Dilbilgisi | `lib/dilbilgisi.py` | Kural tabanlı Türkçe biçimbilim: ek soyma, ünsüz yumuşaması, sırasız belirteç eşleştirme, sınırlı yazım toleransı |
| Planlayıcı | `lib/planlayici.py` | Doğal dil → **sorgu spesifikasyonu**. Deterministik: desen eşleştirme + eşanlamlı sözlüğü + dilbilgisi katmanı |

> **Bu katman ne, nasıl adlandırılmalı?** *Kural tabanlı doğal dil işleme (NLP)* —
> daha dar tanımıyla **kural tabanlı NLU**: sözlük güdümlü niyet tespiti ve yuva
> doldurma yapan bir **anlamsal ayrıştırıcı** (doğal dil → sorgu spesifikasyonu →
> DAX). Ürün kategorisi olarak *veriye doğal dil arayüzü* (NLIDB). YZ
> sınıflandırmasında *sembolik / kural tabanlı sistem* tarafında durur.
>
> **Makine öğrenmesi değildir** — eğitim, veri kümesi, ağırlık yoktur; aynı soru
> her zaman aynı DAX'ı üretir. **Üretken YZ değildir** — cevap metnini model
> değil `lib/yorumlayici.py` şablonları yazar. Sunumda "AI ile yapıldı" demeyin:
> klasik tanımla yanlış olmasa da bugün "AI" LLM anlamına geliyor ve yanlış
> beklenti yaratır. Doğru cümle: *"Kapalı devre, kural tabanlı bir doğal dil
> arayüzü; onaylı semantik model üzerinde çalışır, LLM kullanmaz."*
>
> Bu bir eksiklik değil tasarım kararı: deterministik olduğu için denetlenebilir,
> tekrarlanabilir ve regresyon testi yazılabilir. LLM'in gireceği yer de belli —
> bu satırdaki dosya. Model oraya konsa bile tek çıktısı kısıtlı JSON olurdu.

### Dilbilgisi katmanı — `lib/dilbilgisi.py`

Türkçe eklemeli bir dil; "ciro" ile "cirolarımızdan" aynı kavramdır. Sözlüğe
her çekimi tek tek yazmak yerine kural tabanlı bir biçimbilim katmanı var.
Öğrenme yok: ek listesi sabit, eşik sabit, aynı girdi aynı çıktı.

| Mekanizma | Ne yapar | Örnek |
|---|---|---|
| **Ek soyma** | Aday gövdeler üretir, eşleştirme kesişime bakar | `sayımız` ∩ `sayısı` → `sayı` |
| **Ünsüz yumuşaması** | Son ses değişimini geri alır | `grubu` → `grub` → `grup` |
| **Sırasız belirteç eşleştirme** | Kalıbın kelimeleri her sırada geçebilir | `ciro bölge bazında` = `bölge bazında ciro` |
| **Yazım toleransı** | Sınırlı düzenleme mesafesi | `hedf` → `hedef` |
| **Bileşimsel kırılım** | Boyut adı × kırılım işareti çarpımı | `bölge` + `bazında` → kırılım |

Kapsamayı gevşetmenin bedeli **yanlış eşleşme**; dört kapı bunun için var:

1. Karşılaştırılabilir en kısa gövde **4 harf** — 3'te `hedef` ile `hedefe`
   değil, `hedef` ile `hediye` çakışıyor.
2. Yazım toleransı yalnız **yüzey biçimler** arasında. Türetilmiş gövdeleri de
   sokunca `tutturduğumuz` → `tuttur`, `tuttuk` ile eşleşip *"hedefi tuttuk mu"*
   sorusunu yanlış ölçüye kaydırıyordu.
3. Tolerans için **ilk harf aynı** olmalı — yoksa `yaptık` ↔ `saptık`.
4. **Sözlükte olan kelime düzeltilmez.** `sattık` sözlükte var, dolayısıyla
   `saptık`a çevrilmeye çalışılmaz.

Çıplak boyut adı hâlâ tek başına kırılım sinyali **değil** — *"Marmara
bölgesinin cirosu"* filtredir. Kırılım için ya bir işaret (`göre`, `bazında`,
`kırılım`, `hangi`…) ya çoğul ek gerekir. Bu ayrım bilinçli: yanlış kırılım,
yanlış cevaptan daha sinsidir.

**Ölçüldü.** `test/esanlam_testi.py` 56 söyleyiş içerir; 11'i reddedilmesi
gereken olumsuz örnektir.

| | Katman öncesi | Sonrası |
|---|---|---|
| Söyleyiş kapsaması | 41/56 (%73) | **56/56 (%100)** |
| Altın küme | 14/14 | 14/14 |
| Planlayıcı süresi | — | 0,73 ms/soru |

Planlayıcı maliyeti DAX gidiş-dönüşünün (~750 ms) yanında ölçülemez düzeyde.
| Derleyici · DAX | `lib/derleyici_dax.py` | spec → DAX |
| Yürütücü · DAX | `lib/calistir_dax.py` + `dax-sorgu.ps1` | `child_process` → **PowerShell 5.1** → ADOMD.NET |
| Yorumlayıcı | `lib/yorumlayici.py` | Sonuç kümesi → Türkçe cümle. Sayılar metinden değil sonuçtan basılır |
| Denetim | `lib/denetim_sql.py` | Asenkron JSON → saklı yordam |
| Sunucu | `sunucu.py` | `http.server` — çerçeve yok |

**Ara dil: sorgu spesifikasyonu.** Bu mimarinin çekirdeği. Modelin (bugün deterministik planlayıcı, yarın LLM) ürettiği **tek şey** kısıtlı bir JSON yapısıdır — serbest metin alanı yoktur, her değer sözleşmedeki izin listesinden gelir. SQL ve DAX'ı deterministik derleyiciler yazar. Bu yüzden planlayıcı LLM'e çevrildiğinde başka hiçbir dosya değişmez.

### Arayüz — vanilla web

| Ne | Teknoloji |
|---|---|
| Sayfa | HTML5, CSS custom properties (açık/koyu tema), çerçeve yok |
| Etkileşim | Vanilla JS, `fetch` |
| Konuşma tanıma | **Web Speech API** — `SpeechRecognition`, `lang=tr-TR`. **Sesi tarayıcı satıcısının bulutuna gönderir** (§8) |
| Sesli okuma | **Web Speech API** — `SpeechSynthesis`, yerel ses motoru, dışarı veri gitmez |

### Rapor katmanı — SQL Server Reporting Services 2022 (V16)

| Ne | Dil / teknoloji |
|---|---|
| Rapor sunucusu | **Power BI Report Server** (PBIRS), port 80. SSRS kaldırıldı |
| Rapor tanımı | **RDL** 2016 şeması (XML) |
| İfadeler | **VB.NET** — `Switch`, `IIf`, `StrDup`, `Format`, `UCase`, `System.Uri.EscapeDataString` |
| Veri erişimi | Gömülü veri kaynağı · sağlayıcı **`OLEDB-MD`** (Analysis Services) · **DAX** sorguları · çok değerli parametre |
| Yükleme | **SOAP** — `ReportService2010.CreateCatalogItem` |
| Render | **URL Access** — `rs:Format=PDF/CSV/IMAGE`, `rc:OutputFormat=PNG` |
| Rapordan ajana | `ActionInfo/Hyperlink` — `Uri.EscapeDataString` ile Türkçe soru URL'e kodlanıyor |

### İşletim

| Ne | Teknoloji |
|---|---|
| Dağıtım betikleri | **PowerShell 5.1** (UTF-8 **BOM'lu** kaydedilmeli — BOM'suz `.ps1` ANSI okunur ve Türkçe bozulur) |
| Ajanın kalıcılığı | **Windows Görev Zamanlayıcı** (`POC-YoneticiAsistani`), `cmd` sarmalayıcı |
| Kimlik | Windows kimlik doğrulama uçtan uca — SQL, SSAS ve SSRS |

### Bilinçli olarak kullanılmayanlar

| Yok | Neden |
|---|---|
| **LLM** | PoC'nin amacı zinciri kanıtlamak; planlayıcı deterministik. LLM tek dosyayı değiştirir (§10) |
| **Python** | Makinede kullanılabilir kurulum yok; gerekmedi |
| **üçüncü parti paket** | Kapalı ortamda paket tedariki bir tedarik zinciri kalemidir (§12.4). Az bağımlılık = sıfır tedarik riski |
| **ORM / sorgu üretici kütüphane** | Sorgu üretimi güvenlik sınırıdır; dış kütüphaneye devredilmedi |
| **Grafik kütüphanesi** | Grafikler RDL içinde; arayüzde grafik yok, kart PBIRS'ten geliyor |

---

## 2 · Dizin yapısı

```
poc/
├── 01-veri/
│   └── 01_veritabani_kurulum.sql      kaynak veritabanı + veri (ÇALIŞTIRILDI)
├── 02-tabular/
│   ├── SatisOzet.tmsl.json            semantik model tanımı (TMSL)
│   └── deploy.ps1                     XMLA ile dağıt + işle + doğrula
├── 03-rapor/
│   └── SatisDashboard.rdl             RS dashboard'u + ajan action'ları
├── 04-ajan-py/
│   ├── sunucu.py                      HTTP API + statik sunum
│   ├── lib/sozlesme.py                metrik kaydı · eşanlamlı · boyut kataloğu
│   ├── lib/dilbilgisi.py              Türkçe biçimbilim + yazım toleransı
│   ├── lib/planlayici.py              doğal dil → sorgu spesifikasyonu
│   ├── lib/derleyici_dax.py           spec → DAX
│   ├── lib/calistir_dax.py            ADOMD.NET köprüsü
│   ├── lib/yorumlayici.py             sonuç → Türkçe cevap + künye
│   ├── public/index.html              ses + metin arayüzü
│   ├── test/altin_kume.py             10+1 soruluk regresyon testi
│   └── denetim/denetim.jsonl          her soru buraya yazılır
└── README.md
```

---

## 3 · Adım 1 — Veri katmanı  ✅ yapıldı

```powershell
sqlcmd -S localhost -E -C -f 65001 -i "C:\work\OnpremiseYZ\poc\01-veri\01_veritabani_kurulum.sql"
```

`-f 65001` şart. Bu dosya BOM'suz UTF-8'dir; bayrağı verilmezse sqlcmd baytları ANSI sanar ve veritabanına `Beyaz EÅŸya` gibi bozuk değerler yazar. (Bu hatayı bir kez yapıp düzelttim — betik yeniden çalıştırılabilir.)

Doğrulama, betiğin kendi sonunda: özet 10 satır, detay 600 satır, ikisinin ciro toplamı kuruş farkıyla eşit.

| Nesne | Satır | Amaç |
|---|---|---|
| `dbo.SatisOzet` | **10** | tabular modelin kaynağı — istediğiniz "yıl-ay, max 10 kayıt" |
| `dbo.FactSatisDetay` | 600 | RS dashboard'unun kaynağı (10 dönem × 5 bölge × 4 ürün grubu × 3 kanal) |
| `dbo.vw_SatisOzet`, `dbo.vw_SatisDetay` | — | modelin ve raporun bağlandığı yüzey |

Dönemler: **2025-11 … 2026-08.** Bilinçli olarak 10 ay; bu yüzden yıldan yıla (YoY) karşılaştırma yerine aydan aya (MoM), hedef gerçekleşme ve kümülatif ölçüler kurgulandı.

---

## 4 · Adım 2 — SSAS Tabular  ✅ yapıldı

Kuruldu (`localhost\TABULAR`), model dağıtıldı, veri işlendi, doğrulandı:
`10 satır · Net Ciro 892.450.000 TL · En Yüksek Ay 2025-12` — SQL yoluyla birebir aynı.

**Dağıtım sırasında çıkan üç gerçek hata ve düzeltmeleri** (aynısını başka ortamda yaşamamak için):

| Hata | Neden | Düzeltme |
|---|---|---|
| `Power BI datasets using M based data source format are only supported in Power BI services` | TMSL'de `structured` veri kaynağı + M (Power Query) bölüm kaynağı vardı; on-prem SSAS bunu kabul etmez | Klasik `provider` veri kaynağı (MSOLEDBSQL) + `query` tipi bölüm — TMSL'de düzeltildi |
| `The column 'Yıl' has a SortByColumn property that refers to itself` | `Yıl` kolonu kendine sort-by veriyordu | `sortByColumn` kaldırıldı |
| Doğrulama DAX'ı `'En YÃ¼ksek Ay'` diye aradı | PowerShell 5.1, **BOM'suz `.ps1` dosyalarını ANSI okur**; betik içindeki Türkçe literaller bozuluyordu | `deploy.ps1` ve `dax-sorgu.ps1` UTF-8 **BOM'lu** kaydedildi |

Son iki madde bu ortamın genel tuzağı: Türkçe içeren her `.ps1` BOM'lu kaydedilmeli.

### 4.1 Kurulum (referans — yapıldı)

SQL Server setup'ını **yönetici olarak** açın ve mevcut kuruluma özellik ekleyin:

```powershell
# Setup medyasının bulunduğu yerden (ISO / indirilmiş setup):
.\setup.exe /ACTION=Install /FEATURES=AS `
            /INSTANCENAME=TABULAR /ASSERVERMODE=TABULAR `
            /ASSYSADMINACCOUNTS="LENOVO\sehers" `
            /IACCEPTSQLSERVERLICENSETERMS /Q
```

- Bu makinede yalnızca setup **bootstrap**'ı var (`C:\Program Files\Microsoft SQL Server\170\Setup Bootstrap\SQL2025`), kurulum medyası yok — indirmeniz gerekebilir.
- Özellik listesinde **Analysis Services** görünmüyorsa, o sürümün medyası AS içermiyor demektir; bu durumda SQL Server 2022 Developer medyasıyla ayrı bir `TABULAR` instance kurun. Model TMSL'i 1600 uyumluluk seviyesinde, ikisiyle de çalışır.
- `/ASSERVERMODE=TABULAR` atlanırsa Multidimensional kurulur ve TMSL çalışmaz. Bu bayrak kritiktir.

Kurulumdan sonra:

```powershell
Get-Service | Where-Object Name -like 'MSOLAP*'      # calisiyor olmali
```

### 4.2 Modeli dağıt

```powershell
cd C:\work\OnpremiseYZ\poc\02-tabular
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 -Server "localhost\TABULAR"
```

Betik sırayla: TMSL'i `createOrReplace` ile gönderir → `full refresh` ile veriyi yükler → doğrulama DAX'ı çalıştırıp satır sayısı ve `[Net Ciro]`, `[En Yüksek Ay]` değerlerini basar.

Elle yapmak isterseniz: SSMS → SSAS'a bağlan → sağ tık → **New XMLA Query** → `SatisOzet.tmsl.json` içeriğini yapıştır → çalıştır.

### 4.3 Modelde ne var

Tek tablo (`SatisOzet`, 10 satır), 2 hesaplanmış kolon, **14 ölçü**:

| Klasör | Ölçüler |
|---|---|
| 01 Temel | Net Ciro · Satış Adet · Müşteri Sayısı · Ortalama Sepet |
| 02 Hedef | Hedef · Hedef Gerçekleşme % · Hedef Sapma · Hedefi Tutan Ay Sayısı |
| 03 Karşılaştırma | Önceki Ay Ciro · Aylık Değişim % · Kümülatif Ciro |
| 04 Uç değer | En Yüksek Ay Cirosu · En Yüksek Ay · Ortalama Aylık Ciro |

`Önceki Ay Ciro`, tarih tablosu yerine `Dönem Sıra` hesaplanmış kolonuna dayanır. 10 satırlık, bitişik olmayan aylık bir modelde zaman zekâsı fonksiyonları (`DATEADD` vb.) yanlış sonuç verir; sıra tabanlı yaklaşım bu boyutta doğru olandır.

---

## 5 · Adım 3 — Report Server  ✅ yapıldı

SSRS 2022 (`RS_SSRS`, V16) kuruldu, yapılandırıldı ve rapor yüklendi:

- Web servisi: `http://localhost/ReportServer`
- Portal: `http://localhost/Reports`
- Rapor: `/SatisDashboard`

**Kurulum ile yapılandırma ayrı adımlardır** — `SQLServerReportingServices.exe` yalnızca dosyaları kurar; veritabanı ve URL rezervasyonu Configuration Manager'dan (veya `03-rapor/ssrs-url-yapilandir.ps1` ile) yapılır. Bu ayrımı kaçırmak, servis çalışıyor görünürken hiçbir uç noktanın cevap vermemesine yol açar.

Teşhis notu: SSRS portu **HTTP.SYS**'te (System, PID 4) tutulur, `ReportingServicesService` sürecinde değil. "Servis port dinlemiyor" ölçümü bu yüzden yanıltıcıdır; doğru kontrol `netsh http show urlacl` çıktısında `/ReportServer/` ve `/Reports/` rezervasyonlarını aramaktır.

### 5.0 RDL'de düzeltilen şema hataları

Rapor ilk yüklemede reddedildi. Beş ayrı 2016-şeması ihlali vardı; hepsi düzeltildi ve rapor **sıfır uyarıyla** yüklendi:

| Hata | Düzeltme |
|---|---|
| `Report` altında doğrudan `Body` | `ReportSections/ReportSection` içine alındı, `Width` eklendi |
| `Style` altında `BorderStyle`/`BorderColor`/`BorderWidth` | `Border`/`LeftBorder`/`BottomBorder` biçimine çevrildi (35 eleman) |
| `Style` alt eleman sırası | şema sırasına dizildi (63 blok) — `Style` katı `xs:sequence` |
| `ChartMember` boş | statik seriler için `Label` eklendi |
| `MajorGridLines`, `Title`, `CustomPaletteColors` | `ChartMajorGridLines`, `ChartAxisTitle`, `ChartCustomPaletteColors` |

Dönüşümü `Style` blokları için elle değil betikle yaptım; 104 blok vardı. Ders: RDL'i elle yazacaksanız Report Builder'da bir kez açıp kaydetmek bu sınıf hataların hepsini baştan eler.

### 5.0b Render sonrası düzeltilen görsel kusurlar

Şema geçerli olması raporun *doğru göründüğü* anlamına gelmiyor. PNG önizleme alınıp gözle bakıldığında dört kusur çıktı:

| Kusur | Neden | Düzeltme |
|---|---|---|
| Grafikte kolonların üstünde siyah dikey çizgiler | kategori ekseninin izgara ve tick işaretleri kapatılmamıştı | `ChartMajorGridLines` / `ChartMinorGridLines` / `ChartMajorTickMarks` / `ChartMinorTickMarks` → `Enabled=false` |
| "Kurumsal Satış" başlığı sarıp altındaki her şeyi ~0,85 inç aşağı itiyordu | matris başlık satırı 0,26 inç'e sığmıyordu | başlık satırı 0,42 inç, kolonlar daraltıldı |
| Bölge tabloları ile aylık tablo arasında 1 inç boşluk | yukarıdaki itilmenin sonucu | `tblTrend` konumu ölçülerek telafi edildi |
| Boş bir 2. sayfa (`sayfa 1/2`) | gövde artık boşluğu sayfaya taşıyordu | `<ConsumeContainerWhitespace>true</ConsumeContainerWhitespace>` → `sayfa 1/1` |

Önizleme: `03-rapor/onizleme/SatisDashboard-sayfa1.png`. Yenilemek için:

```powershell
$u='http://localhost/ReportServer?%2fSatisDashboard&rs:Command=Render&rs:Format=IMAGE&rc:OutputFormat=PNG&rc:DpiX=120&rc:DpiY=120'
$r=Invoke-WebRequest $u -UseBasicParsing -UseDefaultCredentials -TimeoutSec 300
[IO.File]::WriteAllBytes('onizleme\SatisDashboard-sayfa1.png',$r.Content)
```

SSRS'in kendi görüntü render'ı; tarayıcı ekran görüntüsü değil, raporun basılı hâlinin birebir çıktısı. Sayfa sayısını doğrulamak için PDF alıp `/Type /Page` saymak yeterli.

### 5.1 Hangisi

| | SSRS 2022 | Power BI Report Server |
|---|---|---|
| İndirme | ~120 MB | ~1 GB |
| `.rdl` (paginated) | ✔ | ✔ |
| `.pbix` barındırma | ✘ | ✔ |
| Lisans | Developer/Express ücretsiz | Power BI Premium veya SQL Server SA gerekir (Dev sürümü değerlendirme için) |

Bu PoC yalnızca `.rdl` kullanıyor. **Önerim: SSRS 2022** — hızlı, hafif, yeter. `.pbix` da barındırmak istiyorsanız PBIRS kurun; RDL dosyası ikisinde de aynı şekilde çalışır.

### 5.2 Kurulum

```powershell
# yonetici PowerShell'de
.\SQLServerReportingServices.exe /quiet /IAcceptLicenseTerms /Edition=Dev
# ardindan: Report Server Configuration Manager
#   → Database → Change Database → yeni ReportServer veritabani olustur (localhost)
#   → Web Service URL ve Web Portal URL → Apply
```

Portal genelde `http://localhost/Reports`, servis `http://localhost/ReportServer` olur.

### 5.3 Raporu yükle

Portalden: **Upload** → `03-rapor\SatisDashboard.rdl` → yükledikten sonra raporun **Manage → Data Sources** bölümünde kimlik bilgisini ayarlayın (Windows kimliği veya saklı kimlik; `POC_SatisYZ` üzerinde okuma yetkisi yeterli).

Betikle yüklemek isterseniz:

```powershell
Install-Module ReportingServicesTools -Scope CurrentUser
Write-RsCatalogItem -ReportServerUri http://localhost/ReportServer `
                    -Path "C:\work\OnpremiseYZ\poc\03-rapor\SatisDashboard.rdl" `
                    -RsFolder "/" -Overwrite
```

### 5.4 Raporda ne var

- **KPI şeridi:** Net Ciro · Hedef Gerçekleşme (hedefin altındaysa kırmızı) · Satış Adedi · Ortalama Sepet
- **Aylık trend grafiği:** net ciro kolonları + hedef çizgisi; her kolon tıklanabilir → o dönemin sorusuyla ajanı açar
- **Bölge tablosu:** ciro ve gerçekleşme, ciroya göre azalan; bölge adı tıklanınca ajana *"<Bölge> bölgesinin cirosu ne kadar?"* sorusuyla gider
- **Ürün grubu × kanal matrisi**
- **Aylık detay tablosu:** dönem · ciro · hedef · gerçekleşme · aylık değişim · **sor →**
- **Dönem parametresi** (çok seçimli, varsayılan 10 ayın tamamı)
- **`pAjanUrl` gizli parametresi:** varsayılan `http://localhost:8787`. Raporu başka makineden açacaksanız bunu ajanın makine adına çevirin, yoksa action `localhost`'a gider ve o makinede ajan yoktur.

### 5.5 Action nasıl çalışıyor

```
=Parameters!pAjanUrl.Value & "/?soru=" &
  System.Uri.EscapeDataString(Fields!DonemAd.Value & " döneminde hedefi tuttuk mu?")
```

Ajan arayüzü `?soru=` parametresini görürse soruyu kutuya yazar ve **kendiliğinden çalıştırır**. Yöneticinin rapordaki bir sayıdan asistana geçişi tek tıktır; bağlam (dönem, bölge, ürün) URL ile taşınır.

> **Doğrulanmadı:** Bu makinede rapor sunucusu olmadığı için RDL render edilerek test edilemedi. XML'i şema açısından geçerli (5 dataset, 3 tablix, 1 grafik, 5 action). Kurulumdan sonra Report Builder'da bir kez önizlemek gerekir; grafik tanımı RDL'nin en kırılgan parçasıdır.

---

## 6 · Adım 4 — Ajan  ✅ çalışıyor

```powershell
cd C:\work\OnpremiseYZ\poc\04-ajan-py
python sunucu.py
# → http://localhost:8787
```

Bağımlılıklar `requirements.txt` içinde ve azdır: SSAS'a `pyadomd` (ADOMD.NET), SQL'e `pyodbc` ile gidiyor.

### Motor seçimi

| Ortam değişkeni | Varsayılan | Anlamı |
|---|---|---|
| `POC_MOTOR` | `auto` | `auto` · `dax` · `sql` |
| `POC_SSAS_SUNUCU` | `localhost` | SSAS kurunca `localhost\TABULAR` yapın |
| `POC_SSAS_MODEL` | `POC_SatisOzet` | |
| `POC_SQL_SUNUCU` | `localhost` | |
| `POC_PORT` | `8787` | |

`auto` davranışı: soru özet veriyle cevaplanabiliyorsa ve SSAS erişilebilirse **DAX**; SSAS yoksa veya soru bölge/ürün/kanal kırılımı istiyorsa **T-SQL**. Şu anda SSAS olmadığı için her şey SQL yolundan geçiyor ve arayüzde "SSAS Tabular yok · motor: SQL yedeği" rozeti görünüyor.

SSAS kurulduktan sonra:

```powershell
$env:POC_SSAS_SUNUCU = "localhost\TABULAR"
python sunucu.py     # rozet "SSAS Tabular bağlı" olur, sorgular DAX'a döner
```

### Test

```powershell
python test\altin_kume.py
```

Son koşu: **11 / 11 geçti.** Test cevabın kendisine değil, *beklenen davranışa* bakar — reddetmesi gereken soruyu reddetmezse test kalır.

---

## 7 · Adım 5 — Demo senaryosu

10 soru + 1 bonus. Arayüzdeki numaralı çipler bunları tek tıkla çalıştırır; 🎤 ile aynısını sesle sorabilirsiniz.

| # | Soru | Gösterdiği şey | Beklenen cevap |
|---|---|---|---|
| 1 | Ağustos ayı net ciromuz ne kadar? | en yalın yol · künyeyi göster | 79,3 mn TL |
| 2 | Bu yıl toplam ciro ne oldu? | göreli dönem çözümleme; "bu yıl = 2026" varsayımı künyede yazıyor | 704,5 mn TL |
| 3 | En yüksek ciro hangi ayda oldu? | uç değer + dönem adı | 2025-12 · 103,7 mn TL |
| 4 | Temmuz ayında hedefi tuttuk mu? | evet/hayır dili, orandan üretiliyor | %102,9 · hedef tutmuş |
| 5 | Haziran cirosu önceki aya göre nasıl değişti? | karşılaştırma ölçüsü otomatik eklenir | +%7,1 |
| 6 | Son 10 ayın ortalama aylık cirosu ne? | dönem aralığı | 89,2 mn TL |
| 7 | Marmara bölgesinin cirosu ne kadar? | **özet modelde bölge yok → detay katmanına yönlendirir** ve bunu künyede söyler | 297,5 mn TL |
| 8 | En çok ciro yapan 3 ürün grubu hangileri? | top-N · detay katmanı | Beyaz Eşya 357,0 / Küçük Ev Aletleri 267,7 / Mobilya 178,5 mn TL |
| 9 | Rakiplerin pazar payı ne oldu? | **kapsam dışı ret** — tahmin üretmiyor, alternatif öneriyor | ret |
| 10 | Ahmet Yılmaz'ın maaşı ne kadar? | **yetkisiz ret** — sorgu hiç çalışmıyor, denetime yazılıyor | ret |
| + | Performans nasıl gidiyor? | **muğlak metrik** → cevap değil, iki seçenekli netleştirme sorusu | soru sorar |

Gösterirken vurgulanacak dört nokta:

1. **Her cevabın altındaki künye.** Metrik adı, onaylı sürümü, sahibi, tanımı, dönem, kaynak, motor, güven, süre. Yönetici "bu sayı nereden geldi" diye sorduğunda cevap ekranda.
2. **Üretilen sorguyu açın.** Modelin ürettiği tek şey `spesifikasyon` JSON'u; SQL/DAX'ı deterministik derleyici yazıyor. İkisi de ayrı ayrı açılabiliyor.
3. **9 ve 10.** Bu ikisi projenin asıl satış argümanı: sistem bilmediğini bilmiyor gibi davranmıyor. Yanlış cevap, cevapsızlıktan pahalıdır.
4. **7.** Aynı soru zincirinin doğru veri katmanını kendisi seçmesi — spekteki katmanlı mimarinin çalıştığının kanıtı.

Rapor→ajan akışını göstermek için: dashboard'da bir bölge adına veya bir ayın **sor →** bağlantısına tıklayın; ajan yeni sekmede açılıp soruyu kendiliğinden koşar.

**Bölge tablosunda gerçekleşme oranları bilinçli olarak farklıdır** — Marmara %113, Karadeniz %108, Ege %103, İç Anadolu %94, Akdeniz %84. İlk kurulumda ciro ve hedefi detaya aynı ağırlıkla dağıtmıştım; bu, oranı her bölgede matematiksel olarak eşitliyor ve kolonu anlamsız kılıyordu. Artık hedef ayrı bir bölge performans profiliyle dağıtılıyor, iki dağıtımın toplamı yine özet tabloyla birebir tutuyor.

**Rapordan gelen dönem biçimi:** Action `2026-08` gibi bir dize üretir. Ajanın ilk hâli bunu tanımıyor, sadece `2026` yılını yakalayıp soruyu sessizce tüm yıla genişletiyordu — yanlış cevap değil ama *yanlış soruya* doğru cevap. `YYYY-MM` deseni artık ay adı aramasından önce çözümleniyor; kapsam dışı bir dönem (`2026-10`) verilirse gerekçeli reddediliyor.

---

## 7.1 · Ajanın sınırları — ölçülmüş

Sabit bir soru listesine bağlı **değil**, ama semantik modelin her şeyini de soramazsınız. Sınır, **anlam sözleşmesidir** (`lib/sozlesme.py`): 12 onaylı metrik, 5 boyut, 10 dönem. Kayıtta olmayan hiçbir şey sorgulanamaz.

Ölçmek için: `python test\sinir_testi.py` (26 soruluk sınır kümesi). Son koşunun özeti:

| Soru tipi | Davranış | Örnek |
|---|---|---|
| Altın kümedeki ifadeler | Cevaplar | *"Ağustos ayı net ciromuz ne kadar?"* → 79,3 mn TL |
| **Farklı söyleniş** | Eşanlamlı sözlüğü tutuyorsa cevaplar | *"temmuz hasılatı neydi"*, *"mayıs ayındaki gelirimiz"*, *"nisan ayı müşteri sayımız kaç"* → hepsi doğru |
| **Belirsiz ifade** | Cevap **vermez**, seçenek sunar | *"ağustosta ne kadar sattık"* → tutar mı adet mi? · *"son 3 ayın ortalaması ne"* → sepet mi aylık ciro mu? |
| **"Neden" sorusu** | Nedensellik **kurmaz**, kırılım önerir | *"ciro neden düştü"* → "Nedensellik kuramam… hangi kırılım?" + bölge/ürün/kanal seçenekleri |
| Kapsam dışı | Gerekçeli ret, tahmin yok | *"rakiplerin pazar payı"*, *"gelecek ay ciro ne olur"*, *"stok durumu"* |
| Yetkisiz | Ret, sorgu hiç çalışmaz | *"Ahmet Yılmaz'ın maaşı"* |
| **Tamamen anlamsız** | Uydurmaz, reddeder | *"asdfgh qwerty"*, *"hava bugün nasıl"*, *"sen kimsin"*, *"bana bir şiir yaz"* → hepsi ret |

### Bu testin yakaladığı ciddi hata

İlk koşuda **modelde ölçü olarak var ama sözleşmede olmayan** dört ölçü (Kümülatif Ciro, Hedef Sapma, Hedefi Tutan Ay Sayısı, Önceki Ay Ciro) reddedilmiyor, **yanlış metrikle cevaplanıyordu**:

```
"kaç ay hedefi tutturduk"  →  Hedef: 887,0 mn TL     (%76 güven)   ✗ tamamen alakasız
"hedef sapması ne kadar"   →  Hedef: 887,0 mn TL     (%76 güven)   ✗
"kümülatif ciro ne kadar"  →  Net Ciro: 892,5 mn TL  (%73 güven)   ✗
```

Eşleştirici, tam karşılığı bulamayınca en yakın gördüğü metriğe kayıyordu — spesifikasyondaki **T-08 riskinin** (ikna edici biçimde yanlış cevap) canlı örneği. Reddetmekten kötü, çünkü kullanıcı yanlış olduğunu anlamıyor.

Düzeltme: dört ölçü de sözleşmeye eklendi (8 → 12 metrik). Artık doğru cevaplıyor:

```
"kaç ay hedefi tutturduk"  →  Hedefi Tutan Ay Sayısı: 7 adet   ✓
"hedef sapması ne kadar"   →  Hedef Sapma: 5,5 mn TL           ✓
"kümülatif ciro ne kadar"  →  Kümülatif Ciro: 892,5 mn TL      ✓
```

**Kural:** semantik modelde bir ölçü varsa, sözleşmede de karşılığı olmalı. Modele ölçü eklerken `lib/sozlesme.py` güncellenmezse ajan sessizce yanlış cevaplamaya başlar. Sınır testi bunun bekçisidir.

### Hâlâ yapamadıkları

- **Çoklu metrik:** *"ciro ve hedef gerçekleşmesini birlikte göster"* → yalnızca birini alır.
- **Karşılaştırmalı ifade:** *"Marmara ve Ege'yi karşılaştır"* → metrik adı geçmediği için reddeder.
- **Serbest ifade:** Sözlükte karşılığı olmayan bir kelime kullanılırsa reddeder. Kapsamı genişletmenin yolu model büyütmek değil, **eşanlamlı sözlüğünü büyütmektir** — gerçek kullanımdaki reddedilen sorular buranın girdisidir.

Bir LLM devreye alınırsa bu üç sınır kalkar; `lib/planlayici.py` dışında hiçbir dosya değişmez.

---

## 8 · Ses hakkında — dürüst uyarı

Arayüzdeki mikrofon **tarayıcının Web Speech API'sini** kullanıyor. Chrome ve Edge bu API'de sesi **satıcının bulut servisine gönderir.** Yani:

- PoC/demo için sorun değil, akışı gösterir.
- **Gerçek kapalı devre kurulumda kullanılamaz** — spesifikasyonun K-01 kısıtını (hiçbir veri dışarı çıkmaz) doğrudan ihlal eder.
- Arayüzde bu uyarı görünür durumda; demoda üstünü örtmeyin, tersine bunu konuşmak güven kazandırır.

Şirket içi karşılığı: yerel bir konuşma tanıma servisi (örn. Whisper sınıfı bir model veya Vosk) `POST /api/ses` uç noktası arkasına konur; arayüzdeki `SpeechRecognition` bloğu bu uca ses gönderip metin alacak şekilde değiştirilir. Değişmesi gereken tek yer o blok — zincirin geri kalanı metinle çalışıyor.

Cevabın sesli okunması (`speechSynthesis`) yerel ses motorunu kullanır, dışarı veri gitmez.

---

## 9 · Denetim kaydı

Her soru — reddedilenler dahil — `04-ajan-py/denetim/denetim.jsonl` dosyasına bir satır olarak yazılır: zaman, kullanıcı, soru metni, çözümlenen spesifikasyon, üretilen sorgu, dönen satır sayısı, güven, süre, sonuç durumu.

```powershell
# -Encoding UTF8 sart: Windows PowerShell 5.1 varsayilan olarak ANSI okur
# ve Turkce karakterler "Ahmet YÄ±lmaz" gibi gorunur.
Get-Content .\denetim\denetim.jsonl -Encoding UTF8 -Tail 3 |
    ForEach-Object { $_ | ConvertFrom-Json } | Format-List
```

Spekteki §9.4'ün karşılığı. Yetkisiz sorularda sorgu hiç çalışmadığı için `sorgu: null` olur ama kayıt yine düşer — denetimin görmesi gereken şey tam olarak budur.

---

## 10 · Bu PoC'nin sınırları

Demoda kimse sormadan siz söyleyin; sorulduğunda söylemek zayıf düşürür.

| Sınır | Ayrıntı |
|---|---|
| **LLM yok** | Niyet çözümlemesi deterministik: eşanlamlı sözlüğü + desen eşleştirme. Sabit soru listesi **değil** — metrik × boyut × filtre × dönem × niyet çarpımı serbest; ölçüldü: 18 doğaçlama soruda 13 cevap, 5 gerekçeli ret. Kırıldığı yer sözlükte olmayan ifade. Gerçek sistemde `lib/planlayici.py` bir LLM çağrısıyla değişir — **çıktı sözleşmesi (spesifikasyon JSON'u) aynı kaldığı için başka hiçbir dosya değişmez.** Zincirin bu şekilde kurulmuş olması PoC'nin asıl gösterdiği şey. |
| **Yetki gerçek değil** | Yetkisiz reddi desen tabanlı. Gerçek kurulumda satır düzeyi güvenlik veri katmanında, SSAS rolleriyle uygulanır (TMSL'de `Yonetici_Okuma` rolü iskelet olarak var, üyesi yok). |
| **Ses bulut kullanıyor** | Bkz. §8. |
| **10 dönem** | YoY karşılaştırma yok; ölçüler MoM ve kümülatif üzerine kurulu. |
| **Kuruş farkı** | Detay, özetten deterministik ağırlıklarla dağıtıldığı için yuvarlamadan dönem başına ±0,04 TL fark var. Doğrulama sorgusu bunu görünür kılıyor; gizlenmedi. |
| **Tek kullanıcı** | Eşzamanlılık, kuyruk, önbellek yok — spekte var, PoC'de yok. |

---

## 11 · Sıradaki adımlar

1. SSAS Tabular kur (§4.1) → `deploy.ps1` çalıştır → ajanı `POC_SSAS_SUNUCU` ile başlat. Aynı 11 soru bu kez DAX üzerinden koşar; arayüzdeki "motor" satırında görürsünüz.
2. SSRS kur (§5.2) → RDL'i yükle → veri kaynağı kimliğini ayarla → action'ları test et.
3. Demoyu §7'deki sırayla bir kez baştan sona prova edin; 9 ve 10 mutlaka gösterilsin.
4. İsteğe bağlı: `lib/planlayici.py` yerine yerel bir LLM koyup aynı testi tekrar koşun — 14/14 korunuyorsa mimari doğrulanmış olur.
