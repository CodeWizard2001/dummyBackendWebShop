 WebShopDummy Backend

Ein einfaches Flask-basiertes Webshop-Backend mit Benutzerverwaltung, Warenkorb, Authentifizierung und Produktendpunkten.

---

## 🚀 Installation (lokal)

### Voraussetzungen

- Python 3.10+
- `pip`

### Installation & Start

```bash
python -m pip install -r requirements.txt
python WebShopDummy.py
```

Das Backend läuft dann unter:

➡️ http://localhost:5000

---

## 🐳 Mit Docker

### 1. Image bauen

```bash
docker build -t webshop-backend .
```

### 2. Container starten

```bash
docker run -p 5000:5000 webshop-backend
```

Das Backend ist nun erreichbar unter:

➡️ http://localhost:5000

---
