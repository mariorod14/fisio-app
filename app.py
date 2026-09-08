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

def normalize_access_code(value):
    if not value: return ""
    s = str(value).strip().upper()
    # Extraemos el código si pegan el link entero
    if "PIN=" in s:
        s = s.split("PIN=")[-1]
    elif "/" in s:
        s = s.split("/")[-1]
    return "".join(ch for ch in s if ch.isalnum())

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
            records.append({
                "id": clean_str(r.get("id", "")), 
                "name": clean_str(r.get("name", "")), 
                "phone": clean_str(r.get("phone", "")),
                "review_date": clean_str(r.get("review_date", "")),
                "anamnesis": clean_str(r.get("anamnesis", "")),
                "inspeccion": clean_str(r.get("inspeccion", "")),
                "movilidad": clean_str(r.get("movilidad", "")),
                "fuerza": clean_str(r.get("fuerza", ""))
            })
        return records
    except Exception:
        st.session_state.gsheets_read_error = True
        return []

def save_patients(patients_list):
    if st.session_state.gsheets_read_error:
        st.error("❌ Guardado bloqueado por seguridad: Hubo un error de conexión al cargar los datos.")
        return
    patient_columns = ["id", "name", "phone", "review_date", "anamnesis", "inspeccion", "movilidad", "fuerza"]
    conn.update(spreadsheet=SHEET_URL, worksheet="pacientes", data=pd.DataFrame(patients_list, columns=patient_columns))
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
                    new_p_review = c_np3.date_input("Fecha de revisión:", value=None, format="DD/MM/YYYY")
                    
                    new_p_ana = st.text_area("Anamnesis (entrevista, historia clínica...):")
                    new_p_ins = st.text_area("Inspección física (temperatura, coloración, medidas...):")
                    new_p_mov = st.text_area("Movilidad activa y pasiva (ROM activo y pasivo...):")
                    new_p_fue = st.text_area("Fuerza (dinamometría...):")
                    
                    if st.form_submit_button("Guardar Paciente Nuevo", type="primary"):
                        if new_p_name:
                            review_str = str(new_p_review) if new_p_review else ""
                            patients.append({
                                "id": str(uuid.uuid4()), "name": new_p_name, "phone": new_p_phone,
                                "review_date": review_str,
                                "anamnesis": new_p_ana, "inspeccion": new_p_ins, "movilidad": new_p_mov, "fuerza": new_p_fue
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
                    st.markdown("#### ⚙️ Datos Clínicos del Paciente")
                    
                    ce1, ce2, ce3 = st.columns([3, 1.5, 1.5])
                    edit_name = ce1.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                    edit_phone = ce2.text_input("Teléfono", value=p.get("phone", ""), key=f"phone_{p['id']}")
                    
                    try:
                        curr_rev_date = datetime.datetime.strptime(p.get("review_date", ""), "%Y-%m-%d").date()
                    except:
                        curr_rev_date = None
                    edit_review = ce3.date_input("Fecha de revisión", value=curr_rev_date, key=f"rev_{p['id']}", format="DD/MM/YYYY")
                    
                    edit_ana = st.text_area("Anamnesis (entrevista, historia clínica...):", value=p.get("anamnesis", ""), key=f"ana_{p['id']}")
                    edit_ins = st.text_area("Inspección física (temperatura, coloración, medidas...):", value=p.get("inspeccion", ""), key=f"ins_{p['id']}")
                    edit_mov = st.text_area("Movilidad activa y pasiva (ROM activo y pasivo...):", value=p.get("movilidad", ""), key=f"mov_{p['id']}")
                    edit_fue = st.text_area("Fuerza (dinamometría...):", value=p.get("fuerza", ""), key=f"fue_{p['id']}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("💾 Actualizar Datos", key=f"upd_{p['id']}", type="primary"):
                        p["name"] = edit_name; p["phone"] = edit_phone
                        p["review_date"] = str(edit_review) if edit_review else ""
                        p["anamnesis"] = edit_ana; p["inspeccion"] = edit_ins
                        p["movilidad"] = edit_mov; p["fuerza"] = edit_fue
                        save_patients(patients); st.rerun()
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
                    elif c2.button("🗑️ Borrar Paciente", key=f"del_{p['id']}"):
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
                                mensaje_wa = f"¡Hola {get_patient_name(pl['patientId'])}! 👋\n\nAquí tienes tu sesión de fisioterapia: *{pl['title']}*.\n\n📱 Accede directamente desde aquí:\n{APP_URL}\n\n🔑 Tu código de acceso es este link (mantén pulsado para copiarlo y pégalo en el espacio de contraseña):\n{APP_URL}/?pin={pl['pin']}\n\n¡A por ello!"
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
                            elif st.button("🗑️ Borrar", key=f"del_btn_{pl['id']}", use_container_width=True):
                                st.session_state.confirm_delete_session_id = pl["id"]
                                st.rerun()
                                
                    st.write("")
        
        with tab_crear_ses:
            if not patients:
                st.warning("Primero debes añadir pacientes en la pestaña 'Archivo'.")
            elif not exercises:
                st.warning("Primero debes añadir ejercicios en la base de datos de 'Archivo'.")
            else:
                paciente_sel = st.selectbox("1. Selecciona Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
                titulo_sesion = st.text_input("2. Título de la Sesión:", placeholder="Ej: Sesión readaptación hombro semana 1")
                
                st.markdown("**3. Selecciona los ejercicios de la base de datos:**")
                ej_options_all = {}
                for cat in CATEGORIAS_EJ:
                    ej_cat = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
                    for e in ej_cat:
                        ej_options_all[f"{cat}  |  {e['name']}"] = e['id']
                        
                if "crear_sesion_ejs" not in st.session_state:
                    st.session_state.crear_sesion_ejs = []
                    
                nombres_actuales = []
                for eid in st.session_state.crear_sesion_ejs:
                    eobj = get_exercise(eid)
                    if eobj: nombres_actuales.append(f"{eobj['category']}  |  {eobj['name']}")
                    
                selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options_all.keys()), default=nombres_actuales, label_visibility="collapsed")
                
                nuevos_ids = [ej_options_all[n] for n in selected_names]
                st.session_state.crear_sesion_ejs = [e for e in st.session_state.crear_sesion_ejs if e in nuevos_ids]
                for e in nuevos_ids:
                    if e not in st.session_state.crear_sesion_ejs:
                        st.session_state.crear_sesion_ejs.append(e)

                instrucciones_dict = {}
                has_missing_videos = False
                
                if st.session_state.crear_sesion_ejs:
                    st.markdown("**4. Configuración y Orden (Arrastra con las flechas):**")
                    for idx, e_id in enumerate(st.session_state.crear_sesion_ejs):
                        ej_obj = get_exercise(e_id)
                        ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                        sin_video = False
                        
                        if ej_obj and not ej_obj.get("videoUrl", "").strip():
                            sin_video = True
                            has_missing_videos = True
                            ej_name += " ⚠️ (SIN VÍDEO)"
                            
                        c_t, c_s, c_r, c_n, c_up, c_dn = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                        with c_t: 
                            color_style = "color:var(--danger); font-weight:bold;" if sin_video else ""
                            st.markdown(f"<div style='margin-top:8px; font-size:14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; {color_style}'>{idx+1}. {ej_name}</div>", unsafe_allow_html=True)
                        with c_s: 
                            s = st.text_input("S", key=f"cs_{e_id}", label_visibility="collapsed", placeholder="Series")
                        with c_r: 
                            r = st.text_input("R", key=f"cr_{e_id}", label_visibility="collapsed", placeholder="Reps")
                        with c_n: 
                            n = st.text_input("N", key=f"cn_{e_id}", label_visibility="collapsed", placeholder="Notas")
                        with c_up:
                            if st.button("⬆️", key=f"cup_{e_id}") and idx > 0:
                                st.session_state.crear_sesion_ejs[idx-1], st.session_state.crear_sesion_ejs[idx] = st.session_state.crear_sesion_ejs[idx], st.session_state.crear_sesion_ejs[idx-1]
                                st.rerun()
                        with c_dn:
                            if st.button("⬇️", key=f"cdn_{e_id}") and idx < len(st.session_state.crear_sesion_ejs) - 1:
                                st.session_state.crear_sesion_ejs[idx+1], st.session_state.crear_sesion_ejs[idx] = st.session_state.crear_sesion_ejs[idx], st.session_state.crear_sesion_ejs[idx+1]
                                st.rerun()
                                
                        instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                        
                st.write("")
                
                if has_missing_videos:
                    st.error("🚨 AVISO IMPORTANTE: Has añadido uno o más ejercicios que no tienen un link de YouTube (aparecen marcados en rojo en la lista). El paciente no podrá ver ningún vídeo de esos ejercicios.")
                
                if st.button("💾 Crear Sesión Clínica", type="primary", use_container_width=True):
                    if titulo_sesion and st.session_state.crear_sesion_ejs:
                        nuevo_pin = generate_unique_access_code()
                        for pl in plans:
                            if pl["patientId"] == paciente_sel:
                                pl["isActive"] = False
                                
                        nuevo_plan = {
                            "id": str(uuid.uuid4()),
                            "patientId": paciente_sel,
                            "title": titulo_sesion,
                            "exerciseIds": st.session_state.crear_sesion_ejs,
                            "exerciseInstructions": instrucciones_dict,
                            "pin": nuevo_pin,
                            "startDate": str(datetime.date.today()),
                            "isActive": True
                        }
                        plans.append(nuevo_plan)
                        save_plans(plans)
                        
                        st.session_state.crear_sesion_ejs = []
                        st.success("¡Sesión creada con éxito!")
                        
                        nombre_paciente = get_patient_name(paciente_sel)
                        mensaje_whatsapp = f"¡Hola {nombre_paciente}! 👋\n\nAquí tienes tu nueva sesión de fisioterapia: *{titulo_sesion}*.\n\n📱 Para ver tus ejercicios y vídeos, entra en este enlace:\n{APP_URL}\n\n🔑 Tu código de acceso es este link (mantén pulsado para copiarlo y pégalo en el espacio de contraseña):\n{APP_URL}/?pin={nuevo_pin}\n\n¡A por ello!"
                        
                        st.markdown("### 📱 Enviar al Paciente")
                        st.caption("Copia este mensaje para mandarlo por WhatsApp:")
                        st.code(mensaje_whatsapp, language="markdown")
                    else:
                        st.warning("Asegúrate de ponerle un título y añadir al menos un ejercicio.")

        with tab_checkins:
            st.markdown("### 📊 Reportes de Pacientes (EVA y Borg)")
            if not checkins:
                st.info("Aún no hay reportes registrados por los pacientes.")
            else:
                for ch in reversed(checkins):
                    plan_relacionado = next((pl for pl in plans if str(pl["id"]) == str(ch["planId"])), None)
                    if plan_relacionado:
                        nombre_pac = get_patient_name(plan_relacionado["patientId"])
                        titulo_plan = plan_relacionado["title"]
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 1])
                            c1.markdown(f"**👤 {nombre_pac}**  \n📋 {titulo_plan}  \n📅 {ch['date']}")
                            c2.markdown(f"<div style='font-size:24px; text-align:center;'>💥 EVA<br><span style='color:var(--danger);'><b>{ch['eva']}</b>/10</span></div>", unsafe_allow_html=True)
                            c3.markdown(f"<div style='font-size:24px; text-align:center;'>🏃 Borg<br><span style='color:var(--green);'><b>{ch['borg']}</b>/10</span></div>", unsafe_allow_html=True)
                            if ch.get("comment"):
                                st.markdown(f"🗨️ **Comentario:** {ch['comment']}")

        with tab_seguimiento:
            st.markdown("### 📈 Evolución del Dolor por Paciente")
            pacientes_con_reportes = set()
            for ch in checkins:
                plan_rel = next((pl for pl in plans if str(pl["id"]) == str(ch["planId"])), None)
                if plan_rel:
                    pacientes_con_reportes.add(plan_rel["patientId"])
                    
            if not pacientes_con_reportes:
                st.info("Aún no hay datos suficientes para mostrar gráficas.")
            else:
                paciente_graf = st.selectbox("Selecciona un paciente:", options=list(pacientes_con_reportes), format_func=get_patient_name)
                datos_paciente = []
                for ch in checkins:
                    plan_rel = next((pl for pl in plans if str(pl["id"]) == str(ch["planId"])), None)
                    if plan_rel and plan_rel["patientId"] == paciente_graf:
                        try:
                            fecha = datetime.datetime.strptime(ch["date"], "%Y-%m-%d %H:%M:%S")
                        except:
                            fecha = ch["date"]
                        datos_paciente.append({
                            "Fecha": fecha,
                            "EVA (Dolor)": int(ch["eva"]),
                            "Borg (Esfuerzo)": int(ch["borg"])
                        })
                
                if datos_paciente:
                    df_graf = pd.DataFrame(datos_paciente)
                    df_graf = df_graf.sort_values(by="Fecha")
                    
                    chart_eva = alt.Chart(df_graf).mark_line(point=True, color='#aa3838').encode(
                        x=alt.X('Fecha:T', title='Fecha'),
                        y=alt.Y('EVA (Dolor):Q', scale=alt.Scale(domain=[0, 10])),
                        tooltip=['Fecha', 'EVA (Dolor)']
                    ).properties(title="Evolución Escala EVA (Dolor)", height=250)
                    st.altair_chart(chart_eva, use_container_width=True)

    elif menu_seleccion == "🏋️ Programas de AF":
        st.markdown("<h1>🏋️ Programas de Acondicionamiento Físico</h1>", unsafe_allow_html=True)
        tab_gest_af, tab_crear_af = st.tabs(["⚙️ Programas Activos", "📝 Crear Nuevo Programa"])
        
        with tab_gest_af:
            if st.session_state.get("editing_program_id"):
                target_pr = next((pr for pr in programs_af if str(pr["id"]) == str(st.session_state.editing_program_id)), None)
                if target_pr:
                    modal_editar_programa(target_pr)
                else:
                    st.session_state.editing_program_id = None
                    
            q_af = st.text_input("🔍 Buscar programa de AF por título o paciente:")
            progs_filtrados = list(reversed(programs_af))
            if q_af:
                q = q_af.lower()
                progs_filtrados = [pr for pr in progs_filtrados if q in pr["title"].lower() or q in get_patient_name(pr["patientId"]).lower()]
                
            if not progs_filtrados:
                st.info("No hay programas de AF creados.")
            else:
                for pr in progs_filtrados:
                    with st.container(border=True):
                        colt, colp = st.columns([7, 3])
                        colt.markdown(f"#### {pr['title']}")
                        colp.markdown(f"<div style='text-align:right;'><span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pr['pin']}</span></div>", unsafe_allow_html=True)
                        
                        st.write(f"👤 **Paciente:** {get_patient_name(pr['patientId'])}")
                        
                        c1, c2, c3, c4, c5 = st.columns([3, 2.5, 1.2, 1.4, 1.2])
                        c1.write(f"⏱️ **Días:** {len(pr['daysData'])} | **Frec:** {pr.get('frequency','-')}")
                        c2.write(f"📅 **Inicio:** {pr.get('startDate', 'No reg.')}")
                        with c3:
                            if st.button("✏️ Editar", key=f"edit_af_{pr['id']}", use_container_width=True):
                                st.session_state.editing_program_id = pr["id"]
                                st.rerun()
                        with c4:
                            with st.popover("📋 Copiar", use_container_width=True):
                                st.caption("Copia el mensaje:")
                                mensaje_wa_gen = f"¡Hola {get_patient_name(pr['patientId'])}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{pr['title']}*.\n\n📱 Accede directamente desde aquí:\n{APP_URL}\n\n🔑 Tu código de acceso es este link (mantén pulsado para copiarlo y pégalo en el espacio de contraseña):\n{APP_URL}/?pin={pr['pin']}\n\n¡A entrenar!"
                                st.code(mensaje_wa_gen, language="markdown")
                        with c5:
                            if st.session_state.confirm_delete_program_id == pr["id"]:
                                st.warning("Vas a borrar este programa. El código de acceso dejará de funcionar.")
                                conf, canc = st.columns(2)
                                if conf.button("Sí, borrar", key=f"conf_del_af_{pr['id']}", type="primary"):
                                    programs_af = [x for x in programs_af if str(x["id"]) != str(pr["id"])]
                                    save_programs_af(programs_af)
                                    st.session_state.confirm_delete_program_id = None
                                    st.rerun()
                                if canc.button("Cancelar", key=f"canc_del_af_{pr['id']}"):
                                    st.session_state.confirm_delete_program_id = None
                                    st.rerun()
                            elif st.button("🗑️ Borrar", key=f"del_af_{pr['id']}", use_container_width=True):
                                st.session_state.confirm_delete_program_id = pr["id"]
                                st.rerun()

        with tab_crear_af:
            if not patients or not exercises:
                st.warning("Debes añadir pacientes y ejercicios primero en 'Archivo'.")
            else:
                c1, c2 = st.columns([1, 2])
                af_paciente = c1.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name, key="af_p")
                af_titulo = c2.text_input("2. Título del programa:", placeholder="Ej: Programa Fuerza Base", key="af_t")
                
                c3, c4 = st.columns(2)
                af_frecuencia = c3.text_input("3. Frecuencia semanal recomendada:", placeholder="Ej: 3 días a la semana", key="af_f")
                af_duracion = c4.text_input("4. Duración aproximada por sesión:", placeholder="Ej: 45 min", key="af_d")
                
                af_nota = st.text_input("5. Nota general del programa:", placeholder="Ej: Céntrate en la técnica, descansos de 90s entre series.", key="af_n")
                
                st.divider()
                st.markdown("### 📅 Diseñador de Días y Bloques")
                
                if "af_dias_count" not in st.session_state: st.session_state.af_dias_count = 1
                
                cb1, cb2 = st.columns(2)
                if cb1.button("➕ Añadir Día al Plan"):
                    st.session_state.af_dias_count += 1
                    st.rerun()
                if cb2.button("➖ Quitar Último Día") and st.session_state.af_dias_count > 1:
                    st.session_state.af_dias_count -= 1
                    st.rerun()
                    
                dias_construidos = []
                falta_algun_video_af = False
                
                for d_idx in range(st.session_state.af_dias_count):
                    st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
                    d_titulo = st.text_input(f"Título del Día {d_idx+1}:", placeholder=f"Ej: Día {d_idx+1} - Empujes", key=f"dtit_{d_idx}")
                    
                    if f"af_b_count_{d_idx}" not in st.session_state: st.session_state[f"af_b_count_{d_idx}"] = 1
                    
                    cc1, cc2 = st.columns(2)
                    if cc1.button(f"➕ Añadir Bloque al Día {d_idx+1}", key=f"addB_{d_idx}"):
                        st.session_state[f"af_b_count_{d_idx}"] += 1
                        st.rerun()
                    if cc2.button(f"➖ Quitar Bloque al Día {d_idx+1}", key=f"subB_{d_idx}") and st.session_state[f"af_b_count_{d_idx}"] > 1:
                        st.session_state[f"af_b_count_{d_idx}"] -= 1
                        st.rerun()
                        
                    bloques_dia = []
                    for b_idx in range(st.session_state[f"af_b_count_{d_idx}"]):
                        with st.container(border=True):
                            col_bcat, col_breg = st.columns([1, 2])
                            b_cat = col_bcat.selectbox("Categoría de la Base:", CATEGORIAS_EJ, key=f"bcat_{d_idx}_{b_idx}")
                            b_regla = col_breg.text_input("Regla / Indicación del bloque:", placeholder="Ej: En circuito / Superserie / Al fallo", key=f"breg_{d_idx}_{b_idx}")
                            
                            ej_cat_filtrados = sorted([e for e in exercises if e.get("category") == b_cat], key=lambda x: x["name"].lower())
                            ej_options_block = {e["name"]: e["id"] for e in ej_cat_filtrados}
                            
                            if f"af_ejs_{d_idx}_{b_idx}" not in st.session_state: st.session_state[f"af_ejs_{d_idx}_{b_idx}"] = []
                            current_block_ids = st.session_state[f"af_ejs_{d_idx}_{b_idx}"]
                            default_names = [get_exercise(eid)["name"] for eid in current_block_ids if get_exercise(eid) and get_exercise(eid)["category"] == b_cat]
                            
                            b_selected_names = st.multiselect("Añadir ejercicios a este bloque:", options=list(ej_options_block.keys()), default=default_names, key=f"bsel_{d_idx}_{b_idx}", label_visibility="collapsed")
                            
                            new_ids = [ej_options_block[n] for n in b_selected_names]
                            st.session_state[f"af_ejs_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"af_ejs_{d_idx}_{b_idx}"] if e in new_ids]
                            for e in new_ids:
                                if e not in st.session_state[f"af_ejs_{d_idx}_{b_idx}"]:
                                    st.session_state[f"af_ejs_{d_idx}_{b_idx}"].append(e)
                                    
                            ejs_bloque_info = []
                            for idx_e, eid in enumerate(st.session_state[f"af_ejs_{d_idx}_{b_idx}"]):
                                ej_obj = get_exercise(eid)
                                ename = ej_obj['name'] if ej_obj else "Ejercicio"
                                sin_video_af = False
                                
                                if ej_obj and not ej_obj.get("videoUrl", "").strip():
                                    sin_video_af = True
                                    falta_algun_video_af = True
                                    ename += " ⚠️ (SIN VÍDEO)"
                                    
                                ce1, ce2, ce3, ce4, ce5, ce6, ce7 = st.columns([3, 1, 1, 2, 1.5, 0.6, 0.6])
                                with ce1:
                                    color_style = "color:var(--danger); font-weight:bold;" if sin_video_af else ""
                                    st.markdown(f"<div style='margin-top:6px; font-weight:bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; {color_style}'>{idx_e+1}. {ename}</div>", unsafe_allow_html=True)
                                with ce2:
                                    s = st.text_input("S", key=f"s_af_{d_idx}_{b_idx}_{eid}", placeholder="Ser", label_visibility="collapsed")
                                with ce3:
                                    r = st.text_input("R", key=f"r_af_{d_idx}_{b_idx}_{eid}", placeholder="Rep", label_visibility="collapsed")
                                with ce4:
                                    n = st.text_input("N", key=f"n_af_{d_idx}_{b_idx}_{eid}", placeholder="Nota", label_visibility="collapsed")
                                with ce5:
                                    es_prio = st.checkbox("⭐ Prio", key=f"prio_{d_idx}_{b_idx}_{eid}", help="Marcar como ejercicio principal")
                                with ce6:
                                    if st.button("⬆️", key=f"up_af_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                                        st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e-1]
                                        st.rerun()
                                with ce7:
                                    if st.button("⬇️", key=f"dn_af_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"af_ejs_{d_idx}_{b_idx}"])-1:
                                        st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e+1]
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
                
                if falta_algun_video_af:
                    st.error("🚨 AVISO IMPORTANTE: Has añadido uno o más ejercicios que no tienen un link de YouTube (aparecen marcados en rojo en la lista). El paciente no podrá ver ningún vídeo de esos ejercicios.")
                
                if st.button("💾 Guardar Programa de AF", type="primary", use_container_width=True):
                    if af_titulo and dias_construidos:
                        nuevo_pin_af = generate_unique_access_code()
                        nuevo_programa = {
                            "id": str(uuid.uuid4()),
                            "patientId": af_paciente,
                            "title": af_titulo,
                            "frequency": af_frecuencia,
                            "duration": af_duracion,
                            "generalNote": af_nota,
                            "pin": nuevo_pin_af,
                            "startDate": str(datetime.date.today()),
                            "daysData": dias_construidos
                        }
                        programs_af.append(nuevo_programa)
                        save_programs_af(programs_af)
                        
                        st.session_state.af_dias_count = 1
                        for key in list(st.session_state.keys()):
                            if key.startswith("af_ejs_") or key.startswith("af_b_count_"):
                                del st.session_state[key]
                                
                        st.success("¡Programa de AF creado con éxito!")
                        
                        nombre_p = get_patient_name(af_paciente)
                        mensaje_wa_gen = f"¡Hola {nombre_p}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{af_titulo}*.\n\n📱 Accede directamente desde tu móvil:\n{APP_URL}\n\n🔑 Tu código de acceso es este link (mantén pulsado para copiarlo y pégalo en el espacio de contraseña):\n{APP_URL}/?pin={nuevo_pin_af}\n\n¡A por todas!"
                        
                        st.markdown("### 📱 Enviar al Paciente")
                        st.code(mensaje_wa_gen, language="markdown")
                    else:
                        st.warning("Debes indicar un título y al menos un día con bloques.")

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE / FORMULARIO LOGIN
# =============================================================
else:
    if not st.session_state.logged_pin:
        st.markdown("<div style='text-align:center; margin-top:40px;'><h1 style='font-size:27px;'>🏋️ Acceso a tu Sesión o Programa</h1><p style='color:#64756e;'>Introduce tu código de acceso</p></div>", unsafe_allow_html=True)
        
        url_pin = ""
        try:
            if hasattr(st, "query_params"):
                url_pin = st.query_params.get("pin", "")
            elif hasattr(st, "experimental_get_query_params"):
                q_params = st.experimental_get_query_params()
                url_pin = q_params.get("pin", [""])[0]
        except:
            pass
            
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form", clear_on_submit=False):
                pin_input = st.text_input("Código de acceso", type="password", value=url_pin, label_visibility="hidden", placeholder="Ej: A7K9Q2M4NP")
                btn_login = st.form_submit_button("🔑 Acceder a mi sesión", type="primary", use_container_width=True)
                
        if login_is_temporarily_locked():
            st.error(f"Demasiados intentos fallidos. Inténtalo de nuevo a las {st.session_state.login_locked_until.strftime('%H:%M')}")
        elif btn_login:
            if not pin_input.strip():
                st.warning("Por favor, introduce tu código de acceso.")
            else:
                admin_code = get_admin_access_code()
                if admin_code and access_code_matches(pin_input, admin_code):
                    reset_login_attempts()
                    st.session_state.admin_mode = True
                    st.rerun()
                else:
                    found_plan = None
                    tipo_plan = None
                    
                    for pl in plans:
                        if pl.get("isActive", True) and access_code_matches(pin_input, pl.get("pin", "")):
                            found_plan = pl
                            tipo_plan = "sesion"
                            break
                    
                    if not found_plan:
                        for pr in programs_af:
                            if access_code_matches(pin_input, pr.get("pin", "")):
                                found_plan = pr
                                tipo_plan = "programa_af"
                                break

                    if found_plan:
                        reset_login_attempts()
                        st.session_state.logged_pin = normalize_access_code(pin_input)
                        st.session_state.current_plan = found_plan
                        st.session_state.current_plan_type = tipo_plan
                        st.rerun()
                    else:
                        register_failed_login()
                        st.error("Código incorrecto o sesión inactiva. Revisa el código proporcionado por tu fisio.")

    else:
        plan = st.session_state.get("current_plan")
        tipo = st.session_state.get("current_plan_type")
        
        if not plan:
            st.session_state.logged_pin = None
            st.rerun()

        st.markdown(f"<h2>{plan['title']}</h2>", unsafe_allow_html=True)
        st.write(f"👤 Hola, **{get_patient_name(plan['patientId'])}**")
        st.divider()

        if tipo == "sesion":
            if not plan["exerciseIds"]:
                st.info("No hay ejercicios asignados en esta sesión.")
            else:
                for idx, ex_id in enumerate(plan["exerciseIds"]):
                    ex_data = get_exercise(ex_id)
                    inst = plan["exerciseInstructions"].get(ex_id, {})
                    if ex_data:
                        with st.container(border=True):
                            st.markdown(f"<div style='font-size:16px; color:var(--dark); font-weight:bold; margin-bottom:8px;'>{idx+1}. {ex_data['name']}</div>", unsafe_allow_html=True)
                            
                            c_vid, c_info = st.columns([1.5, 2])
                            with c_vid:
                                vid = ex_data.get('videoUrl', '')
                                if vid:
                                    if "youtube.com" in vid or "youtu.be" in vid:
                                        try:
                                            video_id = vid.split("v=")[1][:11] if "v=" in vid else vid.split("/")[-1][:11]
                                            embed_url = f"https://www.youtube.com/embed/{video_id}"
                                            st.components.v1.iframe(embed_url, height=200)
                                        except:
                                            st.video(vid)
                                    else:
                                        st.video(vid)
                                else:
                                    st.info("Vídeo no disponible")
                            with c_info:
                                st.markdown(f"<div style='background:var(--mint); color:var(--green); padding:10px; border-radius:8px; font-weight:bold; text-align:center; margin-bottom:10px;'>🔄 {inst.get('series', '-')} series x {inst.get('reps', '-')} reps</div>", unsafe_allow_html=True)
                                if inst.get('notes'):
                                    st.markdown(f"<div style='background:#fff; border:1px solid var(--line); padding:10px; border-radius:8px; font-size:14px;'>💡 {inst['notes']}</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown("### 📝 Terminar Sesión y Reportar")
            st.info("Indica cómo te has sentido hoy. Se guardará la fecha automáticamente para tu fisioterapeuta.")
            with st.form("checkin_form", clear_on_submit=True):
                c_eva, c_borg = st.columns(2)
                eva_val = c_eva.slider("💥 Nivel de dolor (EVA)", 0, 10, 0, help="0 = Sin dolor, 10 = Máximo dolor imaginable")
                borg_val = c_borg.slider("🏃 Nivel de esfuerzo (Borg)", 0, 10, 5, help="0 = Reposo absoluto, 10 = Esfuerzo máximo")
                comentario = st.text_area("Comentarios (opcional):", placeholder="Ej: Me ha costado el segundo ejercicio...")
                
                if st.form_submit_button("✅ Enviar Reporte", type="primary", use_container_width=True):
                    save_checkin_item(plan["id"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), eva_val, borg_val, comentario)
                    st.success("¡Buen trabajo! Reporte enviado a tu fisioterapeuta.")

        elif tipo == "programa_af":
            if plan.get("generalNote"):
                st.info(f"💡 **Nota del fisio:** {plan['generalNote']}")
            if plan.get("frequency") or plan.get("duration"):
                st.caption(f"⏱️ **Recomendación:** {plan.get('frequency', '-')} | Duración aprox: {plan.get('duration', '-')}")
            
            st.write("")
            dias = plan.get("daysData", [])
            
            if not dias:
                st.write("No hay días configurados en este programa.")
            else:
                tabs_dias = st.tabs([d.get("dayTitle", f"Día {i+1}") for i, d in enumerate(dias)])
                
                for idx_d, tab in enumerate(tabs_dias):
                    with tab:
                        bloques = dias[idx_d].get("blocks", [])
                        for b in bloques:
                            st.markdown(f"<div style='margin-top:15px; font-size:16px; color:var(--green); border-bottom:2px solid var(--line); padding-bottom:4px; margin-bottom:10px;'><b>{b.get('blockTitle', 'Bloque')}</b></div>", unsafe_allow_html=True)
                            
                            ejs = b.get("exercises", [])
                            for e_item in ejs:
                                ex_data = get_exercise(e_item["exerciseId"])
                                if ex_data:
                                    prio_badge = "⭐ " if e_item.get("isPriority") else ""
                                    series = e_item.get("series", "-")
                                    reps = e_item.get("reps", "-")
                                    notas = e_item.get("notes", "")
                                    notas_str = f" | 💡 {notas}" if notas else ""
                                    
                                    vid = ex_data.get("videoUrl", "")
                                    btn_video = f"<a href='{vid}' target='_blank' style='background:var(--green); color:white; padding:4px 10px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;'>▶ Ver vídeo</a>" if vid else ""
                                    
                                    card_af_html = f"""
                                    <div style='background:#fff; border:1px solid #dce7e2; border-radius:10px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>
                                        <div style='font-size:15px; color:#103d33;'>
                                            {prio_badge}<span style='text-decoration: underline; font-weight: bold;'>{ex_data['name']}</span> 🔄 {series}x{reps}{notas_str}
                                        </div>
                                        {btn_video}
                                    </div>
                                    """
                                    st.markdown(card_af_html, unsafe_allow_html=True)

        st.divider()
        if st.button("🚪 Salir de mi sesión"):
            st.session_state.logged_pin = None
            st.session_state.current_plan = None
            st.session_state.current_plan_type = None
            st.rerun()
