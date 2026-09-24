import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
import datetime
import secrets
import hmac
import uuid
import json
from copy import deepcopy
from urllib.parse import urlparse, parse_qs
import streamlit.components.v1 as components
from html import escape

# Configuración básica
st.set_page_config(page_title="FisioSesión", layout="wide", initial_sidebar_state="expanded")

# =============================================================
# CONEXIÓN Y SEGURIDAD ANTI-BORRADO
# =============================================================
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_conn()

# Bandera de seguridad: se reinicia cada vez que carga la app.
if 'gsheets_read_error' not in st.session_state:
    st.session_state.gsheets_read_error = False

st.session_state.gsheets_read_error = False 

# VARIABLES GLOBALES
APP_URL = "https://xj2xjmcpyuweucfq3b7axg.streamlit.app"  
CATEGORIAS_EJ = ["CORE", "EEII", "EESS", "Estiramientos y movilidad"]
CATEGORIAS_DB = ["CORE", "EEII", "EEII (3FE)", "EEII (H-H)", "EESS", "Estiramientos y movilidad"]

def get_main_category(cat_str):
    """Devuelve la categoría principal para agrupar (ej: 'EEII (3FE)' -> 'EEII')"""
    if not cat_str: return ""
    s = str(cat_str)
    if s.startswith("EEII"): return "EEII"
    return s

ACCESS_CODE_LENGTH = 10
ACCESS_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 10

# =============================================================
# INYECCIÓN DE CSS
# =============================================================
estilo_css = """
<style>
    :root {
        --ink: #17352e; --muted: #64756e; --green: #13765d;
        --dark: #103d33; --mint: #e9f6f0; --line: #dce7e2;
        --bg: #f6f8f6; --danger: #aa3838;
    }
    .stApp { background-color: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif; }
    h1, h2, h3, h4, p, span, label { color: var(--ink) !important; }
    button[data-testid="baseButton-primary"], button[data-testid="stBaseButton-primary"], .stButton > button[kind="primary"] { background-color: var(--green) !important; color: white !important; border-color: var(--green) !important; border-radius: 9px !important; }
    /* A partir de aquí, todo va dirigido SOLO al botón de vídeo de sesiones clínicas (key empieza por "v_ses_"), usando la clase que Streamlit genera a partir de la key. No afecta a ningún otro botón de la app. */
    div[class*="st-key-v_ses_"] button { padding: 0.35rem 0.9rem !important; font-size: 13px !important; width: auto !important; max-width: 115px !important; white-space: nowrap !important; }
    div[class*="st-key-v_ses_"].stButton { width: auto !important; display: inline-flex !important; }
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-v_ses_"]) { flex-wrap: nowrap !important; align-items: center !important; width: 100% !important; }
        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-v_ses_"]) > div { min-width: 0 !important; }
        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-v_ses_"]) > div:first-child { flex: 1 1 auto !important; width: auto !important; }
        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-v_ses_"]) > div:last-child { flex: 0 0 auto !important; width: auto !important; }
    }
    /* Comentario asociado al ejercicio: apariencia de bocadillo de cómic */
    div[class*="st-key-default_note_"] textarea {
        border: 2px solid #13765d !important;
        border-radius: 18px 18px 18px 5px !important;
        background: #fffef7 !important;
        padding: 14px 16px !important;
        box-shadow: 0 4px 12px rgba(16, 61, 51, 0.10) !important;
        min-height: 110px !important;
        position: relative !important;
    }
    div[class*="st-key-default_note_"] textarea:focus {
        border-color: #103d33 !important;
        box-shadow: 0 0 0 2px rgba(19, 118, 93, 0.12), 0 5px 14px rgba(16, 61, 51, 0.12) !important;
    }
    div[class*="st-key-default_note_"] {
        position: relative !important;
    }
    .stTextInput input, .stTextArea textarea, .stMultiSelect div[data-baseweb="select"], .stSelectbox div[data-baseweb="select"] { border: 1px solid var(--line) !important; border-radius: 9px !important; }
    [data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 15px !important; }
    [data-testid="stForm"] { border: 1px solid var(--line); border-radius: 12px; padding: 20px; background: white;}
    section[data-testid="stSidebar"] { background-color: white; border-right: 1px solid var(--line); }
    .stRadio p { font-size: 16px !important; font-weight: 500 !important; }
</style>
"""
st.markdown(estilo_css, unsafe_allow_html=True)

# Estado de sesión de usuario
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'logged_pin' not in st.session_state:
    st.session_state.logged_pin = None
if 'editing_sesion_id' not in st.session_state:
    st.session_state.editing_sesion_id = None
if 'editing_program_id' not in st.session_state:
    st.session_state.editing_program_id = None
if 'failed_login_attempts' not in st.session_state:
    st.session_state.failed_login_attempts = 0
if 'login_locked_until' not in st.session_state:
    st.session_state.login_locked_until = None
if 'confirm_delete_patient_id' not in st.session_state:
    st.session_state.confirm_delete_patient_id = None
if 'confirm_delete_session_id' not in st.session_state:
    st.session_state.confirm_delete_session_id = None
if 'confirm_delete_program_id' not in st.session_state:
    st.session_state.confirm_delete_program_id = None

SHEET_URL = "https://docs.google.com/spreadsheets/d/1aoQuXwdTdY-AdcI6zetr5p2BbgN5gwxhBXbVQLhU0GI/edit"

# =============================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# =============================================================
def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    if s.lower() == "nan": return ""
    return s

ORDINALES_ES = ["Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta", "Séptima", "Octava", "Novena", "Décima"]
def ordinal_revision(n):
    if 1 <= n <= len(ORDINALES_ES):
        return f"{ORDINALES_ES[n-1]} revisión"
    return f"Revisión {n}"

def tiene_video_valido(url):
    """Comprueba que haya un enlace de vídeo real y no un simple texto de relleno (ej: 'a')."""
    u = str(url).strip()
    return u.lower().startswith("http")

# =============================================================
# GUARDADO ATÓMICO (evita que varios pacientes se pisen los datos
# si guardan casi a la vez, en vez de leer y reescribir la hoja entera)
# =============================================================
def _col_letter(n):
    """Convierte un número de columna (1, 2, 3...) en su letra de Google Sheets (A, B, C...)."""
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

@st.cache_resource
def get_ws(worksheet_name):
    """
    Devuelve (y reutiliza) el objeto de la hoja de Google Sheets. Abrir el documento
    entero (open_by_url) es la parte más lenta de todas, así que solo se hace una
    vez por hoja mientras la app esté funcionando, no cada vez que se guarda algo.
    """
    gc = conn._instance
    sh = gc.open_by_url(SHEET_URL)
    return sh.worksheet(worksheet_name)

@st.cache_data(ttl=300)
def get_ws_headers(worksheet_name, default_columns_tuple):
    try:
        ws = get_ws(worksheet_name)
        headers = ws.row_values(1)
        return headers if headers else list(default_columns_tuple)
    except Exception:
        return list(default_columns_tuple)

def atomic_append_row_by_dict(worksheet_name, row_dict, default_columns):
    """
    Añade una fila nueva directamente a la hoja (operación atómica de Google Sheets),
    sin leer ni reescribir el resto de filas. Así, si dos pacientes guardan casi al
    mismo tiempo, ninguno pisa el dato del otro. Si por lo que sea no se puede
    acceder así a la hoja, devuelve False para poder usar el guardado tradicional
    como respaldo (nunca se pierde el dato, solo se pierde esta protección extra).
    """
    try:
        headers = get_ws_headers(worksheet_name, tuple(default_columns))
        values = [str(row_dict.get(h, "")) for h in headers]
        ws = get_ws(worksheet_name)
        ws.append_row(values, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False

def atomic_upsert_row_by_dict(worksheet_name, key_column, key_value, row_dict, default_columns):
    """
    Actualiza (o crea si no existe) una única fila identificada por key_column/key_value,
    sin tocar el resto de la hoja. Pensado para datos que cambian a menudo por paciente
    (como el progreso de una sesión), evitando que varios pacientes se pisen entre sí.
    Devuelve False si no se puede, para recurrir al guardado tradicional como respaldo.
    """
    try:
        headers = get_ws_headers(worksheet_name, tuple(default_columns))
        values = [str(row_dict.get(h, "")) for h in headers]
        ws = get_ws(worksheet_name)

        # Para encontrar la fila usamos la lectura ya cacheada (rápida) en vez de
        # buscarla directamente en Google Sheets con ws.find() (mucho más lento).
        fila_encontrada = None
        try:
            df_actual = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=2)
            if not df_actual.empty and key_column in df_actual.columns:
                coincidencias = df_actual.index[df_actual[key_column].astype(str) == str(key_value)].tolist()
                if coincidencias:
                    fila_encontrada = coincidencias[0] + 2  # +1 por la cabecera, +1 porque las filas empiezan en 1
        except Exception:
            fila_encontrada = None

        if fila_encontrada:
            rango = f"A{fila_encontrada}:{_col_letter(len(headers))}{fila_encontrada}"
            ws.update(rango, [values])
        else:
            ws.append_row(values, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False

def normalize_access_code(value):
    return "".join(ch for ch in str(value).upper() if ch.isalnum())

def extract_pin_from_input(raw_value):
    """Si el paciente pega el enlace completo (con ?pin=...), nos quedamos solo con el código."""
    raw = str(raw_value).strip()
    if "pin=" in raw.lower():
        idx_pin = raw.lower().rfind("pin=")
        raw = raw[idx_pin + 4:]
    return raw

def access_code_matches(attempt, stored_code):
    normalized_attempt = normalize_access_code(attempt)
    normalized_stored_code = normalize_access_code(stored_code)
    return bool(normalized_attempt and normalized_stored_code) and hmac.compare_digest(normalized_attempt, normalized_stored_code)

def get_admin_access_code():
    try:
        return normalize_access_code(st.secrets["FISIO_ADMIN_PIN"])
    except Exception:
        return ""

def get_existing_access_codes():
    used_codes = set()
    for plan in plans:
        code = normalize_access_code(plan.get("pin", ""))
        if code:
            used_codes.add(code)
    for program in programs_af:
        code = normalize_access_code(program.get("pin", ""))
        if code:
            used_codes.add(code)
    return used_codes

def generate_unique_access_code():
    used_codes = get_existing_access_codes()
    for _ in range(100):
        code = "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(ACCESS_CODE_LENGTH))
        if code not in used_codes:
            return code
    raise RuntimeError("No se pudo generar un código de acceso único. Inténtalo de nuevo.")

def login_is_temporarily_locked():
    locked_until = st.session_state.login_locked_until
    if not locked_until:
        return False
    if datetime.datetime.now() >= locked_until:
        st.session_state.failed_login_attempts = 0
        st.session_state.login_locked_until = None
        return False
    return True

def register_failed_login():
    st.session_state.failed_login_attempts += 1
    if st.session_state.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        st.session_state.login_locked_until = datetime.datetime.now() + datetime.timedelta(minutes=LOGIN_LOCKOUT_MINUTES)

def reset_login_attempts():
    st.session_state.failed_login_attempts = 0
    st.session_state.login_locked_until = None

def get_patients():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="pacientes", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            revisions_raw = r.get("revisions", "[]")
            revisions = []
            if isinstance(revisions_raw, str) and revisions_raw.strip().startswith("["):
                try:
                    revisions = json.loads(revisions_raw)
                except Exception:
                    revisions = []

            # Migración automática: si el paciente tenía los datos antiguos (una sola ficha)
            # y todavía no tiene historial de revisiones, los convertimos en la primera revisión.
            if not revisions:
                old_ana = clean_str(r.get("anamnesis", ""))
                old_ins = clean_str(r.get("inspeccion", ""))
                old_mov = clean_str(r.get("movilidad", ""))
                old_fue = clean_str(r.get("fuerza", ""))
                if old_ana or old_ins or old_mov or old_fue:
                    revisions = [{
                        "date": "",
                        "anamnesis": old_ana, "inspeccion": old_ins,
                        "movilidad": old_mov, "fuerza": old_fue
                    }]

            records.append({
                "id": clean_str(r.get("id", "")), 
                "name": clean_str(r.get("name", "")), 
                "phone": clean_str(r.get("phone", "")),
                "lesion": clean_str(r.get("lesion", "")),
                "review_date": clean_str(r.get("review_date", "")),
                "revisions": revisions
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_patients(patients_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    formatted = []
    for p in patients_list:
        formatted.append({
            "id": p["id"], "name": p["name"], "phone": p.get("phone", ""),
            "lesion": p.get("lesion", ""),
            "review_date": p.get("review_date", ""),
            "revisions": json.dumps(p.get("revisions", []))
        })
    patient_columns = ["id", "name", "phone", "lesion", "review_date", "revisions"]
    conn.update(spreadsheet=SHEET_URL, worksheet="pacientes", data=pd.DataFrame(formatted, columns=patient_columns))
    st.cache_data.clear()

def get_exercises():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="ejercicios", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            records.append({
                "id": clean_str(r.get("id", "")), 
                "name": clean_str(r.get("name", "")), 
                "patientName": clean_str(r.get("patientName", "")),
                "videoUrl": clean_str(r.get("videoUrl", "")), 
                "category": clean_str(r.get("category", "")),
                "defaultNote": clean_str(r.get("defaultNote", ""))
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_exercises(exercises_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    exercise_columns = ["id", "name", "patientName", "videoUrl", "category", "defaultNote"]
    conn.update(spreadsheet=SHEET_URL, worksheet="ejercicios", data=pd.DataFrame(exercises_list, columns=exercise_columns))
    st.cache_data.clear()

def nombre_para_paciente(ex_data):
    """Devuelve el nombre alternativo del ejercicio si existe, o si no, el nombre original."""
    if not ex_data:
        return ""
    alternativo = ex_data.get("patientName", "").strip()
    return alternativo if alternativo else ex_data.get("name", "")

def get_general_instructions():
    """Carga el listado maestro de indicaciones generales."""
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="indicaciones_generales", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            text = clean_str(r.get("text", r.get("indicacion", "")))
            if text:
                records.append({"id": clean_str(r.get("id", "")), "text": text})
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_general_instructions(instructions_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: hubo un error de conexión con Google Sheets.")
        return
    conn.update(spreadsheet=SHEET_URL, worksheet="indicaciones_generales", data=pd.DataFrame(instructions_list, columns=["id", "text"]))
    st.cache_data.clear()

def get_plans():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="sesiones", ttl=600)
        if df.empty: return []
        plans = []
        for _, r in df.iterrows():
            ex_ids_raw = r.get("exerciseIds", "[]")
            if isinstance(ex_ids_raw, str) and ex_ids_raw.startswith("["):
                try: ex_ids = [clean_str(x) for x in json.loads(ex_ids_raw)]
                except: ex_ids = []
            else: ex_ids = []

            inst_raw = r.get("exerciseInstructions", "{}")
            if isinstance(inst_raw, str) and inst_raw.startswith("{"):
                try: cleaned_insts = {clean_str(k): v for k, v in json.loads(inst_raw).items()}
                except: cleaned_insts = {}
            else: cleaned_insts = {}

            plans.append({
                "id": clean_str(r.get("id", "")), 
                "patientId": clean_str(r.get("patientId", "")), 
                "title": clean_str(r.get("title", "")),
                "exerciseIds": ex_ids, 
                "exerciseInstructions": cleaned_insts,
                "generalInstructionIds": json.loads(r.get("generalInstructionIds", "[]")) if isinstance(r.get("generalInstructionIds", "[]"), str) and r.get("generalInstructionIds", "[]").startswith("[") else [],
                "pin": clean_str(r.get("pin", "")),
                "startDate": clean_str(r.get("startDate", "")),
                "isActive": (clean_str(r.get("isActive", "")).lower() in ("true", "1", "si", "sí")) if clean_str(r.get("isActive", "")) else None
            })
        return plans
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_plans(plans_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    formatted = []
    for p in plans_list:
        formatted.append({
            "id": p["id"], "patientId": p["patientId"], "title": p["title"],
            "exerciseIds": json.dumps(p["exerciseIds"]), 
            "exerciseInstructions": json.dumps(p["exerciseInstructions"]),
            "generalInstructionIds": json.dumps(p.get("generalInstructionIds", [])),
            "pin": p["pin"],
            "startDate": p.get("startDate", ""),
            "isActive": bool(p.get("isActive", True))
        })
    plan_columns = ["id", "patientId", "title", "exerciseIds", "exerciseInstructions", "generalInstructionIds", "pin", "startDate", "isActive"]
    conn.update(spreadsheet=SHEET_URL, worksheet="sesiones", data=pd.DataFrame(formatted, columns=plan_columns))
    st.cache_data.clear()

def get_programs_af():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="programas_af", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        programs = []
        for _, r in df.iterrows():
            days_raw = r.get("daysData", "[]")
            if isinstance(days_raw, str) and days_raw.startswith("["):
                try: days_data = json.loads(days_raw)
                except: days_data = []
            else: days_data = []

            programs.append({
                "id": clean_str(r.get("id", "")),
                "patientId": clean_str(r.get("patientId", "")),
                "title": clean_str(r.get("title", "")),
                "frequency": clean_str(r.get("frequency", "")),
                "duration": clean_str(r.get("duration", "")),
                "generalInstructionIds": json.loads(r.get("generalInstructionIds", "[]")) if isinstance(r.get("generalInstructionIds", "[]"), str) and r.get("generalInstructionIds", "[]").startswith("[") else [],
                "generalNote": clean_str(r.get("generalNote", "")),
                "pin": clean_str(r.get("pin", "")),
                "startDate": clean_str(r.get("startDate", "")),
                "daysData": days_data
            })
        return programs
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_programs_af(programs_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    formatted = []
    for p in programs_list:
        formatted.append({
            "id": p["id"], "patientId": p["patientId"], "title": p["title"],
            "frequency": p["frequency"], "duration": p["duration"],
            "generalInstructionIds": json.dumps(p.get("generalInstructionIds", [])),
            "generalNote": p["generalNote"], "pin": p["pin"],
            "startDate": p.get("startDate", ""),
            "daysData": json.dumps(p["daysData"])
        })
    program_columns = ["id", "patientId", "title", "frequency", "duration", "generalInstructionIds", "generalNote", "pin", "startDate", "daysData"]
    conn.update(spreadsheet=SHEET_URL, worksheet="programas_af", data=pd.DataFrame(formatted, columns=program_columns))
    st.cache_data.clear()

CHECKIN_COLUMNS = ["id", "planId", "date", "eva", "borg", "comment", "duration_min"]

def get_checkins():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="checkins", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            records.append({
                "id": clean_str(r.get("id", "")), 
                "planId": clean_str(r.get("planId", "")), 
                "date": clean_str(r.get("date", "")), 
                "eva": clean_str(r.get("eva", "")), 
                "borg": clean_str(r.get("borg", "")), 
                "comment": clean_str(r.get("comment", "")),
                "duration_min": clean_str(r.get("duration_min", ""))
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_checkins(checkins_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return False
    conn.update(spreadsheet=SHEET_URL, worksheet="checkins", data=pd.DataFrame(checkins_list, columns=CHECKIN_COLUMNS))
    st.cache_data.clear()
    return True

def save_checkin_item(plan_id, date, eva, borg, comment, duration_min=None):
    if st.session_state.gsheets_read_error:
        st.error("❌ Error de conexión temporal. Inténtalo de nuevo en unos segundos.")
        return
    row_dict = {
        "id": str(uuid.uuid4()), "planId": str(plan_id), "date": str(date),
        "eva": str(eva), "borg": str(borg), "comment": str(comment),
        "duration_min": "" if duration_min is None else str(duration_min)
    }
    # Guardado atómico (añade solo esta fila, sin tocar el resto) para que
    # varios pacientes puedan enviar su reporte a la vez sin pisarse.
    ok = atomic_append_row_by_dict("checkins", row_dict, CHECKIN_COLUMNS)
    if ok:
        st.cache_data.clear()
    else:
        # Respaldo: el método de guardado tradicional, por si el atómico falla.
        checkins_data = get_checkins()
        checkins_data.append(row_dict)
        save_checkins(checkins_data)

# =============================================================
# PROGRESO EN VIVO DE LA SESIÓN CLÍNICA (cronómetro + checks de ejercicios)
# Se guarda en una hoja aparte ("progreso_sesion") porque cambia muy a
# menudo (cada vez que el paciente marca un ejercicio), así que conviene
# no mezclarlo con la hoja de "sesiones" ni forzar una relectura de
# todas las demás hojas cada vez que se actualiza.
# =============================================================
PROGRESO_COLUMNS = ["planId", "opened_at", "checked_exercises"]
LIMITE_INACTIVIDAD_HORAS = 3

def get_progreso_sesion(plan_id):
    vacio = {"planId": str(plan_id), "opened_at": "", "checked_exercises": []}
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="progreso_sesion", ttl=2)
        if df.empty: return vacio
        df = df.dropna(how="all")
        for _, r in df.iterrows():
            if clean_str(r.get("planId", "")) == str(plan_id):
                raw_checks = clean_str(r.get("checked_exercises", "[]"))
                try:
                    checks = json.loads(raw_checks) if raw_checks.strip().startswith("[") else []
                except Exception:
                    checks = []
                return {"planId": str(plan_id), "opened_at": clean_str(r.get("opened_at", "")), "checked_exercises": checks}
        return vacio
    except Exception:
        return vacio

def guardar_progreso_sesion(plan_id, opened_at, checked_exercises):
    row_dict = {"planId": str(plan_id), "opened_at": opened_at, "checked_exercises": json.dumps(checked_exercises)}
    ok = atomic_upsert_row_by_dict("progreso_sesion", "planId", str(plan_id), row_dict, PROGRESO_COLUMNS)
    if not ok:
        # Respaldo: si no se puede hacer el guardado atómico, se intenta el
        # método tradicional. Si la hoja "progreso_sesion" todavía no existe,
        # simplemente no se guarda (no rompe la app, solo no persiste).
        try:
            df = conn.read(spreadsheet=SHEET_URL, worksheet="progreso_sesion", ttl=0)
            rows = [] if df.empty else df.to_dict("records")
            rows = [r for r in rows if clean_str(r.get("planId", "")) != str(plan_id)]
            rows.append(row_dict)
            conn.update(spreadsheet=SHEET_URL, worksheet="progreso_sesion", data=pd.DataFrame(rows, columns=PROGRESO_COLUMNS))
        except Exception:
            pass

# =============================================================
# CARGA DE DATOS
# =============================================================
patients = get_patients()
exercises = get_exercises()
for _exercise in exercises:
    _exercise.setdefault("defaultNote", "")
general_instructions = get_general_instructions()
plans = get_plans()
programs_af = get_programs_af()
checkins = get_checkins()

latest_plan_index = {}
for idx, plan in enumerate(plans):
    latest_plan_index[plan["patientId"]] = idx
for idx, plan in enumerate(plans):
    if plan.get("isActive") is None:
        plan["isActive"] = latest_plan_index.get(plan["patientId"]) == idx

def get_patient_name(p_id):
    for p in patients:
        if str(p["id"]) == str(p_id): return p["name"]
    return "Paciente Eliminado"

def calcular_semaforo_paciente(paciente, todos_los_planes, todos_los_checkins):
    """
    Calcula el estado del semáforo de adherencia para un paciente, a partir de una
    media ponderada de 5 variables (Tiempo, EVA, Subida de EVA, Borg y Frecuencia
    semanal). El EVA y el Tiempo tienen más peso que el resto. Aunque el resultado
    general salga verde, cualquier variable que esté en rojo se sigue mostrando en
    los motivos para que el fisio pueda revisarla igualmente.
    """
    p_id = str(paciente["id"])
    planes_paciente = [str(p["id"]) for p in todos_los_planes if str(p["patientId"]) == p_id]
    checkins_pac = [c for c in todos_los_checkins if str(c.get("planId")) in planes_paciente]

    def parse_date(c):
        try:
            return datetime.datetime.strptime(c["date"], "%Y-%m-%d %H:%M")
        except Exception:
            return datetime.datetime.min

    iconos = {"ROJO": "🔴", "AMARILLO": "🟡", "VERDE": "🟢"}
    colores_bg = {"ROJO": "#fdecec", "AMARILLO": "#fff8e1", "VERDE": "#e9f6f0"}
    colores_txt = {"ROJO": "#aa3838", "AMARILLO": "#f57f17", "VERDE": "#13765d"}

    def resultado(estado, motivos):
        return {"estado": estado, "icono": iconos[estado], "motivos": motivos,
                "bg_color": colores_bg[estado], "text_color": colores_txt[estado]}

    # Sin al menos 3 reportes, no hay datos suficientes para valorar ninguna
    # variable de forma fiable (ni siquiera EVA/Tiempo, para que el semáforo
    # arranque con criterio desde el principio).
    if len(checkins_pac) < 3:
        if planes_paciente:
            return resultado("AMARILLO", [f"Necesita al menos 3 reportes para calcular su adherencia (lleva {len(checkins_pac)})"])
        return resultado("VERDE", [])

    checkins_ordenados = sorted(checkins_pac, key=parse_date, reverse=True)
    ahora = datetime.datetime.now()
    checkins_7d = [c for c in checkins_ordenados if (ahora - parse_date(c)).days <= 7]

    motivos = []
    puntos_ponderados = 0.0
    peso_total = 0.0

    def registrar(score, peso, motivo_si_no_verde=None):
        nonlocal puntos_ponderados, peso_total
        puntos_ponderados += score * peso
        peso_total += peso
        if score < 2 and motivo_si_no_verde:
            motivos.append(motivo_si_no_verde)

    # --- 1. TIEMPO (duración de sesión, últimos 7 días) — peso alto ---
    duraciones_7d = []
    for c in checkins_7d:
        try:
            if str(c.get("duration_min", "")).strip() != "":
                duraciones_7d.append(float(c["duration_min"]))
        except (ValueError, TypeError):
            pass
    if duraciones_7d:
        if any(d < 30 for d in duraciones_7d):
            registrar(0, 2, "Alguna sesión de esta semana duró menos de 30 min")
        elif any(d <= 45 for d in duraciones_7d):
            registrar(1, 2, "Alguna sesión de esta semana duró entre 30 y 45 min")
        else:
            registrar(2, 2)

    # --- 2. EVA (nivel de dolor, últimos 7 días) — peso alto ---
    evas_7d = []
    for c in checkins_7d:
        try:
            evas_7d.append(float(c.get("eva", 0)))
        except (ValueError, TypeError):
            pass
    if evas_7d:
        peor_eva = max(evas_7d)
        if peor_eva >= 7:
            registrar(0, 2, f"Dolor alto en alguna sesión de esta semana (EVA {int(peor_eva)}/10)")
        elif peor_eva >= 4:
            registrar(1, 2, f"Dolor moderado en alguna sesión de esta semana (EVA {int(peor_eva)}/10)")
        else:
            registrar(2, 2)

    # --- 3. SUBIDA DE EVA (última sesión vs. penúltima) — peso normal ---
    try:
        eva_ultima = float(checkins_ordenados[0].get("eva", 0))
        eva_penultima = float(checkins_ordenados[1].get("eva", 0))
        delta_eva = eva_ultima - eva_penultima
        if delta_eva >= 2:
            registrar(0, 1, f"Subida de dolor entre las dos últimas sesiones (+{int(delta_eva)} puntos de EVA)")
        else:
            registrar(2, 1)
    except (ValueError, TypeError, IndexError):
        pass

    # --- 4. BORG (3 sesiones seguidas con Borg ≥ 8) — peso normal ---
    try:
        ultimas_3 = checkins_ordenados[:3]
        borgs_ultimas_3 = [float(c.get("borg", 0)) for c in ultimas_3]
        if len(borgs_ultimas_3) == 3 and all(b >= 8 for b in borgs_ultimas_3):
            registrar(0, 1, "Fatiga muy alta (Borg ≥8) en las últimas 3 sesiones seguidas")
        else:
            registrar(2, 1)
    except (ValueError, TypeError):
        pass

    # --- 5. FRECUENCIA (sesiones en los últimos 7 días, rodante) — peso normal ---
    n_checkins_7d = len(checkins_7d)
    if n_checkins_7d < 2:
        registrar(0, 1, f"Menos de 2 sesiones esta semana ({n_checkins_7d})")
    elif n_checkins_7d == 2:
        registrar(1, 1, "Solo 2 sesiones esta semana")
    else:
        registrar(2, 1)

    if peso_total == 0:
        return resultado("AMARILLO", ["No hay datos suficientes de esta semana para calcular la adherencia"])

    media = puntos_ponderados / peso_total
    if media >= 1.5:
        estado = "VERDE"
    elif media >= 0.75:
        estado = "AMARILLO"
    else:
        estado = "ROJO"

    return resultado(estado, motivos)

def get_exercise(e_id):
    for e in exercises:
        if str(e["id"]) == str(e_id): return e
    return None

def render_general_instructions_box(ids):
    texts = []
    for i_id in ids or []:
        for item in general_instructions:
            if str(item["id"]) == str(i_id):
                texts.append(item["text"])
                break
    if not texts:
        return
    lis = "".join(f"<li style='margin-bottom:8px;'>{text}</li>" for text in texts)
    st.markdown(f"""<div style='background:#fff; border:1px solid #dce7e2; border-left:5px solid #13765d; border-radius:14px; padding:18px 22px; margin:0 0 25px 0;'>
<div style='color:#13765d; font-size:14px; font-weight:800; text-transform:uppercase; letter-spacing:.8px; margin-bottom:10px;'>📌 Indicaciones generales</div>
<ul style='color:#17352e; margin:0; padding-left:22px; font-size:15px; line-height:1.55;'>{lis}</ul>
</div>""", unsafe_allow_html=True)

# =============================================================
# MÓDULO 1: ÁREA CLÍNICA
# =============================================================
if st.session_state.admin_mode:

    @st.dialog("✏️ Editar Sesión Clínica", width="large")
    def modal_editar_sesion(pl):
        pl_id = pl["id"]
        original_session_exercise_ids = set(pl.get("exerciseIds", []))
        
        pac_idx = 0
        patient_ids = [p["id"] for p in patients]
        if pl["patientId"] in patient_ids:
            pac_idx = patient_ids.index(pl["patientId"])
            
        paciente_sel = st.selectbox("1. Cambiar Paciente:", options=patient_ids, format_func=get_patient_name, index=pac_idx)
        titulo_sesion = st.text_input("2. Título de la Sesión:", value=pl["title"])
        
        st.markdown("**3. Selecciona los ejercicios:**")
        cf1, cf2 = st.columns(2)
        filtro_cat_ed = cf1.selectbox("Filtrar por Categoría:", ["Todas"] + CATEGORIAS_EJ, key=f"fcat_{pl_id}")
        filtro_subcat_ed = "Todos"
        if filtro_cat_ed == "EEII":
            filtro_subcat_ed = cf2.selectbox("Subcategoría EEII:", ["Todos", "EEII (General)", "EEII (3FE)", "EEII (H-H)"], key=f"fsub_{pl_id}")
            
        if f"edit_ses_{pl_id}_ejs" not in st.session_state:
            st.session_state[f"edit_ses_{pl_id}_ejs"] = pl["exerciseIds"].copy()

        nombres_actuales = []
        for eid in st.session_state[f"edit_ses_{pl_id}_ejs"]:
            eobj = get_exercise(eid)
            if eobj: nombres_actuales.append(f"{eobj['category']}  |  {eobj['name']}")
            
        ej_options_all = {}
        for cat in CATEGORIAS_DB:
            mostrar_cat = True
            if filtro_cat_ed != "Todas":
                if get_main_category(cat) != filtro_cat_ed:
                    mostrar_cat = False
                elif filtro_cat_ed == "EEII" and filtro_subcat_ed != "Todos":
                    if filtro_subcat_ed == "EEII (General)" and cat != "EEII": mostrar_cat = False
                    elif filtro_subcat_ed == "EEII (3FE)" and cat != "EEII (3FE)": mostrar_cat = False
                    elif filtro_subcat_ed == "EEII (H-H)" and cat != "EEII (H-H)": mostrar_cat = False
                    
            ej_cat = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
            for e in ej_cat:
                nk = f"{cat}  |  {e['name']}"
                if mostrar_cat or (nk in nombres_actuales):
                    ej_options_all[nk] = e['id']
                    
        selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options_all.keys()), default=nombres_actuales, label_visibility="collapsed")
        
        nuevos_ids = [ej_options_all[n] for n in selected_names]
        st.session_state[f"edit_ses_{pl_id}_ejs"] = [e for e in st.session_state[f"edit_ses_{pl_id}_ejs"] if e in nuevos_ids]
        for e in nuevos_ids:
            if e not in st.session_state[f"edit_ses_{pl_id}_ejs"]:
                st.session_state[f"edit_ses_{pl_id}_ejs"].append(e)

        opciones_ind = {item["text"]: item["id"] for item in general_instructions}
        default_ind = [item["text"] for item in general_instructions if item["id"] in pl.get("generalInstructionIds", [])]
        selected_ind = st.multiselect("**4. Indicaciones generales:**", options=list(opciones_ind.keys()), default=default_ind, key=f"edit_ses_ind_{pl_id}", placeholder="Selecciona las indicaciones para esta sesión...")
        selected_general_instruction_ids = [opciones_ind[x] for x in selected_ind]

        instrucciones_dict = {}
        if st.session_state[f"edit_ses_{pl_id}_ejs"]:
            st.markdown("**5. Configuración y Orden:**")
            for idx, e_id in enumerate(st.session_state[f"edit_ses_{pl_id}_ejs"]):
                ej_obj = get_exercise(e_id)
                ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                prev_inst = pl["exerciseInstructions"].get(e_id, {})
                
                c_t, c_s, c_r, c_n, c_up, c_dn = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                with c_t: 
                    st.markdown(f"<div style='margin-top:8px; font-size:14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx+1}. {ej_name}</div>", unsafe_allow_html=True)
                with c_s: 
                    s = st.text_input("S", value=prev_inst.get("series", ""), key=f"es_{pl_id}_{e_id}", label_visibility="collapsed", placeholder="Series")
                with c_r: 
                    r = st.text_input("R", value=prev_inst.get("reps", ""), key=f"er_{pl_id}_{e_id}", label_visibility="collapsed", placeholder="Reps")
                with c_n:
                    existing_note = prev_inst.get("notes", "")
                    if not existing_note and e_id not in original_session_exercise_ids:
                        existing_note = ej_obj.get("defaultNote", "") if ej_obj else ""
                    n = st.text_input("N", value=existing_note, key=f"en_{pl_id}_{e_id}", label_visibility="collapsed", placeholder="Notas")
                with c_up:
                    if st.button("⬆️", key=f"eup_{pl_id}_{e_id}") and idx > 0:
                        st.session_state[f"edit_ses_{pl_id}_ejs"][idx-1], st.session_state[f"edit_ses_{pl_id}_ejs"][idx] = st.session_state[f"edit_ses_{pl_id}_ejs"][idx], st.session_state[f"edit_ses_{pl_id}_ejs"][idx-1]
                        st.rerun()
                with c_dn:
                    if st.button("⬇️", key=f"edn_{pl_id}_{e_id}") and idx < len(st.session_state[f"edit_ses_{pl_id}_ejs"]) - 1:
                        st.session_state[f"edit_ses_{pl_id}_ejs"][idx+1], st.session_state[f"edit_ses_{pl_id}_ejs"][idx] = st.session_state[f"edit_ses_{pl_id}_ejs"][idx], st.session_state[f"edit_ses_{pl_id}_ejs"][idx+1]
                        st.rerun()
                        
                instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                
        st.write("")
        c_save, c_cancel = st.columns([2, 1])
        if c_save.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True):
            pl["patientId"] = paciente_sel
            pl["title"] = titulo_sesion
            pl["exerciseIds"] = st.session_state[f"edit_ses_{pl_id}_ejs"]
            pl["exerciseInstructions"] = instrucciones_dict
            pl["generalInstructionIds"] = selected_general_instruction_ids
            save_plans(plans)
            st.session_state.editing_sesion_id = None
            st.rerun()
        if c_cancel.button("❌ Cancelar", use_container_width=True):
            st.session_state.editing_sesion_id = None
            st.rerun()

    @st.dialog("✏️ Editar Programa de AF", width="large")
    def modal_editar_programa(pr):
        pr_id = pr["id"]
        
        pac_idx = [p["id"] for p in patients].index(pr["patientId"]) if pr["patientId"] in [p["id"] for p in patients] else 0
        
        c1, c2 = st.columns([1, 2])
        af_paciente = c1.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name, index=pac_idx)
        af_titulo = c2.text_input("2. Título del programa:", value=pr["title"])
        
        c3, c4 = st.columns(2)
        af_frecuencia = c3.text_input("3. Frecuencia semanal:", value=pr["frequency"])
        af_duracion = c4.text_input("4. Duración por sesión:", value=pr["duration"])
        opciones_ind_af = {item["text"]: item["id"] for item in general_instructions}
        default_ind_af = [item["text"] for item in general_instructions if item["id"] in pr.get("generalInstructionIds", [])]
        selected_ind_af = st.multiselect("**5. Indicaciones generales:**", options=list(opciones_ind_af.keys()), default=default_ind_af, key=f"edit_af_ind_{pr_id}", placeholder="Selecciona las indicaciones para este programa...")
        selected_general_instruction_ids_af = [opciones_ind_af[x] for x in selected_ind_af]
        af_nota = st.text_input("6. Nota general:", value=pr["generalNote"])
        
        st.divider()
        st.markdown("### 📅 Días y Bloques")
        
        if f"edit_af_{pr_id}_dias" not in st.session_state:
            st.session_state[f"edit_af_{pr_id}_dias"] = max(1, len(pr["daysData"]))

        cb1, cb2 = st.columns(2)
        if cb1.button("➕ Añadir Día al Plan"):
            st.session_state[f"edit_af_{pr_id}_dias"] += 1
            st.rerun()
        if cb2.button("➖ Quitar Último Día") and st.session_state[f"edit_af_{pr_id}_dias"] > 1:
            st.session_state[f"edit_af_{pr_id}_dias"] -= 1
            st.rerun()
            
        dias_construidos = []
        for d_idx in range(st.session_state[f"edit_af_{pr_id}_dias"]):
            st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
            
            def_d_title = pr["daysData"][d_idx]["dayTitle"] if d_idx < len(pr["daysData"]) else f"Día {d_idx+1}"
            d_titulo = st.text_input(f"Título del Día {d_idx+1}:", value=def_d_title, key=f"edit_dtit_{pr_id}_{d_idx}")
            
            if f"edit_af_{pr_id}_b_{d_idx}" not in st.session_state:
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] = max(1, len(pr["daysData"][d_idx].get("blocks", []))) if d_idx < len(pr["daysData"]) else 1
                
            cc1, cc2 = st.columns(2)
            if cc1.button(f"➕ Añadir Bloque al Día {d_idx+1}", key=f"eaddB_{pr_id}_{d_idx}"):
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] += 1
                st.rerun()
            if cc2.button(f"➖ Quitar Bloque al Día {d_idx+1}", key=f"esubB_{pr_id}_{d_idx}") and st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] > 1:
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] -= 1
                st.rerun()
                
            bloques_dia = []
            for b_idx in range(st.session_state[f"edit_af_{pr_id}_b_{d_idx}"]):
                with st.container(border=True):
                    old_block = None
                    if d_idx < len(pr["daysData"]) and b_idx < len(pr["daysData"][d_idx].get("blocks", [])):
                        old_block = pr["daysData"][d_idx]["blocks"][b_idx]
                        
                    def_cat = old_block.get("blockCategory") if old_block and old_block.get("blockCategory") in CATEGORIAS_EJ else CATEGORIAS_EJ[0]
                    def_rule = old_block.get("blockRule", "") if old_block else ""
                    
                    c_cat, c_sub, c_reg = st.columns([1.2, 1.2, 2])
                    b_cat = c_cat.selectbox("Categoría:", CATEGORIAS_EJ, index=CATEGORIAS_EJ.index(def_cat), key=f"ebcat_{pr_id}_{d_idx}_{b_idx}")
                    b_subcat = "Todos"
                    if b_cat == "EEII":
                        b_subcat = c_sub.selectbox("Filtro EEII:", ["Todos", "EEII (General)", "EEII (3FE)", "EEII (H-H)"], key=f"ebsub_{pr_id}_{d_idx}_{b_idx}")
                    b_regla = c_reg.text_input("Regla / Indicación:", value=def_rule, key=f"ebreg_{pr_id}_{d_idx}_{b_idx}")
                    
                    if f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}" not in st.session_state:
                        default_ids = []
                        if old_block:
                            default_ids = [ex["exerciseId"] for ex in old_block.get("exercises", [])]
                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = default_ids
                        
                    current_block_ids = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]
                    default_names = [get_exercise(eid)["name"] for eid in current_block_ids if get_exercise(eid) and get_main_category(get_exercise(eid)["category"]) == b_cat]
                    
                    ej_options_block = {}
                    for e in exercises:
                        cat_e = e.get("category", "")
                        if get_main_category(cat_e) == b_cat:
                            mostrar = True
                            if b_cat == "EEII" and b_subcat != "Todos":
                                if b_subcat == "EEII (General)" and cat_e != "EEII": mostrar = False
                                elif b_subcat == "EEII (3FE)" and cat_e != "EEII (3FE)": mostrar = False
                                elif b_subcat == "EEII (H-H)" and cat_e != "EEII (H-H)": mostrar = False
                            
                            if mostrar or (e["name"] in default_names):
                                ej_options_block[e["name"]] = e["id"]

                    sorted_options = sorted(ej_options_block.keys(), key=lambda x: x.lower())
                    ej_options_block_sorted = {k: ej_options_block[k] for k in sorted_options}
                    
                    b_selected_names = st.multiselect("Ejercicios:", options=list(ej_options_block_sorted.keys()), default=default_names, key=f"ebsel_{pr_id}_{d_idx}_{b_idx}", label_visibility="collapsed")
                    
                    new_ids = [ej_options_block_sorted[n] for n in b_selected_names]
                    st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] if e in new_ids]
                    for e in new_ids:
                        if e not in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]:
                            st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"].append(e)
                            
                    ejs_bloque_info = []
                    for idx_e, eid in enumerate(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]):
                        ej_obj = get_exercise(eid)
                        ename = ej_obj['name'] if ej_obj else "Ejercicio"
                        
                        def_prio = False
                        def_s = ""
                        def_r = ""
                        def_n = ej_obj.get("defaultNote", "") if ej_obj else ""
                        if old_block:
                            for ex_old in old_block.get("exercises", []):
                                if ex_old.get("exerciseId") == eid:
                                    def_prio = ex_old.get("isPriority", False)
                                    def_s = ex_old.get("series", "")
                                    def_r = ex_old.get("reps", "")
                                    def_n = ex_old.get("notes", "")
                                    break
                                    
                        prio_key = f"eprio_{pr_id}_{d_idx}_{b_idx}_{eid}"
                        if prio_key not in st.session_state:
                            st.session_state[prio_key] = def_prio
                            
                        ce1, ce2, ce3, ce4, ce5, ce6, ce7 = st.columns([3, 1, 1, 2, 1.5, 0.6, 0.6])
                        with ce1:
                            st.markdown(f"<div style='margin-top:6px; font-weight:bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx_e+1}. {ename}</div>", unsafe_allow_html=True)
                        with ce2:
                            s = st.text_input("S", value=def_s, key=f"es_af_{pr_id}_{d_idx}_{b_idx}_{eid}", placeholder="Ser", label_visibility="collapsed")
                        with ce3:
                            r = st.text_input("R", value=def_r, key=f"er_af_{pr_id}_{d_idx}_{b_idx}_{eid}", placeholder="Rep", label_visibility="collapsed")
                        with ce4:
                            n = st.text_input("N", value=def_n, key=f"en_af_{pr_id}_{d_idx}_{b_idx}_{eid}", placeholder="Nota", label_visibility="collapsed")
                        with ce5:
                            es_prio = st.checkbox("⭐ Prio", key=prio_key)
                        with ce6:
                            if st.button("⬆️", key=f"eup_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                                st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1]
                                st.rerun()
                        with ce7:
                            if st.button("⬇️", key=f"edn_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"])-1:
                                st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1]
                                st.rerun()
                            
                        ejs_bloque_info.append({"exerciseId": eid, "isPriority": es_prio, "series": s, "reps": r, "notes": n})
                        
                    bloques_dia.append({
                        "blockTitle": f"{b_cat} {b_regla}".strip(),
                        "blockCategory": b_cat,
                        "blockRule": b_regla,
                        "exercises": ejs_bloque_info
                    })
            dias_construidos.append({
                "dayTitle": d_titulo,
                "blocks": bloques_dia
            })
            
        st.write("")
        c_save, c_cancel = st.columns([2, 1])
        if c_save.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True):
            pr["patientId"] = af_paciente
            pr["title"] = af_titulo
            pr["frequency"] = af_frecuencia
            pr["duration"] = af_duracion
            pr["generalInstructionIds"] = selected_general_instruction_ids_af
            pr["generalNote"] = af_nota
            pr["daysData"] = dias_construidos
            save_programs_af(programs_af)
            st.session_state.editing_program_id = None
            st.rerun()
        if c_cancel.button("❌ Cancelar", use_container_width=True):
            st.session_state.editing_program_id = None
            st.rerun()

    st.sidebar.markdown("<h2 style='color:#13765d !important;'>🩺 FisioSesión</h2>", unsafe_allow_html=True)
    
    menu_seleccion = st.sidebar.radio(
        "Panel de Control:",
        ["📁 Archivo", "🩺 Sesiones", "🏋️ Programas de AF"]
    )
    
    st.sidebar.divider()
    if st.sidebar.button("🔒 Cerrar Sesión Segura", type="primary"):
        st.session_state.admin_mode = False
        st.session_state.logged_pin = None
        st.rerun()

    st.sidebar.divider()
    
    backup_data = {
        "pacientes": patients,
        "ejercicios": exercises,
        "indicaciones_generales": general_instructions,
        "sesiones": plans,
        "programas_af": programs_af,
        "checkins": checkins
    }
    
    backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
    
    st.sidebar.download_button(
        label="📥 Descargar Copia de Seguridad",
        data=backup_json,
        file_name=f"backup_fisiosesion_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        use_container_width=True
    )
    st.sidebar.caption("Pulsa aquí regularmente para guardar una copia de todos tus pacientes y ejercicios en tu ordenador.")

    if st.session_state.gsheets_read_error:
        st.error("⚠️ Atención: Ha habido un fallo de conexión con Google Sheets. Las funciones de guardado y borrado están bloqueadas temporalmente para proteger tus datos. Recarga la página en unos segundos.")

    if menu_seleccion == "📁 Archivo":
        st.markdown("<h1>📁 Base de Datos y Archivo</h1>", unsafe_allow_html=True)
        tab_pac, tab_ej, tab_ind = st.tabs(["👥 Pacientes", "🎥 Ejercicios", "📌 Indicaciones generales"])
        
        with tab_pac:
            with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
                with st.form("nuevo_paciente_form", clear_on_submit=True):
                    c_np1, c_np2, c_np3, c_np4 = st.columns([2.2, 1.3, 1.8, 1.5])
                    new_p_name = c_np1.text_input("Nombre completo:")
                    new_p_phone = c_np2.text_input("Teléfono:")
                    new_p_lesion = c_np3.text_input("Lesión:", placeholder="Ej: Esguince tobillo")
                    new_p_review_input = c_np4.text_input("Próxima revisión (DD/MM/AAAA):", value="", placeholder="Ej: 15/03/2026")
                    
                    st.caption("Podrás añadir la anamnesis, inspección física, movilidad y fuerza de la primera revisión justo después de crear el paciente, desde su ficha.")
                    
                    if st.form_submit_button("Guardar Paciente Nuevo", type="primary"):
                        if new_p_name:
                            review_str = ""
                            fecha_valida = True
                            if new_p_review_input.strip():
                                try:
                                    review_str = datetime.datetime.strptime(new_p_review_input.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                                except ValueError:
                                    fecha_valida = False
                            if not fecha_valida:
                                st.error("⚠️ La fecha de revisión no es válida. Usa el formato DD/MM/AAAA (ej: 15/03/2026).")
                            else:
                                patients.append({
                                    "id": str(uuid.uuid4()), "name": new_p_name, "phone": new_p_phone,
                                    "lesion": new_p_lesion,
                                    "review_date": review_str,
                                    "revisions": []
                                })
                                save_patients(patients)
                                st.success("¡Paciente añadido y sincronizado!")
                                st.rerun()

            total_pacs = len(patients)
            st.markdown(f"<h3 style='margin-top:20px;'>Directorio y Perfiles ({total_pacs})</h3>", unsafe_allow_html=True)
            search_pac = st.text_input("🔍 Buscar paciente por nombre o teléfono:")
            
            pacs_filtrados = patients
            if search_pac:
                q_pac = search_pac.lower()
                pacs_filtrados = [p for p in pacs_filtrados if q_pac in p["name"].lower() or q_pac in p.get("phone", "").lower()]

            if not pacs_filtrados:
                st.info("No se han encontrado pacientes.")
                
            for p in pacs_filtrados:
                titulo_exp = f"👤 {p['name']} - 📞 {p.get('phone', 'Sin teléfono')}" if p.get('phone') else f"👤 {p['name']}"
                with st.expander(titulo_exp):
                    st.markdown("#### 📋 Sesiones / Programas Asignados")
                    sesiones_del_paciente = [pl for pl in plans if str(pl["patientId"]) == str(p["id"])]
                    progs_del_paciente = [pr for pr in programs_af if str(pr["patientId"]) == str(p["id"])]
                    
                    if sesiones_del_paciente:
                        st.markdown("**Sesiones Clínicas:**")
                        for pi in reversed(sesiones_del_paciente):
                            st.write(f"- {pi['title']} (PIN: {pi['pin']})")
                    
                    if progs_del_paciente:
                        st.markdown("**Programas de AF:**")
                        for pr in reversed(progs_del_paciente):
                            st.write(f"- {pr['title']} (PIN: {pr['pin']})")

                    if not sesiones_del_paciente and not progs_del_paciente:
                        st.write("No tiene planes ni programas asignados todavía.")

                    st.divider()
                    st.markdown("#### ⚙️ Datos del Paciente")
                    
                    ce1, ce2, ce3, ce4 = st.columns([2.2, 1.3, 1.8, 1.5])
                    edit_name = ce1.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                    edit_phone = ce2.text_input("Teléfono", value=p.get("phone", ""), key=f"phone_{p['id']}")
                    edit_lesion = ce3.text_input("Lesión", value=p.get("lesion", ""), key=f"lesion_{p['id']}", placeholder="Ej: Esguince tobillo")
                    
                    try:
                        curr_rev_display = datetime.datetime.strptime(p.get("review_date", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
                    except:
                        curr_rev_display = ""
                    edit_review_input = ce4.text_input("Próxima revisión (DD/MM/AAAA)", value=curr_rev_display, key=f"rev_{p['id']}", placeholder="Ej: 15/03/2026")
                    
                    if st.button("💾 Actualizar Datos", key=f"upd_{p['id']}", type="primary"):
                        nueva_review_str = ""
                        fecha_valida = True
                        if edit_review_input.strip():
                            try:
                                nueva_review_str = datetime.datetime.strptime(edit_review_input.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                            except ValueError:
                                fecha_valida = False
                        if not fecha_valida:
                            st.error("⚠️ La fecha de revisión no es válida. Usa el formato DD/MM/AAAA (ej: 15/03/2026).")
                        else:
                            p["name"] = edit_name; p["phone"] = edit_phone
                            p["lesion"] = edit_lesion
                            p["review_date"] = nueva_review_str
                            save_patients(patients); st.rerun()

                    st.markdown("<h4 style='margin-top:6px; margin-bottom:8px;'>📖 Historial de Revisiones</h4>", unsafe_allow_html=True)

                    p.setdefault("revisions", [])

                    if not p["revisions"]:
                        st.caption("Este paciente todavía no tiene ninguna revisión registrada.")

                    for r_idx, rev in enumerate(p["revisions"]):
                        fecha_rev_disp = ""
                        if rev.get("date"):
                            try:
                                fecha_rev_disp = datetime.datetime.strptime(rev["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                            except:
                                fecha_rev_disp = ""

                        col_exp, col_fecha_rev = st.columns([8, 1.3])
                        with col_fecha_rev:
                            rev_fecha_input = st.text_input("Fecha", value=fecha_rev_disp, key=f"rev_fecha_{p['id']}_{r_idx}", placeholder="DD/MM/AAAA", label_visibility="collapsed")
                        with col_exp:
                            with st.expander(f"📋 {ordinal_revision(r_idx + 1)}"):
                                rev_ana = st.text_area("**Anamnesis** (entrevista, historia clínica...):", value=rev.get("anamnesis", ""), key=f"rev_ana_{p['id']}_{r_idx}")
                                rev_ins = st.text_area("**Inspección física** (temperatura, coloración, medidas...):", value=rev.get("inspeccion", ""), key=f"rev_ins_{p['id']}_{r_idx}")
                                rev_mov = st.text_area("**Movilidad activa y pasiva** (ROM activo y pasivo...):", value=rev.get("movilidad", ""), key=f"rev_mov_{p['id']}_{r_idx}")
                                rev_fue = st.text_area("**Fuerza** (dinamometría...):", value=rev.get("fuerza", ""), key=f"rev_fue_{p['id']}_{r_idx}")

                                col_save_rev, col_del_rev = st.columns(2)
                                if col_save_rev.button("💾 Guardar revisión", key=f"save_rev_{p['id']}_{r_idx}", type="primary", use_container_width=True):
                                    fecha_rev_valida = True
                                    nueva_fecha_rev = ""
                                    if rev_fecha_input.strip():
                                        try:
                                            nueva_fecha_rev = datetime.datetime.strptime(rev_fecha_input.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                                        except ValueError:
                                            fecha_rev_valida = False
                                    if not fecha_rev_valida:
                                        st.error("⚠️ La fecha no es válida. Usa el formato DD/MM/AAAA.")
                                    else:
                                        p["revisions"][r_idx] = {
                                            "date": nueva_fecha_rev, "anamnesis": rev_ana,
                                            "inspeccion": rev_ins, "movilidad": rev_mov, "fuerza": rev_fue
                                        }
                                        save_patients(patients)
                                        st.success("Revisión guardada.")
                                        st.rerun()
                                if col_del_rev.button("🗑️ Eliminar revisión", key=f"del_rev_{p['id']}_{r_idx}", use_container_width=True):
                                    p["revisions"].pop(r_idx)
                                    save_patients(patients)
                                    st.rerun()

                    if st.button("➕ Añadir Revisión", key=f"add_rev_{p['id']}"):
                        p["revisions"].append({"date": "", "anamnesis": "", "inspeccion": "", "movilidad": "", "fuerza": ""})
                        save_patients(patients)
                        st.rerun()

                    st.divider()
                    if st.session_state.confirm_delete_patient_id == p["id"]:
                        st.warning("Vas a borrar definitivamente este paciente, todas sus sesiones, programas y reportes. Esta acción no se puede deshacer desde la aplicación.")
                        confirm_col, cancel_col = st.columns(2)
                        if confirm_col.button("Sí, borrar todos sus datos", key=f"confirm_del_patient_{p['id']}", type="primary", use_container_width=True):
                            patient_id = str(p["id"])
                            deleted_plan_ids = {str(pl["id"]) for pl in plans if str(pl["patientId"]) == patient_id}
                            patients = [x for x in patients if str(x["id"]) != patient_id]
                            plans = [pl for pl in plans if str(pl["patientId"]) != patient_id]
                            programs_af = [pr for pr in programs_af if str(pr["patientId"]) != patient_id]
                            checkins = [ch for ch in checkins if str(ch["planId"]) not in deleted_plan_ids]
                            save_checkins(checkins)
                            save_plans(plans)
                            save_programs_af(programs_af)
                            save_patients(patients)
                            st.session_state.confirm_delete_patient_id = None
                            st.rerun()
                        if cancel_col.button("Cancelar", key=f"cancel_del_patient_{p['id']}", use_container_width=True):
                            st.session_state.confirm_delete_patient_id = None
                            st.rerun()
                    elif st.button("🗑️ Borrar Paciente", key=f"del_{p['id']}"):
                        st.session_state.confirm_delete_patient_id = p["id"]
                        st.rerun()

        with tab_ej:
            total_ej = len(exercises)
            st.markdown(f"<h3 style='margin-top:10px;'>🎥 Base de Datos de Ejercicios (Total: {total_ej})</h3>", unsafe_allow_html=True)
            
            with st.form("form_añadir_ejercicio", clear_on_submit=True):
                st.markdown("<div style='color:var(--green); font-weight:bold; font-size:16px; margin: 0 0 10px 0;'>➕ AÑADIR NUEVO EJERCICIO</div>", unsafe_allow_html=True)
                
                cn1, cn_alt, cn2, cn3, cn4 = st.columns([3, 2.9, 3, 1.2, 1])
                with cn1:
                    new_n = st.text_input("new_n", placeholder="Nombre del ejercicio...", label_visibility="collapsed")
                with cn_alt:
                    new_pn = st.text_input("new_pn", placeholder="Nombre para el paciente (opcional)...", label_visibility="collapsed")
                with cn2:
                    new_u = st.text_input("new_u", placeholder="Enlace de YouTube...", label_visibility="collapsed")
                with cn3:
                    new_c = st.selectbox("new_c", CATEGORIAS_DB, label_visibility="collapsed")
                with cn4:
                    btn_add = st.form_submit_button("➕ Añadir", type="primary", use_container_width=True)
                
                if btn_add:
                    if new_n.strip():
                        exercises.append({
                            "id": str(uuid.uuid4()),
                            "name": new_n.strip(),
                            "patientName": new_pn.strip(),
                            "videoUrl": new_u.strip(),
                            "category": new_c,
                            "defaultNote": ""
                        })
                        save_exercises(exercises)
                        st.success("¡Ejercicio añadido a la base de datos!")
                        st.rerun()
                    else:
                        st.warning("⚠️ El nombre del ejercicio es obligatorio.")
            
            st.write("")
            
            # Editor de ejercicios. Es un contenedor normal para poder abrir un
            # bocadillo 💬 junto a cada nombre sin crear una nueva columna de datos.
            with st.container():
                btn_save = st.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True, key="save_all_exercises")
                st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)
                
                nuevos_datos = {}
                ids_borrar = []
                
                # El comentario va como segunda columna. Se deja deliberadamente sin título.
                c_h1, c_h_comment, c_h_alt, c_h2, c_h3, c_h4 = st.columns([2.7, 1.0, 2.0, 2.5, 1.3, 1.0])
                c_h1.caption("NOMBRE")
                # c_h_comment: sin título, solo el botón 📝 ✅ / 📝 ❌
                c_h_alt.caption("NOMBRE PARA EL PACIENTE")
                c_h2.caption("ENLACE YOUTUBE")
                c_h3.caption("CATEGORÍA")
                c_h4.caption("ACCIÓN")
                
                for cat in CATEGORIAS_DB:
                    ej_cat = [e for e in exercises if e.get("category") == cat]
                    ej_cat = sorted(ej_cat, key=lambda x: x["name"].lower())
                    
                    if ej_cat:
                        st.markdown(f"<div style='color:var(--dark); font-weight:bold; font-size:16px; margin: 15px 0 5px 0; border-bottom: 1px solid var(--line);'>{cat} (Total: {len(ej_cat)})</div>", unsafe_allow_html=True)
                        for e in ej_cat:
                            eid = e["id"]
                            c1, c_comment, c_alt, c2, c3, c4 = st.columns([2.7, 1.0, 2.0, 2.5, 1.3, 1.0])
                            with c1:
                                n = st.text_input("n", value=e["name"], key=f"n_{eid}", label_visibility="collapsed")
                            with c_alt:
                                pn = st.text_input("pn", value=e.get("patientName", ""), key=f"pn_{eid}", label_visibility="collapsed", placeholder="(igual que el nombre)")
                            with c2:
                                u = st.text_input("u", value=e["videoUrl"], key=f"u_{eid}", label_visibility="collapsed")
                            with c3:
                                idx = CATEGORIAS_DB.index(e["category"]) if e["category"] in CATEGORIAS_DB else 0
                                c = st.selectbox("c", CATEGORIAS_DB, index=idx, key=f"c_{eid}", label_visibility="collapsed")
                            with c_comment:
                                comentario_ejercicio_actual = e.get("defaultNote", "").strip()
                                icono_estado = "✅" if comentario_ejercicio_actual else "❌"
                                # Botón tipo bocadillo de cómic: icono de escritura + estado.
                                with st.popover(f"📝 {icono_estado}", help="Abrir comentario asociado a este ejercicio"):
                                    st.markdown("""
                                    <div style="
                                        position:relative;
                                        background:#fffef7;
                                        border:2px solid #13765d;
                                        border-radius:20px 20px 20px 7px;
                                        padding:14px 17px 15px 17px;
                                        margin:0 0 12px 0;
                                        color:#103d33;
                                        font-size:13px;
                                        line-height:1.5;
                                        box-shadow:0 5px 15px rgba(16,61,51,.12);
                                    ">
                                        <div style="font-size:15px; font-weight:800; color:#13765d; margin-bottom:5px;">📝 Comentario del ejercicio</div>
                                        <div>Este texto aparecerá automáticamente en <strong>Notas</strong> al añadir este ejercicio a una sesión clínica o a un programa de AF.</div>
                                    </div>
                                    <div style="
                                        width:0; height:0;
                                        border-top:12px solid #13765d;
                                        border-right:12px solid transparent;
                                        margin:-12px 0 10px 18px;
                                    "></div>
                                    """, unsafe_allow_html=True)
                                    st.text_area(
                                        "Comentario",
                                        value=e.get("defaultNote", ""),
                                        key=f"default_note_{eid}",
                                        height=130,
                                        placeholder="Ej: Mantén la rodilla alineada con el segundo dedo del pie...",
                                        label_visibility="collapsed"
                                    )
                            with c4:
                                b = st.checkbox("🗑️ Borrar", key=f"del_{eid}")
                                
                            comentario_ejercicio = st.session_state.get(f"default_note_{eid}", e.get("defaultNote", "")).strip()
                            nuevos_datos[eid] = {
                                "id": eid,
                                "name": n,
                                "patientName": pn,
                                "videoUrl": u,
                                "category": c,
                                "defaultNote": comentario_ejercicio
                            }
                            if b:
                                ids_borrar.append(eid)
                            
                st.markdown("<br>", unsafe_allow_html=True)
                
                if btn_save:
                    exercise_ids_to_delete = set(ids_borrar)
                    references = []
                    if exercise_ids_to_delete:
                        for plan in plans:
                            if any(str(eid) in exercise_ids_to_delete for eid in plan.get("exerciseIds", [])):
                                references.append(f"Sesión: {plan['title']} ({get_patient_name(plan['patientId'])})")
                        for program in programs_af:
                            used_in_program = any(
                                str(item.get("exerciseId", "")) in exercise_ids_to_delete
                                for day in program.get("daysData", [])
                                for block in day.get("blocks", [])
                                for item in block.get("exercises", [])
                            )
                            if used_in_program:
                                references.append(f"Programa AF: {program['title']} ({get_patient_name(program['patientId'])})")

                    if references:
                        st.error("No se han guardado los cambios porque uno o más ejercicios marcados para borrar siguen prescritos. Primero elimínalos de estos planes: " + "; ".join(references))
                    else:
                        lista_final = []
                        for e in exercises:
                            eid = e["id"]
                            if eid not in exercise_ids_to_delete:
                                lista_final.append(nuevos_datos[eid])
                        
                        save_exercises(lista_final)
                        st.success("¡Base de datos de ejercicios actualizada!")
                        st.rerun()

        with tab_ind:
            st.markdown(f"<h3 style='margin-top:10px;'>📌 Banco de Indicaciones Generales (Total: {len(general_instructions)})</h3>", unsafe_allow_html=True)
            st.caption("Crea aquí las indicaciones reutilizables que después podrás seleccionar en cada sesión clínica o programa de AF.")
            with st.form("form_añadir_indicacion", clear_on_submit=True):
                texto_ind = st.text_area("Nueva indicación", placeholder="Ej: Realiza los ejercicios con una técnica controlada y evita movimientos bruscos...", height=90, label_visibility="collapsed")
                if st.form_submit_button("➕ Añadir indicación", type="primary", use_container_width=True):
                    txt = texto_ind.strip()
                    if not txt:
                        st.warning("⚠️ La indicación no puede estar vacía.")
                    elif any(x["text"].strip().lower() == txt.lower() for x in general_instructions):
                        st.warning("⚠️ Esa indicación ya existe.")
                    else:
                        general_instructions.append({"id": str(uuid.uuid4()), "text": txt})
                        save_general_instructions(general_instructions)
                        st.rerun()
            st.write("")
            if not general_instructions:
                st.info("Todavía no has creado ninguna indicación general.")
            else:
                for idx_ind, item in enumerate(general_instructions, 1):
                    with st.container(border=True):
                        st.text_area(f"Indicación {idx_ind}", value=item["text"], key=f"ind_text_{item['id']}", height=90)
                if st.button("💾 Guardar cambios del listado", type="primary", use_container_width=True):
                    updated = []
                    seen = set()
                    valid = True
                    for item in general_instructions:
                        txt = st.session_state.get(f"ind_text_{item['id']}", item["text"]).strip()
                        if not txt or txt.lower() in seen:
                            valid = False
                            break
                        seen.add(txt.lower())
                        updated.append({"id": item["id"], "text": txt})
                    if valid:
                        general_instructions = updated
                        save_general_instructions(general_instructions)
                        st.success("¡Listado actualizado!")
                        st.rerun()

    elif menu_seleccion == "🩺 Sesiones":
        st.markdown("<h1>🩺 Sesiones Clínicas</h1>", unsafe_allow_html=True)
        tab_ses_act, tab_crear_ses, tab_checkins, tab_seguimiento = st.tabs(["⚙️ Sesiones Activas", "📝 Crear Nueva Sesión", "📊 Check-ins", "📈 Seguimiento Pacientes"])
        
        with tab_ses_act:
            if st.session_state.get("editing_sesion_id"):
                target_ses = next((pl for pl in plans if str(pl["id"]) == str(st.session_state.editing_sesion_id)), None)
                if target_ses:
                    modal_editar_sesion(target_ses)
                else:
                    st.session_state.editing_sesion_id = None

            search_query = st.text_input("🔍 Buscar sesión por título o nombre del paciente:")
            
            sesiones_actuales = {}
            for pl in plans:
                if pl.get("isActive", True):
                    sesiones_actuales[pl["patientId"]] = pl
            planes_filtrados = list(reversed(sesiones_actuales.values()))
            
            if search_query:
                q = search_query.lower()
                planes_filtrados = [pl for pl in planes_filtrados if q in pl["title"].lower() or q in get_patient_name(pl["patientId"]).lower()]
            
            if not planes_filtrados:
                st.info("No se encontraron sesiones.")
            else:
                for pl in planes_filtrados:
                    with st.container(border=True):
                        c_title, c_pin = st.columns([7, 3])
                        c_title.markdown(f"#### {pl['title']}")
                        c_pin.markdown(f"<div style='text-align:right;'><span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pl['pin']}</span></div>", unsafe_allow_html=True)
                        
                        st.write(f"👤 **Paciente:** {get_patient_name(pl['patientId'])}")

                        c_date, c_edit, c_copy, c_del = st.columns([5.5, 1.2, 1.4, 1.2])
                        c_date.write(f"📅 **Inicio:** {pl.get('startDate', 'No registrada')}")
                        with c_edit:
                            if st.button("✏️ Editar", key=f"edit_btn_{pl['id']}", use_container_width=True):
                                st.session_state.editing_sesion_id = pl["id"]
                                st.session_state[f"edit_ses_{pl['id']}_ejs"] = pl["exerciseIds"].copy()
                                st.rerun()
                        with c_copy:
                            with st.popover("📋 Copiar", use_container_width=True):
                                st.caption("Copia el mensaje usando el icono de la esquina superior derecha:")
                                mensaje_wa = f"¡Hola {get_patient_name(pl['patientId'])}! 👋\n\nAquí tienes tu sesión de fisioterapia: *{pl['title']}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={pl['pin']}\n\n¡A por ello!"
                                st.code(mensaje_wa, language="markdown")
                        with c_del:
                            if st.session_state.confirm_delete_session_id == pl["id"]:
                                st.warning("Se borrará la sesión y todos los reportes EVA/Borg asociados. El código de acceso dejará de funcionar.")
                                confirm_col, cancel_col = st.columns(2)
                                if confirm_col.button("Sí, borrar sesión", key=f"confirm_del_session_{pl['id']}", type="primary", use_container_width=True):
                                    plan_id = str(pl["id"])
                                    plans = [x for x in plans if str(x["id"]) != plan_id]
                                    checkins = [ch for ch in checkins if str(ch["planId"]) != plan_id]
                                    save_checkins(checkins)
                                    save_plans(plans)
                                    st.session_state.confirm_delete_session_id = None
                                    st.rerun()
                                if cancel_col.button("Cancelar", key=f"cancel_del_session_{pl['id']}", use_container_width=True):
                                    st.session_state.confirm_delete_session_id = None
                                    st.rerun()
                            elif st.button("🗑️ Eliminar", key=f"del_{pl['id']}", use_container_width=True):
                                st.session_state.confirm_delete_session_id = pl["id"]
                                st.rerun()

        with tab_crear_ses:
            if not patients:
                st.warning("Añade pacientes en el apartado 'Archivo' primero.")
            else:
                paciente_sel = st.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
                titulo_sesion = st.text_input("2. Título de la Sesión:", placeholder="Ej: Rehabilitación Rodilla...")
                
                st.markdown("**3. Selecciona los ejercicios:**")
                
                c_filt1, c_filt2 = st.columns(2)
                filtro_cat = c_filt1.selectbox("Filtrar por Categoría:", ["Todas"] + CATEGORIAS_EJ, key="crear_ses_fcat")
                filtro_subcat = "Todos"
                if filtro_cat == "EEII":
                    filtro_subcat = c_filt2.selectbox("Subcategoría EEII:", ["Todos", "EEII (General)", "EEII (3FE)", "EEII (H-H)"], key="crear_ses_fsub")
                
                if 'orden_ejs' not in st.session_state:
                    st.session_state.orden_ejs = []
                
                nombres_actuales = []
                for eid in st.session_state.orden_ejs:
                    eobj = get_exercise(eid)
                    if eobj: nombres_actuales.append(f"{eobj['category']}  |  {eobj['name']}")
                
                ej_options = {}
                for cat in CATEGORIAS_DB:
                    mostrar_cat = True
                    if filtro_cat != "Todas":
                        if get_main_category(cat) != filtro_cat:
                            mostrar_cat = False
                        elif filtro_cat == "EEII" and filtro_subcat != "Todos":
                            if filtro_subcat == "EEII (General)" and cat != "EEII": mostrar_cat = False
                            elif filtro_subcat == "EEII (3FE)" and cat != "EEII (3FE)": mostrar_cat = False
                            elif filtro_subcat == "EEII (H-H)" and cat != "EEII (H-H)": mostrar_cat = False
                            
                    ej_ordenados = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
                    for e in ej_ordenados:
                        name_key = f"{cat}  |  {e['name']}"
                        if mostrar_cat or (name_key in nombres_actuales):
                            ej_options[name_key] = e['id']
                
                selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options.keys()), default=nombres_actuales, label_visibility="collapsed", placeholder="Escribe o despliega para buscar...")
                
                ejs_seleccionados = [ej_options[name] for name in selected_names]
                st.session_state.orden_ejs = [e for e in st.session_state.orden_ejs if e in ejs_seleccionados]
                for e in ejs_seleccionados:
                    if e not in st.session_state.orden_ejs:
                        st.session_state.orden_ejs.append(e)
                
                opciones_ind_crear = {item["text"]: item["id"] for item in general_instructions}
                selected_ind_crear = st.multiselect("**4. Indicaciones generales:**", options=list(opciones_ind_crear.keys()), key="crear_sesion_indicaciones", placeholder="Selecciona las indicaciones para esta sesión...")
                selected_general_instruction_ids_crear = [opciones_ind_crear[x] for x in selected_ind_crear]

                instrucciones_dict = {}
                has_missing_videos = False

                if st.session_state.orden_ejs:
                    st.markdown("**5. Configuración y Orden:**")
                    
                    c_th, c_sh, c_rh, c_nh, c_x1, c_x2 = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                    c_th.caption("EJERCICIO")
                    c_sh.caption("SERIES")
                    c_rh.caption("REPS")
                    c_nh.caption("NOTAS EXTRA")
                    
                    for idx, e_id in enumerate(st.session_state.orden_ejs):
                        ej_obj = get_exercise(e_id)
                        ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                        sin_video = False
                        
                        if ej_obj and not tiene_video_valido(ej_obj.get("videoUrl", "")):
                            sin_video = True
                            has_missing_videos = True
                            ej_name += " ⚠️ (SIN VÍDEO)"

                        col_t, col_s, col_r, col_n, col_up, col_dn = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                        
                        with col_t:
                            color_texto = "#aa3838" if sin_video else "inherit"
                            st.markdown(f"<div style='margin-top:8px; font-weight:bold; font-size:14px; color:{color_texto}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx + 1}. {ej_name}</div>", unsafe_allow_html=True)
                        with col_s:
                            s = st.text_input("S", key=f"ser_{e_id}", placeholder="Series", label_visibility="collapsed")
                        with col_r:
                            r = st.text_input("R", key=f"rep_{e_id}", placeholder="Reps", label_visibility="collapsed")
                        with col_n:
                            note_key = f"not_{e_id}"
                            if note_key not in st.session_state:
                                st.session_state[note_key] = (ej_obj.get("defaultNote", "") if ej_obj else "")
                            n = st.text_input("N", key=note_key, placeholder="Notas...", label_visibility="collapsed")
                        with col_up:
                            if st.button("⬆️", key=f"up_{e_id}"):
                                if idx > 0:
                                    st.session_state.orden_ejs[idx-1], st.session_state.orden_ejs[idx] = st.session_state.orden_ejs[idx], st.session_state.orden_ejs[idx-1]
                                    st.rerun()
                        with col_dn:
                            if st.button("⬇️", key=f"dn_{e_id}"):
                                if idx < len(st.session_state.orden_ejs) - 1:
                                    st.session_state.orden_ejs[idx+1], st.session_state.orden_ejs[idx] = st.session_state.orden_ejs[idx], st.session_state.orden_ejs[idx+1]
                                    st.rerun()
                        
                        instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                
                st.write("")
                if has_missing_videos:
                    st.warning("⚠️ Atención: Hay ejercicios en la lista marcados en rojo que no tienen vídeo asignado en la base de datos. El paciente no tendrá enlace al vídeo para estos ejercicios.")

                if st.button("💾 Generar Sesión", type="primary"):
                    if not titulo_sesion.strip():
                        st.warning("⚠️ Faltan campos por rellenar: Por favor, introduce un título para la sesión.")
                    elif not st.session_state.orden_ejs:
                        st.warning("⚠️ Faltan campos por rellenar: Debes seleccionar al menos un ejercicio.")
                    else:
                        nuevo_pin = generate_unique_access_code()
                        for existing_plan in plans:
                            if str(existing_plan["patientId"]) == str(paciente_sel):
                                existing_plan["isActive"] = False
                        plans.append({
                            "id": str(uuid.uuid4()), "patientId": paciente_sel, "title": titulo_sesion,
                            "exerciseIds": st.session_state.orden_ejs, "exerciseInstructions": instrucciones_dict,
                            "generalInstructionIds": selected_general_instruction_ids_crear,
                            "pin": nuevo_pin, "startDate": datetime.date.today().strftime("%d/%m/%Y"), "isActive": True
                        })
                        save_plans(plans)
                        st.session_state.orden_ejs = []
                        st.success("¡Sesión guardada!")
                        
                        nombre_paciente = get_patient_name(paciente_sel)
                        mensaje_whatsapp = f"¡Hola {nombre_paciente}! 👋\n\nAquí tienes tu nueva sesión de fisioterapia: *{titulo_sesion}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={nuevo_pin}\n\n¡A por ello!"
                        st.info("Copia el mensaje a continuación para enviarlo por WhatsApp:")
                        st.code(mensaje_whatsapp, language="markdown")

        with tab_checkins:
            st.markdown("<h3 style='margin-top:10px;'>Reportes de Carga de Pacientes</h3>", unsafe_allow_html=True)
            if not checkins:
                st.info("Aún no hay reportes registrados por pacientes para sus sesiones.")
            else:
                for plan in reversed(plans):
                    c_plan = [c for c in checkins if str(c.get("planId")) == str(plan["id"])]
                    if c_plan:
                        with st.expander(f"📁 {get_patient_name(plan['patientId'])} - {plan['title']}"):
                            for ch in reversed(c_plan):
                                st.markdown(f"**📅 {ch['date']}**")
                                st.markdown(f"**EVA:** {ch['eva']} / 10 | **Borg:** {ch['borg']} / 10")
                                st.markdown(f"*{ch['comment']}*")
                                st.divider()
                                
        with tab_seguimiento:
            st.markdown("<h3 style='margin-top:10px;'>📈 Evolución Clínica del Paciente</h3>", unsafe_allow_html=True)
            if not patients:
                st.warning("Añade pacientes en el apartado 'Archivo' primero.")
            else:
                paciente_sel_seg = st.selectbox(
                    "🔍 Buscar Paciente:", 
                    options=[p["id"] for p in patients], 
                    format_func=get_patient_name, 
                    key="search_pac_seg"
                )
                
                paciente_obj_seg = next((pp for pp in patients if str(pp["id"]) == str(paciente_sel_seg)), None)
                tiene_sesiones_clinicas_seg = any(str(pl["patientId"]) == str(paciente_sel_seg) for pl in plans)

                if paciente_obj_seg and tiene_sesiones_clinicas_seg:
                    res_semaforo = calcular_semaforo_paciente(paciente_obj_seg, plans, checkins)
                    motivos_str = " · ".join(res_semaforo["motivos"]) if res_semaforo["motivos"] else "Sin incidencias detectadas."
                    st.markdown(f"""
                    <div style='background:{res_semaforo["bg_color"]}; border:1px solid {res_semaforo["text_color"]}; border-radius:12px; padding:16px 20px; margin:12px 0 22px 0;'>
                        <div style='font-size:17px; font-weight:800; color:{res_semaforo["text_color"]};'>{res_semaforo["icono"]} Adherencia: {res_semaforo["estado"].capitalize()}</div>
                        <div style='font-size:13px; color:{res_semaforo["text_color"]}; margin-top:6px;'>{motivos_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                planes_paciente = [p["id"] for p in plans if str(p["patientId"]) == str(paciente_sel_seg)]
                checkins_paciente = [c for c in checkins if str(c["planId"]) in planes_paciente]
                
                if not checkins_paciente:
                    st.info("Este paciente aún no ha registrado ningún reporte en sus sesiones.")
                else:
                    df_checkins = pd.DataFrame(checkins_paciente)
                    df_checkins['date_obj'] = pd.to_datetime(df_checkins['date'], format="%Y-%m-%d %H:%M", errors='coerce')
                    df_checkins = df_checkins.sort_values(by='date_obj')
                    
                    df_checkins['eva'] = pd.to_numeric(df_checkins['eva'], errors='coerce').fillna(0)
                    df_checkins['borg'] = pd.to_numeric(df_checkins['borg'], errors='coerce').fillna(0)
                    
                    df_checkins['Fecha_Corta'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y')
                    df_checkins['Fecha_Larga'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y %H:%M')
                    
                    st.markdown("#### 📊 Gráfica de Dolor y Fatiga")
                    
                    df_melted = df_checkins[['Fecha_Corta', 'eva', 'borg']].copy()
                    df_melted = df_melted.rename(columns={'eva': 'Dolor (EVA)', 'borg': 'Fatiga (Borg)'})
                    df_melted = df_melted.melt('Fecha_Corta', var_name='Métrica', value_name='Puntuación')
                    
                    grafica = alt.Chart(df_melted).mark_line(point=True).encode(
                        x=alt.X('Fecha_Corta:N', title='Fecha', sort=None, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Puntuación:Q', scale=alt.Scale(domain=[0, 10]), title='Escala (0-10)'),
                        color=alt.Color('Métrica:N', scale=alt.Scale(
                            domain=['Dolor (EVA)', 'Fatiga (Borg)'], 
                            range=["#aa3838", "#13765d"]
                        ))
                    ).properties(height=350)
                    
                    st.altair_chart(grafica, use_container_width=True)
                    
                    st.markdown("#### 💬 Historial de Comentarios")
                    df_comments = df_checkins[['Fecha_Larga', 'eva', 'borg', 'comment']].copy()
                    df_comments = df_comments.rename(columns={'Fecha_Larga': 'Fecha', 'eva': 'EVA', 'borg': 'Borg', 'comment': 'Comentario'})
                    st.dataframe(df_comments, use_container_width=True, hide_index=True)

    elif menu_seleccion == "🏋️ Programas de AF":
        st.markdown("<h1>🏋️ Programas de Actividad Física</h1>", unsafe_allow_html=True)
        tab_gest_af, tab_crear_af = tabs = st.tabs(["⚙️ Programas Activos", "📝 Crear Nuevo Programa AF"])
        
        with tab_gest_af:
            if st.session_state.get("editing_program_id"):
                target_pr = next((pr for pr in programs_af if str(pr["id"]) == str(st.session_state.editing_program_id)), None)
                if target_pr:
                    modal_editar_programa(target_pr)
                else:
                    st.session_state.editing_program_id = None

            search_query_af = st.text_input("🔍 Buscar programa por título o nombre del paciente:")
            progs_filtrados = list(reversed(programs_af))
            
            if search_query_af:
                q_af = search_query_af.lower()
                progs_filtrados = [pr for pr in progs_filtrados if q_af in pr["title"].lower() or q_af in get_patient_name(pr["patientId"]).lower()]

            if not progs_filtrados:
                st.info("No hay programas de AF que coincidan con la búsqueda.")
            else:
                for pr in progs_filtrados:
                    with st.container(border=True):
                        c_title, c_pin = st.columns([7, 3])
                        c_title.markdown(f"#### {pr['title']}")
                        c_pin.markdown(f"<div style='text-align:right;'><span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pr['pin']}</span></div>", unsafe_allow_html=True)
                        
                        c_pac, c_freq = st.columns([1, 1])
                        c_pac.write(f"👤 **Paciente:** {get_patient_name(pr['patientId'])}")
                        c_freq.markdown(f"<div style='text-align:right;'>⏱️ **{pr['frequency']} | {pr['duration']}**</div>", unsafe_allow_html=True)
                        
                        c_date, c_edit, c_copy, c_del = st.columns([5.5, 1.2, 1.4, 1.2])
                        c_date.write(f"📅 **Inicio:** {pr.get('startDate', 'No registrada')}")
                        with c_edit:
                            if st.button("✏️ Editar", key=f"edit_btn_af_{pr['id']}", use_container_width=True):
                                pr_id = pr["id"]
                                st.session_state.editing_program_id = pr_id
                                st.session_state[f"edit_af_{pr_id}_dias"] = max(1, len(pr["daysData"]))
                                for d_idx, day in enumerate(pr["daysData"]):
                                    st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] = max(1, len(day.get("blocks", [])))
                                    for b_idx, block in enumerate(day.get("blocks", [])):
                                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = [e["exerciseId"] for e in block.get("exercises", [])]
                                st.rerun()
                        with c_copy:
                            with st.popover("📋 Copiar", use_container_width=True):
                                st.caption("Copia el mensaje usando el icono de la esquina superior derecha:")
                                mensaje_wa_gen = f"¡Hola {get_patient_name(pr['patientId'])}! 👋\n\nAquí tienes tu programa de entrenamiento: *{pr['title']}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={pr['pin']}\n\n¡A entrenar!"
                                st.code(mensaje_wa_gen, language="markdown")
                        with c_del:
                            if st.session_state.confirm_delete_program_id == pr["id"]:
                                st.warning("Se borrará definitivamente este programa y su código de acceso dejará de funcionar.")
                                confirm_col, cancel_col = st.columns(2)
                                if confirm_col.button("Sí, borrar programa", key=f"confirm_del_program_{pr['id']}", type="primary", use_container_width=True):
                                    programs_af = [x for x in programs_af if str(x["id"]) != str(pr["id"])]
                                    save_programs_af(programs_af)
                                    st.session_state.confirm_delete_program_id = None
                                    st.rerun()
                                if cancel_col.button("Cancelar", key=f"cancel_del_program_{pr['id']}", use_container_width=True):
                                    st.session_state.confirm_delete_program_id = None
                                    st.rerun()
                            elif st.button("🗑️ Eliminar", key=f"del_af_{pr['id']}", use_container_width=True):
                                st.session_state.confirm_delete_program_id = pr["id"]
                                st.rerun()

        with tab_crear_af:
            if not patients:
                st.warning("Añade pacientes en el apartado 'Archivo' primero.")
            else:
                if "prio_dict" not in st.session_state:
                    st.session_state.prio_dict = {}
                    
                def _save_prio(k):
                    st.session_state.prio_dict[k] = st.session_state[k]

                st.markdown("### 📝 Diseñador de Programa Semanal de AF")
                
                col_p, col_t = st.columns([1, 2])
                af_paciente = col_p.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name, key="af_pac")
                af_titulo = col_t.text_input("2. Título del programa:", placeholder="Ej: Trabajo de fuerza ANA")
                
                col_f, col_d = st.columns(2)
                
                c_f1, c_f2 = col_f.columns([0.75, 0.25])
                af_frecuencia = c_f1.text_input("3. Frecuencia semanal:", placeholder="Ej: 3 o 3-4")
                c_f2.markdown("<div style='margin-top: 35px; color: #64756e; font-size: 15px;'>días/semana</div>", unsafe_allow_html=True)
                
                c_d1, c_d2 = col_d.columns([0.75, 0.25])
                af_duracion = c_d1.text_input("4. Duración por sesión:", placeholder="Ej: 20-30")
                c_d2.markdown("<div style='margin-top: 35px; color: #64756e; font-size: 15px;'>minutos/día</div>", unsafe_allow_html=True)
                
                opciones_ind_af_crear = {item["text"]: item["id"] for item in general_instructions}
                selected_ind_af_crear = st.multiselect("**5. Indicaciones generales:**", options=list(opciones_ind_af_crear.keys()), key="crear_af_indicaciones", placeholder="Selecciona las indicaciones para este programa...")
                selected_general_instruction_ids_af_crear = [opciones_ind_af_crear[x] for x in selected_ind_af_crear]

                af_nota_gen = st.text_input("6. Nota general explicativa:", value="*Los ejercicios con estrella ⭐ son los más recomendados para ti de cada bloque.")
                
                st.divider()
                st.markdown("### 📅 Días y Bloques de Ejercicios")
                
                if 'num_dias' not in st.session_state:
                    st.session_state.num_dias = 1
                
                col_btn_d1, col_btn_d2 = st.columns(2)
                if col_btn_d1.button("➕ Añadir Día al Plan"):
                    st.session_state.num_dias += 1
                    st.rerun()
                if col_btn_d2.button("➖ Quitar Último Día") and st.session_state.num_dias > 1:
                    st.session_state.num_dias -= 1
                    st.rerun()

                dias_construidos = []
                falta_algun_video_af = False

                # Portapapeles temporal para copiar/pegar bloques dentro del mismo
                # programa de AF que se está diseñando. No se guarda en Google Sheets.
                if "af_block_clipboard" not in st.session_state:
                    st.session_state.af_block_clipboard = None

                for d_idx in range(st.session_state.num_dias):
                    st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
                    
                    d_titulo = st.text_input(f"Título del Día {d_idx + 1}:", placeholder=f"Ej: Día {d_idx + 1}: extremidad superior", key=f"dtit_{d_idx}")
                    
                    key_num_bloques = f"num_bloques_d_{d_idx}"
                    if key_num_bloques not in st.session_state:
                        st.session_state[key_num_bloques] = 1

                    cb1, cb2, cb3 = st.columns(3)
                    if cb1.button(f"➕ Añadir Bloque al Día {d_idx + 1}", key=f"addb_{d_idx}"):
                        st.session_state[key_num_bloques] += 1
                        st.rerun()
                    if cb2.button(f"➖ Quitar Bloque al Día {d_idx + 1}", key=f"delb_{d_idx}") and st.session_state[key_num_bloques] > 1:
                        st.session_state[key_num_bloques] -= 1
                        st.rerun()

                    pegar_bloque = cb3.button(
                        "📥 Pegar bloque copiado",
                        key=f"pasteb_{d_idx}",
                        disabled=st.session_state.af_block_clipboard is None,
                        help="Añade al final de este día una copia exacta del último bloque que hayas copiado."
                    )
                    if pegar_bloque and st.session_state.af_block_clipboard is not None:
                        nuevo_b_idx = st.session_state[key_num_bloques]
                        st.session_state[key_num_bloques] += 1
                        st.session_state.af_pending_paste = {
                            "d_idx": d_idx,
                            "b_idx": nuevo_b_idx,
                            "block": deepcopy(st.session_state.af_block_clipboard)
                        }
                        st.rerun()

                    bloques_dia = []

                    for b_idx in range(st.session_state[key_num_bloques]):
                        pending_paste = st.session_state.get("af_pending_paste")
                        if (
                            pending_paste
                            and pending_paste.get("d_idx") == d_idx
                            and pending_paste.get("b_idx") == b_idx
                        ):
                            pasted_block = pending_paste["block"]
                            pasted_category = pasted_block.get("blockCategory", CATEGORIAS_EJ[0])
                            if pasted_category not in CATEGORIAS_EJ:
                                pasted_category = CATEGORIAS_EJ[0]

                            st.session_state[f"bcat_{d_idx}_{b_idx}"] = pasted_category
                            st.session_state[f"breg_{d_idx}_{b_idx}"] = pasted_block.get("blockRule", "")

                            pasted_exercises = pasted_block.get("exercises", [])
                            pasted_ids = [
                                ex.get("exerciseId")
                                for ex in pasted_exercises
                                if ex.get("exerciseId") and get_exercise(ex.get("exerciseId"))
                            ]
                            st.session_state[f"orden_af_{d_idx}_{b_idx}"] = pasted_ids.copy()

                            pasted_names = [
                                get_exercise(eid)["name"]
                                for eid in pasted_ids
                                if get_exercise(eid)
                                and get_main_category(get_exercise(eid).get("category")) == pasted_category
                            ]
                            st.session_state[f"bejs_{d_idx}_{b_idx}"] = pasted_names

                            for ex in pasted_exercises:
                                eid = ex.get("exerciseId")
                                if not eid or not get_exercise(eid):
                                    continue
                                st.session_state[f"saf_{d_idx}_{b_idx}_{eid}"] = ex.get("series", "")
                                st.session_state[f"raf_{d_idx}_{b_idx}_{eid}"] = ex.get("reps", "")
                                st.session_state[f"naf_{d_idx}_{b_idx}_{eid}"] = ex.get(
                                    "notes",
                                    get_exercise(eid).get("defaultNote", "")
                                )
                                prio_key_paste = f"prio_{d_idx}_{b_idx}_{eid}"
                                st.session_state[prio_key_paste] = bool(ex.get("isPriority", False))
                                st.session_state.prio_dict[prio_key_paste] = bool(ex.get("isPriority", False))

                            st.session_state.af_pending_paste = None

                        with st.container(border=True):
                            col_block_title, col_block_copy = st.columns([4, 1])
                            with col_block_title:
                                st.markdown(f"**Bloque {b_idx + 1}**")
                            
                            c_cat, c_sub, c_reg = st.columns([1.2, 1.2, 2])
                            b_cat = c_cat.selectbox("Categoría del bloque:", CATEGORIAS_EJ, key=f"bcat_{d_idx}_{b_idx}")
                            
                            b_subcat = "Todos"
                            if b_cat == "EEII":
                                b_subcat = c_sub.selectbox("Filtro EEII:", ["Todos", "EEII (General)", "EEII (3FE)", "EEII (H-H)"], key=f"bsub_{d_idx}_{b_idx}")
                                
                            b_regla = c_reg.text_input("Regla / Indicación (opcional):", placeholder="Ej: (elegir 3)", key=f"breg_{d_idx}_{b_idx}")
                            
                            with col_block_copy:
                                if st.button(
                                    "📋 Copiar",
                                    key=f"copyb_{d_idx}_{b_idx}",
                                    use_container_width=True,
                                    help="Copia este bloque completo para poder pegarlo en otro día."
                                ):
                                    copied_exercises = []
                                    for copied_eid in st.session_state.get(f"orden_af_{d_idx}_{b_idx}", []):
                                        copied_obj = get_exercise(copied_eid)
                                        if not copied_obj:
                                            continue
                                        copied_exercises.append({
                                            "exerciseId": copied_eid,
                                            "isPriority": bool(st.session_state.get(f"prio_{d_idx}_{b_idx}_{copied_eid}", False)),
                                            "series": st.session_state.get(f"saf_{d_idx}_{b_idx}_{copied_eid}", ""),
                                            "reps": st.session_state.get(f"raf_{d_idx}_{b_idx}_{copied_eid}", ""),
                                            "notes": st.session_state.get(
                                                f"naf_{d_idx}_{b_idx}_{copied_eid}",
                                                copied_obj.get("defaultNote", "")
                                            ),
                                        })

                                    st.session_state.af_block_clipboard = {
                                        "blockTitle": f"{b_cat} {b_regla}".strip(),
                                        "blockCategory": b_cat,
                                        "blockRule": b_regla,
                                        "exercises": copied_exercises,
                                    }
                                    st.session_state.af_pending_paste = None
                                    st.toast("Bloque copiado. Ya puedes pegarlo en otro día.", icon="📋")

                            if f"orden_af_{d_idx}_{b_idx}" not in st.session_state:
                                st.session_state[f"orden_af_{d_idx}_{b_idx}"] = []

                            current_block_ids = st.session_state[f"orden_af_{d_idx}_{b_idx}"]
                            nombres_actuales_af = [get_exercise(eid)["name"] for eid in current_block_ids if get_exercise(eid) and get_main_category(get_exercise(eid)["category"]) == b_cat]

                            ej_options_block = {}
                            for e in exercises:
                                cat_e = e.get("category", "")
                                if get_main_category(cat_e) == b_cat:
                                    mostrar = True
                                    if b_cat == "EEII" and b_subcat != "Todos":
                                        if b_subcat == "EEII (General)" and cat_e != "EEII": mostrar = False
                                        elif b_subcat == "EEII (3FE)" and cat_e != "EEII (3FE)": mostrar = False
                                        elif b_subcat == "EEII (H-H)" and cat_e != "EEII (H-H)": mostrar = False
                                    
                                    if mostrar or (e["name"] in nombres_actuales_af):
                                        ej_options_block[e["name"]] = e["id"]

                            sorted_options = sorted(ej_options_block.keys(), key=lambda x: x.lower())
                            ej_options_block_sorted = {k: ej_options_block[k] for k in sorted_options}

                            b_selected_names = st.multiselect("Ejercicios:", options=list(ej_options_block_sorted.keys()), default=nombres_actuales_af, key=f"bejs_{d_idx}_{b_idx}", label_visibility="collapsed")
                            
                            new_ids = [ej_options_block_sorted[n] for n in b_selected_names]
                            st.session_state[f"orden_af_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"orden_af_{d_idx}_{b_idx}"] if e in new_ids]
                            for e in new_ids:
                                if e not in st.session_state[f"orden_af_{d_idx}_{b_idx}"]:
                                    st.session_state[f"orden_af_{d_idx}_{b_idx}"].append(e)

                            ejs_bloque_info = []
                            if st.session_state[f"orden_af_{d_idx}_{b_idx}"]:
                                for idx_e, eid in enumerate(st.session_state[f"orden_af_{d_idx}_{b_idx}"]):
                                    ej_obj = get_exercise(eid)
                                    ename = ej_obj['name'] if ej_obj else "Ejercicio"
                                    sin_video_af = False

                                    if ej_obj and not tiene_video_valido(ej_obj.get("videoUrl", "")):
                                        sin_video_af = True
                                        falta_algun_video_af = True
                                        ename += " ⚠️"

                                    ce1, ce2, ce3, ce4, ce5, ce6, ce7 = st.columns([3, 1, 1, 2, 1.5, 0.6, 0.6])
                                    with ce1:
                                        col_text = "#aa3838" if sin_video_af else "inherit"
                                        st.markdown(f"<div style='margin-top:6px; font-weight:bold; color:{col_text}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx_e+1}. {ename}</div>", unsafe_allow_html=True)
                                    with ce2:
                                        s = st.text_input("S", key=f"saf_{d_idx}_{b_idx}_{eid}", placeholder="Ser", label_visibility="collapsed")
                                    with ce3:
                                        r = st.text_input("R", key=f"raf_{d_idx}_{b_idx}_{eid}", placeholder="Rep", label_visibility="collapsed")
                                    with ce4:
                                        n_key = f"naf_{d_idx}_{b_idx}_{eid}"
                                        if n_key not in st.session_state:
                                            st.session_state[n_key] = (ej_obj.get("defaultNote", "") if ej_obj else "")
                                        n = st.text_input("N", key=n_key, placeholder="Nota", label_visibility="collapsed")
                                    with ce5:
                                        prio_key = f"prio_{d_idx}_{b_idx}_{eid}"
                                        if prio_key not in st.session_state.prio_dict:
                                            st.session_state.prio_dict[prio_key] = False
                                        es_prio = st.checkbox("⭐ Prio", value=st.session_state.prio_dict[prio_key], key=prio_key, on_change=_save_prio, args=(prio_key,))
                                    with ce6:
                                        if st.button("⬆️", key=f"up_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                                            st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e], st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e-1]
                                            st.rerun()
                                    with ce7:
                                        if st.button("⬇️", key=f"dn_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"orden_af_{d_idx}_{b_idx}"])-1:
                                            st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e], st.session_state[f"orden_af_{d_idx}_{b_idx}"][idx_e+1]
                                            st.rerun()
                                    
                                    ejs_bloque_info.append({
                                        "exerciseId": eid,
                                        "isPriority": es_prio,
                                        "series": s,
                                        "reps": r,
                                        "notes": n
                                    })
                            
                            bloques_dia.append({
                                "blockTitle": f"{b_cat} {b_regla}".strip(),
                                "blockCategory": b_cat,
                                "blockRule": b_regla,
                                "exercises": ejs_bloque_info
                            })
                            
                    dias_construidos.append({
                        "dayTitle": d_titulo,
                        "blocks": bloques_dia
                    })

                st.write("")
                if falta_algun_video_af:
                    st.warning("⚠️ Hay ejercicios marcados en rojo que no tienen vídeo asignado.")
                
                if st.button("💾 Guardar Programa de AF", type="primary"):
                    if not af_titulo.strip() or not af_frecuencia.strip() or not af_duracion.strip():
                        st.warning("⚠️ Faltan campos básicos (título, frecuencia o duración).")
                    else:
                        hay_ejercicios = any(len(b["exercises"]) > 0 for d in dias_construidos for b in d["blocks"])
                        if not hay_ejercicios:
                            st.warning("⚠️ Debes añadir al menos un ejercicio en alguno de los bloques.")
                        else:
                            nuevo_pin_af = generate_unique_access_code()
                            programs_af.append({
                                "id": str(uuid.uuid4()),
                                "patientId": af_paciente,
                                "title": af_titulo,
                                "frequency": af_frecuencia,
                                "duration": af_duracion,
                                "generalInstructionIds": selected_general_instruction_ids_af_crear,
                                "generalNote": af_nota_gen,
                                "pin": nuevo_pin_af,
                                "startDate": datetime.date.today().strftime("%d/%m/%Y"),
                                "daysData": dias_construidos
                            })
                            save_programs_af(programs_af)
                            
                            for k in list(st.session_state.keys()):
                                if k.startswith("orden_af_") or k.startswith("dtit_") or k.startswith("num_bloques_"):
                                    del st.session_state[k]
                            st.session_state.num_dias = 1
                            st.session_state.prio_dict = {}
                            st.session_state.af_block_clipboard = None
                            
                            st.success("¡Programa de AF guardado con éxito!")
                            
                            nombre_pac = get_patient_name(af_paciente)
                            mensaje_wa = f"¡Hola {nombre_pac}! 👋\n\nAquí tienes tu programa de entrenamiento: *{af_titulo}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={nuevo_pin_af}\n\n¡A entrenar!"
                            st.info("Copia el mensaje a continuación para enviarlo por WhatsApp:")
                            st.code(mensaje_wa, language="markdown")

else:
    # =============================================================
    # MÓDULO 2: ÁREA DEL PACIENTE / INICIO SESIÓN
    # =============================================================
    params = st.query_params
    pin_from_url = extract_pin_from_input(params.get("pin", ""))
    
    if st.session_state.logged_pin is None:
        if pin_from_url and st.session_state.failed_login_attempts == 0:
            st.session_state.logged_pin = normalize_access_code(pin_from_url)
            st.rerun()

        st.markdown("<div style='text-align: center; margin-top: 50px;'><h1 style='color: var(--green) !important;'>🩺 FisioSesión</h1><p style='color: var(--muted) !important; font-size: 18px;'>Acceso a tu programa de recuperación</p></div>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.write("")
            with st.container(border=True):
                if login_is_temporarily_locked():
                    tiempo_restante = (st.session_state.login_locked_until - datetime.datetime.now()).seconds // 60
                    st.error(f"🔒 Acceso bloqueado temporalmente por demasiados intentos fallidos. Inténtalo de nuevo en {tiempo_restante + 1} minutos.")
                else:
                    pin_input = st.text_input("🔑 Código de acceso o enlace:", type="password", help="Pega aquí el enlace que te ha enviado tu fisio, o solo el código PIN.")
                    if st.button("Entrar", type="primary", use_container_width=True):
                        codigo_limpio = extract_pin_from_input(pin_input)
                        if access_code_matches(codigo_limpio, get_admin_access_code()):
                            reset_login_attempts()
                            st.session_state.admin_mode = True
                            st.rerun()
                        else:
                            encontrado = False
                            for pl in plans:
                                if access_code_matches(codigo_limpio, pl.get("pin", "")):
                                    encontrado = True
                                    break
                            if not encontrado:
                                for pr in programs_af:
                                    if access_code_matches(codigo_limpio, pr.get("pin", "")):
                                        encontrado = True
                                        break
                                        
                            if encontrado:
                                reset_login_attempts()
                                st.session_state.logged_pin = normalize_access_code(codigo_limpio)
                                st.rerun()
                            else:
                                register_failed_login()
                                st.error("❌ Código incorrecto o sesión no encontrada.")

    else:
        # PACIENTE LOGUEADO
        codigo_actual = st.session_state.logged_pin
        
        es_admin = access_code_matches(codigo_actual, get_admin_access_code())
        if es_admin:
            st.session_state.admin_mode = True
            st.rerun()
            
        plan_encontrado = next((pl for pl in plans if access_code_matches(codigo_actual, pl.get("pin", ""))), None)
        prog_encontrado = next((pr for pr in programs_af if access_code_matches(codigo_actual, pr.get("pin", ""))), None)

        c_logo, c_out = st.columns([8, 2])
        c_logo.markdown("<h3 style='color:var(--green) !important; margin:0;'>🩺 FisioSesión</h3>", unsafe_allow_html=True)
        if c_out.button("🚪 Salir", use_container_width=True):
            st.session_state.logged_pin = None
            st.rerun()
            
        st.divider()

        if plan_encontrado:
            nombre_pac = get_patient_name(plan_encontrado["patientId"])
            
            # --- Lógica de Reporte del Paciente (Check-in) ---
            if "mostrar_form_checkin" not in st.session_state:
                st.session_state.mostrar_form_checkin = False

            if st.session_state.mostrar_form_checkin:
                st.markdown(f"<h2>¡Buen trabajo, {nombre_pac}! 🎉</h2>", unsafe_allow_html=True)
                st.write("Por favor, rellena este breve reporte para que tu fisio sepa cómo ha ido.")
                with st.form("checkin_form", clear_on_submit=True):
                    c_eva, c_borg = st.columns(2)
                    eva_val = c_eva.slider("💥 Nivel de Dolor (EVA)", 0, 10, 0, help="0 = Nada de dolor, 10 = El peor dolor imaginable")
                    borg_val = c_borg.slider("🥵 Nivel de Fatiga (Borg)", 0, 10, 0, help="0 = Nada de cansancio, 10 = Esfuerzo máximo absoluto")
                    
                    # Calcular tiempo estimado de la sesión con el progreso guardado
                    progreso = get_progreso_sesion(plan_encontrado["id"])
                    tiempo_sugerido = 0
                    if progreso.get("opened_at"):
                        try:
                            inicio = datetime.datetime.strptime(progreso["opened_at"], "%Y-%m-%d %H:%M:%S")
                            minutos_transcurridos = int((datetime.datetime.now() - inicio).total_seconds() / 60)
                            # Si ha pasado un tiempo razonable (entre 1 y 120 min), lo sugerimos
                            if 1 <= minutos_transcurridos <= 120:
                                tiempo_sugerido = minutos_transcurridos
                        except Exception:
                            pass
                            
                    dur_min = st.number_input("⏱️ ¿Cuántos minutos ha durado la sesión aproximadamente?", min_value=1, max_value=300, value=tiempo_sugerido if tiempo_sugerido > 0 else 30)
                    
                    comentario_val = st.text_area("💬 Comentarios o sensaciones (opcional)", placeholder="Ej: Me ha costado el último ejercicio, pero el dolor en la rodilla ha bajado...")
                    
                    if st.form_submit_button("📤 Enviar Reporte al Fisio", type="primary", use_container_width=True):
                        ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_checkin_item(plan_encontrado["id"], ahora_str, eva_val, borg_val, comentario_val, dur_min)
                        st.session_state.mostrar_form_checkin = False
                        # Borrar el progreso en vivo para la próxima vez
                        guardar_progreso_sesion(plan_encontrado["id"], "", [])
                        st.success("¡Reporte enviado! Muchas gracias.")
                        st.balloons()
                        st.rerun()
                        
                if st.button("Cancelar"):
                    st.session_state.mostrar_form_checkin = False
                    st.rerun()
                    
            else:
                # --- Vista Principal de la Sesión Clínica ---
                st.markdown(f"<h2>Hola, {nombre_pac} 👋</h2>", unsafe_allow_html=True)
                st.markdown(f"**Tu sesión:** {plan_encontrado['title']}")
                
                # Sincronizar el progreso en vivo de esta sesión
                progreso_actual = get_progreso_sesion(plan_encontrado["id"])
                
                # Si el progreso es muy antiguo (de un día anterior), lo reiniciamos
                # automáticamente para no arrastrar checks viejos a una nueva sesión.
                if progreso_actual.get("opened_at"):
                    try:
                        inicio = datetime.datetime.strptime(progreso_actual["opened_at"], "%Y-%m-%d %H:%M:%S")
                        horas_transcurridas = (datetime.datetime.now() - inicio).total_seconds() / 3600
                        if horas_transcurridas > LIMITE_INACTIVIDAD_HORAS:
                            progreso_actual["opened_at"] = ""
                            progreso_actual["checked_exercises"] = []
                    except Exception:
                        pass
                
                # Si se abre de cero (o se acaba de reiniciar), fichamos la hora
                if not progreso_actual.get("opened_at"):
                    progreso_actual["opened_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    guardar_progreso_sesion(plan_encontrado["id"], progreso_actual["opened_at"], progreso_actual["checked_exercises"])

                checks_state = set(progreso_actual.get("checked_exercises", []))

                render_general_instructions_box(plan_encontrado.get("generalInstructionIds", []))
                
                total_ejercicios = len(plan_encontrado["exerciseIds"])
                completados = len([e for e in plan_encontrado["exerciseIds"] if e in checks_state])
                if total_ejercicios > 0:
                    progreso_pct = int((completados / total_ejercicios) * 100)
                    st.progress(progreso_pct, text=f"Progreso: {completados} de {total_ejercicios} ejercicios completados")
                
                st.write("")
                for idx, e_id in enumerate(plan_encontrado["exerciseIds"]):
                    ej = get_exercise(e_id)
                    if not ej: continue
                    
                    inst = plan_encontrado["exerciseInstructions"].get(e_id, {})
                    s = inst.get("series", "")
                    r = inst.get("reps", "")
                    n = inst.get("notes", "")

                    ej_nombre_mostrar = nombre_para_paciente(ej)

                    with st.container(border=True):
                        c_title, c_check = st.columns([8.5, 1.5])
                        
                        marcado = e_id in checks_state
                        
                        def toggle_check(eid=e_id):
                            # Al hacer clic en el checkbox, recargamos el progreso más
                            # reciente directamente de la base de datos, lo modificamos y
                            # lo volvemos a guardar, para asegurar que la hora de inicio
                            # y el resto de checks no se pierdan.
                            p = get_progreso_sesion(plan_encontrado["id"])
                            current_checks = set(p.get("checked_exercises", []))
                            if eid in current_checks:
                                current_checks.remove(eid)
                            else:
                                current_checks.add(eid)
                            # Si no hay opened_at, la ponemos
                            op_at = p.get("opened_at")
                            if not op_at:
                                op_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            guardar_progreso_sesion(plan_encontrado["id"], op_at, list(current_checks))

                        c_check.checkbox("✅", value=marcado, key=f"chk_{e_id}_{idx}", on_change=toggle_check, label_visibility="collapsed")
                        
                        titulo_estilo = "color:var(--ink);" if not marcado else "color:var(--muted); text-decoration:line-through;"
                        c_title.markdown(f"<h4 style='{titulo_estilo} margin-bottom:5px;'>{idx + 1}. {ej_nombre_mostrar}</h4>", unsafe_allow_html=True)
                        
                        # Fila de datos (Series / Reps / Video)
                        cols_data = st.columns([2, 2, 6])
                        if s: cols_data[0].markdown(f"**Series:** {s}")
                        if r: cols_data[1].markdown(f"**Reps:** {r}")
                        
                        with cols_data[2]:
                            if tiene_video_valido(ej['videoUrl']):
                                st.link_button("▶️ Ver Vídeo", ej['videoUrl'], use_container_width=False, key=f"v_ses_{e_id}_{idx}")
                        
                        if n:
                            st.markdown(f"""
                            <div style='background-color:#fffef7; border-left:4px solid #f57f17; padding:10px 14px; margin-top:12px; border-radius:4px;'>
                                <span style='font-weight:600; color:#f57f17;'>💡 Nota:</span> <span style='color:#17352e; font-size:14px;'>{n}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                st.write("")
                if st.button("🏁 Finalizar y Enviar Reporte", type="primary", use_container_width=True):
                    st.session_state.mostrar_form_checkin = True
                    st.rerun()

        elif prog_encontrado:
            # --- Vista del Programa de Actividad Física (AF) ---
            nombre_pac_af = get_patient_name(prog_encontrado["patientId"])
            st.markdown(f"<h2>Hola, {nombre_pac_af} 👋</h2>", unsafe_allow_html=True)
            st.markdown(f"**Tu programa:** {prog_encontrado['title']}")
            
            c_f, c_d = st.columns(2)
            c_f.info(f"📅 **Frecuencia:** {prog_encontrado['frequency']} días/semana")
            c_d.info(f"⏱️ **Duración:** {prog_encontrado['duration']} min/día")
            
            if prog_encontrado.get("generalNote"):
                st.markdown(f"<div style='background:#fffef7; border-left:4px solid #f57f17; padding:12px 16px; margin-bottom:20px; border-radius:6px; font-size:14px;'>{prog_encontrado['generalNote']}</div>", unsafe_allow_html=True)

            render_general_instructions_box(prog_encontrado.get("generalInstructionIds", []))

            dias_data = prog_encontrado.get("daysData", [])
            if not dias_data:
                st.info("Este programa todavía no tiene días configurados.")
            else:
                titulos_tabs = [d.get("dayTitle", f"Día {i+1}") for i, d in enumerate(dias_data)]
                tabs_dias = st.tabs(titulos_tabs)
                
                for d_idx, tab_dia in enumerate(tabs_dias):
                    with tab_dia:
                        bloques = dias_data[d_idx].get("blocks", [])
                        if not bloques:
                            st.write("No hay bloques para este día.")
                        else:
                            for b_idx, block in enumerate(bloques):
                                st.markdown(f"<div style='background:#103d33; color:white; padding:8px 15px; border-radius:8px 8px 0 0; margin-top:20px;'><span style='font-weight:bold; font-size:16px;'>{block.get('blockTitle', f'Bloque {b_idx+1}')}</span></div>", unsafe_allow_html=True)
                                
                                ejercicios_b = block.get("exercises", [])
                                if not ejercicios_b:
                                    st.markdown("<div style='border:1px solid #dce7e2; border-top:none; padding:15px; border-radius:0 0 8px 8px; background:white;'>Sin ejercicios</div>", unsafe_allow_html=True)
                                else:
                                    with st.container(border=True):
                                        for idx_e, ex in enumerate(ejercicios_b):
                                            ej_obj = get_exercise(ex.get("exerciseId"))
                                            if not ej_obj: continue
                                            
                                            ej_nombre_mostrar = nombre_para_paciente(ej_obj)
                                            estrella = "⭐ " if ex.get("isPriority") else ""
                                            st.markdown(f"<h5 style='margin-bottom:6px; color:var(--ink);'>{idx_e+1}. {estrella}{ej_nombre_mostrar}</h5>", unsafe_allow_html=True)
                                            
                                            cd1, cd2, cd3 = st.columns([1.5, 1.5, 7])
                                            if ex.get("series"): cd1.markdown(f"**S:** {ex.get('series')}")
                                            if ex.get("reps"): cd2.markdown(f"**R:** {ex.get('reps')}")
                                            with cd3:
                                                if tiene_video_valido(ej_obj.get("videoUrl", "")):
                                                    st.link_button("▶️ Vídeo", ej_obj["videoUrl"], key=f"v_af_{prog_encontrado['id']}_{d_idx}_{b_idx}_{idx_e}")
                                                    
                                            if ex.get("notes"):
                                                st.markdown(f"<div style='color:#64756e; font-size:14px; margin-top:5px;'>*{ex.get('notes')}*</div>", unsafe_allow_html=True)
                                                
                                            if idx_e < len(ejercicios_b) - 1:
                                                st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)
        else:
            st.error("No se ha podido cargar la información de este PIN.")
