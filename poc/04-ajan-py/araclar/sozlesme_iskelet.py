# -*- coding: utf-8 -*-
"""
SÖZLEŞME İSKELETİ ÜRETECİ

Gerçek ortama geçişte elle yazılacak tek büyük dosya lib/sozlesme.py.
Bu araç onun makineden çıkarılabilecek kısmını çıkarır: ölçüler,
boyutlar, düşük kardinaliteli boyut değerleri ve — önemlisi — her
ölçünün hangi boyutlarla ANLAMLI olduğu.

Son madde bir PoC hatasından geldi: Müşteri Sayısı ölçüsü ilişkisi
olmayan bir tablodan geliyordu, Kanal filtresi sessizce yok sayılıyor
ve her satırda aynı sayı dönüyordu. Model ilişkilerine bakarak bunu
önceden hesaplamak, aynı hatayı sizin modelinizde en baştan keser.

Kullanım:
    python araclar/sozlesme_iskelet.py --sunucu "SUNUCU\\ORNEK" --model "ModelAdi"
    python araclar/sozlesme_iskelet.py --sunucu ... --model ... --cikti lib/sozlesme_yeni.py

Gereksinim: modelde yönetici yetkisi ($SYSTEM.TMSCHEMA_* okumak için).
"""

import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import calistir_dax                                   # noqa: E402
from lib.sozlesme import normalize                             # noqa: E402


def arg(ad, varsayilan=None):
    if '--' + ad in sys.argv:
        i = sys.argv.index('--' + ad)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return varsayilan


SUNUCU = arg('sunucu')
MODEL = arg('model')
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIKTI = arg('cikti', os.path.join(KOK, 'lib', 'sozlesme_iskelet.py'))
AZAMI_DEGER = int(arg('azami-deger', 50))

if not SUNUCU or not MODEL:
    print('Kullanım: python araclar/sozlesme_iskelet.py --sunucu "SUNUCU\\ORNEK" --model "ModelAdi"')
    sys.exit(2)

AYAR = {'ssasSunucu': SUNUCU, 'ssasModel': MODEL}


def kodla(ad):
    return normalize(ad).replace('%', '').strip().replace(' ', '_').replace('__', '_')


def pyl(s):
    """Python dize yazımı."""
    return "'" + str(s).replace('\\', '\\\\').replace("'", "\\'") + "'"


def dogru_mu(v):
    return str(v).lower() == 'true' or v is True


# --------------------------------------------------------------------
# Model okuma
# --------------------------------------------------------------------
print('')
print('  Model okunuyor: %s / %s' % (SUNUCU, MODEL))

try:
    sema = calistir_dax.calistir_coklu([
        {'ad': 'tablolar', 'dax': 'SELECT [ID], [Name], [IsHidden] FROM $SYSTEM.TMSCHEMA_TABLES'},
        {'ad': 'kolonlar', 'dax': 'SELECT [ID], [TableID], [ExplicitName], [InferredName], '
                                  '[IsHidden] FROM $SYSTEM.TMSCHEMA_COLUMNS'},
        {'ad': 'olculer', 'dax': 'SELECT [TableID], [Name], [IsHidden], [FormatString], '
                                 '[Description], [DisplayFolder] FROM $SYSTEM.TMSCHEMA_MEASURES'},
        {'ad': 'iliskiler', 'dax': 'SELECT [FromTableID], [ToTableID], [IsActive], '
                                   '[CrossFilteringBehavior] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS'},
    ], AYAR)
except Exception as e:
    print('  Model okunamadı: %s' % str(e).split('\n')[0])
    print('  TMSCHEMA görünümleri modelde YÖNETİCİ yetkisi ister.')
    sys.exit(1)

tablolar = sema['tablolar']
kolonlar = sema['kolonlar']
olculer = sema['olculer']
iliskiler = sema['iliskiler']

tablo_adi = {t['ID']: t['Name'] for t in tablolar}
gizli_tablo = {t['ID']: dogru_mu(t['IsHidden']) for t in tablolar}

print('  %d tablo · %d kolon · %d ölçü · %d ilişki'
      % (len(tablolar), len(kolonlar), len(olculer), len(iliskiler)))

# --------------------------------------------------------------------
# İlişki grafiği: süzme YÖNÜNÜ izler
#
# TMSCHEMA'da FromTable "çok" (olgu), ToTable "bir" (boyut) tarafıdır ve
# süzme varsayılan olarak BOYUTTAN OLGUYA akar: To → From.
#
# Yön önemli. Yönsüz kurulduğunda Bölge, Satış üzerinden Dönem'e
# "ulaşıyor" görünüyor ve Müşteri Sayısı ölçüsü bölgeyle süzülebilir
# sanılıyordu. Gerçekte süzülmüyor: Satış bir olgu tablosu, hiçbir
# ilişkinin "bir" tarafı değil, dolayısıyla oradan devam edilemez.
# --------------------------------------------------------------------
komsu = {t['ID']: set() for t in tablolar}
for r in iliskiler:
    if str(r['IsActive']).lower() == 'false':
        continue
    if r['ToTableID'] in komsu:
        komsu[r['ToTableID']].add(r['FromTableID'])
    # CrossFilteringBehavior = 2 çift yönlü ilişkidir
    if str(r.get('CrossFilteringBehavior')) == '2' and r['FromTableID'] in komsu:
        komsu[r['FromTableID']].add(r['ToTableID'])


def ulasilir(a, b):
    if a == b:
        return True
    gorulen, sira = {a}, [a]
    while sira:
        x = sira.pop(0)
        for y in komsu.get(x, ()):
            if y == b:
                return True
            if y not in gorulen:
                gorulen.add(y)
                sira.append(y)
    return False


# --------------------------------------------------------------------
# Boyut adayları
# Olgu tablosu = en az bir ilişkinin "from" (çok) tarafı olan tablo.
# --------------------------------------------------------------------
olgu_tablolar = {r['FromTableID'] for r in iliskiler}
boyut_adaylari = []
for k in kolonlar:
    if dogru_mu(k['IsHidden']) or k['TableID'] in olgu_tablolar or gizli_tablo.get(k['TableID']):
        continue
    ad = k['ExplicitName'] or k['InferredName']
    if not ad or str(ad).startswith('RowNumber-'):
        continue
    boyut_adaylari.append({
        'tabloId': k['TableID'], 'tablo': tablo_adi[k['TableID']],
        'ad': ad, 'kod': kodla(ad),
        'daxSutun': '%s[%s]' % (tablo_adi[k['TableID']], ad),
    })

# --------------------------------------------------------------------
# Düşük kardinaliteli boyutların değerleri
# --------------------------------------------------------------------
print('  Boyut değerleri okunuyor (%d aday, en fazla %d değer)...'
      % (len(boyut_adaylari), AZAMI_DEGER))
try:
    sayimlar = calistir_dax.calistir_coklu(
        [{'ad': 'n%d' % i,
          'dax': 'EVALUATE ROW ( "n", COUNTROWS ( DISTINCT ( %s ) ) )' % b['daxSutun']}
         for i, b in enumerate(boyut_adaylari)], AYAR)
except Exception as e:
    print('  (kardinalite okunamadı: %s)' % str(e).split('\n')[0])
    sayimlar = {}

deger_istekleri = []
for i, b in enumerate(boyut_adaylari):
    satirlar = sayimlar.get('n%d' % i) or []
    try:
        n = int(satirlar[0]['n']) if satirlar else None
    except (TypeError, ValueError, KeyError):
        n = None
    b['kardinalite'] = n
    if n and 0 < n <= AZAMI_DEGER:
        deger_istekleri.append({'ad': 'd%d' % i,
                                'dax': 'EVALUATE DISTINCT ( %s )' % b['daxSutun']})

degerler = {}
if deger_istekleri:
    try:
        degerler = calistir_dax.calistir_coklu(deger_istekleri, AYAR)
    except Exception as e:
        print('  (değerler okunamadı: %s)' % str(e).split('\n')[0])

for i, b in enumerate(boyut_adaylari):
    satirlar = degerler.get('d%d' % i)
    if satirlar is None:
        continue
    b['degerler'] = [list(s.values())[0] for s in satirlar
                     if list(s.values())[0] not in (None, '')]


# --------------------------------------------------------------------
# Ölçüler
# --------------------------------------------------------------------
def birim_cikar(bicim, ad):
    f = str(bicim or '')
    if '%' in f:
        return 'oran'
    for iz in ('₺', '$', '€', '£', '"TL"', '"USD"', '"EUR"'):
        if iz in f:
            return 'TRY'
    n = normalize(ad)
    if any(x in n for x in ('adet', 'sayi', 'count', 'miktar')):
        return 'adet'
    return 'sayi'


tum_boyut_kodlari = [b['kod'] for b in boyut_adaylari]
metrikler = []
for o in olculer:
    if dogru_mu(o['IsHidden']):
        continue
    gecerli = [b['kod'] for b in boyut_adaylari if ulasilir(b['tabloId'], o['TableID'])]
    eksik = [k for k in tum_boyut_kodlari if k not in gecerli]
    metrikler.append({
        'kod': kodla(o['Name']), 'ad': o['Name'], 'dax': '[%s]' % o['Name'],
        'birim': birim_cikar(o['FormatString'], o['Name']),
        'tanim': o['Description'] or None,
        'tablo': tablo_adi[o['TableID']],
        'esanlamlilar': sorted({normalize(o['Name']).rstrip(' %').strip(),
                                normalize(o['Name'])} - {''}),
        'gecerliBoyutlar': gecerli if eksik else None,
        'erisilemez': eksik,
    })

# --------------------------------------------------------------------
# Dosya üretimi
# --------------------------------------------------------------------
L = []
y = L.append

y('# -*- coding: utf-8 -*-')
# Ham dize: sunucu adindaki ters bolu (SUNUCU\ORNEK) docstring icinde
# gecersiz kacis dizisi uyarisi veriyordu.
y('r"""')
y('ANLAM SÖZLEŞMESİ — İSKELET (otomatik üretildi, ELLE TAMAMLANMALI)')
y('')
y('Kaynak: %s / %s' % (SUNUCU, MODEL))
y('Üretim: %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
y('')
y('Makineden çıkarılabilenler dolduruldu: ölçü adları, DAX karşılıkları,')
y('birimler, boyutlar, boyut değerleri, ölçü-boyut geçerliliği.')
y('')
y('ELLE doldurulacaklar TODO ile işaretli: eşanlamlılar, tanımlar,')
y('sahiplik, onay durumu, dönem sözlüğü, kapsam ve yetki desenleri.')
y('Asıl değer oradadır — ölçü adının kendisi nadiren yeterli olur.')
y('"""')
y('')
y('from lib.sozlesme import normalize      # ortak normalizasyon')
y('')
y('METRIKLER = [')
for m in metrikler:
    y('    {')
    y('        %s: %s,' % (pyl('kod'), pyl(m['kod'])))
    y('        %s: %s,' % (pyl('ad'), pyl(m['ad'])))
    y('        %s: %s,' % (pyl('dax'), pyl(m['dax'])))
    y("        'birim': %s,   # TODO doğrula: biçim dizesinden çıkarıldı" % pyl(m['birim']))
    y("        'tanim': %s," % (pyl(m['tanim']) if m['tanim']
                                else "'TODO: bu ölçü NEYİ ölçer, neyi ölçmez'"))
    y("        'sahip': 'TODO: sahip ekip',")
    y("        'onay': {'durum': 'TODO', 'surum': 1, 'tarih': 'TODO'},")
    y('        # TODO: kullanıcıların gerçekte kullandığı sözcükleri ekleyin.')
    y('        # Türkçe çekim eklerini YAZMAYIN — dilbilgisi katmanı')
    y('        # "ciro" ↔ "cirosu" ↔ "ciromuz" bağını zaten kuruyor.')
    y("        'esanlamlilar': [%s]," % ', '.join(pyl(e) for e in m['esanlamlilar']))
    if m['gecerliBoyutlar'] is not None:
        y('        # Bu ölçünün tablosu (%s) şu boyutlarla İLİŞKİSİZ: %s.'
          % (m['tablo'], ', '.join(m['erisilemez'])))
        y('        # O boyutlarla sorulursa filtre sessizce yok sayılır ve her')
        y('        # satırda aynı sayı döner. Gerekçeli ret için sınırlandı.')
        y("        'gecerliBoyutlar': [%s],"
          % ', '.join(pyl(k) for k in m['gecerliBoyutlar']))
    y('    },')
y(']')
y('')
y('BOYUTLAR = [')
for b in boyut_adaylari:
    n = normalize(b['ad'])
    y('    {')
    y('        %s: %s, %s: %s,' % (pyl('kod'), pyl(b['kod']), pyl('ad'), pyl(b['ad'])))
    y("        'daxSutun': %s," % pyl(b['daxSutun']))
    y('        # Çıplak ad tek başına kırılım DEĞİL, filtredir. Kırılım için')
    y('        # planlayıcı bir işaret arar: göre, bazında, kırılım, hangi…')
    y("        'ciplakAdlar': [%s]," % pyl(n))
    y("        'esanlamlilar': [%s],   # TODO: kuruma özgü söyleyişler"
      % ', '.join(pyl(x) for x in ('%s bazinda' % n, '%s kirilimi' % n, 'hangi %s' % n)))
    y('    },')
y(']')
y('')
y('# Düşük kardinaliteli boyut değerleri — filtre olarak adıyla anılabilir.')
y('BOYUT_DEGERLERI = {')
for b in boyut_adaylari:
    if b.get('degerler'):
        y('    %s: [%s],' % (pyl(b['kod']), ', '.join(pyl(v) for v in b['degerler'])))
y('}')
y('')
y('# TODO — DÖNEM SÖZLÜĞÜ')
y('# Ajanın "mart ayı", "geçen ay", "son 3 ay" ifadelerini çözebilmesi için')
y('# takvim boyutunuza bağlanmalı:')
y('#   AYLAR              ay adı → ay numarası')
y('#   KAPSANAN_DONEMLER  modelin içerdiği dönemlerin listesi')
y('#   EN_GUNCEL_DONEM    "bu ay" bunun karşılığıdır')
y('# Dönem kolonu adaylarınız:')
for b in boyut_adaylari:
    if any(x in normalize(b['ad']) for x in ('donem', 'tarih', 'ay', 'yil', 'date', 'month')):
        y('#   · %s   (%s farklı değer)' % (b['daxSutun'], b['kardinalite']))
y('AYLAR = []')
y('KAPSANAN_DONEMLER = []')
y("EN_GUNCEL_DONEM = ''")
y('')
y('# TODO — KAPSAM DIŞI / YETKİSİZ / MEVCUT OLMAYAN')
y('# Üçü farklı şeydir:')
y('#   KAPSAM_DISI     konu modelde yok (stok, rakip, kârlılık…)')
y('#   YETKISIZ        konu olabilir ama sorulamaz (maaş, kişisel veri)')
y('#   MEVCUT_OLMAYAN  konu VAR, sorulan AYRINTI yok (ürün seviyesi vb.)')
y('# Üçüncüsü en sinsi olanı yakalar: "Buzdolabı satışları" ciro ölçüsüne')
y('# uyup TOPLAM ciro döndürüyordu. PoC dosyasından kopyalayıp uyarlayın.')
y('KAPSAM_DISI = []')
y('YETKISIZ = []')
y('MEVCUT_OLMAYAN = []')
y('')
y('')
y('def metrik_bul(kod):')
y('    return next((m for m in METRIKLER if m[%s] == kod), None)' % pyl('kod'))
y('')
y('')
y('def boyut_bul(kod):')
y('    return next((b for b in BOYUTLAR if b[%s] == kod), None)' % pyl('kod'))
y('')
y('')
y('def _belirtec_dizini():')
y('    """Sözlükte geçen her yüzey belirteci — yazım toleransının kapısı."""')
y('    k = set()')
y('')
y('    def ekle(ifade):')
y("        for t in normalize(ifade).split(' '):")
y('            if t:')
y('                k.add(t)')
y('')
y('    for m in METRIKLER:')
y("        for e in m['esanlamlilar']:")
y('            ekle(e)')
y('    for b in BOYUTLAR:')
y("        for e in b['esanlamlilar'] + b.get('ciplakAdlar', []):")
y('            ekle(e)')
y('    for kod in BOYUT_DEGERLERI:')
y('        for d in BOYUT_DEGERLERI[kod]:')
y('            ekle(d)')
y('    return k')
y('')
y('')
y('TUM_BELIRTECLER = _belirtec_dizini()')

with io.open(CIKTI, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L) + '\n')

calistir_dax.kapat()

# --------------------------------------------------------------------
# Rapor
# --------------------------------------------------------------------
print('')
print('  Üretildi: %s' % CIKTI)
print('')
print('  ' + '=' * 70)
print('  ÖLÇÜLER (%d)' % len(metrikler))
for m in metrikler:
    print('    %-28s %-6s %s%s' % (
        m['ad'][:28], m['birim'],
        'tanım var' if m['tanim'] else 'TANIM YOK',
        '   · ilişkisiz boyut: ' + ', '.join(m['erisilemez']) if m['erisilemez'] else ''))
print('')
print('  BOYUTLAR (%d)' % len(boyut_adaylari))
for b in boyut_adaylari:
    print('    %-34s %6s değer%s' % (
        b['daxSutun'][:34],
        '?' if b['kardinalite'] is None else b['kardinalite'],
        '   (değerler dosyaya yazıldı)' if b.get('degerler') else ''))
print('')
print('  ELLE TAMAMLANACAKLAR')
print('    1. Eşanlamlılar — en çok kazandıran adım. Kullanıcıların gerçekte')
print('       kullandığı sözcükler; ölçü adının kendisi nadiren yeter.')
print('    2. Tanımlar — %d ölçünün model içinde açıklaması yok.'
      % sum(1 for m in metrikler if not m['tanim']))
print('    3. Sahiplik ve onay durumu.')
print('    4. Dönem sözlüğü — takvim boyutuna bağlanmalı.')
print('    5. Kapsam dışı / yetkisiz / mevcut olmayan desenleri.')
print('')
print('  Sonra: test/esanlam-durumlar.json dosyasını KENDİ sorularınızla')
print('  doldurun ve koşun. Kapsama oranı sözleşmenin olgunluk ölçüsüdür.')
print('')
