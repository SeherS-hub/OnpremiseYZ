# -*- coding: utf-8 -*-
"""
AJAN SUNUCUSU — Kapalı Devre Yönetici Asistanı.

Zincir:  soru → planla → doğrula → derle → çalıştır → yorumla → sun
Her adım denetim kaydına yazılır.

Node sürümünden farkı yalnız çalışma zamanı değil: SSAS bağlantısı süreç
ömrü boyunca açık kalıyor. Ölçülen fark cevap başına ~750 ms → ~5 ms.
Açılışta bir ısıtma sorgusu atılıyor ki ilk kullanıcı soğuk başlangıcı
görmesin.

Çalıştırma:  python sunucu.py
Arayüz:      http://localhost:8787
"""

import json
import mimetypes
import os
import posixpath
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import sozlesme as S                                  # noqa: E402
from lib import planlayici                                     # noqa: E402
from lib import derleyici_dax                                  # noqa: E402
from lib import calistir_dax                                   # noqa: E402
from lib import yorumlayici                                    # noqa: E402
from lib import baglam_serisi                                  # noqa: E402
from lib import denetim_sql                                    # noqa: E402
from lib import ileri_analiz                                  # noqa: E402

KOK = os.path.dirname(os.path.abspath(__file__))

AYAR = {
    'port': int(os.environ.get('POC_PORT', 8787)),
    'sqlSunucu': os.environ.get('POC_SQL_SUNUCU', 'localhost'),
    'sqlVeritabani': os.environ.get('POC_SQL_DB', 'POC_SatisYZ'),
    'ssasSunucu': os.environ.get('POC_SSAS_SUNUCU', r'localhost\TABULAR'),
    'ssasModel': os.environ.get('POC_SSAS_MODEL', 'POC_Satis'),
    # PBIRS — cevap kartı bağlantıları bunlardan üretilir
    'raporTaban': os.environ.get('POC_RAPOR_PORTAL', 'http://localhost/Reports'),
    'raporSunucu': os.environ.get('POC_RAPOR_SUNUCU', 'http://localhost/ReportServer'),
}

# Arayüz Node sürümüyle ortak; iki kopya tutmak ayrışma demekti.
GENEL_DIZIN = os.path.join(KOK, 'public')
if not os.path.isdir(GENEL_DIZIN):
    GENEL_DIZIN = os.path.abspath(os.path.join(KOK, '..', '04-ajan', 'public'))

DENETIM_DIZIN = os.path.join(KOK, 'denetim')
DENETIM_DOSYA = os.path.join(DENETIM_DIZIN, 'denetim.jsonl')
os.makedirs(DENETIM_DIZIN, exist_ok=True)

_dosya_kilidi = threading.Lock()

# SSAS yoklaması SÜRELİ önbellekte. Kalıcı önbellek tek kaynaklı mimaride
# ölümcül: modelin yeniden işlendiği ana denk gelen tek bir başarısız
# yoklama, ajanı yeniden başlatılana kadar kapatıyordu. Başarı uzun,
# başarısızlık kısa saklanır — toparlanma hızlı olsun.
_ssas = {'durum': None, 'son': 0.0, 'hata': None}
SSAS_TTL_BASARILI = 60.0
SSAS_TTL_HATALI = 5.0


def ssas_var_mi():
    simdi = time.time()
    ttl = SSAS_TTL_BASARILI if _ssas['durum'] else SSAS_TTL_HATALI
    if _ssas['durum'] is not None and (simdi - _ssas['son']) < ttl:
        return _ssas['durum']
    _ssas['son'] = simdi
    try:
        calistir_dax.calistir('EVALUATE ROW ( "x", 1 )', AYAR)
        _ssas['durum'] = True
        _ssas['hata'] = None
    except Exception as e:
        _ssas['durum'] = False
        _ssas['hata'] = str(e).split('\n')[0][:200]
        print('SSAS yoklamasi basarisiz:', _ssas['hata'])
    return _ssas['durum']


def _denetim_yaz(kayit):
    try:
        with _dosya_kilidi:
            with open(DENETIM_DOSYA, 'a', encoding='utf-8') as f:
                f.write(json.dumps(kayit, ensure_ascii=False, default=str) + '\n')
    except Exception as e:
        # Denetim yazımı cevabı engellemez, ama sessiz de kalmaz.
        print('denetim yazilamadi:', e)


def kaydet(soru, kullanici, cevap, spec):
    k = cevap.get('kunye') or {}
    ana_metrik = None
    if spec and spec.get('metrikler'):
        ana_metrik = S.metrik_bul(spec['metrikler'][0])

    _denetim_yaz({
        'zaman': datetime.now(timezone.utc).isoformat(),
        'kullanici': kullanici,
        'soru': soru,
        'durum': cevap['durum'],
        'cevap': cevap.get('cevap'),
        'metrikler': spec.get('metrikler') if spec else [],
        'donem': spec.get('donemIfade') if spec else None,
        'kaynak': spec.get('kaynak') if spec else None,
        'motor': k.get('motor'),
        'guven': spec.get('guven') if spec else None,
        'sorgu': (cevap.get('sorgu') or {}).get('metin'),
        'satirSayisi': len(cevap.get('satirlar') or []),
        'sureMs': k.get('sureMs'),
        'spesifikasyon': spec,
    })

    metrik = k.get('metrik')
    satirlar = [dict(s, seri='cevap') for s in denetim_sql.satirlari_cikar(
        cevap.get('satirlar'), (cevap.get('vurgu') or {}).get('etiket'))]
    satirlar += cevap.get('baglam') or []

    try:
        return denetim_sql.yaz({
            'kullanici': kullanici,
            'soru': soru,
            'durum': cevap['durum'],
            'cevap': cevap.get('cevap'),
            'aciklama': cevap.get('aciklama') or cevap.get('cevap'),
            'vurguDeger': (cevap.get('vurgu') or {}).get('deger'),
            'vurguEtiket': (cevap.get('vurgu') or {}).get('etiket'),
            'metrikler': ' · '.join(metrik) if isinstance(metrik, list) else metrik,
            'metrikTanim': ana_metrik.get('tanim') if ana_metrik else None,
            'metrikSahip': ana_metrik.get('sahip') if ana_metrik else None,
            'donem': spec.get('donemIfade') if spec else None,
            'kaynak': k.get('kaynak'),
            'motor': k.get('motor'),
            'sorguDili': (cevap.get('sorgu') or {}).get('dil'),
            'sorgu': (cevap.get('sorgu') or {}).get('metin'),
            'spesifikasyon': spec,
            'guven': spec.get('guven') if spec else None,
            'satirSayisi': len(cevap.get('satirlar') or []),
            'sureMs': k.get('sureMs'),
            'sorguSureMs': k.get('sorguSureMs'),
            'belirsizlik': ' | '.join(spec.get('belirsizlikler') or []) if spec else None,
            'satirlar': satirlar,
        }, AYAR)
    except Exception as e:
        print('denetim SQL yazilamadi:', str(e).split('\n')[0])
        return None


def kaydet_ve_teslim(soru, kullanici, cevap, spec):
    """Kayıt yazılır, dönen KayitId cevaba iliştirilir.

    Cevap kartı raporu bu id ile açılıyor; bu yüzden yanıt kayıt
    yazılana kadar bekler.
    """
    kayit_id = kaydet(soru, kullanici, cevap, spec)
    if kayit_id:
        cevap['kayitId'] = kayit_id
        taban = AYAR['raporTaban']
        cevap['cevapKartiUrl'] = '%s/report/CevapKarti?pKayitId=%d' % (taban, kayit_id)
        cevap['cevapKartiGorselUrl'] = (
            '%s?%%2fCevapKarti&rs:Command=Render&rs:Format=IMAGE'
            '&rc:OutputFormat=PNG&rc:DpiX=96&rc:DpiY=96&pKayitId=%d'
            % (AYAR['raporSunucu'], kayit_id))
        # Ana dashboard .pbix; PBIRS'te yolu /report/ değil /powerbi/ altında.
        cevap['dashboardUrl'] = '%s/powerbi/SatisDashboardPBI' % taban
    return cevap


def soruyu_isle(soru, kullanici):
    t0 = time.time()
    adimlar = []

    def gecen():
        return int((time.time() - t0) * 1000)

    # 1-2-3 · planla (niyet, eşleştirme, yetki, kapsam)
    spec = planlayici.planla(soru)
    adimlar.append({'adim': 'planla', 'durum': spec['durum'], 'ms': gecen()})

    # Reddetme / netleştirme yolları — sorgu HİÇ çalışmaz.
    if spec['durum'] != 'ok':
        cevap = {
            'durum': spec['durum'],
            'cevap': spec.get('mesaj'),
            'alternatif': spec.get('alternatif'),
            'secenekler': spec.get('secenekler'),
            'spesifikasyon': spec,
            'sorgu': None,
            'kunye': {'kaynak': '—', 'metrik': '—', 'donem': '—',
                      'motor': '—', 'sureMs': gecen()},
            'adimlar': adimlar,
        }
        return kaydet_ve_teslim(soru, kullanici, cevap, spec)

    adimlar.append({'adim': 'kaynak', 'durum': 'SSAS · ' + AYAR['ssasModel'], 'ms': gecen()})

    # 4b · ileri analiz: tahmin, yıl sonu projeksiyonu, katkı ayrıştırması.
    # Normal boru hattından AYRILIR çünkü tek DAX sorgusu yetmez: seri,
    # iki dönemin kırılımı ya da üç ölçü birlikte gerekiyor ve sonuç
    # üzerinde açık aritmetik yapılıyor. Hesap lib/tahmin.py ve
    # lib/katki.py içinde; dürüstlük kapıları (ufuk sınırı, R² eşiği,
    # kestirim aralığı, "sebep değil" uyarısı) orada uygulanıyor.
    if spec.get('ozel') and ileri_analiz.destekliyor(spec['ozel']):
        try:
            a = ileri_analiz.calistir(spec, AYAR)
        except Exception as e:
            cevap = {'durum': 'hata',
                     'cevap': 'İleri analiz çalıştırılamadı: %s' % str(e).split('\n')[0],
                     'spesifikasyon': spec, 'sorgu': None,
                     'kunye': {'sureMs': gecen()}, 'adimlar': adimlar}
            return kaydet_ve_teslim(soru, kullanici, cevap, spec)

        adimlar.append({'adim': spec['ozel'], 'durum': 'hesaplandı', 'ms': gecen()})
        ana_metrik = S.metrik_bul(spec['metrikler'][0])
        cevap = {
            'baglam': a.get('baglam') or [],
            'durum': 'ok',
            'cevap': a['metin'],
            'aciklama': a.get('aciklama'),
            'vurgu': a.get('vurgu'),
            'satirlar': a.get('satirlar') or [],
            'spesifikasyon': spec,
            'sorgu': {'dil': 'DAX', 'metin': a.get('sorgu')},
            'kunye': {
                'kaynak': 'Semantik model · %s (SSAS Tabular)' % AYAR['ssasModel'],
                'metrik': ['%s · onaylı v%s · %s'
                           % (ana_metrik['ad'], ana_metrik['onay']['surum'], ana_metrik['sahip'])]
                          if ana_metrik else [],
                'tanim': (ana_metrik or {}).get('tanim'),
                'donem': spec.get('donemIfade'),
                'filtreler': spec['filtreler'],
                'motor': 'SSAS Tabular · %s / %s' % (AYAR['ssasSunucu'], AYAR['ssasModel']),
                'guven': spec['guven'],
                'analiz': spec['ozel'],
                # Belirsizlikler burada KRİTİK: tahminin aralığı, yöntemi ve
                # "sebep değil" uyarısı bu listede taşınıyor.
                'belirsizlikler': (spec['belirsizlikler'] or []) + (a.get('belirsizlikler') or []),
                'aciklamalar': spec['aciklamalar'],
                'sureMs': gecen(),
            },
            'adimlar': adimlar,
        }
        return kaydet_ve_teslim(soru, kullanici, cevap, spec)

    # 5 · derle
    try:
        sorgu = derleyici_dax.derle(spec)
    except Exception as e:
        cevap = {'durum': 'hata', 'cevap': 'Sorgu derlenemedi: %s' % e,
                 'spesifikasyon': spec, 'sorgu': None,
                 'kunye': {'sureMs': gecen()}, 'adimlar': adimlar}
        return kaydet_ve_teslim(soru, kullanici, cevap, spec)
    adimlar.append({'adim': 'derle', 'durum': 'DAX', 'ms': gecen()})

    # 6 · çalıştır — ana sorgu ve bağlam serisi birlikte.
    # SSAS erişilemiyorsa SQL'e DÜŞÜLMEZ: düşülseydi aynı soru iki farklı
    # ölçü tanımından cevaplanabilir, sayılar sessizce ayrışırdı.
    try:
        t_sorgu = time.time()
        toplu = calistir_dax.calistir_coklu([
            {'ad': 'ana', 'dax': sorgu},
            {'ad': 'baglam', 'dax': baglam_serisi.sorgu(spec)},
        ], AYAR)
        sorgu_ms = int((time.time() - t_sorgu) * 1000)
        sonuc = {'satirlar': toplu['ana'], 'sureMs': sorgu_ms,
                 'motor': 'SSAS Tabular · %s / %s' % (AYAR['ssasSunucu'], AYAR['ssasModel'])}
        baglam = baglam_serisi.bicimle(toplu['baglam'])
    except Exception as e:
        ileti = str(e)
        bagli_hata = any(x in ileti.lower() for x in
                         ('connect', 'ensure that the server', 'bulunamadi', 'adomd'))
        cevap = {
            'durum': 'hata',
            'cevap': ('Semantik modele şu an ulaşılamıyor, bu yüzden cevap veremiyorum. '
                      'Tek onaylı kaynak SSAS modelidir; başka bir yerden okuyup farklı '
                      'bir sayı üretmem.') if bagli_hata
                     else 'Sorgu çalıştırılamadı: ' + ileti.split('\n')[0],
            'spesifikasyon': spec, 'sorgu': {'dil': 'DAX', 'metin': sorgu},
            'kunye': {'sureMs': gecen()}, 'adimlar': adimlar,
        }
        return kaydet_ve_teslim(soru, kullanici, cevap, spec)

    adimlar.append({'adim': 'calistir',
                    'durum': '%d satır + %d bağlam' % (len(sonuc['satirlar']), len(baglam)),
                    'ms': gecen()})

    # 7 · yorumla
    yorum = yorumlayici.yorumla(spec, sonuc)
    adimlar.append({'adim': 'yorumla', 'durum': 'ok', 'ms': gecen()})

    ana_metrik = S.metrik_bul(spec['metrikler'][0])
    cevap = {
        'baglam': baglam,
        'durum': 'ok',
        'cevap': yorum['metin'],
        'aciklama': yorum.get('aciklama'),
        'vurgu': yorum.get('vurgu'),
        'satirlar': yorum.get('satirlar'),
        'spesifikasyon': spec,
        'sorgu': {'dil': 'DAX', 'metin': sorgu},
        'kunye': {
            'kaynak': 'Semantik model · %s (SSAS Tabular)' % AYAR['ssasModel'],
            'metrik': ['%s · onaylı v%s · %s' % (m['ad'], m['onay']['surum'], m['sahip'])
                       for m in (S.metrik_bul(k) for k in spec['metrikler']) if m],
            'tanim': ana_metrik.get('tanim') if ana_metrik else None,
            'karistirilmamali': (ana_metrik or {}).get('karistirilmamali'),
            'donem': spec['donemIfade'],
            'filtreler': spec['filtreler'],
            'motor': sonuc['motor'],
            'guven': spec['guven'],
            'belirsizlikler': spec['belirsizlikler'],
            'aciklamalar': spec['aciklamalar'],
            'sureMs': gecen(),
            'sorguSureMs': sonuc['sureMs'],
        },
        'adimlar': adimlar,
    }
    return kaydet_ve_teslim(soru, kullanici, cevap, spec)


ALTIN_SORULAR = [
    {'no': 1, 'soru': 'Ağustos ayı net ciromuz ne kadar?', 'bekleniyor': 'Tek dönem, tek ölçü'},
    {'no': 2, 'soru': 'Bu yıl toplam ciro ne oldu?', 'bekleniyor': 'Yıl filtresi'},
    {'no': 3, 'soru': 'En yüksek ciro hangi ayda oldu?', 'bekleniyor': 'Uç değer + dönem adı'},
    {'no': 4, 'soru': 'Temmuz ayında hedefi tuttuk mu?', 'bekleniyor': 'Hedef gerçekleşme · evet/hayır dili'},
    {'no': 5, 'soru': 'Haziran cirosu önceki aya göre nasıl değişti?', 'bekleniyor': 'Aylık değişim otomatik eklenir'},
    {'no': 6, 'soru': 'Son 10 ayın ortalama aylık cirosu ne?', 'bekleniyor': 'Dönem aralığı · ortalama'},
    {'no': 7, 'soru': 'Marmara bölgesinin cirosu ne kadar?', 'bekleniyor': 'Bölge filtresi'},
    {'no': 8, 'soru': 'En çok ciro yapan 3 ürün grubu hangileri?', 'bekleniyor': 'Top-N'},
    {'no': 9, 'soru': 'Rakiplerin pazar payı ne oldu?', 'bekleniyor': 'KAPSAM DIŞI · gerekçeli ret'},
    {'no': 10, 'soru': 'Ahmet Yılmaz’ın maaşı ne kadar?', 'bekleniyor': 'YETKİSİZ · ret + denetim kaydı'},
]


class Islemci(BaseHTTPRequestHandler):
    server_version = 'PoCAjan/1.0'
    protocol_version = 'HTTP/1.1'

    def log_message(self, bicim, *args):
        pass                       # varsayılan gürültülü erişim günlüğü kapalı

    def handle_one_request(self):
        """İstemcinin bağlantıyı yarıda kapatması bir HATA DEĞİLDİR.

        Tarayıcı sekmeyi kapattığında ya da yoklama aracı bağlantıyı
        düşürdüğünde varsayılan işleyici koca bir traceback basıyor;
        gerçek hatalar bu gürültünün içinde kayboluyordu.
        """
        try:
            BaseHTTPRequestHandler.handle_one_request(self)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def _json(self, kod, nesne):
        govde = json.dumps(nesne, ensure_ascii=False, indent=2, default=str).encode('utf-8')
        self.send_response(kod)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != '/api/sor':
            return self._json(404, {'hata': 'bulunamadı'})
        try:
            uzunluk = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            uzunluk = 0
        if uzunluk > 20000:
            return self._json(413, {'hata': 'Gövde çok büyük'})
        try:
            istek = json.loads(self.rfile.read(uzunluk).decode('utf-8') or '{}')
        except Exception:
            return self._json(400, {'hata': 'Geçersiz JSON'})

        soru = str(istek.get('soru') or '')[:500]
        if not soru.strip():
            return self._json(400, {'hata': 'Soru boş'})

        # Kimlik SUNUCUDAN gelmeli. Gerçek kurulumda bu, öndeki Windows
        # kimlik doğrulaması yapan katmandan okunur; istemcinin gönderdiği
        # değere GÜVENİLMEZ (bkz. GERCEK-ORTAMA-GECIS.md · Faz 2).
        kullanici = (self.headers.get('X-Kullanici')
                     or istek.get('kullanici')
                     or os.environ.get('USERNAME') or 'bilinmeyen')
        try:
            self._json(200, soruyu_isle(soru, kullanici))
        except Exception as e:
            traceback.print_exc()
            self._json(500, {'durum': 'hata', 'cevap': 'Beklenmeyen hata: %s' % e})

    def do_GET(self):
        u = urlparse(self.path)

        if u.path == '/api/saglik':
            return self._json(200, {
                'ssas': {'erisim': ssas_var_mi(), 'sunucu': AYAR['ssasSunucu'],
                         'model': AYAR['ssasModel'], 'hata': _ssas['hata']},
                'denetimDb': {'sunucu': AYAR['sqlSunucu'], 'veritabani': AYAR['sqlVeritabani']},
                'metrikSayisi': len(S.METRIKLER),
                'kapsananDonem': len(S.KAPSANAN_DONEMLER),
                'calismaZamani': 'Python %s' % sys.version.split()[0],
            })

        if u.path == '/api/sorular':
            return self._json(200, ALTIN_SORULAR)

        if u.path == '/api/sozlesme':
            return self._json(200, {
                'metrikler': [{'kod': m['kod'], 'ad': m['ad'], 'tanim': m.get('tanim'),
                               'birim': m['birim'], 'sahip': m.get('sahip'),
                               'onay': m.get('onay'), 'esanlamlilar': m['esanlamlilar'],
                               'karistirilmamali': m.get('karistirilmamali')}
                              for m in S.METRIKLER],
                'boyutlar': [{'kod': b['kod'], 'ad': b['ad']} for b in S.BOYUTLAR],
                'donemler': S.KAPSANAN_DONEMLER,
            })

        # --- statik ---
        yol = unquote(u.path)
        yol = '/index.html' if yol == '/' else yol
        # Dizin dışına çıkma girişimi: normalize edip kökle karşılaştır.
        tam = os.path.normpath(os.path.join(GENEL_DIZIN, posixpath.normpath(yol).lstrip('/')))
        if not tam.startswith(os.path.normpath(GENEL_DIZIN)) or not os.path.isfile(tam):
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', '11')
            self.end_headers()
            return self.wfile.write('bulunamadı'.encode('utf-8'))

        tur = mimetypes.guess_type(tam)[0] or 'application/octet-stream'
        if tur.startswith('text/') or tur in ('application/javascript', 'application/json'):
            tur += '; charset=utf-8'
        with open(tam, 'rb') as f:
            veri = f.read()
        self.send_response(200)
        self.send_header('Content-Type', tur)
        self.send_header('Content-Length', str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    # Isıtma. Açılışta yapılmazsa bedelini ilk kullanıcı öder — ölçüldü,
    # ilk soru 2,2 saniye sürüyordu. Üç ayrı soğuk maliyet var:
    #   1. ADOMD.NET assembly yükleme + SSAS bağlantısı  (~700 ms)
    #   2. ilk gerçek sorgunun SSAS'ta derlenmesi
    #   3. pyodbc'nin denetim veritabanına ilk bağlanması (~120 ms)
    # Üçü de burada peşinen ödeniyor.
    t0 = time.time()
    parcalar = []
    try:
        calistir_dax.calistir_coklu([
            {'ad': 'x', 'dax': 'EVALUATE ROW ( "x", 1 )'},
            {'ad': 'baglam', 'dax': baglam_serisi.sorgu(None)},
        ], AYAR)
        parcalar.append('SSAS %d ms' % int((time.time() - t0) * 1000))
    except Exception as e:
        parcalar.append('SSAS BAŞARISIZ — ' + str(e).split('\n')[0][:100])

    t1 = time.time()
    try:
        denetim_sql.yaz({'kullanici': 'sistem', 'soru': '(ısınma)', 'durum': 'hata',
                         'cevap': 'Sunucu açılış ısınması — gerçek soru değil.',
                         'satirlar': []}, AYAR)
        parcalar.append('denetim %d ms' % int((time.time() - t1) * 1000))
    except Exception as e:
        parcalar.append('denetim BAŞARISIZ — ' + str(e).split('\n')[0][:100])

    isinma = ' · '.join(parcalar)

    print('')
    print('  Kapalı Devre Yönetici Asistanı · Python ajanı')
    print('  ------------------------------------------------')
    print('  Arayüz      : http://localhost:%d' % AYAR['port'])
    print('  Kaynak      : SSAS %s / %s  (TEK analitik kaynak)'
          % (AYAR['ssasSunucu'], AYAR['ssasModel']))
    print('  Denetim DB  : %s / %s' % (AYAR['sqlSunucu'], AYAR['sqlVeritabani']))
    print('  Arayüz kökü : %s' % GENEL_DIZIN)
    print('  Isınma      : %s' % isinma)
    print('  Çalışma z.  : Python %s' % sys.version.split()[0])
    print('')

    sys.stdout.flush()

    ThreadingHTTPServer(('127.0.0.1', AYAR['port']), Islemci).serve_forever()


if __name__ == '__main__':
    main()
