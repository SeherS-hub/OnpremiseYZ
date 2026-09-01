# Gerçek ortama geçiş

PoC'den kurumsal kuruluma. Plan dört karara göre yazıldı:

| Karar | Seçim | Sonucu |
|---|---|---|
| Semantik model | Onaylı ölçüler modelde tanımlı | Sözleşme iskeleti otomatik üretilir |
| Kimlik | Kullanıcının kendi kimliği, RLS geçerli | Kimliğe bürünme + önde kimlik doğrulayan katman |
| Kapsam | Tek model, bir konu alanı | Yönlendirme katmanı gerekmez |
| Ses | Yerel konuşma tanıma | Web Speech API çıkar, on-prem STT girer |

Sıra önemli: 1 ve 2 bitmeden 3'e geçmeyin. Ajanı yanlış cevap verirken
yayına almak, hiç almamaktan kötüdür.

---

## Faz 1 · Sözleşme — işin ağırlığı burada

Ajanın kalitesi bu dosyanın kalitesidir. Model bağlanır bağlanmaz cevap
vermeye başlamaz; **hangi sorunun hangi ölçüye karşılık geldiğini** bilmesi
gerekir ve bunu kimse modelden okuyamaz.

### 1.1 · İskeleti üretin

```powershell
cd <ajan>\04-ajan-py
python araclar\sozlesme_iskelet.py --sunucu "SUNUCU\ORNEK" --model "ModelAdi" `
                                 --cikti lib\sozlesme_yeni.py
```

Araç modele bağlanır ve makineden çıkarılabilecek her şeyi doldurur:

| Otomatik | Kaynak |
|---|---|
| Ölçü adları ve DAX karşılıkları | `$SYSTEM.TMSCHEMA_MEASURES` |
| Birimler (TRY / oran / adet) | Biçim dizesi |
| Tanımlar | Ölçü açıklaması — varsa |
| Boyutlar ve DAX sütunları | `TMSCHEMA_COLUMNS`, gizli olanlar elenir |
| Boyut değerleri | Kardinalite ≤ 50 olanlar için `DISTINCT` |
| **Ölçü-boyut geçerliliği** | İlişki grafiği, **süzme yönü izlenerek** |

Son satır en değerlisi. PoC'de `Müşteri Sayısı` ölçüsü ilişkisiz bir tablodan
geliyordu; kanal filtresi sessizce yok sayılıyor, her satırda aynı sayı
dönüyordu. Araç bunu ilişki grafiğinden kendisi buluyor ve `gecerliBoyutlar`
alanını yazıyor — o boyutlarla sorulduğunda ajan gerekçeli ret verir.

> Yön hesabı önemli: süzme boyuttan olguya akar. Yönsüz bakıldığında Bölge,
> Satış üzerinden Dönem'e "ulaşıyor" görünür ve kısıt kaçar.

Araç modelde **yönetici yetkisi** ister (`TMSCHEMA_*` görünümleri için).

### 1.2 · Elle tamamlayın

İskeletteki `TODO`'lar. Sırayla en çok kazandıranlar:

**Eşanlamlılar.** Ölçü adının kendisi nadiren yeter. Kullanıcı *"ciro"* der,
model *"Net Satış Tutarı"* yazar. Kaynak: mevcut raporlarınızın başlıkları,
e-postalardaki ifadeler, ekiplerin jargonu. Türkçe çekim eklerini
yazmayın — dilbilgisi katmanı zaten `ciro` ↔ `cirosu` ↔ `ciromuz` bağını
kuruyor. Yazılması gereken *farklı kelimeler*.

**Tanımlar.** "Bu ölçü neyi ölçer, neyi ölçmez." `karistirilmamali` alanı
özellikle değerli: *"brüt ciro ile karıştırılmamalı"* gibi.

**Sahiplik ve onay.** Cevap künyesinde görünür; sayının arkasında kim var.

**Dönem sözlüğü.** Takvim boyutunuza bağlanır: ay adları, kapsanan dönemler,
"bu ay"ın karşılığı. Ajanın *"mart"*, *"geçen ay"*, *"son 3 ay"* ifadelerini
çözmesi buna bağlı.

**Kapsam dışı / yetkisiz desenleri.** PoC'deki listeyi kurumunuza uyarlayın.

### 1.3 · Ölçün

Sözleşme "bitti" demenin tek nesnel yolu bu:

```powershell
python test\esanlam_testi.py
```

Dosyayı **kendi sorularınızla** doldurun. Yöneticilerden gerçek soru toplayın,
her birinin hangi ölçüye çözülmesi gerektiğini yazın. Olumsuz blok da şart —
reddedilmesi gereken sorular. Kapsama oranı sözleşmenin olgunluk ölçüsüdür;
PoC modelinde 56/56.

---

## Faz 2 · Kimlik ve satır düzeyi güvenlik

PoC her sorguyu tek hesapla koşuyor. RLS istendiğine göre üç parça gerekiyor.

### 2.1 · Kullanıcıyı tanıyan bir ön katman

Python'un standart HTTP sunucusu Kerberos/NTLM konuşmaz ve bunun için
bağımlılık eklemek istemiyoruz. Standart on-prem çözüm: **IIS'i öne koyup
ajanı arkada tutmak.**

```
Kullanıcı ──Kerberos──▶ IIS (Windows Authentication)
                          │  ARR ters vekil, X-Kullanici başlığı
                          ▼
                       Python ajan (127.0.0.1:8787)
                          │  EffectiveUserName
                          ▼
                       SSAS Tabular
```

**Ajan yalnızca `127.0.0.1`'e bağlanmalı.** Dışarıya açık kalırsa kimlik
başlığı taklit edilebilir ve tüm yetki denetimi çöker. Ajan gelen kimliği
istemciden değil, güvendiği ön katmandan alır.

### 2.2 · Kimliğe bürünme

Altyapı hazır. `lib/calistir_dax.py` bağlantıyı `EffectiveUserName` ile
kurabiliyor; değer `ayar['etkinKullanici']` üzerinden geliyor. Kullanıcı adı biçimi
doğrulanıyor (`DOMAIN\kullanici` veya `kullanici@alan`) — bağlantı dizesine
enjeksiyonu bu kapatıyor.

```python
calistir_dax.calistir(dax, {
    'ssasSunucu': r'SUNUCU\ORNEK',
    'ssasModel': 'ModelAdi',
    'etkinKullanici': istekten_kullanici,   # ön katmandan, İSTEMCİDEN DEĞİL
})
```

Servis hesabının **Analysis Services sunucu yöneticisi** olması gerekir —
kimliğe bürünme yetkisini veren tek şey budur. Bu yüzden:

- hesap yalnız bu iş için açılmalı, başka hiçbir serviste kullanılmamalı;
- parolası kasada tutulmalı, mümkünse gMSA kullanılmalı;
- ne yaptığı denetlenebilmeli (aşağıya bakın).

> **Neden Kerberos yetki devri değil?** Çift atlama (kullanıcı → IIS → SSAS)
> kısıtlı yetki devri ister; SPN kurulumu, hesap ayarları, ve her hata
> "erişim reddedildi" diye görünür. `EffectiveUserName` bunu atlar: servis
> hesabı adına bürünür, devir gerekmez. Kurulumu belirgin biçimde basit.

### 2.3 · Denetim kaydı gerçek kullanıcıyı yazmalı

`denetim.AjanKayit` tablosuna servis hesabı değil **etkin kullanıcı**
yazılmalı. Aksi hâlde kayıt "kim sordu" sorusuna cevap veremez ve denetim
değeri sıfırlanır.

### 2.4 · Bunu açıkça söyleyin

Sözleşmedeki `yetkisiz` deseni **güvenlik değildir**. "Maaş" kelimesini
yakalayıp reddetmek bir nezaket katmanıdır; asıl koruma SSAS rolleridir.
Desen listesi kullanıcıyı yanlış yönlendirmemek için var, veriyi korumak
için değil. Spesifikasyona bu cümleyle girsin.

---

## Faz 3 · Dağıtım

| Konu | PoC | Gerçek ortam |
|---|---|---|
| Süreç | Zamanlanmış görev | Windows servisi (NSSM veya benzeri) ya da IIS altında |
| Adres | `http://localhost:8787` | IIS arkasında, HTTPS, kurumsal ad |
| Kimlik | Yok | Windows Authentication (Faz 2) |
| Günlük | Dosya | Dosya + olay günlüğü; boyut döndürme zaten var |
| Denetim | `POC_SatisYZ` | Ayrı denetim veritabanı, yedekleme kapsamında |
| Yapılandırma | Ortam değişkenleri | Aynı — servis tanımında |

Sağlık ucu `/api/saglik` zaten var; izleme sistemine bağlayın. SSAS
erişilemezse ajan cevap üretmiyor, **uydurmuyor** — bu davranış korunmalı.

---

## Faz 4 · Raporlar

İki yön de hazır, yalnız adresler değişir.

**Rapordan ajana.** Dashboard'a köprülü bir metin kutusu: ajan adresi. PBIRS
istemcisinde `actionButton` görselinin web adresi aksiyonu **çalışmıyor**
(`role=link` ekleniyor ama tıklama tetiklenmiyor); köprülü metin parçası
gerçek bir `<a href>` üretiyor. Ayrıntı: `03-rapor/PBIX-KURULUM.md`.

**Ajandan rapora.** Cevap kartı RDL'i (`CevapKarti.rdl`) denetim
tablolarından okuyor; veri kaynağını kendi denetim veritabanınıza çevirin.
Kart RDL kalmalı — PBIRS `.pbix` için sunucu tarafı render sunmuyor, oysa
kartın işi tek bir görüntüye basılıp e-postaya ve arşive gitmek.

---

## Faz 5 · Yerel konuşma tanıma

Web Speech API sesi tarayıcı üreticisinin sunucusuna gönderir; kapalı devre
kısıtını bozan tek bileşen buydu. Yerine:

```
Tarayıcı  MediaRecorder ile ses yakalar
   │      POST /api/ses  (webm/opus)
   ▼
Ajan      yerel STT süreci → metin
   │      metin normal boru hattına girer
   ▼
Cevap     (sesli okuma zaten tarayıcıda yerel, değişmiyor)
```

Aday motorlar, CPU-only ortam için:

| Motor | Not |
|---|---|
| **Vosk** | Hafif, Türkçe modeli var, gerçek zamanlıya yakın. CPU'da en güvenli başlangıç. |
| **whisper.cpp** | Doğruluk daha yüksek, CPU'da yavaş. `small` modelle ölçün. |

Ölçmeden seçmeyin: hedef, konuşma bittikten sonra **1,5 saniyenin altında**
metin. Üstüne çıkarsa kullanıcı yazmayı tercih eder ve özellik ölü doğar.

Sesli okuma (`speechSynthesis`) tarayıcıda yerel çalışıyor, dokunulmuyor.

---

## Faz 6 · Kabul

Yayına almadan önce hepsi yeşil olmalı:

| Kontrol | Ölçüt |
|---|---|
| Altın küme | Kendi sorularınızla, %100 |
| Eşanlam kapsaması | Gerçek kullanıcı sorularıyla, hedefi siz koyun |
| Sınır davranışı | Kapsam dışı / yetkisiz / netleştirme doğru ayrışıyor |
| **RLS** | İki farklı yetkideki kullanıcı **farklı** sayı görüyor |
| Denetim | Her soru kayıtta, etkin kullanıcı adıyla |
| Süre | Cevap < 3 sn (PoC: ~750 ms) |
| Sağlık | SSAS kapalıyken ajan uydurmuyor, hata veriyor |

RLS satırı en kritik olanı ve tam olarak burada yanlış giden kurulumlar
görülüyor: `EffectiveUserName` sessizce yok sayılırsa herkes her şeyi görür
ve bu ancak biri fark ederse anlaşılır. Kabul testinde **iki gerçek hesapla
farklı sonuç** görmeden geçmeyin.

---

## Sıra ve efor

| Faz | İş | Kritik yol mu |
|---|---|---|
| 1 | Sözleşme — otomatik iskelet + elle tamamlama + ölçüm | **Evet.** Her şey buna bağlı |
| 2 | Kimlik, RLS, denetim | **Evet.** Yayın öncesi şart |
| 3 | Servis, HTTPS, izleme | Hayır, paralel yürür |
| 4 | Rapor bağlantıları | Hayır, küçük |
| 5 | Yerel STT | Hayır, sonraya bırakılabilir |

Efor Faz 1'de yoğunlaşır ve teknik değildir: ölçü tanımlarını ve kullanıcı
dilini toplamak. Kod tarafında yapılacak iş azdır — mimari zaten bunun için
kuruldu.

---

## Bu PoC'de doğrulanmayanlar

Dürüst olmak gerekirse, gerçek ortamda ilk karşılaşacağınız üç şey burada
test edilemedi:

1. **Kimliğe bürünme fiilen koşmadı.** Kod yolu ve giriş doğrulaması hazır,
   ama PoC makinesi etki alanında değil (`WORKGROUP`) ve
   `EffectiveUserName` çözümlenebilir bir etki alanı hesabı ister. İlk
   doğrulanacak şey bu olmalı.
2. **IIS ön katmanı kurulmadı.** Mimari tarif edildi, kurulumu yapılmadı.
3. **Yerel STT denenmedi.** Motor seçimi ölçüme bağlı.
