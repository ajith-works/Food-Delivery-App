import os
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for, request, flash, jsonify, session, g
)

import database as db

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

app.teardown_appcontext(db.close_db)
db.init_db(app)


@app.template_filter("fmtdate")
def fmtdate(value):
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(value).strftime("%d %b %Y, %I:%M %p")
    except (ValueError, TypeError):
        return value


# ---------------------------------------------------------------------------
# Lightweight auth (session-based) — no external auth library required
# ---------------------------------------------------------------------------
class AnonymousUser:
    is_authenticated = False
    is_admin = False
    name = ""


class CurrentUser:
    def __init__(self, row):
        self._row = row
        self.is_authenticated = True

    def __getitem__(self, key):
        return self._row[key]

    @property
    def id(self):
        return self._row["id"]

    @property
    def name(self):
        return self._row["name"]

    @property
    def email(self):
        return self._row["email"]

    @property
    def address(self):
        return self._row["address"]

    @property
    def is_admin(self):
        return self._row["role"] == "admin"


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = CurrentUser(db.get_user_by_id(user_id)) if user_id else AnonymousUser()


@app.context_processor
def inject_current_user():
    return {"current_user": g.user}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user.is_authenticated or not g.user.is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Cart helpers (session-based)
# ---------------------------------------------------------------------------
def get_cart():
    return session.setdefault("cart", {})  # {menu_item_id(str): quantity}


def cart_details():
    cart = get_cart()
    items = []
    total = 0.0
    restaurant = None
    for item_id, qty in cart.items():
        mi = db.get_menu_item(int(item_id))
        if not mi:
            continue
        restaurant = db.get_restaurant(mi["restaurant_id"])
        subtotal = mi["price"] * qty
        total += subtotal
        items.append({"item": mi, "qty": qty, "subtotal": round(subtotal, 2)})
    return items, round(total, 2), restaurant


DELIVERY_FEE = 30.0


# ---------------------------------------------------------------------------
# Public / customer routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    cuisine = request.args.get("cuisine", "")
    restaurants = db.list_restaurants(query, cuisine)
    cuisines = db.list_cuisines()
    return render_template(
        "index.html", restaurants=restaurants, cuisines=cuisines,
        query=query, selected_cuisine=cuisine
    )


@app.route("/restaurant/<int:restaurant_id>")
def restaurant_detail(restaurant_id):
    restaurant = db.get_restaurant(restaurant_id)
    if not restaurant:
        flash("Restaurant not found.", "warning")
        return redirect(url_for("index"))

    items = db.get_menu_items(restaurant_id)
    categories = {}
    for item in items:
        categories.setdefault(item["category"], []).append(item)
    return render_template("restaurant.html", restaurant=restaurant, categories=categories)


@app.route("/cart/add/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    mi = db.get_menu_item(item_id)
    if not mi:
        flash("Item not found.", "warning")
        return redirect(url_for("index"))

    cart = get_cart()
    if cart:
        existing_id = list(cart.keys())[0]
        existing_item = db.get_menu_item(int(existing_id))
        if existing_item and existing_item["restaurant_id"] != mi["restaurant_id"]:
            cart.clear()
            flash("Your cart was cleared because you started ordering from a different restaurant.", "info")

    key = str(item_id)
    cart[key] = cart.get(key, 0) + 1
    session.modified = True
    flash(f"Added {mi['name']} to cart.", "success")
    return redirect(request.referrer or url_for("restaurant_detail", restaurant_id=mi["restaurant_id"]))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
def remove_from_cart(item_id):
    cart = get_cart()
    cart.pop(str(item_id), None)
    session.modified = True
    return redirect(url_for("view_cart"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
def update_cart(item_id):
    qty = max(0, int(request.form.get("quantity", 1)))
    cart = get_cart()
    if qty == 0:
        cart.pop(str(item_id), None)
    else:
        cart[str(item_id)] = qty
    session.modified = True
    return redirect(url_for("view_cart"))


@app.route("/cart")
def view_cart():
    items, total, restaurant = cart_details()
    return render_template("cart.html", items=items, total=total, restaurant=restaurant)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if db.get_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        user_id = db.create_user(
            name, email, password,
            phone=request.form.get("phone", ""),
            address=request.form.get("address", ""),
        )
        session["user_id"] = user_id
        flash("Account created successfully!", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = db.get_user_by_email(email)
        if user and db.verify_password(user, password):
            session["user_id"] = user["id"]
            flash("Logged in successfully.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Checkout / Payment gateway (simulated)
# ---------------------------------------------------------------------------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total, restaurant = cart_details()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        address = request.form.get("address") or g.user.address
        payment_method = request.form.get("payment_method", "Card")

        order_id = db.create_order(
            user_id=g.user.id,
            restaurant_id=restaurant["id"],
            total_amount=round(total + DELIVERY_FEE, 2),
            delivery_address=address,
            payment_method=payment_method,
            items=[(entry["item"], entry["qty"]) for entry in items],
        )
        return redirect(url_for("payment", order_id=order_id))

    return render_template("checkout.html", items=items, total=total, restaurant=restaurant,
                            default_address=g.user.address, delivery_fee=DELIVERY_FEE)


@app.route("/payment/<int:order_id>", methods=["GET", "POST"])
@login_required
def payment(order_id):
    order = db.get_order(order_id)
    if not order or order["user_id"] != g.user.id:
        flash("Not authorized.", "danger")
        return redirect(url_for("index"))

    if order["payment_status"] == "Paid":
        return redirect(url_for("track_order", order_id=order_id))

    if request.method == "POST":
        # --- Simulated payment gateway ---------------------------------
        # In production this is where you'd integrate Stripe/Razorpay/PayPal.
        # Here we simulate a gateway round-trip with basic card-field validation.
        card_number = request.form.get("card_number", "").replace(" ", "")
        if len(card_number) >= 12 and card_number.isdigit():
            db.mark_order_paid(order_id)
            session["cart"] = {}
            flash("Payment successful! Your order is confirmed.", "success")
            return redirect(url_for("track_order", order_id=order_id))
        else:
            db.mark_order_failed(order_id)
            flash("Payment failed. Please check your card details and try again.", "danger")
            order = db.get_order(order_id)

    return render_template("payment.html", order=order)


# ---------------------------------------------------------------------------
# Order tracking (real-time simulated via polling)
# ---------------------------------------------------------------------------
@app.route("/orders")
@login_required
def my_orders():
    orders = db.list_user_orders(g.user.id)
    orders_view = []
    for o in orders:
        restaurant = db.get_restaurant(o["restaurant_id"])
        orders_view.append(dict(o, live_status=db.compute_live_status(o),
                                 restaurant_name=restaurant["name"] if restaurant else "Unknown"))
    return render_template("orders.html", orders=orders_view)


@app.route("/order/<int:order_id>")
@login_required
def track_order(order_id):
    order = db.get_order(order_id)
    if not order or (order["user_id"] != g.user.id and not g.user.is_admin):
        flash("Not authorized.", "danger")
        return redirect(url_for("index"))

    restaurant = db.get_restaurant(order["restaurant_id"])
    items = db.get_order_items(order_id)
    delivery = db.get_delivery(order_id)
    live_status = db.compute_live_status(order)
    if live_status != order["status"]:
        db.update_order_status(order_id, live_status)
        order = db.get_order(order_id)

    return render_template(
        "track_order.html", order=order, restaurant=restaurant, items=items,
        delivery=delivery, stages=db.ORDER_STAGES,
        progress=db.progress_percent(order["status"]),
    )


@app.route("/api/order/<int:order_id>/status")
@login_required
def api_order_status(order_id):
    order = db.get_order(order_id)
    if not order or (order["user_id"] != g.user.id and not g.user.is_admin):
        return jsonify({"error": "unauthorized"}), 403

    live_status = db.compute_live_status(order)
    if live_status != order["status"]:
        db.update_order_status(order_id, live_status)

    delivery = db.get_delivery(order_id)
    return jsonify({
        "status": live_status,
        "progress": db.progress_percent(live_status),
        "stages": db.ORDER_STAGES,
        "payment_status": order["payment_status"],
        "delivery": {
            "agent_name": delivery["agent_name"],
            "agent_phone": delivery["agent_phone"],
            "vehicle": delivery["vehicle"],
            "estimated_minutes": delivery["estimated_minutes"],
        } if delivery else None,
    })


# ---------------------------------------------------------------------------
# Admin: restaurant & menu management
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    all_restaurants = db.get_db().execute("SELECT * FROM restaurants").fetchall()
    orders = db.list_recent_orders(20)
    orders_view = []
    for o in orders:
        user = db.get_user_by_id(o["user_id"])
        restaurant = db.get_restaurant(o["restaurant_id"])
        orders_view.append(dict(o, user_name=user["name"], restaurant_name=restaurant["name"],
                                 live_status=db.compute_live_status(o)))
    menu_counts = {r["id"]: len(db.get_menu_items(r["id"], only_available=False)) for r in all_restaurants}
    return render_template("admin/dashboard.html", restaurants=all_restaurants,
                            orders=orders_view, menu_counts=menu_counts)


@app.route("/admin/restaurant/new", methods=["GET", "POST"])
@admin_required
def admin_new_restaurant():
    if request.method == "POST":
        db.add_restaurant(
            name=request.form["name"],
            cuisine=request.form["cuisine"],
            address=request.form["address"],
            rating=float(request.form.get("rating") or 4.0),
            image_url=request.form.get("image_url") or
                      "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600",
            delivery_time_min=int(request.form.get("delivery_time_min") or 30),
        )
        flash("Restaurant added.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/restaurant_form.html")


@app.route("/admin/restaurant/<int:restaurant_id>/menu", methods=["GET", "POST"])
@admin_required
def admin_manage_menu(restaurant_id):
    restaurant = db.get_restaurant(restaurant_id)
    if not restaurant:
        flash("Restaurant not found.", "warning")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        db.add_menu_item(
            restaurant_id=restaurant_id,
            name=request.form["name"],
            description=request.form.get("description", ""),
            price=float(request.form["price"]),
            category=request.form.get("category") or "Main Course",
            image_url=request.form.get("image_url") or
                      "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400",
            is_veg=bool(request.form.get("is_veg")),
        )
        flash("Menu item added.", "success")
        return redirect(url_for("admin_manage_menu", restaurant_id=restaurant_id))

    menu_items = db.get_menu_items(restaurant_id, only_available=False)
    return render_template("admin/menu_form.html", restaurant=restaurant, menu_items=menu_items)


@app.route("/admin/menu-item/<int:item_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_item(item_id):
    item = db.get_menu_item(item_id)
    if item:
        db.toggle_menu_item(item_id)
        return redirect(url_for("admin_manage_menu", restaurant_id=item["restaurant_id"]))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu-item/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_item(item_id):
    item = db.get_menu_item(item_id)
    if item:
        restaurant_id = item["restaurant_id"]
        db.delete_menu_item(item_id)
        return redirect(url_for("admin_manage_menu", restaurant_id=restaurant_id))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/order/<int:order_id>/advance", methods=["POST"])
@admin_required
def admin_advance_order(order_id):
    """Lets an admin manually push an order to the next stage (overrides the
    time-based simulation) — useful for demoing the real-time tracker."""
    db.advance_order_stage(order_id)
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
