/* ===================================================================
   POC · Tahmin yayını

   NEDEN BU TABLO VAR: tahminin sayısı ajanın `lib/tahmin.py` modülünde
   hesaplanıyor. Dashboard'lar SSAS'tan okuyor. Aradaki boşluğu iki
   şekilde kapatabilirdim:

     (a) Tahmini DAX'ta yeniden yazmak. Reddedildi: aynı soruya ajan ve
         dashboard farklı sayı verebilirdi. Bu projenin tek kaynak
         ilkesi tam olarak bunu yasaklıyor (bkz. poc/README §mimari).
     (b) Ajanın hesabını YAYINLAMAK. Seçilen bu.

   Yani bu tablo bir hesap yeri değil, bir **yayın** yeri. İçindeki her
   satır ajanın ürettiği bir kestirimin kopyasıdır; yöntemi, R²'si ve
   üretim zamanı da birlikte durur ki rapora bakan kişi sayının nereden
   geldiğini görebilsin.

   Yazan: 04-ajan-py/araclar/tahmin_yayinla.py
   Okuyan: SSAS tablosu CiroSerisi → SatisDashboard.rdl, SatisDashboardPBI.pbix

   Çalıştırma:
     sqlcmd -S localhost -E -C -d POC_SatisYZ -f 65001 -i 06_tahmin_yayini.sql
   =================================================================== */

USE POC_SatisYZ;
GO

IF OBJECT_ID('dbo.Tahmin', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Tahmin (
        Metrik       NVARCHAR(40)  NOT NULL,
        DonemKey     INT           NOT NULL,   -- YYYYMM, gerçekleşenle aynı biçim
        DonemAd      NVARCHAR(20)  NOT NULL,
        Deger        DECIMAL(38,6) NOT NULL,
        Alt          DECIMAL(38,6) NULL,       -- %80 kestirim aralığı
        Ust          DECIMAL(38,6) NULL,
        Yontem       NVARCHAR(80)  NOT NULL,   -- "son 10 dönem ortalaması" vb.
        R2           DECIMAL(6,4)  NULL,       -- eğilim açıklayıcılığı
        Gozlem       INT           NOT NULL,   -- kaç dönem geçmişle
        UretimZamani DATETIME2(0)  NOT NULL
            CONSTRAINT DF_Tahmin_Zaman DEFAULT SYSDATETIME(),
        CONSTRAINT PK_Tahmin PRIMARY KEY (Metrik, DonemKey)
    );
    PRINT 'dbo.Tahmin olusturuldu';
END
ELSE
    PRINT 'dbo.Tahmin zaten var';
GO

/* -------------------------------------------------------------------
   Gerçekleşen + tahmin TEK tabloda. Neden birleştirilmiş bir görünüm:
   grafikte ikisi AYNI eksende durmalı. Power BI görselleri canlı
   bağlantıda hesaplanmış tablo kuramaz; RDL de iki veri kümesini tek
   grafiğe koyamaz. Birleştirmenin doğru yeri bu yüzden model.

   Sütunlar yan yana (uzun değil geniş biçim): grafik "gerçekleşen"i
   dolu, "tahmin"i boş sütun olarak ayrı serilerde çiziyor.
   ------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_CiroSerisi AS
SELECT  o.DonemKey,
        o.DonemAd,
        CAST(N'Gerçekleşen' AS NVARCHAR(12))    AS Tip,
        o.NetCiro                               AS Ciro,
        o.Hedef                                 AS Hedef,
        CAST(NULL AS DECIMAL(38,6))             AS Tahmin,
        CAST(NULL AS DECIMAL(38,6))             AS TahminAlt,
        CAST(NULL AS DECIMAL(38,6))             AS TahminUst
FROM    dbo.vw_SatisOzet AS o
UNION ALL
SELECT  t.DonemKey,
        t.DonemAd,
        CAST(N'Tahmin' AS NVARCHAR(12)),
        NULL,
        NULL,
        t.Deger,
        t.Alt,
        t.Ust
FROM    dbo.Tahmin AS t
WHERE   t.Metrik = N'Net Ciro';
GO

PRINT '--- tahmin yayini hazir ---';
GO
