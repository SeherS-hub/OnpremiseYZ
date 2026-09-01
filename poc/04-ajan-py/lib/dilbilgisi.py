# -*- coding: utf-8 -*-
"""
DİLBİLGİSİ — Türkçe için deterministik NLP yardımcıları.

Öğrenme yok: ek listesi sabit, mesafe eşiği sabit, aynı girdi her zaman
aynı çıktıyı verir. Amaç eşleştiricinin kapsamasını artırmak — "cirosu",
"ciromuz", "cirolarımızdan" hepsi "ciro"ya inmeli — ama bunu tahmine
kaymadan yapmak.

İki çözümleyici:

  KURAL   varsayılan. Ek soyma + ünsüz yumuşaması. Bağımlılık yok.
  ZEYREK  isteğe bağlı. Zemberek'in Python portu; gerçek biçimbirim
          çözümlemesi yapar. POC_DILBILGISI=zeyrek ile açılır.

Zeyrek daha güçlü ("satışlarımız" → satış VE satmak, "kârlılık" → kâr)
ama iki bedeli var: nltk korpusu (kapalı devrede ayrıca taşınmalı) ve
belirteç başına maliyet. İkisi de aynı test kümesiyle ölçülebilsin diye
arayüz ortak tutuldu.

Kapsamayı gevşetmenin bedeli YANLIŞ EŞLEŞMEdir; aşağıdaki dört kapı,
gerçekten yaşanmış dört hatadan çıktı.
"""

import os
import re

# Karşılaştırılabilir en kısa gövde. 3 harf fazla cömert: "hedef" ile
# "hediye" ikisi de "hed"e iniyor. 4'te bu çakışma kalkıyor.
ASGARI_GOVDE = 4

# Ek soyarken inilebilecek en kısa dize.
ASGARI_SOYMA = 3

# En fazla kaç ek soyulur. Türkçede pratikte 3 yeterli: "ciro-lar-ımız-dan".
AZAMI_DERINLIK = 3

# Normalize edilmiş (diakritiksiz) biçimleriyle çekim ve yaygın yapım ekleri.
_EKLER_HAM = [
    # çoğul + iyelik + hâl zincirleri
    'larimizdan', 'lerimizden', 'larimiza', 'lerimize', 'larimizi', 'lerimizi',
    'larimiz', 'lerimiz', 'lariniz', 'leriniz', 'larinin', 'lerinin',
    'larindan', 'lerinden', 'larinda', 'lerinde', 'larina', 'lerine',
    'larini', 'lerini', 'lardan', 'lerden', 'larda', 'lerde',
    'lari', 'leri', 'lara', 'lere', 'lar', 'ler',
    # iyelik
    'imizden', 'imizde', 'imizin', 'imize', 'imizi', 'imiz',
    'umuzdan', 'umuzda', 'umuzun', 'umuze', 'umuzu', 'umuz',
    'inizden', 'inizde', 'inizin', 'inize', 'inizi', 'iniz',
    'unuzdan', 'unuzda', 'unuzun', 'unuze', 'unuzu', 'unuz',
    'miz', 'muz', 'niz', 'nuz',
    # iyelik + hâl
    'sinden', 'sinde', 'sinin', 'sine', 'sini', 'sin',
    'nden', 'ndan', 'nde', 'nda', 'nin', 'nun', 'ne', 'na', 'ni', 'nu',
    'si', 'su', 'se', 'sa',
    # hâl
    'den', 'dan', 'ten', 'tan', 'de', 'da', 'te', 'ta',
    'yle', 'yla', 'ile', 'le', 'la',
    'yi', 'yu', 'ye', 'ya',
    # Tek harflik 'n' ve 's' BİLEREK yok. Onlarla "gruplandir" soyula
    # soyula "grup"a iniyor ve "grubunun" ile çakışıyordu.
    'in', 'un', 'im', 'um', 'i', 'u', 'e', 'a',
    # yapım ve fiilimsi — dar tutuldu
    'ki', 'ce', 'ca', 'lik', 'luk', 'li', 'lu', 'ci', 'cu', 'siz', 'suz',
    'digi', 'dugu', 'tigi', 'tugu', 'dik', 'duk', 'tik', 'tuk',
    'mis', 'mus', 'dir', 'dur', 'tir', 'tur',
    'iyor', 'yor', 'ecek', 'acak', 'mek', 'mak',
]
EKLER = sorted(set(_EKLER_HAM), key=len, reverse=True)

# Ünsüz yumuşaması: son ses değişimini geri alır. Normalize sonrası
# alfabede ç→c ve ğ→g çöktüğü için yalnız üçü kalır.
SERTLESME = {'b': 'p', 'd': 't', 'g': 'k'}

_BOSLUK = re.compile(r'\s+')
_COGUL = re.compile(r'(ler|lar)$')
_COGUL_EKLI = re.compile(r'(leri|lari)(n|na|ni|nda|ndan)?$')


# --------------------------------------------------------------------
# Gövde adayları
# --------------------------------------------------------------------
def _yumusamayi_geri_al(kok):
    son = kok[-1:] if kok else ''
    return kok[:-1] + SERTLESME[son] if son in SERTLESME else None


_govde_onbellek = {}


def govde_adaylari(kelime):
    """Tek bir 'doğru kök' seçmek yerine tüm makul adayları üretir.

    Eşleştirme iki adayın KESİŞİMİNE bakar; böylece "sayımız" ve "sayısı"
    farklı eklerden geçse de "sayı"da buluşur.
    """
    k = str(kelime or '')
    if not k:
        return []
    onbellek = _govde_onbellek.get(k)
    if onbellek is not None:
        return onbellek

    gorulen = {k}
    sira = [(k, 0)]
    while sira:
        sonraki = []
        for s, derinlik in sira:
            if derinlik >= AZAMI_DERINLIK:
                continue
            for ek in EKLER:
                if len(s) - len(ek) < ASGARI_SOYMA or not s.endswith(ek):
                    continue
                kok = s[:len(s) - len(ek)]
                for aday in (kok, _yumusamayi_geri_al(kok)):
                    if aday and aday not in gorulen:
                        gorulen.add(aday)
                        sonraki.append((aday, derinlik + 1))
        sira = sonraki

    sonuc = list(gorulen)
    _govde_onbellek[k] = sonuc
    return sonuc


def _zeyrek_cozumleyici():
    """Zeyrek yalnız istendiğinde ve bir kez yüklenir."""
    if _zeyrek_cozumleyici.durum is None:
        try:
            import logging
            # Zeyrek bilgi düzeyinde 'APPENDING RESULT' satırlarını
            # stderr'e döküyor; sunucu günlüğünü kirletmesin.
            logging.getLogger('zeyrek').setLevel(logging.ERROR)
            logging.getLogger('zeyrek.rulebasedanalyzer').setLevel(logging.ERROR)
            import zeyrek
            _zeyrek_cozumleyici.durum = zeyrek.MorphAnalyzer()
        except Exception as e:      # nltk korpusu yoksa buraya düşer
            _zeyrek_cozumleyici.durum = False
            _zeyrek_cozumleyici.hata = str(e).split('\n')[0]
    return _zeyrek_cozumleyici.durum


_zeyrek_cozumleyici.durum = None
_zeyrek_cozumleyici.hata = None

ZEYREK_ACIK = os.environ.get('POC_DILBILGISI', 'kural').lower() == 'zeyrek'
_zeyrek_onbellek = {}


def _zeyrek_kokler(kelime):
    coz = _zeyrek_cozumleyici()
    if not coz:
        return []
    if kelime in _zeyrek_onbellek:
        return _zeyrek_onbellek[kelime]
    try:
        sonuc = coz.lemmatize(kelime)
        kokler = []
        for _, adaylar in sonuc:
            for a in adaylar:
                # normalize edilmiş biçimde karşılaştırıyoruz
                from lib.sozlesme import normalize as _n
                d = _n(a)
                if d and d not in kokler:
                    kokler.append(d)
        _zeyrek_onbellek[kelime] = kokler
        return kokler
    except Exception:
        _zeyrek_onbellek[kelime] = []
        return []


def eslesme_adaylari(kelime):
    """Eşleştirmede kullanılacak adaylar: yeterince uzun olanlar.

    Kelimenin kendisi kısa olsa bile listede kalır — "ege", "ay" gibi
    sözlük değerleri tam eşleşmeyle yakalanmalı.
    """
    hepsi = govde_adaylari(kelime)
    if ZEYREK_ACIK:
        for k in _zeyrek_kokler(kelime):
            if k not in hepsi:
                hepsi.append(k)
    uzun = [a for a in hepsi if len(a) >= ASGARI_GOVDE]
    return uzun + [kelime] if uzun else [kelime]


# --------------------------------------------------------------------
# Yazım toleransı
# --------------------------------------------------------------------
def uzaklik(a, b, sinir):
    """Üst sınırlı Levenshtein; sınır aşılınca erken çıkar."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > sinir:
        return sinir + 1
    onceki = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        simdiki = [i] + [0] * len(b)
        satir_en_az = i
        for j in range(1, len(b) + 1):
            bedel = 0 if a[i - 1] == b[j - 1] else 1
            simdiki[j] = min(onceki[j] + 1, simdiki[j - 1] + 1, onceki[j - 1] + bedel)
            if simdiki[j] < satir_en_az:
                satir_en_az = simdiki[j]
        if satir_en_az > sinir:
            return sinir + 1
        onceki = simdiki
    return onceki[len(b)]


def yazim_yakin(a, b):
    """Üç kapı: en az 4 harf · İLK HARF AYNI · dar mesafe.

    İlk harf kapısı olmadan tolerans gerçek kelimeleri birbirine
    karıştırıyor: "yaptık" ile "saptık" arasında 1 harf var ve
    "ne kadar hasılat yaptık" sorusu Hedef Sapma'ya düşüyordu.
    """
    n = max(len(a), len(b))
    if n < 4 or not a or not b or a[0] != b[0]:
        return False
    sinir = 2 if n >= 8 else 1
    return uzaklik(a, b, sinir) <= sinir


# --------------------------------------------------------------------
# Belirteçleme
# --------------------------------------------------------------------
def belirtecler(normalize_metin):
    return [t for t in _BOSLUK.split(str(normalize_metin or '')) if t]


class Cozum(object):
    __slots__ = ('ham', 'adaylar', 'kume', 'cogullar', 'yazim_acik')

    def __init__(self, ham, adaylar, kume, cogullar, yazim_acik):
        self.ham = ham
        self.adaylar = adaylar
        self.kume = kume
        self.cogullar = cogullar
        self.yazim_acik = yazim_acik


def metni_cozumle(normalize_metin, bilinenler=None):
    """Soruyu bir kez çözümleyip yeniden kullanılacak biçime getirir.

    `bilinenler`: sözlükte geçen tüm yüzey belirteçleri. Burada olan bir
    kelime DOĞRU yazılmış sayılır ve yazım toleransına sokulmaz.
    """
    ham = belirtecler(normalize_metin)
    adaylar = [eslesme_adaylari(t) for t in ham]
    kume = set()
    for liste in adaylar:
        kume.update(liste)
    cogullar = set()
    for t in ham:
        if _COGUL.search(t) or _COGUL_EKLI.search(t):
            cogullar.update(eslesme_adaylari(t))
    yazim_acik = [t for t in ham if t not in bilinenler] if bilinenler else list(ham)
    return Cozum(ham, adaylar, kume, cogullar, yazim_acik)


def belirtec_var_mi(cozum, sozluk_belirtec):
    # 1) gövde kesişimi — çekim eklerini bu karşılıyor
    for h in eslesme_adaylari(sozluk_belirtec):
        if h in cozum.kume:
            return True
    # 2) yazım toleransı YALNIZCA yüzey biçimler arasında. Türetilmiş
    #    gövdeleri de toleransa sokmak yanlış eşleşme üretiyordu:
    #    "tutturduğumuz" → "tuttur", "tuttuk" ile 1 harf farkla eşleşiyor.
    if len(sozluk_belirtec) >= 4:
        for t in cozum.yazim_acik:
            if len(t) >= 4 and yazim_yakin(sozluk_belirtec, t):
                return True
    return False


def kalip_var_mi(cozum, kalip):
    """Çok kelimeli kalıp: TÜM belirteçler geçmeli, sıra serbest.

    "bölge bazında ciro" ile "ciro bölge bazında" aynı şeydir.
    """
    gerekli = belirtecler(kalip)
    if not gerekli:
        return False
    return all(belirtec_var_mi(cozum, g) for g in gerekli)
