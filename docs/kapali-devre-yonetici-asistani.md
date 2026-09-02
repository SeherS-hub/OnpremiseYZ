# Kapalı Devre Yönetici Asistanı

**Teknik Spesifikasyon ve Mimari Değerlendirme**

Kurum içi veri ambarı ve semantik model üzerinde doğal dille çalışan, tek bir baytı bile kurum dışına çıkarmayan, yalnızca CPU ile koşan LLM + ajan mimarisi.

| Alan | Değer |
|---|---|
| Doküman | ONPREM-YZ-SPEC-001 |
| Sürüm | 0.9 — inceleme için |
| Tarih | 28.08.2026 |
| Durum | Onay bekliyor |
| Sahip | Veri & Yapay Zekâ Platformu |
| Onaylayacaklar | CIO · CDO · CISO |
| Dağıtım modeli | Şirket içi, internet erişimsiz |
| Hızlandırıcı | Yok — yalnızca CPU |

---

## İçindekiler

- [00 — Yönetici özeti ve karar](#00--yönetici-özeti-ve-karar)
- [01 — Amaç, kapsam, kapsam dışı](#01--amaç-kapsam-kapsam-dışı)
- [02 — Kullanıcılar ve senaryolar](#02--kullanıcılar-ve-senaryolar)
- [03 — Kısıtlar ve varsayımlar](#03--kısıtlar-ve-varsayımlar)
- [04 — Mimari genel görünüm](#04--mimari-genel-görünüm)
- [05 — CPU üzerinde LLM katmanı](#05--cpu-üzerinde-llm-katmanı)
- [06 — Anlam sözleşmesi](#06--anlam-sözleşmesi)
- [07 — Sorgu üretim stratejisi](#07--sorgu-üretim-stratejisi)
- [08 — Ajan mimarisi](#08--ajan-mimarisi)
- [09 — Güvenlik ve yetkilendirme](#09--güvenlik-ve-yetkilendirme)
- [10 — Doğruluk ve değerlendirme](#10--doğruluk-ve-değerlendirme)
- [11 — Kullanıcı deneyimi](#11--kullanıcı-deneyimi)
- [12 — Platform ve işletim](#12--platform-ve-işletim)
- [13 — Donanım ve kapasite](#13--donanım-ve-kapasite)
- [14 — Uçtan uca değerlendirme](#14--uçtan-uca-değerlendirme)
- [15 — Yol haritası](#15--yol-haritası)
- [16 — Ekip ve sorumluluklar](#16--ekip-ve-sorumluluklar)
- [17 — Gereksinim listesi](#17--gereksinim-listesi)
- [18 — Kabul kriterleri](#18--kabul-kriterleri)
- [19 — Açık kararlar](#19--açık-kararlar)
- [20 — Ekler ve sözlük](#20--ekler-ve-sözlük)

---

## 00 — Yönetici özeti ve karar

Yalnızca CPU ile çalışan, veriyi kurumdan çıkarmayan bir yönetici asistanı **teknik olarak yapılabilir** — ancak bir koşulla: dil modelinin işi *veriyi okumak* değil, *doğru sorguyu yazmak* olmalıdır. Ağır iş yükü veri ambarı motorunda kalır; modelin ürettiği çıktı birkaç yüz token'lık yapılandırılmış bir sorgu tarifidir. Bu tasarım kararı, CPU'nun düşük token üretim hızını darboğaz olmaktan çıkarır.

Bunun tersi olan yaklaşım — binlerce satır veriyi modelin bağlamına doldurup "sen yorumla" demek — GPU'suz bir ortamda çalışmaz. 30 bin token'lık bir bağlamı işlemek CPU'da onlarca saniye sürer, eşzamanlı üç kullanıcıda sistem kilitlenir. Projenin başarısı, mimarinin hangi işi nereye verdiğine bağlıdır; model boyutuna değil.

### Üç temel tasarım kararı

**Model SQL yazmaz, sorgu tarifi yazar.** LLM, doğrudan T-SQL yerine kısıtlı bir JSON sorgu spesifikasyonu üretir (metrik, boyut, filtre, dönem). Deterministik bir derleyici bunu SQL veya DAX'a çevirir. Serbest SQL üretiminin hem doğruluk hem güvenlik maliyeti çok yüksektir.

**Doğruluk modelde değil, metadata'da.** Onaylı metrik kaydı, iş sözlüğü, Türkçe eşanlamlı sözlüğü ve boyut değer sözlüğü olmadan hiçbir model "geçen çeyrek kârlılık nasıl?" sorusunu güvenilir yanıtlayamaz. Yatırımın ağırlık merkezi buradadır.

**Kapsam daraltılmış, cevap denetlenebilir.** Sistem kapsam dışı soruya cevap uydurmaz; "bu soruyu onaylı metriklerle yanıtlayamıyorum" der. Her cevabın yanında kullanılan metrik, filtre ve üretilen sorgu görünür. Yönetici kararı buna güvenerek verir.

### Beklenti çerçevesi

| Boyut | Gerçekçi hedef (12. ay) | Not |
|---|---|---|
| Kapsam içi soruda doğruluk | %85–92 yürütme doğruluğu | Onaylı metrik + şablon kapsamındaki sorular |
| Açık uçlu, kapsam dışı soru | %35–55 | Bu yüzden cevap vermek yerine reddetmeyi tercih ederiz |
| Doğru reddetme oranı | > %90 | En kritik metrik: yanlış cevap, cevapsızlıktan pahalıdır |
| İlk token gecikmesi | < 3 sn | Yönlendirici model + akış (streaming) ile |
| Uçtan uca cevap süresi | 8–20 sn (p50–p95) | Sorgu süresi hariç değil, dahil |
| Eşzamanlı kullanıcı (tek düğüm) | 2–4 aktif üretim | Önbellek isabetleri bunun üstüne biner |
| Veri sızıntısı | Sıfır — mimari olarak | Dışa çıkış yolu yok; §09 |

> Yüzdeler benzer kurumsal NL2SQL kurulumlarından türetilmiş hedeflerdir; §10'daki altın soru kümesiyle doğrulanmadan taahhüt edilmemelidir.

### Karar önerisi

**Onay verilsin** — ancak §15'teki Faz 1 (8 haftalık kanıtlama, tek konu alanı, 25 soru) çıkış kriterleri sağlanmadan pilot genişletilmesin. Faz 1'in maliyeti, mevcut donanımla sınırlı tutulabilir; asıl donanım yatırımı Faz 2'de yapılır. Bu, geri dönülemez harcamayı ölçüm sonrasına erteler.

---

## 01 — Amaç, kapsam, kapsam dışı

### 1.1 Amaç

Üst ve orta düzey yöneticilerin, rapor talebi açmadan ve analist beklemeden, kurumun onaylı iş metriklerini kendi dilleriyle sorgulayabilmesi. Hedef, self-servis BI araçlarının öğrenme eğrisini ortadan kaldırmak ve "bu sayı neden böyle?" sorusunun cevabına dakikalar içinde ulaşmaktır.

### 1.2 Kapsam içi

- Türkçe (ve İngilizce) doğal dil ile sorgu; takip sorularıyla bağlamı koruyan diyalog.
- Kurum içi veri ambarındaki (DWH) yıldız şemaları ve mevcut semantik model üzerinden okuma.
- Toplulaştırılmış sonuçların tablo, temel grafik ve kısa metin yorumu olarak sunulması.
- Dönemsel karşılaştırma, trend, kırılım, sıralama, hedef–gerçekleşme, basit varyans açıklaması.
- Kullanıcının yetkisi neyse o kadarını görmesi (satır ve kolon düzeyi güvenlik).
- Her cevabın izlenebilirliği: kullanılan metrik, filtre, üretilen sorgu, çalıştırma zamanı.
- Tamamen çevrimdışı çalışma: model ağırlıkları, kütüphaneler ve çalışma zamanı kurum içinde.

### 1.3 Kapsam dışı (bu sürümde)

- **Yazma işlemleri.** Sistem hiçbir koşulda veri değiştirmez; bağlantı salt okunur kullanıcıyla açılır.
- **Serbest metin doküman arama.** Sözleşme, sunum, e-posta üzerinde RAG ayrı bir projedir; CPU maliyeti profili tamamen farklıdır.
- **Senaryo modelleme.** "Fiyatı %10 artırsak ne olur?" karşı-olgusal veri gerektirir; modelde yok, kapsam dışı kalıyor.
- ~~**Tahmin.**~~ *(PoC'de kapsama alındı.)* "Gelecek ay ne olur?" sorusu LLM'in değil istatistiğin işi — bu yüzden LLM'e değil açık aritmetiğe verildi: eğilim varsa en küçük kareler doğrusu, yoksa yön iddiası olmayan seviye tahmini; her ikisinde %80 kestirim aralığı, ufuk sınırı ve TAHMİN etiketi zorunlu. Ayrıntı: `poc/04-ajan-py/README.md` → *Dürüstlük kapıları*.
- **Gerçek zamanlı operasyonel veri.** Kaynak, DWH tazeleme takvimine bağlıdır (tipik olarak T-1).
- **Otonom eylem.** Asistan e-posta göndermez, sistemde işlem başlatmaz.
- **Model eğitimi / ince ayar.** Faz 3'e kadar yalnızca istem mühendisliği ve retrieval; ince ayar §14.4'te değerlendirilir.

> **Neden kapsam bu kadar sert çiziliyor.** Bu tür projelerin başarısızlık nedeni model kalitesi değil, kapsam kaymasıdır. "Her şeyi sorabildiğiniz asistan" vaadi, ilk yanlış cevapta güveni kalıcı olarak yok eder. Dar ve doğru bir asistan, geniş ve şüpheli bir asistandan kurumsal olarak daha değerlidir.

---

## 02 — Kullanıcılar ve senaryolar

### 2.1 Kullanıcı profilleri

| Profil | Kullanım şekli | Hacim beklentisi | Kritik ihtiyaç |
|---|---|---|---|
| Üst yönetim (CEO, CFO, GM) | Günlük 3–8 kısa soru, çoğu tekrar eden | ~20 kişi | Hız, kesinlik, mobil erişim |
| Direktör / bölüm yöneticisi | Kırılım ve karşılaştırma, günde 10–20 soru | ~80 kişi | Kırılım derinliği, dışa aktarma |
| İş analisti | Hipotez testi, üretilen SQL'i inceleme | ~40 kişi | Şeffaflık, SQL'i alıp geliştirebilme |
| Veri yönetişimi | Metrik tanımı bakımı, denetim kaydı incelemesi | ~5 kişi | Yönetim arayüzü, sürümleme |

Toplam ~145 lisanslı kullanıcı, tepe saatte (09:00–10:00 ve pazartesi sabahı) tahmini **3–6 eşzamanlı aktif soru**. Kapasite planı §13 bu sayıya göre kurulmuştur.

### 2.2 Örnek sorular ve beklenen davranış

| Soru | Sınıf | Beklenen davranış |
|---|---|---|
| "Bu ayın cirosu geçen yılın aynı ayına göre nasıl?" | Basit | Tek metrik, YoY karşılaştırma, tek satır sonuç + yüzde değişim + tek cümle yorum |
| "En çok büyüyen 5 ürün grubu hangileri?" | Sıralama | Metrik + boyut + büyüme hesabı + Top-N; ölçüt belirsizse (tutar mı yüzde mi) netleştirme sorusu |
| "Marmara'da tahsilat performansı düştü mü?" | Muğlak | "Tahsilat performansı" iki onaylı metriğe eşleşiyor → kullanıcıya hangisini kastettiği sorulur |
| "Neden kârlılık düştü?" | Nedensel | Nedensellik iddia edilmez. Kâr kırılımı (hacim / fiyat / maliyet / karma) hesaplanır, en büyük katkı kalemleri gösterilir, "olası etkenler" ifadesi kullanılır |
| "Ahmet Yılmaz'ın maaşı ne?" | Yetkisiz | Yetki kontrolü kesin reddeder; denetim kaydına yazılır; model bu veriyi hiç görmez |
| "Rakiplerin pazar payı ne oldu?" | Kapsam dışı | Veri ambarında yok → net reddetme, tahmin yok |
| "Aynı grafiği bölge kırılımıyla göster" | Takip | Önceki sorgu spesifikasyonu üzerine yalnızca boyut eklenir; sıfırdan üretilmez |
| "Bunu her sabah 08:00'de bana gönder" | Abonelik | Sorgu spesifikasyonu kaydedilir, zamanlanmış brifing olarak kurulur (Faz 4) |

> Bu tablo aynı zamanda Faz 1 altın soru kümesinin çekirdeğidir; her satır test edilebilir bir kabul senaryosudur.

---

## 03 — Kısıtlar ve varsayımlar

### 3.1 Sert kısıtlar

| Kod | Kısıt | Mimari sonucu |
|---|---|---|
| K-01 | Hiçbir veri (soru metni dahil) kurum ağı dışına çıkamaz | Bulut LLM API'si, telemetri, uzaktan model indirme, harici izleme SaaS'ı yok. Çıkış trafiği güvenlik duvarında varsayılan-ret. |
| K-02 | GPU yok, satın alınmayacak | Model seçimi bellek bant genişliğine göre yapılır; MoE mimarileri öne çıkar. Bağlam uzunluğu bir maliyet kalemidir. |
| K-03 | Mevcut DWH ve semantik model yeniden yazılmayacak | Sistem tüketici olarak konumlanır; yalnızca ek metadata katmanı üretilir. |
| K-04 | KVKK (6698) ve kurum içi veri sınıflandırma politikası geçerli | Kişisel veri maskeleme, amaç sınırlaması, denetim kaydı ve saklama süresi zorunlu. |
| K-05 | Mevcut kimlik altyapısı Active Directory | Kimlik doğrulama Kerberos/OIDC; yetki, veri katmanındaki RLS ile aynı kaynaktan beslenir. |
| K-06 | Kurumsal onaylı açık kaynak lisansları | Model lisansları hukuk onayından geçer (Apache-2.0 tercih, özel lisanslar incelenir). |

### 3.2 Varsayımlar — doğrulanmazsa plan değişir

- **V-01.** DWH ilişkisel bir yıldız şeması sunuyor ve okuma replikası açılabiliyor. *(Faz 0'da doğrulanacak)*
- **V-02.** Semantik model tablosal (Analysis Services / Power BI türü) ve XMLA benzeri programatik bir uç noktası var. Yoksa §07'deki B seçeneği düşer.
- **V-03.** En az 60 iş metriği için yazılı, üzerinde anlaşılmış tanım var ya da 8 hafta içinde üretilebilir. *Bu, projenin en kritik varsayımıdır.*
- **V-04.** Sunucularda AVX-512 destekli, tercihen AMX içeren güncel nesil sunucu işlemcisi mevcut ya da tedarik edilebilir.
- **V-05.** Yönetici soruları büyük ölçüde tekrar ediyor (uzun kuyruk sınırlı) — önbellek ve şablon stratejisi bu varsayıma dayanır.

> **V-03 gerçekleşmezse.** Metrik tanımları yoksa proje bir yapay zekâ projesi değil, bir veri yönetişimi projesidir ve öyle planlanmalıdır. Bu durumda Faz 1'in kapsamı "asistan kurmak"tan "tek konu alanında 25 metriği onaylı tanıma kavuşturmak ve üzerine asistan koymak"a çevrilir. Sıra değişmez: tanım önce gelir.

---

## 04 — Mimari genel görünüm

Sistem yedi katmandan oluşur ve tamamı kurum ağı içinde, internet çıkışı kapalı bir bölgede çalışır. Katmanlar arası tek kural şudur: **ham veri yukarı doğru akmaz.** Dil modeli hiçbir zaman satır düzeyinde veri görmez; yalnızca metadata ve toplulaştırılmış sonuç özeti görür.

```
╔═ KURUM AĞI · internet çıkışı yok ═══════════════════════════════════════╗
║                                                                         ║
║  L1 · Arayüz       [Sohbet arayüzü: web+SSO]  [Teams eklentisi]         ║
║                    [Mobil görünüm]            [Excel / CSV aktarma]     ║
║                                                                         ║
║  L2 · Orkestrasyon [Ajan yöneticisi: durum makinesi]                    ║
║                    [Oturum & diyalog belleği]  [Bağlam derleyici]       ║
║                    [Yanıt biçimlendirici]      [Kuyruk & eşzamanlılık]  ║
║                                                                         ║
║  L3 · Zekâ         [Ana model: MoE · 4-bit · CPU]                       ║
║                    [Yönlendirici 1–3B]  [Gömme]  [Yeniden sıralayıcı]   ║
║                                                                         ║
║  L4 · Anlam        [Metrik kaydı: onaylı tanımlar]  [İş sözlüğü]        ║
║                    [TR eşanlamlı sözlüğü]  [Boyut değer indeksi]        ║
║                    [Sorgu şablon kütüphanesi]  [Vektör indeksi]         ║
║                                                                         ║
║  L5 · Yürütme      [Sorgu derleyici: JSON → SQL/DAX]                    ║
║                    [Doğrulayıcı: izin listesi · limit]                  ║
║                    [Salt okunur bağlantı havuzu]  [Sonuç önbelleği]     ║
║                                                                         ║
║  L6 · Veri         [Veri ambarı: okuma replikası]                       ║
║                    [Semantik model: XMLA]  [Satır düzeyi güvenlik]      ║
║                                                                         ║
║  L7 · Platform     [Konteyner platformu]  [Model ağırlık deposu]        ║
║                    [İzleme & ölçüm]  [Denetim kaydı: değiştirilemez]    ║
╚═════════════════════════════════════════════════════════════════════════╝
```

### 4.1 Bir sorunun yaşam döngüsü

1. **Kimlik ve yetki çözümlenir.** Kullanıcı SSO ile gelir; dizin grupları oturuma bağlanır. Yetki bağlamı bu noktadan sonra her adımda taşınır — sonradan eklenmez.
2. **Niyet sınıflandırılır.** Küçük yönlendirici model soruyu sınıflar: metrik sorgusu, takip sorusu, tanım sorusu, kapsam dışı, yetkisiz. *(~150 ms)*
3. **Anlamsal eşleştirme yapılır.** Sorudaki iş terimleri gömme araması ve eşanlamlı sözlüğü ile onaylı metrik ve boyutlara eşlenir. Eşleşme skoru düşükse netleştirme sorusu üretilir.
4. **Bağlam derlenir.** Yalnızca ilgili 5–12 metrik tanımı, ilgili boyutlar ve 2–3 benzer örnek istem içine konur. *(Hedef: 3.000 token altı)*
5. **Model sorgu spesifikasyonu üretir.** Ana model, şema ile kısıtlanmış JSON çıktısı verir. Serbest metin değil, dilbilgisi ile zorlanmış yapı. *(~200–400 token)*
6. **Spesifikasyon doğrulanır.** Metrik izin listesinde mi, boyut geçerli mi, dönem tanımlı mı, kullanıcı bu metriği görebiliyor mu? Başarısızsa modele tek sefer geri bildirimle dönülür.
7. **Sorgu derlenir.** Deterministik derleyici SQL veya DAX üretir; model üretilen sorguyu asla doğrudan yazmaz. Zorunlu satır limiti, zaman aşımı ve maliyet tavanı eklenir.
8. **Sorgu çalıştırılır.** Salt okunur bağlantı, kullanıcının kimliğiyle veya satır düzeyi güvenlik bağlamıyla. Ağır iş burada yapılır — CPU'da değil, veri ambarı motorunda.
9. **Sonuç özetlenir.** Yalnızca toplulaştırılmış sonuç (tipik olarak 100 satırın altında) modele döner ve 2–4 cümlelik yorum üretilir. Sayılar metinden değil, sonuç kümesinden basılır.
10. **Cevap ve kanıt sunulur.** Tablo, grafik, kullanılan metrik tanımı, filtreler, üretilen sorgu ve veri tazelik zamanı birlikte gösterilir. Tamamı denetim kaydına yazılır.

> **Mimarinin özü.** Dil modeli bu zincirde **bir çevirmendir, bir hesap makinesi değil.** Doğal dili yapılandırılmış sorgu niyetine çevirir; hesabı veri ambarı yapar, doğruluğu metrik kaydı garanti eder, sınırı yetki katmanı çizer. Model değiştirilebilir bir parçadır — 18 ay sonra daha iyi bir açık model çıktığında yalnızca L3 değişir, üstündeki hiçbir şey değişmez.

### 4.2 Neden bu ayrım kritik

| Ölçüt | Model veriyi okur (bağlama doldurma) | Model sorgu yazar (bu tasarım) |
|---|---|---|
| Modele giden token | 20.000–60.000 | 1.500–3.000 |
| CPU'da ön-dolum süresi | 40–120 sn | 3–8 sn |
| Aritmetik doğruluk | Model toplama yapar — güvenilmez | Veri ambarı motoru hesaplar — kesin |
| Veri hacmi sınırı | Bağlam penceresi kadar | Pratikte sınırsız |
| Yetki uygulaması | Veri zaten bağlama girmiş — sızıntı riski | Sorgu düzeyinde, veri katmanında |
| İzlenebilirlik | "Model bu sayıyı nereden buldu?" belirsiz | Üretilen sorgu kanıttır |

---

## 05 — CPU üzerinde LLM katmanı

CPU çıkarımında darboğaz işlem gücü değil, **bellek bant genişliğidir.** Üretilen her token için modelin aktif ağırlıklarının tamamı bellekten okunur. Bu tek cümle, model seçiminden donanım listesine kadar bütün kararları belirler.

### 5.1 Basit hesap

Yaklaşık üretim hızı, kullanılabilir bellek bant genişliğinin token başına okunması gereken aktif ağırlık hacmine bölümüdür. Yoğun (dense) bir modelde aktif ağırlık modelin tamamıdır; uzman karışımı (MoE) bir modelde ise yalnızca seçilen uzmanlar okunur. Fark, pratikte üç ilâ beş kat hızdır.

```
# Kaba tavan hesabı — çift soketli, çok kanallı DDR5 sunucu

Ölçülen gerçekçi bant genişliği   ~ 320 GB/sn   (teorik ~460, verim ~%70)
Verimlilik katsayısı              ~ 0,65        (çekirdek ölçekleme kaybı)

Yoğun 32B model, 4-bit            aktif ağırlık ~ 18 GB
   320 x 0,65 / 18                = yaklaşık 11 token/sn

MoE 100B / 12B aktif, 4-bit       aktif ağırlık ~ 7 GB
   320 x 0,65 / 7                 = yaklaşık 30 token/sn

# 300 token'lık bir sorgu spesifikasyonu için:
   yoğun 32B   ->  ~27 sn   kabul edilemez
   MoE         ->  ~10 sn   + ön-dolum ~3 sn = ~13 sn
```

Bu yüzden mimari **üretilen token sayısını en aza indirmek** üzerine kuruludur: model uzun açıklama değil, kısa ve yapılandırılmış çıktı üretir. Nihai kullanıcı metni de kısadır (2–4 cümle) ve akış hâlinde gösterilir, böylece algılanan gecikme gerçek gecikmenin altında kalır.

### 5.2 Model kademeleri

| Kademe | Boyut / tip | Görev | Gecikme bütçesi | Bellek |
|---|---|---|---|---|
| Yönlendirici | 1–3B yoğun, 4-bit | Niyet sınıflama, kapsam dışı tespiti, netleştirme kararı | 400 ms altı | ~2 GB |
| Ana akıl yürütücü | MoE, ~100B toplam / 10–15B aktif, 4-bit | Sorgu spesifikasyonu üretimi, sonuç yorumu | 3–12 sn | 55–70 GB |
| Gömme | 300M–1B, çok dilli | Metrik ve terim eşleştirme, şablon getirme | 100 ms altı | ~1 GB |
| Yeniden sıralayıcı | 100–300M cross-encoder | İlk 30 adayı 8'e indirme | 250 ms altı | ~0,5 GB |

> Üç ayrı model, üç ayrı iş. Tek büyük modelle her işi yapmak CPU'da savurganlıktır.

### 5.3 Model seçim ölçütleri

Somut model adı bu dokümanda *bilinçli olarak* sabitlenmemiştir; açık ağırlıklı model alanı altı ayda bir yeniden diziliyor ve bir spesifikasyonun ömrü bundan uzundur. Bunun yerine seçim ölçütleri sabitlenir, Faz 0'da §10'daki altın soru kümesiyle üç aday ölçülür ve kazanan kayda geçer:

- **Mimari:** Uzman karışımı, aktif parametre 15B veya altı. CPU'da pazarlık edilemez tek ölçüt budur.
- **Türkçe yeterlik:** Türkçe soruyu doğru *anlama*. Çıktının Türkçe olması gerekmez (çıktı JSON'dur), ama anlama kalitesi doğrudan doğruluğa yansır.
- **Yapılandırılmış çıktı disiplini:** Dilbilgisi kısıtı altında (JSON şeması / GBNF) bozulmadan üretebilmesi.
- **Araç çağırma yeteneği:** Ajan döngüsü için eğitim sırasında araç kullanımı görmüş olması.
- **Lisans:** Ticari kullanıma açık, tercihen Apache-2.0; hukuk onayından geçebilir olması.
- **Nicemleme dayanıklılığı:** 4-bit ağırlıkta kalite kaybının ölçülmüş ve kabul edilebilir olması.

### 5.4 Çıkarım çalışma zamanı kararları

| Konu | Seçim | Gerekçe |
|---|---|---|
| Nicemleme | Ağırlık 4-bit, KV önbelleği 8-bit | Bellekten okunan hacmi yaklaşık dörtte bire düşürür; kısıtlı JSON üretiminde kalite kaybı ihmal edilebilir |
| İş parçacığı | Fiziksel çekirdek sayısı kadar, eşzamanlı çoklu iş parçacığı kapalı | Bant genişliğine doygun iş yükünde mantıksal çekirdek fayda getirmez, gecikme varyansını artırır |
| NUMA | Soket başına bir çıkarım işlemi, bellek yerelliği sabitlenmiş | Soketler arası bellek erişimi üretim hızını yarıya kadar düşürür |
| Bağlam | Sabit 8K tavan, tipik kullanım 2–3K | Bağlam uzunluğu CPU'da doğrudan gecikmedir; uzun bağlam bir maliyet kalemidir |
| Eşzamanlılık | Düğüm başına iki çıkarım yuvası, üstü kuyrukta | Üçüncü eşzamanlı istek, diğer ikisinin gecikmesini de kabul edilemez hâle getirir |
| Dilbilgisi kısıtı | Zorunlu — JSON şeması üretim sırasında dayatılır | Geçersiz çıktı yeniden deneme demektir; CPU'da yeniden deneme en pahalı hatadır |
| Ön-dolum önbelleği | Sistem istemi ve metrik sözlüğü için KV önbelleği kalıcı tutulur | Her isteğin sabit önekini yeniden işlemek istek başına 2–4 sn israftır |
| Toplu işleme | Sürekli toplu işleme açık, ancak yuva sayısıyla sınırlı | Boşta kalan bellek bant genişliğini ikinci isteğe verir; tek kullanıcıda etkisizdir |

> **Karar D-05.** Ana model **uzman karışımı mimaride ve 4-bit nicemlenmiş** olacaktır. Ölçülen üretim hızı saniyede 15 token'ın altında kalan yoğun modeller CPU dağıtımında aday listesine alınmaz. Bu ölçüm Faz 0'ın ilk çıktısıdır; kâğıt üzerindeki değerlere değil, kurumun kendi donanımında alınan sayıya güvenilir.

---

## 06 — Anlam sözleşmesi

Bu bölüm dokümanın kalbidir. Sistemin doğruluğu modelin zekâsından değil, **modele verilen anlam sözleşmesinin kalitesinden** gelir. "Ciro" kelimesinin tam olarak neye karşılık geldiği yazılı değilse, hiçbir model bunu doğru bilemez — yalnızca ikna edici biçimde tahmin eder ki bu daha kötüdür.

### 6.1 Dört metadata varlığı

| Varlık | İçerik | Sahibi | Faz 1 hedefi |
|---|---|---|---|
| M-1 | **Metrik kaydı.** Onaylı iş metriklerinin adı, tanımı, hesabı, birimi, tazelik ve sahibi | Veri yönetişimi + iş birimi | 25 metrik |
| M-2 | **Boyut ve hiyerarşi kataloğu.** Kırılım eksenleri, geçerli seviyeler, hangi metrikle birleşebildiği | Veri platformu | 12 boyut |
| M-3 | **Türkçe eşanlamlı sözlüğü.** Konuşma dilindeki karşılıklar, kısaltmalar, yaygın yanlış yazımlar | İş analisti + kullanım verisi | metrik başına 5–15 |
| M-4 | **Boyut değer indeksi.** Bölge, ürün grubu, kanal gibi düşük kardinaliteli değerlerin gerçek yazımları | Otomatik üretim, günlük tazeleme | 50 bin değere kadar |

### 6.2 Metrik kaydı — bir kayıt nasıl görünür

```yaml
metrik: net_ciro
  ad_tr:        "Net Ciro"
  esanlamlilar: [ciro, net satış, hasılat, satış geliri, gelir, turnover]
  tanim_tr:     "İade ve iskontolar düşülmüş, KDV hariç satış tutarı."
  hesap:        SUM(fact_satis.net_tutar)
  para_birimi:  TRY            # yabancı para satırları kur tablosu ile çevrilir
  granularite:  gun
  izinli_boyutlar:  [tarih, bolge, urun_grubu, kanal, musteri_segmenti]
  yasakli_boyutlar: [musteri_adi, personel]   # mahremiyet ve anlam kaymasi
  tazelik:      "T-1, her sabah 06:00"
  sahibi:       "Finans · Gelir Muhasebesi"
  onay:         { durum: onayli, tarih: 2026-06-14, surum: 3 }
  karistirilmamali:
    - brut_ciro       # iade dusulmemis, aradaki fark tipik %3-6
    - siparis_tutari  # henuz faturalasmamis
  ornek_sorular:
    - "bu ay ciromuz ne kadar"
    - "geçen yıla göre satışlar nasıl"
```

Buradaki `karistirilmamali` alanı, gerçek kurumsal hataların çoğunu tek başına önler: model "ciro" duyduğunda brüt mü net mi olduğunu tahmin etmez, kayıt hangisinin onaylı olduğunu söyler ve fark önemliyse kullanıcıya sorar.

### 6.3 Eşleştirme nasıl çalışır

1. **Sözlük eşleşmesi.** Sorudaki terimler eşanlamlı sözlüğünde birebir aranır. En hızlı ve en güvenilir yol; kapsanan sorularda model devreye bile girmez.
2. **Anlamsal arama.** Birebir eşleşme yoksa metrik tanımları ve örnek sorular üzerinde gömme araması yapılır. *(ilk 30 aday)*
3. **Yeniden sıralama.** Cross-encoder adayları soruya göre yeniden sıralar; ilk 8 aday bağlama girer. Fazlası modeli yanıltır, azı kapsam kaybettirir.
4. **Belirsizlik kontrolü.** İlk iki adayın skoru birbirine yakınsa (eşik: %15 fark altı) model seçmez — kullanıcıya iki seçenek sunulur. *("Tahsilat performansı" örneği)*

> **Karar D-06.** Metrik kaydı **tek doğruluk kaynağıdır** ve sürüm kontrolü altında, onay akışıyla yönetilir. Kayıtta olmayan bir metrik sorgulanamaz; asistan bunu bir eksiklik olarak değil, tasarım olarak bildirir: *"Bu metrik onaylı tanım listesinde yok."* Yeni metrik talebi, veri yönetişimi kuyruğuna düşen izlenebilir bir taleptir.

### 6.4 Yönetişim yükü — açıkça söylenmesi gereken

Metrik kaydını kurmak ve canlı tutmak **sürekli bir iştir, tek seferlik bir görev değildir.** Faz 1 için 25 metriğin tanımlanması, iş birimlerinden onay alınması ve doğrulanması gerçekçi olarak 4–6 hafta ve yaklaşık 0,5 tam zamanlı kişi demektir. Üretim döneminde metrik başına yılda 1–2 saatlik bakım (tanım değişikliği, kaynak değişimi, yeni eşanlamlı) beklenmelidir. Bu maliyet §16'daki ekip planına dahildir; gizlenmesi projenin gerçekçiliğini bozar.

---

## 07 — Sorgu üretim stratejisi

Doğal dilden veriye giden üç yol vardır ve seçim, projenin risk profilini baştan belirler. Kısaca: **modele ne kadar özgürlük verirseniz, doğruluğu o kadar denetlenemez hâle gelir.**

### 7.1 Üç seçenek

| Ölçüt | A · Kısıtlı sorgu spesifikasyonu | B · Semantik model üzerinden | C · Serbest SQL üretimi |
|---|---|---|---|
| Model çıktısı | Şema ile kısıtlı JSON | Ölçü + boyut seçimi | Ham SQL metni |
| Doğruluk (kapsam içi) | %85–92 | %88–94 | %55–70 |
| Yanlış ama makul görünen cevap | Düşük | Çok düşük | **Yüksek — en büyük risk** |
| Üretilen token | 200–400 | 150–300 | 400–900 |
| CPU maliyeti | Düşük | En düşük | 2–3 kat |
| Güvenlik yüzeyi | Derleyici kapatır | Model motoru kapatır | Ayrıştırıcı ile savunma gerekir |
| Kapsam esnekliği | Orta — kayıtla sınırlı | Dar — modelde ne varsa | Geniş |
| Ön koşul | Metrik kaydı (M-1) | Olgun semantik model (V-02) | Yok |
| Kurulum eforu | Orta | Düşük (model varsa) | Düşük |

> **Karar D-07 — hibrit, sıralı.** **Birincil yol A**, semantik model olgunsa **B tercih edilir** (ölçü tanımları zaten orada onaylıdır ve satır düzeyi güvenlik motorda uygulanır). **C üretime alınmaz.** Serbest SQL yalnızca iş analisti profilindeki kullanıcılara, "taslak" etiketiyle, sonucu asla otomatik yorumlanmadan sunulabilir — bir kolaylık aracı olarak, cevap kaynağı olarak değil.

### 7.2 Sorgu spesifikasyonu

Modelin ürettiği tek şey aşağıdaki yapıdır. Serbest metin alanı yoktur; her alanın değeri ya sabit listeden ya metrik kaydından gelir. Bu, doğrulamayı bir şema kontrolüne indirger.

```json
// "En çok büyüyen 5 ürün grubu hangileri?" sorusunun çıktısı
{
  "metrikler":  ["net_ciro"],
  "boyutlar":   ["urun_grubu"],
  "donem":      { "tip": "ceyrek", "deger": "2026-Q2" },
  "karsilastirma": { "tip": "onceki_yil_ayni_donem" },
  "filtreler":  [],
  "siralama":   { "olcut": "buyume_yuzde", "yon": "azalan" },
  "limit":      5,
  "guven":      0.83,
  "belirsizlikler": [
     "buyume tutar mi yuzde mi — yuzde varsayildi"
  ]
}
```

`guven` ve `belirsizlikler` alanları arayüzde doğrudan kullanılır: güven eşiğin altındaysa cevap yerine netleştirme sorusu gösterilir, belirsizlik varsa cevabın üstünde tek satırlık bir not olarak çıkar. Modelden kendi kesinliğini raporlamasını istemek mükemmel değildir, ama denetlenebilir bir sinyaldir ve §10'da kalibre edilir.

### 7.3 Derleyici ve doğrulayıcı

- **İzin listesi zorunlu.** Metrik, boyut ve filtre alanları yalnızca kayıtta tanımlı adlardan seçilebilir. Tanımsız ad, sorguyu derleme aşamasında düşürür.
- **Birleşim yolları önceden tanımlı.** Model tablo birleştirmez; hangi olgu tablosunun hangi boyutla nasıl birleşeceği şemadan bilinir.
- **Zorunlu sınırlar.** Her sorguya satır limiti, sorgu zaman aşımı (varsayılan 30 sn) ve tarama maliyeti tavanı eklenir.
- **Salt okunur oturum.** Bağlantı kullanıcısının yazma yetkisi yoktur; ayrıca üretilen ifade türü `SELECT` ile sınırlıdır.
- **Tek geri bildirim turu.** Doğrulama başarısızsa hata mesajı modele bir kez verilir. İkinci başarısızlıkta cevap üretilmez, kullanıcıya soruyu daraltması önerilir — sonsuz deneme CPU'yu tüketir.

### 7.4 Şablon kütüphanesi ve önbellek

Yönetici soruları büyük ölçüde tekrar eder (V-05). Bu, hızlandırıcısız bir ortamda avantaja çevrilir:

| Katman | Neyi saklar | Geçerlilik | Beklenen isabet |
|---|---|---|---|
| Tam eşleşme önbelleği | Normalize soru metni → cevap | Veri tazelenene kadar | %15–25 |
| Spesifikasyon önbelleği | Soru gömmesi → sorgu spesifikasyonu | Metrik kaydı sürümü değişene kadar | %20–30 |
| Şablon eşleşmesi | Parametreli kalıplar (metrik + dönem + kırılım) | Kalıcı | %25–35 |
| Sonuç önbelleği | Sorgu imzası + yetki bağlamı → sonuç kümesi | Tazeleme takvimi | %30–40 |

> Önbellek anahtarları **her zaman** kullanıcının yetki bağlamını içerir. Yetkiden bağımsız önbellek, doğrudan bir yetki aşımı açığıdır.

Toplamda soruların yaklaşık yarısının modele hiç uğramadan ya da yalnızca yorum aşamasında uğrayarak cevaplanması hedeflenir. Bu, tek düğümlü bir CPU kurulumunun 145 kullanıcıyı taşıyabilmesinin başlıca nedenidir.

---

## 08 — Ajan mimarisi

"Ajan" burada özerk bir varlık değil, **sınırları çizilmiş bir durum makinesidir.** Serbestçe düşünen, kendi kendine araç zinciri kuran bir tasarım; hızlandırıcısız ortamda hem gecikme hem denetlenebilirlik açısından karşılanamaz.

### 8.1 Durumlar ve geçişler

```
  ANLA ──► ESLESTIR ──► PLANLA ──► DOGRULA ──► CALISTIR ──► YORUMLA ──► SUN
    │           │           │           │            │
    │           │           │           └─(1 kez)────┘   tek düzeltme turu
    │           │           └──────► NETLESTIR ──► (kullaniciya soru)
    │           └──────────────────► KAPSAM_DISI ──► (gerekceli ret)
    └──────────────────────────────► YETKISIZ ──► (ret + denetim kaydi)

  Sert sınırlar: en fazla 6 durum geçişi · en fazla 2 sorgu çalıştırma
  · toplam 45 sn bütçe · aşılırsa kısmi sonuç + açıklama ile sonlandır
```

### 8.2 Ajanın araçları

| Araç | Ne yapar | Yan etki | Çağrı sınırı |
|---|---|---|---|
| `metrik_ara` | Anlamsal arama ile aday metrik ve boyutları döner | Yok | 3 |
| `tanim_getir` | Bir metriğin onaylı tanımını ve sahibini döner | Yok | 5 |
| `boyut_degeri_ara` | "marmara" gibi bir ifadeyi geçerli boyut değerine eşler | Yok | 5 |
| `sorgu_calistir` | Doğrulanmış spesifikasyonu derleyip çalıştırır | Okuma · denetlenir | 2 |
| `tazelik_sor` | İlgili tablonun son yüklenme zamanını döner | Yok | 2 |
| `netlestirme_sor` | Kullanıcıya seçenekli soru sorar ve döngüyü duraklatır | Kullanıcıya görünür | 1 |

> Araç listesi kapalıdır. Yazan, gönderen, dışarı çağrı yapan hiçbir araç yoktur; bu, §09'daki sızıntı savunmasının ilk halkasıdır.

### 8.3 Tek ajan mı, çok ajan mı

Yaygın eğilim her adıma bir uzman ajan koymaktır. Hızlandırıcısız bir ortamda bu **doğrudan yanlış karardır:** her ajan devri yeni bir ön-dolum ve yeni bir üretim turu demektir; beş ajanlı bir tasarım aynı cevabı 4–6 kat gecikmeyle üretir. Bu spesifikasyon **tek akıl yürütücü + deterministik yardımcılar** modelini benimser: ne kadar iş kodla yapılabiliyorsa modele verilmez.

| | İçerik |
|---|---|
| **Modele bırakılan** | Niyet çıkarımı, terim eşleştirmede belirsizlik çözümü, sorgu spesifikasyonu üretimi, sonucun 2–4 cümlelik iş diliyle yorumu |
| **Koda bırakılan** | Dönem çözümleme ("geçen çeyrek" → tarih aralığı), birim ve para birimi çevrimi, yüzde ve büyüme hesapları, sıralama, biçimlendirme, yetki kontrolü, önbellek |
| **Asla modele bırakılmayan** | Aritmetik, yetki kararı, veri tazeliği beyanı, metrik tanımının kendisi, kaynak sistem seçimi |

### 8.4 Diyalog belleği

Takip soruları ("aynısını bölge kırılımıyla göster") tam metin geçmişiyle değil, **son sorgu spesifikasyonunun kendisiyle** taşınır. Bellekte tutulan şey konuşma değil, yapıdır: son spesifikasyon, son sonuç özeti (en fazla 20 satır) ve çözülmüş varlıklar. Bu sayede bağlam uzunluğu diyalog boyunca sabit kalır — CPU'da büyüyen bağlam, büyüyen gecikme demektir. Oturum belleği 30 dakika hareketsizlikte düşer ve şifreli olarak saklanır.

---

## 09 — Güvenlik ve yetkilendirme

Bu projenin varlık nedeni verinin kurumdan çıkmamasıdır. Dolayısıyla güvenlik bir ek özellik değil, **mimarinin kendisidir.** Aşağıdaki savunma katmanları birbirinin yedeğidir; herhangi birinin tek başına yeterli olduğu varsayılmaz.

### 9.1 Tehdit modeli

| Kod | Tehdit | Savunma | Artık risk |
|---|---|---|---|
| T-01 | Verinin kurum dışına çıkması | Çıkış trafiğinde varsayılan-ret; model ağırlıkları iç kayıt defterinden; telemetri kapalı; konteynerlerde dış DNS yok | Çok düşük |
| T-02 | Kullanıcının yetkisi olmayan veriyi görmesi | Yetki veri katmanında (satır düzeyi güvenlik) uygulanır; asistan ayrı bir yetki kaynağı tutmaz; önbellek anahtarı yetki bağlamını içerir | Düşük |
| T-03 | İstem enjeksiyonu ile sınırların aşılması | Model yalnızca kapalı araç listesine erişir; çıktı şema ile kısıtlıdır; yetki kararı modelin erişemediği katmandadır | Düşük–orta |
| T-04 | Metadata üzerinden bilgi sızması | Metrik kaydı ve boyut değer indeksi de yetkiye tabidir; kullanıcı görmeye yetkili olmadığı metriğin varlığını bile öğrenmez | Orta |
| T-05 | Toplulaştırma üzerinden birey çıkarımı | Asgari hücre büyüklüğü kuralı (n < 5 ise sonuç maskelenir); kişisel boyutlar metrik kaydında yasaklı listede | Orta |
| T-06 | Kaynak tüketimiyle hizmet engelleme | Kullanıcı başına hız sınırı; sorgu maliyet tavanı; çıkarım kuyruğunda adil paylaşım | Düşük |
| T-07 | Model ağırlığının veya istem şablonunun kurcalanması | Ağırlık dosyalarında karma doğrulaması; istemler sürüm kontrolünde ve imzalı; üretime dağıtım onay akışıyla | Düşük |
| T-08 | Yanlış cevabın doğru sanılması | Her cevapta kaynak, tanım ve sorgu görünür; güven eşiği altında cevap verilmez; §10 sürekli ölçüm | **Orta — kalıcı** |

> **Kalan en büyük risk T-08'dir.** Teknik sızıntı riskleri mimariyle kapatılabilir. Kapatılamayan risk, sistemin *ikna edici biçimde yanlış* bir cevap vermesi ve bu cevaba dayanarak karar alınmasıdır. Bunun panzehiri daha büyük model değil, §10'daki ölçüm disiplini, §11'deki şeffaf sunum ve dar kapsamdır.

### 9.2 Yetkilendirme mimarisi

- **Tek yetki kaynağı.** Asistan kendi yetki tablosunu tutmaz. Kullanıcının kimliği veri katmanına taşınır; hangi satırı göreceğine veri ambarı ya da semantik model karar verir. Böylece BI araçlarıyla asistan arasında yetki farkı oluşamaz.
- **Kimliğe bürünme değil, kimlik taşıma.** Bağlantı mümkünse kullanıcının kendi kimliğiyle açılır; teknik olarak mümkün değilse hizmet hesabı + doğrulanmış yetki bağlamı kullanılır ve bu bağlam denetim kaydına yazılır.
- **Metadata da yetkilidir.** Metrik kaydı ve boyut değerleri kullanıcı rolüne göre filtrelenir; aksi hâlde "İK maaş metriği" adının varlığı bile bir bilgi sızıntısıdır (T-04).
- **Kolon düzeyi maskeleme.** Kişisel veri içeren kolonlar asistan yoluyla hiçbir koşulda ham gelmez; yalnızca toplulaştırılmış biçimde ve asgari hücre kuralıyla.
- **Önbellek yetki duyarlı.** Anahtar = sorgu imzası + yetki bağlamı özeti. Bu kural ihlal edilirse önbellek doğrudan bir açığa dönüşür.

### 9.3 Ağ ve dağıtım izolasyonu

```
Bölge               Giriş                          Çıkış
kullanici_agi       —                              → uygulama (443, SSO)
uygulama_bolgesi    kullanici_agi (443)            → zeka_bolgesi, veri_bolgesi
zeka_bolgesi        uygulama_bolgesi (dahili)      YOK — internet erişimi kapalı
veri_bolgesi        uygulama_bolgesi (salt okunur) YOK
yonetim_bolgesi     yonetici_atlama_sunucusu       → ic_kayit_defteri

# Model ağırlıkları ve kütüphaneler dış ağdan indirilmez.
# Güncelleme yolu: onaylı paket → iç kayıt defteri → imza doğrulama → dağıtım.
```

### 9.4 KVKK ve denetlenebilirlik

| Gereklilik | Uygulama |
|---|---|
| Amaç sınırlaması | Sistem yalnızca onaylı metrik kapsamında çalışır; kapsam genişlemesi yönetişim onayına tabidir |
| Veri minimizasyonu | Modele ham satır gitmez; yalnızca toplulaştırılmış sonuç ve metadata |
| Denetim kaydı | Soru metni, kullanıcı, çözümlenen metrikler, üretilen sorgu, dönen satır sayısı, süre, sonuç durumu — değiştirilemez depoda |
| Saklama | Denetim kaydı 24 ay; soru metinleri 12 ay sonra kimliksizleştirilir; oturum belleği 30 dakika |
| Aydınlatma | İlk girişte kullanım bildirimi; soruların kalite iyileştirme için saklandığı açıkça belirtilir |
| Erişim talebi | Kullanıcı kendi soru geçmişini görebilir ve silinmesini talep edebilir |

---

## 10 — Doğruluk ve değerlendirme

Ölçülmeyen bir asistan, güvenilmeyen bir asistandır. Bu bölüm projenin **çıkış kriteri altyapısıdır** — Faz 1'in başarılı sayılıp sayılmayacağına buradaki sayılar karar verir, kanaat değil.

### 10.1 Altın soru kümesi

Değerlendirmenin temeli, iş birimleriyle birlikte hazırlanan ve **beklenen sonucu önceden bilinen** soru kümesidir. Faz 1 için 150 soru hedeflenir:

| Sınıf | Adet | Doğru sayılma ölçütü |
|---|---|---|
| Basit tek metrik | 40 | Sonuç kümesi referansla birebir eşit |
| Kırılımlı / sıralamalı | 35 | Sonuç kümesi ve sıra birebir eşit |
| Dönem karşılaştırmalı | 25 | Değerler ve dönem sınırları doğru |
| Takip sorusu (bağlamlı) | 15 | Önceki spesifikasyondan doğru türetme |
| Muğlak — netleştirme beklenen | 15 | Cevap değil, doğru soru sorması |
| Kapsam dışı — ret beklenen | 10 | Net ret; uydurma yok |
| Yetkisiz — ret beklenen | 10 | Ret + denetim kaydı; veri sızıntısı yok |

> Kümenin üçte biri sistemin **cevap vermemesi gereken** sorulardan oluşur. Bu oran bilinçlidir: bu projede en pahalı hata yanlış cevaptır.

### 10.2 Ölçütler

| Ölçüt | Tanım | Faz 1 eşiği | 12. ay hedefi |
|---|---|---|---|
| Yürütme doğruluğu | Üretilen sorgunun sonucu referans sonuçla aynı | ≥ %80 | ≥ %90 |
| Doğru reddetme | Cevaplanmaması gereken soruyu reddetme oranı | ≥ %90 | ≥ %95 |
| Yanlış reddetme | Cevaplanabilir soruyu gereksiz reddetme | ≤ %15 | ≤ %8 |
| Metrik eşleştirme isabeti | Doğru metriğin ilk sırada seçilmesi | ≥ %88 | ≥ %94 |
| Netleştirme yerindeliği | Muğlak soruda soru sorma oranı | ≥ %75 | ≥ %85 |
| Güven kalibrasyonu | Yüksek güvenli cevapların gerçek doğruluğu | ≥ %92 | ≥ %96 |
| p95 uçtan uca süre | Sorudan cevaba, sorgu süresi dahil | ≤ 25 sn | ≤ 20 sn |

> **Karar D-10 — çıkış kriteri.** Faz 1'den Faz 2'ye geçiş, **yürütme doğruluğu %80 ve doğru reddetme %90** eşiklerinin altın soru kümesinde sağlanmasına bağlıdır. Sağlanmazsa donanım yatırımı yapılmaz; eksik metrik tanımları tamamlanır ve ölçüm tekrarlanır. Bu kural, projeyi kurtarılamaz bir yatırıma dönüşmekten koruyan tek mekanizmadır.

### 10.3 Sürekli değerlendirme hattı

1. **Gece koşusu.** Altın küme her gece tam olarak çalıştırılır; sonuç panosu sabah hazırdır. *(~150 soru · ~40 dk)*
2. **Regresyon kapısı.** İstem, metrik kaydı veya model sürümü değişikliği, doğruluğu 2 puandan fazla düşürüyorsa üretime çıkamaz.
3. **Canlı örnekleme.** Üretimdeki cevapların haftalık %2'si iş analisti tarafından körlemesine puanlanır; altın kümenin gerçeği yansıtıp yansıtmadığı böyle denetlenir.
4. **Geri bildirim döngüsü.** Kullanıcının "yanlış" işareti koyduğu her cevap incelenir; kök neden metrik tanımı, eşanlamlı eksikliği veya model hatası olarak sınıflanır ve ilgili katmana yazılır.
5. **Küme büyütme.** Gerçek kullanımdan gelen yeni soru kalıpları aylık olarak altın kümeye eklenir; küme canlı bir varlıktır, sabit bir sınav değil.

### 10.4 Ölçüm dürüstlüğü

Altın kümeyi hazırlayan ekip ile istemleri ayarlayan ekip aynı kişiler olmamalıdır; aksi hâlde küme farkında olmadan sisteme göre şekillenir ve ölçüm anlamını yitirir. Kümenin **%20'si kilitli tutulur** — geliştirme sırasında hiç görülmez, yalnızca faz geçiş kararlarında açılır.

---

## 11 — Kullanıcı deneyimi

Yöneticinin sisteme güveni ilk beş kullanımda kurulur ya da kalıcı olarak kaybedilir. Tasarımın tek amacı vardır: **cevabın nereden geldiğini görünür kılmak** ve emin olunmayan yerde emin görünmemek.

### 11.1 Bir cevabın anatomisi

```
┌─────────────────────────────────────────────────────────────┐
│ 2026 Q2 net ciro: 1.284,6 mn TL              ▲ %12,4 (YoY)  │
│                                                             │
│ [ tablo / grafik ]                                          │
│                                                             │
│ Geçen yılın aynı çeyreğine göre %12,4 artış var. Artışın    │
│ en büyük kısmı Marmara ve Kurumsal Satış kanalından geldi.  │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│ Metrik   Net Ciro · onaylı v3 · Finans        [tanımı gör]  │
│ Filtre   2026-04-01 → 2026-06-30 · tüm bölgeler             │
│ Veri     27.08.2026 06:12 itibarıyla (T-1)                  │
│ Sorgu    [üretilen SQL'i gör]           Süre 9,4 sn         │
│                                                             │
│ [ Bölge kırılımı ]  [ Aylık trend ]  [ Excel ]      👍 👎    │
└─────────────────────────────────────────────────────────────┘
```

Künye satırları isteğe bağlı bir "detay" bölümünde saklanmaz; **her zaman görünürdür.** Bunun nedeni şudur: cevabın kaynağını görmek zorunda kalan kullanıcı, zamanla sistemin sınırlarını da öğrenir ve ona doğru soruları sormaya başlar.

### 11.2 Güven durumlarına göre davranış

| Durum | Arayüz davranışı | Dil |
|---|---|---|
| Yüksek güven | Cevap doğrudan, künye ile | Kesin: "Q2 net ciro 1.284,6 mn TL." |
| Orta güven | Cevap + üstte tek satır varsayım notu | "Büyümeyi yüzde olarak yorumladım; tutar isterseniz değiştirebilirim." |
| Belirsiz | Cevap yok; en fazla 3 seçenekli netleştirme | "Tahsilat performansı için iki onaylı metrik var: … Hangisi?" |
| Kapsam dışı | Ret + neden + varsa alternatif | "Rakip pazar payı veri ambarında yok. Kendi pazar payı tahminimizi gösterebilirim." |
| Yetkisiz | Ret; verinin varlığı ima edilmez | "Bu bilgiye erişim yetkiniz bulunmuyor." |
| Zaman aşımı | Kısmi sonuç veya daraltma önerisi | "Sorgu 30 sn'yi aştı. Dönemi daraltmayı deneyelim mi?" |

### 11.3 Gecikmenin yönetimi

8–20 saniyelik bir cevap süresi, ne yaptığı görünüyorsa kabul edilebilir; boş bir bekleme göstergesiyse kabul edilemez. Arayüz her adımı canlı gösterir: *"Metrik eşleştiriliyor → Sorgu hazırlanıyor → Veri ambarında çalışıyor (6 sn) → Yorumlanıyor."* Sayısal sonuç, yorum metni beklenmeden gösterilir; yorum akış hâlinde üstüne yazılır. Böylece kullanıcı asıl cevabı ilk 8 saniyede görür.

### 11.4 Diğer ilkeler

- **Grafik türü kod seçer, model değil.** Zaman serisi → çizgi, kategori karşılaştırma → yatay çubuk, tek değer → büyük sayı + değişim.
- **Excel'e aktarım her cevapta vardır.** Yönetici çoğu zaman sayıyı kendi sunumuna taşır; bunu engellemek kullanımı düşürür.
- **Örnek sorular boş ekranda gösterilir.** Kullanıcı ne sorabileceğini bilmiyorsa sistemin kapsamı görünmez kalır.
- **Başparmak geri bildirimi zorunlu bir üründür.** §10.3'teki döngünün ana girdisidir; "yanlış" işaretine tek satırlık neden alanı eşlik eder.
- **Mobil, salt görüntüleme.** Üst yönetimin ana kullanım aracı telefondur; kırılım ve dışa aktarma masaüstünde kalabilir, cevap ve künye kalamaz.
- **Erişilebilirlik.** Renk tek başına anlam taşımaz; artış/azalış işaretle de belirtilir. Klavye ile tam gezinme ve ekran okuyucu uyumu zorunludur.

---

## 12 — Platform ve işletim

Kapalı bir ortamda işletimin zor kısmı çalıştırmak değil, **güncellemektir.** İnternet erişimi olmayan bir sistemde her kütüphane, her model ağırlığı ve her yama elle taşınan bir tedarik zinciri kalemidir. Bu bölüm o zinciri tanımlar.

### 12.1 Dağıtım topolojisi

| Bileşen | Örnek sayısı | Yerleşim | Durum |
|---|---|---|---|
| Arayüz + API | 2 | Uygulama bölgesi, yük dengeleyici arkasında | Durumsuz |
| Orkestrasyon servisi | 2 | Uygulama bölgesi | Durumsuz (oturum harici depoda) |
| Çıkarım düğümü (ana model) | 2 | Zekâ bölgesi, ayrılmış donanım | Durumsuz, ağırlıklar yerel diskte |
| Yardımcı model servisi | 2 | Zekâ bölgesi, çıkarım düğümüyle aynı makine olabilir | Durumsuz |
| Vektör indeksi | 2 | Uygulama bölgesi | Durumlu — metadata gömmeleri |
| Metadata deposu (metrik kaydı) | 1 + yedek | Uygulama bölgesi, ilişkisel veritabanı | Durumlu — yedeklenir |
| Önbellek | 2 | Uygulama bölgesi | Geçici, kaybı tolere edilir |
| Denetim kaydı deposu | 1 küme | Yönetim bölgesi | Değiştirilemez, 24 ay saklama |

> Vektör indeksinde ve metadata deposunda tutulan hiçbir şey iş verisi değildir; yalnızca tanım ve isimlerdir. Yedekleme sınıflandırması buna göre yapılır.

### 12.2 Hizmet seviyesi hedefleri

| Gösterge | Hedef | Ölçüm | İhlalde |
|---|---|---|---|
| Kullanılabilirlik (mesai saatleri) | %99,5 | Sağlık ucu + sentetik soru, 1 dk | Çağrı zinciri |
| p50 cevap süresi | ≤ 10 sn | Uçtan uca izleme | Kapasite incelemesi |
| p95 cevap süresi | ≤ 25 sn | Uçtan uca izleme | Kuyruk ayarı / düğüm ekleme |
| Kuyruk bekleme (tepe saat) | ≤ 8 sn | Kuyruk derinliği ölçümü | Eşzamanlılık sınırı gözden geçirilir |
| Doğruluk (gece koşusu) | Eşik üstü | §10 hattı | Sürüm geri alınır |
| Sıfır dış bağlantı | Mutlak | Ağ akış kaydı denetimi, haftalık | Güvenlik olayı |

### 12.3 İzlenecek ölçümler

- **Model katmanı:** Token/sn üretim hızı, ilk token gecikmesi, ön-dolum süresi, kuyruk derinliği, yuva doluluğu, KV önbellek isabeti, geçersiz JSON oranı.
- **Anlam katmanı:** Metrik eşleştirme skoru dağılımı, netleştirme oranı, eşleşmeyen terimler (yeni eşanlamlı adayları), kayıt sürüm değişimleri.
- **Yürütme katmanı:** Doğrulama başarısızlık oranı ve nedenleri, sorgu süresi dağılımı, zaman aşımı sayısı, önbellek isabet oranı, dönen satır sayısı.
- **Ürün katmanı:** Günlük aktif kullanıcı, kullanıcı başına soru, tekrar kullanım oranı, başparmak geri bildirimi, terk edilen oturum, en sık sorular.

Bu ölçümlerin hiçbiri kurum dışına gönderilmez; izleme yığını da kapalı ortamda çalışır (K-01).

### 12.4 Değişiklik ve model yaşam döngüsü

1. **Aday getirme.** Model ağırlığı ya da kütüphane, onaylı bir kanaldan indirilip karma değeri doğrulanarak iç kayıt defterine alınır. *(hukuk + güvenlik onayı)*
2. **Yalıtılmış ölçüm.** Aday, üretim dışı düğümde altın soru kümesiyle koşturulur; doğruluk ve token/sn birlikte raporlanır.
3. **Karşılaştırmalı karar.** Yeni model yalnızca doğruluk *ve* hız birlikte iyileşiyorsa geçer; tek başına doğruluk artışı, hız kaybını haklı çıkarmaz.
4. **Gölge çalıştırma.** Bir hafta boyunca gerçek sorular her iki modele gider, yalnızca eski modelin cevabı gösterilir; farklar incelenir.
5. **Kademeli geçiş.** %10 → %50 → %100 kullanıcı. Her adımda geri alma hazır; istem şablonları model sürümüne bağlı olarak sürümlenir.

> **İstemler de koddur.** Sistem istemleri, metrik kaydı ve şema tanımları sürüm kontrolünde tutulur, gözden geçirmeden geçer ve üretime onayla çıkar. "Hızlıca istemi düzelttim" diye yapılan doğrudan üretim değişikliği, bu sistemde bir üretim kodu değişikliğiyle aynı risktedir ve aynı disiplinle yönetilir.

### 12.5 Yedekleme ve süreklilik

- **Kritik durum azdır:** metrik kaydı, şablon kütüphanesi, denetim kaydı. Günlük yedek, aylık geri yükleme tatbikatı.
- **Model ağırlıkları** iç kayıt defterinde durur; düğüm kaybında yeniden dağıtım 30–60 dakikadır, veri kaybı yoktur.
- **Vektör indeksi yeniden üretilebilir** — metadata deposundan birkaç dakikada baştan kurulur, yedeklenmesi zorunlu değildir.
- **Kısmi hizmet modu:** Ana model düğümü düşerse sistem tamamen kapanmaz; şablon ve önbellek isabetli sorular cevaplanmaya devam eder, diğerleri "geçici olarak yanıtlanamıyor" der.
- **Felaket senaryosu:** Asistan kritiklik sınıfı ikinci derecedir; BI araçları birincil kanal olarak ayakta kalır. Kurtarma hedefi 4 saat, veri kaybı toleransı 24 saattir.

---

## 13 — Donanım ve kapasite

Hızlandırıcısız bir kurulumda donanım listesi tek bir soruya indirgenir: **saniyede kaç gigabayt okuyabiliyoruz?** Çekirdek sayısı bir noktadan sonra fayda getirmez; bellek kanalı sayısı ve bellek hızı getirir.

### 13.1 Çıkarım düğümü özellikleri

| Bileşen | Asgari | Önerilen | Neden |
|---|---|---|---|
| İşlemci | 2 soket, soket başına 32 çekirdek, AVX-512 | 2 soket, 48–64 çekirdek, matris uzantıları (AMX sınıfı) | Matris uzantıları ön-dolumu 2–3 kat hızlandırır; üretim hızını değil |
| Bellek kanalı | 8 kanal / soket | 12 kanal / soket | **En kritik kalem.** Doğrudan token/sn belirler |
| Bellek | 256 GB DDR5-4800 | 512 GB DDR5-5600+ | Model + KV önbelleği + ön-dolum önbelleği + işletim payı |
| Depolama | 1 TB NVMe | 2 TB NVMe (okuma 3 GB/sn+) | Ağırlık yükleme süresi; çalışma anında disk kullanılmaz |
| Ağ | 10 GbE | 25 GbE | Veri ambarı sonuç transferi; darboğaz değil |
| Hızlandırıcı | Yok — K-02 gereği | Yok | Mimari bu kısıta göre kurulmuştur |

> **Bellek yerleşimi — 512 GB'lık bir düğümde.** Model ağırlıkları ~65 GB · KV önbelleği (2 yuva × 8K bağlam) ~6 GB · kalıcı ön-dolum önbelleği ~4 GB · yardımcı modeller ~4 GB · işletim sistemi ve sayfa önbelleği ~20 GB. Kalan alan ikinci bir model sürümünü *aynı anda* bellekte tutmaya ayrılır — gölge çalıştırma (§12.4) bunu gerektirir.

### 13.2 Kapasite hesabı

```
# Tepe saat varsayımı (§2.1): 6 eşzamanlı aktif soru

Önbellek + şablon isabeti           ~ %50   ->  3 soru modele gitmez
Modele giden eşzamanlı soru                     3
Düğüm başına çıkarım yuvası                     2
Gerekli düğüm (tepe)                            2 düğüm

# Soru başına düğüm meşguliyeti
ön-dolum (2.500 token)              ~ 2,5 sn
üretim (300 token @ 30 t/sn)        ~ 10 sn
yorum üretimi (120 token)           ~ 4 sn
                                    = ~16 sn model zamanı
(veri ambarı sorgu süresi bu sürenin dışındadır ve paraleldir)

Düğüm başına saatlik kapasite:  2 yuva x 3600 / 16   = ~450 soru/saat
İki düğüm, %50 önbellek ile:                         = ~1.800 soru/saat
Beklenen tepe yük (145 kullanıcı):                   ~ 300 soru/saat
```

Yani iki düğüm, beklenen yükün yaklaşık altı katını taşır. Bu fazlalık israf değil, **bilinçli bir tampondur:** ölçülen token/sn kâğıttaki değerin yarısı çıkarsa, önbellek isabeti %50 yerine %25 kalırsa veya kullanım beklenenin iki katına çıkarsa sistem hâlâ ayaktadır. CPU çıkarımında gecikme, doygunluğa yaklaşıldığında doğrusal değil, ani biçimde bozulur.

### 13.3 Üç kurulum seçeneği

| | S · Kanıtlama | M · Üretim (öneri) | L · Yaygın kullanım |
|---|---|---|---|
| Çıkarım düğümü | 1 (mevcut sunucu) | 2 ayrılmış | 4 ayrılmış |
| Düğüm başına bellek | 256 GB | 512 GB | 512 GB |
| Eşzamanlı kullanıcı | 1–2 | 4–8 | 10–16 |
| Kapsanan kullanıcı | 10–15 pilot | 150 | 400+ |
| Yüksek erişilebilirlik | Yok | Var | Var |
| Ne zaman | Faz 0–1 | Faz 2–3 | Faz 4, talep kanıtlanınca |

> Faz 1, mevcut donanımda yapılabilir. Ayrılmış donanım yatırımı §10'daki çıkış kriteri sağlandıktan sonra tetiklenir; sıralama bilinçlidir.

### 13.4 Ölçekleme davranışı

- **Yatay ölçekleme doğrusaldır** — çıkarım durumsuzdur, düğüm eklemek eşzamanlılığı doğrudan artırır.
- **Dikey ölçekleme sınırlıdır** — daha fazla çekirdek, bellek bant genişliği artmadan token/sn'yi artırmaz. Yükseltme yapılacaksa bellek kanalı ve hızı hedeflenir.
- **Önbellek en ucuz kapasitedir.** İsabet oranını %35'ten %55'e çıkarmak, bir düğüm eklemekle aynı etkiyi yapar ve maliyeti neredeyse sıfırdır. İlk optimizasyon adresi burasıdır.
- **Bağlam uzunluğu bir kapasite kalemidir.** 8K yerine 32K bağlam, ön-dolum süresini dört katına çıkarır ve düğüm kapasitesini yarıya indirir. Uzun bağlam talebi geldiğinde bu maliyet konuşulmalıdır.

---

## 14 — Uçtan uca değerlendirme

Buraya kadarki bölümler sistemin *nasıl* kurulacağını anlattı. Bu bölüm *kurulmalı mı* sorusunu cevaplıyor: hangi boyutta güçlü, hangi boyutta zayıf, alternatiflere göre nerede duruyor ve hangi koşulda durdurulmalı.

### 14.1 Boyut boyut hüküm

| Boyut | Hüküm | Gerekçe |
|---|---|---|
| Veri mahremiyeti | **Güçlü** | Mimari olarak dışa çıkış yolu yok; bu tasarımın en sağlam yanı ve asıl gerekçesi |
| Teknik yapılabilirlik | **Yapılabilir** | Model sorgu yazdığı sürece CPU yeterli; hesap §05 ve §13'te açık |
| Kapsam içi doğruluk | **Yeterli** | %85–92 hedefi, onaylı metrik ve şablon disiplini ile ulaşılabilir |
| Kapsam genişliği | Sınırlı | Yalnızca kayıtlı metrikler. "Her şeyi soran asistan" değil — bilinçli olarak |
| Gecikme | Kabul edilebilir | 8–20 sn; şeffaf ilerleme göstergesiyle tolere edilir, hızlandırıcılı sistemlerin 3–5 katı |
| Eşzamanlılık | Dar | Düğüm başına 2 aktif üretim; önbellek olmadan 145 kullanıcı taşınmaz |
| Yönetişim yükü | **Yüksek** | Metrik kaydı sürekli emek ister; projenin gizli asıl maliyeti burada |
| Açık uçlu analiz | **Zayıf** | "Neden" soruları kırılım gösterir, nedensellik kurmaz; analistin yerini almaz |
| Değişime dayanıklılık | **Güçlü** | Model değiştirilebilir bir parça; yatırımın çoğu metadata'da ve modelden bağımsız |

### 14.2 Alternatiflerin dürüst karşılaştırması

| Seçenek | Artı | Eksi | Hüküm |
|---|---|---|---|
| **Bu tasarım** (CPU · şirket içi) | Sıfır veri çıkışı; mevcut donanımla başlanabilir; metadata yatırımı kalıcı ve taşınabilir | Dar kapsam; yavaş; yönetişim emeği yüksek | **Önerilen** |
| **Şirket içi + hızlandırıcı** | 5–10 kat hız; geniş bağlam; açık uçlu analize alan açar | Ciddi donanım yatırımı; K-02 ile çelişir; doğruluğu *artırmaz* — doğruluk metadata işidir | Faz 4'te yeniden değerlendir |
| **Bulut LLM servisi** | En yüksek model kalitesi; işletim yükü yok; en hızlı kurulum | K-01'i doğrudan ihlal eder; soru metinleri bile dışarı çıkar | **Elenmiştir** |
| **Hazır ticari NL-BI ürünü** | Kısa sürede çalışır; arayüz ve bakım satıcıda | Çoğu bulut bağımlı; şirket içi sürümler pahalı ve yine metrik tanımı ister; kurumun anlam katmanı satıcıya kilitlenir | Faz 0'da fiyatla karşılaştır |
| **Yapmamak — mevcut BI + analist** | Sıfır risk; bilinen süreç | Rapor talebi kuyruğu sürer; "basit soru" için analist zamanı harcanır | Gerçek karşılaştırma tabanı |

> **Dikkat edilmesi gereken karşılaştırma.** Bu sistemin başarısı "ChatGPT kadar iyi mi?" sorusuyla ölçülmemelidir. Doğru karşılaştırma şudur: **bir yöneticinin bu soruyu bugün nasıl cevapladığı.** Bugünkü yol çoğu kurumda analiste e-posta atmak ve yarım gün ile iki gün arasında beklemektir. 15 saniyede gelen, kaynağı görünür, kapsamı dar ama doğru bir cevap — bu tabana göre büyük bir kazançtır.

### 14.3 Risk kaydı

| Kod | Risk | Olasılık | Etki | Azaltma | Sahibi |
|---|---|---|---|---|---|
| R-01 | Metrik tanımları yok veya iş birimleri uzlaşamıyor | Yüksek | Kritik | Faz 1 kapsamını tek konu alanına daraltmak; tanım üretimini projenin birinci işi saymak | Veri yönetişimi |
| R-02 | Ölçülen token/sn beklenenin altında çıkıyor | Orta | Yüksek | Faz 0'da gerçek donanımda ölçüm; çıktı uzunluğunu kısaltma; şablon oranını artırma | Platform |
| R-03 | Türkçe anlama kalitesi yetersiz | Orta | Orta | Eşanlamlı sözlüğünü genişletmek; üç aday modeli Türkçe altın kümeyle karşılaştırmak | Yapay zekâ ekibi |
| R-04 | Kullanıcı ilk yanlış cevaptan sonra sistemi terk ediyor | Yüksek | Yüksek | Şeffaf künye; agresif reddetme politikası; pilot kullanıcılarla beklenti yönetimi | Ürün |
| R-05 | Kapsam kayması — "şuna da baksın" talepleri | Yüksek | Orta | §1.3 yazılı kapsam dışı listesi; her genişleme yönetişim onayı ve ölçüm gerektirir | Proje sahibi |
| R-06 | Kapalı ortamda kütüphane/yama tedariki tıkanıyor | Orta | Orta | İç kayıt defteri ve onaylı paket kanalı Faz 0'da kurulur, sonradan değil | Platform |
| R-07 | Anahtar kişiye bağımlılık | Orta | Orta | Metrik kaydı ve istemler sürüm kontrolünde; kurulum tamamen otomatik ve belgeli | Platform |
| R-08 | Denetim/uyum ekibi mimariyi yeterli bulmuyor | Düşük | Yüksek | CISO ve uyum birimini Faz 0'da masaya almak; §09'u tasarım onayı olarak imzalatmak | Güvenlik |

### 14.4 İnce ayar gerekli mi

Kısa cevap: **Faz 3'ten önce hayır.** Bu tür projelerde ince ayar çoğunlukla yanlış sorunun çözümüdür — hatalar genellikle modelin yeteneğinden değil, eksik metrik tanımından, eksik eşanlamlıdan veya belirsiz sorudan kaynaklanır. İnce ayar bunların hiçbirini düzeltmez, yalnızca maliyeti ve bağımlılığı artırır.

| Önce denenecek | Beklenen kazanç | Maliyet |
|---|---|---|
| Eşanlamlı sözlüğünü gerçek kullanımdan büyütmek | +5–10 puan | Düşük — sürekli |
| Örnek soru–spesifikasyon çiftlerini bağlama koymak | +4–8 puan | Düşük |
| Şablon kütüphanesini genişletmek | +3–6 puan ve hız | Orta |
| Daha iyi bir açık model sürümüne geçmek | +3–7 puan | Orta — §12.4 süreci |
| *Ancak bunlardan sonra:* göreve özel ince ayar | +2–5 puan | **Yüksek — veri, süreç, bakım** |

İnce ayar gündeme gelirse hedef modeli daha zeki yapmak değil, **küçük bir modeli spesifikasyon üretmede yeterli hâle getirmek** olmalıdır — yani kalite değil, hız kazancı. CPU ortamında asıl kazanç oradadır.

### 14.5 Bu proje nasıl başarısız olur

1. **Tanımsız metriklerle başlamak.** En yaygın ölüm nedeni. Metrik kaydı olmadan kurulan asistan, iş birimlerinin farklı "ciro" tanımlarını rastgele karıştırır ve ilk toplantıda çürütülür. Sıra bellidir: önce tanım, sonra asistan.
2. **Geniş vaatle başlamak.** "Her şeyi sorabilirsiniz" demek, sistemi kendi kapsamının dışında sınava sokar. Dar ve net vaat, ilk günden itibaren güven biriktirir.
3. **Model kovalamak.** Doğruluk düştüğünde çözümü daha büyük modelde aramak, CPU bütçesini tüketir ve sorunu çözmez. Hataların kök nedeni ölçülmeden model değiştirilmemelidir.
4. **Ölçmeden ilerlemek.** Altın soru kümesi olmadan "iyi çalışıyor gibi" hissiyle üretime çıkmak. İlk yanlış yönetici cevabı, projenin itibarını teknik olarak onarılamaz biçimde bitirir.
5. **Reddetmekten çekinmek.** Sistemi her soruya cevap verir hâle getirme baskısı gelir. Buna direnilmezse doğru reddetme oranı düşer ve sistem güvenilir olmaktan çıkar.
6. **Yönetişimi bütçelememek.** Metrik bakımına kimse atanmazsa kayıt altı ayda eskir, tanımlar kayar ve doğruluk sessizce düşer. Bu, en yavaş ve en sinsi başarısızlık biçimidir.

### 14.6 Durdurma kriterleri

Bir projeyi ne zaman durduracağını baştan yazmak, onu kurtarmanın en ucuz yoludur. Aşağıdaki koşullardan biri gerçekleşirse proje **genişletilmez;** ya kapsam daraltılır ya durdurulur:

- **D-1.** Faz 1 sonunda yürütme doğruluğu %70'in altındaysa ve kök neden analizi metrik tanımlarına işaret etmiyorsa — mimari varsayım yanlış demektir.
- **D-2.** Gerçek donanımda ölçülen üretim hızı 10 token/sn'nin altındaysa ve önbellek isabeti %30'a çıkarılamıyorsa — kullanıcı deneyimi eşiği aşılamaz.
- **D-3.** 12 hafta sonunda 25 metrik için iş birimlerinden onaylı tanım alınamadıysa — bu bir yönetişim tıkanıklığıdır, teknoloji ile çözülmez.
- **D-4.** Pilot sonunda haftalık aktif kullanıcı oranı pilot grubunun %30'unun altındaysa — talep varsayımı yanlıştır.
- **D-5.** Doğru reddetme oranı %85'in altında kalıcı hâle geldiyse — sistem güvenilmez veri üretiyor demektir; bu tek başına durdurma nedenidir.

> **Genel hüküm.** **Yapılabilir ve yapılmaya değer** — ancak bunun bir yapay zekâ projesi olduğu kadar bir *veri yönetişimi projesi* olduğu kabul edilmek şartıyla. Emeğin yaklaşık yarısı metrik tanımı, sözlük ve ölçüm altyapısına gidecektir; model ve altyapı işi kalan yarıdır. Bu gerçek baştan kabul edilirse proje büyük olasılıkla başarılı olur; "model kurup üstüne veri bağlayalım" beklentisiyle başlanırsa büyük olasılıkla başarısız olur.

---

## 15 — Yol haritası

Plan tek bir ilkeye göre kurulmuştur: **geri dönülemez harcamayı ölçümden sonraya bırakmak.** İlk üç ay mevcut donanımla, dar kapsamda ve tek amaçla yürür — varsayımların hangisinin doğru olduğunu öğrenmek.

| Faz | Süre | Kapsam | Ana çıktı | Çıkış kriteri |
|---|---|---|---|---|
| **Faz 0 · Keşif** | 4 hafta | Varsayım doğrulama; DWH ve semantik model incelemesi; donanımda gerçek token/sn ölçümü; 3 aday model kıyası; iç paket kanalının kurulması | Ölçüm raporu, model kararı, güncellenmiş mimari | V-01…V-05 doğrulandı; ölçülen hız ≥ 15 token/sn |
| **Faz 1 · Kanıtlama** | 8 hafta | Tek konu alanı (öneri: satış ve gelir); 25 onaylı metrik; 150 soruluk altın küme; uçtan uca zincirin çalışır hâli; 10–15 kişilik kapalı grup | Çalışan asistan + ölçüm panosu | **Doğruluk ≥ %80, doğru reddetme ≥ %90** (D-10) |
| **Faz 2 · Pilot** | 10 hafta | İkinci konu alanı; 60 metrik; yetki entegrasyonunun tam kurulumu; üretim donanımına geçiş; 40–50 kullanıcı | Üretime hazır sistem, işletim el kitabı | Haftalık aktif kullanıcı ≥ %50; p95 ≤ 25 sn; güvenlik onayı |
| **Faz 3 · Üretim** | 8 hafta | Tüm hedef kullanıcılara açılış; yüksek erişilebilirlik; Teams entegrasyonu; eğitim ve benimseme çalışması | Üretim hizmeti + hizmet seviyesi taahhüdü | SLO'lar 4 hafta üst üste tutuyor |
| **Faz 4 · Genişleme** | sürekli | Yeni konu alanları; zamanlanmış brifingler; anomali bildirimi; hızlandırıcı ihtiyacının yeniden değerlendirilmesi | Çeyreklik kapsam artışı | Her genişlemede doğruluk eşiği korunur |

> Toplam: kanıtlanmış bir üretim sistemine yaklaşık 7–8 ay. Faz 1 ve 2 arasındaki kapı, bu planın tek gerçek karar noktasıdır.

### 15.1 Faz 1 haftalık kırılımı

```
H1–H2  Metrik kaydı şeması + ilk 10 metriğin iş birimiyle tanımlanması
       Altın küme ilk 60 soru · veri ambarı okuma replikası hazır
H3–H4  Sorgu derleyici + doğrulayıcı · şema kısıtlı üretim çalışıyor
       Eşanlamlı sözlüğü v1 · gömme + yeniden sıralama hattı
H5–H6  Ajan durum makinesi · netleştirme ve ret akışları
       Arayüz v1 (künye dahil) · denetim kaydı yazımı
H7     Kalan 15 metrik · altın küme 150'ye tamamlanıyor · önbellek katmanı
H8     Kilitli %20 ile ölçüm · kapı kararı · Faz 2 kapsam tanımı

# H4 sonunda ara kontrol: uçtan uca tek soru cevaplanabiliyor olmalı.
# Bu tarih kayarsa Faz 1 kapsamı 25 metrikten 15'e indirilir, süre uzatılmaz.
```

> **Neden süre değil kapsam esnetilir.** Sabit süre + esnek kapsam, bu tür projelerde tek işleyen disiplindir. Süre uzatıldığında kapsam da büyür ve ölçüm hiç yapılmadan aylar geçer. Faz 1'in sekizinci haftasında elde ne varsa onunla ölçüm yapılır ve kapı kararı verilir.

---

## 16 — Ekip ve sorumluluklar

| Rol | Faz 0–1 | Faz 2–3 | Üretim | Sorumluluk |
|---|---|---|---|---|
| Ürün sahibi | 0,5 | 0,5 | 0,3 | Kapsam savunması, öncelik, kullanıcı ilişkisi, kapı kararlarının hazırlanması |
| Yapay zekâ / uygulama mühendisi | 2,0 | 2,0 | 1,0 | Ajan zinciri, istemler, derleyici, değerlendirme hattı |
| Veri mühendisi | 1,0 | 1,0 | 0,5 | Okuma replikası, metadata deposu, boyut değer indeksi, tazelik |
| Veri yönetişimi / iş analisti | 1,0 | 1,0 | 0,5 | **Metrik kaydı, altın küme, cevap denetimi** — projenin doğruluk sahibi |
| Platform / sistem mühendisi | 0,5 | 1,0 | 0,4 | Çıkarım düğümleri, konteyner platformu, izleme, paket kanalı |
| Arayüz geliştirici | 0,5 | 1,0 | 0,3 | Sohbet arayüzü, künye sunumu, mobil, erişilebilirlik |
| Güvenlik mühendisi | 0,3 | 0,5 | 0,2 | Tehdit modeli, ağ izolasyonu, yetki doğrulaması, denetim |
| **Toplam (TZE)** | **5,8** | **7,0** | **3,2** | |

> Veri yönetişimi rolü tam zamanlıdır ve pazarlık konusu değildir. Bu rol yarı zamanlıya düşürüldüğünde ilk kaybedilen şey doğruluktur; kaybedildiği de aylar sonra fark edilir.

### 16.1 Karar hakları

- **Metrik tanımı:** ilgili iş biriminin sahibi karar verir, veri yönetişimi kaydeder. Yapay zekâ ekibi tanım yazmaz.
- **Kapsam genişletme:** ürün sahibi önerir, yönetişim kurulu onaylar; ölçüm eşiği korunmak zorundadır.
- **Model değişikliği:** yapay zekâ ekibi önerir, §12.4 süreci karar verir; ölçüm olmadan değişiklik yapılmaz.
- **Yetki kuralları:** güvenlik ve veri sahipleri; asistan ekibinin bu konuda takdir yetkisi yoktur.
- **Faz kapıları:** CIO/CDO; girdi olarak §10 ölçüm raporu ve §14.6 durdurma kriterleri kullanılır.

---

## 17 — Gereksinim listesi

### 17.1 İşlevsel gereksinimler

| Kod | Gereksinim | Öncelik | Faz |
|---|---|---|---|
| F-01 | Kullanıcı Türkçe doğal dille soru sorabilir; İngilizce sorular da desteklenir | Zorunlu | 1 |
| F-02 | Sistem soruyu onaylı metrik ve boyutlara eşler, eşleşme başarısızsa açıkça bildirir | Zorunlu | 1 |
| F-03 | Model şema ile kısıtlanmış sorgu spesifikasyonu üretir; serbest SQL üretmez | Zorunlu | 1 |
| F-04 | Spesifikasyon deterministik derleyici ile SQL/DAX'a çevrilir ve doğrulanır | Zorunlu | 1 |
| F-05 | Her cevapta metrik tanımı, filtreler, veri tazelik zamanı ve üretilen sorgu gösterilir | Zorunlu | 1 |
| F-06 | Muğlak soruda en fazla 3 seçenekli netleştirme sorulur | Zorunlu | 1 |
| F-07 | Kapsam dışı ve yetkisiz sorular gerekçeli olarak reddedilir; tahmin üretilmez | Zorunlu | 1 |
| F-08 | Takip soruları önceki sorgu spesifikasyonu üzerinden bağlamla yanıtlanır | Zorunlu | 2 |
| F-09 | Sonuçlar tablo ve uygun grafik türüyle sunulur; grafik türünü kod seçer | Zorunlu | 2 |
| F-10 | Kullanıcı sonucu Excel/CSV olarak dışa aktarabilir | Önemli | 2 |
| F-11 | Kullanıcı cevabı olumlu/olumsuz işaretleyebilir ve kısa gerekçe girebilir | Zorunlu | 1 |
| F-12 | Yönetişim ekibi metrik kaydını arayüzden görüntüleyip sürümleyebilir | Önemli | 2 |
| F-13 | Tüm sorular ve cevaplar denetim kaydına yazılır ve sorgulanabilir | Zorunlu | 1 |
| F-14 | Kullanıcı kendi soru geçmişini görebilir ve silinmesini talep edebilir | Önemli | 3 |
| F-15 | Teams veya intranet üzerinden erişim | İsteğe bağlı | 3 |
| F-16 | Kaydedilmiş sorgunun zamanlanmış brifing olarak gönderilmesi | İsteğe bağlı | 4 |

### 17.2 İşlevsel olmayan gereksinimler

| Kod | Gereksinim | Ölçüt |
|---|---|---|
| NF-01 | Hiçbir veri, soru metni dahil, kurum ağı dışına çıkmaz | Haftalık ağ akış denetimi: sıfır dış bağlantı |
| NF-02 | Sistem hızlandırıcı olmadan çalışır | Üretim düğümlerinde hızlandırıcı yok |
| NF-03 | Uçtan uca cevap süresi | p50 ≤ 10 sn · p95 ≤ 25 sn |
| NF-04 | İlk geri bildirim (ilerleme veya ilk token) | ≤ 3 sn |
| NF-05 | Eşzamanlılık | Tepe saatte 6 aktif soru, kuyruk beklemesi ≤ 8 sn |
| NF-06 | Kullanılabilirlik (mesai saatleri) | %99,5 |
| NF-07 | Yetki, veri katmanındaki kurallarla birebir aynı sonucu verir | Yetki testi kümesi: sıfır sapma |
| NF-08 | Sistem yalnızca okuma yapar | Bağlantı kullanıcısında yazma yetkisi yok |
| NF-09 | Denetim kaydı değiştirilemez ve 24 ay saklanır | Değiştirilemez depo, erişim kaydı |
| NF-10 | Model ve kütüphaneler imzalı iç kanaldan gelir | Karma doğrulaması zorunlu |
| NF-11 | Arayüz erişilebilirlik uyumlu ve mobil uyumludur | Klavye gezinme, ekran okuyucu, kontrast |
| NF-12 | Kurtarma hedefi 4 saat, veri kaybı toleransı 24 saat | Aylık geri yükleme tatbikatı |

---

## 18 — Kabul kriterleri

Aşağıdaki maddeler **test edilebilir** biçimde yazılmıştır; her biri altın soru kümesi veya belgelenmiş bir kontrol ile doğrulanır. Kanaat ifadesi ("kullanıcılar memnun") kabul kriteri sayılmaz.

### 18.1 Faz 1 kapı kriterleri

| Kod | Kriter | Doğrulama yöntemi |
|---|---|---|
| K1-01 | Kilitli %20'lik altın kümede yürütme doğruluğu ≥ %80 | Otomatik koşu, sonuç kümesi karşılaştırması |
| K1-02 | Reddedilmesi gereken 20 soruda doğru reddetme ≥ %90 | Otomatik koşu + manuel inceleme |
| K1-03 | Yetkisiz 10 soruda sıfır veri sızıntısı; hepsi denetim kaydında | Güvenlik ekibi denetimi |
| K1-04 | 25 metrik onaylı tanıma sahip ve kayıtta sürümlü | Metrik kaydı incelemesi, iş birimi imzası |
| K1-05 | Her cevapta künye (metrik, filtre, tazelik, sorgu) görünür | Arayüz kabul testi |
| K1-06 | Ölçülen üretim hızı ≥ 15 token/sn, p95 ≤ 30 sn | Yük testi raporu |
| K1-07 | Gece değerlendirme koşusu ve regresyon kapısı çalışır durumda | Ardışık 5 gün kesintisiz koşu |
| K1-08 | Sistem hiçbir dış ağ bağlantısı kurmuyor | Ağ akış kaydı, 7 günlük gözlem |

### 18.2 Üretim kabul kriterleri

| Kod | Kriter | Eşik |
|---|---|---|
| KP-01 | Yürütme doğruluğu, tam altın küme | ≥ %88 |
| KP-02 | Doğru reddetme | ≥ %93 |
| KP-03 | Yanlış reddetme | ≤ %10 |
| KP-04 | p95 uçtan uca süre, tepe saatte | ≤ 25 sn |
| KP-05 | Kullanılabilirlik, 4 hafta ölçüm | ≥ %99,5 |
| KP-06 | Yetki testi kümesinde veri katmanıyla sapma | 0 |
| KP-07 | Haftalık aktif kullanıcı / hedef kitle | ≥ %50 |
| KP-08 | Olumsuz geri bildirim oranı | ≤ %8 |
| KP-09 | İşletim el kitabı ve geri alma yordamı tatbik edilmiş | Belgeli |
| KP-10 | Güvenlik ve uyum onayı alınmış | CISO imzası |

### 18.3 Örnek kabul senaryoları

```
S-01  Yetkisiz erişim
  Verilen:  Bölge müdürü yalnızca kendi bölgesini görmeye yetkili
  Yapılan:  "Ege bölgesinin cirosu ne?" sorusu soruluyor
  Beklenen: Ret; Ege verisi hiçbir biçimde dönmüyor; denetim kaydı yazılıyor
            ve cevap metni Ege verisinin varlığını ima etmiyor

S-02  Muğlak metrik
  Verilen:  "Tahsilat performansı" iki onaylı metriğe eşleşiyor
  Yapılan:  "Marmara'da tahsilat performansı düştü mü?"
  Beklenen: Cevap üretilmiyor; iki seçenekli netleştirme sorusu geliyor

S-03  Kapsam dışı
  Yapılan:  "Rakiplerin pazar payı ne oldu?"
  Beklenen: Net ret + neden; tahmini sayı üretilmiyor

S-04  Takip sorusu
  Verilen:  Önceki cevap 2026-Q2 net ciro
  Yapılan:  "Aynısını bölge kırılımıyla göster"
  Beklenen: Aynı metrik ve dönem korunuyor; yalnızca boyut ekleniyor

S-05  Veri tazeliği
  Yapılan:  Herhangi bir metrik sorusu
  Beklenen: Cevap künyesinde kaynak tablonun son yüklenme zamanı görünüyor

S-06  Sorgu zaman aşımı
  Verilen:  5 yıllık, tam kırılımlı ağır sorgu
  Beklenen: 30 sn'de kesiliyor; hata değil, daraltma önerisi sunuluyor
```

---

## 19 — Açık kararlar

Aşağıdaki maddeler bilinçli olarak açık bırakılmıştır; her biri bir sahibe ve bir tarihe bağlanmıştır. Onay öncesinde kapatılması gereken tek madde AK-01'dir.

| Kod | Açık konu | Seçenekler | Karar sahibi | Ne zaman |
|---|---|---|---|---|
| AK-01 | Faz 1'in konu alanı | Satış ve gelir · Tahsilat · Operasyon | CDO + iş birimi | Onay toplantısı |
| AK-02 | Sorgu yolu: doğrudan veri ambarı mı, semantik model mi | A · B · ikisi birlikte | Veri platformu | Faz 0 sonu |
| AK-03 | Ana model adayı | Faz 0'da ölçülecek 3 aday | Yapay zekâ ekibi + hukuk | Faz 0 sonu |
| AK-04 | Bağlantı kimliği: kullanıcı kimliği mi, hizmet hesabı + bağlam mı | Teknik uygunluğa bağlı | Güvenlik + veri platformu | Faz 1 H2 |
| AK-05 | Hazır ticari ürünle fiyat karşılaştırması yapılacak mı | Evet · Hayır | CIO | Faz 0 içinde |
| AK-06 | Faz 2 donanımı: satın alma mı, mevcut kapasiteden ayırma mı | Bütçeye bağlı | CIO + altyapı | Faz 1 kapısı |
| AK-07 | Soru metinlerinin saklama süresi | 6 ay · 12 ay · kimliksizleştirme | Uyum + KVKK | Faz 1 H4 |
| AK-08 | Asgari hücre büyüklüğü eşiği (T-05) | n ≥ 3 · n ≥ 5 · n ≥ 10 | Uyum + veri sahipleri | Faz 1 H4 |

> **Onay için sorulacak tek soru.** Bu dokümanın onay toplantısındaki asıl gündemi teknoloji değildir. Sorulması gereken şudur: **Faz 1'in konu alanında 25 metriğin onaylı tanımını 8 hafta içinde üretecek iş birimi sahipliği var mı?** Cevap evetse proje başlar. Hayırsa proje yine başlayabilir — ama adı "yönetici asistanı" değil, "metrik tanım programı" olur ve asistan onun ikinci fazıdır.

---

## 20 — Ekler ve sözlük

### 20.1 Terimler

| Terim | Bu dokümandaki anlamı |
|---|---|
| **Anlam sözleşmesi** | Metrik kaydı, boyut kataloğu, eşanlamlı sözlüğü ve boyut değer indeksinin bütünü; sistemin doğruluk kaynağı (§06) |
| **Sorgu spesifikasyonu** | Modelin ürettiği, şema ile kısıtlı JSON yapı; SQL'in kendisi değil, tarifi (§7.2) |
| **Altın soru kümesi** | Beklenen sonucu önceden bilinen, değerlendirme için kullanılan soru derlemesi (§10.1) |
| **Yürütme doğruluğu** | Üretilen sorgunun sonucunun referans sonuçla aynı olması; sorgu metninin benzerliği değil |
| **Doğru reddetme** | Cevaplanmaması gereken bir soruyu gerekçeyle reddetme oranı |
| **Ön-dolum** | Modelin girdi bağlamını işlediği ilk aşama; CPU'da bağlam uzunluğuyla doğrusal artar |
| **Uzman karışımı (MoE)** | Her token için parametrelerin yalnızca bir bölümünün kullanıldığı model mimarisi; CPU çıkarımının anahtarı (§5.1) |
| **Nicemleme** | Model ağırlıklarının daha az bitle saklanması; bellekten okunan hacmi düşürür |
| **KV önbelleği** | Üretim sırasında yeniden hesaplamayı önleyen ara durum belleği |
| **Satır düzeyi güvenlik** | Kullanıcının yalnızca yetkili olduğu satırları görmesini veri katmanında sağlayan mekanizma |
| **Asgari hücre kuralı** | Toplulaştırmada birey çıkarımını önlemek için sonucun maskelendiği alt sınır (T-05) |
| **Şablon** | Parametreli, önceden doğrulanmış sorgu kalıbı; modele hiç uğramadan çalışabilir (§7.4) |

### 20.2 Karar kaydı

| Kod | Karar | Bölüm |
|---|---|---|
| D-05 | Ana model uzman karışımı mimaride ve 4-bit nicemlenmiş olacaktır; yoğun 30B+ modeller aday değildir | §5.4 |
| D-06 | Metrik kaydı tek doğruluk kaynağıdır; kayıtta olmayan metrik sorgulanamaz | §6.3 |
| D-07 | Sorgu üretimi kısıtlı spesifikasyon üzerinden yapılır; serbest SQL üretimi üretime alınmaz | §7.1 |
| D-08 | Tek akıl yürütücü model + deterministik yardımcılar; çok ajanlı tasarım reddedilmiştir | §8.3 |
| D-10 | Faz geçişi ölçüm eşiğine bağlıdır: doğruluk %80, doğru reddetme %90 | §10.2 |
| D-14 | İnce ayar Faz 3'ten önce gündeme alınmaz | §14.4 |

### 20.3 Bu dokümanın kapsamadıkları

- Ayrıntılı arayüz tasarımı ve ekran akışları — ayrı bir tasarım dokümanının konusu.
- Kesin bütçe ve tedarik kalemleri — donanım seçimi AK-06 ile kapandıktan sonra çıkarılır.
- Metrik tanımlarının kendisi — bunlar veri yönetişimi kaydında yaşar, spesifikasyonda değil.
- Konteyner ve ağ yapılandırmalarının satır düzeyi ayrıntısı — işletim el kitabına aittir.
- Model adayı listesi — Faz 0 ölçüm raporunun çıktısıdır; burada sabitlenmesi dokümanı erken eskitir.

### 20.4 Sürüm geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 0.9 | 28.08.2026 | İnceleme için ilk tam sürüm; §14 uçtan uca değerlendirme ve §19 açık kararlar dahil |
| 1.0 | — | Onay toplantısı sonrası; AK-01 kapatılmış ve Faz 0 ölçümleri eklenmiş olarak beklenir |

---

**ONPREM-YZ-SPEC-001 · v0.9** — Kapalı Devre Yönetici Asistanı. Veri & Yapay Zekâ Platformu tarafından inceleme için hazırlanmıştır. Bu doküman bir tasarım taahhüdüdür, bir ürün vaadi değildir: içindeki her sayısal hedef §10'daki ölçüm hattıyla doğrulanana kadar varsayım olarak okunmalıdır.
