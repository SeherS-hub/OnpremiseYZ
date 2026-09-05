# -*- coding: utf-8 -*-
"""
ANLAM SÖZLEŞMESİ — metrik kaydı, eşanlamlı sözlüğü, boyut kataloğu.

Buradaki her şey veri yönetişiminin sahipliğindedir; kod değildir,
yapılandırmadır. Kayıtta olmayan metrik sorgulanamaz.

Ölçü, boyut ve değer listeleri modelden üretilebilir:
    python araclar/sozlesme_iskelet.py --sunucu ... --model ...
Eşanlamlılar, tanımlar ve sahiplik elle yazılır; asıl değer oradadır.
"""

import re


# Türkçe duyarlı normalizasyon. JS/Python lower() "İ" ve "I" ayrımını
# bozduğu için harf eşlemesi elle yapılıyor. Şapkalı harfler de burada:
# eksik olduklarında "kâr" ifadesi "k r" diye ikiye bölünüyor ve
# kârlılık soruları hiçbir desene uymuyordu.
_HARF = {
    'İ': 'i', 'I': 'i', 'ı': 'i',
    'Ş': 's', 'ş': 's',
    'Ğ': 'g', 'ğ': 'g',
    'Ü': 'u', 'ü': 'u',
    'Ö': 'o', 'ö': 'o',
    'Ç': 'c', 'ç': 'c',
    'Â': 'a', 'â': 'a',
    'Î': 'i', 'î': 'i',
    'Û': 'u', 'û': 'u',
}
_ALFABE_DISI = re.compile(r'[^a-z0-9\s%]')
_BOSLUK = re.compile(r'\s+')


def normalize(s):
    s = ''.join(_HARF.get(ch, ch) for ch in str(s or ''))
    s = s.lower()
    s = _ALFABE_DISI.sub(' ', s)
    return _BOSLUK.sub(' ', s).strip()


# ------------------------------------------------------------------
# METRİK KAYDI (M-1)
# Her ölçünün DAX karşılığı vardır; tek analitik kaynak SSAS Tabular.
# gecerliBoyutlar alanı olan ölçüler yalnız o boyutlarla sorulabilir —
# ilişkisiz boyutta filtre SESSİZCE yok sayılır ve aynı sayı döner.
# ------------------------------------------------------------------
METRIKLER = [
    {
        'kod': 'net_ciro',
        'toplanabilir': True,
        'ad': 'Net Ciro',
        'dax': '[Net Ciro]',
        'birim': 'TRY',
        'tanim': 'İade ve iskontolar düşülmüş, KDV hariç satış tutarı.',
        'sahip': 'Finans · Gelir Muhasebesi',
        'onay': {
            'durum': 'onayli',
            'surum': 3,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'ciro',
            'net ciro',
            'satis',
            'satislar',
            'hasilat',
            'gelir',
            'satis geliri',
            'turnover',
            'net satis',
            'performans',
            'sattik',
            'satildi',
            'satan',
            'satiyoruz',
            'is hacmi',
            'ne kadar sattik'
        ],
        'karistirilmamali': ['brut ciro (iade düşülmemiş)', 'siparis tutari (henüz faturalaşmamış)']
    },
    {
        'kod': 'satis_adet',
        'toplanabilir': True,
        'ad': 'Satış Adet',
        'dax': '[Satış Adet]',
        'birim': 'adet',
        'tanim': 'Satılan ürün adedi.',
        'sahip': 'Satış Operasyon',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'adet',
            'satis adedi',
            'satis adet',
            'kac adet',
            'urun adedi',
            'miktar',
            'sattik',
            'satildi',
            'kac tane',
            'kac urun',
            'kac kalem',
            'adetsel',
            'birim sayisi'
        ]
    },
    {
        'kod': 'musteri_sayisi',
        # Donemler boyunca TOPLANAMAZ (tekil sayim; aylari toplamak tekrar eden musteriyi iki kez sayar) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Müşteri Sayısı',
        'dax': '[Müşteri Sayısı]',
        'birim': 'kişi',
        'tanim': 'Dönem içinde alışveriş yapan tekil müşteri sayısı.',
        'sahip': 'CRM',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'musteri sayi',
            'musteri sayisi',
            'kac musteri',
            'musteri adedi',
            'alici sayisi',
            'alici sayi',
            'kac kisi',
            'musteri',
            'alici adedi',
            'tekil musteri'
        ],
        'gecerliBoyutlar': ['donem', 'yil']
    },
    {
        'kod': 'hedef',
        'toplanabilir': True,
        'ad': 'Hedef',
        'dax': '[Hedef]',
        'birim': 'TRY',
        'tanim': 'Onaylı bütçe hedefi.',
        'sahip': 'Bütçe & Planlama',
        'onay': {
            'durum': 'onayli',
            'surum': 2,
            'tarih': '2026-05-30'
        },
        'esanlamlilar': [
            'hedef',
            'butce',
            'butce hedefi',
            'plan',
            'planlanan',
            'planlanan tutar',
            'hedeflenen',
            'hedef tutar',
            'butcelenen'
        ]
    },
    {
        'kod': 'hedef_gerceklesme',
        # Donemler boyunca TOPLANAMAZ (oran) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Hedef Gerçekleşme %',
        'dax': '[Hedef Gerçekleşme %]',
        'birim': 'oran',
        'tanim': 'Net Ciro / Hedef. 1,00 = hedef tam tutmuş.',
        'sahip': 'Bütçe & Planlama',
        'onay': {
            'durum': 'onayli',
            'surum': 2,
            'tarih': '2026-05-30'
        },
        'esanlamlilar': [
            'hedef gerceklesme',
            'hedefi tuttuk mu',
            'hedef tuttu mu',
            'hedefe ulastik mi',
            'gerceklesme orani',
            'hedef performansi',
            'butce gerceklesme',
            'performans',
            'hedefe ulas',
            'hedefe ulastik',
            'hedefe ulasabildik',
            'butceyi tuttur',
            'butceyi tutturduk',
            'hedefi tuttur',
            'tutturma orani',
            'gerceklesme'
        ]
    },
    {
        'kod': 'ortalama_sepet',
        # Donemler boyunca TOPLANAMAZ (ortalama) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Ortalama Sepet',
        'dax': '[Ortalama Sepet]',
        'birim': 'TRY',
        'tanim': 'Net Ciro / Satış Adet.',
        'sahip': 'Satış Operasyon',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'ortalama sepet',
            'sepet tutari',
            'birim fiyat',
            'ortalama satis tutari',
            'ortalama',
            'sepet',
            'sepet buyuklugu',
            'ortalama fis',
            'fis tutari',
            'ortalama fis tutari'
        ]
    },
    {
        'kod': 'aylik_degisim',
        # Donemler boyunca TOPLANAMAZ (oran) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Aylık Değişim %',
        'dax': '[Aylık Değişim %]',
        'birim': 'oran',
        'tanim': '(Net Ciro - Önceki Ay Ciro) / Önceki Ay Ciro.',
        'sahip': 'Finans · Gelir Muhasebesi',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'aylik degisim',
            'onceki aya gore',
            'gecen aya gore',
            'bir onceki aya gore',
            'aya gore degisim',
            'mom',
            'artti mi',
            'dustu mu',
            'gecen aya kiyasla',
            'onceki aya kiyasla',
            'kiyasla',
            'aydan aya',
            'buyume',
            'buyume orani',
            'artis orani',
            'azalis orani'
        ]
    },
    {
        'kod': 'ortalama_aylik_ciro',
        # Donemler boyunca TOPLANAMAZ (ortalama) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Ortalama Aylık Ciro',
        'dax': '[Ortalama Aylık Ciro]',
        'birim': 'TRY',
        'tanim': 'Seçili dönemlerin aylık Net Ciro ortalaması.',
        'sahip': 'Finans · Gelir Muhasebesi',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': ['ortalama aylik ciro', 'aylik ortalama', 'ortalama ciro', 'ayda ortalama', 'ortalama']
    },
    {
        'kod': 'hedef_sapma',
        'toplanabilir': True,
        'ad': 'Hedef Sapma',
        'dax': '[Hedef Sapma]',
        'birim': 'TRY',
        'tanim': 'Net Ciro - Hedef. Negatif değer hedefin altında kalındığını gösterir.',
        'sahip': 'Bütçe & Planlama',
        'onay': {
            'durum': 'onayli',
            'surum': 2,
            'tarih': '2026-05-30'
        },
        'esanlamlilar': [
            'hedef sapma',
            'hedef sapmasi',
            'hedeften sapma',
            'butce sapmasi',
            'sapma',
            'hedefin altinda',
            'hedefin ustunde',
            'hedefin uzerinde',
            'hedefin ne kadar altinda',
            'hedefin ne kadar ustunde',
            'ne kadar altinda kaldik',
            'ne kadar ustunde kaldik',
            'hedefi ne kadar astik',
            'hedefi astik mi',
            'hedeften ne kadar',
            'hedeften ne kadar saptik',
            'hedefin ustune',
            'hedefin altina',
            'hedefin ustune ciktik'
        ]
    },
    {
        'kod': 'kumulatif_ciro',
        # Donemler boyunca TOPLANAMAZ (zaten birikimli) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Kümülatif Ciro',
        'dax': '[Kümülatif Ciro]',
        'birim': 'TRY',
        'tanim': 'Model kapsamındaki en eski dönemden itibaren birikimli Net Ciro.',
        'sahip': 'Finans · Gelir Muhasebesi',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'kumulatif',
            'kumulatif ciro',
            'birikimli',
            'birikimli ciro',
            'toplam birikim',
            'birikimli toplam',
            'kumule'
        ]
    },
    {
        'kod': 'onceki_ay_ciro',
        # Donemler boyunca TOPLANAMAZ (gecikmeli deger) — yil sonu
        # projeksiyonu ve katki ayristirmasi bu olcuyu reddeder.
        'toplanabilir': False,
        'ad': 'Önceki Ay Ciro',
        'dax': '[Önceki Ay Ciro]',
        'birim': 'TRY',
        'tanim': 'Bir önceki dönemin Net Cirosu.',
        'sahip': 'Finans · Gelir Muhasebesi',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-06-14'
        },
        'esanlamlilar': [
            'onceki ay ciro',
            'onceki ay cirosu',
            'gecen ay ciro',
            'gecen ayin cirosu',
            'bir onceki ayin cirosu'
        ]
    },
    {
        'kod': 'hedefi_tutan_ay',
        'toplanabilir': True,
        'ad': 'Hedefi Tutan Ay Sayısı',
        'dax': '[Hedefi Tutan Ay Sayısı]',
        'birim': 'adet',
        'tanim': 'Net Cironun Hedefe eşit veya üstünde olduğu dönem sayısı.',
        'sahip': 'Bütçe & Planlama',
        'onay': {
            'durum': 'onayli',
            'surum': 1,
            'tarih': '2026-05-30'
        },
        'esanlamlilar': [
            'kac ay hedefi',
            'hedefi tutan ay',
            'kac donem hedefi',
            'hedefi tutturdugumuz',
            'hedefi tutturduk',
            'kac ayda hedef'
        ]
    }
]

# ------------------------------------------------------------------
# BOYUT KATALOĞU (M-2)
# esanlamlilar = KIRILIM isteği sinyalleri. ciplakAdlar tek başına
# kırılım değildir: "Marmara bölgesinin cirosu" filtredir. Kırılım için
# planlayıcı ayrıca bir işaret arar (göre, bazında, kırılım, hangi…).
# ------------------------------------------------------------------
BOYUTLAR = [
    {
        'kod': 'donem',
        'ad': 'Dönem',
        'daxSutun': 'Donem[Dönem]',
        'esanlamlilar': [
            'aylara gore',
            'ay bazinda',
            'ay kirilimi',
            'aylik trend',
            'ay ay',
            'donem bazinda',
            'donemlere gore',
            'donem kirilimi',
            'trend'
        ]
    },
    {
        'kod': 'yil',
        'ad': 'Yıl',
        'daxSutun': 'Donem[Yıl]',
        'esanlamlilar': ['yila gore', 'yil bazinda', 'yillara gore', 'yil kirilimi']
    },
    {
        'kod': 'bolge',
        'ad': 'Bölge',
        'daxSutun': 'Bolge[Bölge]',
        'esanlamlilar': [
            'bolgeye gore',
            'bolge bazinda',
            'bolge kirilimi',
            'bolgeler',
            'bolgelere gore',
            'hangi bolge'
        ],
        'ciplakAdlar': ['bolge']
    },
    {
        'kod': 'urun_grubu',
        'ad': 'Ürün Grubu',
        'daxSutun': 'UrunGrubu[Ürün Grubu]',
        'esanlamlilar': [
            'urun gruplari',
            'urune gore',
            'urun kirilimi',
            'urun bazinda',
            'kategoriye gore',
            'hangi urun'
        ],
        'ciplakAdlar': ['urun grubu', 'urun']
    },
    {
        'kod': 'kanal',
        'ad': 'Kanal',
        'daxSutun': 'Kanal[Kanal]',
        'esanlamlilar': [
            'kanala gore',
            'kanal bazinda',
            'kanal kirilimi',
            'kanallar',
            'kanallara gore',
            'hangi kanal'
        ],
        'ciplakAdlar': ['kanal']
    }
]

BOYUT_DEGERLERI = {
    'bolge': ['Marmara', 'İç Anadolu', 'Ege', 'Akdeniz', 'Karadeniz'],
    'urun_grubu': ['Beyaz Eşya', 'Küçük Ev Aletleri', 'Mobilya', 'Aydınlatma'],
    'kanal': ['Kurumsal Satış', 'Perakende', 'E-Ticaret']
}

AYLAR = [
    {
        'no': 1,
        'ad': 'Ocak',
        'anahtar': ['ocak']
    },
    {
        'no': 2,
        'ad': 'Şubat',
        'anahtar': ['subat']
    },
    {
        'no': 3,
        'ad': 'Mart',
        'anahtar': ['mart']
    },
    {
        'no': 4,
        'ad': 'Nisan',
        'anahtar': ['nisan']
    },
    {
        'no': 5,
        'ad': 'Mayıs',
        'anahtar': ['mayis']
    },
    {
        'no': 6,
        'ad': 'Haziran',
        'anahtar': ['haziran']
    },
    {
        'no': 7,
        'ad': 'Temmuz',
        'anahtar': ['temmuz']
    },
    {
        'no': 8,
        'ad': 'Ağustos',
        'anahtar': ['agustos']
    },
    {
        'no': 9,
        'ad': 'Eylül',
        'anahtar': ['eylul']
    },
    {
        'no': 10,
        'ad': 'Ekim',
        'anahtar': ['ekim']
    },
    {
        'no': 11,
        'ad': 'Kasım',
        'anahtar': ['kasim']
    },
    {
        'no': 12,
        'ad': 'Aralık',
        'anahtar': ['aralik']
    }
]

KAPSANAN_DONEMLER = [
    '2025-11',
    '2025-12',
    '2026-01',
    '2026-02',
    '2026-03',
    '2026-04',
    '2026-05',
    '2026-06',
    '2026-07',
    '2026-08'
]
EN_GUNCEL_DONEM = '2026-08'

# --------------------------------------------------------------------
# MODEL BİÇİMİ — başka bir modele taşırken değişmesi gereken tek yer.
#
# Ölçü ve boyutlar yukarıdaki kataloglardan geliyor, ama trend serisi ve
# ileri analiz sorguları takvim kolonunu doğrudan yazmak zorunda. Eskiden
# bu adlar `baglam_serisi.py` ve `ileri_analiz.py` içine gömülüydü; başka
# bir SSAS'a taşımak "şu iki dosyayı da düzenleyin" demek oluyordu.
# Artık burada.
#
# DONEM_ANAHTAR sıralama içindir (metinsel "2026-10" < "2026-9" tuzağı).
# KART_HEDEF_OLCU cevap kartının hedef grafiğini besler; modelinizde
# hedef ölçüsü yoksa None yapın, kart o grafiği boş bırakır.
# --------------------------------------------------------------------
DONEM_SUTUN = 'Donem[Dönem]'
DONEM_ANAHTAR = 'Donem[DonemKey]'
KART_HEDEF_OLCU = '[Hedef Gerçekleşme %]'

# Kapsam dışı: konu modelde yok.
KAPSAM_DISI = [
    {
        'desen': ['rakip', 'rakipler', 'pazar payi', 'competitor'],
        'neden': 'Rakip ve pazar payı verisi bu veri ambarında yok.',
        'alternatif': 'Kendi ciro ve büyüme rakamlarımızı gösterebilirim.'
    },
    # Tahmin ARTIK kapsam dışı değil — lib/tahmin.py ile eklendi. Ama
    # senaryo modelleme ("fiyatı %10 artırsak ne olur") hâlâ dışında:
    # karşı-olgusal soru bu veriyle cevaplanamaz, elastikiyet bilgisi yok.
    {
        'desen': ['senaryo', 'ya olsaydi', 'olsaydi ne olur', 'simulasyon',
                  'what if', 'artirsak', 'dusursek', 'indirim yapsak'],
        'neden': 'Senaryo modelleme bu sürümün kapsamı dışında: karşı-olgusal '
                 'soru için gereken elastikiyet ve maliyet bilgisi modelde yok.',
        'alternatif': 'Geçmiş eğilimi, yıl sonu projeksiyonunu ve katkı '
                      'ayrıştırmasını gösterebilirim.'
    },
    {
        'desen': ['stok', 'depo', 'envanter'],
        'neden': 'Stok verisi bu semantik modelde tanımlı değil.',
        'alternatif': 'Satış adedi ve ciro üzerinden bakabilirim.'
    },
    {
        'desen': [
            'karlilik',
            'kar marji',
            'brut kar',
            'net kar',
            'kar orani',
            'kar ',
            'kari ',
            'kara ',
            'karin ',
            'marj',
            'maliyet',
            'gider',
            'ebitda'
        ],
        'neden': 'Kârlılık ve maliyet verisi bu semantik modelde tanımlı değil.',
        'alternatif': 'Ciro, hedef gerçekleşme ve ortalama sepet üzerinden bakabilirim.'
    }
]

# Yetkisiz: konu olabilir ama sorulamaz. Bu bir NEZAKET katmanıdır,
# güvenlik değil — asıl koruma SSAS rolleridir (bkz. GERCEK-ORTAMA-GECIS).
YETKISIZ = [
    {
        'desen': ['maas', 'ucret', 'bordro', 'prim', 'insan kaynaklari', 'personel'],
        'neden': 'Bu bilgiye erişim yetkiniz bulunmuyor.'
    },
    {
        'desen': ['tc kimlik', 'kimlik no', 'telefon numarasi', 'adres bilgisi', 'musteri adi'],
        'neden': 'Kişisel veri, asistan üzerinden sorgulanamaz (KVKK · K-04).'
    }
]

# Mevcut olmayan kırılım seviyesi: konu VAR, sorulan ayrıntı yok.
# "Buzdolabı satışları" ciro ölçüsüne uyup toplam döndürüyordu.
MEVCUT_OLMAYAN = [
    {
        'desen': [
            'buzdolabi',
            'camasir makinesi',
            'bulasik makinesi',
            'firin',
            'televizyon',
            'klima',
            'supurge',
            'mikrodalga',
            'utu',
            'koltuk',
            'kanepe',
            'yatak',
            'gardirop',
            'masa',
            'sandalye',
            'ampul',
            'avize',
            'lamba'
        ],
        'neden': 'Modelde ürün seviyesi yok; en ince kırılım Ürün Grubu.',
        'alternatif': 'Ürün grubu bazında bakabilirim: Beyaz Eşya, Küçük Ev Aletleri, Mobilya, Aydınlatma.'
    },
    {
        'desen': [
            'musteri adi',
            'hangi musteri',
            'musteri bazinda',
            'musteri kirilimi',
            'firma bazinda',
            'cari bazinda'
        ],
        'neden': 'Modelde müşteri seviyesi yok; yalnız dönem bazında müşteri SAYISI var.',
        'alternatif': 'Müşteri Sayısı ölçüsünü dönem bazında gösterebilirim.'
    },
    {
        'desen': ['sube', 'magaza', 'il bazinda', 'sehir bazinda', 'hangi sube', 'hangi magaza'],
        'neden': 'Modelde şube veya şehir seviyesi yok; coğrafi kırılım Bölge düzeyinde.',
        'alternatif': 'Bölge bazında bakabilirim: Marmara, İç Anadolu, Ege, Akdeniz, Karadeniz.'
    }
]


def metrik_bul(kod):
    for m in METRIKLER:
        if m['kod'] == kod:
            return m
    return None


def boyut_bul(kod):
    for b in BOYUTLAR:
        if b['kod'] == kod:
            return b
    return None


def _belirtec_dizini():
    """Sözlükte geçen her yüzey belirteci.

    Yazım toleransının kapısı: burada olan bir kelime doğru yazılmıştır,
    düzeltilmeye çalışılmaz. Olmadığında "sattık" ile "saptık" birbirine
    çevriliyor ve soru belirsizleşiyordu.
    """
    k = set()

    def ekle(ifade):
        for t in normalize(ifade).split(' '):
            if t:
                k.add(t)

    for m in METRIKLER:
        for e in m['esanlamlilar']:
            ekle(e)
    for b in BOYUTLAR:
        for e in b['esanlamlilar']:
            ekle(e)
        for e in b.get('ciplakAdlar', []):
            ekle(e)
    for kod in BOYUT_DEGERLERI:
        for d in BOYUT_DEGERLERI[kod]:
            ekle(d)
    for a in AYLAR:
        for e in a['anahtar']:
            ekle(e)
    return k


TUM_BELIRTECLER = _belirtec_dizini()
