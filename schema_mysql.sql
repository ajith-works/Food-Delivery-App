-- Reference MySQL schema, equivalent to the SQLAlchemy models in models.py.
-- The app itself creates tables automatically via SQLAlchemy (db.create_all()),
-- so running this file by hand is optional -- it's provided for documentation
-- and for the "Flask + MySQL" internship requirement.

CREATE DATABASE IF NOT EXISTS food_delivery CHARACTER SET utf8mb4;
USE food_delivery;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'customer',
    phone VARCHAR(20),
    address VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE restaurants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    cuisine VARCHAR(120),
    address VARCHAR(255),
    rating FLOAT DEFAULT 4.0,
    image_url VARCHAR(300),
    delivery_time_min INT DEFAULT 30,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    description VARCHAR(300),
    price FLOAT NOT NULL,
    category VARCHAR(80) DEFAULT 'Main Course',
    image_url VARCHAR(300),
    is_veg BOOLEAN DEFAULT TRUE,
    available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    total_amount FLOAT NOT NULL,
    delivery_address VARCHAR(255),
    payment_method VARCHAR(50) DEFAULT 'Card',
    payment_status VARCHAR(20) DEFAULT 'Pending',
    status VARCHAR(40) DEFAULT 'Order Placed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
);

CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    name_snapshot VARCHAR(150),
    price_snapshot FLOAT,
    quantity INT DEFAULT 1,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    agent_name VARCHAR(120),
    agent_phone VARCHAR(20),
    vehicle VARCHAR(50) DEFAULT 'Bike',
    estimated_minutes INT DEFAULT 30,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
