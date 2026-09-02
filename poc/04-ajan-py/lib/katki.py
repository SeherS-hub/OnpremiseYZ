# -*- coding: utf-8 -*-
"""
KATKI AYRIŞTIRMASI — "neden değişti" sorusunun dürüst karşılığı.

Bu modül eklenene kadar "ciro neden düştü" sorusuna cevap vermiyorduk:
    "Nedensellik kuramam — bu veriyle 'neden' sorusunun cevabı
     kanıtlanamaz. Ama kırılıma bakıp en çok katkı yapan kalemleri
     gösterebilirim."

O cümle hâlâ doğru ve **değişmiyor**. Eklenen şey ikinci yarısı: artık
öneriyi kullanıcıya sorup beklemek yerine hesabı yapıp gösteriyoruz.

Ne YAPAR:
  · İki dönem arasındaki değişimi bir boyuta göre parçalar ve her
    kalemin değişime kaç TL / yüzde kaç katkı verdiğini söyler.
  · Ciro değişimini ADET ve SEPET etkisine ayırır (hacim × fiyat).

Ne YAPMAZ — ve bunu her cevapta yazar:
  · Sebep iddia etmez. "Marmara -12 mn TL katkı verdi" demek,
    "Marmara yüzünden düştü" demek DEĞİLDİR. Marmara'nın düşüşünün
    kendi sebebi bu veride yok.
  · Karşı-olgusal bir şey söylemez ("Marmara düşmeseydi..." gibi).
  · Dış etken, kampanya, rekabet, mevsim — hiçbiri modelde yok.

Aritmetiğin tamamı açık ve toplamı tutar: katkıların toplamı toplam
değişime eşittir. Denetlenebilirliğin ölçüsü bu.
"""


def _sayi(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def boyut_katkisi(onceki_satirlar, simdiki_satirlar, boyut_ad, metrik_ad):
    """İki dönemin kırılımını karşılaştırıp kalem kalem katkı çıkarır.

    Girdi: her biri {boyut_ad: etiket, metrik_ad: deger} sözlük listesi.
    """
    def indeks(satirlar):
        d = {}
        for s in satirlar or []:
            etiket = s.get(boyut_ad)
            if etiket is None:
                for k, v in s.items():
                    if not isinstance(v, (int, float)):
                        etiket = v
                        break
            d[str(etiket)] = _sayi(s.get(metrik_ad)) or 0.0
        return d

    a = indeks(onceki_satirlar)
    b = indeks(simdiki_satirlar)
    etiketler = sorted(set(list(a.keys()) + list(b.keys())))

    kalemler = []
    for e in etiketler:
        onceki = a.get(e, 0.0)
        simdiki = b.get(e, 0.0)
        kalemler.append({
            'etiket': e,
            'onceki': onceki,
            'simdiki': simdiki,
            'degisim': simdiki - onceki,
            'oran': ((simdiki - onceki) / onceki) if onceki else None,
        })

    toplam_degisim = sum(k['degisim'] for k in kalemler)
    # Katkı payı: kalemin değişimi / toplam değişim. Toplam değişim sıfıra
    # yakınsa pay anlamsız büyür; o durumda pay verilmez.
    anlamli = abs(toplam_degisim) > 1e-9
    for k in kalemler:
        k['pay'] = (k['degisim'] / toplam_degisim) if anlamli else None

    # Mutlak büyüklüğe göre sırala — en çok çeken ve en çok iten başta.
    kalemler.sort(key=lambda k: -abs(k['degisim']))

    return {
        'boyut': boyut_ad,
        'metrik': metrik_ad,
        'toplamOnceki': sum(a.values()),
        'toplamSimdiki': sum(b.values()),
        'toplamDegisim': toplam_degisim,
        'kalemler': kalemler,
        'yukariCekenler': [k for k in kalemler if k['degisim'] > 0],
        'asagiCekenler': [k for k in kalemler if k['degisim'] < 0],
    }


def hacim_sepet_ayristirmasi(onceki, simdiki):
    """Ciro değişimini ADET ve SEPET etkisine ayırır.

    Ciro = Adet × Sepet olduğundan değişim üç parçaya ayrılır:

        hacim etkisi  = ΔAdet  × Sepet₀
        sepet etkisi  = ΔSepet × Adet₀
        etkileşim     = ΔAdet  × ΔSepet

    Üçünün toplamı ΔCiro'ya EŞİTTİR — kontrol ediliyor ve sapma
    döndürülüyor. Bu ayrıştırma bir model değil, cebir; "ciro neden
    değişti" sorusunun tek matematiksel olarak kesin cevabı budur:
    ya daha çok/az satıldı, ya birim tutar değişti, ya ikisi birden.

    Girdi: {'ciro': .., 'adet': .., 'sepet': ..} iki dönem için.
    """
    a0, s0 = _sayi(onceki.get('adet')), _sayi(onceki.get('sepet'))
    a1, s1 = _sayi(simdiki.get('adet')), _sayi(simdiki.get('sepet'))
    c0, c1 = _sayi(onceki.get('ciro')), _sayi(simdiki.get('ciro'))
    if None in (a0, s0, a1, s1, c0, c1):
        return None

    da, ds = a1 - a0, s1 - s0
    hacim = da * s0
    sepet = ds * a0
    etkilesim = da * ds
    toplam = hacim + sepet + etkilesim
    return {
        'ciroOnceki': c0, 'ciroSimdiki': c1, 'ciroDegisim': c1 - c0,
        'adetOnceki': a0, 'adetSimdiki': a1, 'adetDegisim': da,
        'sepetOnceki': s0, 'sepetSimdiki': s1, 'sepetDegisim': ds,
        'hacimEtkisi': hacim,
        'sepetEtkisi': sepet,
        'etkilesim': etkilesim,
        'ayristirmaToplami': toplam,
        # Ciro ölçüsü toplama, sepet ise orana dayandığı için yuvarlama
        # sapması olabilir; gizlemek yerine raporluyoruz.
        'sapma': (c1 - c0) - toplam,
        'baskin': ('hacim' if abs(hacim) >= abs(sepet) else 'sepet'),
    }


UYARI = ('Bu bir KATKI ayrıştırmasıdır, sebep değil. Kalemlerin kendi '
         'değişiminin nedeni (kampanya, rekabet, mevsim, fiyat kararı) '
         'bu modelde yok.')
