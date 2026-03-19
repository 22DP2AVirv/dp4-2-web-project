from __future__ import annotations

import html
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    request,
    send_from_directory,
    session,
    url_for,
    g,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"
HTML_PAGES = {path.name for path in BASE_DIR.glob("*.html")}
USER_ONLY_PAGES = {"user_cab.html"}
ADMIN_ONLY_PAGES = {"admin-panel.html", "pieteikumi-adm.html"}

SERVICE_DESCRIPTION_MAP = {
    "Datortomogrāfija": "Ātra un precīza diagnostika ar augstas izšķirtspējas attēliem. Palīdz noteikt dažādas saslimšanas un kontrolēt ārstēšanas gaitu.",
    "Ģimenes ārsts": "Jūsu veselības ceļvedis - profilakse, diagnoze un ārstēšana vienuviet. Individuāla pieeja un rūpes par visu ģimeni.",
    "Vakcinācija": "Drošība jums un jūsu tuviniekiem! Aizsardzība pret infekcijām ar pierādītu efektivitāti un minimālu diskomfortu.",
}

FALLBACK_SERVICES = [
    ("Datortomogrāfija", SERVICE_DESCRIPTION_MAP["Datortomogrāfija"]),
    ("Ģimenes ārsts", SERVICE_DESCRIPTION_MAP["Ģimenes ārsts"]),
    ("Vakcinācija", SERVICE_DESCRIPTION_MAP["Vakcinācija"]),
]

FALLBACK_PRICES = [
    ("Vienas ķermeņa daļas daudzslāņu CT izmeklējums bez kontrastvielas:", "Datortomogrāfija", 110.00),
    ("Apmeklējums filiālē:", "Ģimenes ārsts", 2.00),
    ("Vakcinācija pret gripu:", "Vakcinācija", 22.50),
]

LEGACY_GENERIC_SERVICE_DESCRIPTIONS = {
    "Izmeklējumi ar modernu aparatūru.",
    "Konsultācijas un regulāras pārbaudes.",
    "Daudzveidīgi vakcinācijas pakalpojumi.",
}

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "dev-secret-key-change-me",
)
app.config["ADMIN_EMAIL"] = os.environ.get(
    "ADMIN_EMAIL",
    "aleksisvirvinskis204@gmail.com",
)
app.config["ADMIN_PASSWORD"] = os.environ.get(
    "ADMIN_PASSWORD",
    "Parole290306",
)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def clean_html_text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", value).strip())


def normalize_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def service_public_meta(service_name: str) -> dict[str, str]:
    normalized_name = normalize_lookup(service_name)

    if "tomograf" in normalized_name or "ct" in normalized_name:
        return {
            "image_path": "/images/datortomografija.webp",
            "detail_page": "lasit-vairak-dat.html",
            "button_label": "Lasīt vairāk",
        }

    if "gimen" in normalized_name or "imenes" in normalized_name or "arst" in normalized_name:
        return {
            "image_path": "/images/arsts.webp",
            "detail_page": "lasit-vairak-gim.html",
            "button_label": "Lasīt vairāk",
        }

    if "vakcin" in normalized_name:
        return {
            "image_path": "/images/vakcinacija.webp",
            "detail_page": "lasit-vairak-vakc.html",
            "button_label": "Lasīt vairāk",
        }

    return {
        "image_path": "/images/medicina.webp",
        "detail_page": "pieteikties.html",
        "button_label": "Pieteikties",
    }


def resolve_service_description(service_name: str, stored_description: str) -> str:
    description = (stored_description or "").strip()
    if not description or description in LEGACY_GENERIC_SERVICE_DESCRIPTIONS:
        return SERVICE_DESCRIPTION_MAP.get(service_name, description)
    return description


def load_catalog_data() -> tuple[list[tuple[str, str]], list[tuple[str, str, float]]]:
    cenas_path = BASE_DIR / "cenas.html"
    if not cenas_path.exists():
        return FALLBACK_SERVICES, FALLBACK_PRICES

    text = cenas_path.read_text(encoding="utf-8")
    sections = re.findall(
        r'<div class="service-list">\s*<h4[^>]*>(.*?)</h4>(.*?)</div>\s*</div>',
        text,
        re.S,
    )

    services: list[tuple[str, str]] = []
    prices: list[tuple[str, str, float]] = []

    for raw_service_name, body in sections:
        service_name = clean_html_text(raw_service_name)
        description = SERVICE_DESCRIPTION_MAP.get(
            service_name,
            f"Kategorijas {service_name} pakalpojumi.",
        )
        services.append((service_name, description))

        items = re.findall(
            r"<strong[^>]*>(.*?)</strong>\s*<span[^>]*>(.*?)</span>",
            body,
            re.S,
        )
        for raw_title, raw_price in items:
            title = clean_html_text(raw_title)
            price_text = clean_html_text(raw_price)
            numeric_price = re.sub(r"[^0-9.]", "", price_text)
            if not numeric_price:
                continue

            prices.append((title, service_name, float(numeric_price)))

    if not services or not prices:
        return FALLBACK_SERVICES, FALLBACK_PRICES

    return services, prices


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


@app.teardown_appcontext
def close_db(_: BaseException | None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    services_seed, prices_seed = load_catalog_data()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            password_updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            procedura TEXT NOT NULL,
            datums TEXT NOT NULL,
            laiks TEXT NOT NULL,
            adrese TEXT NOT NULL,
            comment TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            service_name TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    service_count = connection.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    if service_count == 0:
        timestamp = now_iso()
        connection.executemany(
            """
            INSERT INTO services (service_name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [(name, description, timestamp, timestamp) for name, description in services_seed],
        )

    price_count = connection.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    if price_count == 0:
        timestamp = now_iso()
        connection.executemany(
            """
            INSERT INTO prices (title, service_name, price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (title, service_name, price, timestamp, timestamp)
                for title, service_name, price in prices_seed
            ],
        )

    connection.commit()
    connection.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def public_user_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "surname": row["surname"],
        "phone": row["phone"],
        "email": row["email"],
        "created_at": row["created_at"],
        "password_updated_at": row["password_updated_at"],
    }


def current_user_row() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user_row()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        return view(user, *args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Admin authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index() -> Any:
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/assets/<path:filename>")
def assets(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "assets", filename)


@app.route("/images/<path:filename>")
def images(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "images", filename)


@app.route("/<path:filename>")
def pages(filename: str) -> Any:
    if filename in USER_ONLY_PAGES and current_user_row() is None:
        return redirect(url_for("pages", filename="login.html"))

    if filename in ADMIN_ONLY_PAGES and not session.get("is_admin"):
        return redirect(url_for("pages", filename="admin-login.html"))

    if filename in HTML_PAGES:
        return send_from_directory(BASE_DIR, filename)

    abort(404)


@app.errorhandler(404)
def handle_404(_: Exception) -> Any:
    return send_from_directory(BASE_DIR, "404.html"), 404


@app.post("/api/register")
def api_register() -> Any:
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not all([name, surname, phone, email, password]):
        return jsonify({"error": "All fields are required"}), 400

    db = get_db()
    existing_user = db.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 409

    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO users (name, surname, phone, email, password_hash, created_at, password_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            timestamp,
            timestamp,
        ),
    )
    db.commit()

    user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(
        {
            "message": "Registration successful",
            "user": public_user_dict(user),
        }
    ), 201


@app.post("/api/login")
def api_login() -> Any:
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = get_db().execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user["id"]
    return jsonify(
        {
            "message": "Login successful",
            "user": public_user_dict(user),
        }
    )


@app.post("/api/logout")
def api_logout() -> Any:
    session.pop("user_id", None)
    return jsonify({"message": "Logged out"})


@app.get("/api/me")
@login_required
def api_me(user: sqlite3.Row) -> Any:
    return jsonify(public_user_dict(user))


@app.get("/api/catalog")
def api_catalog() -> Any:
    db = get_db()
    service_rows = db.execute(
        "SELECT * FROM services ORDER BY id ASC"
    ).fetchall()
    price_rows = db.execute(
        "SELECT * FROM prices ORDER BY service_name ASC, id ASC"
    ).fetchall()

    grouped_prices: dict[str, list[dict[str, Any]]] = {}
    for row in price_rows:
        item = row_to_dict(row)
        grouped_prices.setdefault(item["service_name"], []).append(item)

    catalog: list[dict[str, Any]] = []
    used_service_names: set[str] = set()

    for service_row in service_rows:
        service = row_to_dict(service_row)
        service_name = service["service_name"]
        catalog.append(
            {
                "id": service["id"],
                "service_name": service_name,
                "description": resolve_service_description(service_name, service["description"]),
                "public_meta": service_public_meta(service_name),
                "items": grouped_prices.get(service_name, []),
            }
        )
        used_service_names.add(service_name)

    for service_name, items in grouped_prices.items():
        if service_name in used_service_names:
            continue

        catalog.append(
            {
                "id": None,
                "service_name": service_name,
                "description": resolve_service_description(service_name, ""),
                "public_meta": service_public_meta(service_name),
                "items": items,
            }
        )

    return jsonify(catalog)


@app.post("/api/update-password")
@login_required
def api_update_password(user: sqlite3.Row) -> Any:
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password", ""))

    if not password:
        return jsonify({"error": "Password is required"}), 400

    timestamp = now_iso()
    db = get_db()
    db.execute(
        """
        UPDATE users
        SET password_hash = ?, password_updated_at = ?
        WHERE id = ?
        """,
        (generate_password_hash(password), timestamp, user["id"]),
    )
    db.commit()

    return jsonify({"message": "Password updated successfully"})


@app.post("/api/appointments")
def api_create_appointment() -> Any:
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedura = str(payload.get("procedura", "")).strip()
    datums = str(payload.get("datums", "")).strip()
    laiks = str(payload.get("laiks", "")).strip()
    adrese = str(payload.get("adrese", "")).strip()
    comment = str(payload.get("comment", "")).strip()

    if not all([name, surname, phone, email, procedura, datums, laiks, adrese]):
        return jsonify({"error": "All appointment fields are required"}), 400

    user = current_user_row()
    timestamp = now_iso()
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO appointments (
            user_id, name, surname, phone, email, procedura, datums, laiks, adrese, comment, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"] if user else None,
            name,
            surname,
            phone,
            email,
            procedura,
            datums,
            laiks,
            adrese,
            comment,
            timestamp,
            timestamp,
        ),
    )
    db.commit()

    appointment = db.execute(
        "SELECT * FROM appointments WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify({"message": "Appointment created", "appointment": row_to_dict(appointment)}), 201


@app.post("/api/admin/login")
def api_admin_login() -> Any:
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))

    if (
        email != app.config["ADMIN_EMAIL"]
        or password != app.config["ADMIN_PASSWORD"]
    ):
        return jsonify({"error": "Invalid admin credentials"}), 401

    session["is_admin"] = True
    return jsonify({"message": "Admin login successful"})


@app.post("/api/admin/logout")
@admin_required
def api_admin_logout() -> Any:
    session.pop("is_admin", None)
    return jsonify({"message": "Admin logged out"})


@app.get("/api/admin/users")
@admin_required
def api_admin_users() -> Any:
    rows = get_db().execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([public_user_dict(row) for row in rows])


@app.post("/api/admin/users")
@admin_required
def api_admin_create_user() -> Any:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not all([name, email, password]):
        return jsonify({"error": "Name, email and password are required"}), 400

    db = get_db()
    existing_user = db.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 409

    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO users (name, surname, phone, email, password_hash, created_at, password_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            timestamp,
            timestamp,
        ),
    )
    db.commit()
    user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(public_user_dict(user)), 201


@app.delete("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_delete_user(user_id: int) -> Any:
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"message": "User deleted"})


@app.put("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_update_user(user_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not all([name, email]):
        return jsonify({"error": "Name and email are required"}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404

    existing_user = db.execute(
        "SELECT id FROM users WHERE email = ? AND id != ?",
        (email, user_id),
    ).fetchone()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 409

    timestamp = now_iso()
    password_hash = user["password_hash"]
    if password:
        password_hash = generate_password_hash(password)

    db.execute(
        """
        UPDATE users
        SET name = ?, surname = ?, phone = ?, email = ?, password_hash = ?, password_updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            surname,
            phone,
            email,
            password_hash,
            timestamp,
            user_id,
        ),
    )
    db.commit()

    updated_user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return jsonify(public_user_dict(updated_user))


@app.get("/api/admin/services")
@admin_required
def api_admin_services() -> Any:
    rows = get_db().execute(
        "SELECT * FROM services ORDER BY id ASC"
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/admin/services")
@admin_required
def api_admin_create_service() -> Any:
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get("serviceName", "")).strip()
    description = str(payload.get("description", "")).strip()

    if not all([service_name, description]):
        return jsonify({"error": "Service name and description are required"}), 400

    timestamp = now_iso()
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO services (service_name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (service_name, description, timestamp, timestamp),
    )
    db.commit()
    row = db.execute("SELECT * FROM services WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.delete("/api/admin/services/<int:service_id>")
@admin_required
def api_admin_delete_service(service_id: int) -> Any:
    db = get_db()
    service = db.execute(
        "SELECT service_name FROM services WHERE id = ?",
        (service_id,),
    ).fetchone()
    if service is None:
        return jsonify({"error": "Service not found"}), 404

    db.execute(
        "DELETE FROM prices WHERE service_name = ?",
        (service["service_name"],),
    )
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    return jsonify({"message": "Service deleted"})


@app.put("/api/admin/services/<int:service_id>")
@admin_required
def api_admin_update_service(service_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    service_name = str(payload.get("serviceName", "")).strip()
    description = str(payload.get("description", "")).strip()

    if not all([service_name, description]):
        return jsonify({"error": "Service name and description are required"}), 400

    db = get_db()
    service = db.execute(
        "SELECT id, service_name FROM services WHERE id = ?",
        (service_id,),
    ).fetchone()
    if service is None:
        return jsonify({"error": "Service not found"}), 404

    db.execute(
        """
        UPDATE services
        SET service_name = ?, description = ?, updated_at = ?
        WHERE id = ?
        """,
        (service_name, description, now_iso(), service_id),
    )
    db.execute(
        """
        UPDATE prices
        SET service_name = ?, updated_at = ?
        WHERE service_name = ?
        """,
        (service_name, now_iso(), service["service_name"]),
    )
    db.commit()

    updated_service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return jsonify(row_to_dict(updated_service))


@app.get("/api/admin/prices")
@admin_required
def api_admin_prices() -> Any:
    rows = get_db().execute(
        "SELECT * FROM prices ORDER BY id ASC"
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/admin/prices")
@admin_required
def api_admin_create_price() -> Any:
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    service_name = str(payload.get("service", "")).strip()
    raw_price = payload.get("price")

    if not all([title, service_name]) or raw_price in (None, ""):
        return jsonify({"error": "Title, service and price are required"}), 400

    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a number"}), 400

    timestamp = now_iso()
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO prices (title, service_name, price, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, service_name, price, timestamp, timestamp),
    )
    db.commit()
    row = db.execute("SELECT * FROM prices WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.delete("/api/admin/prices/<int:price_id>")
@admin_required
def api_admin_delete_price(price_id: int) -> Any:
    db = get_db()
    db.execute("DELETE FROM prices WHERE id = ?", (price_id,))
    db.commit()
    return jsonify({"message": "Price deleted"})


@app.put("/api/admin/prices/<int:price_id>")
@admin_required
def api_admin_update_price(price_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    service_name = str(payload.get("service", "")).strip()
    raw_price = payload.get("price")

    if not all([title, service_name]) or raw_price in (None, ""):
        return jsonify({"error": "Title, service and price are required"}), 400

    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a number"}), 400

    db = get_db()
    existing_price = db.execute("SELECT id FROM prices WHERE id = ?", (price_id,)).fetchone()
    if existing_price is None:
        return jsonify({"error": "Price not found"}), 404

    db.execute(
        """
        UPDATE prices
        SET title = ?, service_name = ?, price = ?, updated_at = ?
        WHERE id = ?
        """,
        (title, service_name, price, now_iso(), price_id),
    )
    db.commit()

    updated_price = db.execute("SELECT * FROM prices WHERE id = ?", (price_id,)).fetchone()
    return jsonify(row_to_dict(updated_price))


@app.get("/api/admin/appointments")
@admin_required
def api_admin_appointments() -> Any:
    rows = get_db().execute(
        "SELECT * FROM appointments ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.put("/api/admin/appointments/<int:appointment_id>")
@admin_required
def api_admin_update_appointment(appointment_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedura = str(payload.get("procedura", "")).strip()
    datums = str(payload.get("datums", "")).strip()
    laiks = str(payload.get("laiks", "")).strip()
    adrese = str(payload.get("adrese", "")).strip()
    comment = str(payload.get("comment", "")).strip()

    if not all([name, surname, phone, email, procedura, datums, laiks, adrese]):
        return jsonify({"error": "All appointment fields are required"}), 400

    db = get_db()
    appointment = db.execute(
        "SELECT id FROM appointments WHERE id = ?",
        (appointment_id,),
    ).fetchone()
    if appointment is None:
        return jsonify({"error": "Appointment not found"}), 404

    db.execute(
        """
        UPDATE appointments
        SET name = ?, surname = ?, phone = ?, email = ?, procedura = ?, datums = ?, laiks = ?, adrese = ?, comment = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            surname,
            phone,
            email,
            procedura,
            datums,
            laiks,
            adrese,
            comment,
            now_iso(),
            appointment_id,
        ),
    )
    db.commit()

    updated_appointment = db.execute(
        "SELECT * FROM appointments WHERE id = ?",
        (appointment_id,),
    ).fetchone()
    return jsonify(row_to_dict(updated_appointment))


@app.delete("/api/admin/appointments/<int:appointment_id>")
@admin_required
def api_admin_delete_appointment(appointment_id: int) -> Any:
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    db.commit()
    return jsonify({"message": "Appointment deleted"})


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
