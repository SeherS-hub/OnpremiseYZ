/* ===================================================================
   POC · Denetim kaydı — soru ve cevapların kalıcı deposu
   Spesifikasyon §9.4'ün çalışan karşılığı.

   İki tablo:
     denetim.AjanKayit       her soru bir satır (cevap metni dahil)
     denetim.AjanKayitSatir  cevabın sonuç satırları (grafik için)

   NOT — yazma yetkisi: Asistan iş verisine ASLA yazmaz; denetim kaydı
   bunun istisnasıdır ve bilinçlidir. Üretimde bu şema ayrı bir
   veritabanında, ayrı ve yalnızca-ekleme yetkili bir kimlikle tutulur
   (§12.1). PoC'de aynı veritabanında ayrı şemada duruyor.

   Çalıştırma:
     sqlcmd -S localhost -E -C -f 65001 -i 03_denetim_kaydi.sql
   =================================================================== */

USE POC_SatisYZ;
GO

IF SCHEMA_ID('denetim') IS NULL EXEC('CREATE SCHEMA denetim');
GO

IF OBJECT_ID('denetim.usp_AjanKayitEkle') IS NOT NULL DROP PROCEDURE denetim.usp_AjanKayitEkle;
IF OBJECT_ID('denetim.vw_SonKayitlar')    IS NOT NULL DROP VIEW      denetim.vw_SonKayitlar;
IF OBJECT_ID('denetim.AjanKayitSatir')    IS NOT NULL DROP TABLE     denetim.AjanKayitSatir;
IF OBJECT_ID('denetim.AjanKayit')         IS NOT NULL DROP TABLE     denetim.AjanKayit;
GO

CREATE TABLE denetim.AjanKayit (
    KayitId       INT IDENTITY(1,1) PRIMARY KEY,
    Zaman         DATETIME2(0)   NOT NULL CONSTRAINT DF_AjanKayit_Zaman DEFAULT SYSDATETIME(),
    Kullanici     NVARCHAR(128)  NOT NULL,
    Soru          NVARCHAR(500)  NOT NULL,
    Durum         NVARCHAR(20)   NOT NULL,   -- ok · netlestir · kapsam_disi · yetkisiz · hata
    Cevap         NVARCHAR(MAX)  NULL,
    VurguDeger    NVARCHAR(100)  NULL,       -- "79,3 mn TL"
    VurguEtiket   NVARCHAR(200)  NULL,       -- "2026-08"
    Metrikler     NVARCHAR(400)  NULL,
    MetrikTanim   NVARCHAR(600)  NULL,
    MetrikSahip   NVARCHAR(200)  NULL,
    Donem         NVARCHAR(120)  NULL,
    Kaynak        NVARCHAR(120)  NULL,
    Motor         NVARCHAR(120)  NULL,
    SorguDili     NVARCHAR(10)   NULL,       -- DAX · T-SQL
    Sorgu         NVARCHAR(MAX)  NULL,
    Spesifikasyon NVARCHAR(MAX)  NULL,       -- JSON
    Guven         DECIMAL(5,2)   NULL,       -- 0..1
    SatirSayisi   INT            NULL,
    SureMs        INT            NULL,
    SorguSureMs   INT            NULL,
    Belirsizlik   NVARCHAR(1000) NULL
);
GO

CREATE INDEX IX_AjanKayit_Zaman ON denetim.AjanKayit (Zaman DESC);
GO

CREATE TABLE denetim.AjanKayitSatir (
    KayitId  INT           NOT NULL REFERENCES denetim.AjanKayit(KayitId),
    Sira     INT           NOT NULL,
    Etiket   NVARCHAR(200) NOT NULL,
    Deger    DECIMAL(38,6) NULL,
    CONSTRAINT PK_AjanKayitSatir PRIMARY KEY (KayitId, Sira)
);
GO

/* -------------------------------------------------------------------
   Tek giriş noktası: ajan JSON gönderir, prosedür ayrıştırır.
   Metin birleştirme yok → kaçış sorunu ve enjeksiyon yüzeyi yok.
   ------------------------------------------------------------------- */
CREATE PROCEDURE denetim.usp_AjanKayitEkle
    @json NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @yeni TABLE (KayitId INT);

    INSERT INTO denetim.AjanKayit
        (Kullanici, Soru, Durum, Cevap, VurguDeger, VurguEtiket, Metrikler,
         MetrikTanim, MetrikSahip, Donem, Kaynak, Motor, SorguDili, Sorgu,
         Spesifikasyon, Guven, SatirSayisi, SureMs, SorguSureMs, Belirsizlik)
    OUTPUT inserted.KayitId INTO @yeni
    SELECT Kullanici, Soru, Durum, Cevap, VurguDeger, VurguEtiket, Metrikler,
           MetrikTanim, MetrikSahip, Donem, Kaynak, Motor, SorguDili, Sorgu,
           Spesifikasyon, Guven, SatirSayisi, SureMs, SorguSureMs, Belirsizlik
    FROM OPENJSON(@json)
    WITH (
        Kullanici     NVARCHAR(128)  '$.kullanici',
        Soru          NVARCHAR(500)  '$.soru',
        Durum         NVARCHAR(20)   '$.durum',
        Cevap         NVARCHAR(MAX)  '$.cevap',
        VurguDeger    NVARCHAR(100)  '$.vurguDeger',
        VurguEtiket   NVARCHAR(200)  '$.vurguEtiket',
        Metrikler     NVARCHAR(400)  '$.metrikler',
        MetrikTanim   NVARCHAR(600)  '$.metrikTanim',
        MetrikSahip   NVARCHAR(200)  '$.metrikSahip',
        Donem         NVARCHAR(120)  '$.donem',
        Kaynak        NVARCHAR(120)  '$.kaynak',
        Motor         NVARCHAR(120)  '$.motor',
        SorguDili     NVARCHAR(10)   '$.sorguDili',
        Sorgu         NVARCHAR(MAX)  '$.sorgu',
        Spesifikasyon NVARCHAR(MAX)  '$.spesifikasyon' AS JSON,
        Guven         DECIMAL(5,2)   '$.guven',
        SatirSayisi   INT            '$.satirSayisi',
        SureMs        INT            '$.sureMs',
        SorguSureMs   INT            '$.sorguSureMs',
        Belirsizlik   NVARCHAR(1000) '$.belirsizlik'
    );

    DECLARE @id INT = (SELECT TOP 1 KayitId FROM @yeni);

    INSERT INTO denetim.AjanKayitSatir (KayitId, Sira, Etiket, Deger)
    SELECT @id, s.Sira, s.Etiket, s.Deger
    FROM OPENJSON(@json, '$.satirlar')
    WITH (
        Sira   INT            '$.sira',
        Etiket NVARCHAR(200)  '$.etiket',
        Deger  DECIMAL(38,6)  '$.deger'
    ) AS s;

    SELECT @id AS KayitId;
END
GO

/* Rapor parametresi için: son 50 soru */
CREATE VIEW denetim.vw_SonKayitlar AS
SELECT TOP (50)
       KayitId,
       CONVERT(NVARCHAR(16), Zaman, 120) + N'  ·  '
         + CASE WHEN LEN(Soru) > 58 THEN LEFT(Soru, 55) + N'…' ELSE Soru END AS Etiket,
       Zaman, Soru, Durum
FROM denetim.AjanKayit
ORDER BY KayitId DESC;
GO

PRINT '--- denetim semasi hazir ---';
SELECT COUNT(*) AS kayit FROM denetim.AjanKayit;
GO
