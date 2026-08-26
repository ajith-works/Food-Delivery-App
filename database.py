"""
Database layer for FoodExpress.

Uses Python's built-in sqlite3 module so the project runs with zero extra
dependencies. The schema below is intentionally identical to schema_mysql.sql
-- switching to MySQL later just means swapping this module's connection
logic for PyMySQL and keeping the same SQL (minor syntax tweaks such as
AUTOINCREMENT -> AUTO_INCREMENT).
"""

import os
import random
import sqlite3
from datetime import datetime

from flask import g
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "food_delivery.db"))

ORDER_STAGES = [
    "Order Placed",
    "Confirmed by Restaurant",
    "Preparing Food",
    "Out for Delivery",
    "Delivered",
]
# Seconds spent in each stage before advancing (demo speed, 4 gaps for 5 stages)
STAGE_DURATIONS = [15, 20, 30, 40]


# ---------------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'customer',
    phone TEXT,
    address TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cuisine TEXT,
    address TEXT,
    rating REAL DEFAULT 4.0,
    image_url TEXT,
    delivery_time_min INTEGER DEFAULT 30,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    category TEXT DEFAULT 'Main Course',
    image_url TEXT,
    is_veg INTEGER DEFAULT 1,
    available INTEGER DEFAULT 1,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    restaurant_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    delivery_address TEXT,
    payment_method TEXT DEFAULT 'Card',
    payment_status TEXT DEFAULT 'Pending',
    status TEXT DEFAULT 'Order Placed',
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    name_snapshot TEXT,
    price_snapshot REAL,
    quantity INTEGER DEFAULT 1,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    agent_name TEXT,
    agent_phone TEXT,
    vehicle TEXT DEFAULT 'Bike',
    estimated_minutes INTEGER DEFAULT 30,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
"""


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
        seed_data(db)
        close_db()


# ---------------------------------------------------------------------------
# Order status helpers (time-based simulation of a real-time tracker)
# ---------------------------------------------------------------------------
def compute_live_status(order_row):
    if order_row["payment_status"] != "Paid":
        return ORDER_STAGES[0]

    created = datetime.fromisoformat(order_row["created_at"])
    elapsed = (datetime.utcnow() - created).total_seconds()

    cumulative = 0
    stage_index = 0
    for i, duration in enumerate(STAGE_DURATIONS):
        cumulative += duration
        if elapsed >= cumulative:
            stage_index = i + 1
        else:
            break
    return ORDER_STAGES[min(stage_index, len(ORDER_STAGES) - 1)]


def progress_percent(status):
    idx = ORDER_STAGES.index(status)
    return int((idx / (len(ORDER_STAGES) - 1)) * 100)


# ---------------------------------------------------------------------------
# Seed demo data
# ---------------------------------------------------------------------------
def seed_data(db):
    existing = db.execute("SELECT id FROM restaurants LIMIT 1").fetchone()
    if existing:
        return

    now = datetime.utcnow().isoformat()

    db.execute(
        "INSERT INTO users (name, email, password_hash, role, phone, address, created_at) VALUES (?,?,?,?,?,?,?)",
        ("Admin", "admin@fooddelivery.com", generate_password_hash("admin123"), "admin", "", "", now),
    )
    db.execute(
        "INSERT INTO users (name, email, password_hash, role, phone, address, created_at) VALUES (?,?,?,?,?,?,?)",
        ("Demo Customer", "customer@example.com", generate_password_hash("password123"),
         "customer", "9876543210", "221B Baker Street, Hyderabad", now),
    )

    restaurants_data = [
        {
            "name": "Spice Route", "cuisine": "Indian", "address": "MG Road, Hyderabad",
            "rating": 4.5, "delivery_time_min": 30,
            "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=600",
            "menu": [
                ("Butter Chicken", "Creamy tomato curry with tender chicken", 320, "Main Course", 0),
                ("Paneer Tikka", "Grilled cottage cheese with spices", 260, "Starters", 1),
                ("Garlic Naan", "Soft flatbread with garlic butter", 60, "Breads", 1),
                ("Veg Biryani", "Fragrant basmati rice with vegetables", 220, "Rice", 1),
                ("Gulab Jamun", "Sweet milk dumplings in syrup", 90, "Desserts", 1),
            ],
        },
        {
            "name": "Pizza Planet", "cuisine": "Italian", "address": "Jubilee Hills, Hyderabad",
            "rating": 4.3, "delivery_time_min": 25,
            "image_url": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600",
            "menu": [
                ("Margherita Pizza", "Classic tomato, mozzarella & basil", 280, "Pizza", 1),
                ("Pepperoni Pizza", "Loaded with pepperoni & cheese", 350, "Pizza", 0),
                ("Garlic Bread", "Toasted bread with garlic herb butter", 120, "Sides", 1),
                ("Pasta Alfredo", "Creamy white sauce pasta", 260, "Pasta", 1),
                ("Tiramisu", "Classic Italian coffee dessert", 150, "Desserts", 1),
            ],
        },
        {
            "name": "Dragon Wok", "cuisine": "Chinese", "address": "Banjara Hills, Hyderabad",
            "rating": 4.1, "delivery_time_min": 35,
            "image_url": "https://images.unsplash.com/photo-1552566626-52f8b828add9?w=600",
            "menu": [
                ("Veg Manchurian", "Fried veg balls in tangy sauce", 210, "Starters", 1),
                ("Chicken Fried Rice", "Wok-tossed rice with chicken", 240, "Rice", 0),
                ("Hakka Noodles", "Stir fried noodles with veggies", 220, "Noodles", 1),
                ("Spring Rolls", "Crispy rolls with veg filling", 150, "Starters", 1),
                ("Chilli Chicken", "Spicy Indo-Chinese chicken dish", 280, "Main Course", 0),
            ],
        },
        {
            "name": "Burger Barn", "cuisine": "American", "address": "Hitech City, Hyderabad",
            "rating": 4.0, "delivery_time_min": 20,
            "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600",
            "menu": [
                ("Classic Cheeseburger", "Beef patty with cheddar cheese", 210, "Burgers", 0),
                ("Veggie Burger", "Grilled veggie patty burger", 180, "Burgers", 1),
                ("French Fries", "Crispy golden fries", 100, "Sides", 1),
                ("Chocolate Shake", "Thick chocolate milkshake", 140, "Beverages", 1),
                ("Chicken Wings", "Spicy fried chicken wings", 240, "Starters", 0),
            ],
        },
    ]

    for rdata in restaurants_data:
        cur = db.execute(
            "INSERT INTO restaurants (name, cuisine, address, rating, image_url, delivery_time_min, is_active) "
            "VALUES (?,?,?,?,?,?,1)",
            (rdata["name"], rdata["cuisine"], rdata["address"], rdata["rating"],
             rdata["image_url"], rdata["delivery_time_min"]),
        )
        restaurant_id = cur.lastrowid
        for name, desc, price, category, is_veg in rdata["menu"]:
            db.execute(
                "INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, available) "
                "VALUES (?,?,?,?,?,?,?,1)",
                (restaurant_id, name, desc, price, category,
                 "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400", is_veg),
            )

    db.commit()


# ---------------------------------------------------------------------------
# Query helper functions used by routes
# ---------------------------------------------------------------------------
def get_user_by_email(email):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_user(name, email, password, phone="", address=""):
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash, role, phone, address, created_at) VALUES (?,?,?,?,?,?,?)",
        (name, email, generate_password_hash(password), "customer", phone, address, datetime.utcnow().isoformat()),
    )
    db.commit()
    return cur.lastrowid


def verify_password(user_row, password):
    return check_password_hash(user_row["password_hash"], password)


def list_restaurants(query="", cuisine=""):
    sql = "SELECT * FROM restaurants WHERE is_active = 1"
    params = []
    if query:
        sql += " AND name LIKE ?"
        params.append(f"%{query}%")
    if cuisine:
        sql += " AND cuisine = ?"
        params.append(cuisine)
    return get_db().execute(sql, params).fetchall()


def list_cuisines():
    rows = get_db().execute("SELECT DISTINCT cuisine FROM restaurants").fetchall()
    return [r["cuisine"] for r in rows]


def get_restaurant(restaurant_id):
    return get_db().execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()


def get_menu_items(restaurant_id, only_available=True):
    sql = "SELECT * FROM menu_items WHERE restaurant_id = ?"
    if only_available:
        sql += " AND available = 1"
    return get_db().execute(sql, (restaurant_id,)).fetchall()


def get_menu_item(item_id):
    return get_db().execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()


def add_menu_item(restaurant_id, name, description, price, category, image_url, is_veg):
    db = get_db()
    db.execute(
        "INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, available) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (restaurant_id, name, description, price, category, image_url, 1 if is_veg else 0),
    )
    db.commit()


def toggle_menu_item(item_id):
    db = get_db()
    item = get_menu_item(item_id)
    db.execute("UPDATE menu_items SET available = ? WHERE id = ?", (0 if item["available"] else 1, item_id))
    db.commit()


def delete_menu_item(item_id):
    db = get_db()
    db.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    db.commit()


def add_restaurant(name, cuisine, address, rating, image_url, delivery_time_min):
    db = get_db()
    cur = db.execute(
        "INSERT INTO restaurants (name, cuisine, address, rating, image_url, delivery_time_min, is_active) "
        "VALUES (?,?,?,?,?,?,1)",
        (name, cuisine, address, rating, image_url, delivery_time_min),
    )
    db.commit()
    return cur.lastrowid


def create_order(user_id, restaurant_id, total_amount, delivery_address, payment_method, items):
    """items: list of (menu_item_row, quantity)"""
    db = get_db()
    cur = db.execute(
        "INSERT INTO orders (user_id, restaurant_id, total_amount, delivery_address, payment_method, "
        "payment_status, status, created_at) VALUES (?,?,?,?,?, 'Pending', ?, ?)",
        (user_id, restaurant_id, total_amount, delivery_address, payment_method,
         ORDER_STAGES[0], datetime.utcnow().isoformat()),
    )
    order_id = cur.lastrowid
    for item, qty in items:
        db.execute(
            "INSERT INTO order_items (order_id, menu_item_id, name_snapshot, price_snapshot, quantity) "
            "VALUES (?,?,?,?,?)",
            (order_id, item["id"], item["name"], item["price"], qty),
        )
    db.commit()
    return order_id


def get_order(order_id):
    return get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_order_items(order_id):
    return get_db().execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()


def get_delivery(order_id):
    return get_db().execute("SELECT * FROM deliveries WHERE order_id = ?", (order_id,)).fetchone()


def list_user_orders(user_id):
    return get_db().execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()


def list_recent_orders(limit=20):
    return get_db().execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


def mark_order_paid(order_id):
    db = get_db()
    db.execute(
        "UPDATE orders SET payment_status = 'Paid', status = ?, created_at = ? WHERE id = ?",
        (ORDER_STAGES[1], datetime.utcnow().isoformat(), order_id),
    )
    agent_name = random.choice(["Ravi Kumar", "Anita Sharma", "Vikram Singh", "Sneha Rao"])
    agent_phone = f"+91-9{random.randint(100000000, 999999999)}"
    vehicle = random.choice(["Bike", "Scooter"])
    estimated_minutes = random.randint(25, 45)
    db.execute(
        "INSERT INTO deliveries (order_id, agent_name, agent_phone, vehicle, estimated_minutes) VALUES (?,?,?,?,?)",
        (order_id, agent_name, agent_phone, vehicle, estimated_minutes),
    )
    db.commit()


def mark_order_failed(order_id):
    db = get_db()
    db.execute("UPDATE orders SET payment_status = 'Failed' WHERE id = ?", (order_id,))
    db.commit()


def update_order_status(order_id, status):
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()


def advance_order_stage(order_id):
    db = get_db()
    order = get_order(order_id)
    idx = ORDER_STAGES.index(order["status"])
    if idx < len(ORDER_STAGES) - 1:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (ORDER_STAGES[idx + 1], order_id))
        db.commit()
