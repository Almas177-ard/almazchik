-- Hamyon — MySQL sxemasi (ma'lumot uchun).
-- Amalda jadvallar main.py ishga tushganda avtomatik yaratiladi (app/db.py).

CREATE DATABASE IF NOT EXISTS `hamyon` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `hamyon`;

CREATE TABLE IF NOT EXISTS settings (
    skey VARCHAR(64) NOT NULL PRIMARY KEY,
    sval TEXT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    tg_id BIGINT NOT NULL PRIMARY KEY,
    username VARCHAR(64) NULL,
    first_name VARCHAR(128) NULL,
    last_name VARCHAR(128) NULL,
    lang VARCHAR(8) NOT NULL DEFAULT 'uz',
    theme VARCHAR(8) NOT NULL DEFAULT 'auto',
    role VARCHAR(16) NOT NULL DEFAULT 'user',
    blocked TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tg_id BIGINT NOT NULL,
    order_code VARCHAR(64) NOT NULL,
    external_order_id VARCHAR(128) NOT NULL,
    product_slug VARCHAR(128) NULL,
    product_name VARCHAR(255) NULL,
    delivery_type VARCHAR(32) NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(12,2) NULL,
    total_charged DECIMAL(12,2) NULL,
    status VARCHAR(32) NULL,
    delivery_json MEDIUMTEXT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uq_order_code (order_code),
    KEY idx_orders_tg (tg_id),
    KEY idx_orders_ext (external_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS texts (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tkey VARCHAR(128) NOT NULL,
    lang VARCHAR(8) NOT NULL,
    value TEXT NOT NULL,
    UNIQUE KEY uq_texts (tkey, lang)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS product_blocks (
    product_slug VARCHAR(128) NOT NULL PRIMARY KEY,
    reason VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS providers_cache (
    provider_id INT NOT NULL PRIMARY KEY,
    payload MEDIUMTEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products_cache (
    product_id INT NOT NULL PRIMARY KEY,
    slug VARCHAR(128) NOT NULL,
    payload MEDIUMTEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_products_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cache_meta (
    mkey VARCHAR(64) NOT NULL PRIMARY KEY,
    mval TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS images (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NULL,
    path VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
