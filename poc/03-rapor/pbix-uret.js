'use strict';
/* ===================================================================
   SatisDashboardPBI.pbix ureteci

   .pbix bir OPC/ZIP paketidir. Canli baglantili (live connection) bir
   rapor icin paketin icinde veri modeli YOKTUR; yalnizca baglanti
   tanimi ve rapor yerlesimi bulunur. Bu yuzden dosyayi elle uretmek
   mumkun ve deterministik.

   Uretilen parcalar:
     [Content_Types].xml   OPC icerik tipleri            (UTF-8)
     Version               pbix bicim surumu             (UTF-16LE)
     Connections           SSAS canli baglanti tanimi    (UTF-16LE)
     Report/Layout         gorsel yerlesimi              (UTF-16LE)

   Settings / Metadata / SecurityBindings parcalari opsiyoneldir;
   Power BI Desktop dosyayi ilk kaydedisinde kendisi olusturur.

   Calistirma:  node pbix-uret.js
   =================================================================== */

const fs   = require('fs');
const path = require('path');
const zlib = require('zlib');

const SUNUCU = process.env.POC_SSAS_SUNUCU || 'localhost\\TABULAR';
const MODEL  = process.env.POC_SSAS_MODEL  || 'POC_Satis';
const AJAN   = process.env.POC_AJAN_URL    || 'http://localhost:8787/';
const CIKTI  = path.join(__dirname, 'SatisDashboardPBI.pbix');

/* ================= renk paleti (poc-tema.json ile ayni) ============ */
const R = {
  teal:    '#1B5C77',
  bakir:   '#A9541E',
  yesil:   '#2C6B4C',
  kirmizi: '#93262B',
  metin:   '#141A20',
  soluk:   '#7D919B',
  ikincil: '#48565D',
  cizgi:   '#DCE5E9',
  izgara:  '#EAF0F2',
  zemin:   '#FFFFFF',
  sayfa:   '#F4F7F8'
};

/* ================= ifade yardimcilari ==============================
   Power BI bicimlendirme degerlerini expr/Literal sarmalinda tutar.
   Sayilar sonuna D (double), metinler tek tirnak icinde yazilir.      */
const say  = v => ({ expr: { Literal: { Value: String(v) + 'D' } } });
const met  = v => ({ expr: { Literal: { Value: "'" + String(v).replace(/'/g, "''") + "'" } } });
const mnt  = v => ({ expr: { Literal: { Value: v ? 'true' : 'false' } } });
const renk = v => ({ solid: { color: met(v) } });

/* Her gorselin ortak cercevesi: beyaz zemin, ince kenarlik, gizli ust
   bant. Tema dosyasina bagimli olmamak icin degerler dogrudan gorsele
   yaziliyor; dosya tema secilmeden de dogru gorunuyor.                 */
function kabuk(baslik) {
  const o = {
    background:   [{ properties: { show: mnt(true), color: renk(R.zemin) } }],
    border:       [{ properties: { show: mnt(true), color: renk(R.cizgi), radius: say(4) } }],
    dropShadow:   [{ properties: { show: mnt(false) } }],
    visualHeader: [{ properties: { show: mnt(false) } }]
  };
  o.title = baslik
    ? [{ properties: {
        show: mnt(true), text: met(baslik), fontSize: say(9),
        fontColor: renk(R.soluk), alignment: met('left'), titleWrap: mnt(false)
      } }]
    : [{ properties: { show: mnt(false) } }];
  return o;
}

/* ================= sorgu yardimcilari ============================== */
const takma = t => t.charAt(0).toLowerCase() + t;

function kaynak(tablo) { return { Name: takma(tablo), Entity: tablo, Type: 0 }; }

function olcu(tablo, ad) {
  return {
    Measure: { Expression: { SourceRef: { Source: takma(tablo) } }, Property: ad },
    Name: tablo + '.' + ad,
    NativeReferenceName: ad
  };
}
function kolon(tablo, ad) {
  return {
    Column: { Expression: { SourceRef: { Source: takma(tablo) } }, Property: ad },
    Name: tablo + '.' + ad,
    NativeReferenceName: ad
  };
}
function ref(tablo, ad) { return { queryRef: tablo + '.' + ad }; }

/* alan listesinden From/Select uretir; tablo tekrarlari teklestirilir */
function sorgu(alanlar) {
  const tablolar = [];
  for (const a of alanlar) if (tablolar.indexOf(a.tablo) === -1) tablolar.push(a.tablo);
  return {
    Version: 2,
    From: tablolar.map(kaynak),
    Select: alanlar.map(a => (a.tur === 'o' ? olcu(a.tablo, a.ad) : kolon(a.tablo, a.ad)))
  };
}
const O = (t, a) => ({ tur: 'o', tablo: t, ad: a });   // olcu
const K = (t, a) => ({ tur: 'k', tablo: t, ad: a });   // kolon

/* ================= gorsel kabi ===================================== */
let z = 0;
function gorsel(ad, x, y, w, h, tek) {
  z += 1000;
  return {
    x: x, y: y, z: z, width: w, height: h,
    config: JSON.stringify({
      name: ad,
      layouts: [{ id: 0, position: { x: x, y: y, z: z, width: w, height: h, tabOrder: z } }],
      singleVisual: tek
    }),
    filters: '[]'
  };
}

/* Veriye bagli gorsel: projeksiyon ve sorgu ayni alan listesinden. */
function veriGorseli(ad, tip, x, y, w, h, kuyular, baslik, ekObjeler) {
  const projections = {};
  const alanlar = [];
  for (const kuyu of Object.keys(kuyular)) {
    projections[kuyu] = kuyular[kuyu].map(a => ref(a.tablo, a.ad));
    for (const a of kuyular[kuyu]) alanlar.push(a);
  }
  return gorsel(ad, x, y, w, h, {
    visualType: tip,
    projections: projections,
    prototypeQuery: sorgu(alanlar),
    drillFilterOtherVisuals: true,
    objects: ekObjeler || {},
    vcObjects: kabuk(baslik)
  });
}

/* KPI karti. birim: 1 = yok, 1000000 = milyon.
   Not: olcunun bicim dizesi zaten " TL" ekliyor; milyon birimi secilirse
   sonuc "892.5MTL" gibi cikiyor. Bu yuzden birim yok, punto kucuk.      */
function kart(ad, x, olcuAdi, baslik, birim, basamak, punto) {
  return veriGorseli(ad, 'card', x, 76, 232, 104,
    { Values: [O('Satis', olcuAdi)] }, baslik,
    {
      labels: [{ properties: {
        color: renk(R.metin), fontSize: say(punto || 26), fontFamily: met('Segoe UI Bold'),
        labelDisplayUnits: say(birim), labelPrecision: say(basamak)
      } }],
      categoryLabels: [{ properties: { show: mnt(false) } }],
      wordWrap: [{ properties: { show: mnt(false) } }]
    });
}

/* Tablo ve matris icin ortak izgara bicimi. */
function izgara() {
  return {
    grid: [{ properties: {
      gridVertical: mnt(false), gridHorizontalColor: renk(R.izgara), rowPadding: say(3)
    } }],
    columnHeaders: [{ properties: {
      fontColor: renk(R.soluk), backColor: renk(R.izgara), fontSize: say(9)
    } }],
    values: [{ properties: { fontColorPrimary: renk(R.metin), fontSize: say(10) } }]
  };
}

/* ================= sayfa ============================================ */
const gorseller = [];

/* --- baslik --- */
gorseller.push(gorsel('bslk', 24, 6, 620, 68, {
  visualType: 'textbox',
  drillFilterOtherVisuals: true,
  objects: { general: [{ properties: { paragraphs: [
    { horizontalTextAlignment: 'left', textRuns: [{
      value: 'SATIŞ PERFORMANSI',
      textStyle: { fontFamily: 'Segoe UI', fontSize: '20pt', fontWeight: 'bold', color: R.metin }
    }] },
    { horizontalTextAlignment: 'left', textRuns: [{
      value: 'Kaynak: SSAS Tabular · POC_Satis · canlı bağlantı',
      textStyle: { fontFamily: 'Segoe UI', fontSize: '9pt', color: R.soluk }
    }] }
  ] } }] },
  vcObjects: {
    background:   [{ properties: { show: mnt(false) } }],
    border:       [{ properties: { show: mnt(false) } }],
    visualHeader: [{ properties: { show: mnt(false) } }],
    title:        [{ properties: { show: mnt(false) } }]
  }
}));

/* --- donem secici --- */
gorseller.push(veriGorseli('slcDonem', 'slicer', 1024, 16, 232, 196,
  { Values: [K('Donem', 'Dönem')] }, 'DÖNEM',
  {
    items:  [{ properties: { fontColor: renk(R.ikincil), fontSize: say(10) } }],
    header: [{ properties: { show: mnt(false) } }]
  }));

/* --- KPI seridi --- */
gorseller.push(kart('kpiCiro',   24, 'Net Ciro',            'NET CİRO',          1, 0, 20));
gorseller.push(kart('kpiHedef', 272, 'Hedef Gerçekleşme %', 'HEDEF GERÇEKLEŞME', 1, 1, 26));
gorseller.push(kart('kpiAdet',  520, 'Satış Adet',          'SATIŞ ADEDİ',       1, 0, 26));
gorseller.push(kart('kpiSepet', 768, 'Ortalama Sepet',      'ORTALAMA SEPET',    1, 0, 26));

/* --- ajana gecis dugmesi --- */
/* Yukseklik baslik bandinin yuksekligiyle ayni; fazlasi dugmenin altinda
   ince bir teal serit olarak gorunuyor.                                  */
/* actionButton DEGIL. Dugmenin web adresi aksiyonu (vcObjects.visualLink)
   bu istemcide gorsele yalnizca role="link" ekliyor, tiklamada hicbir sey
   yapmiyor — fare olayi da Enter de tetiklemiyor. Metin kutusunun koprulu
   metin parcasi ise gercek bir <a href> uretiyor ve calisiyor.           */
gorseller.push(gorsel('btnAjan', 24, 196, 976, 32, {
  visualType: 'textbox',
  drillFilterOtherVisuals: true,
  objects: { general: [{ properties: { paragraphs: [{
    horizontalTextAlignment: 'center',
    textRuns: [{
      value: 'Yönetici Asistanına sor — sesli veya yazılı  →',
      url: AJAN,
      textStyle: {
        fontFamily: 'Segoe UI', fontSize: '11pt', fontWeight: 'bold',
        color: '#FFFFFF', textDecoration: 'none'
      }
    }]
  }] } }] },
  vcObjects: {
    background:   [{ properties: { show: mnt(true), color: renk(R.teal), transparency: say(0) } }],
    border:       [{ properties: { show: mnt(false) } }],
    visualHeader: [{ properties: { show: mnt(false) } }],
    title:        [{ properties: { show: mnt(false) } }]
  }
}));

/* --- aylik trend: kolon gerceklesen, cizgi hedef --- */
gorseller.push(veriGorseli('grfTrend', 'lineClusteredColumnComboChart', 24, 248, 816, 216,
  {
    Category: [K('Donem', 'Dönem')],
    Y:        [O('Satis', 'Net Ciro')],
    Y2:       [O('Satis', 'Hedef')]
  },
  'AYLIK CİRO VE HEDEF',
  {
    dataPoint: [
      { properties: { fill: renk(R.teal)  }, selector: { metadata: 'Satis.Net Ciro' } },
      { properties: { fill: renk(R.bakir) }, selector: { metadata: 'Satis.Hedef' } }
    ],
    categoryAxis: [{ properties: {
      show: mnt(true), showAxisTitle: mnt(false), gridlineShow: mnt(false),
      fontSize: say(9), labelColor: renk(R.ikincil)
    } }],
    valueAxis: [{ properties: {
      show: mnt(true), showAxisTitle: mnt(false), fontSize: say(9),
      labelColor: renk(R.ikincil), gridlineColor: renk(R.izgara), secShow: mnt(false),
      labelDisplayUnits: say(1000000)
    } }],
    legend: [{ properties: {
      show: mnt(true), position: met('TopCenter'), showTitle: mnt(false),
      fontSize: say(9), labelColor: renk(R.ikincil)
    } }]
  }));

/* --- bolge kirilimi --- */
gorseller.push(veriGorseli('tblBolge', 'tableEx', 856, 248, 400, 216,
  { Values: [K('Bolge', 'Bölge'), O('Satis', 'Net Ciro'), O('Satis', 'Hedef Gerçekleşme %')] },
  'BÖLGE KIRILIMI', izgara()));

/* --- urun grubu x kanal --- */
gorseller.push(veriGorseli('mtrUrun', 'pivotTable', 24, 480, 560, 216,
  {
    Rows:    [K('UrunGrubu', 'Ürün Grubu')],
    Columns: [K('Kanal', 'Kanal')],
    Values:  [O('Satis', 'Net Ciro')]
  },
  'ÜRÜN GRUBU × KANAL', izgara()));

/* --- aylik detay --- */
gorseller.push(veriGorseli('tblAy', 'tableEx', 600, 480, 656, 216,
  { Values: [
      K('Donem', 'Dönem'),
      O('Satis', 'Net Ciro'),
      O('Satis', 'Hedef'),
      O('Satis', 'Hedef Gerçekleşme %'),
      O('Satis', 'Aylık Değişim %'),
      O('Satis', 'Kümülatif Ciro')
    ] },
  'AYLIK DETAY', izgara()));

/* ================= tema kaynagi =====================================
   Gercek .pbix dosyalarinda tema her zaman bir kaynak paketi olarak
   gomulu gelir. Yalnizca config'te tema adi yazip dosyayi koymazsak
   istemci temayi cozemiyor ve tuvali hic cizmiyor. poc-tema.json
   zaten gecerli bir Power BI tema belgesi; temel tema olarak gomuluyor. */
const TEMA_AD  = 'CY24SU10';
const TEMA_YOL = 'BaseThemes/' + TEMA_AD + '.json';
const temaIcerik = fs.readFileSync(path.join(__dirname, 'poc-tema.json'), 'utf8');

/* ================= yerlesim ======================================== */
const yerlesim = {
  id: 0,
  resourcePackages: [{
    resourcePackage: {
      name: 'SharedResources',
      type: 2,
      disabled: false,
      items: [{ name: TEMA_AD, path: TEMA_YOL, type: 202 }]
    }
  }],
  config: JSON.stringify({
    version: '5.43',
    themeCollection: { baseTheme: { name: TEMA_AD, version: '5.43', type: 2 } },
    activeSectionIndex: 0,
    defaultDrillFilterOtherVisuals: true,
    objects: {
      outspacePane: [{ properties: { expanded: mnt(false), visible: mnt(false) } }]
    },
    settings: {
      useStylableVisualContainerHeader: true,
      allowChangeFilterTypes: true,
      useNewFilterPaneExperience: true,
      useCrossReportDrillthrough: false
    }
  }),
  layoutOptimization: 0,
  publicCustomVisuals: [],
  sections: [{
    id: 0,
    name: 'SayfaSatis',
    displayName: 'Satış Performansı',
    filters: '[]',
    ordinal: 0,
    visualContainers: gorseller,
    config: JSON.stringify({
      objects: {
        background:   [{ properties: { color: renk(R.sayfa), transparency: say(0) } }],
        /* Filtre boludu kapali acilsin; yonetici ekraninda yer kapliyor. */
        outspacePane: [{ properties: { expanded: mnt(false), visible: mnt(false) } }]
      }
    }),
    displayOption: 1,
    width: 1280,
    height: 720
  }]
};

/* ================= baglanti ======================================== */
const baglanti = {
  Version: 1,
  Connections: [{
    Name: 'EntityDataSource',
    ConnectionString: 'Data Source=' + SUNUCU + ';Initial Catalog=' + MODEL + ';',
    ConnectionType: 'analysisServicesDatabaseLive'
  }]
};

const icerikTipleri =
  '<?xml version="1.0" encoding="utf-8"?>\r\n' +
  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
  '<Default Extension="json" ContentType="" />' +
  '<Override PartName="/Version" ContentType="" />' +
  '<Override PartName="/Connections" ContentType="" />' +
  '<Override PartName="/Report/Layout" ContentType="" />' +
  '</Types>';

/* ================= ZIP yazici ======================================
   Bagimlilik kullanmamak icin ZIP paketi elle uretiliyor: yerel baslik,
   deflate govde, merkezi dizin, dizin sonu kaydi.                      */
const CRC = (function () {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = (c >>> 8) ^ CRC[(c ^ buf[i]) & 0xFF];
  return (c ^ -1) >>> 0;
}

function zipYaz(hedef, parcalar) {
  const yerel = [], merkez = [];
  let konum = 0;

  for (const p of parcalar) {
    const ad   = Buffer.from(p.ad, 'utf8');
    const ham  = p.veri;
    const sik  = zlib.deflateRawSync(ham, { level: 9 });
    const ozet = crc32(ham);

    const lb = Buffer.alloc(30);
    lb.writeUInt32LE(0x04034b50, 0);   // yerel baslik imzasi
    lb.writeUInt16LE(20, 4);           // gereken surum
    lb.writeUInt16LE(0, 6);            // bayraklar
    lb.writeUInt16LE(8, 8);            // yontem: deflate
    lb.writeUInt16LE(0, 10);           // saat
    lb.writeUInt16LE(0x21, 12);        // tarih: 1980-01-01
    lb.writeUInt32LE(ozet, 14);
    lb.writeUInt32LE(sik.length, 18);
    lb.writeUInt32LE(ham.length, 22);
    lb.writeUInt16LE(ad.length, 26);
    lb.writeUInt16LE(0, 28);
    yerel.push(lb, ad, sik);

    const mb = Buffer.alloc(46);
    mb.writeUInt32LE(0x02014b50, 0);   // merkezi dizin imzasi
    mb.writeUInt16LE(20, 4);           // yazan surum
    mb.writeUInt16LE(20, 6);           // gereken surum
    mb.writeUInt16LE(0, 8);
    mb.writeUInt16LE(8, 10);
    mb.writeUInt16LE(0, 12);
    mb.writeUInt16LE(0x21, 14);
    mb.writeUInt32LE(ozet, 16);
    mb.writeUInt32LE(sik.length, 20);
    mb.writeUInt32LE(ham.length, 24);
    mb.writeUInt16LE(ad.length, 28);
    mb.writeUInt16LE(0, 30);           // ek alan
    mb.writeUInt16LE(0, 32);           // yorum
    mb.writeUInt16LE(0, 34);           // disk
    mb.writeUInt16LE(0, 36);           // ic oznitelik
    mb.writeUInt32LE(0, 38);           // dis oznitelik
    mb.writeUInt32LE(konum, 42);       // yerel baslik konumu
    merkez.push(mb, ad);

    konum += lb.length + ad.length + sik.length;
  }

  const merkezBuf = Buffer.concat(merkez);
  const son = Buffer.alloc(22);
  son.writeUInt32LE(0x06054b50, 0);
  son.writeUInt16LE(0, 4);
  son.writeUInt16LE(0, 6);
  son.writeUInt16LE(parcalar.length, 8);
  son.writeUInt16LE(parcalar.length, 10);
  son.writeUInt32LE(merkezBuf.length, 12);
  son.writeUInt32LE(konum, 16);
  son.writeUInt16LE(0, 20);

  fs.writeFileSync(hedef, Buffer.concat([Buffer.concat(yerel), merkezBuf, son]));
}

/* pbix ic parcalari BOM'SUZ UTF-16LE olmali. BOM birakilirsa
   PowerBIPackager.ValidateVersion surum dizesini '?1.22' okur ve
   paketi "not a valid .pbix file version number" ile reddeder.        */
const u16 = s => Buffer.from(s, 'utf16le');

/* Parcalarin kodlamasi ayni degil:
     Version, Report/Layout -> UTF-16LE (BOM'suz)
     Connections            -> UTF-8. UTF-16 yazilirsa ayristirici
                               'localhost\TABULAR' icindeki ters boluyu
                               "Bad JSON escape sequence" diye reddeder. */
zipYaz(CIKTI, [
  { ad: 'Version',             veri: u16('1.22') },
  { ad: 'Connections',         veri: Buffer.from(JSON.stringify(baglanti), 'utf8') },
  { ad: 'Report/Layout',       veri: u16(JSON.stringify(yerlesim)) },
  { ad: 'Report/StaticResources/SharedResources/' + TEMA_YOL,
                               veri: Buffer.from(temaIcerik, 'utf8') },
  { ad: '[Content_Types].xml', veri: Buffer.from(icerikTipleri, 'utf8') }
]);

console.log('');
console.log('  Uretildi : ' + CIKTI);
console.log('  Boyut    : ' + fs.statSync(CIKTI).size + ' bayt');
console.log('  Baglanti : ' + SUNUCU + ' / ' + MODEL + ' (canli)');
console.log('  Gorsel   : ' + gorseller.length + ' adet, 1280x720 tek sayfa');
console.log('');
