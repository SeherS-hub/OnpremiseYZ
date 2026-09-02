# -*- coding: utf-8 -*-
"""
İLERİ ANALİZ — tahmin, yıl sonu projeksiyonu, katkı ayrıştırması.

Planlayıcı bu niyetleri `spec['ozel']` ile işaretler; buradaki tek giriş
noktası gereken DAX'ları çalıştırıp hesabı yapar ve cevap metnini kurar.

Metin üretimi neden yorumlayici.py'de değil: bu cevapların dili hesaba
sıkı bağlı. Tahmin cümlesi aralığı, katkı cümlesi payları ve uyarıyı
taşımak zorunda; ayrı dosyada tutmak ikisini de yarım bırakırdı.

Üç kural, üçü de burada uygulanıyor:
  · Tahmin çıktısı her yerde TAHMİN diye etiketlenir.
  · Nokta tahmini asla aralıksız verilmez.
  · Katkı cevabı sebep iddia etmediğini AÇIKÇA yazar.
"""

from lib import sozlesme as S
from lib import calistir_dax
from lib import katki
from lib import tahmin
from lib.yorumlayici import sayi_bicimle, donem_dogal, metrik_ad_sade, tr_buyuk_ilk


def _ondalik(x):
    """R² gibi birimsiz sayılar için Türkçe ondalık ayırıcı. Cevabın geri
    kalanı virgül kullanırken künyede nokta görmek tutarsız duruyordu."""
    return ('%.2f' % (x or 0)).replace('.', ',')


def _met(spec):
    return S.metrik_bul(spec['metrikler'][0])


def _seri_sorgusu(met):
    """Metriğin dönem serisi — sıralı."""
    return ('EVALUATE\nSUMMARIZECOLUMNS (\n'
            '    Donem[DonemKey],\n    Donem[Dönem],\n'
            '    "%s", %s\n)\nORDER BY Donem[DonemKey] ASC' % (met['ad'], met['dax']))


def _kirilim_sorgusu(met, boyut, donem):
    b = S.boyut_bul(boyut)
    return ('EVALUATE\nSUMMARIZECOLUMNS (\n    %s,\n'
            '    FILTER ( ALL ( Donem[Dönem] ), Donem[Dönem] = "%s" ),\n'
            '    "%s", %s\n)' % (b['daxSutun'], donem, met['ad'], met['dax']))


def _uclu_sorgusu(donem):
    """Ciro, adet ve sepet — hacim/sepet ayrıştırması için."""
    f = 'FILTER ( ALL ( Donem[Dönem] ), Donem[Dönem] = "%s" )' % donem
    return ('EVALUATE\nROW (\n'
            '    "ciro",  CALCULATE ( [Net Ciro], %s ),\n'
            '    "adet",  CALCULATE ( [Satış Adet], %s ),\n'
            '    "sepet", CALCULATE ( [Ortalama Sepet], %s )\n)' % (f, f, f))


def _seri_al(met, ayar):
    sorgu = _seri_sorgusu(met)
    satirlar = calistir_dax.calistir(sorgu, ayar)['satirlar']
    etiketler = [str(s.get('Dönem')) for s in satirlar]
    degerler = []
    for s in satirlar:
        v = s.get(met['ad'])
        degerler.append(float(v) if v is not None else None)
    return etiketler, degerler, sorgu


def _sonraki_donemler(son_etiket, adet):
    """"2026-08" sonrası ay etiketleri. Model kapsamı dışına çıkar —
    zaten tahmin edilen dönemler onlar."""
    try:
        y, a = (int(x) for x in str(son_etiket).split('-'))
    except (ValueError, TypeError):
        return ['+%d' % (i + 1) for i in range(adet)]
    cikti = []
    for _ in range(adet):
        a += 1
        if a > 12:
            a = 1
            y += 1
        cikti.append('%04d-%02d' % (y, a))
    return cikti


def _etiketle(noktalar, son_etiket):
    """Tahmin noktalarına dönem etiketi yazar — model kapsamının ötesi."""
    donemler = _sonraki_donemler(son_etiket, len(noktalar))
    cikti = []
    for n, d in zip(noktalar, donemler):
        n = dict(n)
        n['etiket'] = d
        cikti.append(n)
    return cikti


def _seviye_belirsizlik(t):
    """Seviye tahmininin künyesi. Aralığın genişliğinin NEDEN o genişlikte
    olduğunu da yazıyor: aralığı okuyan kişi varsayımı da görmeli."""
    b = [
        'TAHMİN — gerçekleşme değil. Yöntem: %s. Doğrusal eğilim açıklayıcılığı '
        'R²=%s (eşik %s) olduğu için yön tahmini üretilmedi.'
        % (t['yontem'], _ondalik(t['r2']), _ondalik(t['esik'])),
        'Aralık %80 kestirim aralığıdır; gerçekleşme beşte bir olasılıkla dışına çıkar.',
    ]
    if t['altYontem'] == 'ortalama':
        b.append('Aralık her ufukta aynı genişlikte, çünkü ölçülen lag-1 '
                 'otokorelasyon %s: şoklar kalıcı değil, seri ortalamasına dönüyor.'
                 % _ondalik(t['otokorelasyon']))
    else:
        b.append('Aralık ufukla genişliyor, çünkü ölçülen lag-1 otokorelasyon %s: '
                 'şoklar kalıcı, her dönem yeni bir sapma ekliyor.'
                 % _ondalik(t['otokorelasyon']))
    if t['kirpildi']:
        b.append('İstenen ufuk %d döneme kırpıldı: %d dönem geçmişle daha ileriye '
                 'gitmek kestirim değil kehanet olur.' % (t['ufuk'], t['gozlem']))
    b.append('Seviye tahmini serinin kendi dağılımından gelir; kampanya, fiyat kararı, '
             'rekabet gibi dışsal etkiler bu modelde yok.')
    return b


def _baglam(etiketler, degerler, met, ek_noktalar=None):
    """Cevap kartı serisi. Tahmin noktaları 'tahmin' serisi olarak ayrı
    işaretlenir; kartta gerçekleşenle aynı renge girmemeleri için.

    Kestirim aralığı 'tahmin_alt' / 'tahmin_ust' serileriyle taşınır —
    kart bunları kesikli çizgi olarak çiziyor. Nokta tahmini aralıksız
    göstermek, olmayan bir kesinlik iddia etmek olurdu.

    Sıra numarası gerçekleşenin ardından devam eder; birleşik anahtar
    (KayitId, Seri, Sira) aynı sırayı farklı seride tutmaya izin
    verdiği için üç tahmin serisi aynı sıra numarasını paylaşır."""
    olcek = 1000000.0 if met['birim'] == 'TRY' else 1.0
    cikti = []
    for i, (e, d) in enumerate(zip(etiketler, degerler), start=1):
        cikti.append({'seri': 'trend', 'sira': i, 'etiket': e,
                      'deger': (d or 0) / olcek})
    for j, n in enumerate(ek_noktalar or [], start=len(etiketler) + 1):
        cikti.append({'seri': 'tahmin', 'sira': j, 'etiket': n['etiket'],
                      'deger': n['deger'] / olcek})
        if n.get('alt') is not None and n.get('ust') is not None:
            cikti.append({'seri': 'tahmin_alt', 'sira': j,
                          'etiket': n['etiket'], 'deger': n['alt'] / olcek})
            cikti.append({'seri': 'tahmin_ust', 'sira': j,
                          'etiket': n['etiket'], 'deger': n['ust'] / olcek})
    return cikti


# ====================================================================
# TAHMİN
# ====================================================================
def _tahmin(spec, ayar):
    met = _met(spec)
    etiketler, degerler, sorgu = _seri_al(met, ayar)
    ufuk = int(spec.get('tahminUfuk') or 1)
    t = tahmin.tahminle(degerler, ufuk)
    ad = metrik_ad_sade(met['ad'])

    if t['durum'] == 'yetersiz_veri':
        return {
            'metin': ('Tahmin için yeterli geçmiş yok: %d dönem var, en az %d gerekiyor.'
                      % (t['gozlem'], t['gereken'])),
            'aciklama': 'Tahmin üretilemedi — geçmiş seri çok kısa.',
            'satirlar': [], 'baglam': _baglam(etiketler, degerler, met),
            'sorgu': sorgu, 'belirsizlikler': [], 'vurgu': None,
        }

    if t['durum'] == 'seviye':
        # Eğilim yok. Eskiden burada tahmin ÜRETİLMİYORDU; artık yön
        # iddiası olmayan bir seviye tahmini veriliyor. Fark önemli:
        # "önümüzdeki ay şu bandın içinde olmasını bekliyorum" dürüst bir
        # cümle, "şu kadar artacak" ise bu seride uydurma olurdu.
        noktalar = _etiketle(t['noktalar'], etiketler[-1])
        ilk = noktalar[0]
        bicim = lambda x: sayi_bicimle(x, met['birim'])   # noqa: E731
        if t['altYontem'] == 'ortalama':
            # Aralık her dönemde aynı; üç kez aynı sayıyı yazmak gürültü.
            kapsam = ('önümüzdeki dönem için' if t['ufuk'] == 1
                      else 'önümüzdeki %d dönemin her biri için aynı:' % t['ufuk'])
            beklenti = ('%s son %d dönemin ortalaması **%s**, %%80 aralık **%s – %s**'
                        % (kapsam, t['gozlem'], bicim(ilk['deger']),
                           bicim(ilk['alt']), bicim(ilk['ust'])))
        else:
            beklenti = ('son gerçekleşen seviye taşınarak ' + '; '.join(
                '%s **%s** (%%80 aralık: %s – %s)'
                % (donem_dogal(n['etiket']), bicim(n['deger']),
                   bicim(n['alt']), bicim(n['ust'])) for n in noktalar))
        return {
            'metin': ('**TAHMİN · SEVİYE** · %s: seride belirgin bir yön yok '
                      '(R²=%s, eşik %s) — bu yüzden artış/azalış tahmini '
                      'yapmıyorum. Beklenti %s. Bu bir seviye tahminidir, yön '
                      'iddiası içermez.'
                      % (ad, _ondalik(t['r2']), _ondalik(t['esik']), beklenti)),
            'aciklama': ('%s serisinde belirgin eğilim yok; %d dönem ileri için yön '
                         'iddiası olmayan seviye tahmini verildi.'
                         % (tr_buyuk_ilk(ad), t['ufuk'])),
            'satirlar': [{'Dönem': n['etiket'], met['ad']: n['deger']}
                         for n in noktalar],
            'baglam': _baglam(etiketler, degerler, met, noktalar),
            'sorgu': sorgu,
            'belirsizlikler': _seviye_belirsizlik(t),
            'vurgu': {'etiket': 'TAHMİN · seviye · ' + donem_dogal(ilk['etiket']),
                      'deger': sayi_bicimle(ilk['deger'], met['birim'])},
        }

    noktalar = _etiketle(t['noktalar'], etiketler[-1])
    ilk = noktalar[0]
    parcalar = []
    for n in noktalar:
        parcalar.append('%s **%s** (%%80 aralık: %s – %s)'
                        % (donem_dogal(n['etiket']),
                           sayi_bicimle(n['deger'], met['birim']),
                           sayi_bicimle(n['alt'], met['birim']),
                           sayi_bicimle(n['ust'], met['birim'])))

    belirsizlik = [
        'TAHMİN — gerçekleşme değil. Yöntem: %s, %d dönem geçmiş, R²=%s.'
        % (t['yontem'], t['gozlem'], _ondalik(t['r2'])),
        # Bu dize % işlecinden GEÇMEZ; %% yazmak kullanıcıya "%%80" gösterir.
        'Aralık %80 kestirim aralığıdır; gerçekleşme beşte bir olasılıkla dışına çıkar.',
    ]
    if t['kirpildi']:
        belirsizlik.append('İstenen ufuk %d döneme kırpıldı: %d dönem geçmişle daha '
                           'ileriye gitmek kestirim değil kehanet olur.'
                           % (t['ufuk'], t['gozlem']))

    return {
        'metin': '**TAHMİN** · ' + ad + ': ' + '; '.join(parcalar) + '.',
        'aciklama': ('%s için %d dönem ileri doğrusal eğilim tahmini. Gerçekleşme değil, '
                     'kestirimdir.' % (tr_buyuk_ilk(ad), t['ufuk'])),
        'satirlar': [{'Dönem': n['etiket'], met['ad']: n['deger']} for n in noktalar],
        'baglam': _baglam(etiketler, degerler, met, noktalar),
        'sorgu': sorgu,
        'belirsizlikler': belirsizlik,
        'vurgu': {'etiket': 'TAHMİN · ' + donem_dogal(ilk['etiket']),
                  'deger': sayi_bicimle(ilk['deger'], met['birim'])},
    }


# ====================================================================
# YIL SONU PROJEKSİYONU
# ====================================================================
def _yil_sonu(spec, ayar):
    met = _met(spec)

    # Koşu hızı projeksiyonu DÖNEMLERİ TOPLAR. Toplanamaz bir ölçüyle
    # bunu yapmak saçmalık üretiyordu: "Yıl sonunda hedefe ulaşır mıyız"
    # sorusu Hedef Gerçekleşme %'ye eşleşiyor ve yüzdeler toplanıp
    # "793,8%" çıkıyordu.
    #
    # "Hedefe ulaşır mıyız" sorusunun doğru cevabı Net Ciro projeksiyonunu
    # Hedef ile karşılaştırmaktır; oraya YÖNLENDİRİYORUZ ve bunu söylüyoruz.
    yonlendirme = None
    if met['kod'] == 'hedef_gerceklesme':
        yonlendirme = ('Soru hedef gerçekleşmesini işaret ediyor ama oran '
                       'toplanamaz; projeksiyon Net Ciro üzerinden yapıldı ve '
                       'gerçekleşen dönemlerin hedefiyle karşılaştırıldı.')
        met = S.metrik_bul('net_ciro')
    elif met.get('toplanabilir') is False:
        ad = metrik_ad_sade(met['ad'])
        return {
            'metin': ('**%s dönemler boyunca toplanamaz**, bu yüzden yıl sonu koşu '
                      'hızı projeksiyonu bu ölçü için anlamsız olur. Toplanabilir '
                      'ölçülerle sorabilirsiniz: net ciro, satış adet, hedef, '
                      'hedef sapma.' % tr_buyuk_ilk(ad)),
            'aciklama': '%s için yıl sonu projeksiyonu tanımlı değil.' % tr_buyuk_ilk(ad),
            'satirlar': [], 'baglam': [], 'sorgu': None,
            'belirsizlikler': ['Projeksiyon dönemleri toplar; oran, ortalama, tekil '
                               'sayım ve birikimli ölçüler toplanamaz.'],
            'vurgu': None,
        }

    etiketler, degerler, sorgu = _seri_al(met, ayar)

    yil = None
    for f in spec.get('filtreler') or []:
        if f['boyut'] == 'yil':
            yil = int(f['deger'])
    if yil is None:
        yil = int(str(etiketler[-1]).split('-')[0])

    ikili = [(e, d) for e, d in zip(etiketler, degerler)
             if str(e).startswith(str(yil)) and d is not None]
    if not ikili:
        return {
            'metin': '%d yılına ait dönem modelde yok.' % yil,
            'aciklama': 'Projeksiyon yapılamadı.', 'satirlar': [],
            'baglam': _baglam(etiketler, degerler, met), 'sorgu': sorgu,
            'belirsizlikler': [], 'vurgu': None,
        }

    son_ay = int(str(ikili[-1][0]).split('-')[1])
    kalan = 12 - son_ay
    p = tahmin.yil_sonu_projeksiyon([d for _, d in ikili], kalan)
    ad = metrik_ad_sade(met['ad'])

    if kalan == 0:
        return {
            'metin': '%d yılı tamamlanmış: %s **%s**.'
                     % (yil, ad, sayi_bicimle(p['gerceklesen'], met['birim'])),
            'aciklama': '%d yılı %s — yıl tamamlandı, projeksiyon gerekmiyor.' % (yil, ad),
            'satirlar': [], 'baglam': _baglam(etiketler, degerler, met),
            'sorgu': sorgu, 'belirsizlikler': [], 'vurgu': None,
        }

    metin = ('%d yılının **%d ayı** gerçekleşti: %s **%s**. Aylık ortalama hız '
             '**%s**; bu hız korunursa yıl **%s** ile kapanır.'
             % (yil, p['donemSayisi'], ad,
                sayi_bicimle(p['gerceklesen'], met['birim']),
                sayi_bicimle(p['hiz'], met['birim']),
                sayi_bicimle(p['yilSonu'], met['birim'])))

    # Hedef karşılaştırması — AYNI DÖNEM ARALIĞI üzerinden.
    #
    # Burada bir tuzak var ve ilk sürümde ona düştük: modeldeki hedef
    # yalnız var olan 8 dönemi kapsıyor. 12 aylık projeksiyonu 8 aylık
    # hedefe bölmek "%148,8" gibi anlamsız ama ikna edici bir sayı
    # üretiyordu. Elmayla armut karşılaştırmasını dipnotla kurtarmak
    # olmaz; cümlenin kendisi doğru olmalı.
    #
    # Doğru karşılaştırma: gerçekleşen dönemler ile aynı dönemlerin
    # hedefi (YTD gerçekleşme). Tam yıl hedefi modelde YOK, o yüzden tam
    # yıl karşılaştırması da yapılmıyor — bunu açıkça söylüyoruz.
    hedef_met = S.metrik_bul('hedef')
    ek = []
    if met['kod'] == 'net_ciro' and hedef_met:
        aylar = [str(e).split('-')[1] for e, _ in ikili]
        kosul = ' || '.join('Donem[Dönem] = "%s"' % e for e, _ in ikili)
        hs = ('EVALUATE\nROW ( "hedef", CALCULATE ( %s,\n'
              '    FILTER ( ALL ( Donem[Dönem] ), %s ) ) )' % (hedef_met['dax'], kosul))
        try:
            h = calistir_dax.calistir(hs, ayar)['satirlar'][0].get('hedef')
            h = float(h) if h is not None else None
        except Exception:
            h = None
        if h:
            oran = p['gerceklesen'] / h
            metin += (' Aynı %d ayın hedefi **%s**; gerçekleşme **%%%s** — '
                      '%s. Tam yıl hedefi modelde olmadığı için yıl sonu '
                      'projeksiyonu hedefle KARŞILAŞTIRILMADI.'
                      % (len(aylar), sayi_bicimle(h, 'TRY'),
                         ('%.1f' % (oran * 100)).replace('.', ','),
                         'hedefin üzerinde' if oran >= 1 else 'hedefin altında'))
            ek.append('Hedef karşılaştırması gerçekleşen %d dönemle AYNI aralık '
                      'üzerinedir. Kalan %d ay için hedef verisi modele girildiğinde '
                      'tam yıl karşılaştırması da yapılabilir.' % (len(aylar), kalan))

    return {
        'metin': metin,
        'aciklama': ('%d yılı %s · %d ay gerçekleşen üzerinden koşu hızı projeksiyonu.'
                     % (yil, ad, p['donemSayisi'])),
        'satirlar': [],
        'baglam': _baglam(etiketler, degerler, met),
        'sorgu': sorgu,
        'belirsizlikler': ([yonlendirme] if yonlendirme else []) + [
            'PROJEKSİYON — tahmin modeli değil, ortalama koşu hızı aritmetiği: '
            'gerçekleşen / dönem sayısı × kalan dönem.',
            'Mevsimsellik hesaba KATILMADI; model bir tam yıl içermiyor.',
        ] + ek,
        'vurgu': {'etiket': '%d yıl sonu projeksiyonu' % yil,
                  'deger': sayi_bicimle(p['yilSonu'], met['birim'])},
    }


# ====================================================================
# KATKI AYRIŞTIRMASI
# ====================================================================
def _iki_donem(spec, etiketler):
    """Karşılaştırılacak iki dönem. Soruda tek dönem varsa o ve öncesi."""
    secili = []
    for f in spec.get('filtreler') or []:
        if f['boyut'] == 'donem':
            if isinstance(f['deger'], list):
                secili.extend(str(x) for x in f['deger'])
            else:
                secili.append(str(f['deger']))
    secili = sorted(set(secili))
    if len(secili) >= 2:
        return secili[-2], secili[-1]
    if len(secili) == 1 and secili[0] in etiketler:
        i = etiketler.index(secili[0])
        if i > 0:
            return etiketler[i - 1], etiketler[i]
    if len(etiketler) >= 2:
        return etiketler[-2], etiketler[-1]
    return None, None


def _katki(spec, ayar):
    met = _met(spec)

    # Katkı ayrıştırması KALEMLERİ TOPLAR: kalemlerin değişimi toplam
    # değişime eşit olmalı. Oran ve ortalama ölçülerde bu eşitlik yok —
    # bölgelerin gerçekleşme yüzdelerinin toplamı toplam gerçekleşmeye
    # eşit değildir. "Aritmetik kapalıdır" iddiası ancak toplanabilir
    # ölçüde doğru; yoksa reddediyoruz.
    if met.get('toplanabilir') is False:
        ad = metrik_ad_sade(met['ad'])
        return {
            'metin': ('**%s için katkı ayrıştırması yapılamaz**: bu ölçü kalemler '
                      'boyunca toplanmaz, dolayısıyla "şu kalem şu kadarını çekti" '
                      'demek aritmetik olarak yanlış olur. Net ciro, satış adet veya '
                      'hedef sapma üzerinden sorabilirsiniz.' % tr_buyuk_ilk(ad)),
            'aciklama': '%s için katkı ayrıştırması tanımlı değil.' % tr_buyuk_ilk(ad),
            'satirlar': [], 'baglam': [], 'sorgu': None,
            'belirsizlikler': ['Katkı ayrıştırması kalemlerin toplamının toplam '
                               'değişime eşit olmasını gerektirir; oran ve ortalama '
                               'ölçülerde bu eşitlik sağlanmaz.'],
            'vurgu': None,
        }

    etiketler, degerler, seri_sorgu = _seri_al(met, ayar)
    onceki_d, simdiki_d = _iki_donem(spec, etiketler)
    if not onceki_d or not simdiki_d:
        return {
            'metin': 'Karşılaştırma için iki dönem gerekiyor; modelde yeterli dönem yok.',
            'aciklama': 'Katkı ayrıştırması yapılamadı.', 'satirlar': [],
            'baglam': _baglam(etiketler, degerler, met), 'sorgu': seri_sorgu,
            'belirsizlikler': [], 'vurgu': None,
        }

    boyut = spec.get('katkiBoyut') or (spec['boyutlar'][0] if spec['boyutlar'] else 'bolge')
    b = S.boyut_bul(boyut)
    s1 = _kirilim_sorgusu(met, boyut, onceki_d)
    s2 = _kirilim_sorgusu(met, boyut, simdiki_d)
    toplu = calistir_dax.calistir_coklu(
        [{'ad': 'onceki', 'dax': s1}, {'ad': 'simdiki', 'dax': s2}], ayar)
    k = katki.boyut_katkisi(toplu['onceki'], toplu['simdiki'], b['ad'], met['ad'])

    ad = metrik_ad_sade(met['ad'])
    yon = 'düştü' if k['toplamDegisim'] < 0 else 'arttı'
    ilk_uc = k['kalemler'][:3]
    parcalar = []
    for x in ilk_uc:
        pay = ('%%%d' % round(abs(x['pay']) * 100)) if x['pay'] is not None else '—'
        parcalar.append('%s **%s** (%s)'
                        % (x['etiket'], sayi_bicimle(x['degisim'], met['birim']), pay))

    metin = ('%s → %s arasında %s **%s** %s. %s kırılımında en çok katkı: %s.'
             % (donem_dogal(onceki_d), donem_dogal(simdiki_d), ad,
                sayi_bicimle(k['toplamDegisim'], met['birim']), yon,
                b['ad'], '; '.join(parcalar)))

    ters = [x for x in k['kalemler']
            if (x['degisim'] > 0) != (k['toplamDegisim'] > 0) and abs(x['degisim']) > 0]
    if ters:
        metin += (' Ters yönde: %s.'
                  % ', '.join('%s %s' % (x['etiket'],
                                         sayi_bicimle(x['degisim'], met['birim']))
                              for x in ters[:3]))

    return {
        'metin': metin,
        'aciklama': ('%s → %s · %s %s kırılımında katkı ayrıştırması.'
                     % (donem_dogal(onceki_d), donem_dogal(simdiki_d),
                        met['ad'], b['ad'].lower())),
        'satirlar': [{b['ad']: x['etiket'], met['ad']: x['degisim']}
                     for x in k['kalemler']],
        'baglam': _baglam(etiketler, degerler, met),
        'sorgu': s1 + '\n\n/* ve */\n\n' + s2,
        'belirsizlikler': [katki.UYARI,
                           'Katkıların toplamı toplam değişime eşittir — aritmetik '
                           'kapalıdır, kalıntı yoktur.'],
        'vurgu': {'etiket': '%s → %s · %s' % (onceki_d, simdiki_d, b['ad']),
                  'deger': sayi_bicimle(k['toplamDegisim'], met['birim'])},
    }


def _hacim_sepet(spec, ayar):
    met = S.metrik_bul('net_ciro')
    etiketler, degerler, seri_sorgu = _seri_al(met, ayar)
    onceki_d, simdiki_d = _iki_donem(spec, etiketler)
    if not onceki_d or not simdiki_d:
        return {
            'metin': 'Karşılaştırma için iki dönem gerekiyor.',
            'aciklama': 'Ayrıştırma yapılamadı.', 'satirlar': [],
            'baglam': _baglam(etiketler, degerler, met), 'sorgu': seri_sorgu,
            'belirsizlikler': [], 'vurgu': None,
        }

    q1, q2 = _uclu_sorgusu(onceki_d), _uclu_sorgusu(simdiki_d)
    toplu = calistir_dax.calistir_coklu(
        [{'ad': 'a', 'dax': q1}, {'ad': 'b', 'dax': q2}], ayar)
    h = katki.hacim_sepet_ayristirmasi(toplu['a'][0], toplu['b'][0])
    if not h:
        return {
            'metin': 'Hacim/sepet ayrıştırması için gereken ölçüler okunamadı.',
            'aciklama': 'Ayrıştırma yapılamadı.', 'satirlar': [],
            'baglam': _baglam(etiketler, degerler, met), 'sorgu': q1,
            'belirsizlikler': [], 'vurgu': None,
        }

    baskin = ('adet' if h['baskin'] == 'hacim' else 'ortalama sepet')
    metin = ('%s → %s arasında net ciro **%s** değişti. Bunun **%s**\'si adet '
             'değişiminden (%s adet), **%s**\'si ortalama sepet değişiminden '
             '(%s) geliyor; etkileşim **%s**. Baskın etken: **%s**.'
             % (donem_dogal(onceki_d), donem_dogal(simdiki_d),
                sayi_bicimle(h['ciroDegisim'], 'TRY'),
                sayi_bicimle(h['hacimEtkisi'], 'TRY'),
                ('%+d' % h['adetDegisim']).replace('+', '+'),
                sayi_bicimle(h['sepetEtkisi'], 'TRY'),
                sayi_bicimle(h['sepetDegisim'], 'TRY'),
                sayi_bicimle(h['etkilesim'], 'TRY'), baskin))

    return {
        'metin': metin,
        'aciklama': ('%s → %s · net ciro değişiminin adet ve sepet etkisine '
                     'ayrıştırması.' % (donem_dogal(onceki_d), donem_dogal(simdiki_d))),
        'satirlar': [
            {'Etken': 'Adet (hacim)', 'Net Ciro': h['hacimEtkisi']},
            {'Etken': 'Ortalama sepet', 'Net Ciro': h['sepetEtkisi']},
            {'Etken': 'Etkileşim', 'Net Ciro': h['etkilesim']},
        ],
        'baglam': _baglam(etiketler, degerler, met),
        'sorgu': q1 + '\n\n/* ve */\n\n' + q2,
        'belirsizlikler': [
            'Ciro = Adet × Sepet olduğundan bu ayrıştırma CEBİRDİR, model değil: '
            'üç etkinin toplamı ciro değişimine eşittir.',
            katki.UYARI,
        ],
        'vurgu': {'etiket': 'baskın etken · %s' % baskin,
                  'deger': sayi_bicimle(h['ciroDegisim'], 'TRY')},
    }


# ====================================================================
DAGITICI = {
    'tahmin': _tahmin,
    'yil_sonu': _yil_sonu,
    'katki': _katki,
    'hacim_sepet': _hacim_sepet,
}


def destekliyor(ozel):
    return ozel in DAGITICI


def calistir(spec, ayar):
    return DAGITICI[spec['ozel']](spec, ayar)
