# -*- coding: utf-8 -*-
"""
PLANLAYICI — doğal dil sorusu → SORGU SPESİFİKASYONU.

Niyet çözümlemesi deterministik: eşanlamlı sözlüğü + desen eşleştirme +
kural tabanlı Türkçe biçimbilim (lib/dilbilgisi). Öğrenme yoktur; aynı
soru her zaman aynı spesifikasyonu üretir.

Bir LLM devreye alınacaksa değişecek TEK yer burasıdır — çıktı sözleşmesi
(spesifikasyon şeması) aynı kaldığı için derleyici, doğrulayıcı ve arayüz
hiç değişmez.
"""

import re
from datetime import date

from lib import sozlesme as S
from lib import dilbilgisi as dil

normalize = S.normalize


# --------------------------------------------------------------------
# Küçük yardımcılar
# --------------------------------------------------------------------
_icerir_onbellek = {}


def icerir(metin, kalip):
    """Sol kelime sınırı ile eşleşme.

    Düz substring araması Türkçe'de tehlikeli: "aylık cirosu" içindeki
    "ik " eki, İK (insan kaynakları) desenini tetikleyip masum bir soruyu
    "yetkisiz" saydırıyordu. Sol sınır şart, sağ sınır serbest — çünkü
    Türkçe eklemeli: "ciro" → "cirosu", "cironun".

    Kalıbın sonundaki boşluk ANLAMLI ve kırpılmaz: 'top ' kalıbı
    "toplam ciro" ifadesine takılmasın diye oraya konmuştur.
    """
    k = str(kalip)
    if not k.strip():
        return False
    desen = _icerir_onbellek.get(k)
    if desen is None:
        desen = re.compile(r'(^|\s)' + re.escape(k))
        _icerir_onbellek[k] = desen
    return bool(desen.search(metin))


def soru_eki(kelime):
    """Türkçe soru eki ünlü uyumuna girer: "Marmara mı", "Ege mi",
    "İç Anadolu mu". Sabit 'mi' yazmak cevabı bozuk Türkçe yapıyordu."""
    unluler = re.findall(r'[aeıioöuü]', str(kelime).lower())
    son = unluler[-1] if unluler else 'a'
    if son in 'aı':
        return 'mı'
    if son in 'ei':
        return 'mi'
    if son in 'ou':
        return 'mu'
    return 'mü'


def esanlamli_eslestir(metin, liste, cozum, bicimbilim_kapali=False):
    """En uzun kalıp kazanır (en özgül eşleşme).

    İki aşamalı. Önce bitişik dize araması; bulamazsa dilbilgisi katmanı
    (gövdeleme, sırasız belirteç eşleşmesi, dar yazım toleransı). Sıra
    önemli: bitişik eşleşme daha güçlü kanıttır.
    """
    bulunan = []
    for oge in liste:
        en_iyi = 0
        for kalip in oge['esanlamlilar']:
            if len(kalip) <= en_iyi:
                continue
            if icerir(metin, kalip) or (not bicimbilim_kapali and dil.kalip_var_mi(cozum, kalip)):
                en_iyi = len(kalip)
        if en_iyi > 0:
            bulunan.append({'oge': oge, 'skor': en_iyi})
    bulunan.sort(key=lambda x: -x['skor'])
    return bulunan


# Yalnız ADSAL işaretler. Fiil kökleri ('dagit', 'gruplandir', 'ayir')
# listede yok: ek soyma onları kısa gövdelere indirip alakasız sözcüklerle
# çakıştırıyordu — "gruplandir" → "grup", "grubunun" ile eşleşiyordu.
KIRILIM_ISARETLERI = [
    'gore', 'bazinda', 'bazli', 'bazda', 'kirilim', 'kiriliminda',
    'dagilim', 'dagilimi', 'basina', 'itibariyla', 'itibaryla',
    'ayriminda', 'ayrimi', 'bakimindan', 'acisindan', 'hangi',
]


def _kirilim_isareti_var_mi(metin, cozum):
    return any(icerir(metin, i) or dil.belirtec_var_mi(cozum, i)
               for i in KIRILIM_ISARETLERI)


def boyutlari_coz(metin, cozum):
    """Boyut adı ile kırılım işaretini AYIRIR.

    Eskiden her söyleyiş sözlüğe tek tek yazılıyordu ("bolgeye gore",
    "bolge bazinda"…). Şimdi boyut adı × işaret çarpımı serbest.

    Çıplak boyut adı TEK BAŞINA kırılım sayılmaz — bu bilinçli:
    "Marmara bölgesinin cirosu" filtredir. Kırılım için ya bir işaret ya
    çoğul ek gerekir.
    """
    kodlar = []

    # 1) sözlükteki tam kırılım kalıpları. Biçimbilim BİLEREK kapalı:
    #    açık olsaydı 'bolgeler' kalıbı "bölgesinin" ile eşleşirdi
    #    (ikisi de "bolge" gövdesine iner) ve filtre kırılım sanılırdı.
    for b in esanlamli_eslestir(metin, S.BOYUTLAR, cozum, True):
        if b['oge']['kod'] not in kodlar:
            kodlar.append(b['oge']['kod'])

    # 2) bileşimsel: çıplak boyut adı + kırılım işareti (veya çoğul ek)
    isaret = _kirilim_isareti_var_mi(metin, cozum)
    for b in S.BOYUTLAR:
        if b['kod'] in kodlar:
            continue
        for ad in b.get('ciplakAdlar', []):
            parcalar = dil.belirtecler(ad)
            if not all(dil.belirtec_var_mi(cozum, t) for t in parcalar):
                continue
            cogul = any(a in cozum.cogullar
                        for t in parcalar for a in dil.eslesme_adaylari(t))
            if isaret or cogul:
                kodlar.append(b['kod'])
                break
    return kodlar


# --------------------------------------------------------------------
# Dönem çözümleme
# --------------------------------------------------------------------
_DONEM_DESENI = re.compile(r'\b(20\d{2})[-/. ](0?[1-9]|1[0-2])\b')
_YIL_DESENI = re.compile(r'\b(20\d{2})\b')
_SON_N_AY = re.compile(r'son (\d+) ay')


def donem_coz(metin):
    sonuc = {'filtreler': [], 'notlar': [], 'ifade': None,
             'hataKapsam': None, 'kirilimGerek': None}

    # Açık dönem: "2026-08". Ay adı aramasından ÖNCE denenmeli, yoksa yıl
    # deseni "2026"yı yakalar ve soru sessizce tüm yıla genişler.
    m = _DONEM_DESENI.search(metin)
    if m:
        d = '%s-%02d' % (m.group(1), int(m.group(2)))
        if d not in S.KAPSANAN_DONEMLER:
            sonuc['hataKapsam'] = (d + ' dönemi modelin kapsadığı %d dönem içinde yok. Kapsam: %s … %s.'
                                   % (len(S.KAPSANAN_DONEMLER), S.KAPSANAN_DONEMLER[0], S.EN_GUNCEL_DONEM))
            return sonuc
        sonuc['filtreler'].append({'boyut': 'donem', 'operator': '=', 'deger': d})
        sonuc['ifade'] = d
        return sonuc

    ym = _YIL_DESENI.search(metin)
    yil = int(ym.group(1)) if ym else None

    # Ay adlarının TÜMÜ toplanır, ilkinde durulmaz. Eskiden ilk eşleşmede
    # kesiliyordu: "Şubat ve mart cirolarını karşılaştır" sessizce yalnız
    # şubata dönüyordu.
    aylar = [a for a in S.AYLAR if any(icerir(metin, k) for k in a['anahtar'])]
    ay = aylar[0] if aylar else None

    bu_ay = icerir(metin, 'bu ay') or icerir(metin, 'son ay') or icerir(metin, 'guncel ay')
    gecen_ay = icerir(metin, 'gecen ay') or icerir(metin, 'onceki ay')
    bu_yil = icerir(metin, 'bu yil') or icerir(metin, 'yil basindan') or icerir(metin, 'ytd')
    son_n = _SON_N_AY.search(metin)

    guncel = S.EN_GUNCEL_DONEM
    gy, gm = (int(x) for x in guncel.split('-'))

    # Birden fazla ay: karşılaştırma isteği. Filtre 'in' olur ve dönem
    # kırılımı eklenir — yoksa iki ay toplanıp tek sayı döner.
    if len(aylar) > 1:
        donemler = []
        for a in aylar:
            adaylar = sorted(d for d in S.KAPSANAN_DONEMLER
                             if int(d.split('-')[1]) == a['no']
                             and (not yil or int(d.split('-')[0]) == yil))
            if adaylar:
                donemler.append(adaylar[-1])
        tekil = sorted(set(donemler))
        if len(tekil) > 1:
            sonuc['filtreler'].append({'boyut': 'donem', 'operator': 'in', 'deger': tekil})
            sonuc['ifade'] = ' · '.join(tekil)
            sonuc['kirilimGerek'] = 'donem'
            sonuc['notlar'].append('Birden fazla dönem soruldu (%s); karşılaştırma için dönem kırılımı eklendi.'
                                   % ', '.join(tekil))
            return sonuc

    if ay:
        hedef_yil = yil
        if not hedef_yil:
            adaylar = sorted(d for d in S.KAPSANAN_DONEMLER if int(d.split('-')[1]) == ay['no'])
            if not adaylar:
                sonuc['hataKapsam'] = ay['ad'] + ' ayı bu modelin kapsadığı dönemler içinde yok.'
                return sonuc
            hedef_yil = int(adaylar[-1].split('-')[0])
            if len(adaylar) > 1:
                sonuc['notlar'].append('%s için yıl belirtilmedi; en güncel olan %d alındı.'
                                       % (ay['ad'], hedef_yil))
        donem = '%d-%02d' % (hedef_yil, ay['no'])
        if donem not in S.KAPSANAN_DONEMLER:
            sonuc['hataKapsam'] = (donem + ' dönemi modelin kapsadığı %d dönem içinde yok. Kapsam: %s … %s.'
                                   % (len(S.KAPSANAN_DONEMLER), S.KAPSANAN_DONEMLER[0], S.EN_GUNCEL_DONEM))
            return sonuc
        sonuc['filtreler'].append({'boyut': 'donem', 'operator': '=', 'deger': donem})
        sonuc['ifade'] = donem
        return sonuc

    if bu_ay:
        sonuc['filtreler'].append({'boyut': 'donem', 'operator': '=', 'deger': guncel})
        sonuc['ifade'] = guncel
        sonuc['notlar'].append('"bu ay" = %s olarak çözümlendi.' % guncel)
        return sonuc

    if gecen_ay:
        d = date(gy, gm, 1)
        onceki = '%04d-%02d' % ((d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12))
        sonuc['filtreler'].append({'boyut': 'donem', 'operator': '=', 'deger': onceki})
        sonuc['ifade'] = onceki
        sonuc['notlar'].append('"geçen ay" = %s olarak çözümlendi.' % onceki)
        return sonuc

    if son_n:
        n = int(son_n.group(1))
        dizi = S.KAPSANAN_DONEMLER[-n:]
        sonuc['filtreler'].append({'boyut': 'donem', 'operator': 'in', 'deger': dizi})
        sonuc['ifade'] = '%s … %s' % (dizi[0], dizi[-1])
        if n > len(S.KAPSANAN_DONEMLER):
            sonuc['notlar'].append('Model %d dönem içeriyor; istenen %d ay için tamamı alındı.'
                                   % (len(S.KAPSANAN_DONEMLER), n))
        return sonuc

    if bu_yil or yil:
        y = yil or gy
        sonuc['filtreler'].append({'boyut': 'yil', 'operator': '=', 'deger': y})
        sonuc['ifade'] = '%d yılı' % y
        if bu_yil and not yil:
            sonuc['notlar'].append('"bu yıl" = %d olarak çözümlendi.' % y)
        return sonuc

    sonuc['ifade'] = 'tüm dönemler (%s … %s)' % (S.KAPSANAN_DONEMLER[0], S.EN_GUNCEL_DONEM)
    return sonuc


def boyut_degeri_coz(metin, cozum):
    """Değerlerde yazım toleransı YOK — bilerek. Yanlış bölge filtresi
    sessizce yanlış sayı üretir; burada kesinlik esneklikten önemli.
    Çekim eki serbest ("Marmara'nın", "Ege'de"), harf hatası değil."""
    filtreler = []
    for boyut_kod, degerler in S.BOYUT_DEGERLERI.items():
        for deger in degerler:
            d = normalize(deger)
            parcalar = dil.belirtecler(d)
            if icerir(metin, d) or all(p in cozum.kume or p in cozum.ham for p in parcalar):
                filtreler.append({'boyut': boyut_kod, 'operator': '=', 'deger': deger})
    return filtreler


# --------------------------------------------------------------------
# Sıralama / top-N
# --------------------------------------------------------------------
SAYI_ADLARI = {'bir': 1, 'iki': 2, 'uc': 3, 'dort': 4, 'bes': 5,
               'alti': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9, 'on': 10}

# Ardından gelirse sayıyı adet değil DÖNEM yapan kelimeler.
DONEM_KELIMELERI = ['ay', 'ayin', 'aylik', 'yil', 'yilin', 'yillik', 'donem', 'donemin']


# --------------------------------------------------------------------
# İleri analiz niyetleri — tahmin, projeksiyon, katkı
#
# Bu dördü eskiden REDDEDİLİYORDU: tahmin KAPSAM_DISI'ndaydı, "neden"
# soruları da netleştirmeye düşüyordu. Ret gerekçeleri hâlâ geçerli;
# değişen şey reddetmek yerine BELİRSİZLİĞİ VE SINIRI birlikte vermek.
# Hesabın kendisi lib/tahmin.py ve lib/katki.py içinde, dürüstlük
# kapıları da orada.
# --------------------------------------------------------------------
TAHMIN_ISARETLERI = ['tahmin', 'ongoru', 'ne olur', 'ne olacak', 'bekleniyor',
                     'beklenti', 'gelecek ay', 'gelecek donem', 'onumuzdeki',
                     'forecast', 'kestirim', 'projeksiyon']
YIL_SONU_ISARETLERI = ['yil sonu', 'yil sonunda', 'yili nasil kapat',
                       'yil sonuna', 'seneyi nasil kapat', 'yil sonu itibariyla',
                       'hedefe ulasir mi', 'hedefi tutar mi', 'yil sonu hedef']
KATKI_ISARETLERI = ['neden', 'nicin', 'niye', 'sebebi', 'sebep', 'kaynaklaniyor',
                    'katki', 'katkisi', 'hangisi cekti', 'kim cekti',
                    'nereden geldi', 'ne kadarini']
HACIM_SEPET_ISARETLERI = ['adetten mi', 'fiyattan mi', 'hacim mi', 'sepet mi',
                          'adet mi', 'adetten mi sepetten mi', 'birim fiyattan mi',
                          'hacimden mi']

_SAYI_UFUK = {'bir': 1, 'iki': 2, 'uc': 3, 'dort': 4, 'bes': 5, 'alti': 6}


def _ufuk_coz(metin):
    """'önümüzdeki 3 ay' → 3. Bulunamazsa 1."""
    t = dil.belirtecler(metin)
    for i, k in enumerate(t):
        sonraki = t[i + 1] if i + 1 < len(t) else ''
        if sonraki not in ('ay', 'ayin', 'aylik', 'donem', 'donemin'):
            continue
        if k.isdigit() and len(k) < 3:
            return int(k)
        if k in _SAYI_UFUK:
            return _SAYI_UFUK[k]
    return 1


def ileri_niyet(metin, cozum):
    """Dönen: None ya da {'ozel': ..., 'ufuk': ...}

    Sıra önemli: yıl sonu, tahmin işaretlerinden ÖNCE bakılır. "Yıl sonu
    ne olur" ikisine de uyuyor ama doğru cevap koşu hızı projeksiyonudur —
    regresyonla 4 ay ileri gitmek zaten ufuk sınırına takılırdı.
    """
    if any(icerir(metin, i) for i in YIL_SONU_ISARETLERI):
        return {'ozel': 'yil_sonu'}
    if any(icerir(metin, i) for i in HACIM_SEPET_ISARETLERI):
        return {'ozel': 'hacim_sepet'}
    if any(icerir(metin, i) for i in TAHMIN_ISARETLERI):
        return {'ozel': 'tahmin', 'ufuk': _ufuk_coz(metin)}
    if any(icerir(metin, i) for i in KATKI_ISARETLERI):
        return {'ozel': 'katki'}
    return None


def siralama_coz(metin):
    en_cok = (icerir(metin, 'en cok') or icerir(metin, 'en yuksek')
              or icerir(metin, 'en fazla') or icerir(metin, 'en iyi')
              or icerir(metin, 'top ') or icerir(metin, 'ilk '))
    en_az = icerir(metin, 'en az') or icerir(metin, 'en dusuk') or icerir(metin, 'en kotu')
    if not en_cok and not en_az:
        return None

    # Eski hâli metindeki İLK sayıyı alıyordu; "2026 yılında en çok satan
    # 3 ürün grubu" sorusunda limit 2026 oluyordu.
    t = dil.belirtecler(metin)
    limit = None
    for i, kelime in enumerate(t):
        if limit is not None:
            break
        sonraki = t[i + 1] if i + 1 < len(t) else ''
        if sonraki in DONEM_KELIMELERI:
            continue
        if kelime.isdigit():
            n = int(kelime)
            if len(kelime) < 4 and 1 <= n <= 50:
                limit = n
        elif kelime in SAYI_ADLARI:
            limit = SAYI_ADLARI[kelime]

    return {'yon': 'artan' if en_az else 'azalan', 'limit': 5 if limit is None else limit}


# --------------------------------------------------------------------
# Ana giriş
# --------------------------------------------------------------------
def planla(soru):
    m = normalize(soru)
    spec = {
        'soru': soru, 'durum': 'ok', 'kaynak': 'tabular',
        'metrikler': [], 'boyutlar': [], 'filtreler': [],
        'siralama': None, 'limit': None, 'ozel': None,
        'donemIfade': None, 'guven': 0,
        'belirsizlikler': [], 'aciklamalar': [],
    }

    if not m:
        spec['durum'] = 'netlestir'
        spec['mesaj'] = 'Soruyu anlayamadım, yazabilir misiniz?'
        return spec

    # Biçimbilimsel çözümleme bir kez yapılır, her eşleştiricide kullanılır.
    cozum = dil.metni_cozumle(m, S.TUM_BELIRTECLER)

    # --- 1) yetki kontrolü, her şeyden önce ---
    for y in S.YETKISIZ:
        if any(icerir(m, d) for d in y['desen']):
            spec['durum'] = 'yetkisiz'
            spec['mesaj'] = y['neden']
            spec['guven'] = 1
            return spec

    # --- 2) kapsam kontrolü ---
    for k in S.KAPSAM_DISI:
        if any(icerir(m, d) for d in k['desen']):
            spec['durum'] = 'kapsam_disi'
            spec['mesaj'] = k['neden']
            spec['alternatif'] = k.get('alternatif')
            spec['guven'] = 1
            return spec

    # --- 2c) modelde olmayan kırılım seviyesi ---
    # Metrik eşleştirmesinden ÖNCE. "Buzdolabı satışları" ciro ölçüsüne
    # uyuyor ve cevaplanıyordu; "buzdolabı" sessizce yok sayılıp TOPLAM
    # ciro dönüyordu.
    for mo in getattr(S, 'MEVCUT_OLMAYAN', []):
        eslesen = next((d for d in mo['desen']
                        if icerir(m, d) or dil.kalip_var_mi(cozum, d)), None)
        if eslesen:
            spec['durum'] = 'kapsam_disi'
            spec['mesaj'] = mo['neden']
            spec['alternatif'] = mo.get('alternatif')
            spec['guven'] = 1
            spec['aciklamalar'].append('Soruda geçen "%s" bu modelde kırılım olarak yok.' % eslesen)
            return spec

    # --- 2d) boyut değerine YAKIN ama eşleşmeyen ifade ---
    # "Marmar" yazıp hiç filtre uygulanmaması da sessiz yanlış cevaptır.
    yakin = []
    for boyut_kod, degerler in S.BOYUT_DEGERLERI.items():
        for deger in degerler:
            d = normalize(deger)
            if icerir(m, d):
                continue
            for t in cozum.ham:
                if len(t) < 4 or t in S.TUM_BELIRTECLER:
                    continue
                if any(dil.yazim_yakin(p, t) for p in dil.belirtecler(d)):
                    yakin.append((t, deger))
    if yakin:
        yazilan, deger = yakin[0]
        spec['durum'] = 'netlestir'
        spec['mesaj'] = '"%s" diye bir değer yok. %s %s demek istediniz?' % (
            yazilan, deger, soru_eki(deger))
        spec['secenekler'] = [{'kod': normalize(d), 'ad': d, 'tanim': 'Yazılan: ' + y}
                              for y, d in yakin[:3]]
        spec['guven'] = 0.4
        return spec

    # --- 2b) nedensellik ---
    # Sistem hâlâ NEDEN iddia etmiyor; iddia edemez, bu veride sebep yok.
    # Ama artık "hangi kalem ne kadarını çekti" hesabını yapıp gösteriyor —
    # eskiden bunu kullanıcıya önerip bekliyordu. Cevap metni her seferinde
    # bunun bir KATKI ayrıştırması olduğunu, sebep olmadığını yazar
    # (lib/katki.py · UYARI).

    # --- 3) özel niyet ---
    hangi_ay = icerir(m, 'hangi ay') or icerir(m, 'hangi donem') or icerir(m, 'hangi ayda')
    siralama = siralama_coz(m)
    ileri = ileri_niyet(m, cozum)

    # --- 4) metrik eşleştirme ---
    metrik_adaylari = esanlamli_eslestir(m, S.METRIKLER, cozum)
    if not metrik_adaylari:
        # İleri analiz niyeti anlaşıldıysa ("... neden düştü", "... tahmini")
        # ama hangi ölçü olduğu belli değilse, düz reddetmek yerine SOR.
        # "Ağustos düşüşü neden" sorusunda niyet açık, eksik olan ölçü.
        if ileri:
            spec['durum'] = 'netlestir'
            spec['mesaj'] = ('Hangi ölçüyü kastettiğinizi seçmem gerekiyor — '
                             'niyeti anladım ama ölçü belirtilmedi.')
            spec['secenekler'] = [
                {'kod': k, 'ad': S.metrik_bul(k)['ad'], 'tanim': S.metrik_bul(k)['tanim']}
                for k in ('net_ciro', 'satis_adet', 'hedef_gerceklesme')
                if S.metrik_bul(k)]
            spec['guven'] = 0.45
            return spec
        spec['durum'] = 'kapsam_disi'
        spec['mesaj'] = 'Bu soruyu onaylı metriklerle eşleştiremedim.'
        spec['alternatif'] = 'Tanımlı metrikler: ' + ', '.join(x['ad'] for x in S.METRIKLER) + '.'
        return spec

    # Belirsizlik: ilk iki aday aynı skorda ise seçmeyip soruyoruz.
    if len(metrik_adaylari) > 1 and metrik_adaylari[0]['skor'] == metrik_adaylari[1]['skor']:
        spec['durum'] = 'netlestir'
        spec['mesaj'] = 'Bu soruda hangi onaylı metriği kastettiğinizi seçmem gerekiyor.'
        spec['secenekler'] = [{'kod': a['oge']['kod'], 'ad': a['oge']['ad'], 'tanim': a['oge']['tanim']}
                              for a in metrik_adaylari[:3]]
        spec['guven'] = 0.4
        return spec

    ana_metrik = metrik_adaylari[0]['oge']
    spec['metrikler'].append(ana_metrik['kod'])

    if (any(icerir(m, d) for d in ['onceki aya gore', 'gecen aya gore', 'nasil degisti', 'degisim'])
            and ana_metrik['kod'] != 'aylik_degisim'):
        spec['metrikler'].append('aylik_degisim')
        spec['aciklamalar'].append('Karşılaştırma istendiği için "Aylık Değişim %" ölçüsü de eklendi.')

    # --- 5) boyut (kırılım) ---
    for kod in boyutlari_coz(m, cozum):
        if kod not in spec['boyutlar']:
            spec['boyutlar'].append(kod)

    # --- 6) dönem ---
    donem = donem_coz(m)
    if donem['hataKapsam']:
        spec['durum'] = 'kapsam_disi'
        spec['mesaj'] = donem['hataKapsam']
        return spec
    spec['filtreler'].extend(donem['filtreler'])
    spec['donemIfade'] = donem['ifade']
    spec['belirsizlikler'].extend(donem['notlar'])

    # --- 7) boyut değeri filtreleri ---
    # Aynı boyuttan birden çok değer ('Marmara ve Ege') iki ayrı '=' filtresi
    # olarak eklenirse DAX'ta VE ile birleşir ve sonuç boş döner.
    boyuta_gore = {}
    for f in boyut_degeri_coz(m, cozum):
        boyuta_gore.setdefault(f['boyut'], []).append(f['deger'])
    for boyut_kod, degerler in boyuta_gore.items():
        if len(degerler) == 1:
            spec['filtreler'].append({'boyut': boyut_kod, 'operator': '=', 'deger': degerler[0]})
        else:
            spec['filtreler'].append({'boyut': boyut_kod, 'operator': 'in', 'deger': degerler})
            if boyut_kod not in spec['boyutlar']:
                spec['boyutlar'].append(boyut_kod)
            ad = (S.boyut_bul(boyut_kod) or {}).get('ad', boyut_kod)
            spec['aciklamalar'].append(
                'Birden fazla %s değeri soruldu; karşılaştırma için o boyutta kırılım eklendi.' % ad)

    if donem['kirilimGerek'] and donem['kirilimGerek'] not in spec['boyutlar']:
        spec['boyutlar'].append(donem['kirilimGerek'])

    # --- 7b) ölçünün desteklemediği boyut ---
    # İlişki yoksa DAX hata vermez; filtreyi sessizce yok sayıp her satırda
    # aynı sayıyı döndürür.
    for kod in spec['metrikler']:
        olculen = S.metrik_bul(kod)
        if not olculen or not olculen.get('gecerliBoyutlar'):
            continue
        kullanilan = spec['boyutlar'] + [f['boyut'] for f in spec['filtreler']]
        desteklenmeyen = []
        for b in kullanilan:
            if b not in olculen['gecerliBoyutlar'] and b not in desteklenmeyen:
                desteklenmeyen.append(b)
        if desteklenmeyen:
            adlar = [(S.boyut_bul(b) or {}).get('ad', b) for b in desteklenmeyen]
            spec['durum'] = 'kapsam_disi'
            spec['mesaj'] = '%s ölçüsü %s boyutuyla tanımlı değil.' % (olculen['ad'], ' / '.join(adlar))
            spec['alternatif'] = ('%s yalnızca dönem bazında sorulabilir. Bu kırılım için '
                                  'Net Ciro veya Satış Adet kullanabilirim.' % olculen['ad'])
            return spec

    # --- 7c) ileri analiz niyeti ---
    # Sıralamadan ÖNCE: tahmin/katkı sorularında top-N veya uç değer
    # mantığı devreye girmemeli, hesap tamamen farklı.
    if ileri:
        spec['ozel'] = ileri['ozel']
        if ileri.get('ufuk'):
            spec['tahminUfuk'] = ileri['ufuk']
        if ileri['ozel'] == 'katki':
            # Kırılım belirtilmemişse bölge varsayılan: en kaba ve en
            # yorumlanabilir kırılım o. Kullanıcı isterse belirtir.
            spec['katkiBoyut'] = spec['boyutlar'][0] if spec['boyutlar'] else 'bolge'
            if not spec['boyutlar']:
                spec['aciklamalar'].append(
                    'Kırılım belirtilmediği için bölge bazında ayrıştırıldı.')
        spec['guven'] = 0.70 if ileri['ozel'] in ('katki', 'hacim_sepet') else 0.60
        return spec

    # --- 8) sıralama ---
    if hangi_ay:
        spec['ozel'] = 'en_yuksek_donem'
        spec['boyutlar'] = ['donem']
        spec['siralama'] = {'olcut': spec['metrikler'][0],
                            'yon': 'artan' if (siralama and siralama['yon'] == 'artan') else 'azalan'}
        spec['limit'] = 1
    elif siralama:
        # "en çok ciro yapan 2 kanal hangisi" — burada çıplak boyut adı
        # kırılım kasteder. Bakılmazsa döneme göre kırılıp iki AY dönüyordu.
        if not spec['boyutlar']:
            en_iyi = None
            for b in S.BOYUTLAR:
                for ad in b.get('ciplakAdlar', []):
                    if dil.kalip_var_mi(cozum, ad) and (not en_iyi or len(ad) > en_iyi[1]):
                        en_iyi = (b['kod'], len(ad))
            spec['boyutlar'].append(en_iyi[0] if en_iyi else 'donem')
        spec['siralama'] = {'olcut': spec['metrikler'][0], 'yon': siralama['yon']}
        spec['limit'] = siralama['limit']

    # --- 9) modelde karşılığı olmayan metrik ---
    eksik = [S.metrik_bul(k) for k in spec['metrikler']]
    eksik = [x for x in eksik if x and not x.get('dax')]
    if eksik:
        spec['durum'] = 'kapsam_disi'
        spec['mesaj'] = ', '.join(x['ad'] for x in eksik) + ' ölçüsü semantik modelde tanımlı değil.'
        return spec

    # --- 10) güven skoru ---
    guven = 0.55
    guven += min(metrik_adaylari[0]['skor'] / 40.0, 0.2)     # eşleşme özgüllüğü
    if donem['filtreler']:
        guven += 0.12                                        # dönem netleşti
    if len(metrik_adaylari) == 1:
        guven += 0.08                                        # rakip aday yok
    if spec['belirsizlikler']:
        guven -= 0.10                                        # varsayım yaptık
    spec['guven'] = round(min(guven, 0.98), 2)

    return spec
