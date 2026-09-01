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

## Testler

```powershell
.\testler.cmd                      # üçü peş peşe
python test\altin_kume.py          # 19/19 · davranış regresyonu
python test\esanlam_testi.py       # 56/56 · söyleyiş kapsaması
python test\sinir_testi.py         # keşif · çalışan ajan gerektirir
```

**Altın küme** iddialıdır: reddetmesi gereken soruyu reddetmezse test kalır.
19 vakanın 8'i geçmişte **sessiz yanlış cevap** üretmiş gerçek hatalardır —
dördü denetim kaydından, kullanıcıların gerçekten sorduğu sorulardan çıktı.

**Eşanlam testi** kapsama ölçer: aynı şeyin farklı söylenişlerini anlıyor mu?
56 söyleyişin 11'i reddedilmesi gereken olumsuz örnektir. Eşleştiriciyi
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

**Ölçüldü: bu test kümesinde zeyrek'in kazancı yok.** İkisi de 56/56, hız
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
python araclar\sozluk_bosluk.py --gun 30
python araclar\sozlesme_iskelet.py --sunucu "SUNUCU\ORNEK" --model "Model"
```

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

araclar/                  sözleşme iskeleti · sözlük boşluğu
public/index.html         arayüz
test/                     altın küme · eşanlam · sınır
```

**`lib/sozlesme.py` kod değil yapılandırmadır** — veri yönetişiminin
sahipliğinde. Bir LLM devreye alınırsa değişecek tek dosya
`lib/planlayici.py`'dir; çıktı sözleşmesi aynı kaldığı için derleyici,
yorumlayıcı ve arayüz hiç değişmez.
