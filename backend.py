from flask import Flask, request, jsonify, session
import uuid
import json
import os
from datetime import datetime
from flask_cors import CORS
app = Flask(__name__)
app.secret_key = 'mein_geheimer_schluessel'
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
# ------------------------------
# Laden der Produkte (wie zuvor)
dummy_products_file = "products.json"
if os.path.exists(dummy_products_file):
    with open(dummy_products_file, "r") as f:
        products_db = json.load(f)
else:
   print("product fail")

# ------------------------------
# Laden der User-Daten (wie im vorherigen Beispiel)
dummy_users_file = "user.json"
if os.path.exists(dummy_users_file):
    with open(dummy_users_file, "r") as f:
        users_data = json.load(f)
    if isinstance(users_data, list):
        users_db = {user["username"]: user for user in users_data}
    else:
        users_db = users_data
    for uname, user in users_db.items():
        if "orders" not in user:
            user["orders"] = []
    try:
        next_user_id = max(user["id"] for user in users_db.values()) + 1
    except ValueError:
        next_user_id = 1
else:
    print("user fail")


# ------------------------------
# Laden und Speichern des Warenkorbs in einer JSON-Datei

dummy_cart_file = "dummy_cart.json"
if os.path.exists(dummy_cart_file):
    with open(dummy_cart_file, "r") as f:
        carts_db = json.load(f)
else:
    carts_db = {}  # Struktur: { username: { "cart_id": ..., "items": { "product_id": {...}, ... } } }

def save_carts():
    with open(dummy_cart_file, "w") as f:
        json.dump(carts_db, f, indent=4)

def get_cart_for_user(username):
    """Holt den Warenkorb für den gegebenen Benutzer (erstellt einen neuen, falls nicht vorhanden)."""
    if username not in carts_db:
        carts_db[username] = {
            "cart_id": f"cart_{uuid.uuid4()}",
            "items": {}  # items wird als Dictionary gespeichert, z.B. { "1": {"product_id": 1, "quantity": 2}, ... }
        }
    return carts_db[username]

def get_cart_details(cart):
    """Berechnet Details für einen Warenkorb, der die Struktur {cart_id, items} hat."""
    detailed_products = []
    total_quantity = 0
    total_price = 0.0
    items = cart.get("items", {})

    for item_key, item_data in items.items():
        product = next((p for p in products_db if p["id"] == item_data['product_id']), None)
        if product:
            quantity = item_data['quantity']
            item_total = round(product['price'] * quantity, 2)
            discount_percentage = product.get('discountPercentage', 0)
            item_discounted_price = round(item_total * (1 - discount_percentage / 100), 2)
            detailed_products.append({
                "id": product['id'],
                "title": product['title'],
                "price": product['price'],
                "quantity": quantity,
                "total": item_total,
                "discountPercentage": discount_percentage,
                "discountedPrice": item_discounted_price
            })
            total_quantity += quantity
            total_price += item_total

    discounted_total_price = sum(p['discountedPrice'] for p in detailed_products)

    return {
        "id": cart.get("cart_id"),
        "products": detailed_products,
        "total": round(total_price, 2),
        "discountedTotal": round(discounted_total_price, 2),
        "userId": session.get('user_id', None),
        "totalProducts": len(detailed_products),
        "totalQuantity": total_quantity
    }

# ------------------------------
# Endpunkte

# Authentifizierung (unverändert)
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"message": "Username and password are required"}), 400
    username = data['username']
    password = data['password']
    user_data = users_db.get(username)
    if user_data and user_data['password'] == password:
        user_info = {k: v for k, v in user_data.items() if k != 'password'}
        session['user_id'] = user_data['id']
        session['username'] = username
        session.modified = True
        dummy_token = f"dummy-jwt-token-for-{username}-{uuid.uuid4()}"
        user_info['token'] = dummy_token
        return jsonify(user_info), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/auth/me', methods=['GET'])
def get_current_user():
    if 'user_id' not in session or 'username' not in session:
        return jsonify({"message": "Authentication required"}), 401
    username = session['username']
    user_data = users_db.get(username)
    if user_data:
        user_info = {k: v for k, v in user_data.items() if k != 'password'}
        return jsonify(user_info), 200
    else:
        session.clear()
        return jsonify({"message": "User data inconsistency, logged out."}), 500

# Produkte (unverändert)

@app.route('/products', methods=['GET'])
def get_products():
    # Parameter 'limit' und 'skip' aus der URL abrufen.
    # Standardwerte: limit=30, skip=0 (kannst Du je nach Bedarf anpassen)
    limit = request.args.get('limit', default=30, type=int)
    skip = request.args.get('skip', default=0, type=int)

    # Erzeuge die paginierte Liste der Produkte (alle Felder bleiben erhalten).
    paginated_products = products_db[skip: skip + limit]

    # Erstelle das Response-Objekt im gewünschten Format.
    response = {
        "products": paginated_products,
        "total": len(products_db),
        "skip": skip,
        "limit": limit
    }
    return jsonify(response)


@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = next((p for p in products_db if p["id"] == product_id), None)
    if product:
        return jsonify(product)
    else:
        return jsonify({"message": f"Product with id '{product_id}' not found"}), 404

@app.route('/products/search', methods=['GET'])
def search_products():
    query = request.args.get('q')
    if not query:
        return jsonify({"message": "Search query 'q' is required"}), 400
    query = query.lower()
    results = []
    for p in products_db:
        if (query in p.get('title', '').lower() or
            query in p.get('description', '').lower() or
            any(query in tag.lower() for tag in p.get('tags', []))):
            results.append(p)
    limit = request.args.get('limit', default=10, type=int)
    skip = request.args.get('skip', default=0, type=int)
    paginated_results = results[skip: skip + limit]
    response = {
        "products": paginated_results,
        "total": len(results),
        "skip": skip,
        "limit": limit
    }
    return jsonify(response)

# ------------------------------
# Warenkorb-Endpunkte mit JSON-Persistenz

@app.route('/cart', methods=['GET'])
def view_cart():
    if 'username' not in session:
        return jsonify({"message": "Authentication required"}), 401
    username = session['username']
    user_cart = get_cart_for_user(username)
    cart_details = get_cart_details(user_cart)
    return jsonify(cart_details)

@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    if 'username' not in session:
        return jsonify({"message": "Authentication required to modify cart"}), 401
    data = request.get_json()
    if not data or 'product_id' not in data or 'quantity' not in data:
        return jsonify({"message": "Missing product_id or quantity"}), 400
    try:
        product_id = int(data['product_id'])
    except ValueError:
        return jsonify({"message": "Invalid product_id"}), 400
    quantity = data['quantity']
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"message": "Invalid quantity"}), 400
    product = next((p for p in products_db if p["id"] == product_id), None)
    if not product:
        return jsonify({"message": "Product not found"}), 404

    username = session['username']
    user_cart = get_cart_for_user(username)
    items = user_cart.get("items", {})

    item_key = str(product_id)
    if item_key in items:
        items[item_key]['quantity'] += quantity
    else:
        items[item_key] = {'product_id': product_id, 'quantity': quantity}
    user_cart["items"] = items
    carts_db[username] = user_cart
    save_carts()  # Persistiere die Änderung
    cart_details = get_cart_details(user_cart)
    return jsonify(cart_details), 200

@app.route('/cart/item/<int:product_id>', methods=['PUT'])
def update_cart_item(product_id):
    if 'username' not in session:
        return jsonify({"message": "Authentication required to modify cart"}), 401
    data = request.get_json()
    if not data or 'quantity' not in data:
        return jsonify({"message": "Missing quantity"}), 400
    quantity = data['quantity']
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"message": "Invalid quantity, must be a positive integer"}), 400

    username = session['username']
    user_cart = get_cart_for_user(username)
    items = user_cart.get("items", {})
    item_key = str(product_id)
    if item_key not in items:
        return jsonify({"message": "Product not found in cart"}), 404
    items[item_key]['quantity'] = quantity
    user_cart["items"] = items
    carts_db[username] = user_cart
    save_carts()
    cart_details = get_cart_details(user_cart)
    return jsonify(cart_details), 200

@app.route('/cart/item/<int:product_id>', methods=['DELETE'])
def remove_from_cart(product_id):
    if 'username' not in session:
        return jsonify({"message": "Authentication required to modify cart"}), 401
    username = session['username']
    user_cart = get_cart_for_user(username)
    items = user_cart.get("items", {})
    item_key = str(product_id)
    if item_key not in items:
        return jsonify({"message": "Product not found in cart"}), 404
    del items[item_key]
    user_cart["items"] = items
    carts_db[username] = user_cart
    save_carts()
    cart_details = get_cart_details(user_cart)
    return jsonify(cart_details), 200

# ------------------------------
# Die übrigen Endpunkte (Benutzer, Checkout, Orders) bleiben wie zuvor.
# ...

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
