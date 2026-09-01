# -*- coding: utf-8 -*-
"""
DENETİM KAYDI — her soru ve cevabın SQL Server'a yazılması.

Node sürümü bunu `sqlcmd`'ye kabuk çağrısıyla yapıyordu: geçici .sql
dosyası yaz, süreç aç, JSON'u tırnak kaçırarak metne göm, çıktıyı
kod sayfası tahmin ederek oku. Üç ayrı hata kaynağı — Türkçe karakter
bozulması, tırnak kaçışı, süreç maliyeti.

Burada `pyodbc` ile parametreli çağrı: kaçış yok, kod sayfası yok,
süreç yok. Bağlantı kalıcı.

Kayıt PBIRS cevap kartı raporunun veri kaynağıdır; dönen KayitId ile
kart açılır. Bu yüzden yazım eşzamanlıdır — kanıt zincirinin bedeli.
"""

import json
import threading

import pyodbc

_kilit = threading.Lock()
_baglanti = {}


def _cs(ayar):
    return ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=%s;DATABASE=%s;'
            'Trusted_Connection=yes;TrustServerCertificate=yes;'
            % ((ayar or {}).get('sqlSunucu') or 'localhost',
               (ayar or {}).get('sqlVeritabani') or 'POC_SatisYZ'))


def _con(ayar):
    anahtar = _cs(ayar)
    with _kilit:
        con = _baglanti.get(anahtar)
        if con is None:
            con = pyodbc.connect(anahtar, timeout=10, autocommit=True)
            _baglanti[anahtar] = con
        return con, anahtar


def satirlari_cikar(satirlar, vurgu_etiket=None):
    """Sonuç kümesini kartın beklediği etiket/değer çiftlerine indirger.

    Kart yalnız denetim kaydından okur; sonuç kümesinin ham hâli değil,
    çizilebilir seri saklanır.
    """
    cikti = []
    for i, s in enumerate(satirlar or [], start=1):
        etiket = None
        deger = None
        for k, v in s.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if deger is None:
                    deger = float(v)
            elif etiket is None:
                etiket = str(v)
        if deger is None:
            continue
        cikti.append({'sira': i,
                      'etiket': etiket or (vurgu_etiket or str(i)),
                      'deger': deger})
    return cikti


def yaz(kayit, ayar=None):
    """Denetim kaydını yazar ve KayitId döner.

    JSON gövdesi PARAMETRE olarak gidiyor; Node sürümündeki tek tırnak
    kaçırma numarası ("Yılmaz'ın" sorguyu bozuyordu) burada gereksiz.
    """
    govde = json.dumps(kayit, ensure_ascii=False, default=str)
    con, anahtar = _con(ayar)
    try:
        cur = con.cursor()
        cur.execute('EXEC denetim.usp_AjanKayitEkle ?', govde)
        satir = None
        while True:
            try:
                satir = cur.fetchone()
            except pyodbc.ProgrammingError:
                satir = None
            if satir is not None or not cur.nextset():
                break
        cur.close()
        return int(satir[0]) if satir and satir[0] is not None else None
    except Exception:
        # Bağlantı düşmüş olabilir; bir kez yeniden kur ve dene.
        with _kilit:
            eski = _baglanti.pop(anahtar, None)
            if eski is not None:
                try:
                    eski.close()
                except Exception:
                    pass
        con, _ = _con(ayar)
        cur = con.cursor()
        cur.execute('EXEC denetim.usp_AjanKayitEkle ?', govde)
        satir = cur.fetchone()
        cur.close()
        return int(satir[0]) if satir and satir[0] is not None else None


def kapat():
    with _kilit:
        for con in _baglanti.values():
            try:
                con.close()
            except Exception:
                pass
        _baglanti.clear()
