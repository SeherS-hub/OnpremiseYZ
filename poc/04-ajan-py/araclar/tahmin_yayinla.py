# -*- coding: utf-8 -*-
"""
TAHMİN YAYINI — ajanın hesabını dashboard'ların okuyabileceği yere yazar.

Neden ayrı bir araç: tahminin sayısı `lib/tahmin.py`'de üretiliyor.
Dashboard'lar SSAS'tan okuyor. Aynı hesabı DAX'ta ikinci kez yazmak
yerine ajanın çıktısı YAYINLANIYOR — böylece ajanın cevabı ile
dashboard'daki sütun aynı sayıyı gösteriyor. İki hesap = iki cevap,
bu projede kabul edilmiyor.

Zinciri: SSAS (geçmiş seri) → lib/tahmin.py → dbo.Tahmin →
         SSAS tablosu CiroSerisi → SatisDashboard.rdl / .pbix

Kullanım:
    py araclar\\tahmin_yayinla.py                # net_ciro, 3 dönem
    py araclar\\tahmin_yayinla.py --ufuk 2
    py araclar\\tahmin_yayinla.py --metrik net_ciro --metrik hedef
    py araclar\\tahmin_yayinla.py --kuru         # yaz, ama SSAS'ı tazeleme

Modelin veri tazelemesinden SONRA çalıştırılmalı: geçmiş seri değişince
tahmin de değişir. Bayat tahmin, yanlış tahminden daha sinsi bir hatadır;
bu yüzden her satır kendi UretimZamani'nı taşıyor ve rapor onu gösteriyor.
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import calistir_dax                                  # noqa: E402
from lib import ileri_analiz                                  # noqa: E402
from lib import sozlesme as S                                 # noqa: E402
from lib import tahmin                                        # noqa: E402

CIKTI = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def yaz(s=''):
    CIKTI.write(s + '\n')
    CIKTI.flush()


def _sonraki_donem_key(son_etiket, adim):
    """'2026-08' + 1 → (202609, '2026-09'). Model kapsamının ötesi."""
    yil, ay = (int(x) for x in str(son_etiket).split('-'))
    ay += adim
    yil += (ay - 1) // 12
    ay = (ay - 1) % 12 + 1
    return yil * 100 + ay, '%04d-%02d' % (yil, ay)


def uret(metrik_kod, ufuk, ayar):
    """Bir metriğin tahminini hesaplar, satır listesi döner."""
    met = S.metrik_bul(metrik_kod)
    if met is None:
        raise SystemExit('Bilinmeyen metrik: %s' % metrik_kod)

    etiketler, degerler, _ = ileri_analiz._seri_al(met, ayar)
    t = tahmin.tahminle(degerler, ufuk)

    if t['durum'] == 'yetersiz_veri':
        yaz('  %-14s ATLANDI · yetersiz veri (%d dönem, en az %d)'
            % (met['ad'], t['gozlem'], t['gereken']))
        return met['ad'], []

    satirlar = []
    for n in t['noktalar']:
        anahtar, ad = _sonraki_donem_key(etiketler[-1], n['adim'])
        satirlar.append((met['ad'], anahtar, ad, n['deger'], n['alt'], n['ust'],
                         t['yontem'], round(t.get('r2') or 0.0, 4), t['gozlem']))

    tur = 'EĞİLİM' if t['durum'] == 'ok' else 'SEVİYE'
    yaz('  %-14s %s · %d dönem · R²=%.2f · %s'
        % (met['ad'], tur, len(satirlar), t.get('r2') or 0.0, t['yontem']))
    for s in satirlar:
        yaz('      %s  %14.0f   [%14.0f – %14.0f]' % (s[2], s[3], s[4], s[5]))
    return met['ad'], satirlar


def sqlye_yaz(tum_satirlar, ayar):
    """Metrik bazında sil-yaz. Eski ufuk yeni ufuktan uzunsa artık
    satırlar kalmasın diye önce siliniyor."""
    import pyodbc
    cs = ('Driver={ODBC Driver 18 for SQL Server};Server=%s;Database=%s;'
          'Trusted_Connection=yes;Encrypt=no;'
          % (ayar['sqlSunucu'], ayar['sqlVeritabani']))
    cn = pyodbc.connect(cs, autocommit=False)
    try:
        im = cn.cursor()
        for metrik_ad, satirlar in tum_satirlar:
            im.execute('DELETE FROM dbo.Tahmin WHERE Metrik = ?', metrik_ad)
            if satirlar:
                im.executemany(
                    'INSERT INTO dbo.Tahmin (Metrik, DonemKey, DonemAd, Deger, '
                    'Alt, Ust, Yontem, R2, Gozlem) VALUES (?,?,?,?,?,?,?,?,?)',
                    satirlar)
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


def modeli_tazele(ayar):
    """CiroSerisi tablosunu işle — yalnız o tabloyu, tüm modeli değil.

    pyadomd kullanılmıyor: onun `execute`'u ExecuteReader çağırıyor, TMSL
    komutu ise rowset döndürmüyor ("The result set returned by the server
    is not a rowset"). Komut arayüzüne doğrudan iniyoruz.
    """
    calistir_dax._pyadomd()          # ADOMD dizinlerini sys.path'e ekler
    from Microsoft.AnalysisServices.AdomdClient import AdomdConnection

    tmsl = ('{"refresh":{"type":"full","objects":'
            '[{"database":"%s","table":"CiroSerisi"}]}}' % ayar['ssasModel'])
    cs = 'Data Source=%s;Catalog=%s;' % (ayar['ssasSunucu'], ayar['ssasModel'])
    con = AdomdConnection(cs)
    con.Open()
    try:
        im = con.CreateCommand()
        im.CommandText = tmsl
        im.CommandTimeout = 600
        im.ExecuteNonQuery()
    finally:
        con.Close()


def main():
    ap = argparse.ArgumentParser(description='Tahmini SQL\'e yayınla')
    ap.add_argument('--metrik', action='append', default=None,
                    help='metrik kodu (yinelenebilir); varsayılan net_ciro')
    ap.add_argument('--ufuk', type=int, default=3)
    ap.add_argument('--kuru', action='store_true',
                    help='SQL\'e yaz ama SSAS tablosunu tazeleme')
    ap.add_argument('--sunucu', default=os.environ.get('POC_SSAS_SUNUCU',
                                                       r'localhost\TABULAR'))
    ap.add_argument('--model', default=os.environ.get('POC_SSAS_MODEL', 'POC_Satis'))
    a = ap.parse_args()

    ayar = {'ssasSunucu': a.sunucu, 'ssasModel': a.model,
            'sqlSunucu': os.environ.get('POC_SQL_SUNUCU', 'localhost'),
            'sqlVeritabani': os.environ.get('POC_SQL_VT', 'POC_SatisYZ')}

    yaz('')
    yaz('  TAHMİN YAYINI · %s / %s' % (a.sunucu, a.model))
    yaz('  ' + '─' * 72)

    kodlar = a.metrik or ['net_ciro']
    tum = [uret(k, a.ufuk, ayar) for k in kodlar]

    sqlye_yaz(tum, ayar)
    yaz('')
    yaz('  dbo.Tahmin yazıldı (%d satır)' % sum(len(s) for _, s in tum))

    if a.kuru:
        yaz('  SSAS tazelenmedi (--kuru). Rapor eski tahmini gösterir.')
    else:
        modeli_tazele(ayar)
        yaz('  SSAS · CiroSerisi tablosu tazelendi')

    calistir_dax.kapat()
    yaz('')


if __name__ == '__main__':
    main()
