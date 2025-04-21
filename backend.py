from flask import Flask, request, jsonify, session
import uuid
import json
import os
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'mein_geheimer_schluessel'
CORS(app, resources={r"/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]}})

# ----------------------------------
# Produkte laden
dummy_products_file = "products.json"
if os.path.exists(dummy_products_file):
    try:
        with open(dummy_products_file, "r") as f:
            products_db = json.load(f)
    except Exception as e:
        print("Fehler beim Laden der Produkte:", e)
        products_db = []
else:
    print("products.json nicht gefunden. Lege leere Produktliste an.")
    products_db = []

# ----------------------------------
# Benutzerdaten laden (für Authentifizierung)
dummy_users_file = "user.json"
if os.path.exists(dummy_users_file):
    try:
        with open(dummy_users_file, "r") as f:
            users_data = json.load(f)
    except Exception as e:
        print("Fehler beim Laden der Benutzerdaten:", e)
        users_data = []
else:
    print("user.json nicht gefunden. Lege leere Benutzerdaten an.")
    users_data = []

if isinstance(users_data, list):
    users_db = {user["username"]: user for user in users_data}
else:
    users_db = users_data

# Sicherstellen, dass jeder Benutzer eine Liste für Bestellungen hat
for uname, user in users_db.items():
    if "orders" not in user:
        user["orders"] = []

try:
    next_user_id = max(user["id"] for user in users_db.values()) + 1
except Exception:
    next_user_id = 1

# ----------------------------------
# Carts persistent speichern als Liste (DummyJSON-Style)
dummy_cart_file = "cart.json"
if os.path.exists(dummy_cart_file):
    try:
        with open(dummy_cart_file, "r") as f:
            carts_db = json.load(f)  # Erwartet wird eine Liste von Cart-Objekten
            if not isinstance(carts_db, list):
                # Falls doch ein anderes Format gespeichert wurde, konvertieren wir es in eine Liste:
                carts_db = list(carts_db.values())
    except Exception as e:
        print("Fehler beim Laden des Warenkorbs:", e)
        carts_db = []
else:
    carts_db = []  # Leere Liste, falls keine Datei existiert

def save_carts():
    try:
        with open(dummy_cart_file, "w") as f:
            json.dump(carts_db, f, indent=4)
    except Exception as e:
        print("Fehler beim Speichern des Warenkorbs:", e)

# Berechne next_cart_id basierend auf der Liste der vorhandenen Carts
    next_cart_id = 1 if not carts_db else max(cart.get("id", 0) for cart in carts_db) + 1

def calculate_cart(cart):
    """
    Berechnet zu einem Cart (mit 'products' als Liste von { "id": product_id, "quantity": ... })
    die Details: total, discountedTotal, totalProducts, totalQuantity und ergänzt die Produktdaten.
    """
    products_detail = []
    total_quantity = 0
    total_price = 0.0
    for prod in cart.get("products", []):
        product = next((p for p in products_db if p["id"] == prod["id"]), None)
        if product:
            quantity = prod.get("quantity", 0)
            item_total = round(product['price'] * quantity, 2)
            discount_percentage = product.get("discountPercentage", 0)
            item_discounted_price = round(item_total * (1 - discount_percentage / 100), 2)
            products_detail.append({
                "id": product["id"],
                "title": product["title"],
                "price": product["price"],
                "quantity": quantity,
                "total": item_total,
                "discountPercentage": discount_percentage,
                "discountedTotal": item_discounted_price,
                "thumbnail": product.get("thumbnail", "")
            })
            total_quantity += quantity
            total_price += item_total
    discounted_total = sum(item["discountedTotal"] for item in products_detail)
    cart["products"] = products_detail
    cart["total"] = round(total_price, 2)
    cart["discountedTotal"] = round(discounted_total, 2)
    cart["totalProducts"] = len(products_detail)
    cart["totalQuantity"] = total_quantity
    return cart

# ----------------------------------
# Authentifizierung und Benutzerverwaltung (unverändert)

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"message": "Username und Passwort sind erforderlich"}), 400
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
        return jsonify({"message": "Ungültige Zugangsdaten"}), 401

@app.route('/auth/me', methods=['GET'])
def get_current_user():
    if 'user_id' not in session or 'username' not in session:
        return jsonify({"message": "Authentifizierung erforderlich"}), 401
    username = session['username']
    user_data = users_db.get(username)
    if user_data:
        user_info = {k: v for k, v in user_data.items() if k != 'password'}
        return jsonify(user_info), 200
    else:
        session.clear()
        return jsonify({"message": "Dateninkonsistenz: Benutzer existiert nicht. Abmeldung erfolgt."}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Erfolgreich abgemeldet"}), 200

@app.route('/users/add', methods=['POST', 'OPTIONS'])
def add_user():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"message": "Username und Passwort sind erforderlich"}), 400
    username = data['username']
    if username in users_db:
        return jsonify({"message": "Username existiert bereits"}), 409
    global next_user_id
    new_user = {
        "id": next_user_id,
        "username": username,
        "password": data['password'],
        "role": data.get("role", "user"),
        "firstName": data.get("firstName", ""),
        "lastName": data.get("lastName", ""),
        "maidenName": data.get("maidenName", ""),
        "age": data.get("age", 0),
        "gender": data.get("gender", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "birthDate": data.get("birthDate", ""),
        "image": data.get("image", ""),
        "bloodGroup": data.get("bloodGroup", ""),
        "height": data.get("height", 0.0),
        "weight": data.get("weight", 0.0),
        "eyeColor": data.get("eyeColor", ""),
        "hair": data.get("hair", {}),
        "ip": data.get("ip", ""),
        "address": data.get("address", {}),
        "macAddress": data.get("macAddress", ""),
        "university": data.get("university", ""),
        "bank": data.get("bank", {}),
        "company": data.get("company", {}),
        "ein": data.get("ein", ""),
        "ssn": data.get("ssn", ""),
        "userAgent": data.get("userAgent", ""),
        "crypto": data.get("crypto", {}),
        "orders": []
    }
    next_user_id += 1
    users_db[username] = new_user
    try:
        with open(dummy_users_file, "w") as f:
            json.dump(list(users_db.values()), f, indent=4)
    except Exception as e:
        print("Fehler beim Speichern der Benutzerdaten:", e)
    new_user_info = {k: v for k, v in new_user.items() if k != 'password'}
    return jsonify(new_user_info), 201

# ----------------------------------
# Produkt-Endpunkte (unverändert)

@app.route('/products', methods=['GET'])
def get_products():
    limit = request.args.get('limit', default=30, type=int)
    skip = request.args.get('skip', default=0, type=int)
    paginated_products = products_db[skip: skip + limit]
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
        return jsonify({"message": f"Produkt mit id '{product_id}' nicht gefunden"}), 404

@app.route('/products/search', methods=['GET'])
def search_products():
    query = request.args.get('q')
    if not query:
        return jsonify({"message": "Suchparameter 'q' ist erforderlich"}), 400
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

# ----------------------------------
# DummyJSON-Style Carts Endpunkte (arbeiten jetzt mit einer Liste)

# GET alle Carts
@app.route('/carts', methods=['GET'])
def get_all_carts():
    response = {
        "carts": carts_db,
        "total": len(carts_db),
        "skip": 0,
        "limit": len(carts_db)
    }
    return jsonify(response)

# GET einen einzelnen Cart
@app.route('/carts/<int:cart_id>', methods=['GET'])
def get_cart(cart_id):
    # Suche nach einem existierenden Cart mit der angegebenen ID
    cart = next((c for c in carts_db if c.get("id") == cart_id), None)
    if cart:
        return jsonify(cart)
    else:
        # Kein Cart gefunden: Neuen leeren Cart mit der gegebenen ID anlegen
        new_cart = {
            "id": cart_id,
            "userId": None,        # Hier ggf. anpassen, falls der Cart mit einem Benutzer verknüpft werden soll
            "products": [],        # Leere Liste für Produkte
            "total": 0,
            "discountedTotal": 0,
            "totalProducts": 0,
            "totalQuantity": 0
        }
        carts_db.append(new_cart)  # Neuen Cart zur Liste hinzufügen
        save_carts()               # Persistiere die Änderung in der JSON-Datei
        return jsonify(new_cart)

# GET Carts eines Benutzers
@app.route('/carts/user/<int:user_id>', methods=['GET'])
def get_carts_by_user(user_id):
    carts_list = [cart for cart in carts_db if cart.get("userId") == user_id]
    response = {
        "carts": carts_list,
        "total": len(carts_list)
    }
    return jsonify(response)

# POST zum Hinzufügen eines neuen Carts (Simulation)
@app.route('/carts/add', methods=['POST'])
def add_cart():
    data = request.get_json()
    if not data or 'userId' not in data or 'products' not in data:
        return jsonify({"message": "userId and products are required"}), 400

    userId = data['userId']
    products = data['products']
    global next_cart_id
    cart = {
        "id": next_cart_id,
        "userId": userId,
        "products": products
    }
    cart = calculate_cart(cart)
    carts_db.append(cart)
    next_cart_id += 1
    save_carts()
    return jsonify(cart)

# PUT / PATCH zum Aktualisieren eines Carts (Simulation)
@app.route('/carts/<int:cart_id>', methods=['PUT', 'PATCH'])
def update_cart(cart_id):
    # Suche den existierenden Cart in der Liste
    index = next((i for i, c in enumerate(carts_db) if c.get("id") == cart_id), None)
    if index is None:
        return jsonify({"message": f"Cart with id {cart_id} not found"}), 404

    data = request.get_json()
    if not data or 'products' not in data:
        return jsonify({"message": "products field is required"}), 400

    merge = data.get("merge", False)
    new_products = data['products']
    existing_cart = carts_db[index]
    if merge:
        # Vorhandene Produkte mit den neuen zusammenführen
        existing_products = {prod['id']: prod for prod in existing_cart.get("products", [])}
        for prod in new_products:
            prod_id = prod['id']
            if prod_id in existing_products:
                existing_products[prod_id]['quantity'] += prod.get('quantity', 0)
            else:
                existing_products[prod_id] = prod
        merged_products = list(existing_products.values())
        existing_cart['products'] = merged_products
    else:
        existing_cart['products'] = new_products

    updated_cart = calculate_cart(existing_cart)
    carts_db[index] = updated_cart
    save_carts()
    return jsonify(updated_cart)

# DELETE zum Löschen eines Carts (Simulation)
@app.route('/carts/<int:cart_id>', methods=['DELETE'])
def delete_cart(cart_id):
    index = next((i for i, c in enumerate(carts_db) if c.get("id") == cart_id), None)
    if index is None:
        return jsonify({"message": f"Cart with id {cart_id} not found"}), 404

    cart = carts_db.pop(index)
    cart['isDeleted'] = True
    cart['deletedOn'] = datetime.utcnow().isoformat()
    save_carts()
    return jsonify(cart)

# ----------------------------------
# Weitere Endpunkte (z.B. Order-Management) können hier ergänzt werden.

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
