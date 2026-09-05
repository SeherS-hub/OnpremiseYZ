# -*- coding: utf-8 -*-
"""
BAĞLAM SERİSİ — cevap kartındaki trend ve hedef grafiklerinin verisi.

Neden ajan çekiyor da rapor kendi sorgulamıyor:

  1. Kartın TEK veri kaynağı denetim kaydı olsun. Rapor hem denetim
     kaydına hem semantik modele bağlanırsa iki kaynaklı olur ve iki
     kaynak er geç ayrışır.
  2. Kart bir DENETİM ARTEFAKTIDIR. Cevabın verildiği ANDAKİ değerleri
     göstermeli; model sonradan yeniden işlenirse kart geçmişi yine
     doğru anlatmalı.

Tek DAX çağrısı, iki seri (UNION). Node sürümünde bu ~600 ms'ydi ve
ayrı süreçte koşuyordu; kalıcı bağlantıda birkaç milisaniye.
"""

from lib import sozlesme as S


def birim(met):
    """Trend, sorulan metriğin kendisini gösterir; birim kartta etikete girer."""
    if not met:
        return 'mn TL'
    if met['birim'] == 'oran':
        return '%'
    if met['birim'] in ('adet', 'kişi'):
        return met['birim']
    return 'mn TL'


def _olcek(met):
    """Para birimli ölçüler milyona indirgenir; grafik ekseni okunur kalsın."""
    return 1000000 if (met and met['birim'] == 'TRY') else 1


def _sade(sutun):
    """'Donem[Dönem]' → '[Dönem]'. SUMMARIZECOLUMNS çıktısında kolonlar
    tablo adı olmadan anılır."""
    return sutun[sutun.index('['):]


def _dax_sorgu(met):
    olcu = met['dax'] if (met and met.get('dax')) else '[Net Ciro]'
    b = _olcek(met)
    trend_deger = olcu if b == 1 else 'DIVIDE ( %s, %d )' % (olcu, b)

    # Takvim kolonları ve hedef ölçüsü sözleşmeden geliyor; başka bir
    # modele taşırken bu dosyaya dokunmak gerekmesin diye.
    anahtar, donem = S.DONEM_ANAHTAR, S.DONEM_SUTUN
    a, d = _sade(anahtar), _sade(donem)

    trend = ('  SELECTCOLUMNS (\n'
             '    SUMMARIZECOLUMNS ( %s, %s, "v", %s ),\n'
             '    "Seri", "trend", "Sira", %s, "Etiket", %s, "Deger", [v]\n'
             '  )' % (anahtar, donem, trend_deger, a, d))

    hedef_olcu = getattr(S, 'KART_HEDEF_OLCU', None)
    if not hedef_olcu:
        # Modelde hedef ölçüsü yoksa kartın hedef grafiği boş kalır —
        # uydurulmuş bir seri koymaktan iyidir.
        return 'EVALUATE\n' + trend.strip() + '\nORDER BY [Seri], [Sira]'

    hedef = ('  SELECTCOLUMNS (\n'
             '    SUMMARIZECOLUMNS ( %s, %s, "g", %s * 100 ),\n'
             '    "Seri", "hedef", "Sira", %s, "Etiket", %s, "Deger", [g]\n'
             '  )' % (anahtar, donem, hedef_olcu, a, d))

    return ('EVALUATE\nUNION (\n' + trend + ',\n' + hedef +
            '\n)\nORDER BY [Seri], [Sira]')


def sorgu(spec):
    """Sorgu METNİNİ verir; çalıştırma ana sorguyla aynı çağrıda yapılır."""
    met = None
    if spec and spec.get('metrikler'):
        met = S.metrik_bul(spec['metrikler'][0])
    return _dax_sorgu(met)


def bicimle(satirlar):
    """Ham satırları denetim kaydının beklediği biçime çevirir."""
    cikti = []
    for i, s in enumerate(satirlar or [], start=1):
        try:
            deger = float(s.get('Deger'))
        except (TypeError, ValueError):
            deger = 0.0
        cikti.append({
            'seri': str(s.get('Seri') or 'trend'),
            'sira': i,
            'etiket': '' if s.get('Etiket') is None else str(s.get('Etiket')),
            'deger': deger,
        })
    return cikti
