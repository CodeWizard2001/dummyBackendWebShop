from flask import Flask, request, jsonify, session, g # g hinzugefügt
import uuid
import json
import os
from datetime import datetime
from functools import wraps # für Decorator
from flask_cors import CORS


#python -m pip install -r requirements.txt
app = Flask(__name__)
app.secret_key = 'mein_geheimer_schluessel' # Sollte sicherer sein in Produktion!
CORS(app, resources={r"/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]}})

# ----------------------------------
# Produkte laden
dummy_products_file = "products.json"
try:
    with open(dummy_products_file, "r") as f:
        products_db = json.load(f)
except Exception as e:
    print(f"Warnung: Konnte {dummy_products_file} nicht laden oder Datei ist leer/ungültig: {e}")
    products_db = []

# ----------------------------------
# Benutzerdaten laden
dummy_users_file = "user.json"
try:
    with open(dummy_users_file, "r") as f:
        users_list = json.load(f)
        users_db = {user["username"]: user for user in users_list} # Für schnellen Zugriff über Username
        users_by_id = {user["id"]: user for user in users_list} # Für schnellen Zugriff über ID
except Exception as e:
    print(f"Warnung: Konnte {dummy_users_file} nicht laden oder Datei ist leer/ungültig: {e}")
    users_db = {}
    users_by_id = {}

# Nächste User ID finden
try:
    next_user_id = max(user["id"] for user in users_by_id.values()) + 1 if users_by_id else 1
except Exception:
    next_user_id = 1

# ----------------------------------
# Bearer Token Speicherung
dummy_tokens_file = "bearer_tokens.json"
# Struktur: { "token_string": user_id }
try:
    with open(dummy_tokens_file, "r") as f:
        bearer_tokens = json.load(f)
        if not isinstance(bearer_tokens, dict):
             print(f"Warnung: {dummy_tokens_file} hat kein gültiges Dictionary-Format. Initialisiere neu.")
             bearer_tokens = {}
except FileNotFoundError:
    print(f"{dummy_tokens_file} nicht gefunden. Lege neue Datei an.")
    bearer_tokens = {}
except json.JSONDecodeError:
    print(f"Warnung: {dummy_tokens_file} enthält ungültiges JSON. Initialisiere neu.")
    bearer_tokens = {}
except Exception as e:
    print(f"Fehler beim Laden der Tokens: {e}")
    bearer_tokens = {}


def save_bearer_tokens():
    try:
        # Optional: Alte Tokens für den Benutzer entfernen (siehe login)
        with open(dummy_tokens_file, "w") as f:
            json.dump(bearer_tokens, f, indent=4)
    except Exception as e:
        print("Fehler beim Speichern der Tokens:", e)

# ----------------------------------
# Warenkörbe laden
dummy_cart_file = "cart.json"
# Struktur: Liste von Warenkörben, jeder mit "userId" als Kennung
try:
    with open(dummy_cart_file, "r") as f:
        carts_db_list = json.load(f)
        if not isinstance(carts_db_list, list):
             print(f"Warnung: {dummy_cart_file} hat kein gültiges Listen-Format. Initialisiere neu.")
             carts_db_list = []
except FileNotFoundError:
    print(f"{dummy_cart_file} nicht gefunden. Lege neue Datei an.")
    carts_db_list = []
except json.JSONDecodeError:
    print(f"Warnung: {dummy_cart_file} enthält ungültiges JSON. Initialisiere neu.")
    carts_db_list = []
except Exception as e:
    print(f"Fehler beim Laden der Warenkörbe: {e}")
    carts_db_list = []

# Für schnellen Zugriff: Konvertiere zu Dict { userId: cart }
# Annahme: Jeder User hat max. 1 Warenkorb (kann angepasst werden)
carts_db = {cart['userId']: cart for cart in carts_db_list if 'userId' in cart}

def save_carts():
    try:
        # Konvertiere Dict zurück zu Liste für Speicherung
        carts_list_to_save = list(carts_db.values())
        with open(dummy_cart_file, "w") as f:
            json.dump(carts_list_to_save, f, indent=4)
    except Exception as e:
        print("Fehler beim Speichern des Warenkorbs:", e)

# ----------------------------------
# Hilfsfunktionen

def calculate_cart_totals(cart, products_lookup):
    """Berechnet die Summen für einen Warenkorb basierend auf product_ids."""
    products_detail = []
    total_quantity = 0
    total_price = 0.0

    cart_products = cart.get("products", [])
    if not isinstance(cart_products, list):
         print(f"Warnung: 'products' in cart für userId {cart.get('userId')} ist keine Liste.")
         cart_products = [] # Sicherheitshalber leere Liste verwenden

    # Erstelle ein Dictionary für schnellen Produktzugriff anhand der ID
    products_by_id = {p['id']: p for p in products_lookup}

    valid_cart_products = [] # Liste für gültige Produkte im Warenkorb

    for item in cart_products:
        product_id = item.get("id")
        quantity = item.get("quantity", 0)

        if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity <= 0:
             print(f"Warnung: Ungültiger Eintrag im Warenkorb {cart.get('userId')}: {item}")
             continue # Überspringe ungültige Einträge

        product = products_by_id.get(product_id)

        if product:
            item_total = round(product.get('price', 0) * quantity, 2)
            discount_percentage = product.get("discountPercentage", 0)
            item_discounted_price = round(item_total * (1 - discount_percentage / 100), 2)

            products_detail.append({
                "id": product["id"],
                "title": product["title"],
                "price": product.get('price', 0),
                "quantity": quantity,
                "total": item_total,
                "discountPercentage": discount_percentage,
                "discountedTotal": item_discounted_price,
                "thumbnail": product.get("thumbnail", "")
            })

            total_quantity += quantity
            total_price += item_total
            valid_cart_products.append(item) # Füge gültigen Eintrag hinzu
        else:
            print(f"Warnung: Produkt mit ID {product_id} im Warenkorb {cart.get('userId')} nicht in Produktdatenbank gefunden.")

    discounted_total = sum(item["discountedTotal"] for item in products_detail)

    # Aktualisiere den Warenkorb mit den berechneten Werten und Details
    cart["products"] = products_detail # Überschreibt die alte Produktliste mit detaillierten Infos
    cart["total"] = round(total_price, 2)
    cart["discountedTotal"] = round(discounted_total, 2)
    cart["totalProducts"] = len(products_detail)
    cart["totalQuantity"] = total_quantity
    # Wichtig: Stelle sicher, dass die *Originalstruktur* der Produkte für das Speichern erhalten bleibt, falls calculate nur temporär ist.
    # Hier überschreiben wir es absichtlich für die API-Antwort.
    # Wenn du die ursprüngliche Struktur {id, quantity} behalten willst, musst du das anders handhaben.
    # Für dieses Beispiel ist das Überschreiben OK.

    return cart

def get_user_id_from_token(token):
    """Sucht die userId anhand des Tokens."""
    return bearer_tokens.get(token)

# Decorator für Token-basierte Authentifizierung
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
            else:
                return jsonify({"message": "Ungültiges Token-Format (erwartet: Bearer <token>)"}), 400

        if not token:
            return jsonify({"message": "Authentifizierungstoken fehlt im 'Authorization' Header"}), 401

        user_id = get_user_id_from_token(token)
        if user_id is None:
            return jsonify({"message": "Ungültiger oder abgelaufener Token"}), 401 # Oder 403 Forbidden

        # Optional: Benutzerobjekt für einfachen Zugriff in der Route verfügbar machen
        current_user = users_by_id.get(user_id)
        if not current_user:
             # Sollte nicht passieren, wenn Tokens und User synchron sind
             print(f"WARNUNG: Token {token} gehört zu userId {user_id}, aber User nicht gefunden!")
             # Alten Token entfernen, da er ungültig ist
             if token in bearer_tokens:
                 del bearer_tokens[token]
                 save_bearer_tokens()
             return jsonify({"message": "Benutzer zum Token nicht gefunden, bitte neu anmelden."}), 401

        g.user_id = user_id
        g.current_user = current_user # Ganzen User in g speichern

        return f(*args, **kwargs)
    return decorated_function

# ----------------------------------
# Authentifizierung und Benutzerverwaltung

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"message": "Username und Passwort sind erforderlich"}), 400

    username = data['username']
    password = data['password']
    user_data = users_db.get(username)

    if user_data and user_data['password'] == password:
        user_id = user_data['id']
        user_info = {k: v for k, v in user_data.items() if k != 'password'}

        # Neuen Token generieren
        new_token = f"dummy-jwt-token-for-{username}-{uuid.uuid4()}"

        # --- Token Management ---
        # 1. Finde und entferne alle *alten* Tokens dieses Benutzers (optional, aber empfohlen)
        tokens_to_remove = [t for t, uid in bearer_tokens.items() if uid == user_id]
        for t in tokens_to_remove:
            del bearer_tokens[t]
            print(f"Alten Token für User {user_id} entfernt: {t[:10]}...") # Gekürzt loggen

        # 2. Speichere den neuen Token
        bearer_tokens[new_token] = user_id
        save_bearer_tokens()
        # --- Ende Token Management ---

        user_info['token'] = new_token
        print(f"User '{username}' (ID: {user_id}) eingeloggt, Token: {new_token}")

        # Session kann optional bleiben, aber API sollte Token nutzen
        # session['user_id'] = user_id
        # session['username'] = username
        # session.modified = True

        return jsonify(user_info), 200
    else:
        return jsonify({"message": "Ungültige Zugangsdaten"}), 401

# Dieser Endpunkt kann weiterhin Session-basiert sein oder auch Token-basiert
@app.route('/auth/me', methods=['GET'])
@token_required # Umstellung auf Token-basiert für Konsistenz
def get_current_user():
    # user_id und current_user sind jetzt in g verfügbar dank @token_required
    user_info = {k: v for k, v in g.current_user.items() if k != 'password'}
    return jsonify(user_info), 200
    # Alten Session-basierten Code entfernen/auskommentieren:
    # if 'user_id' not in session or 'username' not in session:
    #     return jsonify({"message": "Authentifizierung erforderlich"}), 401
    # username = session['username']
    # user_data = users_db.get(username)
    # if user_data:
    #     user_info = {k: v for k, v in user_data.items() if k != 'password'}
    #     return jsonify(user_info), 200
    # else:
    #     session.clear()
    #     return jsonify({"message": "Dateninkonsistenz: Benutzer existiert nicht. Abmeldung erfolgt."}), 500

# Logout sollte den verwendeten Token invalidieren
@app.route('/auth/logout', methods=['POST'])
@token_required # Token ist nötig, um zu wissen, welcher invalidiert werden soll
def logout():
     auth_header = request.headers.get('Authorization')
     parts = auth_header.split()
     token_to_invalidate = parts[1]

     if token_to_invalidate in bearer_tokens:
         del bearer_tokens[token_to_invalidate]
         save_bearer_tokens()
         print(f"Token für User {g.user_id} invalidiert: {token_to_invalidate[:10]}...")
     else:
         print(f"Warnung: Logout-Versuch mit Token, der nicht (mehr) in bearer_tokens ist: {token_to_invalidate[:10]}...")

     # Session auch löschen, falls sie noch genutzt wird
     session.clear()
     return jsonify({"message": "Erfolgreich abgemeldet"}), 200


@app.route('/users/add', methods=['POST', 'OPTIONS'])
def add_user():
    # (Keine Änderung hier nötig, fügt nur User hinzu)
    if request.method == 'OPTIONS':
        return jsonify({}), 200 # Preflight OK
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
        "password": data['password'], # In Realworld-Apps: Hashen!
        "role": data.get("role", "user"),
        "firstName": data.get("firstName", ""),
        "lastName": data.get("lastName", ""),
        # ... (restliche Felder wie gehabt) ...
        "orders": []
    }
    current_id = next_user_id
    next_user_id += 1
    users_db[username] = new_user
    users_by_id[current_id] = new_user # Auch im ID-Lookup hinzufügen
    try:
        # Speichere die Liste der User-Objekte
        with open(dummy_users_file, "w") as f:
            json.dump(list(users_by_id.values()), f, indent=4)
    except Exception as e:
        print("Fehler beim Speichern der Benutzerdaten:", e)
        # Optional: Rollback?
    new_user_info = {k: v for k, v in new_user.items() if k != 'password'}
    return jsonify(new_user_info), 201

# ----------------------------------
# Produkt-Endpunkte (unverändert)

@app.route('/products', methods=['GET'])
def get_products():
    # Query-Parameter auslesen
    limit = request.args.get('limit', default=30, type=int)
    skip = request.args.get('skip', default=0, type=int)
    category_filter = request.args.get('category', default=None, type=str) # NEU: Kategorie-Filter lesen

    # Produkte laden (wie bisher)
    current_products = products_db # Start mit allen Produkten

    # NEU: Filtern nach Kategorie, falls Parameter angegeben wurde
    if category_filter:
        category_filter_lower = category_filter.lower() # Für case-insensitive Vergleich
        filtered_products = []
        for p in current_products:
            # Prüfen, ob das Produkt eine Kategorie hat und sie übereinstimmt
            product_category = p.get('category')
            if isinstance(product_category, str) and product_category.lower() == category_filter_lower:
                filtered_products.append(p)
        current_products = filtered_products # Überschreibe die Liste mit den gefilterten Ergebnissen
        print(f"Filtere Produkte nach Kategorie: {category_filter}. Gefunden: {len(current_products)}") # Log-Ausgabe

    # Berechne die Gesamtzahl *nach* dem Filtern
    total_filtered_products = len(current_products)

    # Paginierung auf die (ggf. gefilterte) Liste anwenden
    paginated_products = current_products[skip : skip + limit]

    # Antwort zusammenstellen
    response = {
        "products": paginated_products,
        "total": total_filtered_products, # Wichtig: Gesamtzahl der gefilterten Produkte
        "skip": skip,
        "limit": limit
    }
    if category_filter:
        response['filter'] = {'category': category_filter} # Optional: Info über aktiven Filter mitsenden

    return jsonify(response)

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    # Effizienter: Direktes Lookup, wenn products_db ein Dict wäre {id: product}
    product = next((p for p in products_db if p.get("id") == product_id), None)
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
        # Verbesserte Suche (stellt sicher, dass Felder existieren und Strings sind)
        match = False
        if isinstance(p.get('title'), str) and query in p['title'].lower():
            match = True
        elif isinstance(p.get('description'), str) and query in p['description'].lower():
            match = True
        elif isinstance(p.get('tags'), list):
             if any(isinstance(tag, str) and query in tag.lower() for tag in p['tags']):
                 match = True
        # Weitere Felder hinzufügen? (z.B. category)
        # elif isinstance(p.get('category'), str) and query in p['category'].lower():
        #     match = True

        if match:
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
# Warenkorb-Endpunkte: Nutzen UserID aus dem Token

# GET /cart: Holt den Warenkorb des eingeloggten Benutzers
@app.route('/cart', methods=['GET'])
@token_required # Stellt sicher, dass g.user_id gesetzt ist
def get_my_cart():
    user_id = g.user_id
    cart = carts_db.get(user_id)

    if not cart:
        # Wenn kein Warenkorb existiert, erstelle einen leeren für den Benutzer
        print(f"Kein Warenkorb für User {user_id} gefunden. Erstelle neuen.")
        new_cart = {
            "id": uuid.uuid4().hex, # Eine eindeutige ID für den Warenkorb selbst
            "userId": user_id,
            "products": [],  # Format: [{"id": product_id, "quantity": num}, ...]
            "total": 0.0,
            "discountedTotal": 0.0,
            "totalProducts": 0,
            "totalQuantity": 0
            # Kein isDeleted oder deletedOn beim Erstellen
        }
        carts_db[user_id] = new_cart
        save_carts()
        # Wichtig: Berechne auch für den leeren Warenkorb die Totals (wird 0 sein)
        cart_to_return = calculate_cart_totals(new_cart.copy(), products_db) # Kopie verwenden!
        return jsonify(cart_to_return)
    else:
        # Berechne die Details und Totals *vor* dem Zurückgeben
        cart_to_return = calculate_cart_totals(cart.copy(), products_db) # Kopie verwenden!
        return jsonify(cart_to_return)


# PUT /cart: Aktualisiert/Ersetzt den Warenkorb des eingeloggten Benutzers
# PATCH /cart: Aktualisiert Teile des Warenkorbs (z.B. Zusammenführen)
@app.route('/cart', methods=['PUT', 'PATCH'])
@token_required # Stellt sicher, dass g.user_id gesetzt ist
def update_my_cart():
    user_id = g.user_id
    data = request.get_json()

    if not data or 'products' not in data or not isinstance(data['products'], list):
        return jsonify({"message": "'products' (als Liste) ist im Request Body erforderlich"}), 400

    # Hole den existierenden Warenkorb oder erstelle einen neuen, falls nicht vorhanden
    existing_cart = carts_db.get(user_id)
    if not existing_cart:
         existing_cart = {
            "id": uuid.uuid4().hex,
            "userId": user_id,
            "products": [],
            # Initialwerte für Totals etc. sind hier nicht wichtig, werden eh neu berechnet
        }
         carts_db[user_id] = existing_cart # Füge zum In-Memory Dict hinzu

    new_products_input = data['products'] # Format: [{"id": int, "quantity": int}, ...]

    # Prüfe die Eingabeprodukte auf korrektes Format
    valid_new_products = []
    for item in new_products_input:
        if isinstance(item, dict) and isinstance(item.get('id'), int) and isinstance(item.get('quantity'), int) and item['quantity'] >= 0:
             # Quantity 0 bedeutet Entfernen beim Mergen, ok beim Ersetzen
             valid_new_products.append(item)
        else:
             print(f"Warnung: Ungültiger Produkteintrag in Request für User {user_id}: {item}")
             # Optional: Fehler zurückgeben oder Eintrag ignorieren
             # return jsonify({"message": f"Ungültiger Produkteintrag: {item}"}), 400

    if request.method == 'PUT':
        # Ersetzen: Die neuen Produkte sind der gesamte Warenkorbinhalt
        existing_cart['products'] = [p for p in valid_new_products if p['quantity'] > 0] # Nur Produkte mit Menge > 0 behalten
        print(f"Warenkorb für User {user_id} wird ersetzt (PUT).")

    elif request.method == 'PATCH':
        # Zusammenführen (Merge): Standardverhalten für PATCH hier implementieren
        # Gehe davon aus, dass die Liste die *Änderungen* enthält
        print(f"Warenkorb für User {user_id} wird aktualisiert (PATCH/Merge).")
        # Konvertiere existierende Produkte in ein Dict für schnellen Zugriff
        current_products_dict = {prod['id']: prod for prod in existing_cart.get('products', []) if isinstance(prod, dict) and 'id' in prod}

        for item in valid_new_products:
            product_id = item['id']
            quantity = item['quantity']

            if quantity > 0:
                # Produkt hinzufügen oder Menge aktualisieren
                current_products_dict[product_id] = {"id": product_id, "quantity": quantity}
            elif quantity == 0 and product_id in current_products_dict:
                # Produkt entfernen (Menge 0)
                del current_products_dict[product_id]

        # Aktualisiere die Produktliste im Warenkorb
        existing_cart['products'] = list(current_products_dict.values())

    else: # Sollte nicht vorkommen wegen Flask Routing
        return jsonify({"message": "Methode nicht unterstützt"}), 405

    # Neuberechnung der Details und Summen nach der Änderung
    # Wichtig: Hier das Original `existing_cart` übergeben, das in `carts_db` ist!
    updated_cart_calculated = calculate_cart_totals(existing_cart, products_db)

    # Speichern nicht vergessen!
    carts_db[user_id] = updated_cart_calculated # Stelle sicher, dass die berechneten Werte (falls überschrieben) hier landen
    save_carts()

    # Gib den *neu berechneten* Warenkorb zurück
    return jsonify(updated_cart_calculated)


# DELETE /cart: Löscht den Warenkorb des eingeloggten Benutzers
@app.route('/cart', methods=['DELETE'])
@token_required # Stellt sicher, dass g.user_id gesetzt ist
def delete_my_cart():
    user_id = g.user_id

    if user_id in carts_db:
        deleted_cart_data = carts_db.pop(user_id) # Entferne aus dem In-Memory Dict
        save_carts() # Speichere die Änderung (Entfernung)

        # Markiere als gelöscht für die Antwort (optional)
        deleted_cart_data['isDeleted'] = True
        deleted_cart_data['deletedOn'] = datetime.utcnow().isoformat() + "Z" # ISO 8601 Format

        print(f"Warenkorb für User {user_id} gelöscht.")
        return jsonify(deleted_cart_data) # Gib die Daten des gelöschten Warenkorbs zurück
    else:
        print(f"Kein Warenkorb für User {user_id} zum Löschen gefunden.")
        return jsonify({"message": "Warenkorb nicht gefunden"}), 404


# ----------------------------------
# Endpunkte für Admin/Übersicht (weniger Änderungen nötig)

# GET /carts: Holt ALLE Warenkörbe (evtl. Admin-Funktion)
@app.route('/carts', methods=['GET'])
# Optional: @admin_required Decorator hinzufügen
def get_all_carts():
    # Berechne Details für jeden Warenkorb vor der Ausgabe
    all_carts_calculated = []
    for cart in carts_db.values():
        # Wichtig: Kopie verwenden, um Originaldaten nicht zu ändern, falls calculate_cart_totals überschreibt
        all_carts_calculated.append(calculate_cart_totals(cart.copy(), products_db))

    response = {
        "carts": all_carts_calculated,
        "total": len(all_carts_calculated),
        "skip": 0, # Einfache Implementierung gibt immer alles zurück
        "limit": len(all_carts_calculated)
    }
    return jsonify(response)

# GET /carts/user/<user_id>: Holt den Warenkorb eines bestimmten Benutzers (evtl. Admin)
@app.route('/carts/user/<int:target_user_id>', methods=['GET'])
# Optional: @admin_required Decorator hinzufügen
def get_cart_by_user_id(target_user_id):
    # Prüfen, ob der anfragende User Berechtigung hat (hier nicht implementiert)
    # Beispiel: if g.current_user.get('role') != 'admin' and g.user_id != target_user_id: return jsonify({"message": "Forbidden"}), 403

    cart = carts_db.get(target_user_id)

    if cart:
        cart_to_return = calculate_cart_totals(cart.copy(), products_db)
        response = {
            "carts": [cart_to_return], # API erwartet oft eine Liste
            "total": 1,
            "skip": 0,
            "limit": 1
        }
        return jsonify(response)
    else:
        # Gib einen leeren Warenkorb oder 404 zurück? Konsistent mit /cart GET: leeren Warenkorb
         empty_cart_response = {
             "id": None, # Keine ID, da nicht existent
             "userId": target_user_id,
             "products": [],
             "total": 0.0,
             "discountedTotal": 0.0,
             "totalProducts": 0,
             "totalQuantity": 0
         }
         response = {
             "carts": [empty_cart_response],
             "total": 0 # Zeigt an, dass kein *gespeicherter* Cart gefunden wurde
         }
         # Oder besser 404? Hängt von API Design ab.
         # return jsonify({"message": f"Warenkorb für Benutzer {target_user_id} nicht gefunden"}), 404
         return jsonify(response), 200 # Gibt leere Liste zurück, Status 200 OK


# ------ Veraltete/Überflüssige Endpunkte (auskommentiert/entfernt) ------

# POST /carts/add: Ersetzt durch PUT /cart (oder reserviert für Admin)
# @app.route('/carts/add', methods=['POST'])
# def add_cart():
#     # Diese Logik ist jetzt in PUT /cart enthalten oder sollte Admin-only sein
#     # Wenn Admin: Benötigt target_user_id im Body und Prüfung der Admin-Rolle
#     return jsonify({"message": "Endpoint deprecated or for admin use only. Use PUT /cart to create/update your cart."}), 405


# ----------------------------------
# Hauptausführung

if __name__ == '__main__':
    # Stelle sicher, dass die JSON-Dateien existieren oder erstellt werden können
    for filename in [dummy_products_file, dummy_users_file, dummy_tokens_file, dummy_cart_file]:
        if not os.path.exists(filename):
            try:
                # Versuche, eine leere Datei zu erstellen, wenn sie fehlt
                initial_content = "[]" if "products" in filename or "user" in filename or "cart" in filename else "{}"
                with open(filename, "w") as f:
                    f.write(initial_content)
                print(f"Datei {filename} nicht gefunden, leere Datei erstellt.")
            except Exception as e:
                print(f"Konnte fehlende Datei {filename} nicht erstellen: {e}")

    # Lade Daten erneut nach potentiellem Erstellen
    # (In einer echten App würde man das Refactoring sauberer machen)
    # ... (Code zum Laden hier wiederholen oder besser strukturieren) ...

    app.run(host='127.0.0.1', port=5000, debug=True)