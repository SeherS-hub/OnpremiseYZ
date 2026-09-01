/* ===================================================================
   POC · denetim.AjanKayit — Aciklama kolonu

   Neden ayrı bir kolon: cevap kartında soru gösterilmiyor, dolayısıyla
   cevabın kendi başına anlaşılır olması gerekiyor. Ayrıca rakam kartta
   yalnızca bir kez (dev punto) görünmeli. `Cevap` sayıyı içerir,
   `Aciklama` içermez — kart Aciklama'yı kullanır.

   Çalıştırma:
     sqlcmd -S localhost -E -C -f 65001 -i 04_aciklama_kolonu.sql
   =================================================================== */

USE POC_SatisYZ;
GO

IF COL_LENGTH('denetim.AjanKayit', 'Aciklama') IS NULL
BEGIN
    ALTER TABLE denetim.AjanKayit ADD Aciklama NVARCHAR(1000) NULL;
    PRINT 'Aciklama kolonu eklendi';
END
ELSE
    PRINT 'Aciklama kolonu zaten var';
GO

CREATE OR ALTER PROCEDURE denetim.usp_AjanKayitEkle
    @json NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @yeni TABLE (KayitId INT);

    INSERT INTO denetim.AjanKayit
        (Kullanici, Soru, Durum, Cevap, Aciklama, VurguDeger, VurguEtiket, Metrikler,
         MetrikTanim, MetrikSahip, Donem, Kaynak, Motor, SorguDili, Sorgu,
         Spesifikasyon, Guven, SatirSayisi, SureMs, SorguSureMs, Belirsizlik)
    OUTPUT inserted.KayitId INTO @yeni
    SELECT Kullanici, Soru, Durum, Cevap, Aciklama, VurguDeger, VurguEtiket, Metrikler,
           MetrikTanim, MetrikSahip, Donem, Kaynak, Motor, SorguDili, Sorgu,
           Spesifikasyon, Guven, SatirSayisi, SureMs, SorguSureMs, Belirsizlik
    FROM OPENJSON(@json)
    WITH (
        Kullanici     NVARCHAR(128)  '$.kullanici',
        Soru          NVARCHAR(500)  '$.soru',
        Durum         NVARCHAR(20)   '$.durum',
        Cevap         NVARCHAR(MAX)  '$.cevap',
        Aciklama      NVARCHAR(1000) '$.aciklama',
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

PRINT '--- prosedur guncellendi ---';
GO
