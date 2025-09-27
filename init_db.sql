-- SQL Schema for the Church Inventory Flask App (MySQL)

-- Set default engine and character set for new tables
SET default_storage_engine=InnoDB;
SET NAMES 'utf8mb4';

-- Table for Locations
CREATE TABLE `location` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL UNIQUE,
    PRIMARY KEY (`id`)
);
CREATE INDEX `ix_location_name` ON `location` (`name`);

-- Table for Inventory Items
CREATE TABLE `inventory` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL,
    `description` VARCHAR(200),
    `category` VARCHAR(50),
    `condition` VARCHAR(50),
    `date_acquired` DATE,
    `price_per_item` FLOAT DEFAULT 0.00,
    PRIMARY KEY (`id`)
);
CREATE INDEX `ix_inventory_name` ON `inventory` (`name`);
CREATE INDEX `ix_inventory_category` ON `inventory` (`category`);

-- Junction Table for Item Locations and Quantities
CREATE TABLE `item_location` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `item_id` INTEGER NOT NULL,
    `location_id` INTEGER NOT NULL,
    `quantity` INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `_item_location_uc` (`item_id`, `location_id`),
    CONSTRAINT `fk_item_location_item_id` FOREIGN KEY(`item_id`) REFERENCES `inventory` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_item_location_location_id` FOREIGN KEY(`location_id`) REFERENCES `location` (`id`),
    CONSTRAINT `check_quantity_non_negative` CHECK (`quantity` >= 0)
);

-- Table for Item Movements
CREATE TABLE `movement` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `item_id` INTEGER NOT NULL,
    `quantity` INTEGER NOT NULL,
    `from_location_id` INTEGER,
    `to_location_id` INTEGER,
    `movement_date` DATETIME NOT NULL,
    `responsible_person` VARCHAR(100),
    `notes` TEXT,
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_movement_item_id` FOREIGN KEY(`item_id`) REFERENCES `inventory` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_movement_from_location_id` FOREIGN KEY(`from_location_id`) REFERENCES `location` (`id`),
    CONSTRAINT `fk_movement_to_location_id` FOREIGN KEY(`to_location_id`) REFERENCES `location` (`id`),
    CONSTRAINT `check_movement_quantity_positive` CHECK (`quantity` > 0),
    CONSTRAINT `check_location_presence` CHECK (`from_location_id` IS NOT NULL OR `to_location_id` IS NOT NULL)
);

-- Table for Disposed Items
CREATE TABLE `disposed_item` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `item_id` INTEGER NOT NULL,
    `location_id` INTEGER NOT NULL,
    `quantity` INTEGER NOT NULL,
    `reason` VARCHAR(100) NOT NULL,
    `disposed_date` DATE NOT NULL,
    `disposed_by` VARCHAR(100) NOT NULL,
    `notes` VARCHAR(200),
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_disposed_item_item_id` FOREIGN KEY(`item_id`) REFERENCES `inventory` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_disposed_item_location_id` FOREIGN KEY(`location_id`) REFERENCES `location` (`id`),
    CONSTRAINT `check_disposal_quantity_positive` CHECK (`quantity` > 0)
);

-- Table for Users
CREATE TABLE `user` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `username` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(128) NOT NULL,
    `is_admin` BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (`id`)
);
CREATE INDEX `ix_user_username` ON `user` (`username`);

-- Table for Login Attempts
CREATE TABLE `login_attempt` (
    `id` INTEGER NOT NULL AUTO_INCREMENT,
    `username` VARCHAR(100) NOT NULL,
    `attempt_time` DATETIME NOT NULL,
    `ip_address` VARCHAR(45),
    `successful` BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (`id`)
);
CREATE INDEX `ix_login_attempt_username` ON `login_attempt` (`username`);
