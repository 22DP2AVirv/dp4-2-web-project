from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import unicodedata
import calendar
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

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
ACCOUNT_ONLY_PAGES = {"user_cab.html", "pieteikties.html"}
PATIENT_ONLY_PAGES = {"pieteikties.html"}
ADMIN_ONLY_PAGES = {
    "admin-panel.html",
    "admin-users.html",
    "admin-doctors.html",
    "admin-services.html",
    "admin-prices.html",
    "admin-about.html",
    "admin-messages.html",
    "pieteikumi-adm.html",
}
DOCTOR_PROCEDURES = {"datortomografija", "gimenesArsts", "vakcinacija"}
DOCTOR_APPOINTMENT_MESSAGE = "Ārsta kontam procedūru pieteikšana nav pieejama."

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

FALLBACK_ABOUT_PAGE_TITLE = "Par mums"
FALLBACK_ABOUT_CONTENT = [
    {
        "entry_type": "page_title",
        "title": FALLBACK_ABOUT_PAGE_TITLE,
        "content": "",
        "content_format": "text",
        "image_path": "",
        "image_alt": "",
        "sort_order": 0,
    },
    {
        "entry_type": "section",
        "title": "Par uzņēmumu",
        "content": (
            "\"Health and Care\" ir mūsdienīgs medicīnas centrs Rīgā, kas kopš 2010. gada "
            "piedāvā kvalitatīvus veselības aprūpes pakalpojumus. Mūsu mērķis ir nodrošināt "
            "profesionālu, drošu un pieejamu medicīnas aprūpi ikvienam pacientam. "
            "Mēs pastāvīgi ieguldām jaunākajās tehnoloģijās, lai uzlabotu diagnostiku, "
            "ārstēšanu un pacientu pieredzi."
        ),
        "content_format": "paragraph",
        "image_path": "/images/aboutUS.webp",
        "image_alt": "Par uzņēmumu",
        "sort_order": 1,
    },
    {
        "entry_type": "section",
        "title": "Mūsu misija",
        "content": (
            "Uzlabot cilvēku dzīves kvalitāti, nodrošinot uzticamu un efektīvu veselības aprūpi. "
            "Mēs strādājam ar sirdi un zināšanām, lai sniegtu labāko iespējamo palīdzību katram. "
            "Mūsu misija ir balstīta uz cieņpilnu attieksmi, zinātnē balstītiem lēmumiem un "
            "ilgtermiņa attiecību veidošanu ar pacientiem."
        ),
        "content_format": "paragraph",
        "image_path": "/images/misija.webp",
        "image_alt": "Mūsu misija",
        "sort_order": 2,
    },
    {
        "entry_type": "section",
        "title": "Mūsu vērtības",
        "content": "\n".join(
            [
                "Pacienta cieņa un individuāla pieeja",
                "Augsta profesionalitāte",
                "Inovācijas un attīstība",
                "Sadarbība un uzticība",
            ]
        ),
        "content_format": "list",
        "image_path": "/images/values.webp",
        "image_alt": "Mūsu vērtības",
        "sort_order": 3,
    },
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
app.config["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "").strip()
app.config["OPENAI_CHAT_MODEL"] = os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"

CLINIC_NAME = "Health and Care"
CLINIC_PHONE = "+371 22351340"
CLINIC_EMAIL = "info@healthandcare.lv"
CLINIC_MAIN_ADDRESS = "Lidoņu iela 13, Rīga, LV-1055"
CLINIC_BRANCHES = [
    "Rīga, Brīvības iela",
    "Jelgava, Zemgales prospekts",
    "Liepāja, Rožu iela",
]
CHATBOT_OFF_TOPIC_MESSAGE = (
    "Varu palīdzēt tikai ar jautājumiem par klīniku Health and Care, tās pakalpojumiem, "
    "ārstiem, cenām, filiālēm, darba laiku un pieraksta kārtību."
)
CHATBOT_FALLBACK_MESSAGE = (
    "Varu palīdzēt ar darba laiku, kontaktiem, pakalpojumiem, cenām, ārstiem, "
    "reģistrāciju un pieraksta noteikumiem. Uzraksti, kas tieši interesē."
)
CHATBOT_GREETINGS = {
    "sveiki",
    "labdien",
    "hey",
    "hi",
    "hello",
    "čau",
    "cau",
}
CHATBOT_SERVICE_LABELS = {
    "datortomografija": "Datortomogrāfija",
    "gimenesArsts": "Ģimenes ārsts",
    "vakcinacija": "Vakcinācija",
}
CHATBOT_SERVICE_ALIASES = {
    "datortomografija": ("datortomograf", "tomograf", "ct"),
    "gimenesArsts": ("gimenes arst", "gimenesarst", "arsts", "arsta konsult", "konsultacij"),
    "vakcinacija": ("vakcin", "pot"),
}
CHATBOT_CLINIC_KEYWORDS = (
    "klin",
    "health and care",
    "pakalpoj",
    "procedur",
    "cena",
    "cen",
    "maks",
    "pierakst",
    "pieteikt",
    "darba laik",
    "filial",
    "adrese",
    "kontakti",
    "talrun",
    "epast",
    "arst",
    "vakcin",
    "datortomograf",
    "gimenes",
    "profils",
    "parole",
    "registr",
    "lietotaj",
    "kabinet",
)


def normalize_chatbot_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_diacritics = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9\s+]", " ", without_diacritics)


def format_chatbot_price(value: float | int | str) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return f"{value} EUR"
    return f"{amount:.2f}".replace(".", ",") + " EUR"


def detect_chatbot_service_key(message: str) -> str | None:
    normalized_message = normalize_chatbot_text(message)
    for service_key, aliases in CHATBOT_SERVICE_ALIASES.items():
        if any(alias in normalized_message for alias in aliases):
            return service_key
    return None


def is_chatbot_greeting(message: str) -> bool:
    normalized_message = normalize_chatbot_text(message).strip()
    return normalized_message in CHATBOT_GREETINGS


def is_clinic_related_message(message: str) -> bool:
    normalized_message = normalize_chatbot_text(message)
    if not normalized_message.strip():
        return False
    if is_chatbot_greeting(message):
        return True
    return any(keyword in normalized_message for keyword in CHATBOT_CLINIC_KEYWORDS)


def fetch_chatbot_doctors(service_key: str | None = None) -> list[sqlite3.Row]:
    db = get_db()
    if service_key:
        return db.execute(
            """
            SELECT id, name, surname, procedure
            FROM doctors
            WHERE procedure = ?
            ORDER BY surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
            """,
            (service_key,),
        ).fetchall()

    return db.execute(
        """
        SELECT id, name, surname, procedure
        FROM doctors
        ORDER BY procedure ASC, surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
        """
    ).fetchall()


def fetch_chatbot_prices(service_label: str | None = None) -> list[sqlite3.Row]:
    db = get_db()
    if service_label:
        return db.execute(
            """
            SELECT title, service_name, price
            FROM prices
            WHERE service_name = ?
            ORDER BY id ASC
            """,
            (service_label,),
        ).fetchall()

    return db.execute(
        """
        SELECT title, service_name, price
        FROM prices
        ORDER BY service_name ASC, id ASC
        """
    ).fetchall()


def build_doctor_listing_response(service_key: str | None) -> str:
    if service_key:
        doctors = fetch_chatbot_doctors(service_key)
        service_label = CHATBOT_SERVICE_LABELS[service_key]
        if not doctors:
            return f"Šobrīd sistēmā vēl nav pievienotu ārstu procedūrai \"{service_label}\"."

        names = ", ".join(
            doctor_display_name(row["name"], row["surname"])
            for row in doctors
        )
        return f"Procedūrai \"{service_label}\" šobrīd pieejami šādi ārsti: {names}."

    grouped: dict[str, list[str]] = {}
    for doctor in fetch_chatbot_doctors():
        grouped.setdefault(doctor["procedure"], []).append(
            doctor_display_name(doctor["name"], doctor["surname"])
        )

    if not grouped:
        return "Šobrīd sistēmā vēl nav pievienotu ārstu saraksta."

    parts = []
    for service_key_item, service_label in CHATBOT_SERVICE_LABELS.items():
        doctors = grouped.get(service_key_item, [])
        if doctors:
            parts.append(f"{service_label}: {', '.join(doctors)}")

    if not parts:
        return "Šobrīd sistēmā vēl nav pieejamas ārstu specializācijas."

    return "Šobrīd klīnikā pieejamie ārsti ir: " + " | ".join(parts) + "."


def build_price_response(service_key: str | None) -> str:
    if service_key:
        service_label = CHATBOT_SERVICE_LABELS[service_key]
        prices = fetch_chatbot_prices(service_label)
        if not prices:
            return f"Šobrīd man nav cenu saraksta procedūrai \"{service_label}\"."

        lines = [
            f"{row['title']} {format_chatbot_price(row['price'])}"
            for row in prices
        ]
        return f"Procedūras \"{service_label}\" cenas: " + " | ".join(lines) + "."

    grouped: dict[str, list[str]] = {}
    for row in fetch_chatbot_prices():
        grouped.setdefault(row["service_name"], []).append(
            f"{row['title']} {format_chatbot_price(row['price'])}"
        )

    if not grouped:
        return "Šobrīd cenu saraksts nav pieejams."

    preview_parts = []
    for service_label in CHATBOT_SERVICE_LABELS.values():
        service_prices = grouped.get(service_label, [])
        if service_prices:
            preview_parts.append(f"{service_label}: {service_prices[0]}")

    if not preview_parts:
        return "Šobrīd cenu saraksts nav pieejams."

    return (
        "Pieejamās cenas pēc kategorijām: "
        + " | ".join(preview_parts)
        + ". Ja vēlies, vari pajautāt arī par konkrētu procedūru."
    )


def build_services_response() -> str:
    services = get_db().execute(
        """
        SELECT service_name, description
        FROM services
        ORDER BY id ASC
        """
    ).fetchall()

    if not services:
        return "Šobrīd pakalpojumu saraksts nav pieejams."

    return "Klīnikā pieejamie pakalpojumi: " + " | ".join(
        f"{row['service_name']}: {resolve_service_description(row['service_name'], row['description'])}"
        for row in services
    ) + "."


def build_appointment_rules_response() -> str:
    return (
        "Uz procedūru var pierakstīties tikai reģistrēts lietotājs. "
        "Ārsta konts pierakstus veidot nevar. "
        "Pieraksts iespējams līdz 3 mēnešiem uz priekšu, laikos ar 15 minūšu soli, "
        "un katrai procedūrai vienam lietotājam vienlaikus var būt tikai viens aktīvs pieteikums. "
        "Izvēloties procedūru, jāizvēlas arī tai atbilstošs ārsts."
    )


def build_profile_help_response() -> str:
    return (
        "Lietotāja kabinetā vari apskatīt un labot profila datus, nomainīt paroli, "
        "apskatīt savus pieteikumus un atcelt pieteikumu. "
        "Ārsta kabinetā ir pieejams profils, paroles maiņa un sadaļa \"Mani pieraksti\"."
    )


def build_contact_response() -> str:
    return (
        f"Klīnikas {CLINIC_NAME} galvenie kontakti: tālrunis {CLINIC_PHONE}, "
        f"e-pasts {CLINIC_EMAIL}, galvenā adrese {CLINIC_MAIN_ADDRESS}. "
        "Pieejamās filiāles: " + ", ".join(CLINIC_BRANCHES) + "."
    )


def build_working_hours_response() -> str:
    return (
        "Darba laiks ir šāds: pirmdiena līdz piektdiena 9:00-21:00, "
        "sestdiena 10:00-20:00, svētdiena slēgts."
    )


def build_local_chatbot_response(message: str) -> tuple[str, bool]:
    normalized_message = normalize_chatbot_text(message)
    service_key = detect_chatbot_service_key(message)

    if is_chatbot_greeting(message):
        return (
            "Sveiki! Esmu klīnikas Health and Care asistents. "
            "Varu palīdzēt ar jautājumiem par pakalpojumiem, cenām, ārstiem, darba laiku, "
            "filiālēm un pieraksta kārtību.",
            True,
        )

    if any(keyword in normalized_message for keyword in ("darba laik", "strada", "atverts", "atver")):
        return build_working_hours_response(), True

    if any(keyword in normalized_message for keyword in ("kontakti", "talrun", "epast", "adrese", "atrod", "filial", "kur jus atrodat")):
        return build_contact_response(), True

    if any(keyword in normalized_message for keyword in ("cena", "cen", "maks", "izmaks", "eur")):
        return build_price_response(service_key), True

    if any(keyword in normalized_message for keyword in ("pakalpoj", "procedur", "ko jus piedavajat", "ko jus piedavat")):
        return build_services_response(), True

    if any(keyword in normalized_message for keyword in ("arst", "specialist", "dakter")):
        return build_doctor_listing_response(service_key), True

    if any(keyword in normalized_message for keyword in ("pierakst", "pieteikt", "rezerv", "vizit")):
        return build_appointment_rules_response(), True

    if any(keyword in normalized_message for keyword in ("profils", "parole", "kabinet", "mani pieteikumi", "mani pieraksti")):
        return build_profile_help_response(), True

    if any(keyword in normalized_message for keyword in ("registr", "ieiet", "konts", "lietotaj", "arsta kont")):
        return (
            "Lietotājs var reģistrēties un ieiet savā kontā, lai pieteiktos procedūrām. "
            "Ārsts var ieiet savā ārsta kontā, kur redz savus pierakstus, bet ārsta konts pats pierakstus neveido.",
            True,
        )

    return CHATBOT_FALLBACK_MESSAGE, False


def build_clinic_chatbot_context() -> str:
    services = get_db().execute(
        """
        SELECT service_name, description
        FROM services
        ORDER BY id ASC
        """
    ).fetchall()
    prices = fetch_chatbot_prices()
    doctors = fetch_chatbot_doctors()

    service_lines = [
        f"- {row['service_name']}: {resolve_service_description(row['service_name'], row['description'])}"
        for row in services
    ]
    price_lines = [
        f"- {row['service_name']}: {row['title']} {format_chatbot_price(row['price'])}"
        for row in prices
    ]
    doctor_lines = [
        f"- {CHATBOT_SERVICE_LABELS.get(row['procedure'], row['procedure'])}: {doctor_display_name(row['name'], row['surname'])}"
        for row in doctors
    ]

    return "\n".join(
        [
            f"Klīnika: {CLINIC_NAME}",
            f"Tālrunis: {CLINIC_PHONE}",
            f"E-pasts: {CLINIC_EMAIL}",
            f"Galvenā adrese: {CLINIC_MAIN_ADDRESS}",
            "Filiāles: " + ", ".join(CLINIC_BRANCHES),
            "Darba laiks: pirmdiena-piektdiena 9:00-21:00, sestdiena 10:00-20:00, svētdiena slēgts.",
            "Pieraksta noteikumi: tikai reģistrēts lietotājs var pieteikties procedūrām; ārsta konts pierakstus neveido; pieraksts iespējams līdz 3 mēnešiem uz priekšu; pieejami tikai 15 minūšu laika sloti; vienam lietotājam vienlaikus var būt tikai viens aktīvs pieteikums katrai procedūrai; izvēloties procedūru, jāizvēlas arī tai atbilstošs ārsts.",
            "Pieejamie pakalpojumi:",
            *service_lines,
            "Cenas:",
            *price_lines,
            "Ārsti:",
            *doctor_lines,
        ]
    )


def extract_openai_response_text(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue

        for content_item in item.get("content", []):
            if not isinstance(content_item, dict):
                continue

            if content_item.get("type") not in {"output_text", "text"}:
                continue

            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                texts.append(text_value.strip())
                continue

            if isinstance(text_value, dict):
                nested_value = text_value.get("value")
                if isinstance(nested_value, str) and nested_value.strip():
                    texts.append(nested_value.strip())

    return "\n".join(texts).strip()


def call_openai_clinic_chatbot(message: str, history: list[dict[str, Any]]) -> str | None:
    api_key = app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    developer_prompt = (
        "Tu esi klīnikas Health and Care mājaslapas asistents. "
        "Atbildi tikai latviešu valodā un tikai par šo klīniku, tās pakalpojumiem, cenām, ārstiem, "
        "filiālēm, darba laiku, profila/pieraksta plūsmu un vietnes lietošanu. "
        "Ja jautājums nav par klīniku vai kontekstā nav atbildes, pieklājīgi atsaki un paskaidro, "
        "ka vari palīdzēt tikai ar klīnikas tēmas jautājumiem. "
        "Neizdomā faktus, balsties tikai uz tālāk doto kontekstu.\n\n"
        + build_clinic_chatbot_context()
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "developer",
            "content": developer_prompt,
        }
    ]

    for item in history[-8:]:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue

        messages.append(
            {
                "role": role,
                "content": content[:1000],
            }
        )

    messages.append(
        {
            "role": "user",
            "content": message[:1200],
        }
    )

    request_payload = {
        "model": app.config["OPENAI_CHAT_MODEL"],
        "input": messages,
        "temperature": 0.2,
    }

    request_data = json.dumps(request_payload).encode("utf-8")
    request_object = urllib_request.Request(
        "https://api.openai.com/v1/responses",
        data=request_data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request_object, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError:
        return None
    except urllib_error.URLError:
        return None
    except TimeoutError:
        return None

    reply = extract_openai_response_text(payload)
    return reply or None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def add_months(source_date: date, months: int) -> date:
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def get_working_hours_for_date(target_date: date) -> tuple[int, int] | None:
    weekday = target_date.weekday()
    if weekday <= 4:
        return (9 * 60, 21 * 60)
    if weekday == 5:
        return (10 * 60, 20 * 60)
    return None


def validate_appointment_schedule(datums: str, laiks: str) -> str | None:
    try:
        appointment_date = datetime.strptime(datums, "%Y-%m-%d").date()
    except ValueError:
        return "Lūdzu izvēlieties korektu datumu."

    try:
        appointment_time = datetime.strptime(laiks, "%H:%M").time()
    except ValueError:
        return "Lūdzu izvēlieties korektu laiku."

    today = date.today()
    max_date = add_months(today, 3)

    if appointment_date < today or appointment_date > max_date:
        return "Pieteikties var tikai no šodienas līdz 3 mēnešiem uz priekšu."

    working_hours = get_working_hours_for_date(appointment_date)
    if working_hours is None:
        return "Svētdienā medicīnas centrs ir slēgts."

    if appointment_time.minute not in {0, 15, 30, 45}:
        return "Lūdzu izvēlieties laiku ar 15 minūšu soli: 00, 15, 30 vai 45."

    appointment_minutes = appointment_time.hour * 60 + appointment_time.minute
    opening_minutes, closing_minutes = working_hours
    if appointment_minutes < opening_minutes or appointment_minutes > closing_minutes:
        if appointment_date.weekday() <= 4:
            return "Darba dienās var pieteikties tikai laikā no 9:00 līdz 21:00."
        return "Sestdienās var pieteikties tikai laikā no 10:00 līdz 20:00."

    return None


APPOINTMENT_DUPLICATE_MESSAGE = (
    "Uz šo procedūru Jums jau ir aktīvs pieteikums. "
    "Vienlaikus var būt tikai viens pieteikums katrai procedūrai."
)


def appointment_owner_column(role: str) -> str:
    if role == "doctor":
        return "doctor_id"
    return "user_id"


def find_active_procedure_appointment(
    owner_role: str,
    owner_id: int | None,
    procedura: str,
    *,
    exclude_appointment_id: int | None = None,
) -> sqlite3.Row | None:
    if owner_id is None or not procedura:
        return None

    owner_column = appointment_owner_column(owner_role)
    current_moment = datetime.now()
    today_value = current_moment.strftime("%Y-%m-%d")
    time_value = current_moment.strftime("%H:%M")

    query = f"""
        SELECT id, user_id, doctor_id, procedura, datums, laiks
        FROM appointments
        WHERE {owner_column} = ?
          AND procedura = ?
          AND (
              datums > ?
              OR (datums = ? AND laiks >= ?)
          )
    """
    params: list[Any] = [owner_id, procedura, today_value, today_value, time_value]

    if exclude_appointment_id is not None:
        query += " AND id != ?"
        params.append(exclude_appointment_id)

    query += " ORDER BY datums ASC, laiks ASC LIMIT 1"
    return get_db().execute(query, params).fetchone()


def is_valid_doctor_procedure(procedure: str) -> bool:
    return procedure in DOCTOR_PROCEDURES


def doctor_display_name(name: str | None, surname: str | None) -> str:
    return " ".join(part for part in [name or "", surname or ""] if part).strip()


def appointment_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    if "doctor_name" in data or "doctor_surname" in data:
        data["doctor_full_name"] = doctor_display_name(
            data.get("doctor_name"),
            data.get("doctor_surname"),
        )
    return data


def validate_appointment_doctor(doctor_id: Any, procedura: str) -> sqlite3.Row | None:
    if doctor_id in (None, ""):
        return None

    try:
        doctor_identifier = int(doctor_id)
    except (TypeError, ValueError):
        return None

    return get_db().execute(
        """
        SELECT * FROM doctors
        WHERE id = ? AND procedure = ?
        """,
        (doctor_identifier, procedura),
    ).fetchone()


def public_doctor_option_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "surname": row["surname"],
        "procedure": row["procedure"],
        "full_name": doctor_display_name(row["name"], row["surname"]),
    }


def public_user_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "surname": row["surname"],
        "phone": row["phone"],
        "email": row["email"],
        "created_at": row["created_at"],
        "password_updated_at": row["password_updated_at"],
        "role": "user",
        "procedure": None,
        "can_book_appointments": True,
    }


def public_doctor_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "surname": row["surname"],
        "phone": row["phone"],
        "email": row["email"],
        "created_at": row["created_at"],
        "password_updated_at": row["password_updated_at"],
        "role": "doctor",
        "procedure": row["procedure"],
        "can_book_appointments": False,
    }


def current_user_row() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def current_doctor_row() -> sqlite3.Row | None:
    doctor_id = session.get("doctor_id")
    if not doctor_id:
        return None
    return get_db().execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()


def current_account() -> dict[str, Any] | None:
    user = current_user_row()
    if user is not None:
        return {
            "role": "user",
            **row_to_dict(user),
        }

    doctor = current_doctor_row()
    if doctor is not None:
        return {
            "role": "doctor",
            **row_to_dict(doctor),
        }

    return None


def public_account_dict(account: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    if account["role"] == "doctor":
        return public_doctor_dict(account)
    return public_user_dict(account)


def clear_account_session() -> None:
    session.pop("user_id", None)
    session.pop("doctor_id", None)


def user_email_exists(
    email: str,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    db = get_db()

    user_query = "SELECT id FROM users WHERE email = ?"
    user_params: list[Any] = [email]
    if exclude_user_id is not None:
        user_query += " AND id != ?"
        user_params.append(exclude_user_id)

    existing_user = db.execute(user_query, user_params).fetchone()
    return existing_user is not None


def doctor_email_exists(
    email: str,
    *,
    exclude_doctor_id: int | None = None,
) -> bool:
    db = get_db()

    doctor_query = "SELECT id FROM doctors WHERE email = ?"
    doctor_params: list[Any] = [email]
    if exclude_doctor_id is not None:
        doctor_query += " AND id != ?"
        doctor_params.append(exclude_doctor_id)

    existing_doctor = db.execute(doctor_query, doctor_params).fetchone()
    return existing_doctor is not None


def clean_html_text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", value).strip())


def normalize_public_asset_path(value: str) -> str:
    path = (value or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/")):
        return path
    return "/" + path.lstrip("./")


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


def load_about_data() -> list[dict[str, Any]]:
    about_path = BASE_DIR / "parmums.html"
    if not about_path.exists():
        return FALLBACK_ABOUT_CONTENT

    text = about_path.read_text(encoding="utf-8")
    sections = re.findall(
        r'<section[^>]*class="[^"]*parmumsContent[^"]*"[^>]*>(.*?)</section>',
        text,
        re.S,
    )

    page_title_match = re.search(
        r'<h1[^>]*class="[^"]*parmumsTitle[^"]*"[^>]*>(.*?)</h1>',
        text,
        re.S,
    )
    page_title = clean_html_text(page_title_match.group(1)) if page_title_match else FALLBACK_ABOUT_PAGE_TITLE

    content_rows: list[dict[str, Any]] = [
        {
            "entry_type": "page_title",
            "title": page_title or FALLBACK_ABOUT_PAGE_TITLE,
            "content": "",
            "content_format": "text",
            "image_path": "",
            "image_alt": "",
            "sort_order": 0,
        }
    ]

    for index, section_html in enumerate(sections, start=1):
        title_match = re.search(r"<h2[^>]*>(.*?)</h2>", section_html, re.S)
        title = clean_html_text(title_match.group(1)) if title_match else f"Sadaļa {index}"

        image_match = re.search(
            r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
            section_html,
            re.S,
        )
        image_path = normalize_public_asset_path(image_match.group(1)) if image_match else ""
        image_alt = clean_html_text(image_match.group(2)) if image_match else title

        list_items = re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.S)
        if list_items:
            content = "\n".join(clean_html_text(item) for item in list_items if clean_html_text(item))
            content_format = "list"
        else:
            paragraphs = [
                clean_html_text(item)
                for item in re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.S)
                if clean_html_text(item)
            ]
            content = " ".join(paragraphs)
            content_format = "paragraph"

        content_rows.append(
            {
                "entry_type": "section",
                "title": title,
                "content": content,
                "content_format": content_format,
                "image_path": image_path,
                "image_alt": image_alt,
                "sort_order": index,
            }
        )

    has_placeholder_content = any(
        item["entry_type"] == "section"
        and (
            item["title"].startswith("Sadaļa ")
            or "Ielādējam sadaļu" in item["content"]
        )
        for item in content_rows
    )

    if len(content_rows) <= 1 or has_placeholder_content:
        return FALLBACK_ABOUT_CONTENT

    return content_rows


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
    about_seed = load_about_data()

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

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            procedure TEXT NOT NULL,
            created_at TEXT NOT NULL,
            password_updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            doctor_id INTEGER,
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

        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_role TEXT NOT NULL DEFAULT 'guest',
            user_id INTEGER,
            doctor_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS par_mums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            content_format TEXT NOT NULL DEFAULT 'paragraph',
            image_path TEXT NOT NULL DEFAULT '',
            image_alt TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    appointment_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(appointments)").fetchall()
    }
    if "doctor_id" not in appointment_columns:
        connection.execute("ALTER TABLE appointments ADD COLUMN doctor_id INTEGER")

    legacy_about_table = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'about_content'
        """
    ).fetchone()
    if legacy_about_table is not None:
        legacy_about_rows = connection.execute(
            """
            SELECT entry_type, title, content, content_format, image_path, image_alt, sort_order, created_at, updated_at
            FROM about_content
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()
        current_about_count = connection.execute("SELECT COUNT(*) FROM par_mums").fetchone()[0]

        if current_about_count == 0 and legacy_about_rows:
            connection.executemany(
                """
                INSERT INTO par_mums (
                    entry_type, title, content, content_format, image_path, image_alt, sort_order, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                legacy_about_rows,
            )

        connection.execute("DROP TABLE about_content")

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

    about_rows = connection.execute(
        "SELECT entry_type, title, content FROM par_mums ORDER BY sort_order ASC, id ASC"
    ).fetchall()
    should_reset_about_content = (
        not about_rows
        or (
            len(about_rows) <= 2
            and any(
                row[1].startswith("Sadaļa ")
                or "Ielādējam sadaļu" in (row[2] or "")
                for row in about_rows
                if row[0] == "section"
            )
        )
    )

    if should_reset_about_content:
        connection.execute("DELETE FROM par_mums")
        timestamp = now_iso()
        connection.executemany(
            """
            INSERT INTO par_mums (
                entry_type, title, content, content_format, image_path, image_alt, sort_order, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["entry_type"],
                    item["title"],
                    item["content"],
                    item["content_format"],
                    item["image_path"],
                    item["image_alt"],
                    item["sort_order"],
                    timestamp,
                    timestamp,
                )
                for item in about_seed
            ],
        )

    connection.commit()
    connection.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        account = current_account()
        if account is None:
            return jsonify({"error": "Authentication required"}), 401
        return view(account, *args, **kwargs)

    return wrapped


def patient_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        account = current_account()
        if account is None:
            return jsonify({"error": "Authentication required"}), 401
        if account["role"] != "user":
            return jsonify({"error": DOCTOR_APPOINTMENT_MESSAGE}), 403
        return view(account, *args, **kwargs)

    return wrapped


def doctor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        account = current_account()
        if account is None:
            return jsonify({"error": "Authentication required"}), 401
        if account["role"] != "doctor":
            return jsonify({"error": "Doctor authentication required"}), 403
        return view(account, *args, **kwargs)

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
    account = current_account()

    if filename in ACCOUNT_ONLY_PAGES and account is None:
        return redirect(url_for("pages", filename="login.html"))

    if filename in PATIENT_ONLY_PAGES:
        if account is None:
            return redirect(url_for("pages", filename="login.html"))
        if account["role"] != "user":
            return redirect(url_for("pages", filename="user_cab.html"))

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
    if user_email_exists(email):
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


@app.post("/api/doctors/register")
def api_register_doctor() -> Any:
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    procedure = str(payload.get("procedure", "")).strip()

    if not all([name, surname, phone, email, password, procedure]):
        return jsonify({"error": "All fields are required"}), 400

    if not is_valid_doctor_procedure(procedure):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    db = get_db()
    if doctor_email_exists(email):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO doctors (name, surname, phone, email, password_hash, procedure, created_at, password_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            procedure,
            timestamp,
            timestamp,
        ),
    )
    db.commit()

    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(
        {
            "message": "Doctor registration successful",
            "user": public_doctor_dict(doctor),
        }
    ), 201


@app.post("/api/login")
def api_login() -> Any:
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "user")).strip().lower()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if role not in {"user", "doctor"}:
        return jsonify({"error": "Lūdzu izvēlieties konta tipu."}), 400

    db = get_db()
    clear_account_session()

    if role == "user":
        user = db.execute(
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

    doctor = db.execute(
        "SELECT * FROM doctors WHERE email = ?",
        (email,),
    ).fetchone()
    if doctor is None or not check_password_hash(doctor["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["doctor_id"] = doctor["id"]
    return jsonify(
        {
            "message": "Login successful",
            "user": public_doctor_dict(doctor),
        }
    )


@app.post("/api/logout")
def api_logout() -> Any:
    clear_account_session()
    return jsonify({"message": "Logged out"})


@app.get("/api/me")
@login_required
def api_me(account: dict[str, Any]) -> Any:
    return jsonify(public_account_dict(account))


@app.put("/api/me")
@login_required
def api_update_me(account: dict[str, Any]) -> Any:
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedure = str(payload.get("procedure", "")).strip()

    if not all([name, surname, phone, email]):
        return jsonify({"error": "Name, surname, phone and email are required"}), 400

    db = get_db()
    if account["role"] == "user" and user_email_exists(email, exclude_user_id=account["id"]):
        return jsonify({"error": "User with this email already exists"}), 409
    if account["role"] == "doctor" and doctor_email_exists(email, exclude_doctor_id=account["id"]):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    if account["role"] == "doctor":
        if not procedure or not is_valid_doctor_procedure(procedure):
            return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

        procedure_changed = account.get("procedure") != procedure
        db.execute(
            """
            UPDATE doctors
            SET name = ?, surname = ?, phone = ?, email = ?, procedure = ?
            WHERE id = ?
            """,
            (name, surname, phone, email, procedure, account["id"]),
        )
        if procedure_changed:
            db.execute(
                """
                UPDATE appointments
                SET doctor_id = NULL, updated_at = ?
                WHERE doctor_id = ?
                """,
                (timestamp, account["id"]),
            )
        db.commit()

        updated_doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (account["id"],)).fetchone()
        return jsonify(
            {
                "message": "Profile updated successfully",
                "user": public_doctor_dict(updated_doctor),
            }
        )

    db.execute(
        """
        UPDATE users
        SET name = ?, surname = ?, phone = ?, email = ?
        WHERE id = ?
        """,
        (name, surname, phone, email, account["id"]),
    )
    db.execute(
        """
        UPDATE appointments
        SET name = ?, surname = ?, phone = ?, email = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (name, surname, phone, email, timestamp, account["id"]),
    )
    db.commit()

    updated_user = db.execute("SELECT * FROM users WHERE id = ?", (account["id"],)).fetchone()
    return jsonify(
        {
            "message": "Profile updated successfully",
            "user": public_user_dict(updated_user),
        }
    )


@app.get("/api/my-appointments")
@login_required
def api_my_appointments(account: dict[str, Any]) -> Any:
    db = get_db()

    if account["role"] == "doctor":
        rows = db.execute(
            """
            SELECT
                appointments.*,
                doctors.name AS doctor_name,
                doctors.surname AS doctor_surname
            FROM appointments
            LEFT JOIN doctors ON doctors.id = appointments.doctor_id
            WHERE appointments.doctor_id = ?
            ORDER BY appointments.datums ASC, appointments.laiks ASC, appointments.created_at DESC
            """,
            (account["id"],),
        ).fetchall()
        return jsonify([appointment_to_dict(row) for row in rows])

    rows = db.execute(
        """
        SELECT
            appointments.*,
            doctors.name AS doctor_name,
            doctors.surname AS doctor_surname
        FROM appointments
        LEFT JOIN doctors ON doctors.id = appointments.doctor_id
        WHERE appointments.user_id = ?
        ORDER BY appointments.datums ASC, appointments.laiks ASC, appointments.created_at DESC
        """,
        (account["id"],),
    ).fetchall()
    return jsonify([appointment_to_dict(row) for row in rows])


@app.delete("/api/my-appointments/<int:appointment_id>")
@patient_required
def api_delete_my_appointment(account: dict[str, Any], appointment_id: int) -> Any:
    db = get_db()
    appointment = db.execute(
        """
        SELECT id FROM appointments
        WHERE id = ? AND user_id = ?
        """,
        (appointment_id, account["id"]),
    ).fetchone()
    if appointment is None:
        return jsonify({"error": "Appointment not found"}), 404

    db.execute(
        "DELETE FROM appointments WHERE id = ?",
        (appointment_id,),
    )
    db.commit()
    return jsonify({"message": "Appointment cancelled successfully"})


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


@app.get("/api/about")
def api_about() -> Any:
    rows = get_db().execute(
        """
        SELECT *
        FROM par_mums
        ORDER BY sort_order ASC, id ASC
        """
    ).fetchall()

    page_title = FALLBACK_ABOUT_PAGE_TITLE
    sections: list[dict[str, Any]] = []

    for row in rows:
        item = row_to_dict(row)
        if item["entry_type"] == "page_title":
            page_title = item["title"] or FALLBACK_ABOUT_PAGE_TITLE
            continue

        sections.append(item)

    if not rows:
        page_title = FALLBACK_ABOUT_PAGE_TITLE
        sections = [
            item
            for item in FALLBACK_ABOUT_CONTENT
            if item["entry_type"] == "section"
        ]

    return jsonify(
        {
            "page_title": page_title,
            "sections": sections,
        }
    )


@app.get("/api/doctors")
@patient_required
def api_doctors_by_procedure(account: dict[str, Any]) -> Any:
    procedura = str(request.args.get("procedura", "")).strip()
    if not procedura:
        return jsonify([])

    if not is_valid_doctor_procedure(procedura):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    rows = get_db().execute(
        """
        SELECT id, name, surname, procedure
        FROM doctors
        WHERE procedure = ?
        ORDER BY surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
        """,
        (procedura,),
    ).fetchall()
    return jsonify([public_doctor_option_dict(row) for row in rows])


@app.post("/api/chatbot")
def api_chatbot() -> Any:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history")

    if not message:
        return jsonify({"error": "Ziņa nedrīkst būt tukša."}), 400

    if len(message) > 1200:
        message = message[:1200]

    if not is_clinic_related_message(message):
        return jsonify({"reply": CHATBOT_OFF_TOPIC_MESSAGE, "source": "local"})

    history_items = history if isinstance(history, list) else []
    local_reply, _ = build_local_chatbot_response(message)

    openai_reply = call_openai_clinic_chatbot(message, history_items)
    if openai_reply:
        return jsonify({"reply": openai_reply, "source": "openai"})

    return jsonify({"reply": local_reply, "source": "local"})


@app.post("/api/contact-messages")
def api_create_contact_message() -> Any:
    payload = request.get_json(silent=True) or {}
    account = current_account()

    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Ziņojums ir obligāts."}), 400

    if len(message) > 2000:
        return jsonify({"error": "Ziņojums ir pārāk garš."}), 400

    sender_role = "guest"
    user_id: int | None = None
    doctor_id: int | None = None

    if account is not None:
        name = " ".join(
            part.strip()
            for part in [str(account.get("name", "")), str(account.get("surname", ""))]
            if str(part).strip()
        )
        email = str(account.get("email", "")).strip().lower()
        sender_role = str(account.get("role", "guest")).strip() or "guest"
        if sender_role == "user":
            user_id = int(account["id"])
        elif sender_role == "doctor":
            doctor_id = int(account["id"])
    else:
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()

    if not name:
        return jsonify({"error": "Vārds ir obligāts."}), 400

    if not email:
        return jsonify({"error": "E-pasts ir obligāts."}), 400

    email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    if not email_pattern.match(email):
        return jsonify({"error": "Lūdzu ievadiet korektu e-pastu."}), 400

    db = get_db()
    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO contact_messages (
            sender_role, user_id, doctor_id, name, email, message, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sender_role,
            user_id,
            doctor_id,
            name,
            email,
            message,
            timestamp,
        ),
    )
    db.commit()

    saved_message = db.execute(
        "SELECT * FROM contact_messages WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify(
        {
            "message": "Ziņojums veiksmīgi nosūtīts.",
            "contact_message": row_to_dict(saved_message),
        }
    ), 201


@app.post("/api/update-password")
@login_required
def api_update_password(account: dict[str, Any]) -> Any:
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password", ""))

    if not password:
        return jsonify({"error": "Password is required"}), 400

    timestamp = now_iso()
    db = get_db()
    if account["role"] == "doctor":
        db.execute(
            """
            UPDATE doctors
            SET password_hash = ?, password_updated_at = ?
            WHERE id = ?
            """,
            (generate_password_hash(password), timestamp, account["id"]),
        )
    else:
        db.execute(
            """
            UPDATE users
            SET password_hash = ?, password_updated_at = ?
            WHERE id = ?
            """,
            (generate_password_hash(password), timestamp, account["id"]),
        )
    db.commit()

    return jsonify({"message": "Password updated successfully"})


@app.post("/api/appointments")
@patient_required
def api_create_appointment(account: dict[str, Any]) -> Any:
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
    raw_doctor_id = payload.get("doctor_id")

    if not all([name, surname, phone, email, procedura, datums, laiks, adrese]):
        return jsonify({"error": "All appointment fields are required"}), 400

    schedule_error = validate_appointment_schedule(datums, laiks)
    if schedule_error:
        return jsonify({"error": schedule_error}), 400

    doctor = validate_appointment_doctor(raw_doctor_id, procedura)
    if doctor is None:
        return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 400

    existing_appointment = find_active_procedure_appointment(
        "user",
        account["id"],
        procedura,
    )
    if existing_appointment is not None:
        return jsonify({"error": APPOINTMENT_DUPLICATE_MESSAGE}), 409

    timestamp = now_iso()
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO appointments (
            user_id, doctor_id, name, surname, phone, email, procedura, datums, laiks, adrese, comment, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account["id"],
            doctor["id"],
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
        """
        SELECT
            appointments.*,
            doctors.name AS doctor_name,
            doctors.surname AS doctor_surname
        FROM appointments
        LEFT JOIN doctors ON doctors.id = appointments.doctor_id
        WHERE appointments.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify({"message": "Appointment created", "appointment": appointment_to_dict(appointment)}), 201


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
    if user_email_exists(email):
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

    if user_email_exists(email, exclude_user_id=user_id):
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


@app.get("/api/admin/doctors")
@admin_required
def api_admin_doctors() -> Any:
    rows = get_db().execute(
        "SELECT * FROM doctors ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([public_doctor_dict(row) for row in rows])


@app.post("/api/admin/doctors")
@admin_required
def api_admin_create_doctor() -> Any:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedure = str(payload.get("procedure", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not all([name, email, procedure, password]):
        return jsonify({"error": "Name, email, procedure and password are required"}), 400

    if not is_valid_doctor_procedure(procedure):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    db = get_db()
    if doctor_email_exists(email):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO doctors (name, surname, phone, email, password_hash, procedure, created_at, password_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            procedure,
            timestamp,
            timestamp,
        ),
    )
    db.commit()

    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(public_doctor_dict(doctor)), 201


@app.delete("/api/admin/doctors/<int:doctor_id>")
@admin_required
def api_admin_delete_doctor(doctor_id: int) -> Any:
    db = get_db()
    db.execute(
        "UPDATE appointments SET doctor_id = NULL, updated_at = ? WHERE doctor_id = ?",
        (now_iso(), doctor_id),
    )
    db.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
    db.commit()
    return jsonify({"message": "Doctor deleted"})


@app.put("/api/admin/doctors/<int:doctor_id>")
@admin_required
def api_admin_update_doctor(doctor_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedure = str(payload.get("procedure", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not all([name, email, procedure]):
        return jsonify({"error": "Name, email and procedure are required"}), 400

    if not is_valid_doctor_procedure(procedure):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    db = get_db()
    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    if doctor_email_exists(email, exclude_doctor_id=doctor_id):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    password_hash = doctor["password_hash"]
    procedure_changed = doctor["procedure"] != procedure
    if password:
        password_hash = generate_password_hash(password)

    db.execute(
        """
        UPDATE doctors
        SET name = ?, surname = ?, phone = ?, email = ?, password_hash = ?, procedure = ?, password_updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            surname,
            phone,
            email,
            password_hash,
            procedure,
            timestamp,
            doctor_id,
        ),
    )
    if procedure_changed:
        db.execute(
            """
            UPDATE appointments
            SET doctor_id = NULL, updated_at = ?
            WHERE doctor_id = ?
            """,
            (timestamp, doctor_id),
        )
    db.commit()

    updated_doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    return jsonify(public_doctor_dict(updated_doctor))


@app.get("/api/admin/about-content")
@admin_required
def api_admin_about_content() -> Any:
    rows = get_db().execute(
        """
        SELECT *
        FROM par_mums
        ORDER BY sort_order ASC, id ASC
        """
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.put("/api/admin/about-content/<int:entry_id>")
@admin_required
def api_admin_update_about_content(entry_id: int) -> Any:
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", "")).strip()
    content_format = str(payload.get("content_format", "paragraph")).strip().lower()
    image_path = normalize_public_asset_path(str(payload.get("image_path", "")).strip())
    image_alt = str(payload.get("image_alt", "")).strip()
    raw_sort_order = payload.get("sort_order", 0)

    if not title:
        return jsonify({"error": "Title is required"}), 400

    if content_format not in {"text", "paragraph", "list"}:
        return jsonify({"error": "Invalid content format"}), 400

    try:
        sort_order = int(raw_sort_order)
    except (TypeError, ValueError):
        return jsonify({"error": "Sort order must be a number"}), 400

    db = get_db()
    entry = db.execute(
        "SELECT * FROM par_mums WHERE id = ?",
        (entry_id,),
    ).fetchone()
    if entry is None:
        return jsonify({"error": "About content entry not found"}), 404

    entry_type = entry["entry_type"]
    if entry_type == "page_title":
        content = ""
        content_format = "text"
        image_path = ""
        image_alt = ""
        sort_order = 0
    else:
        if not content:
            return jsonify({"error": "Content is required"}), 400
        if not image_alt:
            image_alt = title

    db.execute(
        """
        UPDATE par_mums
        SET title = ?, content = ?, content_format = ?, image_path = ?, image_alt = ?, sort_order = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            content,
            content_format,
            image_path,
            image_alt,
            sort_order,
            now_iso(),
            entry_id,
        ),
    )
    db.commit()

    updated_entry = db.execute(
        "SELECT * FROM par_mums WHERE id = ?",
        (entry_id,),
    ).fetchone()
    return jsonify(row_to_dict(updated_entry))


@app.get("/api/admin/contact-messages")
@admin_required
def api_admin_contact_messages() -> Any:
    rows = get_db().execute(
        """
        SELECT *
        FROM contact_messages
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.delete("/api/admin/contact-messages/<int:message_id>")
@admin_required
def api_admin_delete_contact_message(message_id: int) -> Any:
    db = get_db()
    existing_message = db.execute(
        "SELECT id FROM contact_messages WHERE id = ?",
        (message_id,),
    ).fetchone()
    if existing_message is None:
        return jsonify({"error": "Ziņojums nav atrasts."}), 404

    db.execute("DELETE FROM contact_messages WHERE id = ?", (message_id,))
    db.commit()
    return jsonify({"message": "Ziņojums dzēsts."})


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
        """
        SELECT
            appointments.*,
            doctors.name AS doctor_name,
            doctors.surname AS doctor_surname
        FROM appointments
        LEFT JOIN doctors ON doctors.id = appointments.doctor_id
        ORDER BY appointments.created_at DESC
        """
    ).fetchall()
    return jsonify([appointment_to_dict(row) for row in rows])


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

    schedule_error = validate_appointment_schedule(datums, laiks)
    if schedule_error:
        return jsonify({"error": schedule_error}), 400

    db = get_db()
    appointment = db.execute(
        "SELECT id, user_id, doctor_id FROM appointments WHERE id = ?",
        (appointment_id,),
    ).fetchone()
    if appointment is None:
        return jsonify({"error": "Appointment not found"}), 404

    owner_role = "user"
    owner_id = appointment["user_id"]
    if owner_id is not None:
        conflicting_appointment = find_active_procedure_appointment(
            owner_role,
            owner_id,
            procedura,
            exclude_appointment_id=appointment_id,
        )
        if conflicting_appointment is not None:
            return jsonify({"error": APPOINTMENT_DUPLICATE_MESSAGE}), 409

    raw_doctor_id = payload.get("doctor_id", appointment["doctor_id"])
    doctor = validate_appointment_doctor(raw_doctor_id, procedura)
    if raw_doctor_id not in (None, "") and doctor is None and "doctor_id" in payload:
        return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 400

    doctor_id = doctor["id"] if doctor is not None else None

    db.execute(
        """
        UPDATE appointments
        SET name = ?, surname = ?, phone = ?, email = ?, procedura = ?, doctor_id = ?, datums = ?, laiks = ?, adrese = ?, comment = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            surname,
            phone,
            email,
            procedura,
            doctor_id,
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
        """
        SELECT
            appointments.*,
            doctors.name AS doctor_name,
            doctors.surname AS doctor_surname
        FROM appointments
        LEFT JOIN doctors ON doctors.id = appointments.doctor_id
        WHERE appointments.id = ?
        """,
        (appointment_id,),
    ).fetchone()
    return jsonify(appointment_to_dict(updated_appointment))


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
