/* ===================================================================
   POC — Kapalı Devre Yönetici Asistanı
   01 · Kaynak veritabanı ve veri kurulumu
   Hedef: SQL Server 2025 (localhost\MSSQLSERVER)
   Çalıştırma (ÖNEMLİ — -f 65001 şart, yoksa Türkçe karakterler bozulur):
     sqlcmd -S localhost -E -C -f 65001 -i 01_veritabani_kurulum.sql
   Bu dosya BOM'suz UTF-8'dir; -f 65001 verilmezse sqlcmd baytları ANSI
   sanar ve veritabanına "Beyaz EÅŸya" gibi bozuk değerler yazar.
   =================================================================== */

IF DB_ID('POC_SatisYZ') IS NULL
    CREATE DATABASE POC_SatisYZ;
GO

USE POC_SatisYZ;
GO

/* ---------- temizlik (yeniden çalıştırılabilir olsun) ---------- */
IF OBJECT_ID('dbo.vw_SatisOzet')      IS NOT NULL DROP VIEW  dbo.vw_SatisOzet;
IF OBJECT_ID('dbo.vw_SatisDetay')     IS NOT NULL DROP VIEW  dbo.vw_SatisDetay;
IF OBJECT_ID('dbo.FactSatisDetay')    IS NOT NULL DROP TABLE dbo.FactSatisDetay;
IF OBJECT_ID('dbo.SatisOzet')         IS NOT NULL DROP TABLE dbo.SatisOzet;
IF OBJECT_ID('dbo.DimBolge')          IS NOT NULL DROP TABLE dbo.DimBolge;
IF OBJECT_ID('dbo.DimUrunGrubu')      IS NOT NULL DROP TABLE dbo.DimUrunGrubu;
IF OBJECT_ID('dbo.DimKanal')          IS NOT NULL DROP TABLE dbo.DimKanal;
IF OBJECT_ID('dbo.DimDonem')          IS NOT NULL DROP TABLE dbo.DimDonem;
GO

/* ===================================================================
   A · TABULAR MODELİN KAYNAĞI — özet, tam 10 kayıt (yıl · ay)
   =================================================================== */
CREATE TABLE dbo.SatisOzet (
    DonemKey     INT           NOT NULL PRIMARY KEY,   -- 202511 gibi
    Yil          SMALLINT      NOT NULL,
    Ay           TINYINT       NOT NULL,
    AyAd         NVARCHAR(20)  NOT NULL,
    DonemAd      NVARCHAR(20)  NOT NULL,               -- "2026-03"
    NetCiro      DECIMAL(18,2) NOT NULL,               -- TRY
    SatisAdet    INT           NOT NULL,
    Hedef        DECIMAL(18,2) NOT NULL,               -- TRY
    MusteriSayisi INT          NOT NULL
);
GO

INSERT INTO dbo.SatisOzet
    (DonemKey, Yil, Ay, AyAd,      DonemAd,   NetCiro,      SatisAdet, Hedef,        MusteriSayisi)
VALUES
    (202511, 2025, 11, N'Kasım',   N'2025-11',  84250000.00,  12480,    82000000.00,  1840),
    (202512, 2025, 12, N'Aralık',  N'2025-12', 103700000.00,  15320,    95000000.00,  2115),
    (202601, 2026,  1, N'Ocak',    N'2026-01',  71900000.00,  10640,    78000000.00,  1620),
    (202602, 2026,  2, N'Şubat',   N'2026-02',  76400000.00,  11250,    80000000.00,  1705),
    (202603, 2026,  3, N'Mart',    N'2026-03',  91850000.00,  13410,    86000000.00,  1978),
    (202604, 2026,  4, N'Nisan',   N'2026-04',  88300000.00,  12890,    88000000.00,  1902),
    (202605, 2026,  5, N'Mayıs',   N'2026-05',  95600000.00,  13980,    90000000.00,  2044),
    (202606, 2026,  6, N'Haziran', N'2026-06', 102400000.00,  14760,    94000000.00,  2168),
    (202607, 2026,  7, N'Temmuz',  N'2026-07',  98750000.00,  14230,    96000000.00,  2091),
    (202608, 2026,  8, N'Ağustos', N'2026-08',  79300000.00,  11640,    98000000.00,  1733);
GO

/* ===================================================================
   B · RS DASHBOARD'UN KAYNAĞI — boyutlar + detay olgu tablosu
   =================================================================== */
CREATE TABLE dbo.DimBolge (
    BolgeKey INT NOT NULL PRIMARY KEY,
    BolgeAd  NVARCHAR(30) NOT NULL,
    BolgeKod NVARCHAR(5)  NOT NULL
);
INSERT INTO dbo.DimBolge VALUES
    (1, N'Marmara',        N'MAR'),
    (2, N'İç Anadolu',     N'ICA'),
    (3, N'Ege',            N'EGE'),
    (4, N'Akdeniz',        N'AKD'),
    (5, N'Karadeniz',      N'KAR');
GO

CREATE TABLE dbo.DimUrunGrubu (
    UrunGrubuKey INT NOT NULL PRIMARY KEY,
    UrunGrubuAd  NVARCHAR(40) NOT NULL,
    Kategori     NVARCHAR(20) NOT NULL
);
INSERT INTO dbo.DimUrunGrubu VALUES
    (1, N'Beyaz Eşya',        N'Dayanıklı'),
    (2, N'Küçük Ev Aletleri', N'Dayanıklı'),
    (3, N'Mobilya',           N'Ev'),
    (4, N'Aydınlatma',        N'Ev');
GO

CREATE TABLE dbo.DimKanal (
    KanalKey INT NOT NULL PRIMARY KEY,
    KanalAd  NVARCHAR(30) NOT NULL
);
INSERT INTO dbo.DimKanal VALUES
    (1, N'Kurumsal Satış'),
    (2, N'Perakende'),
    (3, N'E-Ticaret');
GO

CREATE TABLE dbo.DimDonem (
    DonemKey INT NOT NULL PRIMARY KEY,
    Yil      SMALLINT     NOT NULL,
    Ay       TINYINT      NOT NULL,
    AyAd     NVARCHAR(20) NOT NULL,
    DonemAd  NVARCHAR(20) NOT NULL,
    DonemBaslangic DATE   NOT NULL
);
INSERT INTO dbo.DimDonem
SELECT DonemKey, Yil, Ay, AyAd, DonemAd,
       DATEFROMPARTS(Yil, Ay, 1)
FROM dbo.SatisOzet;
GO

/* Detay olgu: dönem × bölge × ürün grubu × kanal
   Özet tablonun aylık net cirosu, deterministik ağırlıklarla dağıtılır;
   böylece detay toplamı özet ile birebir tutar (doğruluk testi için şart). */
CREATE TABLE dbo.FactSatisDetay (
    SatisId      INT IDENTITY(1,1) PRIMARY KEY,
    DonemKey     INT NOT NULL REFERENCES dbo.DimDonem(DonemKey),
    BolgeKey     INT NOT NULL REFERENCES dbo.DimBolge(BolgeKey),
    UrunGrubuKey INT NOT NULL REFERENCES dbo.DimUrunGrubu(UrunGrubuKey),
    KanalKey     INT NOT NULL REFERENCES dbo.DimKanal(KanalKey),
    NetCiro      DECIMAL(18,2) NOT NULL,
    SatisAdet    INT NOT NULL,
    Hedef        DECIMAL(18,2) NOT NULL
);
GO

/* Ciro ve hedef AYRI ağırlıklarla dağıtılır. Aynı ağırlık kullanılırsa
   hedef gerçekleşme oranı her bölgede matematiksel olarak aynı çıkar ve
   dashboard'daki "gerçekleşme" kolonu hiçbir şey anlatmaz. Bölgeye özel
   performans katsayısı bunu ayrıştırır; iki dağıtımın toplamı yine
   özet tablodaki değere eşittir. */
;WITH agirlik AS (
    SELECT b.BolgeKey, u.UrunGrubuKey, k.KanalKey,
           /* sabit, tekrarlanabilir ağırlık — rastgelelik yok */
           w = CAST(
                 (6 - b.BolgeKey) * 1.0
               * (5 - u.UrunGrubuKey) * 1.0
               * CASE k.KanalKey WHEN 1 THEN 3.0 WHEN 2 THEN 2.0 ELSE 1.2 END
               AS DECIMAL(18,6)),
           /* hedef ağırlığı: bölgeye göre sapan performans profili
              (<1 = bölge hedefi aşıyor, >1 = hedefin altında kalıyor) */
           wh = CAST(
                 (6 - b.BolgeKey) * 1.0
               * (5 - u.UrunGrubuKey) * 1.0
               * CASE k.KanalKey WHEN 1 THEN 3.0 WHEN 2 THEN 2.0 ELSE 1.2 END
               * CASE b.BolgeKey
                     WHEN 1 THEN 0.88   -- Marmara    : hedefin üzerinde
                     WHEN 2 THEN 1.06   -- İç Anadolu : hafif altında
                     WHEN 3 THEN 0.97   -- Ege        : hedefe yakın
                     WHEN 4 THEN 1.18   -- Akdeniz    : belirgin altında
                     ELSE 0.92          -- Karadeniz  : üzerinde
                 END
               AS DECIMAL(18,6))
    FROM dbo.DimBolge b
    CROSS JOIN dbo.DimUrunGrubu u
    CROSS JOIN dbo.DimKanal k
),
toplam AS (SELECT SUM(w) AS wt, SUM(wh) AS wht FROM agirlik)
INSERT INTO dbo.FactSatisDetay (DonemKey, BolgeKey, UrunGrubuKey, KanalKey, NetCiro, SatisAdet, Hedef)
SELECT o.DonemKey, a.BolgeKey, a.UrunGrubuKey, a.KanalKey,
       CAST(o.NetCiro   * a.w  / t.wt  AS DECIMAL(18,2)),
       CAST(ROUND(o.SatisAdet * a.w / t.wt, 0) AS INT),
       CAST(o.Hedef     * a.wh / t.wht AS DECIMAL(18,2))
FROM dbo.SatisOzet o
CROSS JOIN agirlik a
CROSS JOIN toplam t;
GO

/* Yuvarlama artığını kapat: dönem başına kalan farkı ilk satıra ekle.
   Ölçüler artık semantik modelde detay olgudan hesaplanıyor; detay
   toplamı özetten 5 kuruş saparsa bu fark dashboard'da görünür hâle
   gelir. Dağıtım deterministik olduğu için düzeltme de deterministiktir. */
;WITH fark AS (
    SELECT f.DonemKey,
           o.NetCiro   - SUM(f.NetCiro)   AS dCiro,
           o.Hedef     - SUM(f.Hedef)     AS dHedef,
           o.SatisAdet - SUM(f.SatisAdet) AS dAdet
    FROM dbo.FactSatisDetay f
    JOIN dbo.SatisOzet o ON o.DonemKey = f.DonemKey
    GROUP BY f.DonemKey, o.NetCiro, o.Hedef, o.SatisAdet
),
ilkSatir AS (
    SELECT DonemKey, MIN(SatisId) AS SatisId
    FROM dbo.FactSatisDetay GROUP BY DonemKey
)
UPDATE f
   SET f.NetCiro   = f.NetCiro   + fark.dCiro,
       f.Hedef     = f.Hedef     + fark.dHedef,
       f.SatisAdet = f.SatisAdet + fark.dAdet
FROM dbo.FactSatisDetay f
JOIN ilkSatir ON ilkSatir.SatisId = f.SatisId
JOIN fark     ON fark.DonemKey    = f.DonemKey;
GO

/* ---------- görünümler ---------- */
CREATE VIEW dbo.vw_SatisOzet AS
SELECT DonemKey, Yil, Ay, AyAd, DonemAd, NetCiro, SatisAdet, Hedef, MusteriSayisi
FROM dbo.SatisOzet;
GO

CREATE VIEW dbo.vw_SatisDetay AS
SELECT f.SatisId,
       d.DonemKey, d.Yil, d.Ay, d.AyAd, d.DonemAd, d.DonemBaslangic,
       b.BolgeKey, b.BolgeAd, b.BolgeKod,
       u.UrunGrubuKey, u.UrunGrubuAd, u.Kategori,
       k.KanalKey, k.KanalAd,
       f.NetCiro, f.SatisAdet, f.Hedef
FROM dbo.FactSatisDetay f
JOIN dbo.DimDonem     d ON d.DonemKey     = f.DonemKey
JOIN dbo.DimBolge     b ON b.BolgeKey     = f.BolgeKey
JOIN dbo.DimUrunGrubu u ON u.UrunGrubuKey = f.UrunGrubuKey
JOIN dbo.DimKanal     k ON k.KanalKey     = f.KanalKey;
GO

/* ---------- doğrulama ---------- */
PRINT '--- SatisOzet satir sayisi (10 olmali) ---';
SELECT COUNT(*) AS ozet_satir FROM dbo.SatisOzet;

PRINT '--- FactSatisDetay satir sayisi (10*5*4*3=600) ---';
SELECT COUNT(*) AS detay_satir FROM dbo.FactSatisDetay;

PRINT '--- Ozet ile detay tutuyor mu (fark ~0 olmali) ---';
SELECT o.DonemAd,
       o.NetCiro                      AS ozet_ciro,
       SUM(f.NetCiro)                 AS detay_ciro,
       o.NetCiro - SUM(f.NetCiro)     AS fark
FROM dbo.SatisOzet o
JOIN dbo.FactSatisDetay f ON f.DonemKey = o.DonemKey
GROUP BY o.DonemAd, o.NetCiro
ORDER BY o.DonemAd;
GO
