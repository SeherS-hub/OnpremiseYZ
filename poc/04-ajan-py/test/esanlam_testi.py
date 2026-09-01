# -*- coding: utf-8 -*-
"""
EŞANLAM / SÖYLEYİŞ ÇEŞİTLİLİĞİ TESTİ — Python portu.

Vaka listesi Node sürümüyle AYNI dosyadan okunur (test/esanlam-durumlar.json).
Parite iddiası ancak iki taraf aynı listeyi koşarsa anlamlıdır; listeyi iki
yerde tutmak sessizce ayrışmaya davetiye çıkarır.

Listeyi tazelemek için:
    POC_KUME_DOK=1 node ../04-ajan/test/esanlam-testi.js > test/esanlam-durumlar.json

Çalıştırma:
    python test/esanlam_testi.py
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import planlayici                                    # noqa: E402

DURUM_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'esanlam-durumlar.json')


def degerlendir(spec, b):
    if b.get('durum'):
        return spec['durum'] == b['durum']
    if spec['durum'] != 'ok':
        return False
    if b.get('metrik') and (not spec['metrikler'] or spec['metrikler'][0] != b['metrik']):
        return False
    if 'boyut' in b and b['boyut'] is None and spec['boyutlar']:
        return False
    if b.get('boyut') and b['boyut'] not in spec['boyutlar']:
        return False
    if b.get('limit') and spec.get('limit') != b['limit']:
        return False
    return True


def ozet(spec):
    if spec['durum'] != 'ok':
        return spec['durum']
    s = '+'.join(spec['metrikler'])
    if spec['boyutlar']:
        s += ' /' + ','.join(spec['boyutlar'])
    if spec.get('limit'):
        s += ' limit:%s' % spec['limit']
    return s


def main():
    with io.open(DURUM_DOSYASI, encoding='utf-8-sig') as f:
        kume = json.load(f)

    gecti = kaldi = 0
    kalanlar = []

    print('')
    print('  dilbilgisi: %s' % ('zeyrek' if os.environ.get('POC_DILBILGISI', '') == 'zeyrek' else 'kural'))
    print('')
    for baslik, liste in kume:
        print('  ' + baslik)
        print('  ' + '-' * 72)
        for t in liste:
            try:
                spec = planlayici.planla(t['s'])
            except Exception as e:
                spec = {'durum': 'HATA:' + str(e), 'metrikler': [], 'boyutlar': []}
            ok = degerlendir(spec, t['b'])
            if ok:
                gecti += 1
            else:
                kaldi += 1
                kalanlar.append((t['s'], ozet(spec)))
            b = t['b']
            bekleniyor = b.get('durum') or (
                str(b.get('metrik'))
                + (' /' + b['boyut'] if b.get('boyut') else (' /—' if 'boyut' in b else ''))
                + (' limit:%s' % b['limit'] if b.get('limit') else ''))
            print('    %-5s %-44s bekle: %-28s gelen: %s'
                  % ('OK' if ok else 'KALDI', t['s'][:44], str(bekleniyor)[:28], ozet(spec)))
        print('')

    print('  ' + '=' * 74)
    print('  KAPSAMA: %d/%d  (%%%d)' % (gecti, gecti + kaldi,
                                        round(gecti * 100.0 / (gecti + kaldi))))
    if kalanlar:
        print('')
        print('  Kalanlar:')
        for s, o in kalanlar:
            print('    · %s   → %s' % (s, o))
    print('')
    return 0 if kaldi == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
