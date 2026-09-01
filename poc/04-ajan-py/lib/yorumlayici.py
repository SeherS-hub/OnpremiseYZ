# -*- coding: utf-8 -*-
"""
YORUMLAYICI — sonuç kümesi → Türkçe cevap metni + künye.

Kritik kural: sayılar metinden değil, SONUÇ KÜMESİNDEN basılır. Burada
hiçbir aritmetik tahmin yapılmaz; tek istisna listelenen satırların
toplamı ve o da açıkça "listelenen satırların toplamı" diye söylenir.

İki ayrı metin üretilir:
    metin     rakamı içeren tam cümle — arayüz, sesli okuma, denetim
    aciklama  RAKAMSIZ, kendi başına anlaşılır cümle — cevap kartı
Kartta rakam zaten bir kez, büyük puntoyla duruyor; cümlede tekrar
etmesi "aynı sayıyı iki kere gördüm, hangisi doğru" hissi yaratıyordu.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

from lib import sozlesme as S

# Türkçe küçük/büyük harf. Python'un lower() metodu 'I' harfini 'i'ye
# çeviriyor; Türkçede 'I' → 'ı' olmalı, 'İ' → 'i'.
_KUCUK = {'I': 'ı', 'İ': 'i'}
_BUYUK = {'i': 'İ', 'ı': 'I'}


def tr_kucuk(s):
    return ''.join(_KUCUK.get(ch, ch) for ch in str(s)).lower()


def tr_buyuk_ilk(s):
    s = str(s)
    if not s:
        return s
    ilk = _BUYUK.get(s[0], s[0].upper())
    return ilk + s[1:]


def _tr_sayi(n, basamak=0, sondaki_sifiri_at=False):
    """1234567.89 → '1.234.567,89' (Türkçe ayraçlar).

    Yuvarlama YARIYI YUKARI. Python'un varsayılan format'ı bankacı
    yuvarlaması yapıyor ve ikili gösterimden dolayı 91,85 → "91,8"
    veriyordu; JS'in Intl'i aynı sayıya "91,9" diyor. Aynı soruya iki
    sistemin farklı rakam yazması kabul edilemez — Decimal(repr(n)) ile
    önce sayının kısa ondalık gösterimine inip oradan yuvarlıyoruz.
    """
    q = Decimal(1).scaleb(-basamak) if basamak else Decimal(1)
    d = Decimal(repr(float(n))).quantize(q, rounding=ROUND_HALF_UP)
    s = '{:,f}'.format(d)
    if basamak == 0 and '.' in s:
        s = s.split('.')[0]
    s = s.replace(',', '\x00').replace('.', ',').replace('\x00', '.')
    if sondaki_sifiri_at and ',' in s:
        s = s.rstrip('0').rstrip(',')
    return s


def sayi_bicimle(deger, birim):
    if deger is None:
        return '—'
    try:
        n = float(deger)
    except (TypeError, ValueError):
        return str(deger)

    if birim == 'oran':
        return _tr_sayi(n * 100, 1) + '%'
    if birim == 'TRY':
        if abs(n) >= 1000000:
            return _tr_sayi(n / 1000000.0, 1) + ' mn TL'
        return _tr_sayi(n, 0) + ' TL'
    if birim in ('adet', 'kişi'):
        return _tr_sayi(n, 0) + (' kişi' if birim == 'kişi' else ' adet')
    return _tr_sayi(n, 2, sondaki_sifiri_at=True)


_TEK_DONEM = re.compile(r'^(\d{4})-(\d{2})$')
_ARALIK = re.compile(r'^(\d{4}-\d{2})\s*…\s*(\d{4}-\d{2})$')


def donem_dogal(ifade):
    """"2026-03" → "2026 Mart ayı".

    Cevap cümlesi yöneticiye gidiyor; orada teknik dönem kodu değil
    okunur Türkçe olmalı.
    """
    if not ifade:
        return ''
    s = str(ifade).strip()

    m = _TEK_DONEM.match(s)
    if m:
        ay = next((a for a in S.AYLAR if a['no'] == int(m.group(2))), None)
        return '%s %s ayı' % (m.group(1), ay['ad'] if ay else m.group(2))

    m = _ARALIK.match(s)
    if m:
        # "ayı" eki aralıkta gereksiz uzunluk yaratıyor:
        # 2025 Kasım – 2026 Ağustos
        sade = lambda k: re.sub(r' ayı$', '', donem_dogal(k))       # noqa: E731
        return '%s – %s dönemi' % (sade(m.group(1)), sade(m.group(2)))

    # Çoklu dönem: "2026-02 · 2026-03" → "2026 Şubat ve 2026 Mart".
    # Ham dönem kodu cevap cümlesine girmemeli.
    if ' · ' in s and all(_TEK_DONEM.match(p.strip()) for p in s.split(' · ')):
        parcalar = [re.sub(r' ayı$', '', donem_dogal(p.strip())) for p in s.split(' · ')]
        return ' ve '.join(parcalar) + ' ayları'

    if s.startswith('tüm dönemler'):
        return 'tüm dönemler'
    return s                      # "2026 yılı" ve diğerleri olduğu gibi


def donem_lokatif(dogal):
    """"2025 Aralık ayı" → "2025 Aralık ayında".

    Cümle içinde "ayı döneminde" gibi çift ek oluşmasın diye.
    """
    if dogal.endswith('ayı') or dogal.endswith('yılı') or dogal.endswith('ayları'):
        return dogal + 'nda'
    if dogal.endswith('dönemi'):
        return dogal + 'nde'
    return dogal + ' içinde'


def metrik_ad_sade(ad):
    """Ölçü adının sonundaki "%" cümlede değerin yüzdesiyle çakışıyor
    ("hedef gerçekleşme % 102,9%"). Cümlede kırpılır."""
    return tr_kucuk(re.sub(r'\s*%\s*$', '', str(ad)))


def _metrik_deger(satir, met):
    if met['ad'] in satir:
        return satir[met['ad']]
    for k in satir:
        if k.lower() == met['ad'].lower():
            return satir[k]
    return None


def _boyut_deger(satir, boyut_kod):
    b = S.boyut_bul(boyut_kod)
    if not b:
        return None
    if b['ad'] in satir:
        return satir[b['ad']]
    for k in satir:
        if k.lower() == b['ad'].lower():
            return satir[k]
    return None


def _sayi(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def filtre_ifadesi(spec):
    """Dönem DIŞI filtreleri açık biçimde yazar: 'Bölge = Marmara'.

    Bu eksikti ve cevabı yanıltıcı yapıyordu: "Marmara bölgesinin cirosu"
    sorusuna "tüm dönemler net ciro 297,5 mn TL" deniyordu. Kartı gören
    biri bunu TOPLAM ciro (892,5 mn) sanardı — filtre hiçbir yerde
    görünmüyordu.

    Bilinçli olarak düz Türkçe tamlama değil, 'Boyut = Değer' biçimi:
    değer adları ("İç Anadolu", "E-Ticaret") ek aldığında ünlü uyumu
    tahmini gerektiriyor ve yanlış ek, denetim artefaktında kabul
    edilemez bir özensizlik olurdu. Eşittir işareti belirsizlik bırakmaz.
    """
    parcalar = []
    for f in (spec.get('filtreler') or []):
        if f['boyut'] in ('donem', 'yil'):
            continue
        b = S.boyut_bul(f['boyut'])
        ad = b['ad'] if b else f['boyut']
        deger = f['deger']
        if isinstance(deger, list):
            deger = ' / '.join(str(d) for d in deger)
        parcalar.append('%s = %s' % (ad, deger))
    return ' · '.join(parcalar)


def yorumla(spec, sonuc):
    satirlar = sonuc.get('satirlar') or []
    metrikler = [m for m in (S.metrik_bul(k) for k in spec['metrikler']) if m]
    ana = metrikler[0] if metrikler else None

    if not satirlar:
        return {
            'metin': 'Bu koşullarda kayıt bulunamadı. Dönem veya filtreyi gevşetmeyi deneyebiliriz.',
            'aciklama': 'Seçili koşullarda kayıt yok.',
            'satirlar': [], 'vurgu': None,
        }

    donem_metni = spec.get('donemIfade') or 'tüm dönemler'

    # --- özel: en yüksek / en düşük dönem ---
    if spec.get('ozel') == 'en_yuksek_donem':
        s = satirlar[0]
        d = donem_dogal(_boyut_deger(s, 'donem'))
        v = sayi_bicimle(_metrik_deger(s, ana), ana['birim'])
        yon = 'en düşük' if (spec.get('siralama') or {}).get('yon') == 'artan' else 'en yüksek'
        govde = ('Model kapsamındaki %d dönem içinde %s %s'
                 % (len(S.KAPSANAN_DONEMLER), yon, metrik_ad_sade(ana['ad'])))
        fil = filtre_ifadesi(spec)
        ek = ('  [%s]' % fil) if fil else ''
        return {
            'metin': '%s **%s** gerçekleşti: **%s**.%s' % (govde, donem_lokatif(d), v, ek),
            'aciklama': '%s %s gerçekleşti.%s' % (govde, donem_lokatif(d), ek),
            'satirlar': satirlar,
            'vurgu': {'etiket': d, 'deger': v},
        }

    # --- tek satır, boyutsuz ---
    if not spec['boyutlar'] and len(satirlar) == 1:
        s = satirlar[0]
        dogal = donem_dogal(donem_metni)

        if len(metrikler) == 1:
            metin = '%s %s **%s**.' % (dogal, metrik_ad_sade(ana['ad']),
                                       sayi_bicimle(_metrik_deger(s, ana), ana['birim']))
        else:
            parcalar = ['%s **%s**' % (metrik_ad_sade(m['ad']),
                                       sayi_bicimle(_metrik_deger(s, m), m['birim']))
                        for m in metrikler]
            metin = '%s — %s.' % (dogal, ', '.join(parcalar))

        yorumlar = []

        hg = next((m for m in metrikler if m['kod'] == 'hedef_gerceklesme'), None)
        if hg:
            oran = _sayi(_metrik_deger(s, hg))
            if oran is not None:
                yorumlar.append('Hedef tutmuş — gerçekleşme hedefin üzerinde.' if oran >= 1
                                else 'Hedef tutmamış — gerçekleşme hedefin altında kaldı.')

        ad = next((m for m in metrikler if m['kod'] == 'aylik_degisim'), None)
        if ad:
            d = _sayi(_metrik_deger(s, ad))
            if d is not None:
                yorumlar.append('Önceki aya göre artış var.' if d >= 0
                                else 'Önceki aya göre düşüş var.')

        fil = filtre_ifadesi(spec)
        if fil:
            metin += '  [%s]' % fil
        if yorumlar:
            metin += ' ' + ' '.join(yorumlar)

        # Açıklama rakam içermez. Yorumlanacak bir şey varsa o, yoksa
        # metriğin onaylı tanımı — ikisi de "bu sayı ne demek" sorusunu
        # sayıyı tekrarlamadan cevaplar.
        bas = '%s %s.' % (tr_buyuk_ilk(dogal), metrik_ad_sade(ana['ad']))
        aciklama = bas + (('  [%s]' % fil) if fil else '') + ' ' \
            + (' '.join(yorumlar) if yorumlar else (ana.get('tanim') or ''))

        return {
            'metin': metin,
            'aciklama': aciklama.strip(),
            'satirlar': satirlar,
            'vurgu': {'etiket': dogal,
                      'deger': sayi_bicimle(_metrik_deger(s, ana), ana['birim'])},
        }

    # --- boyutlu liste ---
    boyut_kod = spec['boyutlar'][0]
    boyut_ad = S.boyut_bul(boyut_kod)['ad']
    ilkler = ['%s %s' % (_boyut_deger(s, boyut_kod),
                         sayi_bicimle(_metrik_deger(s, ana), ana['birim']))
              for s in satirlar[:5]]

    dogal_liste = donem_dogal(donem_metni)
    metin = ('%s için %s, %s kırılımında %d satır döndü'
             % (dogal_liste, metrik_ad_sade(ana['ad']), tr_kucuk(boyut_ad), len(satirlar)))
    if spec.get('siralama'):
        metin += ' (%s sıralı)' % ('en düşükten' if spec['siralama']['yon'] == 'artan'
                                   else 'en yüksekten')
    metin += '. İlk sıralar: ' + ' · '.join(ilkler) + '.'

    toplam = sum((_sayi(_metrik_deger(s, ana)) or 0) for s in satirlar)
    if ana['birim'] in ('TRY', 'adet'):
        metin += ' Listelenen satırların toplamı %s.' % sayi_bicimle(toplam, ana['birim'])

    fil = filtre_ifadesi(spec)
    if fil:
        metin += '  [%s]' % fil

    en_ust = _boyut_deger(satirlar[0], boyut_kod)
    aciklama = ('%s · %s, %s kırılımı. %d satır%s'
                % (tr_buyuk_ilk(dogal_liste), ana['ad'], tr_kucuk(boyut_ad), len(satirlar),
                   ('; başta %s.' % en_ust) if spec.get('siralama') else '.'))
    if fil:
        aciklama += '  [%s]' % fil

    return {
        'metin': metin,
        'aciklama': aciklama,
        'satirlar': satirlar,
        'vurgu': {'etiket': '%s · %d satır' % (boyut_ad, len(satirlar)),
                  'deger': sayi_bicimle(toplam, ana['birim'])},
    }
