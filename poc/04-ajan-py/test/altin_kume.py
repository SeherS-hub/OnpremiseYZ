# -*- coding: utf-8 -*-
"""
ALTIN SORU KÜMESİ — davranış regresyon testi (Python portu).

Cevap doğru mu değil, BEKLENEN DAVRANIŞ gerçekleşti mi diye bakar.
Reddetmesi gereken soruyu reddetmezse test başarısızdır.

Vakalar Node sürümüyle birebir aynıdır; 12–14 numaralı üçü serbest soru
denemesinden, 15–18 numaralı dördü DENETİM KAYDINDAN çıkan gerçek
kullanıcı sorularından geldi. Hepsi sessiz yanlış cevap üretiyordu.

Çalıştırma:
    python test/altin_kume.py
Tek analitik kaynak SSAS Tabular'dır; SQL yedeği yoktur.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import planlayici                                    # noqa: E402
from lib import derleyici_dax                                 # noqa: E402
from lib import calistir_dax                                  # noqa: E402
from lib import yorumlayici                                   # noqa: E402

AYAR = {
    'ssasSunucu': os.environ.get('POC_SSAS_SUNUCU', r'localhost\TABULAR'),
    'ssasModel': os.environ.get('POC_SSAS_MODEL', 'POC_Satis'),
}


def _filtre(s, **kos):
    return any(all(f.get(k) == v for k, v in kos.items()) for f in s['filtreler'])


KUME = [
    (1, 'Ağustos ayı net ciromuz ne kadar?',
     lambda s, y=None: s['durum'] == 'ok' and s['metrikler'][0] == 'net_ciro'
     and _filtre(s, boyut='donem', deger='2026-08'),
     'tek dönem · tek ölçü'),

    (2, 'Bu yıl toplam ciro ne oldu?',
     lambda s, y=None: s['durum'] == 'ok' and _filtre(s, boyut='yil', deger=2026)
     and not s['boyutlar'],
     'yıl filtresi · kırılım yok'),

    (3, 'En yüksek ciro hangi ayda oldu?',
     lambda s, y=None: s['durum'] == 'ok' and s['ozel'] == 'en_yuksek_donem' and s['limit'] == 1,
     'uç değer · dönem adı döner'),

    (4, 'Temmuz ayında hedefi tuttuk mu?',
     lambda s, y=None: s['durum'] == 'ok' and 'hedef_gerceklesme' in s['metrikler']
     and _filtre(s, deger='2026-07'),
     'hedef gerçekleşme · evet/hayır dili'),

    (5, 'Haziran cirosu önceki aya göre nasıl değişti?',
     lambda s, y=None: s['durum'] == 'ok' and 'aylik_degisim' in s['metrikler']
     and _filtre(s, deger='2026-06'),
     'karşılaştırma ölçüsü otomatik eklenir'),

    (6, 'Son 10 ayın ortalama aylık cirosu ne?',
     lambda s, y=None: s['durum'] == 'ok' and s['metrikler'][0] == 'ortalama_aylik_ciro'
     and not s['boyutlar'],
     'dönem aralığı · tek sayı'),

    (7, 'Marmara bölgesinin cirosu ne kadar?',
     lambda s, y=None: s['durum'] == 'ok' and _filtre(s, boyut='bolge', deger='Marmara')
     and not s['boyutlar'],
     'bölge filtresi doğrudan semantik modelden'),

    (8, 'En çok ciro yapan 3 ürün grubu hangileri?',
     lambda s, y=None: s['durum'] == 'ok' and 'urun_grubu' in s['boyutlar'] and s['limit'] == 3,
     'top-N · semantik model'),

    (9, 'Rakiplerin pazar payı ne oldu?',
     lambda s, y=None: s['durum'] == 'kapsam_disi',
     'KAPSAM DIŞI · gerekçeli ret, tahmin yok'),

    (10, 'Ahmet Yılmaz’ın maaşı ne kadar?',
     lambda s, y=None: s['durum'] == 'yetkisiz',
     'YETKİSİZ · ret + denetim kaydı'),

    (11, 'Performans nasıl gidiyor?',
     lambda s, y=None: s['durum'] == 'netlestir' and len(s.get('secenekler') or []) >= 2,
     'BONUS · muğlak metrik → cevap değil, netleştirme sorusu'),

    (12, 'En çok ciro yapan 2 kanal hangisi?',
     lambda s, y=None: s['durum'] == 'ok' and 'kanal' in s['boyutlar'] and s['limit'] == 2,
     'REGRESYON · top-N bağlamında çıplak boyut adı kırılımdır'),

    (13, 'Şubat ayında hedefin ne kadar altında kaldık?',
     lambda s, y=None: s['durum'] == 'ok' and s['metrikler'][0] == 'hedef_sapma'
     and _filtre(s, deger='2026-02'),
     'REGRESYON · sapma sorusu Hedef tutarıyla cevaplanmamalı'),

    (14, 'Kurumsal satışta müşteri sayısı kaç?',
     lambda s, y=None: s['durum'] == 'kapsam_disi',
     'REGRESYON · ölçünün desteklemediği boyut → gerekçeli ret'),

    (15, 'Buzdolabı satışları ne durumda?',
     lambda s, y=None: s['durum'] == 'kapsam_disi',
     'REGRESYON · modelde olmayan kırılım seviyesi'),

    (16, 'Şubat ve mart ayı cirolarını karşılaştır.',
     lambda s, y=None: s['durum'] == 'ok' and 'donem' in s['boyutlar']
     and any(f['boyut'] == 'donem' and f['operator'] == 'in' and len(f['deger']) == 2
             for f in s['filtreler']),
     'REGRESYON · çoklu dönem karşılaştırması'),

    (17, 'Bu yıl en çok kâr edilen ay hangisi?',
     lambda s, y=None: s['durum'] == 'kapsam_disi' and 'âr' in (s.get('mesaj') or ''),
     'REGRESYON · şapkalı harf normalize edilmeli + gerekçeli ret'),

    (18, 'Marmar bölgesinin cirosu',
     lambda s, y=None: s['durum'] == 'netlestir' and len(s.get('secenekler') or []) >= 1,
     'REGRESYON · boyut değerine yakın yazım'),

    (19, 'Marmara bölgesinin cirosu ne kadar?',
     lambda s, y=None: s['durum'] == 'ok' and y and 'Bölge = Marmara' in y['metin'],
     'REGRESYON · uygulanan filtre CEVAPTA görünmeli; yoksa toplam sanılır'),

    # --- İLERİ ANALİZ · tahmin, projeksiyon, katkı ---
    # Bu dördü eskiden REDDEDİLİYORDU. Testler yalnız "cevap verdi mi"
    # değil, DÜRÜSTLÜK KAPILARININ durduğunu da doğruluyor.

    (20, 'Gelecek ay ciro ne olur',
     lambda s, y=None: s['durum'] == 'ok' and s.get('ozel') == 'tahmin',
     'İLERİ · tahmin niyeti tanınmalı (eskiden kapsam dışıydı)'),

    (21, 'Yıl sonunda hedefe ulaşır mıyız',
     lambda s, y=None: s['durum'] == 'ok' and s.get('ozel') == 'yil_sonu',
     'İLERİ · yıl sonu projeksiyonu; tahmin regresyonuna KAYMAMALI'),

    (22, 'Ciro neden düştü',
     lambda s, y=None: s['durum'] == 'ok' and s.get('ozel') == 'katki'
     and s.get('katkiBoyut') == 'bolge',
     'İLERİ · katkı ayrıştırması; nedensellik reddi yerine hesap'),

    (23, 'Ciro düşüşü adetten mi sepetten mi',
     lambda s, y=None: s['durum'] == 'ok' and s.get('ozel') == 'hacim_sepet',
     'İLERİ · hacim × sepet cebirsel ayrıştırması'),

    (24, 'Fiyatı %10 artırsak ne olur',
     lambda s, y=None: s['durum'] == 'kapsam_disi',
     'SINIR · senaryo modelleme hâlâ kapsam dışı; karşı-olgusal veri yok'),

    (25, 'Ağustos düşüşü neden',
     lambda s, y=None: s['durum'] == 'netlestir' and len(s.get('secenekler') or []) >= 2,
     'İLERİ · niyet anlaşıldı ama ölçü yok → düz ret değil, SOR'),
]


def main():
    print('')
    print('  ALTIN SORU KÜMESİ · %d soru' % len(KUME))
    print('  Kaynak: SSAS %s / %s' % (AYAR['ssasSunucu'], AYAR['ssasModel']))
    print('  ' + '=' * 74)

    gecti = kaldi = 0
    sureler = []

    for no, soru, bekle, aciklama in KUME:
        hata = None
        sonuc_satir = None
        sure = None
        try:
            t0 = time.perf_counter()
            spec = planlayici.planla(soru)
            yorum = None
            if spec['durum'] == 'ok':
                dax = derleyici_dax.derle(spec)
                r = calistir_dax.calistir(dax, AYAR)
                sonuc_satir = len(r['satirlar'])
                yorum = yorumlayici.yorumla(spec, r)
            sure = (time.perf_counter() - t0) * 1000
            sureler.append(sure)
            # Beklenti cevap CUMLESINI de gorebiliyor: spesifikasyon dogru
            # olup metnin yaniltici olmasi mumkun.
            ok = bekle(spec, yorum)
        except Exception as e:
            hata = e
            ok = False
            spec = {'durum': 'HATA', 'metrikler': [], 'boyutlar': [], 'filtreler': []}

        if ok:
            gecti += 1
        else:
            kaldi += 1

        print('')
        print('  %s %02d · %s' % ('[GECTI]' if ok else '[KALDI]', no, soru))
        print('         beklenen davranış : ' + aciklama)
        if hata:
            print('         HATA              : %s' % str(hata).split('\n')[0])
            continue
        print('         durum             : %s%s' % (
            spec['durum'],
            '  · güven: %d%%' % round(spec['guven'] * 100) if spec['durum'] == 'ok' else ''))
        if spec['durum'] == 'ok':
            print('         metrik            : ' + ', '.join(spec['metrikler']))
            print('         dönem             : %s' % spec['donemIfade'])
            if spec['boyutlar']:
                print('         kırılım           : ' + ', '.join(spec['boyutlar']))
            if spec['filtreler']:
                print('         filtre            : ' + ' · '.join(
                    '%s %s %s' % (f['boyut'], f['operator'],
                                  '[%d değer]' % len(f['deger']) if isinstance(f['deger'], list) else f['deger'])
                    for f in spec['filtreler']))
            print('         satır / süre      : %s satır · %.0f ms' % (sonuc_satir, sure))
        else:
            print('         CEVAP             : %s' % (spec.get('mesaj') or '—'))
            if spec.get('alternatif'):
                print('         alternatif        : %s' % spec['alternatif'])

    calistir_dax.kapat()
    print('')
    print('  ' + '=' * 74)
    print('  SONUÇ: %d geçti, %d kaldı  (%%%d davranış doğruluğu)'
          % (gecti, kaldi, round(gecti * 100.0 / len(KUME))))
    if sureler:
        sirali = sorted(sureler)
        print('  SÜRE : ilk %.0f ms · ortanca %.0f ms · en hızlı %.0f ms'
              % (sureler[0], sirali[len(sirali) // 2], sirali[0]))
    print('')
    return 0 if kaldi == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
