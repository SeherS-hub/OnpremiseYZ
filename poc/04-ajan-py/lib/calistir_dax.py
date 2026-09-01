# -*- coding: utf-8 -*-
"""
DAX ÇALIŞTIRICI — ADOMD.NET üzerinden, KALICI bağlantıyla.

Node sürümünde her soru için yeni bir PowerShell süreci açılıyordu.
Ölçüm, cevabın nereye gittiğini net gösterdi:

    PowerShell süreci açılışı      ~190 ms
    ADOMD.NET yükleme               ~75 ms
    bağlantı açma                  ~150 ms
    SORGUNUN KENDİSİ                  4 ms
    ------------------------------------
    gözlenen toplam                ~700 ms

Cevap süresinin %99'u sorgu değil, altyapıydı. Burada bağlantı süreç
ömrü boyunca açık kalıyor; sorgu maliyeti ölçülen 2–5 ms'ye iniyor.

RLS: `etkin_kullanici` verilirse bağlantı EffectiveUserName ile kurulur
ve sorgu O kullanıcının rolleriyle koşar. Kimlik SUNUCUDAN gelir,
istemciden asla — istemci kendi kimliğini söyleyebilseydi yetki
denetiminin anlamı kalmazdı.
"""

import os
import re
import sys
import threading
import time

_ADOMD_DIZINLERI = [
    r'C:\Program Files\Microsoft.NET\ADOMD.NET\170',
    r'C:\Program Files\Microsoft.NET\ADOMD.NET\160',
    r'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE',
]

_KULLANICI_DESENI = re.compile(r'^[A-Za-z0-9._-]+(\\[A-Za-z0-9._-]+|@[A-Za-z0-9._-]+)$')

_kilit = threading.Lock()
_havuz = {}          # anahtar -> bağlantı
_Pyadomd = None


def _pyadomd():
    global _Pyadomd
    if _Pyadomd is None:
        for d in _ADOMD_DIZINLERI:
            if os.path.isdir(d) and d not in sys.path:
                sys.path.append(d)
        from pyadomd import Pyadomd      # noqa: E402
        _Pyadomd = Pyadomd
    return _Pyadomd


def _baglanti_dizesi(sunucu, model, etkin_kullanici):
    cs = 'Data Source=%s;Catalog=%s;' % (sunucu, model)
    if etkin_kullanici:
        # Kullanıcı adı bağlantı dizesine giriyor; enjeksiyona kapatmak
        # için yalnız DOMAIN\kullanici ve kullanici@alan biçimleri geçer.
        if not _KULLANICI_DESENI.match(etkin_kullanici):
            raise ValueError('Gecersiz etkin kullanici bicimi: %s' % etkin_kullanici)
        cs += 'EffectiveUserName=%s;' % etkin_kullanici
    return cs


def _baglanti(ayar):
    """Kalıcı bağlantı. Kimliğe bürünme farklı bağlantı ister; anahtar
    (sunucu, model, kullanıcı) üçlüsüdür."""
    sunucu = (ayar or {}).get('ssasSunucu') or 'localhost'
    model = (ayar or {}).get('ssasModel') or 'POC_Satis'
    kullanici = (ayar or {}).get('etkinKullanici')
    anahtar = (sunucu, model, kullanici)

    with _kilit:
        con = _havuz.get(anahtar)
        if con is None:
            con = _pyadomd()(_baglanti_dizesi(sunucu, model, kullanici))
            con.open()
            _havuz[anahtar] = con
        return con, anahtar


def _sutun_adi(ad):
    """DAX sütun adları iki biçimde gelir: "[Ölçü]" ve "Tablo[Sütun]".
    İkisinde de son [...] parçası alınır."""
    m = re.search(r'\[([^\]]+)\]\s*$', ad or '')
    return m.group(1) if m else str(ad).strip('[]')


def _tek(con, dax):
    with con.cursor().execute(dax) as cur:
        basliklar = [_sutun_adi(a[0]) for a in cur.description]
        return [dict(zip(basliklar, satir)) for satir in cur.fetchall()]


def calistir(dax, ayar=None):
    t0 = time.perf_counter()
    con, anahtar = _baglanti(ayar)
    try:
        satirlar = _tek(con, dax)
    except Exception:
        # Bağlantı düşmüş olabilir; bir kez yeniden kurup dene. Kalıcı
        # bağlantının tek gerçek riski budur.
        with _kilit:
            _havuz.pop(anahtar, None)
        con, anahtar = _baglanti(ayar)
        satirlar = _tek(con, dax)
    sunucu, model, _ = anahtar
    return {
        'satirlar': satirlar,
        'sureMs': int((time.perf_counter() - t0) * 1000),
        'motor': 'SSAS Tabular · %s / %s' % (sunucu, model),
    }


def calistir_coklu(sorgular, ayar=None):
    """Birden fazla sorgu. Node'da bu 'tek süreçte çalıştır' optimizasyonuydu;
    burada bağlantı zaten açık olduğu için sadece sıralı çalıştırma."""
    con, anahtar = _baglanti(ayar)
    cikti = {}
    for istek in sorgular:
        try:
            cikti[istek['ad']] = _tek(con, istek['dax'])
        except Exception:
            with _kilit:
                _havuz.pop(anahtar, None)
            con, anahtar = _baglanti(ayar)
            cikti[istek['ad']] = _tek(con, istek['dax'])
    return cikti


def kapat():
    with _kilit:
        for con in _havuz.values():
            try:
                con.close()
            except Exception:
                pass
        _havuz.clear()
