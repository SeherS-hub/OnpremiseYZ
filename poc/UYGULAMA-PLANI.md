# Uygulama Planı ve Test Planı

Bu doküman iki soruyu cevaplar: **ne sırayla kurulur** ve **her adımda neyi test ederek devam edilir.** Üçüncü bölüm, PoC'yi gerçek bir kurumsal ortama taşımanın koşullarını sayar.

Spesifikasyonun kendisi ayrı dosyadadır: [`../docs/kapali-devre-yonetici-asistani.md`](../docs/kapali-devre-yonetici-asistani.md) — 21 bölüm, mimari kararlar, risk kaydı, uçtan uca değerlendirme.

---

## 1 · Bileşen envanteri

| # | Bileşen | Dosya | Durum |
|---|---|---|---|
| 1 | Kaynak veri | `01-veri/01_veritabani_kurulum.sql` | kuruldu |
| 2 | SSAS servis yetkisi | `01-veri/02_ssas_servis_yetkisi.sql` | kuruldu |
| 3 | Denetim şeması | `01-veri/03_denetim_kaydi.sql` | kuruldu |
| 4 | Semantik model | `02-tabular/SatisOzet.tmsl.json` + `deploy.ps1` | dağıtıldı |
| 5 | Dashboard | `03-rapor/SatisDashboard.rdl` | yüklendi |
| 6 | Cevap kartı (infografik) | `03-rapor/CevapKarti.rdl` | yüklendi |
| 7 | Ajan | `04-ajan-py/` | çalışıyor · zamanlanmış görev |
| 8 | Testler | `04-ajan-py/test/` | 2 paket, aşağıda |

---

## 2 · Uygulama adımları — her adımın kendi testi var

Kural: **bir adımın testi geçmeden sonrakine geçilmez.** Bu PoC'de her adımın testi bir kez kırıldı ve gerçek hata yakaladı; sıralamayı bu yüzden ciddiye alın.

### Adım 1 — Kaynak veri

```powershell
sqlcmd -S localhost -E -C -f 65001 -i 01-veri\01_veritabani_kurulum.sql
```

| Test | Nasıl | Geçme ölçütü |
|---|---|---|
| T1.1 Satır sayısı | Betiğin sonundaki doğrulama | Özet 10, detay 600 |
| T1.2 Özet–detay tutarlılığı | Aynı doğrulama bloğu | Dönem başına fark ≤ 0,05 TL |
| T1.3 **Türkçe kodlama** | `SELECT UrunGrubuAd FROM dbo.DimUrunGrubu` | `Beyaz Eşya` — `Beyaz EÅŸya` değil |

> T1.3 gerçek bir hata yakaladı: `-f 65001` verilmeden çalıştırılınca veritabanına bozuk metin yazıldı. Kodlama testi olmasa demoya kadar fark edilmezdi.

### Adım 2 — Semantik model

```powershell
sqlcmd -S localhost -E -C -f 65001 -i 01-veri\02_ssas_servis_yetkisi.sql
powershell -File 02-tabular\deploy.ps1 -Server "localhost\TABULAR"
```

| Test | Nasıl | Geçme ölçütü |
|---|---|---|
| T2.1 Dağıtım | `deploy.ps1` çıktısı | `TAMAM: model olusturuldu` |
| T2.2 İşleme | Aynı çıktı | `TAMAM: veri islendi` |
| T2.3 Ölçü doğrulaması | Betiğin doğrulama DAX'ı | `Satir=10`, `NetCiro=892450000`, `EnYuksekAy=2025-12` |
| T2.4 **Tek kaynak doğrulaması** | `python test\altin_kume.py` (SSAS kapalıyken cevap YOK) | DAX ve SQL sonuçları birebir aynı |

> T2.4 bu mimarinin asıl testidir: aynı sorgu spesifikasyonu iki farklı motora derleniyor. Sayılar ayrışıyorsa ya derleyicilerden biri ya ölçü tanımı hatalıdır.

### Adım 3 — Ajan

```powershell
cd 04-ajan
python sunucu.py
```

| Test | Nasıl | Geçme ölçütü |
|---|---|---|
| T3.1 Altın küme | `python test\altin_kume.py` | 19/19 |
| T3.2 Eşanlam kapsaması | `python test\esanlam_testi.py` | 56/56 |
| T3.2 Sınır davranışı | `python test\sinir_testi.py` | Anlamsız sorularda uydurma yok |
| T3.3 Sağlık | `GET /api/saglik` | `sql.erisim=true`, `ssas.erisim=true` |
| T3.4 Denetim kaydı | `SELECT TOP 5 * FROM denetim.AjanKayit` | Her soru bir satır, cevap metni dolu |
| T3.5 Yetkisiz soru | Altın küme #10 | `Durum=yetkisiz` **ve** `Sorgu IS NULL` |

> T3.5'te iki koşul birden aranır: reddetmek yetmez, **sorgunun hiç çalışmamış olması** gerekir. Reddedip yine de sorguyu çalıştıran bir sistem yetki ihlali yapmıştır.

### Adım 4 — Raporlar

```powershell
powershell -File 03-rapor\ssrs-url-yapilandir.ps1   # yonetici olarak, bir kez
```

| Test | Nasıl | Geçme ölçütü |
|---|---|---|
| T4.1 Şema geçerliliği | Yükleme sırasında | `uyari: 0` |
| T4.2 Render | `rs:Format=PDF` | HTTP 200, gerçek veri |
| T4.3 Sayfa sayısı | PDF içinde `/Type /Page` say | 1 (hayalet sayfa yok) |
| T4.4 Görsel denetim | `rs:Format=IMAGE&rc:OutputFormat=PNG` → **göze bak** | Grafikte artefakt yok, boşluk yok, taşma yok |
| T4.5 Action bağlantıları | HTML render içinde `8787` ara | ≥ 1 bağlantı, Türkçe doğru kodlanmış |

> T4.4 otomatikleştirilemez ve atlanamaz. Rapor **şema açısından geçerliyken görsel olarak bozuk** olabilir: bu PoC'de grafikte siyah dikey çizgiler, 1 inçlik boşluk ve boş bir ikinci sayfa vardı — hepsi `uyari: 0` ile yüklenmiş bir rapordaydı.

### Adım 5 — Uçtan uca

| Test | Nasıl | Geçme ölçütü |
|---|---|---|
| T5.1 Rapor → ajan | Dashboard'da bir "sor →" tıkla | Ajan açılır, soruyu kendiliğinden koşar |
| T5.2 Dönem biçimi | `?soru=2026-08 döneminde…` | Dönem `2026-08` çözümlenir, tüm yıla genişlemez |
| T5.3 Ajan → cevap kartı | `CevapKarti` raporunu aç | Son soru infografik olarak görünür |
| T5.4 Kapsam dışı dönem | `?soru=2026-10 döneminde ciro` | Gerekçeli ret |

> T5.2 de gerçek bir hata yakaladı: rapordan gelen `2026-08` biçimi tanınmıyor, ajan sadece `2026`yı görüp soruyu sessizce tüm yıla genişletiyordu. Yanlış cevap değil — **yanlış soruya doğru cevap**, ki tespiti daha zordur.

---

## 3 · Test paketleri

### 3.1 Altın soru kümesi — `python test\altin_kume.py`

11 soru. Cevabın kendisine değil **beklenen davranışa** bakar: reddetmesi gereken soruyu reddetmezse test kalır.

| Sınıf | Adet | Örnek |
|---|---|---|
| Tek metrik / dönem | 3 | *"Ağustos ayı net ciromuz ne kadar?"* |
| Hesaplanmış ölçü | 2 | *"Temmuz ayında hedefi tuttuk mu?"* |
| Kaynak yönlendirme | 2 | *"Marmara bölgesinin cirosu"* → detay katmanı |
| Ret | 2 | kapsam dışı · yetkisiz |
| Netleştirme | 1 | muğlak metrik |
| Uç değer | 1 | *"En yüksek ciro hangi ayda?"* |

Tek analitik kaynak SSAS Tabular; SQL yedeği yok. **14/14 geçmeli ve dashboard ile aynı sayıları üretmeli.**

### 3.2 Eşanlam / söyleyiş testi — `python test\esanlam_testi.py`

Kapsama testi: aynı şeyin farklı söylenişlerini ajan hâlâ anlıyor mu?
56 söyleyiş, 11'i reddedilmesi gereken olumsuz örnek. **56/56 beklenir.**

Olumsuz blok en az diğerleri kadar önemli — eşleştiriciyi gevşetmenin bedeli
oradan görülür. Yeni eşanlamlı eklendiğinde önce bu koşulmalı.

### 3.3 Sınır testi — `python test\sinir_testi.py`

26 soru, 6 sınıf: altın küme ifadeleri · yeniden söyleyiş · sözleşmede olmayan ölçüler · karmaşık sözdizimi · kapsam/yetki dışı · tamamen anlamsız.

Bu test **ciddi bir hata yakaladı:** semantik modelde ölçü olarak var ama sözleşmede olmayan dört ölçü (Kümülatif Ciro, Hedef Sapma, Hedefi Tutan Ay Sayısı, Önceki Ay Ciro) reddedilmiyor, yanlış metrikle %76 güvenle cevaplanıyordu. Spesifikasyondaki **T-08 riskinin** canlı örneği.

**Kalıcı kural:** semantik modele ölçü eklenirse `lib/sozlesme.py` de güncellenmeli. Sınır testi bunun bekçisidir ve her model değişikliğinden sonra koşturulmalıdır.

### 3.4 Neyin testi yok — açıkça

| Boşluk | Neden | Ne zaman gerekir |
|---|---|---|
| Yük / eşzamanlılık | Tek kullanıcılı PoC | Pilot öncesi |
| Yetki matrisi | RLS kurulmadı, ret desen tabanlı | RLS devreye girince — **ilk yazılacak test** |
| Rapor görsel regresyonu | PNG karşılaştırması kurulmadı | Rapor sayısı 3'ü geçince |
| Ses tanıma doğruluğu | Tarayıcı API'si, ölçülmedi | Yerel STT'ye geçince |
| Sızıntı testi | Ağ akış denetimi elle | Üretim öncesi, zorunlu |

---

## 4 · Gerçek ortamda kullanım

PoC'yi kurumsal ortama taşımak beş şeyi değiştirmeyi gerektirir. Sırası önemli.

### 4.1 Anlam sözleşmesi — önce bu

PoC'de 12 metrik elle yazıldı. Gerçek ortamda:

- Metrik kaydı **veri yönetişiminin sahipliğinde**, sürüm kontrollü bir depoda durur; `lib/sozlesme.py` onu okur, kaynağı olmaz.
- Her metrik için sahibi, onay tarihi ve `karistirilmamali` alanı zorunludur.
- Eşanlamlı sözlüğü **reddedilen sorulardan** beslenir: `SELECT Soru FROM denetim.AjanKayit WHERE Durum='kapsam_disi'` haftalık gözden geçirilir. Kapsamı büyüten şey budur, daha büyük model değil.

Bu adım atlanırsa gerisi anlamsız. Spesifikasyon §6.4 bunun sürekli bir iş olduğunu söylüyor: metrik başına yılda 1–2 saat bakım.

### 4.2 Yetkilendirme — PoC'de yok

Şu an yetkisiz reddi **desen tabanlı**; gerçek yetki kontrolü değil. Üretimde:

- Satır düzeyi güvenlik SSAS rollerinde tanımlanır (`Yonetici_Okuma` rolü TMSL'de iskelet olarak duruyor, üyesi yok).
- Ajan kullanıcının kimliğini taşır — kendi hizmet hesabıyla sorgulamaz. ADOMD bağlantısında `EffectiveUserName` veya kimlik devri kullanılır.
- Önbellek anahtarı yetki bağlamını **içermek zorundadır**; yoksa önbellek doğrudan bir yetki aşımı açığına dönüşür.
- Metadata da yetkilidir: kullanıcı, görmeye yetkili olmadığı metriğin adını bile öğrenmemeli.

### 4.3 Niyet çözümleme — LLM'e geçiş

`lib/planlayici.py` deterministik. Değiştirilecek **tek dosya** budur; çıktı sözleşmesi (spesifikasyon JSON'u) sabit kaldığı sürece derleyici, yürütücü, yorumlayıcı ve arayüz hiç değişmez.

Geçiş adımları:

1. Yeni planlayıcıyı yaz, aynı JSON şemasını üret.
2. `python test\altin_kume.py` → 19/19 korunuyor mu?
3. `python test\sinir_testi.py` → anlamsız sorularda hâlâ uydurmuyor mu?
4. Gölge çalıştırma: bir hafta iki planlayıcıyı paralel koştur, yalnızca eskisinin cevabını göster, farkları incele.
5. Kademeli geçiş: %10 → %50 → %100.

LLM devreye girince kalkan sınırlar: çoklu metrik, karşılaştırmalı ifadeler, sözlükte olmayan kelimeler.

### 4.3b Giriş noktası — dashboard mı, asistan mı

PoC'de iki ayrı adres var: dashboard (`/Reports`) ve asistan (`:8787`). Demoda sorun değil, gerçek kullanımda sorun. Yönetici dashboard'da yaşar; soru oradaki bir sayıdan doğar. Asistan **ayrı bir yer** olursa her soru bir bağlam kaybıdır: dashboard kapanır, filtreler gider, geri dönmek ayrı bir tıktır.

**Kural: tek kapı olmalı.** Hangisi kapı olacak sorusunun cevabı teknik olarak zaten belli:

| Aday kabuk | Neden olmaz / olur |
|---|---|
| Dashboard (RDL) kabuk olsun | **Olmaz.** RDL serbest metin girişi barındıramaz, katman (overlay) açamaz, canlı cevap gösteremez. Rapor parametresi bir metin kutusudur ama "View Report" tıkı gerektirir ve sayfayı yeniler |
| Asistan (HTML) kabuk olsun, dashboard içeride | **Olur.** Soru çubuğu üstte sabit, dashboard gövdede, cevap kartı katman olarak üstte. Bağlam hiç kaybolmaz |

**Ölçülmüş engel:** Rapor sunucusu `X-Frame-Options: SAMEORIGIN` gönderiyor. Asistan `:8787`'de, rapor `:80`'de olduğu sürece farklı köken sayılır ve tarayıcı çerçevelemeyi **engeller**. Yani gömme, ancak ikisi aynı köken altına alınırsa çalışır.

**Hedef mimari:**

```
http://raporlar/                    ← tek kapı, tek kimlik doğrulama
├── /              →  asistan kabuğu (Python, ters vekil arkasında)
│   ├── üst çubuk  →  soru + mikrofon
│   ├── gövde      →  <iframe src="/ReportServer?...SatisDashboard">
│   └── katman     →  cevap kartı
└── /ReportServer  →  SSRS (mevcut)
```

Gereken tek altyapı işi: **IIS ters vekil** (ARR + URL Rewrite) ile `http://raporlar/asistan` → `localhost:8787`. Bu üç şeyi birden çözer — aynı köken (çerçeveleme serbest), tek kimlik doğrulama turu, tek adres.

**Akış:**

1. Yönetici `http://raporlar/` açar → dashboard görür, üstte soru çubuğu durur
2. Bir sayıya takılır → çubuğa yazar ya da rapordaki **sor →** bağlantısına tıklar (çubuğu doldurur, sayfa değişmez)
3. Cevap kartı katman olarak açılır
4. Kapatır → dashboard aynı yerde, aynı filtrelerle duruyor

Adım 4 farkı yaratan yer: bugünkü kurulumda oraya "geri dönmek" gerekiyor, hedefte hiç ayrılınmıyor.

**Ara çözüm (ters vekil yokken):** Asistan sayfası dashboard'u çerçeveleyemediği için gövdeye raporun **PNG render'ını** koyabilir (`rs:Format=IMAGE`) ve üstüne "interaktif aç" bağlantısı verir. Görsel bütünlük korunur, etkileşim kaybolur. Kalıcı çözüm değil, köprü.

### 4.4 İşletim

| Konu | PoC | Üretim |
|---|---|---|
| Ajan | Zamanlanmış görev, tek örnek | En az 2 örnek, yük dengeleyici arkasında |
| Kimlik | Oturum açan kullanıcı | Yönetilen hizmet hesabı + kimlik devri |
| Denetim | `POC_SatisYZ.denetim` şeması | **Ayrı veritabanı**, yalnızca-ekleme yetkisi, 24 ay saklama |
| Önbellek | Yok | Yetki duyarlı sonuç önbelleği (§7.4) |
| Eşzamanlılık | Sınırsız | Kuyruk + düğüm başına yuva sınırı |
| İzleme | `denetim/ajan.log` | Merkezi log + doğruluk panosu (§12.3) |
| Ses | Tarayıcı API'si — **buluta gider** | Şirket içi STT; aksi hâlde K-01 ihlali |

### 4.5 Güvenlik kapısı — üretim öncesi zorunlu

- Çıkış trafiği varsayılan-ret; ağ akış kaydıyla 7 gün gözlem, sıfır dış bağlantı.
- Model ağırlıkları ve paketler iç kayıt defterinden, imza doğrulamalı.
- İstemler ve metrik kaydı sürüm kontrolünde, gözden geçirmeden geçerek üretime çıkar.
- CISO ve uyum birimi spesifikasyon §9'u tasarım onayı olarak imzalar.

### 4.6 Hangi sırayla

```
1. Metrik kaydını gerçek yönetişim deposuna taşı        ← her şeyin ön koşulu
2. RLS'i SSAS rollerinde kur + yetki testi kümesi yaz
3. Denetim kaydını ayrı veritabanına al
4. Ajanı iki örnek + kimlik devri ile dağıt
5. Ses katmanını şirket içi STT ile değiştir
6. Planlayıcıyı LLM'e çevir (gölge çalıştırma ile)
7. Güvenlik kapısı ve uyum onayı
```

1–3 arası yapılmadan kullanıcıya açmayın. 6 en sona kalmalı: model değiştirmek en görünür ama en az kritik adımdır.

---

## 5 · Bakım rutini

| Sıklık | İş |
|---|---|
| Her model değişikliğinde | `altin_kume.py` + `sinir_testi.py` |
| Haftalık | Reddedilen soruları incele, eşanlamlı sözlüğünü büyüt |
| Haftalık | Ağ akış denetimi: sıfır dış bağlantı |
| Aylık | Altın kümeye gerçek kullanımdan yeni soru ekle |
| Aylık | Denetim kaydından doğruluk örneklemesi (%2 manuel puanlama) |
| Çeyreklik | Metrik tanımlarını sahipleriyle gözden geçir |
