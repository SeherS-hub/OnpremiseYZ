# -*- coding: utf-8 -*-
"""
DERLEYİCİ · DAX — sorgu spesifikasyonu → DAX (SSAS Tabular).

Spesifikasyondan DAX'a çeviri DETERMİNİSTİKTİR ve tek yerdedir. Bir dil
modeli planlayıcıya konsa bile buraya dokunmaz: model yalnızca kısıtlı
JSON üretir, DAX'ı bu dosya yazar. Mimarinin taşıyıcı kararı budur.
"""

from lib import sozlesme as S


def _lit(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return '"' + str(v).replace('"', '""') + '"'


def _boyut_dax(kod):
    """Boyut → DAX sütunu eşlemesi sözleşmeden okunur.

    Burada ikinci bir liste tutmak, iki yerde güncelleme demekti.
    """
    b = S.boyut_bul(kod)
    if not b or not b.get('daxSutun'):
        raise ValueError('Semantik modelde olmayan boyut: %s' % kod)
    return b['daxSutun']


def derle(spec):
    # --- ölçüler --- ad ve ifade AYRI tutulur; birleştirilmiş metni
    # sonradan parçalamak sessizce bozuk DAX üretiyordu.
    olculer = []
    for kod in spec['metrikler']:
        met = S.metrik_bul(kod)
        if not met or not met.get('dax'):
            raise ValueError('Semantik modelde tanımlı olmayan ölçü: %s' % kod)
        olculer.append((met['ad'], met['dax']))

    # --- filtreler ---
    filtreler = []
    for f in spec['filtreler']:
        sut = _boyut_dax(f['boyut'])
        if f['operator'] == 'in':
            degerler = ', '.join(_lit(d) for d in f['deger'])
            filtreler.append('FILTER ( ALL ( %s ), %s IN { %s } )' % (sut, sut, degerler))
        else:
            filtreler.append('FILTER ( ALL ( %s ), %s = %s )' % (sut, sut, _lit(f['deger'])))

    # --- boyut yoksa tek satır ---
    if not spec['boyutlar']:
        satirlar = []
        for ad, dax in olculer:
            if filtreler:
                satirlar.append('"%s", CALCULATE ( %s, %s )' % (ad, dax, ', '.join(filtreler)))
            else:
                satirlar.append('"%s", %s' % (ad, dax))
        return 'EVALUATE\nROW (\n    ' + ',\n    '.join(satirlar) + '\n)'

    # --- boyutlu: SUMMARIZECOLUMNS ---
    boyut_sutunlari = [_boyut_dax(k) for k in spec['boyutlar']]
    parcalar = (boyut_sutunlari + filtreler
                + ['"%s", %s' % (ad, dax) for ad, dax in olculer])
    tablo = 'SUMMARIZECOLUMNS (\n        ' + ',\n        '.join(parcalar) + '\n    )'

    dax = 'EVALUATE\n'
    siralama = spec.get('siralama')
    limit = spec.get('limit')

    if limit and siralama:
        met = S.metrik_bul(siralama['olcut'])
        yon = 'ASC' if siralama['yon'] == 'artan' else 'DESC'
        dax += 'TOPN (\n    %d,\n    %s,\n    [%s], %s\n)' % (int(limit), tablo, met['ad'], yon)
        dax += '\nORDER BY [%s] %s' % (met['ad'], yon)
    else:
        dax += tablo
        if siralama:
            met = S.metrik_bul(siralama['olcut'])
            yon = 'ASC' if siralama['yon'] == 'artan' else 'DESC'
            dax += '\nORDER BY [%s] %s' % (met['ad'], yon)
        else:
            dax += '\nORDER BY %s ASC' % boyut_sutunlari[0]

    return dax
