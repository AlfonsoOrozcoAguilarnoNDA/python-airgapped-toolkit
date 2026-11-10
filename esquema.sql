-- =============================================================================
-- esquema.sql  -  Bases de datos de los ejercicios (recargas.py y usuarios.py)
-- Licencia MIT. Compatible con MySQL 5.7+ / 8.x y MariaDB 10.x.
--
-- Uso:
--     mysql -u USUARIO -p < esquema.sql
-- (o ábrelo y ejecútalo desde HeidiSQL, MySQL Workbench, phpMyAdmin, etc.)
--
-- Es IDEMPOTENTE: usa IF NOT EXISTS, así que se puede correr varias veces sin
-- borrar nada. NO modifica tablas que ya existan (si cambias una columna,
-- usa ALTER TABLE a mano).
--
-- Los scripts Python crean lo mismo por su cuenta al arrancar; este archivo
-- es para crearlo de forma controlada (por ejemplo, con un usuario que sí
-- tenga permiso de CREATE pero sin dar ese permiso a la aplicación).
-- =============================================================================

SET NAMES utf8mb4;


-- =============================================================================
-- 1. recargas.py  ->  base: practica_recargas
-- =============================================================================
CREATE DATABASE IF NOT EXISTS `practica_recargas`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE `practica_recargas`;

CREATE TABLE IF NOT EXISTS `celulares` (
    `id`         INT          NOT NULL AUTO_INCREMENT,
    `telefono`   VARCHAR(15)  NOT NULL,
    `comentario` VARCHAR(255) NOT NULL DEFAULT '',
    `creado`     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `telefono` (`telefono`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `recargas` (
    `id`         INT           NOT NULL AUTO_INCREMENT,
    `celular_id` INT           NOT NULL,
    `fecha`      DATE          NOT NULL,
    `importe`    DECIMAL(10,2) NOT NULL,
    `comentario` VARCHAR(255)  NOT NULL DEFAULT '',
    `creado`     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_celular_fecha` (`celular_id`, `fecha`),
    CONSTRAINT `recargas_ibfk_1` FOREIGN KEY (`celular_id`) REFERENCES `celulares` (`id`)
) ENGINE=InnoDB;


-- =============================================================================
-- 2. usuarios.py  ->  base: practica_usuarios
-- =============================================================================
CREATE DATABASE IF NOT EXISTS `practica_usuarios`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE `practica_usuarios`;

-- id             = "número de usuario".
-- usuario        = nombre de acceso; UNIQUE: la base impide repetirlo.
-- password_hash  = hash PBKDF2 de Werkzeug (nunca la contraseña en claro).
-- ultima_ip      = VARCHAR(45) alcanza para una IPv6 completa.
-- mes_cumple /
-- dia_cumple     = cumpleaños SIN año (ambos NULL o ambos con valor).
-- activo         = 'S' activo, 'N' dado de baja (baja LÓGICA: no se borra el registro).
-- foto           = JPG de perfil. MEDIUMBLOB (hasta 16 MB); el límite de 8 MB lo
--                  aplica la aplicación. Requiere max_allowed_packet >= 8 MB.
CREATE TABLE IF NOT EXISTS `usuarios` (
    `id`             INT          NOT NULL AUTO_INCREMENT,
    `usuario`        VARCHAR(30)  NOT NULL,
    `nombre_usuario` VARCHAR(100) NOT NULL,
    `password_hash`  VARCHAR(255) NOT NULL,
    `fecha_alta`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `ultima_ip`      VARCHAR(45)  NULL,
    `ultimo_login`   DATETIME     NULL,
    `unidad_negocio` VARCHAR(100) NOT NULL DEFAULT '',
    `comentario`     VARCHAR(255) NOT NULL DEFAULT '',
    `mes_cumple`     TINYINT      NULL,
    `dia_cumple`     TINYINT      NULL,
    `activo`         VARCHAR(1)   NOT NULL DEFAULT 'S',
    `foto`           MEDIUMBLOB   NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `usuario` (`usuario`)
) ENGINE=InnoDB;


-- =============================================================================
-- Usuario inicial (OPCIONAL)
-- usuarios.py ya crea el usuario "admin" por sí solo, con contraseña aleatoria,
-- la primera vez que arranca con la tabla vacía. Solo si prefieres crearlo tú:
--
--   1) Genera el hash (la contraseña NUNCA va en texto claro en esta tabla):
--        python -c "from werkzeug.security import generate_password_hash as g; print(g('TuClaveAqui1', method='pbkdf2:sha256'))"
--   2) Pega el resultado en lugar de PEGA_AQUI_EL_HASH y quita los '-- ':
--
--   INSERT INTO `usuarios` (`usuario`, `nombre_usuario`, `password_hash`, `unidad_negocio`)
--   VALUES ('admin', 'Administrador', 'PEGA_AQUI_EL_HASH', 'Sistemas');
-- =============================================================================


-- =============================================================================
-- Reinicio total (PELIGRO: borra TODOS los datos de práctica)
-- Descomenta solo si quieres empezar de cero:
--
--   DROP DATABASE IF EXISTS `practica_recargas`;
--   DROP DATABASE IF EXISTS `practica_usuarios`;
-- =============================================================================
