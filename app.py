import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import random
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
PASSWORD_FISIO = "FISIO123"
APP_URL = "https://xj2xjmcpyuweucfq3b7axg.streamlit.app"  
CATEGORIAS_EJ = ["CORE", "EEII", "EESS", "Estiramientos y movilidad"]

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
    conn.update(spreadsheet=SHEET_URL, worksheet="pacientes", data=pd.DataFrame(patients_list))
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
    conn.update(spreadsheet=SHEET_URL, worksheet="ejercicios", data=pd.DataFrame(exercises_list))
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
                "pin": clean_str(r.get("pin", ""))
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
            "pin": p["pin"]
        })
    conn.update(spreadsheet=SHEET_URL, worksheet="sesiones", data=pd.DataFrame(formatted))
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
            "daysData": json.dumps(p["daysData"])
        })
    conn.update(spreadsheet=SHEET_URL, worksheet="programas_af", data=pd.DataFrame(formatted))
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

def save_checkin_item(plan_id, date, eva, borg, comment):
    if st.session_state.gsheets_read_error:
        st.error("❌ Error de conexión temporal. Inténtalo de nuevo en unos segundos.")
        return
    checkins_data = get_checkins()
    checkins_data.append({"id": str(uuid.uuid4())[:4], "planId": str(plan_id), "date": str(date), "eva": str(eva), "borg": str(borg), "comment": str(comment)})
    conn.update(spreadsheet=SHEET_URL, worksheet="checkins", data=pd.DataFrame(checkins_data))
    st.cache_data.clear()

# =============================================================
# CARGA DE DATOS
# =============================================================
patients = get_patients()
exercises = get_exercises()
plans = get_plans()
programs_af = get_programs_af()
checkins = get_checkins()

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

    # --- VENTANAS EMERGENTES (MODALES) DE EDICIÓN ---
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
                with c_dn:
                    if st.button("⬇️", key=f"edn_{pl_id}_{e_id}") and idx < len(st.session_state[f"edit_ses_{pl_id}_ejs"]) - 1:
                        st.session_state[f"edit_ses_{pl_id}_ejs"][idx+1], st.session_state[f"edit_ses_{pl_id}_ejs"][idx] = st.session_state[f"edit_ses_{pl_id}_ejs"][idx], st.session_state[f"edit_ses_{pl_id}_ejs"][idx+1]
                        
                instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                
        st.write("")
        if st.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True):
            pl["patientId"] = paciente_sel
            pl["title"] = titulo_sesion
            pl["exerciseIds"] = st.session_state[f"edit_ses_{pl_id}_ejs"]
            pl["exerciseInstructions"] = instrucciones_dict
            save_plans(plans)
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
        
        cb1, cb2 = st.columns(2)
        if cb1.button("➕ Añadir Día al Plan"):
            st.session_state[f"edit_af_{pr_id}_dias"] += 1
        if cb2.button("➖ Quitar Último Día") and st.session_state[f"edit_af_{pr_id}_dias"] > 1:
            st.session_state[f"edit_af_{pr_id}_dias"] -= 1
            
        dias_construidos = []
        for d_idx in range(st.session_state[f"edit_af_{pr_id}_dias"]):
            st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
            
            def_d_title = pr["daysData"][d_idx]["dayTitle"] if d_idx < len(pr["daysData"]) else f"Día {d_idx+1}"
            d_titulo = st.text_input(f"Título del Día {d_idx+1}:", value=def_d_title, key=f"edit_dtit_{pr_id}_{d_idx}")
            
            if f"edit_af_{pr_id}_b_{d_idx}" not in st.session_state:
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] = 1
                
            cc1, cc2 = st.columns(2)
            if cc1.button(f"➕ Añadir Bloque al Día {d_idx+1}", key=f"eaddB_{pr_id}_{d_idx}"):
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] += 1
            if cc2.button(f"➖ Quitar Bloque al Día {d_idx+1}", key=f"esubB_{pr_id}_{d_idx}") and st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] > 1:
                st.session_state[f"edit_af_{pr_id}_b_{d_idx}"] -= 1
                
            bloques_construidos = []
            for b_idx in range(st.session_state[f"edit_af_{pr_id}_b_{d_idx}"]):
                with st.expander(f"📦 Bloque {b_idx+1}", expanded=True):
                    
                    def_b_title = ""
                    def_b_note = ""
                    if d_idx < len(pr["daysData"]) and b_idx < len(pr["daysData"][d_idx].get("blocks", [])):
                        def_b_title = pr["daysData"][d_idx]["blocks"][b_idx].get("blockTitle", "")
                        def_b_note = pr["daysData"][d_idx]["blocks"][b_idx].get("blockNote", "")
                        
                    btitle = st.text_input("Nombre (ej. Calentamiento):", value=def_b_title, key=f"ebtit_{pr_id}_{d_idx}_{b_idx}")
                    bnote = st.text_input("Nota del bloque:", value=def_b_note, key=f"ebnot_{pr_id}_{d_idx}_{b_idx}")
                    
                    if f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}" not in st.session_state:
                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = []
                        
                    nombres_actuales_af = []
                    for eid in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]:
                        eobj = get_exercise(eid)
                        if eobj: nombres_actuales_af.append(f"{eobj['category']}  |  {eobj['name']}")
                        
                    ej_options_all = {}
                    for cat in CATEGORIAS_EJ:
                        for e in [x for x in exercises if x.get("category") == cat]:
                            ej_options_all[f"{cat}  |  {e['name']}"] = e['id']
                            
                    sel_names_af = st.multiselect(
                        "Buscar ejercicios", 
                        options=list(ej_options_all.keys()), 
                        default=nombres_actuales_af, 
                        key=f"ems_{pr_id}_{d_idx}_{b_idx}", 
                        label_visibility="collapsed"
                    )
                    
                    nuevos_ids_af = [ej_options_all[n] for n in sel_names_af]
                    st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"] if e in nuevos_ids_af]
                    for e in nuevos_ids_af:
                        if e not in st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]:
                            st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"].append(e)

                    inst_dict_af = {}
                    if st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]:
                        for idx_e, eid in enumerate(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"]):
                            ej_obj = get_exercise(eid)
                            ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                            
                            def_s, def_r, def_n = "", "", ""
                            if d_idx < len(pr["daysData"]) and b_idx < len(pr["daysData"][d_idx].get("blocks", [])):
                                prev_dict = pr["daysData"][d_idx]["blocks"][b_idx].get("instructions", {})
                                def_s = prev_dict.get(eid, {}).get("series", "")
                                def_r = prev_dict.get(eid, {}).get("reps", "")
                                def_n = prev_dict.get(eid, {}).get("notes", "")

                            ce1, ce2, ce3, ce4 = st.columns([5, 1, 1, 3])
                            ce1.markdown(f"<div style='margin-top:8px; font-size:14px;'>{idx_e+1}. {ej_name}</div>", unsafe_allow_html=True)
                            
                            cd_up, cd_dn = st.columns(2)
                            with ce2: s = st.text_input("S", value=def_s, key=f"es_{pr_id}_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="S")
                            with ce3: r = st.text_input("R", value=def_r, key=f"er_{pr_id}_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="R")
                            with ce4: 
                                cf1, cf2, cf3 = st.columns([3,0.7,0.7])
                                with cf1: n = st.text_input("N", value=def_n, key=f"en_{pr_id}_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="Notas")
                                with cf2:
                                    if cf2.button("⬆️", key=f"eup_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1]
                                with cf3:
                                    if cf3.button("⬇️", key=f"edn_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"])-1:
                                        st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1]
                                        
                            inst_dict_af[eid] = {"series": s, "reps": r, "notes": n}
                            
                    bloques_construidos.append({
                        "blockTitle": btitle,
                        "blockNote": bnote,
                        "exercises": st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"],
                        "instructions": inst_dict_af
                    })
            dias_construidos.append({"dayTitle": d_titulo, "blocks": bloques_construidos})
            
        st.write("")
        if st.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True):
            pr["patientId"] = af_paciente
            pr["title"] = af_titulo
            pr["frequency"] = af_frecuencia
            pr["duration"] = af_duracion
            pr["generalNote"] = af_nota
            pr["daysData"] = dias_construidos
            save_programs_af(programs_af)
            st.rerun()

    # --- MAIN ADMIN INTERFACE ---
    with st.sidebar:
        st.markdown("<h2 style='color:var(--ink); font-weight:700;'>Área Clínica</h2>", unsafe_allow_html=True)
        menu_admin = st.radio("", ["Gestión Pacientes", "Catálogo Ejercicios", "Crear Nueva Sesión", "Historial Sesiones Clínicas", "Crear Nuevo Programa AF", "Historial Programas AF"])
        st.divider()
        if st.button("Cerrar Sesión Fisio"):
            st.session_state.admin_mode = False
            st.rerun()

    if menu_admin == "Gestión Pacientes":
        st.title("Gestión de Pacientes")
        with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
            with st.form("form_nuevo_paciente", clear_on_submit=True):
                col1, col2 = st.columns(2)
                p_name = col1.text_input("Nombre Completo")
                p_phone = col2.text_input("Teléfono (Opcional)")
                p_anamnesis = st.text_area("Anamnesis / Historia", height=100)
                c_ins, c_mov, c_fue = st.columns(3)
                p_insp = c_ins.text_area("Inspección")
                p_mov = c_mov.text_area("Movilidad")
                p_fue = c_fue.text_area("Fuerza")
                if st.form_submit_button("Guardar Paciente", use_container_width=True):
                    if p_name:
                        patients.append({"id": str(uuid.uuid4())[:6], "name": p_name, "phone": p_phone, "anamnesis": p_anamnesis, "inspeccion": p_insp, "movilidad": p_mov, "fuerza": p_fue})
                        save_patients(patients)
                        st.success("Paciente añadido!")
                        st.rerun()
        
        st.write("---")
        for p in patients:
            with st.expander(f"👤 {p['name']}", expanded=False):
                st.markdown(f"**Teléfono:** {p['phone']}")
                st.markdown(f"**Anamnesis:** {p['anamnesis']}")
                colA, colB, colC = st.columns(3)
                colA.markdown(f"**Inspección:**\n{p['inspeccion']}")
                colB.markdown(f"**Movilidad:**\n{p['movilidad']}")
                colC.markdown(f"**Fuerza:**\n{p['fuerza']}")
                if st.button("🗑️ Eliminar Paciente", key=f"del_p_{p['id']}", help="Esta acción no se puede deshacer."):
                    patients = [x for x in patients if x["id"] != p["id"]]
                    save_patients(patients)
                    st.rerun()

    elif menu_admin == "Catálogo Ejercicios":
        st.title("Catálogo de Ejercicios")
        with st.expander("➕ Añadir Nuevo Ejercicio", expanded=False):
            with st.form("form_nuevo_ejercicio", clear_on_submit=True):
                e_name = st.text_input("Nombre del Ejercicio")
                e_cat = st.selectbox("Categoría", CATEGORIAS_EJ)
                e_url = st.text_input("URL del Video (YouTube, Drive...)")
                if st.form_submit_button("Guardar Ejercicio", use_container_width=True):
                    if e_name and e_url:
                        exercises.append({"id": str(uuid.uuid4())[:6], "name": e_name, "videoUrl": e_url, "category": e_cat})
                        save_exercises(exercises)
                        st.success("Ejercicio añadido!")
                        st.rerun()
                        
        st.write("---")
        for cat in CATEGORIAS_EJ:
            ejs_cat = [e for e in exercises if e["category"] == cat]
            if ejs_cat:
                st.subheader(cat)
                for e in ejs_cat:
                    c1, c2, c3 = st.columns([5, 1, 1])
                    c1.markdown(f"**{e['name']}**")
                    c2.markdown(f"[Ver Video]({e['videoUrl']})")
                    if c3.button("🗑️", key=f"del_e_{e['id']}"):
                        exercises = [x for x in exercises if x["id"] != e["id"]]
                        save_exercises(exercises)
                        st.rerun()

    elif menu_admin == "Crear Nueva Sesión":
        st.title("Crear Sesión Clínica")
        if not patients:
            st.warning("Añade al menos un paciente primero.")
        elif not exercises:
            st.warning("Añade al menos un ejercicio al catálogo.")
        else:
            if 'ses_ejs' not in st.session_state: st.session_state.ses_ejs = []
            
            c1, c2 = st.columns([1, 2])
            paciente_sel = c1.selectbox("1. Asignar a Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
            titulo_sesion = c2.text_input("2. Título de la Sesión (ej. Fase 1 Hombro):", value="Sesión Clínica")
            
            st.markdown("### 3. Seleccionar Ejercicios")
            
            ej_options_all = {}
            for cat in CATEGORIAS_EJ:
                ej_cat = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
                if ej_cat:
                    for e in ej_cat: ej_options_all[f"{cat}  |  {e['name']}"] = e['id']

            nombres_actuales = []
            for eid in st.session_state.ses_ejs:
                eobj = get_exercise(eid)
                if eobj: nombres_actuales.append(f"{eobj['category']}  |  {eobj['name']}")

            selected_names = st.multiselect("Buscador de ejercicios", options=list(ej_options_all.keys()), default=nombres_actuales, label_visibility="collapsed")
            
            nuevos_ids = [ej_options_all[n] for n in selected_names]
            st.session_state.ses_ejs = [e for e in st.session_state.ses_ejs if e in nuevos_ids]
            for e in nuevos_ids:
                if e not in st.session_state.ses_ejs: st.session_state.ses_ejs.append(e)
            
            instrucciones_dict = {}
            if st.session_state.ses_ejs:
                st.markdown("### 4. Configurar Pautas y Orden")
                
                for idx, e_id in enumerate(st.session_state.ses_ejs):
                    ej_obj = get_exercise(e_id)
                    ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                    
                    c_t, c_s, c_r, c_n, c_up, c_dn = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                    with c_t: 
                        st.markdown(f"<div style='margin-top:8px; font-size:14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx+1}. {ej_name}</div>", unsafe_allow_html=True)
                    with c_s: 
                        s = st.text_input("S", key=f"is_{e_id}", label_visibility="collapsed", placeholder="Series")
                    with c_r: 
                        r = st.text_input("R", key=f"ir_{e_id}", label_visibility="collapsed", placeholder="Reps")
                    with c_n: 
                        n = st.text_input("N", key=f"in_{e_id}", label_visibility="collapsed", placeholder="Notas breves")
                    with c_up:
                        if st.button("⬆️", key=f"up_{e_id}") and idx > 0:
                            st.session_state.ses_ejs[idx-1], st.session_state.ses_ejs[idx] = st.session_state.ses_ejs[idx], st.session_state.ses_ejs[idx-1]
                            st.rerun()
                    with c_dn:
                        if st.button("⬇️", key=f"dn_{e_id}") and idx < len(st.session_state.ses_ejs) - 1:
                            st.session_state.ses_ejs[idx+1], st.session_state.ses_ejs[idx] = st.session_state.ses_ejs[idx], st.session_state.ses_ejs[idx+1]
                            st.rerun()
                            
                    instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                
                st.write("")
                if st.button("✅ Generar y Guardar Sesión", type="primary", use_container_width=True):
                    pin = str(random.randint(1000, 9999))
                    new_plan = {
                        "id": str(uuid.uuid4())[:8],
                        "patientId": paciente_sel,
                        "title": titulo_sesion,
                        "exerciseIds": st.session_state.ses_ejs,
                        "exerciseInstructions": instrucciones_dict,
                        "pin": pin
                    }
                    plans.append(new_plan)
                    save_plans(plans)
                    st.session_state.ses_ejs = []
                    st.success(f"Sesión guardada! El PIN del paciente es: {pin}")
                    st.info("Ve al Historial de Sesiones para verla.")
            else:
                st.info("Usa el buscador para añadir ejercicios a la sesión.")

    elif menu_admin == "Historial Sesiones Clínicas":
        st.title("Historial de Sesiones")
        
        pacientes_con_planes = list(set([p["patientId"] for p in plans]))
        paciente_filtro = st.selectbox("Filtrar por Paciente:", options=["Todos"] + pacientes_con_planes, format_func=lambda x: "Todos" if x == "Todos" else get_patient_name(x))
        
        planes_filtrados = plans if paciente_filtro == "Todos" else [p for p in plans if p["patientId"] == paciente_filtro]
        
        for p in reversed(planes_filtrados):
            with st.expander(f"📁 {p['title']} - {get_patient_name(p['patientId'])}", expanded=False):
                c_pin, c_link = st.columns(2)
                c_pin.markdown(f"**PIN de acceso:** `{p['pin']}`")
                link = f"{APP_URL}?pin={p['pin']}"
                c_link.markdown(f"**Enlace directo:** [Copiar Link]({link})")
                
                st.markdown("### Ejercicios:")
                for e_id in p["exerciseIds"]:
                    e = get_exercise(e_id)
                    inst = p["exerciseInstructions"].get(e_id, {})
                    if e:
                        st.markdown(f"- **{e['name']}** (Series: {inst.get('series','')}, Reps: {inst.get('reps','')}) - {inst.get('notes','')}")
                
                st.divider()
                st.markdown("### Historial de Feedback del Paciente (Check-ins)")
                cks = [c for c in checkins if c["planId"] == p["id"]]
                if cks:
                    for c in cks:
                        st.info(f"🗓️ **{c['date']}** | 💥 Dolor (EVA): **{c['eva']}/10** | 🥵 Esfuerzo (Borg): **{c['borg']}/10**\n\n💬 {c['comment']}")
                else:
                    st.write("Aún no hay registros para esta sesión.")
                    
                st.divider()
                ca, cb = st.columns(2)
                if ca.button("✏️ Editar Sesión", key=f"edit_{p['id']}"):
                    st.session_state[f"edit_ses_{p['id']}_ejs"] = p["exerciseIds"].copy()
                    modal_editar_sesion(p)
                if cb.button("🗑️ Eliminar Sesión", key=f"del_plan_{p['id']}"):
                    plans = [x for x in plans if x["id"] != p["id"]]
                    save_plans(plans)
                    st.rerun()

    elif menu_admin == "Crear Nuevo Programa AF":
        st.title("Crear Programa de Actividad Física")
        if not patients:
            st.warning("Añade al menos un paciente.")
        elif not exercises:
            st.warning("Añade ejercicios al catálogo.")
        else:
            if 'num_dias' not in st.session_state: st.session_state.num_dias = 1
            
            c1, c2 = st.columns([1, 2])
            af_paciente = c1.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
            af_titulo = c2.text_input("2. Título del programa:", value="Plan Semanal Actividad Física")
            
            c3, c4 = st.columns(2)
            af_frecuencia = c3.text_input("3. Frecuencia semanal (ej. 3 días/semana):")
            af_duracion = c4.text_input("4. Duración por sesión (ej. 45 min):")
            
            af_nota = st.text_input("5. Nota general o indicaciones globales:")
            
            st.divider()
            st.markdown("### 📅 Días y Bloques")
            
            cb1, cb2 = st.columns(2)
            if cb1.button("➕ Añadir Día al Plan"): 
                st.session_state.num_dias += 1
                st.rerun()
            if cb2.button("➖ Quitar Último Día") and st.session_state.num_dias > 1: 
                st.session_state.num_dias -= 1
                st.rerun()

            dias_construidos = []
            
            for d_idx in range(st.session_state.num_dias):
                st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
                d_titulo = st.text_input(f"Título del Día (opcional, ej. 'Día de Fuerza' o 'Lunes'):", key=f"dtit_{d_idx}")
                
                if f"num_bloques_{d_idx}" not in st.session_state:
                    st.session_state[f"num_bloques_{d_idx}"] = 1
                
                cc1, cc2 = st.columns(2)
                if cc1.button(f"➕ Añadir Bloque al Día {d_idx+1}", key=f"addB_{d_idx}"):
                    st.session_state[f"num_bloques_{d_idx}"] += 1
                    st.rerun()
                if cc2.button(f"➖ Quitar Bloque al Día {d_idx+1}", key=f"subB_{d_idx}") and st.session_state[f"num_bloques_{d_idx}"] > 1:
                    st.session_state[f"num_bloques_{d_idx}"] -= 1
                    st.rerun()
                
                bloques_construidos = []
                for b_idx in range(st.session_state[f"num_bloques_{d_idx}"]):
                    with st.expander(f"📦 Bloque {b_idx+1}", expanded=True):
                        btitle = st.text_input("Nombre (ej. Calentamiento, Fuerza, Cardio):", key=f"btit_{d_idx}_{b_idx}")
                        bnote = st.text_input("Nota del bloque (ej. Realizar en circuito, descansar 1 min...):", key=f"bnot_{d_idx}_{b_idx}")
                        
                        if f"af_ejs_{d_idx}_{b_idx}" not in st.session_state:
                            st.session_state[f"af_ejs_{d_idx}_{b_idx}"] = []
                            
                        nombres_actuales_af = []
                        for eid in st.session_state[f"af_ejs_{d_idx}_{b_idx}"]:
                            eobj = get_exercise(eid)
                            if eobj: nombres_actuales_af.append(f"{eobj['category']}  |  {eobj['name']}")
                            
                        ej_options_all = {}
                        for cat in CATEGORIAS_EJ:
                            for e in [x for x in exercises if x.get("category") == cat]:
                                ej_options_all[f"{cat}  |  {e['name']}"] = e['id']
                                
                        sel_names_af = st.multiselect(
                            "Buscar ejercicios", 
                            options=list(ej_options_all.keys()), 
                            default=nombres_actuales_af, 
                            key=f"ms_{d_idx}_{b_idx}", 
                            label_visibility="collapsed"
                        )
                        
                        nuevos_ids_af = [ej_options_all[n] for n in sel_names_af]
                        st.session_state[f"af_ejs_{d_idx}_{b_idx}"] = [e for e in st.session_state[f"af_ejs_{d_idx}_{b_idx}"] if e in nuevos_ids_af]
                        for e in nuevos_ids_af:
                            if e not in st.session_state[f"af_ejs_{d_idx}_{b_idx}"]:
                                st.session_state[f"af_ejs_{d_idx}_{b_idx}"].append(e)

                        inst_dict_af = {}
                        if st.session_state[f"af_ejs_{d_idx}_{b_idx}"]:
                            for idx_e, eid in enumerate(st.session_state[f"af_ejs_{d_idx}_{b_idx}"]):
                                ej_obj = get_exercise(eid)
                                ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                                
                                ce1, ce2, ce3, ce4 = st.columns([5, 1, 1, 3])
                                ce1.markdown(f"<div style='margin-top:8px; font-size:14px;'>{idx_e+1}. {ej_name}</div>", unsafe_allow_html=True)
                                
                                cd_up, cd_dn = st.columns(2)
                                with ce2: s = st.text_input("S", key=f"afs_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="S")
                                with ce3: r = st.text_input("R", key=f"afr_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="R")
                                with ce4: 
                                    cf1, cf2, cf3 = st.columns([3,0.7,0.7])
                                    with cf1: n = st.text_input("N", key=f"afn_{d_idx}_{b_idx}_{eid}", label_visibility="collapsed", placeholder="Notas")
                                    with cf2:
                                        if cf2.button("⬆️", key=f"afup_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                                            st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e-1]
                                            st.rerun()
                                    with cf3:
                                        if cf3.button("⬇️", key=f"afdn_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"af_ejs_{d_idx}_{b_idx}"])-1:
                                            st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"af_ejs_{d_idx}_{b_idx}"][idx_e+1]
                                            st.rerun()
                                            
                                inst_dict_af[eid] = {"series": s, "reps": r, "notes": n}
                                
                        bloques_construidos.append({
                            "blockTitle": btitle,
                            "blockNote": bnote,
                            "exercises": st.session_state[f"af_ejs_{d_idx}_{b_idx}"],
                            "instructions": inst_dict_af
                        })
                
                dias_construidos.append({
                    "dayTitle": d_titulo if d_titulo else f"Día {d_idx+1}",
                    "blocks": bloques_construidos
                })

            st.write("")
            if st.button("✅ Generar y Guardar Programa AF", type="primary", use_container_width=True):
                pin = str(random.randint(1000, 9999))
                new_af = {
                    "id": f"AF-{str(uuid.uuid4())[:6]}",
                    "patientId": af_paciente,
                    "title": af_titulo,
                    "frequency": af_frecuencia,
                    "duration": af_duracion,
                    "generalNote": af_nota,
                    "pin": pin,
                    "daysData": dias_construidos
                }
                programs_af.append(new_af)
                save_programs_af(programs_af)
                
                # Reset states
                st.session_state.num_dias = 1
                for key in list(st.session_state.keys()):
                    if key.startswith("num_bloques_") or key.startswith("af_ejs_"):
                        del st.session_state[key]
                        
                st.success(f"Programa guardado! El PIN del paciente es: {pin}")

    elif menu_admin == "Historial Programas AF":
        st.title("Historial Programas AF")
        
        for pr in reversed(programs_af):
            with st.expander(f"🏃 {pr['title']} - {get_patient_name(pr['patientId'])}", expanded=False):
                c_pin, c_link = st.columns(2)
                c_pin.markdown(f"**PIN de acceso:** `{pr['pin']}`")
                link = f"{APP_URL}?pin={pr['pin']}"
                c_link.markdown(f"**Enlace directo:** [Copiar Link]({link})")
                
                st.markdown(f"**Frecuencia:** {pr['frequency']} | **Duración:** {pr['duration']}")
                if pr["generalNote"]: st.markdown(f"*{pr['generalNote']}*")
                
                for d_idx, dia in enumerate(pr["daysData"]):
                    st.markdown(f"#### {dia.get('dayTitle', f'Día {d_idx+1}')}")
                    for b_idx, bloque in enumerate(dia.get("blocks", [])):
                        btit = bloque.get('blockTitle', '')
                        if btit: st.markdown(f"**📦 {btit}**")
                        bnot = bloque.get('blockNote', '')
                        if bnot: st.markdown(f"_{bnot}_")
                        
                        for eid in bloque.get("exercises", []):
                            e = get_exercise(eid)
                            inst = bloque.get("instructions", {}).get(eid, {})
                            if e:
                                st.markdown(f"- **{e['name']}** (S: {inst.get('series','')}, R: {inst.get('reps','')}) {inst.get('notes','')}")
                
                st.divider()
                st.markdown("### Historial de Feedback (Check-ins)")
                cks = [c for c in checkins if c["planId"] == pr["id"]]
                if cks:
                    for c in cks:
                        st.info(f"🗓️ **{c['date']}** | 💥 Dolor: **{c['eva']}/10** | 🥵 Esfuerzo: **{c['borg']}/10**\n\n💬 {c['comment']}")
                else:
                    st.write("Aún no hay registros.")
                
                st.divider()
                ca, cb = st.columns(2)
                if ca.button("✏️ Editar Programa", key=f"edit_pr_{pr['id']}"):
                    st.session_state[f"edit_af_{pr['id']}_dias"] = len(pr["daysData"])
                    for d_i, dia in enumerate(pr["daysData"]):
                        st.session_state[f"edit_af_{pr['id']}_b_{d_i}"] = len(dia.get("blocks", []))
                        for b_i, bloque in enumerate(dia.get("blocks", [])):
                            st.session_state[f"edit_af_{pr['id']}_ejs_{d_i}_{b_i}"] = bloque.get("exercises", []).copy()
                    modal_editar_programa(pr)
                if cb.button("🗑️ Eliminar Programa", key=f"del_pr_{pr['id']}"):
                    programs_af = [x for x in programs_af if x["id"] != pr["id"]]
                    save_programs_af(programs_af)
                    st.rerun()

# =============================================================
# PANTALLA DE ACCESO PACIENTE/FISIO
# =============================================================
elif not st.session_state.logged_pin:
    # URL parameters
    query_params = st.query_params
    pin_from_url = query_params.get("pin", "")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: var(--ink); margin-bottom: 30px;'>Acceso a Sesión</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            pin_input = st.text_input("Introduce tu código PIN (o contraseña Fisio):", type="password", value=pin_from_url)
            submit = st.form_submit_button("Entrar", use_container_width=True)
            if submit:
                if pin_input == PASSWORD_FISIO:
                    st.session_state.admin_mode = True
                    st.rerun()
                else:
                    found = False
                    for p in plans:
                        if p["pin"] == pin_input:
                            st.session_state.logged_pin = pin_input
                            found = True
                            st.rerun()
                            break
                    if not found:
                        for pr in programs_af:
                            if pr["pin"] == pin_input:
                                st.session_state.logged_pin = pin_input
                                found = True
                                st.rerun()
                                break
                    if not found:
                        st.error("PIN incorrecto. Revisa el código.")

# =============================================================
# MÓDULO 2: ÁREA PACIENTE
# =============================================================
else:
    active_plan = None
    is_af = False
    
    for p in plans:
        if p["pin"] == st.session_state.logged_pin:
            active_plan = p
            break
            
    if not active_plan:
        for pr in programs_af:
            if pr["pin"] == st.session_state.logged_pin:
                active_plan = pr
                is_af = True
                break

    if active_plan:
        with st.sidebar:
            st.markdown(f"### Hola, {get_patient_name(active_plan['patientId'])}")
            if st.button("Salir"):
                st.session_state.logged_pin = None
                st.rerun()
                
        st.title(active_plan['title'])
        
        # --- RENDERIZADO SESIÓN CLÍNICA ---
        if not is_af:
            for idx, e_id in enumerate(active_plan["exerciseIds"]):
                e = get_exercise(e_id)
                if not e: continue
                inst = active_plan["exerciseInstructions"].get(e_id, {})
                
                with st.container():
                    st.markdown(f"<div style='background:white; border-radius:15px; padding:20px; border:1px solid var(--line); margin-bottom:15px;'>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='margin-top:0; color:var(--green) !important;'>{idx+1}. {e['name']}</h3>", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([1.5, 1])
                    with c1:
                        if e['videoUrl']:
                            st.video(e['videoUrl'])
                        else:
                            st.info("Sin video disponible.")
                    with c2:
                        st.markdown(f"**Series:** {inst.get('series', '-')}")
                        st.markdown(f"**Repeticiones:** {inst.get('reps', '-')}")
                        if inst.get('notes'):
                            st.info(f"💡 {inst.get('notes')}")
                    st.markdown("</div>", unsafe_allow_html=True)

        # --- RENDERIZADO PROGRAMA AF ---
        else:
            st.markdown(f"**Frecuencia:** {active_plan['frequency']} | **Duración:** {active_plan['duration']}")
            if active_plan["generalNote"]: 
                st.info(active_plan["generalNote"])
                
            for d_idx, dia in enumerate(active_plan["daysData"]):
                st.markdown(f"### {dia.get('dayTitle', f'Día {d_idx+1}')}")
                
                for b_idx, bloque in enumerate(dia.get("blocks", [])):
                    btit = bloque.get('blockTitle', '')
                    if btit: st.markdown(f"#### 📦 {btit}")
                    bnot = bloque.get('blockNote', '')
                    if bnot: st.markdown(f"_{bnot}_")
                    
                    for idx_e, eid in enumerate(bloque.get("exercises", [])):
                        e = get_exercise(eid)
                        if not e: continue
                        inst = bloque.get("instructions", {}).get(eid, {})
                        
                        with st.container():
                            st.markdown(f"<div style='background:white; border-radius:15px; padding:20px; border:1px solid var(--line); margin-bottom:15px;'>", unsafe_allow_html=True)
                            st.markdown(f"<h4 style='margin-top:0; color:var(--green) !important;'>{idx_e+1}. {e['name']}</h4>", unsafe_allow_html=True)
                            
                            c1, c2 = st.columns([1.5, 1])
                            with c1:
                                if e['videoUrl']: st.video(e['videoUrl'])
                            with c2:
                                st.markdown(f"**Series:** {inst.get('series', '-')}")
                                st.markdown(f"**Repeticiones:** {inst.get('reps', '-')}")
                                if inst.get('notes'): st.info(f"💡 {inst.get('notes')}")
                            st.markdown("</div>", unsafe_allow_html=True)
                st.divider()

        # --- FORMULARIO DE CHECK-IN ---
        st.markdown("### ✅ Registro de Sesión")
        st.write("¿Has completado el entrenamiento? Déjame tu feedback.")
        with st.form("checkin_form", clear_on_submit=True):
            col_eva, col_borg = st.columns(2)
            eva = col_eva.slider("Nivel de Dolor (EVA)", 0, 10, 0, help="0 = Sin dolor, 10 = Máximo dolor")
            borg = col_borg.slider("Esfuerzo Percibido (Borg)", 0, 10, 5, help="0 = Reposo, 10 = Esfuerzo Máximo")
            comment = st.text_area("Comentarios o molestias durante los ejercicios:")
            
            if st.form_submit_button("Enviar Feedback", use_container_width=True):
                hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                save_checkin_item(active_plan["id"], hoy, eva, borg, comment)
                st.success("¡Buen trabajo! Feedback enviado al fisioterapeuta.")
