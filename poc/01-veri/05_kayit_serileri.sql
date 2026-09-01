/* ===================================================================
   POC · denetim.AjanKayitSatir — seri ayrımı

   Neden: Cevap kartındaki üç grafik de tek kaynaktan okumalı. Önce
   trend ve hedef grafikleri doğrudan dbo.vw_SatisOzet'e gidiyordu;
   bu, raporun iki kaynağa bağlı olması demekti.

   Artık ajan bu serileri SSAS'tan çekip cevapla birlikte kaydediyor.
   İki kazanç:
     1. Kartın tek veri kaynağı var (denetim kaydı).
     2. Kart, cevabın verildiği ANDAKİ değerleri gösterir. Model
        sonradan değişse bile denetim artefaktı geçmişi doğru anlatır.

   Seri değerleri: 'cevap' · 'trend' · 'hedef'

   Çalıştırma:
     sqlcmd -S localhost -E -C -f 65001 -i 05_kayit_serileri.sql
   =================================================================== */

USE POC_SatisYZ;
GO

IF COL_LENGTH('denetim.AjanKayitSatir', 'Seri') IS NULL
BEGIN
    ALTER TABLE denetim.AjanKayitSatir DROP CONSTRAINT PK_AjanKayitSatir;
    ALTER TABLE denetim.AjanKayitSatir
        ADD Seri NVARCHAR(20) NOT NULL CONSTRAINT DF_AjanKayitSatir_Seri DEFAULT N'cevap';
    PRINT 'Seri kolonu eklendi';
END
ELSE
    PRINT 'Seri kolonu zaten var';
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'PK_AjanKayitSatir')
BEGIN
    ALTER TABLE denetim.AjanKayitSatir
        ADD CONSTRAINT PK_AjanKayitSatir PRIMARY KEY (KayitId, Seri, Sira);
    PRINT 'birlesik anahtar kuruldu';
END
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

    INSERT INTO denetim.AjanKayitSatir (KayitId, Seri, Sira, Etiket, Deger)
    SELECT @id, ISNULL(NULLIF(s.Seri, N''), N'cevap'), s.Sira, s.Etiket, s.Deger
    FROM OPENJSON(@json, '$.satirlar')
    WITH (
        Seri   NVARCHAR(20)   '$.seri',
        Sira   INT            '$.sira',
        Etiket NVARCHAR(200)  '$.etiket',
        Deger  DECIMAL(38,6)  '$.deger'
    ) AS s;

    SELECT @id AS KayitId;
END
GO

PRINT '--- seri destegi hazir ---';
GO
