# -*- coding: utf-8 -*-
"""
TAHMİN BİRİM TESTİ — SSAS gerekmez, saf aritmetik.

Buradaki vakalar "cevap verdi mi" değil **doğru cevabı mı verdi** ve
**belirsizliği doğru mu ölçtü** sorusunu sınıyor. Tahmin kodunda sessiz
hata en tehlikeli hatadır: sayı yine çıkar, kimse fark etmez.

Özellikle korunan davranışlar:
  · Eğilim varsa yön iddiası; yoksa seviye tahmini (yön iddiası YOK).
  · Şoklar kalıcıysa aralık ufukla genişler, geçiciyse genişlemez.
    Yanlış tarafı seçmek aralığı sahte biçimde daraltır.
  · Nokta tahmini her zaman aralığın içinde.
  · Ufuk sınırı: geçmişin üçte birinden ve 3 dönemden fazlası yok.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import tahmin  # noqa: E402

gecti = 0
kaldi = []


def dogrula(ad, kosul, aciklama=''):
    global gecti
    if kosul:
        gecti += 1
        print('  OK    %s' % ad)
    else:
        kaldi.append((ad, aciklama))
        print('  KALDI %s   %s' % (ad, aciklama))


# ------------------------------------------------------------------ 1
# Kusursuz doğrusal seri: eğilim yakalanmalı, tahmin çizgiyi sürdürmeli.
duz = [100.0 + 10 * i for i in range(10)]
t = tahmin.tahminle(duz, 3)
dogrula('dogrusal seride egilim yakalandi', t['durum'] == 'ok', str(t['durum']))
dogrula('egim 10 bulundu', abs(t['egim'] - 10.0) < 1e-6, str(t.get('egim')))
dogrula('ilk nokta cizginin devami',
        abs(t['noktalar'][0]['deger'] - 200.0) < 1e-6,
        str(t['noktalar'][0]['deger']))
dogrula('kusursuz uyumda aralik cok dar',
        t['noktalar'][0]['ust'] - t['noktalar'][0]['alt'] < 1e-6)

# ------------------------------------------------------------------ 2
# Ortalamaya dönen gürültü: eğilim YOK, seviye tahmini gelmeli ve
# aralık ufukla GENİŞLEMEMELİ.
salinim = [100.0, 90.0, 105.0, 95.0, 102.0, 92.0, 104.0, 96.0, 101.0, 93.0]
s = tahmin.tahminle(salinim, 3)
dogrula('salinimli seride egilim yok', s['durum'] == 'seviye', str(s['durum']))
dogrula('alt yontem ortalama', s.get('altYontem') == 'ortalama',
        str(s.get('altYontem')))
dogrula('beklenti ortalamaya esit',
        abs(s['noktalar'][0]['deger'] - sum(salinim) / len(salinim)) < 1e-9)
genislikler = [n['ust'] - n['alt'] for n in s['noktalar']]
dogrula('aralik ufukla genislemiyor',
        max(genislikler) - min(genislikler) < 1e-9, str(genislikler))

# ------------------------------------------------------------------ 3
# Kalıcı şoklu seri: yükselip inen bir kambur. Doğrusal eğilim YOK
# (R²≈0,03) ama komşu dönemler birbirine bağlı (lag-1≈0,6). Doğru
# davranış: beklenti SON DEĞER, aralık ufukla GENİŞLESİN. Bu kırılırsa
# 3 dönem ileri için sahte kesinlik üretiriz.
yuruyus = [100.0, 110, 118, 124, 127, 126, 120, 112, 104, 99]
y = tahmin.tahminle(yuruyus, 3)
dogrula('kalici sokta egilim yok', y['durum'] == 'seviye', str(y['durum']))
dogrula('alt yontem son deger', y.get('altYontem') == 'son_deger',
        'lag-1 %.2f' % y.get('otokorelasyon', 0))
dogrula('beklenti son gerceklesen',
        abs(y['noktalar'][0]['deger'] - yuruyus[-1]) < 1e-9)
g = [n['ust'] - n['alt'] for n in y['noktalar']]
dogrula('aralik ufukla genisliyor', g[-1] > g[0] and g[1] > g[0],
        ['%.1f' % x for x in g])

# Alt yöntem seçiminin kendisi: kalıcı şoklu seri ortalamaya dönmez.
ac_yuruyus = tahmin.otokorelasyon(yuruyus)
ac_salinim = tahmin.otokorelasyon(salinim)
dogrula('otokorelasyon kamburda yuksek, salinimda dusuk',
        ac_yuruyus >= tahmin.OTOKORELASYON_ESIGI > ac_salinim,
        '%.2f vs %.2f' % (ac_yuruyus, ac_salinim))

# ------------------------------------------------------------------ 4
# Kapılar: kısa seri ve ufuk kırpma.
k = tahmin.tahminle([1.0, 2.0, 3.0], 1)
dogrula('kisa seri reddedildi', k['durum'] == 'yetersiz_veri', str(k['durum']))

u = tahmin.tahminle(duz, 12)
dogrula('ufuk kirpildi', u['ufuk'] == 3 and u['kirpildi'],
        'ufuk %s' % u.get('ufuk'))
dogrula('9 donemle ufuk 3', tahmin.azami_ufuk(9) == 3)
dogrula('6 donemle ufuk 2', tahmin.azami_ufuk(6) == 2)

# ------------------------------------------------------------------ 5
# Her durumda: nokta aralığın içinde, alt < üst.
for ad, sonuc in (('dogrusal', t), ('seviye', s)):
    tamam = all(n['alt'] < n['deger'] < n['ust'] or
                n['ust'] - n['alt'] < 1e-6 for n in sonuc['noktalar'])
    dogrula('%s: nokta aralik icinde' % ad, tamam)

print('\n  SONUÇ: %d geçti, %d kaldı' % (gecti, len(kaldi)))
if kaldi:
    sys.exit(1)
