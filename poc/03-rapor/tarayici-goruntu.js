/* ===================================================================
   Bir sayfayi headless tarayicida cizdirip PNG ve konsol kaydini alir.

   NEDEN VAR: .pbix raporu sunucu tarafinda cizdirilemiyor — PBIRS REST
   v2.0, PowerBIReport icin Render islemi sunmuyor. Dogru cizdigini
   gormenin tek yolu gercek bir tarayicida acmak. (RDL icin gerek yok;
   onu sunucu PNG olarak veriyor.)

   NEDEN NODE: ayni is once PowerShell'in ClientWebSocket'i ile yazildi
   ve iki yerde kirildi — (1) about:blank'ten Page.navigate ile gezinmek
   hedefi degistirip soketi sessizce koparıyor, (2) ekran goruntusunun
   base64'u onlarca WebSocket cercevesine bolunuyor ve elle birlestirmek
   guvenilir olmadi. Node'un yerlesik WebSocket'i (18+) parcalari kendi
   birlestiriyor. Node bu depoda zaten .pbix uretmek icin var.

   --screenshot anahtari yeni headless modunda cikti uretmiyor; bu yuzden
   CDP'nin Page.captureScreenshot cagrisi kullaniliyor.

   Kullanim:
     node tarayici-goruntu.js <url> [cikti.png] [bekleSaniye]
     node tarayici-goruntu.js http://localhost/Reports/powerbi/SatisDashboardPBI \
          onizleme/SatisDashboardPBI.png 25
   =================================================================== */
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const URL_ADRES = process.argv[2];
const CIKTI = process.argv[3] || 'ekran.png';
const BEKLE = Number(process.argv[4] || 25) * 1000;
const PORT = Number(process.argv[5] || 9222);
const OLCU = { genislik: 1400, yukseklik: 1000 };

if (!URL_ADRES) {
  console.error('kullanim: node tarayici-goruntu.js <url> [cikti.png] [bekleSaniye]');
  process.exit(2);
}

const TARAYICILAR = [
  path.join(process.env['ProgramFiles'] || '', 'Microsoft/Edge/Application/msedge.exe'),
  path.join(process.env['ProgramFiles(x86)'] || '', 'Microsoft/Edge/Application/msedge.exe'),
  path.join(process.env['ProgramFiles'] || '', 'Google/Chrome/Application/chrome.exe'),
  path.join(process.env['ProgramFiles(x86)'] || '', 'Google/Chrome/Application/chrome.exe'),
];

const uyu = ms => new Promise(r => setTimeout(r, ms));

async function hedefBul() {
  for (let i = 0; i < 60; i++) {
    try {
      const y = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const liste = await y.json();
      const s = liste.find(t => t.type === 'page' && !/^(about|edge|chrome):/.test(t.url));
      if (s) return s;
    } catch { /* tarayici henuz ayakta degil */ }
    await uyu(500);
  }
  throw new Error(`CDP hedefi bulunamadi (port ${PORT})`);
}

function cdp(ws) {
  let sonId = 0;
  const bekleyen = new Map();
  const olaylar = [];
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && bekleyen.has(m.id)) {
      const { coz, sap } = bekleyen.get(m.id);
      bekleyen.delete(m.id);
      m.error ? sap(new Error(m.error.message)) : coz(m.result);
    } else if (m.method) {
      olaylar.push(m);
    }
  });
  return {
    olaylar,
    cagir(yontem, parametre) {
      const id = ++sonId;
      return new Promise((coz, sap) => {
        bekleyen.set(id, { coz, sap });
        ws.send(JSON.stringify({ id, method: yontem, params: parametre || {} }));
        setTimeout(() => {
          if (bekleyen.has(id)) { bekleyen.delete(id); sap(new Error(yontem + ': zaman asimi')); }
        }, 120000);
      });
    },
  };
}

(async () => {
  const tarayici = TARAYICILAR.find(p => p && fs.existsSync(p));
  if (!tarayici) throw new Error('Edge veya Chrome bulunamadi.');

  const profil = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
  const surec = spawn(tarayici, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profil}`,
    `--window-size=${OLCU.genislik},${OLCU.yukseklik}`,
    // PBIRS Negotiate istiyor; headless varsayilan olarak vermiyor.
    '--auth-server-allowlist=*localhost',
    '--auth-negotiate-delegate-allowlist=*localhost',
    URL_ADRES,
  ], { stdio: 'ignore' });

  try {
    const hedef = await hedefBul();
    const ws = new WebSocket(hedef.webSocketDebuggerUrl);
    await new Promise((coz, sap) => {
      ws.addEventListener('open', coz, { once: true });
      ws.addEventListener('error', () => sap(new Error('WebSocket acilamadi')), { once: true });
    });
    const c = cdp(ws);

    await c.cagir('Runtime.enable');
    await c.cagir('Log.enable');

    // Duz bekleme: Power BI yuklemeyi loadEventFired'dan SONRA surduruyor,
    // olay bize bir sey soylemiyor.
    console.log(`  yukleniyor : ${URL_ADRES}`);
    await uyu(BEKLE);

    // Sayfanin kendi metni: gorsel sayisi ve varsa hata kutulari.
    const d = await c.cagir('Runtime.evaluate', {
      returnByValue: true,
      // Power BI tuvali IFRAME icinde ('/powerbi/?id=...'). Ust belgeye
      // bakmak yanlis olcum verir: gorsel sayisi hep 0 cikar ve calisan
      // rapor bozuk sanilir. Ayni kokenli iframe'ler de taraniyor.
      expression: `(() => {
        const belgeler = [document];
        for (const f of document.querySelectorAll('iframe')) {
          try { if (f.contentDocument) belgeler.push(f.contentDocument); } catch { /* capraz koken */ }
        }
        let gorsel = 0; const hata = []; let metin = '';
        for (const b of belgeler) {
          gorsel += b.querySelectorAll('visual-container, .visualContainer').length;
          for (const e of b.querySelectorAll('.errorContainer, .visual-error, .error-message, .pbi-error')) {
            const t = (e.innerText || '').trim(); if (t) hata.push(t);
          }
          if (b.body) metin += ' ' + (b.body.innerText || '');
        }
        return { gorsel, hata: hata.slice(0, 5),
                 metin: metin.replace(/\\s+/g, ' ').trim().slice(0, 700) };
      })()`,
    });
    const o = d.result.value || {};
    console.log(`  gorsel     : ${o.gorsel}`);
    for (const h of o.hata || []) console.log(`  GORSEL HATA: ${h}`);
    if (o.metin) console.log(`  metin      : ${o.metin}`);

    const g = await c.cagir('Page.captureScreenshot', { format: 'png' });
    const tam = path.isAbsolute(CIKTI) ? CIKTI : path.join(process.cwd(), CIKTI);
    fs.mkdirSync(path.dirname(tam), { recursive: true });
    fs.writeFileSync(tam, Buffer.from(g.data, 'base64'));
    console.log(`  PNG        : ${tam} (${fs.statSync(tam).size} bayt)`);

    const hatalar = c.olaylar.filter(m => {
      const s = JSON.stringify(m);
      return /"(error|exception)"/i.test(s) || /Error:/.test(s);
    });
    if (!hatalar.length) {
      console.log('  KONSOL     : hata yok');
    } else {
      console.log(`  KONSOL     : ${hatalar.length} hata`);
      for (const h of hatalar.slice(0, 8)) {
        const p = h.params || {};
        const t = (p.entry && p.entry.text) ||
                  (p.exceptionDetails && p.exceptionDetails.text) ||
                  (p.args && p.args.map(a => a.description || a.value).join(' ')) ||
                  JSON.stringify(p);
        console.log('    ' + String(t).replace(/\s+/g, ' ').slice(0, 320));
      }
    }
    ws.close();
  } finally {
    surec.kill();
    await uyu(400);
    // Tarayici dosyalari birakmakta gecikebilir; temizlik hatasi isin
    // sonucunu bozmasin (EPERM ile cikip PNG'yi gormemek anlamsiz).
    try { fs.rmSync(profil, { recursive: true, force: true }); } catch { /* sonra silinir */ }
  }
})().catch(e => { console.error('  HATA: ' + e.message); process.exit(1); });
