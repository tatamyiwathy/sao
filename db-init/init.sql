--  CREATE DATABASE IF NOT EXISTS test_sao_db CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE DATABASE IF NOT EXISTS sao_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'saoadmin'@'%' IDENTIFIED BY 'saoadmin';
GRANT ALL PRIVILEGES ON sao_db.* TO 'saoadmin'@'%';
GRANT ALL PRIVILEGES ON sao_db.* TO 'saoadmin'@'localhost';
FLUSH PRIVILEGES;
-- 作成されたユーザーを確認
SELECT User, Host FROM mysql.user WHERE User='saoadmin';