/* ===================================================================
   POC · SSAS servis hesabına okuma yetkisi

   Neden gerekli: Tabular model verisini içe alırken (refresh) sorgu
   SİZİN kimliğinizle değil, SSAS servis hesabıyla çalışır. O hesabın
   POC_SatisYZ üzerinde okuma yetkisi yoksa refresh şu hatayla düşer:
       "Login failed for user 'NT SERVICE\MSOLAP$TABULAR'"

   SSAS KURULDUKTAN SONRA çalıştırılmalı — servis hesabı var olmadan
   CREATE LOGIN başarısız olur.

   Çalıştırma:
     sqlcmd -S localhost -E -C -f 65001 -i 02_ssas_servis_yetkisi.sql

   Instance adı TABULAR değilse aşağıdaki @hesap değişkenini değiştirin.
   Varsayılan instance ise hesap adı: NT SERVICE\MSSQLServerOLAPService
   =================================================================== */

DECLARE @hesap SYSNAME = N'NT SERVICE\MSOLAP$TABULAR';
DECLARE @sql   NVARCHAR(MAX);

/* 1 · sunucu düzeyinde login */
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @hesap)
BEGIN
    SET @sql = N'CREATE LOGIN ' + QUOTENAME(@hesap) + N' FROM WINDOWS;';
    EXEC sp_executesql @sql;
    PRINT 'login olusturuldu: ' + @hesap;
END
ELSE
    PRINT 'login zaten var: ' + @hesap;
GO

USE POC_SatisYZ;
GO

DECLARE @hesap SYSNAME = N'NT SERVICE\MSOLAP$TABULAR';
DECLARE @sql   NVARCHAR(MAX);

/* 2 · veritabanı kullanıcısı */
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @hesap)
BEGIN
    SET @sql = N'CREATE USER ' + QUOTENAME(@hesap) + N' FOR LOGIN ' + QUOTENAME(@hesap) + N';';
    EXEC sp_executesql @sql;
    PRINT 'kullanici olusturuldu';
END

/* 3 · yalnızca okuma — yazma yetkisi bilinçli olarak verilmiyor */
SET @sql = N'ALTER ROLE db_datareader ADD MEMBER ' + QUOTENAME(@hesap) + N';';
EXEC sp_executesql @sql;
PRINT 'db_datareader verildi';
GO

/* 4 · doğrulama */
SELECT dp.name        AS db_kullanicisi,
       r.name         AS rol,
       sp.type_desc   AS tur
FROM sys.database_principals dp
JOIN sys.database_role_members drm ON drm.member_principal_id = dp.principal_id
JOIN sys.database_principals r     ON r.principal_id = drm.role_principal_id
LEFT JOIN sys.server_principals sp ON sp.name = dp.name
WHERE dp.name LIKE N'NT SERVICE\MSOLAP%' OR dp.name LIKE N'NT SERVICE\MSSQLServerOLAP%';
GO
