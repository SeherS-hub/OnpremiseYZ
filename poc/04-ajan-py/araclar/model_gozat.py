# -*- coding: utf-8 -*-
r"""
MODEL GÖZATICI — SSAS Tabular modelini konsoldan inceler.

SSMS 21+ Analysis Services Object Explorer desteğini kaldırdı; bu makinede
SSMS 22'de Analysis Services bileşeni yok. Bu araç o boşluğu doldurur:
hiçbir şey kurmadan, zaten kullandığımız XMLA yolundan modelin tamamını
okur.

SSMS'in yerini tutmaz — düzenleme yok, işleme yok. Ama günlük soruları
cevaplar: bu ölçünün DAX'ı ne, hangi kolon gizli, ilişkiler nasıl kurulmuş,
rollerde hangi satır filtresi var, tablolar kaç satır.

Kullanım:
    python araclar\model_gozat.py                      # tam özet
    python araclar\model_gozat.py --veritabanlari      # sunucudaki modeller
    python araclar\model_gozat.py --tablo Satis        # tek tablo ayrıntısı
    python araclar\model_gozat.py --olcu "Net Ciro"    # ölçünün DAX'ı
    python araclar\model_gozat.py --ara ciro           # ad araması
    python araclar\model_gozat.py --dax "EVALUATE ROW(\"x\", [Net Ciro])"
    python araclar\model_gozat.py --dax-dosya sorgu.dax
    python araclar\model_gozat.py --satir-sayma-yok    # hızlı, sayım atlanır
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import calistir_dax                                   # noqa: E402


def arg(ad, varsayilan=None):
    if '--' + ad in sys.argv:
        i = sys.argv.index('--' + ad)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('--'):
            return sys.argv[i + 1]
        return True
    return varsayilan


SUNUCU = arg('sunucu', os.environ.get('POC_SSAS_SUNUCU', r'localhost\TABULAR'))
MODEL = arg('model', os.environ.get('POC_SSAS_MODEL', 'POC_Satis'))
AYAR = {'ssasSunucu': SUNUCU, 'ssasModel': MODEL}

# TOM DataType numaralandırması — DMV sayı döndürüyor, insan okusun diye.
VERI_TURU = {
    1: 'Otomatik', 2: 'Metin', 6: 'Tamsayı', 8: 'Ondalık', 9: 'Tarih',
    10: 'Para/Decimal', 11: 'Mantıksal', 17: 'İkili', 19: 'Bilinmiyor',
    20: 'Değişken',
}
IZIN = {1: 'Yok', 2: 'Oku', 3: 'Oku+İşle', 4: 'İşle', 5: 'Yönetici'}
KARDINALITE = {1: 'bir', 2: 'çok'}
# Bölüm durumu — DMV sayı döndürüyor, insan okusun diye.
BOLUM_DURUM = {1: 'Hazır', 3: 'Veri yok', 4: 'Hesap gerekli', 5: 'Anlam hatası',
               6: 'Değerlendirme hatası', 7: 'Bağımlılık hatası', 8: 'Eksik',
               9: 'Sözdizimi hatası'}
SUZME = {1: 'tek yön', 2: 'çift yön'}


def dogru(v):
    return str(v).lower() == 'true' or v is True


def cizgi(baslik=''):
    if baslik:
        print('')
        print('  ' + baslik)
        print('  ' + '─' * 74)
    else:
        print('  ' + '─' * 74)


def tablo_yaz(basliklar, satirlar, girinti='    '):
    """Hizalanmış metin tablosu."""
    if not satirlar:
        print(girinti + '(yok)')
        return
    gen = [len(str(b)) for b in basliklar]
    for s in satirlar:
        for i, h in enumerate(s):
            gen[i] = max(gen[i], len(str(h)))
    gen = [min(g, 46) for g in gen]

    def satir(hucreler):
        return girinti + '  '.join(str(h)[:gen[i]].ljust(gen[i]) for i, h in enumerate(hucreler))

    print(satir(basliklar))
    print(girinti + '  '.join('─' * g for g in gen))
    for s in satirlar:
        print(satir(s))


def dmv(sorgu):
    try:
        return calistir_dax.calistir(sorgu, AYAR)['satirlar']
    except Exception as e:
        print('    ! okunamadı: %s' % str(e).split('\n')[0][:120])
        return []


# --------------------------------------------------------------------
def veritabanlarini_listele():
    print('')
    print('  Sunucu: %s' % SUNUCU)
    cizgi('VERİTABANLARI')
    # Katalog listesi model bağlamı gerektirmez.
    eski = AYAR.get('ssasModel')
    AYAR['ssasModel'] = ''
    satirlar = dmv('SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS')
    AYAR['ssasModel'] = eski
    for s in satirlar:
        print('    %s' % list(s.values())[0])
    print('')


def dax_calistir(sorgu):
    print('')
    print('  %s / %s' % (SUNUCU, MODEL))
    cizgi('DAX')
    for satir in sorgu.strip().split('\n'):
        print('    │ ' + satir)
    try:
        r = calistir_dax.calistir(sorgu, AYAR)
    except Exception as e:
        print('')
        print('  HATA: %s' % str(e).split('\n')[0])
        return 1
    satirlar = r['satirlar']
    cizgi('SONUÇ · %d satır · %d ms' % (len(satirlar), r['sureMs']))
    if satirlar:
        basliklar = list(satirlar[0].keys())
        tablo_yaz(basliklar, [[s.get(b) for b in basliklar] for s in satirlar])
    else:
        print('    (satır yok)')
    print('')
    return 0


def model_oku():
    """Tüm şemayı tek turda çeker; kalıcı bağlantıda maliyeti birkaç ms."""
    s = {}
    s['tablolar'] = dmv('SELECT [ID], [Name], [IsHidden], [Description] '
                        'FROM $SYSTEM.TMSCHEMA_TABLES')
    s['kolonlar'] = dmv('SELECT [ID], [TableID], [ExplicitName], [InferredName], '
                        '[ExplicitDataType], [IsHidden], [IsKey], [SortByColumnID], '
                        '[FormatString], [Description] FROM $SYSTEM.TMSCHEMA_COLUMNS')
    s['olculer'] = dmv('SELECT [ID], [TableID], [Name], [Expression], [FormatString], '
                       '[IsHidden], [DisplayFolder], [Description] '
                       'FROM $SYSTEM.TMSCHEMA_MEASURES')
    s['iliskiler'] = dmv('SELECT [FromTableID], [FromColumnID], [ToTableID], [ToColumnID], '
                         '[IsActive], [CrossFilteringBehavior], [FromCardinality], '
                         '[ToCardinality] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS')
    s['roller'] = dmv('SELECT [ID], [Name], [ModelPermission], [Description] '
                      'FROM $SYSTEM.TMSCHEMA_ROLES')
    s['uyeler'] = dmv('SELECT [RoleID], [MemberName] FROM $SYSTEM.TMSCHEMA_ROLE_MEMBERSHIPS')
    s['satirIzinleri'] = dmv('SELECT [RoleID], [TableID], [FilterExpression] '
                             'FROM $SYSTEM.TMSCHEMA_TABLE_PERMISSIONS')
    s['bolumler'] = dmv('SELECT [TableID], [Name], [State], [RefreshedTime], [Mode] '
                        'FROM $SYSTEM.TMSCHEMA_PARTITIONS')
    return s


def satir_sayilari(tablolar):
    """Her tablo için COUNTROWS. Kalıcı bağlantıda tablo başına birkaç ms."""
    istekler = [{'ad': str(t['ID']), 'dax': "EVALUATE ROW ( \"n\", COUNTROWS ( '%s' ) )" % t['Name']}
                for t in tablolar]
    if not istekler:
        return {}
    try:
        sonuc = calistir_dax.calistir_coklu(istekler, AYAR)
    except Exception:
        return {}
    cikti = {}
    for t in tablolar:
        satirlar = sonuc.get(str(t['ID'])) or []
        try:
            cikti[t['ID']] = int(satirlar[0]['n']) if satirlar else None
        except (TypeError, ValueError, KeyError):
            cikti[t['ID']] = None
    return cikti


def ozet(s, sayimlar):
    tablo_adi = {t['ID']: t['Name'] for t in s['tablolar']}
    kolon_adi = {k['ID']: (k['ExplicitName'] or k['InferredName']) for k in s['kolonlar']}

    print('')
    print('  %s / %s' % (SUNUCU, MODEL))

    # ---- tablolar ----
    cizgi('TABLOLAR (%d)' % len(s['tablolar']))
    satirlar = []
    for t in sorted(s['tablolar'], key=lambda x: x['Name']):
        kolon_sayi = sum(1 for k in s['kolonlar'] if k['TableID'] == t['ID']
                         and not str(k['ExplicitName'] or '').startswith('RowNumber-'))
        olcu_sayi = sum(1 for m in s['olculer'] if m['TableID'] == t['ID'])
        n = sayimlar.get(t['ID'])
        satirlar.append([
            t['Name'],
            'gizli' if dogru(t['IsHidden']) else '',
            '{:,}'.format(n).replace(',', '.') if n is not None else '?',
            kolon_sayi, olcu_sayi,
        ])
    tablo_yaz(['Tablo', '', 'Satır', 'Kolon', 'Ölçü'], satirlar)

    # ---- ölçüler ----
    gorunur = [m for m in s['olculer'] if not dogru(m['IsHidden'])]
    gizli = [m for m in s['olculer'] if dogru(m['IsHidden'])]
    cizgi('ÖLÇÜLER (%d görünür%s)'
          % (len(gorunur), ', %d gizli' % len(gizli) if gizli else ''))
    satirlar = []
    for m in sorted(s['olculer'], key=lambda x: (x['DisplayFolder'] or '', x['Name'])):
        satirlar.append([
            m['Name'],
            tablo_adi.get(m['TableID'], '?'),
            m['FormatString'] or '',
            m['DisplayFolder'] or '',
            'gizli' if dogru(m['IsHidden']) else '',
        ])
    tablo_yaz(['Ölçü', 'Tablo', 'Biçim', 'Klasör', ''], satirlar)
    print('')
    print('    DAX ifadesi için:  --olcu "<ad>"')

    # ---- ilişkiler ----
    cizgi('İLİŞKİLER (%d)' % len(s['iliskiler']))
    satirlar = []
    for r in s['iliskiler']:
        yon = SUZME.get(int(r['CrossFilteringBehavior'] or 1), '?')
        satirlar.append([
            '%s[%s]' % (tablo_adi.get(r['ToTableID'], '?'), kolon_adi.get(r['ToColumnID'], '?')),
            '%s──▶' % KARDINALITE.get(int(r['ToCardinality'] or 1), '?'),
            '%s[%s]' % (tablo_adi.get(r['FromTableID'], '?'), kolon_adi.get(r['FromColumnID'], '?')),
            KARDINALITE.get(int(r['FromCardinality'] or 2), '?'),
            yon,
            '' if dogru(r['IsActive']) else 'PASİF',
        ])
    tablo_yaz(['Boyut (bir)', '', 'Olgu (çok)', '', 'Süzme', ''], satirlar)
    print('')
    print('    Süzme boyuttan olguya akar. Bir ölçü, kendi tablosuna bu oklar')
    print('    izlenerek ULAŞILAMAYAN bir boyutla süzülemez — filtre sessizce')
    print('    yok sayılır ve her satırda aynı sayı döner.')

    # ---- roller ----
    cizgi('ROLLER (%d)' % len(s['roller']))
    if not s['roller']:
        print('    (yok)')
    for r in s['roller']:
        uyeler = [u['MemberName'] for u in s['uyeler'] if u['RoleID'] == r['ID']]
        print('    %s  ·  izin: %s' % (r['Name'], IZIN.get(int(r['ModelPermission'] or 0), '?')))
        print('      üyeler: %s' % (', '.join(uyeler) if uyeler else '(üye yok)'))
        for p in s['satirIzinleri']:
            if p['RoleID'] == r['ID'] and p['FilterExpression']:
                print('      satır filtresi · %s: %s'
                      % (tablo_adi.get(p['TableID'], '?'), p['FilterExpression']))

    # ---- bölümler ----
    cizgi('BÖLÜMLER / SON İŞLEME')
    satirlar = []
    for p in s['bolumler']:
        try:
            durum = BOLUM_DURUM.get(int(p['State']), p['State'])
        except (TypeError, ValueError):
            durum = p['State']
        satirlar.append([tablo_adi.get(p['TableID'], '?'), p['Name'],
                         durum, str(p['RefreshedTime'] or '')[:19]])
    tablo_yaz(['Tablo', 'Bölüm', 'Durum', 'Son işleme'], satirlar)
    print('')


def tablo_ayrinti(s, ad):
    t = next((x for x in s['tablolar'] if str(x['Name']).lower() == ad.lower()), None)
    if not t:
        print('')
        print('  "%s" diye bir tablo yok. Tablolar: %s'
              % (ad, ', '.join(x['Name'] for x in s['tablolar'])))
        return
    kolon_adi = {k['ID']: (k['ExplicitName'] or k['InferredName']) for k in s['kolonlar']}
    print('')
    print('  %s / %s' % (SUNUCU, MODEL))
    cizgi('TABLO · %s%s' % (t['Name'], '  (gizli)' if dogru(t['IsHidden']) else ''))
    if t['Description']:
        print('    %s' % t['Description'])

    satirlar = []
    for k in s['kolonlar']:
        if k['TableID'] != t['ID']:
            continue
        adi = k['ExplicitName'] or k['InferredName']
        if str(adi).startswith('RowNumber-'):
            continue
        satirlar.append([
            adi,
            VERI_TURU.get(int(k['ExplicitDataType'] or 19), str(k['ExplicitDataType'])),
            'gizli' if dogru(k['IsHidden']) else '',
            'anahtar' if dogru(k['IsKey']) else '',
            kolon_adi.get(k['SortByColumnID'], '') if k['SortByColumnID'] else '',
            k['FormatString'] or '',
        ])
    cizgi('KOLONLAR (%d)' % len(satirlar))
    tablo_yaz(['Kolon', 'Tür', '', '', 'Sıralama', 'Biçim'], satirlar)

    olculer = [m for m in s['olculer'] if m['TableID'] == t['ID']]
    cizgi('ÖLÇÜLER (%d)' % len(olculer))
    for m in sorted(olculer, key=lambda x: x['Name']):
        print('    %s%s' % (m['Name'], '  (gizli)' if dogru(m['IsHidden']) else ''))
        if m['Description']:
            print('      %s' % m['Description'])
        for satir in str(m['Expression'] or '').strip().split('\n'):
            print('      │ %s' % satir)
        print('')


def olcu_ayrinti(s, ad):
    tablo_adi = {t['ID']: t['Name'] for t in s['tablolar']}
    bulunan = [m for m in s['olculer'] if ad.lower() in str(m['Name']).lower()]
    if not bulunan:
        print('')
        print('  "%s" ile eşleşen ölçü yok.' % ad)
        return
    print('')
    print('  %s / %s' % (SUNUCU, MODEL))
    for m in bulunan:
        cizgi('ÖLÇÜ · %s' % m['Name'])
        print('    tablo   : %s' % tablo_adi.get(m['TableID'], '?'))
        print('    biçim   : %s' % (m['FormatString'] or '—'))
        print('    klasör  : %s' % (m['DisplayFolder'] or '—'))
        print('    görünür : %s' % ('hayır' if dogru(m['IsHidden']) else 'evet'))
        if m['Description']:
            print('    tanım   : %s' % m['Description'])
        print('')
        for satir in str(m['Expression'] or '').strip().split('\n'):
            print('      │ %s' % satir)
    print('')


def ara(s, kelime):
    k = kelime.lower()
    tablo_adi = {t['ID']: t['Name'] for t in s['tablolar']}
    print('')
    cizgi('ARAMA · "%s"' % kelime)
    bulundu = False
    for t in s['tablolar']:
        if k in str(t['Name']).lower():
            print('    tablo  · %s' % t['Name'])
            bulundu = True
    for m in s['olculer']:
        if k in str(m['Name']).lower() or k in str(m['Expression'] or '').lower():
            nerede = 'ad' if k in str(m['Name']).lower() else 'DAX içinde'
            print('    ölçü   · %s[%s]   (%s)' % (tablo_adi.get(m['TableID'], '?'), m['Name'], nerede))
            bulundu = True
    for c in s['kolonlar']:
        adi = c['ExplicitName'] or c['InferredName']
        if str(adi).startswith('RowNumber-'):
            continue
        if k in str(adi).lower():
            print('    kolon  · %s[%s]%s' % (tablo_adi.get(c['TableID'], '?'), adi,
                                             '  (gizli)' if dogru(c['IsHidden']) else ''))
            bulundu = True
    if not bulundu:
        print('    (bulunamadı)')
    print('')


def main():
    if arg('veritabanlari'):
        veritabanlarini_listele()
        return 0

    d = arg('dax')
    if d and d is not True:
        return dax_calistir(d)

    df = arg('dax-dosya')
    if df and df is not True:
        with io.open(df, encoding='utf-8-sig') as f:
            return dax_calistir(f.read())

    s = model_oku()
    if not s['tablolar']:
        print('  Model okunamadı. TMSCHEMA görünümleri YÖNETİCİ yetkisi ister.')
        return 1

    t = arg('tablo')
    if t and t is not True:
        tablo_ayrinti(s, t)
        return 0

    o = arg('olcu')
    if o and o is not True:
        olcu_ayrinti(s, o)
        return 0

    a = arg('ara')
    if a and a is not True:
        ara(s, a)
        return 0

    sayimlar = {} if arg('satir-sayma-yok') else satir_sayilari(
        [x for x in s['tablolar']])
    ozet(s, sayimlar)
    return 0


if __name__ == '__main__':
    try:
        kod = main()
    finally:
        calistir_dax.kapat()
    sys.exit(kod)
