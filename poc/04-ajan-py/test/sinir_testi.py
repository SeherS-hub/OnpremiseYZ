# -*- coding: utf-8 -*-
"""
SINIR TESTİ — ajanın sınırlarını ölçer: hangi soruya cevap veriyor,
hangisini reddediyor.

Altın küme ve eşanlam testi İDDİALIDIR (geçti/kaldı). Bu ise KEŞİF
amaçlıdır: çıktıyı insan okur. Amaç bir eşiği doğrulamak değil,
davranışın haritasını görmek — özellikle F bloğu (tamamen anlamsız
girdiler) ajanın uydurmadığını gözle doğrulatır.

Çalışan bir ajan gerektirir (HTTP üzerinden sorar), çünkü ölçtüğü şey
planlayıcı değil UÇTAN UCA davranış.

Çalıştırma:
    python test/sinir_testi.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ADRES = os.environ.get('POC_AJAN_URL', 'http://localhost:8787') + '/api/sor'

SORULAR = [
    ('A · altın kümedeki ifadeler', [
        'Ağustos ayı net ciromuz ne kadar?',
        'Temmuz ayında hedefi tuttuk mu?',
    ]),
    ('B · aynı şeyin farklı söylenişi', [
        'temmuz hasılatı neydi',
        'ağustosta ne kadar sattık',
        'mayıs ayındaki gelirimiz',
        'haziranda kaç adet ürün satıldı',
        'nisan ayı müşteri sayımız kaç',
        'ortalama sepet tutarı nedir',
        'geçen ay ciro',
        'son 3 ayın ortalaması ne',
    ]),
    ('C · modelde ölçü VAR ama sözleşmede yok', [
        'kümülatif ciro ne kadar',
        'hedef sapması ne kadar',
        'kaç ay hedefi tutturduk',
        'önceki ay cirosu neydi',
    ]),
    ('D · sözdizimi zor / yapı karmaşık', [
        'Marmara ve Ege bölgelerini karşılaştır',
        'ürün grubuna göre ciro ve hedef gerçekleşmesini birlikte göster',
        'ciro neden düştü',
        'en kötü performans gösteren kanal hangisi',
        'Şubat ve mart ayı cirolarını karşılaştır.',
    ]),
    ('E · kapsam ve yetki dışı', [
        'Rakiplerin pazar payı ne oldu?',
        'Ahmet Yılmaz’ın maaşı ne kadar?',
        'gelecek ay ciro ne olur',
        'stok durumu nedir',
        'Bu yıl en çok kâr edilen ay hangisi?',
        'Buzdolabı satışları ne durumda?',
    ]),
    ('F · tamamen anlamsız', [
        'asdfgh qwerty',
        'hava bugün nasıl',
        'sen kimsin',
        'merhaba',
        '?????',
        'bana bir şiir yaz',
    ]),
]


def sor(soru):
    govde = json.dumps({'soru': soru}, ensure_ascii=False).encode('utf-8')
    istek = urllib.request.Request(
        ADRES, data=govde,
        headers={'Content-Type': 'application/json; charset=utf-8'})
    with urllib.request.urlopen(istek, timeout=60) as y:
        return json.loads(y.read().decode('utf-8'))


def main():
    print('')
    print('  Ajan: %s' % ADRES)
    for baslik, liste in SORULAR:
        print('')
        print('=== %s %s' % (baslik, '=' * max(0, 66 - len(baslik))))
        for s in liste:
            try:
                c = sor(s)
            except (urllib.error.URLError, OSError) as e:
                print('  ! %s -> istek hatası: %s' % (s, e))
                continue

            durum = (c.get('durum') or '?').upper().ljust(12)
            spec = c.get('spesifikasyon') or {}
            metrik = '+'.join(spec.get('metrikler') or []) or '—'
            kunye = c.get('kunye') or {}
            guven = ('%d%%' % round(kunye['guven'] * 100)) \
                if isinstance(kunye.get('guven'), (int, float)) else '—'
            cevap = ' '.join((c.get('cevap') or '').replace('**', '').split())
            if len(cevap) > 105:
                cevap = cevap[:105] + '…'

            print('  %s | %-22s | %4s | %s' % (durum, metrik[:22], guven, s))
            print('  %s | %s |      > %s' % (' ' * 12, ' ' * 22, cevap))
    print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
