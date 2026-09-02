# -*- coding: utf-8 -*-
"""
TAHMİN — geçmiş seriden ileriye doğrusal eğilim kestirimi.

Bu modül eklenene kadar tahmin sorularını REDDEDİYORDUK. Ret gerekçesi
hâlâ geçerliydi: 10 dönemle, tam bir mevsim döngüsü olmadan yapılan her
tahmin zayıftır. Değişen şey, reddetmek yerine **belirsizliği birlikte
vermek**.

Yöntem: en küçük kareler (OLS) doğrusal regresyon. Bilinçli olarak basit.
ARIMA/Prophet gibi bir şey 10 gözlemle daha iyisini yapmaz, ama sonucun
neden o çıktığını açıklanamaz hâle getirir. Denetlenebilir bir sistemde
"model öyle dedi" kabul edilebilir bir cevap değil.

DÜRÜSTLÜK KAPILARI — hepsi bilinçli, hepsi gevşetilebilir ama gevşetmenin
bedeli sahte kesinliktir:

  1. Ufuk en fazla 3 dönem VE geçmişin üçte birinden fazla değil.
     10 dönemle 12 ay ileri gitmek kestirim değil kehanettir.
  2. R² < 0.30 ise tahmin ÜRETİLMEZ. Eğilim yoksa doğru yanıt
     "belirgin bir eğilim yok" demektir.
  3. Nokta tahmini asla tek başına dönmez; %80 kestirim aralığı
     zorunludur. Tek sayı gören insan onu kesinlik sanıyor.
  4. Çıktı her yerde TAHMİN diye etiketlenir — cevap cümlesinde,
     denetim kaydında, kartta.

Sayılar gerçek sonuç kümesinden gelir; bu modül yalnız o sayılar
üzerinde açık aritmetik yapar. Hiçbir yerde uydurma yoktur.
"""

import math

# Tahmin üretmek için gereken en az gözlem.
ASGARI_GOZLEM = 6

# Ufuk sınırı: hem sabit üst sınır hem geçmişe oranlı sınır.
AZAMI_UFUK = 3
UFUK_ORANI = 3.0          # geçmiş / 3

# Bu eşiğin altında eğilim "yok" sayılır.
ASGARI_R2 = 0.30

# %80 aralık için t katsayısı (serbestlik derecesine göre, iki yönlü).
# Tablo küçük tutuldu; scipy bağımlılığı eklemeye değmez.
_T80 = {1: 3.078, 2: 1.886, 3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440,
        7: 1.415, 8: 1.397, 9: 1.383, 10: 1.372, 11: 1.363, 12: 1.356,
        15: 1.341, 20: 1.325, 30: 1.310}


def _t80(sd):
    if sd <= 0:
        return 3.078
    if sd in _T80:
        return _T80[sd]
    for k in sorted(_T80):
        if sd <= k:
            return _T80[k]
    return 1.282          # normal dağılım sınırı


def azami_ufuk(gozlem_sayisi):
    return max(1, min(AZAMI_UFUK, int(gozlem_sayisi / UFUK_ORANI)))


def dogrusal_uydur(degerler):
    """OLS doğrusal uyum. x = 0..n-1.

    Döner: eğim, kesişim, R², kalıntı standart hatası, serbestlik derecesi.
    """
    n = len(degerler)
    if n < 2:
        return None
    xort = (n - 1) / 2.0
    yort = sum(degerler) / float(n)
    sxx = sum((i - xort) ** 2 for i in range(n))
    sxy = sum((i - xort) * (degerler[i] - yort) for i in range(n))
    if sxx == 0:
        return None
    egim = sxy / sxx
    kesisim = yort - egim * xort

    tahminler = [kesisim + egim * i for i in range(n)]
    kalinti_kt = sum((degerler[i] - tahminler[i]) ** 2 for i in range(n))
    toplam_kt = sum((d - yort) ** 2 for d in degerler)
    r2 = 1.0 - (kalinti_kt / toplam_kt) if toplam_kt > 0 else 0.0
    sd = n - 2
    kalinti_sh = math.sqrt(kalinti_kt / sd) if sd > 0 else 0.0
    return {'egim': egim, 'kesisim': kesisim, 'r2': r2,
            'kalintiSH': kalinti_sh, 'sd': sd, 'n': n, 'sxx': sxx, 'xort': xort}


def tahminle(degerler, ufuk):
    """Seriyi `ufuk` dönem ileri kestirir.

    Döner: {'durum': 'ok'|'egilim_yok'|'yetersiz_veri', ...}
    """
    temiz = [float(d) for d in degerler if d is not None]
    if len(temiz) < ASGARI_GOZLEM:
        return {'durum': 'yetersiz_veri', 'gozlem': len(temiz),
                'gereken': ASGARI_GOZLEM}

    uy = dogrusal_uydur(temiz)
    if uy is None:
        return {'durum': 'yetersiz_veri', 'gozlem': len(temiz),
                'gereken': ASGARI_GOZLEM}

    if uy['r2'] < ASGARI_R2:
        return {'durum': 'egilim_yok', 'r2': uy['r2'],
                'ortalama': sum(temiz) / len(temiz),
                'esik': ASGARI_R2}

    sinir = azami_ufuk(len(temiz))
    kirpildi = ufuk > sinir
    ufuk = min(ufuk, sinir)

    t = _t80(uy['sd'])
    n = uy['n']
    noktalar = []
    for k in range(1, ufuk + 1):
        x = n - 1 + k
        deger = uy['kesisim'] + uy['egim'] * x
        # Kestirim (prediction) aralığı — güven aralığından geniştir,
        # çünkü tek bir gelecek gözlemin saçılımını da içerir.
        se = uy['kalintiSH'] * math.sqrt(1.0 + 1.0 / n
                                         + ((x - uy['xort']) ** 2) / uy['sxx'])
        noktalar.append({'adim': k, 'deger': deger,
                         'alt': deger - t * se, 'ust': deger + t * se})

    return {'durum': 'ok', 'noktalar': noktalar, 'r2': uy['r2'],
            'egim': uy['egim'], 'gozlem': n, 'ufuk': ufuk,
            'ufukSiniri': sinir, 'kirpildi': kirpildi,
            'yontem': 'en küçük kareler doğrusal eğilim'}


def yil_sonu_projeksiyon(degerler, kalan_donem):
    """Yıl sonu koşu hızı projeksiyonu.

    Regresyon tahmininden AYRI tutuluyor, çünkü sorusu da farklı:
    "bu hızla nereye varırız". Ortalama hız aritmetiği — model değil.
    Bu yüzden ufuk sınırına tabi değil, ama kendi uyarısını taşıyor.
    """
    temiz = [float(d) for d in degerler if d is not None]
    if not temiz or kalan_donem <= 0:
        return None
    gerceklesen = sum(temiz)
    hiz = gerceklesen / len(temiz)
    return {
        'gerceklesen': gerceklesen,
        'donemSayisi': len(temiz),
        'hiz': hiz,
        'kalan': kalan_donem,
        'kalanProjeksiyon': hiz * kalan_donem,
        'yilSonu': gerceklesen + hiz * kalan_donem,
        'yontem': 'ortalama koşu hızı (gerçekleşen / dönem sayısı)',
    }
