import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
import datetime
import secrets
import hmac
import uuid
import json

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
    button[data-testid="baseButton-primary"] { background-color: var(--green) !important; color: white !important; border-radius: 9px !important; }
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
            "review_date": p.get("review_date", ""),
            "revisions": json.dumps(p.get("revisions", []))
        })
    patient_columns = ["id", "name", "phone", "review_date", "revisions"]
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
                "videoUrl": clean_str(r.get("videoUrl", "")), 
                "category": clean_str(r.get("category", ""))
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_exercises(exercises_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    exercise_columns = ["id", "name", "videoUrl", "category"]
    conn.update(spreadsheet=SHEET_URL, worksheet="ejercicios", data=pd.DataFrame(exercises_list, columns=exercise_columns))
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
            "pin": p["pin"],
            "startDate": p.get("startDate", ""),
            "isActive": bool(p.get("isActive", True))
        })
    plan_columns = ["id", "patientId", "title", "exerciseIds", "exerciseInstructions", "pin", "startDate", "isActive"]
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
            "generalNote": p["generalNote"], "pin": p["pin"],
            "startDate": p.get("startDate", ""),
            "daysData": json.dumps(p["daysData"])
        })
    program_columns = ["id", "patientId", "title", "frequency", "duration", "generalNote", "pin", "startDate", "daysData"]
    conn.update(spreadsheet=SHEET_URL, worksheet="programas_af", data=pd.DataFrame(formatted, columns=program_columns))
    st.cache_data.clear()

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
                "comment": clean_str(r.get("comment", ""))
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_checkins(checkins_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return False
    checkin_columns = ["id", "planId", "date", "eva", "borg", "comment"]
    conn.update(spreadsheet=SHEET_URL, worksheet="checkins", data=pd.DataFrame(checkins_list, columns=checkin_columns))
    st.cache_data.clear()
    return True

def save_checkin_item(plan_id, date, eva, borg, comment):
    if st.session_state.gsheets_read_error:
        st.error("❌ Error de conexión temporal. Inténtalo de nuevo en unos segundos.")
        return
    checkins_data = get_checkins()
    checkins_data.append({"id": str(uuid.uuid4()), "planId": str(plan_id), "date": str(date), "eva": str(eva), "borg": str(borg), "comment": str(comment)})
    save_checkins(checkins_data)

# =============================================================
# CARGA DE DATOS
# =============================================================
patients = get_patients()
exercises = get_exercises()
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

def get_exercise(e_id):
    for e in exercises:
        if str(e["id"]) == str(e_id): return e
    return None

# =============================================================
# MÓDULO 1: ÁREA CLÍNICA
# =============================================================
if st.session_state.admin_mode:

    @st.dialog("✏️ Editar Sesión Clínica", width="large")
    def modal_editar_sesion(pl):
        pl_id = pl["id"]
        
        pac_idx = 0
        patient_ids = [p["id"] for p in patients]
        if pl["patientId"] in patient_ids:
            pac_idx = patient_ids.index(pl["patientId"])
            
        paciente_sel = st.selectbox("1. Cambiar Paciente:", options=patient_ids, format_func=get_patient_name, index=pac_idx)
        titulo_sesion = st.text_input("2. Título de la Sesión:", value=pl["title"])
        
        st.markdown("**3. Selecciona los ejercicios:**")
        ej_options_all = {}
        for cat in CATEGORIAS_EJ:
            ej_cat = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
            for e in ej_cat:
                ej_options_all[f"{cat}  |  {e['name']}"] = e['id']
                
        if f"edit_ses_{pl_id}_ejs" not in st.session_state:
            st.session_state[f"edit_ses_{pl_id}_ejs"] = pl["exerciseIds"].copy()

        nombres_actuales = []
        for eid in st.session_state[f"edit_ses_{pl_id}_ejs"]:
            eobj = get_exercise(eid)
            if eobj: nombres_actuales.append(f"{eobj['category']}  |  {eobj['name']}")
            
        selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options_all.keys()), default=nombres_actuales, label_visibility="collapsed")
        
        nuevos_ids = [ej_options_all[n] for n in selected_names]
        st.session_state[f"edit_ses_{pl_id}_ejs"] = [e for e in st.session_state[f"edit_ses_{pl_id}_ejs"] if e in nuevos_ids]
        for e in nuevos_ids:
            if e not in st.session_state[f"edit_ses_{pl_id}_ejs"]:
                st.session_state[f"edit_ses_{pl_id}_ejs"].append(e)

        instrucciones_dict = {}
        if st.session_state[f"edit_ses_{pl_id}_ejs"]:
            st.markdown("**4. Configuración y Orden:**")
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
                    n = st.text_input("N", value=prev_inst.get("notes", ""), key=f"en_{pl_id}_{e_id}", label_visibility="collapsed", placeholder="Notas")
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
        af_nota = st.text_input("5. Nota general:", value=pr["generalNote"])
        
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
                    
                    col_bcat, col_breg = st.columns([1, 2])
                    b_cat = col_bcat.selectbox("Categoría:", CATEGORIAS_EJ, index=CATEGORIAS_EJ.index(def_cat), key=f"ebcat_{pr_id}_{d_idx}_{b_idx}")
                    b_regla = col_breg.text_input("Regla / Indicación:", value=def_rule, key=f"ebreg_{pr_id}_{d_idx}_{b_idx}")
                    
                    ej_cat_filtrados = sorted([e for e in exercises if e.get("category") == b_cat], key=lambda x: x["name"].lower())
                    ej_options_block = {e["name"]: e["id"] for e in ej_cat_filtrados}
                    
                    if f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}" not in st.session_state:
                        default_ids = []
                        if old_block:
                            default_ids = [ex["exerciseId"] for ex in old_block.get("exercises", [])]
                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = default_ids
                        
                    current_block_ids = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]
                    default_names = [get_exercise(eid)["name"] for eid in current_block_ids if get_exercise(eid) and get_exercise(eid)["category"] == b_cat]
                    
                    b_selected_names = st.multiselect("Ejercicios:", options=list(ej_options_block.keys()), default=default_names, key=f"ebsel_{pr_id}_{d_idx}_{b_idx}", label_visibility="collapsed")
                    
                    new_ids = [ej_options_block[n] for n in b_selected_names]
                    st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] if e in new_ids]
                    for e in new_ids:
                        if e not in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]:
                            st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"].append(e)
                            
                    ejs_bloque_info = []
                    for idx_e, eid in enumerate(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]):
                        ename = get_exercise(eid)['name'] if get_exercise(eid) else "Ejercicio"
                        
                        def_prio = False
                        def_s = ""
                        def_r = ""
                        def_n = ""
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
        tab_pac, tab_ej = st.tabs(["👥 Pacientes", "🎥 Ejercicios"])
        
        with tab_pac:
            with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
                with st.form("nuevo_paciente_form", clear_on_submit=True):
                    c_np1, c_np2, c_np3 = st.columns([3, 1.5, 1.5])
                    new_p_name = c_np1.text_input("Nombre completo:")
                    new_p_phone = c_np2.text_input("Teléfono:")
                    new_p_review_input = c_np3.text_input("Próxima revisión (DD/MM/AAAA):", value="", placeholder="Ej: 15/03/2026")
                    
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
                    
                    ce1, ce2, ce3 = st.columns([3, 1.5, 1.5])
                    edit_name = ce1.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                    edit_phone = ce2.text_input("Teléfono", value=p.get("phone", ""), key=f"phone_{p['id']}")
                    
                    try:
                        curr_rev_display = datetime.datetime.strptime(p.get("review_date", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
                    except:
                        curr_rev_display = ""
                    edit_review_input = ce3.text_input("Próxima revisión (DD/MM/AAAA)", value=curr_rev_display, key=f"rev_{p['id']}", placeholder="Ej: 15/03/2026")
                    
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
                
                cn1, cn2, cn3, cn4 = st.columns([4, 4, 3, 1.5])
                with cn1:
                    new_n = st.text_input("new_n", placeholder="Nombre del ejercicio...", label_visibility="collapsed")
                with cn2:
                    new_u = st.text_input("new_u", placeholder="Enlace de YouTube...", label_visibility="collapsed")
                with cn3:
                    new_c = st.selectbox("new_c", CATEGORIAS_EJ, label_visibility="collapsed")
                with cn4:
                    btn_add = st.form_submit_button("➕ Añadir", type="primary", use_container_width=True)
                
                if btn_add:
                    if new_n.strip():
                        exercises.append({
                            "id": str(uuid.uuid4()),
                            "name": new_n.strip(),
                            "videoUrl": new_u.strip(),
                            "category": new_c
                        })
                        save_exercises(exercises)
                        st.success("¡Ejercicio añadido a la base de datos!")
                        st.rerun()
                    else:
                        st.warning("⚠️ El nombre del ejercicio es obligatorio.")
            
            st.write("")
            
            with st.form("form_editar_ejercicios"):
                btn_save = st.form_submit_button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True)
                
                st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)
                
                nuevos_datos = {}
                ids_borrar = []
                
                c_h1, c_h2, c_h3, c_h4 = st.columns([4, 4, 3, 1.5])
                c_h1.caption("NOMBRE")
                c_h2.caption("ENLACE YOUTUBE")
                c_h3.caption("CATEGORÍA")
                c_h4.caption("ACCIÓN")
                
                for cat in CATEGORIAS_EJ:
                    ej_cat = [e for e in exercises if e.get("category") == cat]
                    ej_cat = sorted(ej_cat, key=lambda x: x["name"].lower())
                    
                    if ej_cat:
                        st.markdown(f"<div style='color:var(--dark); font-weight:bold; font-size:16px; margin: 15px 0 5px 0; border-bottom: 1px solid var(--line);'>{cat} (Total: {len(ej_cat)})</div>", unsafe_allow_html=True)
                        for e in ej_cat:
                            eid = e["id"]
                            c1, c2, c3, c4 = st.columns([4, 4, 3, 1.5])
                            with c1:
                                n = st.text_input("n", value=e["name"], key=f"n_{eid}", label_visibility="collapsed")
                            with c2:
                                u = st.text_input("u", value=e["videoUrl"], key=f"u_{eid}", label_visibility="collapsed")
                            with c3:
                                idx = CATEGORIAS_EJ.index(e["category"]) if e["category"] in CATEGORIAS_EJ else 0
                                c = st.selectbox("c", CATEGORIAS_EJ, index=idx, key=f"c_{eid}", label_visibility="collapsed")
                            with c4:
                                b = st.checkbox("🗑️ Borrar", key=f"del_{eid}")
                                
                            nuevos_datos[eid] = {"id": eid, "name": n, "videoUrl": u, "category": c}
                            if b: ids_borrar.append(eid)
                            
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
                
                ej_options = {}
                for cat in CATEGORIAS_EJ:
                    ej_ordenados = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
                    for e in ej_ordenados:
                        ej_options[f"{cat}  |  {e['name']}"] = e['id']
                
                selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options.keys()), label_visibility="collapsed", placeholder="Escribe o despliega para buscar...")
                
                if 'orden_ejs' not in st.session_state:
                    st.session_state.orden_ejs = []
                
                ejs_seleccionados = [ej_options[name] for name in selected_names]
                st.session_state.orden_ejs = [e for e in st.session_state.orden_ejs if e in ejs_seleccionados]
                for e in ejs_seleccionados:
                    if e not in st.session_state.orden_ejs:
                        st.session_state.orden_ejs.append(e)
                
                instrucciones_dict = {}
                has_missing_videos = False

                if st.session_state.orden_ejs:
                    st.markdown("**4. Configuración y Orden:**")
                    
                    c_th, c_sh, c_rh, c_nh, c_x1, c_x2 = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                    c_th.caption("EJERCICIO")
                    c_sh.caption("SERIES")
                    c_rh.caption("REPS")
                    c_nh.caption("NOTAS EXTRA")
                    
                    for idx, e_id in enumerate(st.session_state.orden_ejs):
                        ej_obj = get_exercise(e_id)
                        ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                        sin_video = False
                        
                        if ej_obj and not ej_obj.get("videoUrl", "").strip():
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
                            n = st.text_input("N", key=f"not_{e_id}", placeholder="Notas...", label_visibility="collapsed")
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
                                mensaje_wa_gen = f"¡Hola {get_patient_name(pr['patientId'])}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{pr['title']}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={pr['pin']}\n\n¡A entrenar!"
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
                
                af_nota_gen = st.text_input("5. Nota general explicativa:", value="*Los ejercicios con estrella ⭐ son los más recomendados para ti de cada bloque.")
                
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

                for d_idx in range(st.session_state.num_dias):
                    st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
                    
                    d_titulo = st.text_input(f"Título del Día {d_idx + 1}:", placeholder=f"Ej: Día {d_idx + 1}: extremidad superior", key=f"dtit_{d_idx}")
                    
                    key_num_bloques = f"num_bloques_d_{d_idx}"
                    if key_num_bloques not in st.session_state:
                        st.session_state[key_num_bloques] = 1

                    cb1, cb2 = st.columns(2)
                    if cb1.button(f"➕ Añadir Bloque al Día {d_idx + 1}", key=f"addb_{d_idx}"):
                        st.session_state[key_num_bloques] += 1
                        st.rerun()
                    if cb2.button(f"➖ Quitar Bloque al Día {d_idx + 1}", key=f"delb_{d_idx}") and st.session_state[key_num_bloques] > 1:
                        st.session_state[key_num_bloques] -= 1
                        st.rerun()

                    bloques_dia = []

                    for b_idx in range(st.session_state[key_num_bloques]):
                        with st.container(border=True):
                            st.markdown(f"**Bloque {b_idx + 1}**")
                            col_bcat, col_breg = st.columns([1, 2])
                            
                            b_cat = col_bcat.selectbox("Categoría del bloque:", CATEGORIAS_EJ, key=f"bcat_{d_idx}_{b_idx}")
                            b_regla = col_breg.text_input("Regla / Indicación (opcional):", placeholder="Ej: (elegir 3)", key=f"breg_{d_idx}_{b_idx}")
                            
                            b_nombre_completo = f"{b_cat} {b_regla}".strip()
                            
                            ej_cat_filtrados = sorted([e for e in exercises if e.get("category") == b_cat], key=lambda x: x["name"].lower())
                            ej_options_block = {e["name"]: e["id"] for e in ej_cat_filtrados}
                            
                            b_selected_names = st.multiselect(
                                f"Ejercicios de {b_cat}:", 
                                options=list(ej_options_block.keys()), 
                                key=f"bejs_{d_idx}_{b_idx}",
                                placeholder=f"Selecciona ejercicios..."
                            )
                            
                            key_order_af = f"orden_af_{d_idx}_{b_idx}"
                            if key_order_af not in st.session_state:
                                st.session_state[key_order_af] = []
                                
                            selected_ids = [ej_options_block[name] for name in b_selected_names if name in ej_options_block]
                            st.session_state[key_order_af] = [e for e in st.session_state[key_order_af] if e in selected_ids]
                            for e in selected_ids:
                                if e not in st.session_state[key_order_af]:
                                    st.session_state[key_order_af].append(e)

                            ejs_bloque_info = []
                            if st.session_state[key_order_af]:
                                st.caption("Ordena y configura los ejercicios con sus series y repeticiones:")
                                for idx_e, eid in enumerate(st.session_state[key_order_af]):
                                    ej_obj = get_exercise(eid)
                                    ename = ej_obj['name'] if ej_obj else "Ejercicio"
                                    sin_video_af = False
                                    
                                    if ej_obj and not ej_obj.get("videoUrl", "").strip():
                                        sin_video_af = True
                                        falta_algun_video_af = True
                                        ename += " ⚠️ (SIN VÍDEO)"
                                    
                                    # Ajuste para añadir campos de Series y Reps en la misma línea
                                    col_e_name, col_s, col_r, col_n, col_e_prio, col_e_up, col_e_dn = st.columns([3, 1, 1, 2, 1.5, 0.6, 0.6])
                                    with col_e_name:
                                        color_t = "#aa3838" if sin_video_af else "inherit"
                                        st.markdown(f"<div style='margin-top:6px; font-weight:bold; color:{color_t}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx_e + 1}. {ename}</div>", unsafe_allow_html=True)
                                    with col_s:
                                        s = st.text_input("S", key=f"saf_{d_idx}_{b_idx}_{eid}", placeholder="Ser", label_visibility="collapsed")
                                    with col_r:
                                        r = st.text_input("R", key=f"raf_{d_idx}_{b_idx}_{eid}", placeholder="Rep", label_visibility="collapsed")
                                    with col_n:
                                        n = st.text_input("N", key=f"naf_{d_idx}_{b_idx}_{eid}", placeholder="Nota", label_visibility="collapsed")
                                    with col_e_prio:
                                        prio_key = f"prio_{d_idx}_{b_idx}_{eid}"
                                        if prio_key not in st.session_state:
                                            st.session_state[prio_key] = st.session_state.prio_dict.get(prio_key, False)
                                        es_prio = st.checkbox("⭐ Prio", key=prio_key, on_change=_save_prio, args=(prio_key,))
                                    with col_e_up:
                                        if st.button("⬆️", key=f"up_{d_idx}_{b_idx}_{eid}"):
                                            if idx_e > 0:
                                                st.session_state[key_order_af][idx_e-1], st.session_state[key_order_af][idx_e] = st.session_state[key_order_af][idx_e], st.session_state[key_order_af][idx_e-1]
                                                st.rerun()
                                    with col_e_dn:
                                        if st.button("⬇️", key=f"dn_{d_idx}_{b_idx}_{eid}"):
                                            if idx_e < len(st.session_state[key_order_af]) - 1:
                                                st.session_state[key_order_af][idx_e+1], st.session_state[key_order_af][idx_e] = st.session_state[key_order_af][idx_e+1], st.session_state[key_order_af][idx_e]
                                                st.rerun()

                                    ejs_bloque_info.append({"exerciseId": eid, "isPriority": es_prio, "series": s, "reps": r, "notes": n})

                            bloques_dia.append({
                                "blockTitle": b_nombre_completo,
                                "blockCategory": b_cat,
                                "blockRule": b_regla,
                                "exercises": ejs_bloque_info
                            })

                    dias_construidos.append({
                        "dayTitle": d_titulo,
                        "blocks": bloques_dia
                    })

                st.divider()
                
                if falta_algun_video_af:
                    st.warning("⚠️ Atención: Hay ejercicios marcados en rojo que no tienen vídeo de YouTube asignado. El paciente verá el nombre del ejercicio pero no tendrá enlace al vídeo.")
                    
                if st.button("💾 Guardar y Crear Programa de AF", type="primary", use_container_width=True):
                    if not af_titulo.strip() or not af_frecuencia.strip() or not af_duracion.strip():
                        st.warning("⚠️ Faltan campos por rellenar: Asegúrate de completar el título del programa, la frecuencia y la duración.")
                    else:
                        faltan_titulos_dias = any(not d["dayTitle"].strip() for d in dias_construidos)
                        if faltan_titulos_dias:
                            st.warning("⚠️ Faltan campos por rellenar: Comprueba que todos los Días creados tengan un 'Título del Día'.")
                        else:
                            nuevo_pin_af = generate_unique_access_code()
                            frecuencia_guardar = f"{af_frecuencia.strip()} días/semana" if af_frecuencia.strip() else ""
                            duracion_guardar = f"{af_duracion.strip()} minutos/día" if af_duracion.strip() else ""
                            
                            programs_af.append({
                                "id": str(uuid.uuid4()),
                                "patientId": af_paciente,
                                "title": af_titulo,
                                "frequency": frecuencia_guardar,
                                "duration": duracion_guardar,
                                "generalNote": af_nota_gen,
                                "pin": nuevo_pin_af,
                                "startDate": datetime.date.today().strftime("%d/%m/%Y"),
                                "daysData": dias_construidos
                            })
                            save_programs_af(programs_af)
                            st.session_state.prio_dict = {} 
                            st.success("¡Programa de AF creado con éxito!")
                            
                            nombre_p = get_patient_name(af_paciente)
                            mensaje_wa_gen = f"¡Hola {nombre_p}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{af_titulo}*.\n\n📱 Pulsa en el enlace para entrar directamente:\n{APP_URL}/?pin={nuevo_pin_af}\n\n¡A por todas!"
                            st.info("Copia el mensaje para mandarlo por WhatsApp:")
                            st.code(mensaje_wa_gen, language="markdown")

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE / FORMULARIO LOGIN
# =============================================================
else:
    # Auto-acceso: si el paciente entra desde el enlace con el código incluido (?pin=...),
    # entramos directamente a su sesión sin que tenga que escribir ni pegar nada.
    if not st.session_state.logged_pin and not st.session_state.admin_mode and not login_is_temporarily_locked():
        try:
            qp_pin_raw = st.query_params.get("pin", "")
        except Exception:
            qp_pin_raw = st.experimental_get_query_params().get("pin", [""])[0]

        if qp_pin_raw:
            val_pin_auto = normalize_access_code(extract_pin_from_input(qp_pin_raw))
            session_match_auto = next((p for p in plans if p.get("isActive", True) and access_code_matches(val_pin_auto, p.get("pin", ""))), None)
            program_match_auto = next((pr for pr in programs_af if access_code_matches(val_pin_auto, pr.get("pin", ""))), None)
            if session_match_auto or program_match_auto:
                reset_login_attempts()
                st.session_state.logged_pin = val_pin_auto
                st.rerun()

    if not st.session_state.logged_pin:
        st.markdown("<div style='text-align:center; margin-top:40px;'><h1 style='font-size:27px;'>🏋️ Acceso a tu Sesión o Programa</h1><p style='color:#64756e;'>Introduce tu código de acceso</p></div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form", clear_on_submit=False):
                pin_input = st.text_input("Código de acceso", type="password", label_visibility="hidden", placeholder="Ej: A7K9Q2M4NP")
                btn_login = st.form_submit_button("🔑 Acceder a mi sesión", type="primary", use_container_width=True)
                
                if login_is_temporarily_locked():
                    remaining = st.session_state.login_locked_until - datetime.datetime.now()
                    minutes = max(1, int(remaining.total_seconds() // 60) + 1)
                    st.error(f"Por seguridad, espera aproximadamente {minutes} minuto(s) antes de volver a intentarlo.")
                elif btn_login and pin_input:
                    val_pin = normalize_access_code(extract_pin_from_input(pin_input))
                    admin_access_code = get_admin_access_code()
                    session_match = next((p for p in plans if p.get("isActive", True) and access_code_matches(val_pin, p.get("pin", ""))), None)
                    program_match = next((pr for pr in programs_af if access_code_matches(val_pin, pr.get("pin", ""))), None)

                    if admin_access_code and access_code_matches(val_pin, admin_access_code):
                        reset_login_attempts()
                        st.session_state.admin_mode = True
                        st.rerun()
                    elif session_match or program_match:
                        reset_login_attempts()
                        st.session_state.logged_pin = val_pin
                        st.rerun()
                    else:
                        register_failed_login()
                        remaining_attempts = max(0, MAX_LOGIN_ATTEMPTS - st.session_state.failed_login_attempts)
                        if login_is_temporarily_locked():
                            st.error("Demasiados intentos. El acceso se ha bloqueado temporalmente por seguridad.")
                        else:
                            st.error(f"Código incorrecto o no disponible. Te quedan {remaining_attempts} intento(s).")

    else:
        pin_ingresado = st.session_state.logged_pin
        
        sesion_encontrada = next((p for p in plans if p.get("isActive", True) and access_code_matches(pin_ingresado, p.get("pin", ""))), None)
        programa_af_encontrado = next((pr for pr in programs_af if access_code_matches(pin_ingresado, pr.get("pin", ""))), None)
        
        col_exit1, col_exit2 = st.columns([4, 1])
        with col_exit2:
            if st.button("🚪 Cambiar código", key="exit_pin_btn"):
                st.session_state.logged_pin = None
                st.rerun()

        if programa_af_encontrado:
            pr = programa_af_encontrado
            banner_af = f"""
            <div style='background:#e9f6f0; border: 1px solid #dce7e2; border-radius:16px; padding:25px; margin: 10px 0px 25px 0px; text-align:center;'>
                <span style='color:#13765d; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>PROGRAMA DE ENTRENAMIENTO</span>
                <h2 style='color:#103d33 !important; font-size:28px; font-weight:800; margin:10px 0px 5px 0px;'>{pr['title']}</h2>
                <p style='color:#64756e; font-size:14px; margin:0;'>⏱️ {pr['frequency']} | {pr['duration']}</p>
            </div>
            """
            st.markdown(banner_af, unsafe_allow_html=True)
            
            if pr['generalNote']:
                st.info(f"💡 {pr['generalNote']}")

            for d_idx, day in enumerate(pr['daysData'], start=1):
                dia_titulo_mostrado = f"Día {d_idx}: {day['dayTitle']}" if day.get('dayTitle', '').strip() else f"Día {d_idx}"
                st.markdown(f"<div style='background:#103d33; color:white; padding:12px 18px; border-radius:10px; font-weight:bold; font-size:18px; margin-top:25px; margin-bottom:15px;'>{dia_titulo_mostrado}</div>", unsafe_allow_html=True)
                
                for block in day['blocks']:
                    b_cat = block.get('blockCategory')
                    b_rule = block.get('blockRule')
                    
                    if b_cat is not None:
                        if b_rule:
                            b_regla_limpia = b_rule.replace("(", "").replace(")", "").strip()
                            html_titulo = f"<h4 style='color:#13765d !important; margin: 15px 0 10px 0;'>📌 <span style='font-weight:800;'>{b_cat}</span> <span style='font-weight:400; background-color: #ffeb3b; color: #103d33; padding: 2px 6px; border-radius: 4px; margin-left: 5px;'>({b_regla_limpia})</span></h4>"
                        else:
                            html_titulo = f"<h4 style='color:#13765d !important; margin: 15px 0 10px 0;'>📌 <span style='font-weight:800;'>{b_cat}</span></h4>"
                    else:
                        html_titulo = f"<h4 style='color:#13765d !important; margin: 15px 0 10px 0;'>📌 <span style='font-weight:800;'>{block['blockTitle']}</span></h4>"
                    
                    st.markdown(html_titulo, unsafe_allow_html=True)
                    
                    for idx, item in enumerate(block['exercises'], start=1):
                        ex_data = get_exercise(item['exerciseId'])
                        if ex_data:
                            series = item.get("series", "-")
                            reps = item.get("reps", "-")
                            notes = item.get("notes", "")
                            
                            prio_badge = "⭐ " if item.get('isPriority') else ""
                            notas_str = f" 📝 {notes}" if notes else ""
                            
                            vid_url = ex_data.get('videoUrl', '').strip()
                            btn_video = f"<a href='{vid_url}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:6px 12px; border-radius:6px; font-weight:bold; font-size:12px; margin-left:10px; white-space:nowrap;'>▶ Vídeo</a>" if vid_url else ""
                                
                            card_af_html = f"""
                            <div style='background:#fff; border:1px solid #dce7e2; border-radius:10px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>
                                <div style='font-size:15px; color:#103d33;'>
                                    {prio_badge}<span style='font-weight:600;'>{ex_data['name']}</span> 🔄 {series}x{reps}{notas_str}
                                </div>
                                {btn_video}
                            </div>
                            """
                            
                            st.markdown(card_af_html, unsafe_allow_html=True)

        elif sesion_encontrada:
            sesiones_del_pac = [pl for pl in plans if pl.get("isActive", True) and str(pl["patientId"]) == str(sesion_encontrada["patientId"])]
            sesion_actual = sesiones_del_pac[-1] if sesiones_del_pac else None
            
            if sesion_actual and str(sesion_actual["id"]) != str(sesion_encontrada["id"]):
                st.markdown("<div style='background:#fdecec; color:#aa3838; padding:11px 13px; border-radius:9px; text-align:center;'>⚠️ Esta sesión es antigua y ya no está disponible. Por favor, pídele a tu fisioterapeuta el PIN de tu nueva sesión.</div>", unsafe_allow_html=True)
            else:
                paciente_obj = next((pac for pac in patients if str(pac["id"]) == str(sesion_encontrada["patientId"])), None)
                rev_date_str = paciente_obj.get("review_date", "") if paciente_obj else ""
                
                show_warning = False
                days_left = 0
                if rev_date_str:
                    try:
                        r_date = datetime.datetime.strptime(rev_date_str, "%Y-%m-%d").date()
                        days_left = (r_date - datetime.date.today()).days
                        show_warning = True
                    except:
                        pass
                
                ack_key = f"ack_rev_{sesion_encontrada['id']}"
                
                if show_warning and not st.session_state.get(ack_key, False):
                    fecha_rev_str = r_date.strftime("%d/%m/%Y")
                    if days_left > 0:
                        texto_revision = f"Tu próxima revisión es en {days_left} días, el {fecha_rev_str}."
                    elif days_left == 0:
                        texto_revision = f"Tu revisión clínica es hoy, {fecha_rev_str}."
                    else:
                        texto_revision = f"Tu revisión clínica fue hace {abs(days_left)} días, el {fecha_rev_str}."

                    reminder_html = f"""
                    <div style='background:#fff8e1; border: 2px solid #fbc02d; border-radius:12px; padding:30px; text-align:center; margin-top:20px;'>
                        <h2 style='color:#f57f17 !important; margin:0 0 15px 0;'>⚠️ Recordatorio de Revisión</h2>
                        <p style='font-size:18px; color:#103d33; margin:0;'>{texto_revision}</p>
                    </div>
                    """
                    st.markdown(reminder_html, unsafe_allow_html=True)

                    col_btn_w1, col_btn_w2, col_btn_w3 = st.columns([1, 1, 1])
                    if col_btn_w2.button("Aceptar y ver mi sesión", type="primary", use_container_width=True):
                        st.session_state[ack_key] = True
                        st.rerun()
                
                else:
                    nombre_paciente_ses = paciente_obj.get('name', '').strip() if paciente_obj else ''
                    saludo_ses = f"Esta es tu sesión de hoy, {nombre_paciente_ses}" if nombre_paciente_ses else "Esta es tu sesión de hoy"
                    banner_html = f"""
                    <div style='background:#e9f6f0; border: 1px solid #dce7e2; border-radius:16px; padding:25px; margin: 10px 0px 35px 0px; text-align:center;'>
                        <span style='color:#13765d; font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:1px;'>{saludo_ses}</span>
                        <h2 style='color:#103d33 !important; font-size:32px; font-weight:800; margin:10px 0px 5px 0px; line-height:1.2;'>{sesion_encontrada['title']}</h2>
                    </div>
                    """
                    st.markdown(banner_html, unsafe_allow_html=True)
    
                    if not sesion_encontrada["exerciseIds"]:
                        st.info("No hay ejercicios para esta sesión.")
                    
                    st.markdown("<h3 style='margin-bottom:20px; font-size:22px; color:#103d33 !important;'>🎥 Lista de Ejercicios</h3>", unsafe_allow_html=True)
                    
                    for idx, ex_id in enumerate(sesion_encontrada["exerciseIds"], start=1):
                        ex_data = get_exercise(ex_id)
                        inst_data = sesion_encontrada["exerciseInstructions"].get(ex_id, {})
                        
                        if ex_data:
                            series = inst_data.get("series", "-")
                            reps = inst_data.get("reps", "-")
                            notes = inst_data.get("notes", "")
                            
                            vid_url = ex_data.get("videoUrl", "").strip()
                            btn_video_ses = f"<a href='{vid_url}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:10px 20px; border-radius:8px; font-weight:bold; font-size:14px; margin-left:10px; white-space:nowrap;'>▶ Vídeo</a>" if vid_url else ""

                            box_series_reps = f"""
                            <div style='display:flex; gap:10px; margin-top:10px;'>
                                <div style='flex:1; background:#f6f8f6; border:1px solid #dce7e2; border-radius:8px; padding:8px 10px; text-align:center;'>
                                    <div style='font-size:11px; color:#13765d; font-weight:700; letter-spacing:0.5px; text-transform:uppercase;'>Series</div>
                                    <div style='font-size:18px; color:#103d33; font-weight:800; margin-top:2px;'>{series}</div>
                                </div>
                                <div style='flex:1; background:#f6f8f6; border:1px solid #dce7e2; border-radius:8px; padding:8px 10px; text-align:center;'>
                                    <div style='font-size:11px; color:#13765d; font-weight:700; letter-spacing:0.5px; text-transform:uppercase;'>Repeticiones</div>
                                    <div style='font-size:18px; color:#103d33; font-weight:800; margin-top:2px;'>{reps}</div>
                                </div>
                            </div>
                            """

                            notas_html = f"""
                            <div style='display:flex; align-items:center; gap:12px; background:#f6f8f6; border:1px solid #dce7e2; border-radius:8px; padding:8px 12px; margin-top:8px;'>
                                <div style='font-size:11px; color:#13765d; font-weight:700; letter-spacing:0.5px; text-transform:uppercase; white-space:nowrap;'>Notas</div>
                                <div style='font-size:14px; color:#103d33; flex:1;'>{notes}</div>
                            </div>
                            """ if notes else ""

                            card_html = f"""
                            <div style='background:#fff; border:1px solid #dce7e2; border-radius:10px; padding:12px 14px; margin-bottom:10px;'>
                                <div style='display:flex; justify-content:space-between; align-items:center;'>
                                    <div style='font-size:15px; color:#103d33;'>
                                        <strong>{idx}. {ex_data['name']}</strong>
                                    </div>
                                    {btn_video_ses}
                                </div>
                                {box_series_reps}
                                {notas_html}
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
                    
                    st.divider()
                    st.markdown("<h3 style='margin-top:20px; color:#103d33 !important;'>✅ Sesión Terminada</h3>", unsafe_allow_html=True)
                    st.write("¿Cómo ha ido? Por favor, reporta la intensidad para tu fisioterapeuta.")
                    with st.form(f"checkin_form_{sesion_encontrada['id']}"):
                        eva = st.slider("**Dolor**: 0 (Nada) a 10 (Máximo)", 0, 10, 0)
                        borg = st.slider("**Fatiga**: 0 (Reposo) a 10 (Extenuante)", 0, 10, 0)
                        comentarios = st.text_area("¿Alguna molestia o comentario? (Opcional)")
                        
                        if st.form_submit_button("Enviar Reporte a mi Fisio", type="primary"):
                            save_checkin_item(sesion_encontrada["id"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), eva, borg, comentarios)
                            st.success("¡Enviado con éxito! Tu fisio ya puede verlo.")
        else:
            st.error("PIN incorrecto o no encontrado.")
            if st.button("Intentar de nuevo"):
                st.session_state.logged_pin = None
                st.rerun()
