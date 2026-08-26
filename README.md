# FoodExpress — Food Delivery Platform

A full-stack food delivery web app built with **Python (Flask)**, **SQLAlchemy**,
and **HTML/CSS/Bootstrap**, covering all the required internship task features:

- 🍽️ **Restaurant listings** — search & filter by cuisine
- 📋 **Menu management** — admin panel to add/enable/disable/delete menu items per restaurant
- 🛒 **Cart & checkout** — add items, adjust quantities, single-restaurant cart rule
- 💳 **Payment gateway (simulated)** — card entry form, validated & "processed" server-side
- 📦 **Order tracking with real-time delivery status** — a live progress tracker that
  polls the server every few seconds and advances through: Order Placed → Confirmed →
  Preparing → Out for Delivery → Delivered
- 👤 **Authentication** — signup/login (Flask-Login, hashed passwords)
- 🛠️ **Admin dashboard** — manage restaurants/menus, view & advance orders

## Project structure

```
food_delivery_app/
├── app.py                  # Flask routes & app setup
├── models.py                # SQLAlchemy models (User, Restaurant, MenuItem, Order, OrderItem, Delivery)
├── schema_mysql.sql         # Reference MySQL schema (matches the models)
├── requirements.txt
├── static/
│   └── css/style.css
└── templates/
    ├── base.html, index.html, restaurant.html, cart.html,
    ├── checkout.html, payment.html, track_order.html, orders.html,
    ├── login.html, register.html
    └── admin/dashboard.html, restaurant_form.html, menu_form.html
```

## Setup

```bash
pip install -r requirements.txt
python app.py
```

The app runs at **http://localhost:5000**. On first run it auto-creates the
database and seeds 4 demo restaurants with menus, plus two demo accounts:

| Role     | Email                        | Password    |
|----------|------------------------------|-------------|
| Customer | customer@example.com          | password123 |
| Admin    | admin@fooddelivery.com        | admin123    |

## Database: SQLite by default, MySQL-ready

The app uses SQLAlchemy, so it runs out-of-the-box on **SQLite** (zero setup —
great for demos/grading). To use **MySQL** as the internship task specifies:

```bash
pip install pymysql
export DATABASE_URL="mysql+pymysql://<user>:<password>@localhost/food_delivery"
python app.py
```

`schema_mysql.sql` is included for reference/documentation — SQLAlchemy will
create the same tables automatically via `db.create_all()`.

## How the "real-time" delivery tracking works

Rather than requiring a message queue/websocket server for a demo project,
each order's stage is derived deterministically from **elapsed time since
payment** (`Order.compute_live_status()` in `models.py`). The tracking page
(`track_order.html`) polls `GET /api/order/<id>/status` every 4 seconds and
animates the progress bar/stage indicators — so it behaves like a live tracker
without extra infrastructure. An admin can also manually push an order to the
next stage from the Admin Dashboard for demo purposes.

## Payment gateway

`app.py`'s `/payment/<order_id>` route simulates a gateway: it validates a
card-like number format and marks the order `Paid` on success (or `Failed`
otherwise), then generates a delivery assignment. Swapping in a real processor
(Stripe, Razorpay) only requires replacing the body of that route with an API
call — the rest of the flow (order → payment → tracking) stays the same.

## Notes for extending

- Add real-time push (Flask-SocketIO) instead of polling if you want instant updates.
- Add restaurant owner accounts (currently one shared `admin` role manages all restaurants).
- Add ratings/reviews, order cancellation, and refunds for a production version.
