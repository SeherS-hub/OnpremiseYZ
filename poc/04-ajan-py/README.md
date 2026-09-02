# Yönetici Asistanı — ajan

Doğal dil sorusu → onaylı semantik model → cevap. Python 3.12, kapalı devre.

```
soru → planla → doğrula → derle (DAX) → çalıştır → yorumla → sun
```

Her adım denetim kaydına yazılır. Kayıtta olmayan metrik sorgulanamaz;
model erişilemezse ajan cevap **uydurmaz**, hata verir.

---

## Çalıştırma

```powershell
python sunucu.py
```

Arayüz: `http://localhost:8787` — soru kutusu, sesli sorma, cevap kartı.

Kalıcı çalıştırma için zamanlanmış görev:

```powershell
.\gorev-kur.ps1            # kur (veya güncelle)
.\gorev-kur.ps1 -Durum     # durum + sağlık
.\gorev-kur.ps1 -Baslat
.\gorev-kur.ps1 -Durdur
```

Görev **S4U** kimliğiyle koşar: parolasız, etkileşimsiz oturum. Etkileşimli
koşarken konsolu paylaşıyordu ve başka bir sürece gönderilen Ctrl+C ajanı da
düşürüyordu (logda `^C`). Çökerse 1 dk arayla 3 kez yeniden denenir.

Log: `denetim\ajan.log` (5 MB'ı geçince arşivlenir).

---

## Kurulum

```powershell
winget install --id Python.Python.3.12 --scope machine
pip install -r requirements.txt
```

İki tuzak:

**Store saplaması.** Ayarlar → Uygulamalar → Gelişmiş → Uygulama yürütme
takma adları: `python.exe` ve `python3.exe` **kapalı** olmalı. Açık kalırsa
`WindowsApps\python.exe` (0 bayt) PATH'i gölgeler ve "Python bulunamadı"
alırsınız. `ajan-baslat.cmd` bu yüzden Python'u tam yolla çağırıyor.

**Kapalı devre.** Paketleri iç aynadan ya da tekerlek deposundan kurun:

```powershell
pip download -r requirements.txt -d wheelhouse `
    --platform win_amd64 --python-version 312 --only-binary=:all:
pip install --no-index --find-links=wheelhouse -r requirements.txt
```

ADOMD.NET zaten kurulu (SSMS ile gelir). `pyodbc` için **ODBC Driver 18 for
SQL Server** gerekir.

---

## Neden bu kadar hızlı

Bağlantı süreç ömrü boyunca açık kalıyor. Bu bir mikro-optimizasyon değil,
ölçülmüş bir mimari karar:

```
PowerShell süreci açılışı      ~190 ms
ADOMD.NET yükleme               ~75 ms
bağlantı açma                  ~150 ms
SORGUNUN KENDİSİ                  4 ms
```

İlk gerçekleme her soru için yeni bir PowerShell süreci açıyordu; cevap
süresinin **%99'u sorgu değil altyapıydı**. `pythonnet` + `pyadomd` ile
bağlantı açık tutulunca:

| Ölçüm | Değer |
|---|---|
| HTTP tam gidiş-dönüş | 19–24 ms |
| Bunun sorgu kısmı | 10–14 ms |
| Ret cevapları (sorgu çalışmadan) | 5–6 ms |
| Açılış ısınması | SSAS ~730 ms · denetim ~37 ms, bir kez |
| İlk gerçek soru | 86 ms |
| Planlayıcı (yalnız NLP) | 0,9 ms |

Isınma üç soğuk maliyeti peşinen ödüyor: assembly yükleme + SSAS bağlantısı,
ilk sorgunun SSAS'ta derlenmesi, ve `pyodbc`'nin denetim veritabanına ilk
bağlanması. Yalnız birincisi ısıtıldığında ilk soru 2.177 ms sürüyordu.

Isınma denetim kaydına `(ısınma)` sorusuyla bir satır yazar;
`araclar/sozluk_bosluk.py` bunu ayıklar, yoksa her yeniden başlatma
cevaplama oranını yanlış gösterir.

---

## İleri analiz — tahmin, projeksiyon, katkı

Bu dördü eskiden **reddediliyordu**: tahmin `KAPSAM_DISI`'ndaydı, "neden"
soruları netleştirmeye düşüyordu. Ret gerekçeleri hâlâ geçerli; değişen şey
reddetmek yerine **belirsizliği ve sınırı birlikte vermek**.

| Niyet | Örnek soru | Hesap |
|---|---|---|
| `tahmin` | *"Gelecek ay ciro ne olur"* | OLS doğrusal eğilim + %80 kestirim aralığı |
| `yil_sonu` | *"Yıl sonunda hedefe ulaşır mıyız"* | Koşu hızı projeksiyonu + aynı dönem hedefi |
| `katki` | *"Ciro neden düştü"* | Boyut bazında katkı ayrıştırması |
| `hacim_sepet` | *"Düşüş adetten mi sepetten mi"* | Ciro = Adet × Sepet cebirsel ayrıştırma |

`lib/tahmin.py` · `lib/katki.py` · `lib/ileri_analiz.py`

### Dürüstlük kapıları

Bu özelliğin tamamı, sahte kesinlik üretmemek üzerine kurulu.

**Ufuk sınırı** — en fazla 3 dönem ve geçmişin üçte birinden fazla değil.
12 ay istenirse kırpılır ve kırpıldığı söylenir. 10 dönemle 12 ay ileri
gitmek kestirim değil kehanettir.

**R² eşiği 0,30** — eğilim yoksa tahmin **üretilmez**. Bu modelin gerçek
ciro serisinde R²=0,04; ajan şunu diyor:

> Tahmin üretmiyorum: belirgin bir eğilim yok. Net ciro serisinde yön
> açıklayıcılığı %4 (eşik %30) — bu seride doğrusal bir eğilim yakalamak
> sayı uydurmak olurdu. Son 10 dönemin ortalaması 89,2 mn TL.

**Nokta tahmini asla tek başına dönmez.** %80 kestirim aralığı zorunlu;
tek sayı gören insan onu kesinlik sanıyor.

**Toplanabilirlik.** Her ölçüde `toplanabilir` bayrağı var. Projeksiyon ve
katkı dönemleri/kalemleri **toplar**; oran, ortalama, tekil sayım ve
birikimli ölçülerde bu anlamsızdır ve reddedilir. İlk sürümde bu kapı
yoktu ve *"Yıl sonunda hedefe ulaşır mıyız"* sorusu yüzdeleri toplayıp
**"793,8%"** üretiyordu.

**Aynı dönem karşılaştırması.** Hedef karşılaştırması gerçekleşen dönemlerle
aynı aralık üzerinden yapılır. İlk sürüm 12 aylık projeksiyonu 8 aylık
hedefe bölüp **%148,8** diyordu — dipnotu vardı ama cümlenin kendisi
yanıltıcıydı. Şimdi %99,2 (704,5 / 710,0) ve tam yıl hedefi modelde
olmadığı için tam yıl karşılaştırması **yapılmıyor**.

### Nedensellik iddia edilmiyor

Katkı ayrıştırması "neden" sorusunun cevabı **değil**; her cevapta yazıyor:

> Bu bir KATKI ayrıştırmasıdır, sebep değil. Kalemlerin kendi değişiminin
> nedeni (kampanya, rekabet, mevsim, fiyat kararı) bu modelde yok.

Aritmetik kapalı: katkıların toplamı toplam değişime **tam** eşit, hacim ×
sepet ayrıştırmasında sapma sıfır. Denetlenebilirliğin ölçüsü bu.

Senaryo modelleme hâlâ kapsam dışı — *"fiyatı %10 artırsak"* karşı-olgusal
bir soru, elastikiyet ve maliyet bilgisi modelde yok.

---

## Testler

```powershell
.\testler.cmd                      # üçü peş peşe
python test\altin_kume.py          # 25/25 · davranış regresyonu
python test\esanlam_testi.py       # 65/65 · söyleyiş kapsaması
python test\sinir_testi.py         # keşif · çalışan ajan gerektirir
```

**Altın küme** iddialıdır: reddetmesi gereken soruyu reddetmezse test kalır.
25 vakanın 8'i geçmişte **sessiz yanlış cevap** üretmiş gerçek hatalardır —
dördü denetim kaydından, kullanıcıların gerçekten sorduğu sorulardan çıktı.

**Eşanlam testi** kapsama ölçer: aynı şeyin farklı söylenişlerini anlıyor mu?
65 söyleyişin 13'ü reddedilmesi gereken olumsuz örnektir. Eşleştiriciyi
gevşetmenin bedeli oradan görülür; yeni eşanlamlı eklendiğinde önce bu
koşulmalı. Vakalar `test/esanlam-durumlar.json` içinde — düz JSON, elle
düzenlenir.

**Sınır testi** iddiasızdır, çıktıyı insan okur. Özellikle F bloğu (anlamsız
girdiler) ajanın uydurmadığını gözle doğrulatır.

---

## Dilbilgisi katmanı — iki çözümleyici

Türkçe eklemeli; "ciro" ile "cirolarımızdan" aynı kavram. Sözlüğe her çekimi
yazmak yerine `lib/dilbilgisi.py` var.

| `POC_DILBILGISI` | Ne yapar |
|---|---|
| `kural` (varsayılan) | Ek soyma + ünsüz yumuşaması. Bağımlılık yok. |
| `zeyrek` | Zemberek'in Python portu; gerçek biçimbirim çözümlemesi. |

**Ölçüldü: bu test kümesinde zeyrek'in kazancı yok.** İkisi de 65/65, hız
farkı ihmal edilebilir. Zeyrek `satışlarımız → satmak`, `kârlılık → kâr`
bağlarını kurabiliyor — kural katmanı kuramıyor — ama mevcut sorular bunu
gerektirmiyor. Zeyrek `nltk` ve bir korpus indirmesi getiriyor; kapalı
devrede ayrıca taşınması gereken varlıklar.

Karar: varsayılan kural katmanı kalsın. `araclar/sozluk_bosluk.py` ile
toplanan gerçek soru havuzu büyüdüğünde yeniden ölçün.

Kapsamayı gevşetmenin bedeli yanlış eşleşme; dört kapı bunun için, dördü de
yaşanmış hatalardan çıktı:

1. Karşılaştırılabilir en kısa gövde **4 harf** — 3'te `hedef` ile `hediye`
   çakışıyor.
2. Yazım toleransı yalnız **yüzey biçimler** arasında — türetilmiş gövdeler
   de girince `tutturduğumuz` → `tuttur`, `tuttuk` ile eşleşiyordu.
3. Tolerans için **ilk harf aynı** olmalı — yoksa `yaptık` ↔ `saptık`.
4. **Sözlükte olan kelime düzeltilmez** — `sattık`, `saptık`a çevrilmemeli.

---

## Araçlar

```powershell
python araclar\model_gozat.py                    # modeli incele
python araclar\sozluk_bosluk.py --gun 30         # sözlük boşluğu raporu
python araclar\sozlesme_iskelet.py --sunucu "SUNUCU\ORNEK" --model "Model"
```

**`model_gozat`** — SSAS Tabular modelini konsoldan inceler. SSMS 21+
Analysis Services Object Explorer desteğini kaldırdı; bu makinede SSMS 22'de
AS bileşeni yok. Bu araç o boşluğu doldurur, hiçbir şey kurmadan.

```powershell
python araclar\model_gozat.py                    # tam özet
python araclar\model_gozat.py --veritabanlari    # sunucudaki modeller
python araclar\model_gozat.py --tablo Satis      # kolonlar, türler, gizlilik
python araclar\model_gozat.py --olcu "Net Ciro"  # ölçünün DAX'ı
python araclar\model_gozat.py --ara ciro         # ad ve DAX içinde arama
python araclar\model_gozat.py --dax-dosya araclar\ornek.dax
python araclar\model_gozat.py --satir-sayma-yok  # hızlı
```

Tam özet şunları verir: tablolar (satır sayısı, gizlilik), ölçüler (biçim,
klasör), **ilişkiler süzme yönüyle birlikte**, roller + üyeler + satır
filtreleri, bölüm durumu ve son işleme zamanı.

Düzenleme ve işleme yok — o iş için Tabular Editor gerekir.

> Karmaşık DAX'ı `--dax-dosya` ile verin. PowerShell argüman içindeki çift
> tırnakları yutuyor; `"Ciro"` etiketi `Ciro` olup sözdizimi hatası veriyor.

**`sozluk_bosluk`** — zenginleştirme döngüsünün motoru. Denetim kaydındaki
gerçek soruları okur, sözleşmeye neyin eklenmesi gerektiğini sıralar:
reddedilen sorulardaki bilinmeyen kelimeler, netleştirme kümeleri, cevaplanmış
ama içinde tanınmayan kelime geçen sorular, en sık sorulanlar.

**`sozlesme_iskelet`** — modelden sözleşme iskeleti çıkarır. En değerlisi
**ölçü-boyut geçerliliği**: ilişki grafiğini süzme yönünü izleyerek gezip
hangi ölçünün hangi boyutla anlamsız olduğunu bulur. PoC'de `Müşteri Sayısı`
ilişkisiz bir tablodan geliyordu ve kanal filtresi sessizce yok sayılıyordu;
araç bu kısıtı kendisi buluyor.

---

## Satır düzeyi güvenlik (RLS)

`ayar['etkinKullanici']` verilirse bağlantı `EffectiveUserName` ile kurulur
ve sorgu o kullanıcının rolleriyle koşar. Kimlik **sunucudan** gelir,
istemciden asla — `sunucu.py` bunu `X-Kullanici` başlığından okur ve bu
başlık yalnızca öndeki kimlik doğrulayan katmandan gelmelidir.

Kullanıcı adı biçimi doğrulanıyor (`DOMAIN\kullanici` / `kullanici@alan`);
bağlantı dizesine enjeksiyonu bu kapatıyor.

Bu makinede fiilen doğrulanamadı: makine etki alanında değil (`WORKGROUP`),
`EffectiveUserName` çözümlenebilir bir etki alanı hesabı ister. Kurulum ve
kabul ölçütleri: `../GERCEK-ORTAMA-GECIS.md`.

---

## Dosyalar

```
sunucu.py                 HTTP API + statik sunum
ajan-baslat.cmd           zamanlanmış görev bunu çağırır
gorev-kur.ps1             görev kurulumu / durum / kaldırma
testler.cmd               üç testi sırayla koşar

lib/sozlesme.py           metrik kaydı · eşanlamlı sözlüğü · boyut kataloğu
lib/dilbilgisi.py         Türkçe biçimbilim + yazım toleransı
lib/planlayici.py         doğal dil → sorgu spesifikasyonu
lib/derleyici_dax.py      spesifikasyon → DAX
lib/calistir_dax.py       ADOMD.NET, kalıcı bağlantı, RLS
lib/yorumlayici.py        sonuç → Türkçe cevap + künye
lib/baglam_serisi.py      cevap kartının trend/hedef serileri
lib/denetim_sql.py        denetim kaydı (pyodbc)
lib/tahmin.py             OLS eğilim tahmini + kestirim aralığı
lib/katki.py              katkı ayrıştırması · hacim × sepet
lib/ileri_analiz.py       tahmin/projeksiyon/katkı orkestrasyonu

araclar/                  model gözatıcı · sözleşme iskeleti · sözlük boşluğu
public/index.html         arayüz
test/                     altın küme · eşanlam · sınır
```

**`lib/sozlesme.py` kod değil yapılandırmadır** — veri yönetişiminin
sahipliğinde. Bir LLM devreye alınırsa değişecek tek dosya
`lib/planlayici.py`'dir; çıktı sözleşmesi aynı kaldığı için derleyici,
yorumlayıcı ve arayüz hiç değişmez.
