from __future__ import annotations

import html
import json
import os
import re
import unicodedata
import calendar
from datetime import date, datetime, time, timedelta
from functools import wraps
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib.parse import unquote, urlsplit, urlunsplit
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
import psycopg
from psycopg import sql
from psycopg.errors import InvalidCatalogName
from werkzeug.security import check_password_hash, generate_password_hash


# Projekta pamatceļi, vides mainīgie un lapu piekļuves noteikumi.
BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
HTML_PAGES = {path.name for path in BASE_DIR.glob("*.html")}
ACCOUNT_ONLY_PAGES = {"user_cab.html", "pieteikties.html", "doctor-schedule.html"}
PATIENT_ONLY_PAGES = {"pieteikties.html"}
DOCTOR_ONLY_PAGES = {"doctor-schedule.html"}
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
DOCTOR_APPROVAL_PENDING = "pending"
DOCTOR_APPROVAL_APPROVED = "approved"
DOCTOR_APPROVAL_CANCELLED = "cancelled"
DOCTOR_APPROVAL_STATUSES = {
    DOCTOR_APPROVAL_PENDING,
    DOCTOR_APPROVAL_APPROVED,
    DOCTOR_APPROVAL_CANCELLED,
}
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

ADDITIONAL_FALLBACK_PRICES = [
    ("Plaušu CT izmeklējums:", "Datortomogrāfija", 110.00),
    ("Galvas, deguna blakusdobumu vai muskuloskeletālās sistēmas CT izmeklējums ar i/v kontrastēšanu:", "Datortomogrāfija", 125.00),
    ("CT izmeklējums krūšu kurvja orgāniem ar i/v kontrastēšanu:", "Datortomogrāfija", 175.00),
    ("CT izmeklējums vēdera dobumam un retroperitoneālai telpai ar i/v kontrastēšanu:", "Datortomogrāfija", 200.00),
    ("CT angiogrāfija nieru artērijām:", "Datortomogrāfija", 180.00),
    ("CT angiogrāfija vēdera aortai un kāju asinsvadiem:", "Datortomogrāfija", 180.00),
    ("CT angiogrāfija vēdera aortai un tās zariem:", "Datortomogrāfija", 180.00),
    ("CT angiogrāfija aortas lokam un roku asinsvadiem:", "Datortomogrāfija", 180.00),
    ("CT angiogrāfija brahiocefālajiem asinsvadiem:", "Datortomogrāfija", 180.00),
    ("CT angiogrāfija krūšu un vēdera aortai:", "Datortomogrāfija", 180.00),
    ("CT sirdij, sirds asinsvadiem vai krūšu kurvja aortai sirdsdarbības kontroles režīmā:", "Datortomogrāfija", 200.00),
    ("Kontrastviela 50 ml CT izmeklējumiem (Ultravist, Iopamiro, Iohexolo):", "Datortomogrāfija", 37.00),
    ("Kontrastviela 100 ml CT izmeklējumiem (Ultravist, Iopamiro, Iohexolo):", "Datortomogrāfija", 40.00),
    ("CT kaulu traumas vai lūzuma kontrolei (bez apraksta):", "Datortomogrāfija", 38.00),
    ("CT vienai ķermeņa daļai bez kontrastēšanas (bez apraksta):", "Datortomogrāfija", 75.00),
    ("CT vēdera dobumam un mazajam iegurnim bez kontrastēšanas:", "Datortomogrāfija", 110.00),
    ("Vakcinācija pret pneimokoku:", "Vakcinācija", 100.50),
    ("Vakcinācija pret ērču encefalītu (TICOVAC):", "Vakcinācija", 40.50),
    ("Vakcinācija pret ērču encefalītu bērniem (TICOVAC):", "Vakcinācija", 34.50),
    ("Vakcinācija pret vīrushepatītu A (HAVRIX):", "Vakcinācija", 60.50),
    ("Vakcinācija pret vīrushepatītu B (ENGERIX):", "Vakcinācija", 45.50),
    ("Vakcinācija pret vīrushepatītu A un B (TWINRIX):", "Vakcinācija", 90.50),
    ("Vakcinācija pret dzelteno drudzi (STAMARIL):", "Vakcinācija", 70.50),
    ("Vakcinācija pret vēdertīfu (Typhim Vi):", "Vakcinācija", 55.50),
    ("Vakcinācija pret masalām, masaliņām un parotītu M-M-RVAXPro:", "Vakcinācija", 30.50),
    ("Dzeltenā drudža sertifikāts:", "Vakcinācija", 3.50),
    ("Vakcinācija pret trakumsērgu (VERORAB):", "Vakcinācija", 66.50),
    ("Vakcinācija pret difteriju, stinguma krampjiem un garo klepu (ADACEL):", "Vakcinācija", 47.50),
    ("Vakcinācija pret vīrushepatītu A (AVAXIM):", "Vakcinācija", 60.50),
    ("Vakcinācija pret difteriju, stinguma krampjiem, poliomielītu (DULTAVAX):", "Vakcinācija", 30.50),
    ("Piesūkušās ērces noņemšana un koduma vietas apstrāde:", "Vakcinācija", 10.00),
    ("Dzeltenā drudža sertifikāta dublikāta izsniegšana:", "Vakcinācija", 10.00),
    ("Vakcīna pret dzemdes kakla vēzi Gardasil 9:", "Vakcinācija", 190.50),
    ("Vakcinācija pret meningokoku (Nimenrix):", "Vakcinācija", 80.50),
    ("Vakcinācija pret holēru (DUKORAL):", "Vakcinācija", 60.50),
    ("Apmeklējums mājās:", "Ģimenes ārsts", 10.00),
]

def fallback_price_service_name(service_name: str) -> str:
    # Cenu importēšanas laikā mēģina atpazīt, kurai pakalpojumu kategorijai cena pieder.
    normalized_name = unicodedata.normalize("NFKD", service_name)
    normalized_name = normalized_name.encode("ascii", "ignore").decode("ascii").lower()
    if "tomograf" in normalized_name or "ct" in normalized_name:
        return FALLBACK_PRICES[0][1]
    if "vakcin" in normalized_name:
        return FALLBACK_PRICES[2][1]
    if "gimen" in normalized_name or "imenes" in normalized_name or "arst" in normalized_name:
        return FALLBACK_PRICES[1][1]
    return service_name


DEFAULT_PRICES = FALLBACK_PRICES + [
    (title, fallback_price_service_name(service_name), price)
    for title, service_name, price in ADDITIONAL_FALLBACK_PRICES
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

# Flask lietotnes konfigurācija un sensitīvās vērtības no vides mainīgajiem.
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
    # Tekstu vienkāršo, lai čatbots atpazītu jautājumus arī bez garumzīmēm.
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_diacritics = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9\s+]", " ", without_diacritics)


def format_chatbot_price(value: float | int | str) -> str:
    # Cenas tiek formatētas lietotājam saprotamā EUR formātā.
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return f"{value} EUR"
    return f"{amount:.2f}".replace(".", ",") + " EUR"


def detect_chatbot_service_key(message: str) -> str | None:
    # Pēc atslēgvārdiem nosaka, par kuru pakalpojumu lietotājs jautā.
    normalized_message = normalize_chatbot_text(message)
    for service_key, aliases in CHATBOT_SERVICE_ALIASES.items():
        if any(alias in normalized_message for alias in aliases):
            return service_key
    return None


def is_chatbot_greeting(message: str) -> bool:
    normalized_message = normalize_chatbot_text(message).strip()
    return normalized_message in CHATBOT_GREETINGS


def is_clinic_related_message(message: str) -> bool:
    # Čatbots atbild tikai uz jautājumiem, kas saistīti ar klīniku.
    normalized_message = normalize_chatbot_text(message)
    if not normalized_message.strip():
        return False
    if is_chatbot_greeting(message):
        return True
    return any(keyword in normalized_message for keyword in CHATBOT_CLINIC_KEYWORDS)


def fetch_chatbot_doctors(service_key: str | None = None) -> list[DbRow]:
    # Čatbotam rāda tikai apstiprinātos ārstus.
    db = get_db()
    if service_key:
        return db.execute(
            """
            SELECT id, name, surname, procedure
            FROM doctors
            WHERE procedure = ? AND approval_status = ?
            ORDER BY surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
            """,
            (service_key, DOCTOR_APPROVAL_APPROVED),
        ).fetchall()

    return db.execute(
        """
        SELECT id, name, surname, procedure
        FROM doctors
        WHERE approval_status = ?
        ORDER BY procedure ASC, surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
        """,
        (DOCTOR_APPROVAL_APPROVED,),
    ).fetchall()


def fetch_chatbot_prices(service_label: str | None = None) -> list[DbRow]:
    # Cenu sarakstu var ielādēt visam katalogam vai vienai procedūrai.
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
    # Sagatavo cilvēkam saprotamu čatbota atbildi par ārstiem.
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
    # Sagatavo čatbota atbildi par cenām, izmantojot datubāzes datus.
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
    # Izveido īsu pakalpojumu sarakstu čatbota atbildei.
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
    # Lokālā atbilžu loģika darbojas arī tad, ja OpenAI API nav pieejams.
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
    # OpenAI čatbotam tiek padots konteksts no reālajiem projekta datiem.
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
    # No OpenAI atbildes struktūras izvelk tikai gala tekstu.
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
    # Ja API atslēgas nav vai pieprasījums neizdodas, funkcija atgriež None un strādā lokālā atbilde.
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
    # Pievieno mēnešus, saglabājot derīgu datumu arī īsākos mēnešos.
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_iso_date(value: str) -> date | None:
    # Pārveido HTML datuma vērtību Python date objektā.
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_iso_time(value: str) -> time | None:
    # Pārveido HTML laika vērtību Python time objektā.
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def validate_booking_window(target_date: date) -> str | None:
    # Pierakstus atļauj veidot tikai no šodienas līdz trīs mēnešiem uz priekšu.
    today = date.today()
    max_date = add_months(today, 3)
    if target_date < today or target_date > max_date:
        return "Pieteikties var tikai no šodienas līdz 3 mēnešiem uz priekšu."
    return None


def get_working_hours_for_date(target_date: date) -> tuple[int, int] | None:
    # Darba laiku atgriež minūtēs, lai laiku salīdzināšana būtu vienkārša.
    weekday = target_date.weekday()
    if weekday <= 4:
        return (9 * 60, 21 * 60)
    if weekday == 5:
        return (10 * 60, 20 * 60)
    return None


def validate_appointment_schedule(datums: str, laiks: str) -> str | None:
    # Servera puses validācija pasargā no nekorektiem pieraksta datiem.
    appointment_date = parse_iso_date(datums)
    if appointment_date is None:
        return "Lūdzu izvēlieties korektu datumu."

    appointment_time = parse_iso_time(laiks)
    if appointment_time is None:
        return "Lūdzu izvēlieties korektu laiku."

    booking_window_error = validate_booking_window(appointment_date)
    if booking_window_error:
        return booking_window_error

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
DOCTOR_SLOT_UNAVAILABLE_MESSAGE = "Ārsts šajā datumā un laikā nav pieejams."
DOCTOR_SLOT_ALREADY_BOOKED_MESSAGE = "Šis laiks vairs nav pieejams. Lūdzu izvēlieties citu laiku."


def appointment_owner_column(role: str) -> str:
    # Atkarībā no konta lomas izvēlas, pēc kuras kolonnas meklēt pierakstu īpašnieku.
    if role == "doctor":
        return "doctor_id"
    return "user_id"


def find_active_procedure_appointment(
    owner_role: str,
    owner_id: int | None,
    procedura: str,
    *,
    exclude_appointment_id: int | None = None,
) -> DbRow | None:
    # Neļauj vienam kontam vienlaikus turēt vairākus aktīvus pierakstus uz to pašu procedūru.
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


def is_valid_doctor_approval_status(status: str) -> bool:
    return status in DOCTOR_APPROVAL_STATUSES


def doctor_has_access(row: DbRow | dict[str, Any]) -> bool:
    # Ārsta konts sistēmā darbojas tikai pēc administratora apstiprinājuma.
    if isinstance(row, DbRow):
        status = row["approval_status"]
    else:
        status = row.get("approval_status")
    return status == DOCTOR_APPROVAL_APPROVED


def doctor_access_denied_message(status: str | None) -> str:
    if status == DOCTOR_APPROVAL_PENDING:
        return "Ārsta profils vēl gaida administratora apstiprinājumu."
    if status == DOCTOR_APPROVAL_CANCELLED:
        return "Ārsta profils ir atcelts. Sazinieties ar administratoru."
    return "Ārsta profils nav pieejams."


def doctor_display_name(name: str | None, surname: str | None) -> str:
    return " ".join(part for part in [name or "", surname or ""] if part).strip()


def appointment_to_dict(row: DbRow) -> dict[str, Any]:
    # API atbildē pievieno pilnu ārsta vārdu, lai frontendam tas nav jāveido pašam.
    data = row_to_dict(row)
    if "doctor_name" in data or "doctor_surname" in data:
        data["doctor_full_name"] = doctor_display_name(
            data.get("doctor_name"),
            data.get("doctor_surname"),
        )
    return data


def validate_appointment_doctor(doctor_id: Any, procedura: str) -> DbRow | None:
    # Pārbauda, vai ārsts ir apstiprināts un atbilst izvēlētajai procedūrai.
    if doctor_id in (None, ""):
        return None

    try:
        doctor_identifier = int(doctor_id)
    except (TypeError, ValueError):
        return None

    return get_db().execute(
        """
        SELECT * FROM doctors
        WHERE id = ? AND procedure = ? AND approval_status = ?
        """,
        (doctor_identifier, procedura, DOCTOR_APPROVAL_APPROVED),
    ).fetchone()


def public_doctor_option_dict(row: DbRow | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "surname": row["surname"],
        "procedure": row["procedure"],
        "full_name": doctor_display_name(row["name"], row["surname"]),
    }


def public_user_dict(row: DbRow | dict[str, Any]) -> dict[str, Any]:
    # Uz klienta pusi nesūta paroles hash, tikai publiski vajadzīgos lietotāja datus.
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


def public_doctor_dict(row: DbRow | dict[str, Any]) -> dict[str, Any]:
    # Ārsta publiskajā objektā iekļauj arī specializāciju un apstiprinājuma statusu.
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
        "approval_status": row["approval_status"],
        "status_updated_at": row["status_updated_at"],
        "can_book_appointments": False,
    }


def parse_month_value(value: str) -> tuple[date, date] | None:
    # Ārsta kalendāram pārveido YYYY-MM vērtību par mēneša sākumu un beigām.
    parts = value.split("-")
    if len(parts) != 2:
        return None

    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError:
        return None

    if month < 1 or month > 12:
        return None

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    return month_start, month_end


def serialize_time_from_minutes(total_minutes: int) -> str:
    # Minūšu skaitu pārvērš HH:MM tekstā.
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def build_time_slots_for_date(target_date: date) -> list[str]:
    # Ģenerē visus iespējamos 15 minūšu slotus konkrētai darba dienai.
    working_hours = get_working_hours_for_date(target_date)
    if working_hours is None:
        return []

    opening_minutes, closing_minutes = working_hours
    return [
        serialize_time_from_minutes(total_minutes)
        for total_minutes in range(opening_minutes, closing_minutes + 1, 15)
    ]


def get_doctor_configured_times(doctor_id: int, datums: str) -> list[str]:
    # Nolasa laikus, kurus ārsts pats ir atzīmējis kā pieejamus.
    rows = get_db().execute(
        """
        SELECT available_time
        FROM doctor_availability
        WHERE doctor_id = ? AND available_date = ?
        ORDER BY available_time ASC
        """,
        (doctor_id, datums),
    ).fetchall()
    return [row["available_time"] for row in rows]


def get_doctor_booked_times(
    doctor_id: int,
    datums: str,
    *,
    exclude_appointment_id: int | None = None,
) -> list[str]:
    # Nolasa jau aizņemtos laikus, lai tie netiktu piedāvāti atkārtoti.
    query = """
        SELECT laiks
        FROM appointments
        WHERE doctor_id = ? AND datums = ?
    """
    params: list[Any] = [doctor_id, datums]
    if exclude_appointment_id is not None:
        query += " AND id != ?"
        params.append(exclude_appointment_id)

    query += " ORDER BY laiks ASC"
    rows = get_db().execute(query, params).fetchall()
    return [row["laiks"] for row in rows]


def build_doctor_day_schedule_payload(
    doctor_id: int,
    target_date: date,
    *,
    exclude_appointment_id: int | None = None,
) -> dict[str, Any]:
    # Apvieno ārsta pieejamos, aizņemtos un brīvos laikus vienā objektā.
    date_value = target_date.isoformat()
    configured_times = get_doctor_configured_times(doctor_id, date_value)
    booked_times = get_doctor_booked_times(
        doctor_id,
        date_value,
        exclude_appointment_id=exclude_appointment_id,
    )
    booked_time_set = set(booked_times)
    working_hours = get_working_hours_for_date(target_date)

    return {
        "date": date_value,
        "opening_time": serialize_time_from_minutes(working_hours[0]) if working_hours else None,
        "closing_time": serialize_time_from_minutes(working_hours[1]) if working_hours else None,
        "configured_times": configured_times,
        "booked_times": booked_times,
        "open_times": [time_value for time_value in configured_times if time_value not in booked_time_set],
    }


def build_doctor_month_schedule_summary(
    doctor_id: int,
    month_start: date,
    month_end: date,
) -> dict[str, dict[str, int]]:
    # Kalendāram apkopo katras dienas brīvo, aizņemto un kopējo slotu skaitu.
    db = get_db()
    date_from = month_start.isoformat()
    date_to = month_end.isoformat()
    summary: dict[str, dict[str, int]] = {}

    open_rows = db.execute(
        """
        SELECT a.available_date AS date_value, COUNT(*) AS open_slots
        FROM doctor_availability AS a
        LEFT JOIN appointments AS ap
            ON ap.doctor_id = a.doctor_id
           AND ap.datums = a.available_date
           AND ap.laiks = a.available_time
        WHERE a.doctor_id = ?
          AND a.available_date BETWEEN ? AND ?
          AND ap.id IS NULL
        GROUP BY a.available_date
        """,
        (doctor_id, date_from, date_to),
    ).fetchall()
    for row in open_rows:
        summary[row["date_value"]] = {
            "open_slots": row["open_slots"],
            "booked_slots": 0,
            "configured_slots": row["open_slots"],
        }

    booked_rows = db.execute(
        """
        SELECT datums AS date_value, COUNT(*) AS booked_slots
        FROM appointments
        WHERE doctor_id = ?
          AND datums BETWEEN ? AND ?
        GROUP BY datums
        """,
        (doctor_id, date_from, date_to),
    ).fetchall()
    for row in booked_rows:
        day_summary = summary.setdefault(
            row["date_value"],
            {"open_slots": 0, "booked_slots": 0, "configured_slots": 0},
        )
        day_summary["booked_slots"] = row["booked_slots"]
        day_summary["configured_slots"] = day_summary["open_slots"] + row["booked_slots"]

    return summary


def get_doctor_open_dates(doctor_id: int) -> list[dict[str, Any]]:
    # Pacienta pieraksta formai atgriež tikai dienas ar brīviem laikiem.
    today = date.today().isoformat()
    max_date = add_months(date.today(), 3).isoformat()
    rows = get_db().execute(
        """
        SELECT a.available_date AS date_value, COUNT(*) AS open_slots
        FROM doctor_availability AS a
        LEFT JOIN appointments AS ap
            ON ap.doctor_id = a.doctor_id
           AND ap.datums = a.available_date
           AND ap.laiks = a.available_time
        WHERE a.doctor_id = ?
          AND a.available_date BETWEEN ? AND ?
          AND ap.id IS NULL
        GROUP BY a.available_date
        ORDER BY a.available_date ASC
        """,
        (doctor_id, today, max_date),
    ).fetchall()

    return [
        {
            "date": row["date_value"],
            "open_slots": row["open_slots"],
        }
        for row in rows
    ]


def validate_doctor_slot_selection(
    doctor_id: int,
    datums: str,
    laiks: str,
    *,
    exclude_appointment_id: int | None = None,
) -> tuple[str | None, int | None]:
    # Pirms pieraksta saglabāšanas vēlreiz pārbauda, vai izvēlētais laiks ir brīvs.
    configured_times = set(get_doctor_configured_times(doctor_id, datums))
    if laiks not in configured_times:
        return DOCTOR_SLOT_UNAVAILABLE_MESSAGE, 400

    booked_times = set(
        get_doctor_booked_times(
            doctor_id,
            datums,
            exclude_appointment_id=exclude_appointment_id,
        )
    )
    if laiks in booked_times:
        return DOCTOR_SLOT_ALREADY_BOOKED_MESSAGE, 409

    return None, None


def current_user_row() -> DbRow | None:
    # Atrod sesijā ielogoto pacientu, ja tāds ir.
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def current_doctor_row() -> DbRow | None:
    # Atrod sesijā ielogoto ārstu, ja tāds ir.
    doctor_id = session.get("doctor_id")
    if not doctor_id:
        return None
    return get_db().execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()


def current_account() -> dict[str, Any] | None:
    # Vienotā veidā nosaka pašreizējo kontu neatkarīgi no tā, vai tas ir pacients vai ārsts.
    user = current_user_row()
    if user is not None:
        return {
            "role": "user",
            **row_to_dict(user),
        }

    doctor = current_doctor_row()
    if doctor is not None:
        if not doctor_has_access(doctor):
            clear_account_session()
            return None
        return {
            "role": "doctor",
            **row_to_dict(doctor),
        }

    return None


def public_account_dict(account: DbRow | dict[str, Any]) -> dict[str, Any]:
    # Izvēlas pareizo publisko datu formātu pēc konta lomas.
    if account["role"] == "doctor":
        return public_doctor_dict(account)
    return public_user_dict(account)


def clear_account_session() -> None:
    # Izrakstoties notīra abas iespējamās konta sesijas vērtības.
    session.pop("user_id", None)
    session.pop("doctor_id", None)


def user_email_exists(
    email: str,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    # Pārbauda, vai pacienta e-pasts jau netiek izmantots.
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
    # Pārbauda, vai ārsta e-pasts jau netiek izmantots.
    db = get_db()

    doctor_query = "SELECT id FROM doctors WHERE email = ?"
    doctor_params: list[Any] = [email]
    if exclude_doctor_id is not None:
        doctor_query += " AND id != ?"
        doctor_params.append(exclude_doctor_id)

    existing_doctor = db.execute(doctor_query, doctor_params).fetchone()
    return existing_doctor is not None


def clean_html_text(value: str) -> str:
    # No HTML fragmentiem iztīra liekas atstarpes un HTML simbolus.
    return html.unescape(re.sub(r"\s+", " ", value).strip())


def normalize_public_asset_path(value: str) -> str:
    # Attēlu ceļus normalizē tā, lai frontend tos varētu droši izmantot.
    path = (value or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/")):
        return path
    return "/" + path.lstrip("./")


def normalize_lookup(value: str) -> str:
    # Nosaukumus vienkāršo salīdzināšanai neatkarīgi no garumzīmēm.
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def service_public_meta(service_name: str) -> dict[str, str]:
    # Pakalpojumam piemeklē publiskās lapas attēlu, detalizēto lapu un pogas tekstu.
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
    # Ja datubāzē ir tukšs vai vecs apraksts, izmanto kvalitatīvāku noklusējuma tekstu.
    description = (stored_description or "").strip()
    if not description or description in LEGACY_GENERIC_SERVICE_DESCRIPTIONS:
        return SERVICE_DESCRIPTION_MAP.get(service_name, description)
    return description


def load_catalog_data() -> tuple[list[tuple[str, str]], list[tuple[str, str, float]]]:
    # Sākotnējo pakalpojumu katalogu ielasa no cenas.html vai izmanto rezerves datus.
    cenas_path = BASE_DIR / "cenas.html"
    if not cenas_path.exists():
        return FALLBACK_SERVICES, DEFAULT_PRICES

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
        return FALLBACK_SERVICES, DEFAULT_PRICES

    return services, prices


def load_about_data() -> list[dict[str, Any]]:
    # Par mums lapas sākotnējais saturs tiek ielasīts no esošā HTML faila.
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


class DbRow:
    # Vienkārša rindu klase, lai datubāzes rezultātus varētu lasīt gan pēc indeksa, gan kolonnas nosaukuma.
    def __init__(self, columns: list[str], values: tuple[Any, ...]) -> None:
        self._columns = columns
        self._values = values
        self._data = dict(zip(columns, values))

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def __iter__(self):
        return iter(self._values)

    def keys(self):
        return self._data.keys()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class PostgresCursor:
    # Aptin psycopg kursoru, lai pārējais kods varētu strādāt ar DbRow objektiem.
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.lastrowid: int | None = None

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> DbRow | None:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return self._make_row(row)

    def fetchall(self) -> list[DbRow]:
        return [self._make_row(row) for row in self._cursor.fetchall()]

    def _make_row(self, row: tuple[Any, ...]) -> DbRow:
        columns = [column.name for column in self._cursor.description or []]
        return DbRow(columns, row)


class PostgresConnection:
    # Datubāzes savienojuma klase, kas pielāgo SQLite stila vaicājumus PostgreSQL videi.
    def __init__(self) -> None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. Add a PostgreSQL database in Coolify "
                "and pass its connection string as DATABASE_URL."
            )
        self._connection = self._connect()

    @staticmethod
    def _connect():
        try:
            return psycopg.connect(DATABASE_URL, autocommit=True)
        except InvalidCatalogName:
            PostgresConnection._create_database()
            return psycopg.connect(DATABASE_URL, autocommit=True)

    @staticmethod
    def _create_database() -> None:
        parsed_url = urlsplit(DATABASE_URL)
        database_name = unquote(parsed_url.path.lstrip("/"))
        if not database_name:
            raise

        maintenance_db = "template1" if database_name == "postgres" else "postgres"
        maintenance_url = urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                f"/{maintenance_db}",
                parsed_url.query,
                parsed_url.fragment,
            )
        )
        with psycopg.connect(maintenance_url, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> PostgresCursor:
        sql = self._prepare_query(query)
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            sql = "BEGIN"

        should_return_id = self._should_return_insert_id(sql)
        if should_return_id:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"

        cursor = self._connection.cursor()
        cursor.execute(sql, params)
        wrapped = PostgresCursor(cursor)
        if should_return_id:
            row = cursor.fetchone()
            wrapped.lastrowid = row[0] if row else None
        return wrapped

    def executemany(self, query: str, params_seq) -> PostgresCursor:
        cursor = self._connection.cursor()
        cursor.executemany(self._prepare_query(query), params_seq)
        return PostgresCursor(cursor)

    def executescript(self, script: str) -> None:
        self._connection.execute(script)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _prepare_query(query: str) -> str:
        return query.replace("?", "%s")

    @staticmethod
    def _should_return_insert_id(query: str) -> bool:
        normalized = query.lstrip().upper()
        return normalized.startswith("INSERT INTO") and " RETURNING " not in normalized


DatabaseError = psycopg.Error


DEMO_PASSWORD = "Demo12345"
DEMO_EMAIL_DOMAIN = "demo.healthandcare.lv"

DEMO_USERS = [
    ("Anna", "Ozola", "+371 20110001", f"anna.ozola@{DEMO_EMAIL_DOMAIN}"),
    ("Martins", "Kalnins", "+371 20110002", f"martins.kalnins@{DEMO_EMAIL_DOMAIN}"),
    ("Laura", "Berzina", "+371 20110003", f"laura.berzina@{DEMO_EMAIL_DOMAIN}"),
    ("Edgars", "Liepa", "+371 20110004", f"edgars.liepa@{DEMO_EMAIL_DOMAIN}"),
    ("Ieva", "Jansone", "+371 20110005", f"ieva.jansone@{DEMO_EMAIL_DOMAIN}"),
    ("Kristaps", "Balodis", "+371 20110006", f"kristaps.balodis@{DEMO_EMAIL_DOMAIN}"),
    ("Sintija", "Petrova", "+371 20110007", f"sintija.petrova@{DEMO_EMAIL_DOMAIN}"),
    ("Rihards", "Lacis", "+371 20110008", f"rihards.lacis@{DEMO_EMAIL_DOMAIN}"),
    ("Elina", "Eglite", "+371 20110009", f"elina.eglite@{DEMO_EMAIL_DOMAIN}"),
    ("Niks", "Abolins", "+371 20110010", f"niks.abolins@{DEMO_EMAIL_DOMAIN}"),
]

DEMO_DOCTORS = [
    ("Ilze", "Karklina", "+371 20220001", f"ilze.karklina@{DEMO_EMAIL_DOMAIN}", "gimenesArsts"),
    ("Andris", "Vitols", "+371 20220002", f"andris.vitols@{DEMO_EMAIL_DOMAIN}", "gimenesArsts"),
    ("Maija", "Silina", "+371 20220003", f"maija.silina@{DEMO_EMAIL_DOMAIN}", "gimenesArsts"),
    ("Roberts", "Zarins", "+371 20220004", f"roberts.zarins@{DEMO_EMAIL_DOMAIN}", "gimenesArsts"),
    ("Dace", "Priedite", "+371 20220005", f"dace.priedite@{DEMO_EMAIL_DOMAIN}", "gimenesArsts"),
    ("Janis", "Liepinsh", "+371 20220006", f"janis.liepinsh@{DEMO_EMAIL_DOMAIN}", "datortomografija"),
    ("Liene", "Riekstina", "+371 20220007", f"liene.riekstina@{DEMO_EMAIL_DOMAIN}", "datortomografija"),
    ("Pauls", "Krumins", "+371 20220008", f"pauls.krumins@{DEMO_EMAIL_DOMAIN}", "datortomografija"),
    ("Evija", "Saulite", "+371 20220009", f"evija.saulite@{DEMO_EMAIL_DOMAIN}", "datortomografija"),
    ("Oskars", "Birznieks", "+371 20220010", f"oskars.birznieks@{DEMO_EMAIL_DOMAIN}", "datortomografija"),
    ("Linda", "Melne", "+371 20220011", f"linda.melne@{DEMO_EMAIL_DOMAIN}", "vakcinacija"),
    ("Gatis", "Sprogis", "+371 20220012", f"gatis.sprogis@{DEMO_EMAIL_DOMAIN}", "vakcinacija"),
    ("Agnese", "Dreimane", "+371 20220013", f"agnese.dreimane@{DEMO_EMAIL_DOMAIN}", "vakcinacija"),
    ("Renars", "Veveris", "+371 20220014", f"renars.veveris@{DEMO_EMAIL_DOMAIN}", "vakcinacija"),
    ("Marta", "Luse", "+371 20220015", f"marta.luse@{DEMO_EMAIL_DOMAIN}", "vakcinacija"),
]

DEMO_LOCATIONS_BY_PROCEDURE = {
    "gimenesArsts": [
        "Riga, Brivibas iela",
        "Jelgava, Zemgales prospekts",
    ],
    "datortomografija": [
        "Riga, Lidonu iela 13",
        "Liepaja, Rozu iela",
    ],
    "vakcinacija": [
        "Riga, Brivibas iela",
        "Jelgava, Zemgales prospekts",
        "Liepaja, Rozu iela",
    ],
}


def get_seeded_row_id(connection: PostgresConnection, table_name: str, email: str) -> int:
    # Pēc demo konta e-pasta atrod tā ID turpmākai datu sasaistīšanai.
    row = connection.execute(
        f"SELECT id FROM {table_name} WHERE email = ?",
        (email,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Demo row was not created in {table_name}: {email}")
    return row["id"]


def seed_demo_accounts(connection: PostgresConnection) -> tuple[dict[str, int], dict[str, int]]:
    # Izveido demo pacientus un ārstus, lai projekts uzreiz būtu pārbaudāms.
    timestamp = now_iso()
    password_hash = generate_password_hash(DEMO_PASSWORD)

    for name, surname, phone, email in DEMO_USERS:
        if connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone() is None:
            connection.execute(
                """
                INSERT INTO users (name, surname, phone, email, password_hash, created_at, password_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, surname, phone, email, password_hash, timestamp, timestamp),
            )

    for name, surname, phone, email, procedure in DEMO_DOCTORS:
        existing_doctor = connection.execute(
            "SELECT id FROM doctors WHERE email = ?",
            (email,),
        ).fetchone()
        if existing_doctor is None:
            connection.execute(
                """
                INSERT INTO doctors (
                    name, surname, phone, email, password_hash, procedure, approval_status,
                    created_at, password_updated_at, status_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    surname,
                    phone,
                    email,
                    password_hash,
                    procedure,
                    DOCTOR_APPROVAL_APPROVED,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
        else:
            connection.execute(
                """
                UPDATE doctors
                SET approval_status = ?, status_updated_at = COALESCE(NULLIF(status_updated_at, ''), ?)
                WHERE email = ?
                """,
                (DOCTOR_APPROVAL_APPROVED, timestamp, email),
            )

    user_ids = {
        email: get_seeded_row_id(connection, "users", email)
        for _, _, _, email in DEMO_USERS
    }
    doctor_ids = {
        email: get_seeded_row_id(connection, "doctors", email)
        for _, _, _, email, _ in DEMO_DOCTORS
    }
    return user_ids, doctor_ids


def demo_schedule_times(procedure: str, weekday: int, doctor_index: int) -> list[str]:
    # Demo grafikam ģenerē atšķirīgus laikus pēc procedūras un nedēļas dienas.
    if weekday == 6:
        return []

    if procedure == "datortomografija":
        base_times = ["09:00", "09:45", "10:30", "11:15", "12:00", "13:30", "14:15", "15:00"]
        if weekday in {1, 3}:
            base_times += ["16:00", "16:45", "17:30"]
    elif procedure == "vakcinacija":
        base_times = ["10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "14:00", "14:15", "14:30", "14:45"]
        if weekday in {0, 2, 4}:
            base_times += ["16:00", "16:15", "16:30", "16:45"]
    else:
        base_times = ["09:00", "09:30", "10:00", "10:30", "11:00", "13:00", "13:30", "14:00", "15:00", "15:30"]
        if weekday in {1, 3}:
            base_times += ["17:00", "17:30", "18:00"]

    if weekday == 5:
        base_times = [slot for slot in base_times if "10:00" <= slot <= "17:30"]

    if doctor_index % 2:
        return base_times[1:]
    return base_times[:-1]


def seed_demo_doctor_availability(
    connection: PostgresConnection,
    doctor_ids: dict[str, int],
) -> None:
    # Aizpilda demo ārstu pieejamības grafikus tuvākajam mēnesim.
    timestamp = now_iso()
    today = date.today()
    rows: list[tuple[int, str, str, str, str]] = []

    for doctor_index, (_, _, _, email, procedure) in enumerate(DEMO_DOCTORS):
        doctor_id = doctor_ids[email]
        for day_offset in range(0, 31):
            target_date = today + timedelta(days=day_offset)
            for available_time in demo_schedule_times(procedure, target_date.weekday(), doctor_index):
                rows.append((doctor_id, target_date.isoformat(), available_time, timestamp, timestamp))

    if rows:
        connection.executemany(
            """
            INSERT INTO doctor_availability (doctor_id, available_date, available_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (doctor_id, available_date, available_time)
            DO UPDATE SET updated_at = EXCLUDED.updated_at
            """,
            rows,
        )


def find_demo_slot(
    connection: PostgresConnection,
    doctor_id: int,
    day_offset: int,
    preferred_index: int,
) -> tuple[str, str]:
    # Atrod pirmo brīvo demo laiku, lai automātiski izveidotie pieraksti nepārklātos.
    for extra_days in range(0, 31):
        target_date = date.today() + timedelta(days=day_offset + extra_days)
        rows = connection.execute(
            """
            SELECT available_time
            FROM doctor_availability
            WHERE doctor_id = ? AND available_date = ?
            ORDER BY available_time ASC
            """,
            (doctor_id, target_date.isoformat()),
        ).fetchall()
        free_times = [
            row["available_time"]
            for row in rows
            if connection.execute(
                """
                SELECT id
                FROM appointments
                WHERE doctor_id = ? AND datums = ? AND laiks = ?
                """,
                (doctor_id, target_date.isoformat(), row["available_time"]),
            ).fetchone() is None
        ]
        if free_times:
            return target_date.isoformat(), free_times[preferred_index % len(free_times)]

    raise RuntimeError(f"No demo availability found for doctor {doctor_id}")


def seed_demo_appointments(
    connection: PostgresConnection,
    user_ids: dict[str, int],
    doctor_ids: dict[str, int],
) -> None:
    # Izveido demo pacientu pierakstus pie dažādiem ārstiem un procedūrām.
    timestamp = now_iso()
    plans = [
        (0, 0, 0, 1, "Profilaktiska apskate un asinsspiediena kontrole."),
        (0, 1, 5, 3, "Datortomografija ar kontrastvielu."),
        (0, 2, 10, 5, "Papildu vakcinacijas konsultacija."),
        (1, 3, 1, 2, "Gimenes arsta konsultacija par muguras sapem."),
        (1, 4, 6, 4, "CT izmeklejums pec arsta nosutijuma."),
        (1, 5, 11, 6, "Vakcinacija pret hepatitu A."),
        (2, 6, 2, 3, "Konsultacija par hronisku nogurumu."),
        (2, 7, 7, 5, "Vedera dobuma CT izmeklejums."),
        (2, 8, 12, 7, "Gripas vakcinacija pirms brauciena."),
        (3, 9, 3, 4, "Akuta konsultacija par saaukstesanos."),
        (3, 10, 8, 6, "Kontroles datortomografija pec traumas."),
        (3, 11, 13, 8, "Celojuma vakcinacijas konsultacija."),
        (4, 12, 4, 5, "Gimenes arsta nosutijuma apspriesana."),
        (4, 13, 9, 7, "Galvas CT izmeklejums."),
        (4, 14, 14, 9, "Erchu encefalita revakcinacija."),
        (5, 15, 0, 6, "Profilaktiska veselibas parbaude."),
        (5, 16, 5, 8, "Plausu CT izmeklejums."),
        (5, 17, 10, 10, "Difterijas un stingumkrampju vakcina."),
        (6, 18, 1, 7, "Gimenes arsta konsultacija par analizem."),
        (6, 19, 6, 9, "Mugurkaula datortomografija."),
        (6, 20, 11, 11, "Vakcinacijas kalendara papildinasana."),
        (7, 21, 2, 8, "Konsultacija par terapijas turpinajumu."),
        (7, 22, 7, 10, "Krusu kurvja CT izmeklejums."),
        (7, 23, 12, 12, "Pneimokoku vakcina."),
        (8, 24, 3, 9, "Gimenes arsta vizite pec saslimsanas."),
        (8, 25, 8, 11, "CT kontrole pec operacijas."),
        (8, 26, 13, 13, "Gripas vakcinacija."),
        (9, 27, 4, 10, "Profilaktiska konsultacija un analizu rezultati."),
        (9, 28, 9, 12, "Datortomografija deguna blakusdobumiem."),
        (9, 29, 14, 14, "Revakcinacija pec iepriekseja pieraksta."),
    ]

    for user_index, doctor_index, doctor_list_index, day_offset, comment in plans:
        user = DEMO_USERS[user_index]
        doctor = DEMO_DOCTORS[doctor_list_index]
        user_id = user_ids[user[3]]
        doctor_id = doctor_ids[doctor[3]]
        procedure = doctor[4]
        existing_active = connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE user_id = ? AND procedura = ? AND datums >= ?
            ORDER BY datums ASC, laiks ASC
            LIMIT 1
            """,
            (user_id, procedure, date.today().isoformat()),
        ).fetchone()
        if existing_active is not None:
            continue

        datums, laiks = find_demo_slot(connection, doctor_id, day_offset, doctor_index)
        location_options = DEMO_LOCATIONS_BY_PROCEDURE[procedure]
        adrese = location_options[(user_index + doctor_index) % len(location_options)]

        if connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE user_id = ? AND doctor_id = ? AND datums = ? AND laiks = ?
            """,
            (user_id, doctor_id, datums, laiks),
        ).fetchone() is not None:
            continue

        connection.execute(
            """
            INSERT INTO appointments (
                user_id, doctor_id, name, surname, phone, email, procedura, datums,
                laiks, adrese, comment, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                doctor_id,
                user[0],
                user[1],
                user[2],
                user[3],
                procedure,
                datums,
                laiks,
                adrese,
                comment,
                timestamp,
                timestamp,
            ),
        )


def seed_demo_data(connection: PostgresConnection) -> None:
    # Vienā solī sagatavo demo kontus, ārstu grafikus un pierakstus.
    user_ids, doctor_ids = seed_demo_accounts(connection)
    seed_demo_doctor_availability(connection, doctor_ids)
    seed_demo_appointments(connection, user_ids, doctor_ids)


def get_db() -> PostgresConnection:
    # Viena pieprasījuma laikā atkārtoti izmanto to pašu datubāzes savienojumu.
    if "db" not in g:
        g.db = PostgresConnection()
    return g.db


@app.teardown_appcontext
def close_db(_: BaseException | None) -> None:
    # Pēc pieprasījuma beigām aizver datubāzes savienojumu.
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    # Inicializē tabulas, indeksus un sākotnējos datus, ja tie vēl nav izveidoti.
    connection = PostgresConnection()
    services_seed, prices_seed = load_catalog_data()
    about_seed = load_about_data()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            password_updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            procedure TEXT NOT NULL,
            approval_status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL,
            password_updated_at TEXT NOT NULL,
            status_updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS doctor_availability (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            doctor_id INTEGER NOT NULL,
            available_date TEXT NOT NULL,
            available_time TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
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
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            service_name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            title TEXT NOT NULL,
            service_name TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
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
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
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

        CREATE UNIQUE INDEX IF NOT EXISTS idx_doctor_availability_slot
        ON doctor_availability (doctor_id, available_date, available_time);
        """
    )

    def table_exists(table_name: str) -> bool:
        return connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table_name,),
        ).fetchone() is not None

    def table_columns(table_name: str) -> set[str]:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table_name,),
        ).fetchall()
        return {row[0] for row in rows}

    appointment_columns = table_columns("appointments")
    if "doctor_id" not in appointment_columns:
        connection.execute("ALTER TABLE appointments ADD COLUMN doctor_id INTEGER")

    doctor_columns = table_columns("doctors")
    if "approval_status" not in doctor_columns:
        connection.execute(
            "ALTER TABLE doctors ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'"
        )
    if "status_updated_at" not in doctor_columns:
        connection.execute(
            "ALTER TABLE doctors ADD COLUMN status_updated_at TEXT NOT NULL DEFAULT ''"
        )

    connection.execute(
        """
        UPDATE doctors
        SET approval_status = ?
        WHERE approval_status IS NULL
           OR TRIM(approval_status) = ''
           OR approval_status NOT IN (?, ?, ?)
        """,
        (
            DOCTOR_APPROVAL_APPROVED,
            DOCTOR_APPROVAL_PENDING,
            DOCTOR_APPROVAL_APPROVED,
            DOCTOR_APPROVAL_CANCELLED,
        ),
    )
    connection.execute(
        """
        UPDATE doctors
        SET status_updated_at = COALESCE(NULLIF(status_updated_at, ''), created_at, password_updated_at, ?)
        WHERE status_updated_at IS NULL OR TRIM(status_updated_at) = ''
        """,
        (now_iso(),),
    )

    if table_exists("about_content"):
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
    else:
        existing_prices = {
            (row["title"], row["service_name"])
            for row in connection.execute("SELECT title, service_name FROM prices").fetchall()
        }
        missing_prices = [
            (title, service_name, price)
            for title, service_name, price in prices_seed
            if (title, service_name) not in existing_prices
        ]
        if missing_prices:
            timestamp = now_iso()
            connection.executemany(
                """
                INSERT INTO prices (title, service_name, price, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (title, service_name, price, timestamp, timestamp)
                    for title, service_name, price in missing_prices
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

    seed_demo_data(connection)

    connection.commit()
    connection.close()


def row_to_dict(row: DbRow) -> dict[str, Any]:
    # Datubāzes rindu pārveido par vārdnīcu JSON atbildēm.
    return {key: row[key] for key in row.keys()}


def login_required(view):
    # Dekorators API maršrutiem, kuriem vajadzīgs jebkurš ielogots konts.
    @wraps(view)
    def wrapped(*args, **kwargs):
        account = current_account()
        if account is None:
            return jsonify({"error": "Authentication required"}), 401
        return view(account, *args, **kwargs)

    return wrapped


def patient_required(view):
    # Dekorators maršrutiem, kurus drīkst izmantot tikai pacients.
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
    # Dekorators maršrutiem, kurus drīkst izmantot tikai apstiprināts ārsts.
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
    # Dekorators administratora API aizsardzībai.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Admin authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index() -> Any:
    # Galvenā lapa tiek pasniegta kā statisks HTML fails.
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/assets/<path:filename>")
def assets(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "assets", filename)


@app.route("/images/<path:filename>")
def images(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "images", filename)


@app.route("/<path:filename>")
def pages(filename: str) -> Any:
    # Pirms HTML lapas atdošanas pārbauda, vai lietotājam ir tiesības to skatīt.
    account = current_account()

    if filename in ACCOUNT_ONLY_PAGES and account is None:
        return redirect(url_for("pages", filename="login.html"))

    if filename in PATIENT_ONLY_PAGES:
        if account is None:
            return redirect(url_for("pages", filename="login.html"))
        if account["role"] != "user":
            return redirect(url_for("pages", filename="user_cab.html"))

    if filename in DOCTOR_ONLY_PAGES:
        if account is None:
            return redirect(url_for("pages", filename="login.html"))
        if account["role"] != "doctor":
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
    # Reģistrē jaunu pacientu un paroli glabā tikai hash veidā.
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
    # Ārsta reģistrācija izveido kontu ar statusu "pending", līdz administrators to apstiprina.
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
        INSERT INTO doctors (
            name,
            surname,
            phone,
            email,
            password_hash,
            procedure,
            approval_status,
            created_at,
            password_updated_at,
            status_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            procedure,
            DOCTOR_APPROVAL_PENDING,
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    db.commit()

    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(
        {
            "message": "Doctor registration successful. Waiting for admin approval.",
            "user": public_doctor_dict(doctor),
        }
    ), 201


@app.post("/api/login")
def api_login() -> Any:
    # Ielogo pacientu vai ārstu, pārbaudot paroli un konta lomu.
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
    if not doctor_has_access(doctor):
        return jsonify({"error": doctor_access_denied_message(doctor["approval_status"])}), 403

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
    # Lietotājs vai ārsts var labot savus profila datus.
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
    # Pacientam rāda viņa pierakstus, bet ārstam - pacientu pierakstus pie šī ārsta.
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
    # Pacients drīkst atcelt tikai savus pierakstus.
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


@app.get("/api/doctor/schedule")
@doctor_required
def api_doctor_schedule(account: dict[str, Any]) -> Any:
    # Ārsts var ielādēt mēneša kopsavilkumu vai konkrētas dienas grafiku.
    month_value = str(request.args.get("month", "")).strip()
    date_value = str(request.args.get("date", "")).strip()

    if month_value:
        month_range = parse_month_value(month_value)
        if month_range is None:
            return jsonify({"error": "Lūdzu izvēlieties korektu mēnesi."}), 400

        month_start, month_end = month_range
        today = date.today()
        max_date = add_months(today, 3)
        if month_end < today or month_start > max_date:
            return jsonify({"error": "Grafiku var plānot tikai no šī brīža līdz 3 mēnešiem uz priekšu."}), 400

        return jsonify(
            {
                "month": month_value,
                "days": build_doctor_month_schedule_summary(
                    account["id"],
                    month_start,
                    month_end,
                ),
            }
        )

    if date_value:
        target_date = parse_iso_date(date_value)
        if target_date is None:
            return jsonify({"error": "Lūdzu izvēlieties korektu datumu."}), 400

        booking_window_error = validate_booking_window(target_date)
        if booking_window_error:
            return jsonify({"error": booking_window_error}), 400

        return jsonify(build_doctor_day_schedule_payload(account["id"], target_date))

    return jsonify({"error": "Lūdzu norādiet datumu vai mēnesi."}), 400


@app.put("/api/doctor/schedule")
@doctor_required
def api_update_doctor_schedule(account: dict[str, Any]) -> Any:
    # Ārsts saglabā dienas pieejamos laikus; jau aizņemtie laiki netiek izdzēsti.
    payload = request.get_json(silent=True) or {}
    date_value = str(payload.get("date", "")).strip()
    raw_times = payload.get("available_times", [])

    target_date = parse_iso_date(date_value)
    if target_date is None:
        return jsonify({"error": "Lūdzu izvēlieties korektu datumu."}), 400

    booking_window_error = validate_booking_window(target_date)
    if booking_window_error:
        return jsonify({"error": booking_window_error}), 400

    working_hours = get_working_hours_for_date(target_date)
    if working_hours is None:
        return jsonify({"error": "Svētdienās grafiku plānot nevar, jo klīnika ir slēgta."}), 400

    if not isinstance(raw_times, list):
        return jsonify({"error": "Pieejamajiem laikiem jābūt sarakstā."}), 400

    normalized_times: set[str] = set()
    for raw_time in raw_times:
        time_value = str(raw_time).strip()
        time_error = validate_appointment_schedule(date_value, time_value)
        if time_error:
            return jsonify({"error": time_error}), 400
        normalized_times.add(time_value)

    booked_times = set(get_doctor_booked_times(account["id"], date_value))
    final_times = sorted(normalized_times | booked_times)

    timestamp = now_iso()
    db = get_db()
    db.execute(
        """
        DELETE FROM doctor_availability
        WHERE doctor_id = ? AND available_date = ?
        """,
        (account["id"], date_value),
    )

    if final_times:
        db.executemany(
            """
            INSERT INTO doctor_availability (
                doctor_id, available_date, available_time, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (account["id"], date_value, time_value, timestamp, timestamp)
                for time_value in final_times
            ],
        )

    db.commit()
    return jsonify(build_doctor_day_schedule_payload(account["id"], target_date))


@app.get("/api/doctors/<int:doctor_id>/available-slots")
@patient_required
def api_doctor_available_slots(account: dict[str, Any], doctor_id: int) -> Any:
    # Pacienta formai atgriež konkrēta ārsta brīvos laikus izvēlētajā datumā.
    del account
    procedura = str(request.args.get("procedura", "")).strip()
    date_value = str(request.args.get("date", "")).strip()

    if not procedura or not is_valid_doctor_procedure(procedura):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    target_date = parse_iso_date(date_value)
    if target_date is None:
        return jsonify({"error": "Lūdzu izvēlieties korektu datumu."}), 400

    booking_window_error = validate_booking_window(target_date)
    if booking_window_error:
        return jsonify({"error": booking_window_error}), 400

    doctor = validate_appointment_doctor(doctor_id, procedura)
    if doctor is None:
        return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 404

    if get_working_hours_for_date(target_date) is None:
        return jsonify({"date": date_value, "available_times": []})

    schedule_payload = build_doctor_day_schedule_payload(doctor["id"], target_date)
    return jsonify(
        {
            "date": date_value,
            "available_times": schedule_payload["open_times"],
        }
    )


@app.get("/api/doctors/<int:doctor_id>/available-dates")
@patient_required
def api_doctor_available_dates(account: dict[str, Any], doctor_id: int) -> Any:
    # Pacienta formai atgriež datumus, kuros izvēlētajam ārstam vēl ir brīvi laiki.
    del account
    procedura = str(request.args.get("procedura", "")).strip()

    if not procedura or not is_valid_doctor_procedure(procedura):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    doctor = validate_appointment_doctor(doctor_id, procedura)
    if doctor is None:
        return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 404

    return jsonify(
        {
            "doctor_id": doctor["id"],
            "available_dates": get_doctor_open_dates(doctor["id"]),
        }
    )


@app.get("/api/catalog")
def api_catalog() -> Any:
    # Publiskajām lapām atgriež pakalpojumus kopā ar cenām un lapas metadatiem.
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
    # Publiskajai "Par mums" lapai atgriež administrējamu saturu.
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
    # Pieraksta formai atgriež tikai izvēlētajai procedūrai atbilstošus ārstus.
    procedura = str(request.args.get("procedura", "")).strip()
    if not procedura:
        return jsonify([])

    if not is_valid_doctor_procedure(procedura):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    rows = get_db().execute(
        """
        SELECT id, name, surname, procedure
        FROM doctors
        WHERE procedure = ? AND approval_status = ?
        ORDER BY surname COLLATE NOCASE ASC, name COLLATE NOCASE ASC, id ASC
        """,
        (procedura, DOCTOR_APPROVAL_APPROVED),
    ).fetchall()
    return jsonify([public_doctor_option_dict(row) for row in rows])


@app.post("/api/chatbot")
def api_chatbot() -> Any:
    # Saņem lietotāja jautājumu un atbild ar lokālo vai OpenAI čatbota atbildi.
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
    # Saglabā kontaktformas ziņojumu gan viesiem, gan ielogotiem kontiem.
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
    # Paroles maiņa pārbauda veco paroli un saglabā tikai jaunu hash vērtību.
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
    # Izveido pacienta pierakstu, pārbaudot procedūru, ārstu, datumu un brīvo laiku.
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

    timestamp = now_iso()
    db = get_db()
    try:
        db.execute("BEGIN")

        doctor = validate_appointment_doctor(raw_doctor_id, procedura)
        if doctor is None:
            db.rollback()
            return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 400

        existing_appointment = find_active_procedure_appointment(
            "user",
            account["id"],
            procedura,
        )
        if existing_appointment is not None:
            db.rollback()
            return jsonify({"error": APPOINTMENT_DUPLICATE_MESSAGE}), 409

        slot_error, slot_status = validate_doctor_slot_selection(
            doctor["id"],
            datums,
            laiks,
        )
        if slot_error:
            db.rollback()
            return jsonify({"error": slot_error}), slot_status or 400

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
    except DatabaseError:
        db.rollback()
        raise

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
    # Administratora pieteikšanās izmanto atsevišķus konfigurācijas datus.
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
    # Administratora sesija tiek notīrīta atsevišķi no pacienta/ārsta sesijas.
    session.pop("is_admin", None)
    return jsonify({"message": "Admin logged out"})


@app.get("/api/admin/users")
@admin_required
def api_admin_users() -> Any:
    # Admin panelim atgriež visus pacientu kontus.
    rows = get_db().execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([public_user_dict(row) for row in rows])


@app.post("/api/admin/users")
@admin_required
def api_admin_create_user() -> Any:
    # Administrators var manuāli izveidot pacienta kontu.
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
    # Dzēš pacienta kontu pēc administratora pieprasījuma.
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"message": "User deleted"})


@app.put("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_update_user(user_id: int) -> Any:
    # Administrators var labot pacienta datus un pēc vajadzības nomainīt paroli.
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
    # Admin panelim atgriež visus ārstu kontus.
    rows = get_db().execute(
        "SELECT * FROM doctors ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([public_doctor_dict(row) for row in rows])


@app.post("/api/admin/doctors")
@admin_required
def api_admin_create_doctor() -> Any:
    # Administrators var izveidot ārsta kontu un uzreiz noteikt tā statusu.
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedure = str(payload.get("procedure", "")).strip()
    approval_status = str(
        payload.get("approval_status", DOCTOR_APPROVAL_APPROVED)
    ).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not all([name, email, procedure, password]):
        return jsonify({"error": "Name, email, procedure and password are required"}), 400

    if not is_valid_doctor_procedure(procedure):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400
    if not is_valid_doctor_approval_status(approval_status):
        return jsonify({"error": "Lūdzu izvēlieties korektu ārsta statusu."}), 400

    db = get_db()
    if doctor_email_exists(email):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    cursor = db.execute(
        """
        INSERT INTO doctors (
            name,
            surname,
            phone,
            email,
            password_hash,
            procedure,
            approval_status,
            created_at,
            password_updated_at,
            status_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            surname,
            phone,
            email,
            generate_password_hash(password),
            procedure,
            approval_status,
            timestamp,
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
    # Dzēšot ārstu, esošie pieraksti netiek dzēsti, bet tiek atsaistīti no ārsta.
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
    # Labo ārsta profilu; ja mainās specializācija vai statuss, pieraksti tiek atsaistīti.
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    procedure = str(payload.get("procedure", "")).strip()
    approval_status = str(payload.get("approval_status", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not all([name, email, procedure]):
        return jsonify({"error": "Name, email and procedure are required"}), 400

    if not is_valid_doctor_procedure(procedure):
        return jsonify({"error": "Lūdzu izvēlieties korektu procedūru."}), 400

    db = get_db()
    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    if not approval_status:
        approval_status = doctor["approval_status"]
    if not is_valid_doctor_approval_status(approval_status):
        return jsonify({"error": "Lūdzu izvēlieties korektu ārsta statusu."}), 400

    if doctor_email_exists(email, exclude_doctor_id=doctor_id):
        return jsonify({"error": "Doctor with this email already exists"}), 409

    timestamp = now_iso()
    password_hash = doctor["password_hash"]
    password_updated_at = doctor["password_updated_at"]
    procedure_changed = doctor["procedure"] != procedure
    status_changed = doctor["approval_status"] != approval_status
    status_updated_at = doctor["status_updated_at"]
    deactivate_doctor = (
        doctor["approval_status"] == DOCTOR_APPROVAL_APPROVED
        and approval_status != DOCTOR_APPROVAL_APPROVED
    )
    if password:
        password_hash = generate_password_hash(password)
        password_updated_at = timestamp
    if status_changed:
        status_updated_at = timestamp

    db.execute(
        """
        UPDATE doctors
        SET name = ?, surname = ?, phone = ?, email = ?, password_hash = ?, procedure = ?, approval_status = ?, password_updated_at = ?, status_updated_at = ?
        WHERE id = ?
        """,
        (
            name,
            surname,
            phone,
            email,
            password_hash,
            procedure,
            approval_status,
            password_updated_at,
            status_updated_at,
            doctor_id,
        ),
    )
    if procedure_changed or deactivate_doctor:
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


@app.put("/api/admin/doctors/<int:doctor_id>/status")
@admin_required
def api_admin_update_doctor_status(doctor_id: int) -> Any:
    # Ātri maina ārsta apstiprinājuma statusu no admin paneļa.
    payload = request.get_json(silent=True) or {}
    approval_status = str(payload.get("approval_status", "")).strip().lower()

    if not is_valid_doctor_approval_status(approval_status):
        return jsonify({"error": "Lūdzu izvēlieties korektu ārsta statusu."}), 400

    db = get_db()
    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    if doctor["approval_status"] == approval_status:
        return jsonify(public_doctor_dict(doctor))

    timestamp = now_iso()
    db.execute(
        """
        UPDATE doctors
        SET approval_status = ?, status_updated_at = ?
        WHERE id = ?
        """,
        (approval_status, timestamp, doctor_id),
    )

    if (
        doctor["approval_status"] == DOCTOR_APPROVAL_APPROVED
        and approval_status != DOCTOR_APPROVAL_APPROVED
    ):
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
    # Admin panelim atgriež "Par mums" lapas rediģējamos ierakstus.
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
    # Atjaunina vienu "Par mums" satura ierakstu.
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
    # Admin panelī parāda visus kontaktformas ziņojumus.
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
    # Administrators var dzēst apstrādātus vai nevajadzīgus ziņojumus.
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
    # Atgriež visus pakalpojumus admin paneļa sarakstam.
    rows = get_db().execute(
        "SELECT * FROM services ORDER BY id ASC"
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/admin/services")
@admin_required
def api_admin_create_service() -> Any:
    # Izveido jaunu pakalpojumu kategoriju.
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
    # Dzēšot pakalpojumu, dzēš arī ar to saistītās cenas.
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
    # Atjaunina pakalpojuma nosaukumu un sinhronizē šo nosaukumu cenu tabulā.
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
    # Atgriež visus cenu ierakstus admin panelim.
    rows = get_db().execute(
        "SELECT * FROM prices ORDER BY id ASC"
    ).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/admin/prices")
@admin_required
def api_admin_create_price() -> Any:
    # Izveido jaunu cenu konkrētam pakalpojumam.
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
    # Dzēš vienu cenu ierakstu.
    db = get_db()
    db.execute("DELETE FROM prices WHERE id = ?", (price_id,))
    db.commit()
    return jsonify({"message": "Price deleted"})


@app.put("/api/admin/prices/<int:price_id>")
@admin_required
def api_admin_update_price(price_id: int) -> Any:
    # Atjaunina cenu, pārbaudot, vai ievadītā vērtība tiešām ir skaitlis.
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
    # Admin panelim atgriež visus pierakstus kopā ar ārsta informāciju.
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
    # Administrators var labot pierakstu, bet sistēma joprojām pārbauda grafiku un konfliktus.
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
        "SELECT id, user_id, doctor_id, datums, laiks FROM appointments WHERE id = ?",
        (appointment_id,),
    ).fetchone()
    if appointment is None:
        return jsonify({"error": "Appointment not found"}), 404

    try:
        db.execute("BEGIN")

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
                db.rollback()
                return jsonify({"error": APPOINTMENT_DUPLICATE_MESSAGE}), 409

        raw_doctor_id = payload.get("doctor_id", appointment["doctor_id"])
        doctor = validate_appointment_doctor(raw_doctor_id, procedura)
        if raw_doctor_id not in (None, "") and doctor is None and "doctor_id" in payload:
            db.rollback()
            return jsonify({"error": "Lūdzu izvēlieties ārstējošo ārstu šai procedūrai."}), 400

        doctor_id = doctor["id"] if doctor is not None else None
        current_slot_unchanged = (
            doctor_id == appointment["doctor_id"]
            and datums == appointment["datums"]
            and laiks == appointment["laiks"]
        )

        if doctor_id is not None and not current_slot_unchanged:
            slot_error, slot_status = validate_doctor_slot_selection(
                doctor_id,
                datums,
                laiks,
                exclude_appointment_id=appointment_id,
            )
            if slot_error:
                db.rollback()
                return jsonify({"error": slot_error}), slot_status or 400

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
    except DatabaseError:
        db.rollback()
        raise

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
    # Dzēš pierakstu no admin paneļa.
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    db.commit()
    return jsonify({"message": "Appointment deleted"})


with app.app_context():
    init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
