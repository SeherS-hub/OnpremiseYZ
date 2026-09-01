# -*- coding: utf-8 -*-
"""
SÖZLÜK BOŞLUĞU ÇÖZÜMLEYİCİSİ

Kural tabanlı bir dil arayüzü eğitilmez, ZENGİNLEŞTİRİLİR. Bu araç o
döngünün motoru: denetim kaydındaki gerçek soruları okur ve sözleşmeye
neyin eklenmesi gerektiğini önem sırasına göre söyler.

Node sürümü `sqlcmd`'ye kabuk çağrısı yapıyordu ve çıktıyı UTF-16
dosyadan okumak zorundaydı — "bölgelerini" kelimesi "b?lgelerini" olup
belirteç ayrıştırması yanlış kelimeler üretiyordu. Burada `pyodbc`;
kod sayfası sorunu yok.

Kullanım:
    python araclar/sozluk_bosluk.py
    python araclar/sozluk_bosluk.py --gun 30 --en-az 2
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pyodbc                                                  # noqa: E402
from lib import sozlesme as S                                  # noqa: E402
from lib import dilbilgisi as dil                              # noqa: E402


def arg(ad, varsayilan=None):
    if '--' + ad in sys.argv:
        i = sys.argv.index('--' + ad)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return varsayilan


SUNUCU = arg('sunucu', os.environ.get('POC_SQL_SUNUCU', 'localhost'))
VT = arg('vt', os.environ.get('POC_SQL_DB', 'POC_SatisYZ'))
GUN = int(arg('gun', 90))
EN_AZ = int(arg('en-az', 1))

# Soruların doğal parçası olan, sözleşmeye girmesi anlamsız kelimeler.
# Bunlar raporda gürültü yapar; ayıklanıyor.
DURAK = {
    'ne', 'kadar', 'nedir', 'neydi', 'kac', 'kaci', 'mi', 'mu',
    've', 'ile', 'icin', 'gibi', 'daha', 'en', 'bir', 'bu', 'su', 'o',
    'var', 'yok', 'oldu', 'olur', 'olacak', 'nasil', 'hangi', 'nerede',
    'bana', 'bize', 'lutfen', 'soyle', 'soyler', 'misin', 'musun',
    'goster', 'gosterir', 'ver', 'verir', 'ogrenebilir', 'miyim',
    'yapti', 'yaptik', 'ettik', 'etti', 'toplam', 'genel',
}


def kayitlari_oku():
    cs = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=%s;DATABASE=%s;'
          'Trusted_Connection=yes;TrustServerCertificate=yes;' % (SUNUCU, VT))
    with pyodbc.connect(cs, timeout=15) as cn:
        cur = cn.cursor()
        # Açılış ısınma kaydı gerçek bir soru değil; her yeniden
        # başlatmada 'hata' sayısını şişirip cevaplama oranını
        # yanlış gösteriyordu. Ölçümün kirlenmemesi için ayıklanıyor.
        cur.execute("""
            SELECT Durum, Soru, ISNULL(Metrikler, '')
            FROM denetim.AjanKayit
            WHERE Zaman >= DATEADD(DAY, -?, SYSDATETIME())
              AND Soru <> N'(ısınma)'
            ORDER BY KayitId
        """, GUN)
        return [{'durum': (r[0] or '').strip(),
                 'soru': (r[1] or '').strip(),
                 'metrikler': (r[2] or '').strip()}
                for r in cur.fetchall() if r[1]]


def bilinmeyenler(soru):
    c = dil.metni_cozumle(S.normalize(soru), S.TUM_BELIRTECLER)
    return [t for t in c.ham
            if len(t) >= 3
            and not t.isdigit()
            and t not in DURAK
            # gövde kesişimi de tutmuyorsa gerçekten sözlükte yok
            and not any(a in S.TUM_BELIRTECLER for a in dil.eslesme_adaylari(t))]


def sirala(kayitlar, suzgec):
    sayac, ornek = {}, {}
    for k in kayitlar:
        if not suzgec(k):
            continue
        for t in set(bilinmeyenler(k['soru'])):
            sayac[t] = sayac.get(t, 0) + 1
            ornek.setdefault(t, k['soru'])
    return sorted(((t, n, ornek[t]) for t, n in sayac.items() if n >= EN_AZ),
                  key=lambda x: (-x[1], x[0]))


def bolum(baslik):
    print('')
    print('  ' + baslik)
    print('  ' + '-' * 72)


def main():
    print('')
    print('  Denetim kaydı okunuyor: %s / %s  (son %d gün)' % (SUNUCU, VT, GUN))
    try:
        kayitlar = kayitlari_oku()
    except Exception as e:
        print('  Denetim kaydı okunamadı: %s' % str(e).split('\n')[0])
        return 1

    if not kayitlar:
        print('  Kayıt yok. Ajan kullanılmaya başlanmadan bu araç bir şey söylemez —')
        print('  zenginleştirmenin girdisi gerçek sorulardır.')
        return 0

    durumlar = {}
    for k in kayitlar:
        durumlar[k['durum']] = durumlar.get(k['durum'], 0) + 1

    print('')
    print('  %d soru' % len(kayitlar))
    for d in sorted(durumlar, key=lambda x: -durumlar[x]):
        print('    %-14s %6d   %%%d' % (d, durumlar[d],
                                        round(durumlar[d] * 100.0 / len(kayitlar))))
    print('')
    print('  CEVAPLAMA ORANI: %%%d   — zenginleştirmenin tek özet göstergesi budur.'
          % round(durumlar.get('ok', 0) * 100.0 / len(kayitlar)))

    # 1) reddedilen sorulardaki bilinmeyenler
    bolum('1 · REDDEDİLEN sorulardaki bilinmeyen kelimeler  (eklenecekler listesi)')
    redler = sirala(kayitlar, lambda k: k['durum'] == 'kapsam_disi')
    if not redler:
        print('    yok')
    else:
        for t, n, o in redler[:30]:
            print('    %4d  %-22s  örnek: %s' % (n, t[:22], o[:46]))
        print('')
        print('    Her kelime için karar: (a) var olan bir ölçünün eşanlamlısı mı,')
        print('    (b) modelde olmayan bir konu mu — o zaman KAPSAM_DISI desenine')
        print('    gerekçesiyle girmeli, (c) modelde olan ama o AYRINTIDA olmayan')
        print('    bir kırılım mı — o da MEVCUT_OLMAYAN listesine.')
        print('    Hiçbiri kod değişikliği değildir; hepsi sözleşmeye yazılır.')

    # 2) netleştirme kümeleri
    bolum('2 · NETLEŞTİRME istenen sorular  (ayırt edici kalıp gerekiyor)')
    netler = [k for k in kayitlar if k['durum'] == 'netlestir']
    if not netler:
        print('    yok')
    else:
        sayac = {}
        for k in netler:
            sayac[k['soru']] = sayac.get(k['soru'], 0) + 1
        for s in sorted(sayac, key=lambda x: -sayac[x])[:15]:
            print('    %4d  %s' % (sayac[s], s[:64]))
        print('')
        print('    Bunların çözümü eşanlamlı EKLEMEK değil. İki ölçü aynı kelimeye')
        print('    uyuyorsa yeni eşanlamlı belirsizliği artırır. Yapılacak: daha')
        print('    UZUN ve ayırt edici kalıp yazmak — eşleştirici en uzun kalıbı')
        print('    seçtiği için belirsizlik kendiliğinden çözülür.')

    # 3) cevaplanan ama bilinmeyen kelime içeren sorular
    bolum('3 · CEVAPLANAN sorulardaki bilinmeyen kelimeler  (gözden geçir)')
    okb = sirala(kayitlar, lambda k: k['durum'] == 'ok')
    if not okb:
        print('    yok')
    else:
        for t, n, o in okb[:20]:
            print('    %4d  %-22s  örnek: %s' % (n, t[:22], o[:46]))
        print('')
        print('    Bu sorular cevaplandı ama içlerinde tanımadığımız kelime var:')
        print('    eşleşme sorunun BAŞKA bir parçasından gelmiş olabilir. Cevabın')
        print('    doğru olduğunu varsaymayın; birkaçını elle doğrulayın.')

    # 4) en sık sorulanlar
    bolum('4 · EN SIK SORULANLAR  (altın kümeye girmeli)')
    sik = {}
    for k in kayitlar:
        sik[k['soru']] = sik.get(k['soru'], 0) + 1
    for s in sorted(sik, key=lambda x: -sik[x])[:12]:
        print('    %4d  %s' % (sik[s], s[:64]))
    print('')
    print('    Sık sorulan her soru test/esanlam-durumlar.json dosyasına girmeli.')
    print('    Bir kez doğru cevaplandıktan sonra bir daha bozulmasın.')

    print('')
    print('  ' + '=' * 74)
    print("  DÖNGÜ: bu raporu oku → sözleşmeye ekle → esanlam testini genişlet")
    print('  → koş → cevaplama oranını tekrar ölç.')
    print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
