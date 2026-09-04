import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import altair as alt
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
if 'editing_sesion_id' not in st.session_state:
    st.session_state.editing_sesion_id = None
if 'editing_program_id' not in st.session_state:
    st.session_state.editing_program_id = None

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
                        if old_block:
                            for ex_old in old_block.get("exercises", []):
                                if ex_old.get("exerciseId") == eid:
                                    def_prio = ex_old.get("isPriority", False)
                                    break
                                    
                        prio_key = f"eprio_{pr_id}_{d_idx}_{b_idx}_{eid}"
                        if prio_key not in st.session_state:
                            st.session_state[prio_key] = def_prio
                            
                        ce1, ce2, ce3, ce4 = st.columns([4, 2, 0.6, 0.6])
                        ce1.markdown(f"<div style='margin-top:6px; font-weight:bold;'>{idx_e+1}. {ename}</div>", unsafe_allow_html=True)
                        es_prio = ce2.checkbox("⭐ Prioritario", key=prio_key)
                        if ce3.button("⬆️", key=f"eup_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e > 0:
                            st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e-1]
                            st.rerun()
                        if ce4.button("⬇️", key=f"edn_{pr_id}_{d_idx}_{b_idx}_{eid}") and idx_e < len(st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"])-1:
                            st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e] = st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e], st.session_state[f"edit_af_{pr_id}_ejs_{d_idx}_{b_idx}"][idx_e+1]
                            st.rerun()
                            
                        ejs_bloque_info.append({"exerciseId": eid, "isPriority": es_prio})
                        
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
    # --- FIN DE VENTANAS EMERGENTES ---

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

    # -------------------------------------------------------------
    # BOTÓN DE COPIA DE SEGURIDAD LOCAL
    # -------------------------------------------------------------
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

    # AVISO DE ERROR DE CONEXIÓN
    if st.session_state.gsheets_read_error:
        st.error("⚠️ Atención: Ha habido un fallo de conexión con Google Sheets. Las funciones de guardado y borrado están bloqueadas temporalmente para proteger tus datos. Recarga la página en unos segundos.")

    # -------------------------------------------------------------
    # VISTA 1: ARCHIVO
    # -------------------------------------------------------------
    if menu_seleccion == "📁 Archivo":
        st.markdown("<h1>📁 Base de Datos y Archivo</h1>", unsafe_allow_html=True)
        tab_pac, tab_ej = st.tabs(["👥 Pacientes", "🎥 Ejercicios"])
        
        with tab_pac:
            with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
                with st.form("nuevo_paciente_form", clear_on_submit=True):
                    c_np1, c_np2 = st.columns([3, 1])
                    new_p_name = c_np1.text_input("Nombre completo:")
                    new_p_phone = c_np2.text_input("Teléfono:")
                    
                    new_p_ana = st.text_area("Anamnesis (entrevista, historia clínica...):")
                    new_p_ins = st.text_area("Inspección física (temperatura, coloración, medidas...):")
                    new_p_mov = st.text_area("Movilidad activa y pasiva (ROM activo y pasivo...):")
                    new_p_fue = st.text_area("Fuerza (dinamometría...):")
                    
                    if st.form_submit_button("Guardar Paciente Nuevo", type="primary"):
                        if new_p_name:
                            patients.append({
                                "id": str(uuid.uuid4())[:4], "name": new_p_name, "phone": new_p_phone,
                                "anamnesis": new_p_ana, "inspeccion": new_p_ins, "movilidad": new_p_mov, "fuerza": new_p_fue
                            })
                            save_patients(patients)
                            st.success("¡Paciente añadido y sincronizado!")
                            st.rerun()

            total_pacs = len(patients)
            st.markdown(f"<h3 style='margin-top:20px;'>Directorio y Perfiles ({total_pacs})</h3>", unsafe_allow_html=True)
            search_pac = st.text_input("🔍 Buscar paciente por nombre:")
            
            pacs_filtrados = patients
            if search_pac:
                q_pac = search_pac.lower()
                pacs_filtrados = [p for p in pacs_filtrados if q_pac in p["name"].lower()]

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
                    
                    ce1, ce2 = st.columns([3, 1])
                    edit_name = ce1.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                    edit_phone = ce2.text_input("Teléfono", value=p.get("phone", ""), key=f"phone_{p['id']}")
                    
                    edit_ana = st.text_area("Anamnesis (entrevista, historia clínica...):", value=p.get("anamnesis", ""), key=f"ana_{p['id']}")
                    edit_ins = st.text_area("Inspección física (temperatura, coloración, medidas...):", value=p.get("inspeccion", ""), key=f"ins_{p['id']}")
                    edit_mov = st.text_area("Movilidad activa y pasiva (ROM activo y pasivo...):", value=p.get("movilidad", ""), key=f"mov_{p['id']}")
                    edit_fue = st.text_area("Fuerza (dinamometría...):", value=p.get("fuerza", ""), key=f"fue_{p['id']}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("💾 Actualizar Datos", key=f"upd_{p['id']}", type="primary"):
                        p["name"] = edit_name; p["phone"] = edit_phone
                        p["anamnesis"] = edit_ana; p["inspeccion"] = edit_ins
                        p["movilidad"] = edit_mov; p["fuerza"] = edit_fue
                        save_patients(patients); st.rerun()
                    if c2.button("🗑️ Borrar Paciente", key=f"del_{p['id']}"):
                        patients = [x for x in patients if str(x["id"]) != str(p["id"])]
                        save_patients(patients); st.rerun()

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
                            "id": str(uuid.uuid4())[:4],
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
                    lista_final = []
                    for e in exercises:
                        eid = e["id"]
                        if eid not in ids_borrar:
                            lista_final.append(nuevos_datos[eid])
                        
                    save_exercises(lista_final)
                    st.success("¡Base de datos de ejercicios actualizada!")
                    st.rerun()

    # -------------------------------------------------------------
    # VISTA 2: SESIONES CLÍNICAS
    # -------------------------------------------------------------
    elif menu_seleccion == "🩺 Sesiones":
        st.markdown("<h1>🩺 Sesiones Clínicas</h1>", unsafe_allow_html=True)
        # Añadimos la nueva pestaña de Seguimiento Pacientes
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
            for pl in plans: sesiones_actuales[pl["patientId"]] = pl
            planes_filtrados = list(reversed(sesiones_actuales.values()))
            
            if search_query:
                q = search_query.lower()
                planes_filtrados = [pl for pl in planes_filtrados if q in pl["title"].lower() or q in get_patient_name(pl["patientId"]).lower()]
            
            if not planes_filtrados:
                st.info("No se encontraron sesiones.")
            else:
                for pl in planes_filtrados:
                    with st.container(border=True):
                        st.markdown(f"#### {pl['title']}")
                        st.markdown(f"<span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pl['pin']}</span>", unsafe_allow_html=True)
                        st.write(f"👤 **Paciente:** {get_patient_name(pl['patientId'])}")

                        st.write("")
                        c_espacio, c_edit, c_copy, c_del = st.columns([6, 1.2, 1.4, 1.2])
                        with c_edit:
                            if st.button("✏️ Editar", key=f"edit_btn_{pl['id']}", use_container_width=True):
                                st.session_state.editing_sesion_id = pl["id"]
                                st.session_state[f"edit_ses_{pl['id']}_ejs"] = pl["exerciseIds"].copy()
                                st.rerun()
                        with c_copy:
                            with st.popover("📋 Copiar", use_container_width=True):
                                st.caption("Copia el mensaje usando el icono de la esquina superior derecha:")
                                mensaje_wa = f"¡Hola {get_patient_name(pl['patientId'])}! 👋\n\nAquí tienes tu sesión de fisioterapia: *{pl['title']}*.\n\n📱 Accede directamente desde aquí:\n{APP_URL}\n\n🔑 Tu código de acceso (PIN) es: {pl['pin']}\n\n¡A por ello!"
                                st.code(mensaje_wa, language="markdown")
                        with c_del:
                            if st.button("🗑️ Eliminar", key=f"del_{pl['id']}", use_container_width=True):
                                plans = [x for x in plans if str(x["id"]) != str(pl["id"])]
                                save_plans(plans); st.rerun()

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
                        nuevo_pin = str(random.randint(100000, 999999))
                        plans.append({
                            "id": str(uuid.uuid4())[:4], "patientId": paciente_sel, "title": titulo_sesion,
                            "exerciseIds": st.session_state.orden_ejs, "exerciseInstructions": instrucciones_dict,
                            "pin": nuevo_pin
                        })
                        save_plans(plans)
                        st.session_state.orden_ejs = []
                        st.success("¡Sesión guardada!")
                        
                        nombre_paciente = get_patient_name(paciente_sel)
                        mensaje_whatsapp = f"¡Hola {nombre_paciente}! 👋\n\nAquí tienes tu nueva sesión de fisioterapia: *{titulo_sesion}*.\n\n📱 Para ver tus ejercicios y vídeos, entra en este enlace:\n{APP_URL}\n\n🔑 Tu código de acceso (PIN) es: {nuevo_pin}\n\n¡A por ello!"
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
                # Buscador con autocompletado nativo
                paciente_sel_seg = st.selectbox(
                    "🔍 Buscar Paciente:", 
                    options=[p["id"] for p in patients], 
                    format_func=get_patient_name, 
                    key="search_pac_seg"
                )
                
                # Filtrar sesiones y checkins del paciente
                planes_paciente = [p["id"] for p in plans if str(p["patientId"]) == str(paciente_sel_seg)]
                checkins_paciente = [c for c in checkins if str(c["planId"]) in planes_paciente]
                
                if not checkins_paciente:
                    st.info("Este paciente aún no ha registrado ningún reporte en sus sesiones.")
                else:
                    # Preparar los datos con pandas
                    df_checkins = pd.DataFrame(checkins_paciente)
                    df_checkins['date_obj'] = pd.to_datetime(df_checkins['date'], format="%Y-%m-%d %H:%M", errors='coerce')
                    df_checkins = df_checkins.sort_values(by='date_obj')
                    
                    # Asegurar que EVA y Borg sean números
                    df_checkins['eva'] = pd.to_numeric(df_checkins['eva'], errors='coerce').fillna(0)
                    df_checkins['borg'] = pd.to_numeric(df_checkins['borg'], errors='coerce').fillna(0)
                    
                    # --- NUEVOS FORMATOS DE FECHA ---
                    # Para la gráfica (Solo día/mes/año)
                    df_checkins['Fecha_Corta'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y')
                    # Para la tabla de comentarios (Día/mes/año Hora:Minuto)
                    df_checkins['Fecha_Larga'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y %H:%M')
                    
                    st.markdown("#### 📊 Gráfica de Dolor y Fatiga")
                    
                    # Preparar dataframe estructurado para Altair
                    df_melted = df_checkins[['Fecha_Corta', 'eva', 'borg']].copy()
                    df_melted = df_melted.rename(columns={'eva': 'Dolor (EVA)', 'borg': 'Fatiga (Borg)'})
                    # "Derretir" los datos para que Altair entienda las dos líneas
                    df_melted = df_melted.melt('Fecha_Corta', var_name='Métrica', value_name='Puntuación')
                    
                    # --- CREACIÓN DE LA GRÁFICA FIJA ---
                    grafica = alt.Chart(df_melted).mark_line(point=True).encode(
                        x=alt.X('Fecha_Corta:N', title='Fecha', sort=None, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Puntuación:Q', scale=alt.Scale(domain=[0, 10]), title='Escala (0-10)'),
                        color=alt.Color('Métrica:N', scale=alt.Scale(
                            domain=['Dolor (EVA)', 'Fatiga (Borg)'], 
                            range=["#aa3838", "#13765d"]
                        ))
                    ).properties(height=350)
                    
                    # Al usar st.altair_chart sin la opción ".interactive()", el zoom queda desactivado automáticamente
                    st.altair_chart(grafica, use_container_width=True)
                    
                    st.markdown("#### 💬 Historial de Comentarios")
                    df_comments = df_checkins[['Fecha_Larga', 'eva', 'borg', 'comment']].copy()
                    df_comments = df_comments.rename(columns={'Fecha_Larga': 'Fecha', 'eva': 'EVA', 'borg': 'Borg', 'comment': 'Comentario'})
                    st.dataframe(df_comments, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # VISTA 3: PROGRAMAS DE AF
    # -------------------------------------------------------------
    elif menu_seleccion == "🏋️ Programas de AF":
        st.markdown("<h1>🏋️ Programas de Actividad Física</h1>", unsafe_allow_html=True)
        tab_gest_af, tab_crear_af = st.tabs(["⚙️ Programas Activos", "📝 Crear Nuevo Programa AF"])
        
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
                        st.markdown(f"#### {pr['title']}")
                        st.markdown(f"<span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pr['pin']}</span>", unsafe_allow_html=True)
                        st.write(f"👤 **Paciente:** {get_patient_name(pr['patientId'])}")
                        st.write(f"⏱️ **Frecuencia:** {pr['frequency']} | **Duración:** {pr['duration']}")
                        
                        st.write("")
                        c_espacio, c_edit, c_copy, c_del = st.columns([6, 1.2, 1.4, 1.2])
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
                                mensaje_wa_gen = f"¡Hola {get_patient_name(pr['patientId'])}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{pr['title']}*.\n\n📱 Accede directamente desde aquí:\n{APP_URL}\n\n🔑 Tu código PIN de acceso es: {pr['pin']}\n\n¡A entrenar!"
                                st.code(mensaje_wa_gen, language="markdown")
                        with c_del:
                            if st.button("🗑️ Eliminar", key=f"del_af_{pr['id']}", use_container_width=True):
                                programs_af = [x for x in programs_af if str(x["id"]) != str(pr["id"])]
                                save_programs_af(programs_af)
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
                
                # Configuración de Frecuencia y Duración con formato automático (Diseño optimizado)
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
                                st.caption("Ordena los ejercicios con las flechas ⬆️/⬇️ y marca si son ⭐ Prioritarios:")
                                for idx_e, eid in enumerate(st.session_state[key_order_af]):
                                    ej_obj = get_exercise(eid)
                                    ename = ej_obj['name'] if ej_obj else "Ejercicio"
                                    sin_video_af = False
                                    
                                    if ej_obj and not ej_obj.get("videoUrl", "").strip():
                                        sin_video_af = True
                                        falta_algun_video_af = True
                                        ename += " ⚠️ (SIN VÍDEO)"
                                    
                                    col_e_name, col_e_prio, col_e_up, col_e_dn = st.columns([4, 2, 0.6, 0.6])
                                    with col_e_name:
                                        color_t = "#aa3838" if sin_video_af else "inherit"
                                        st.markdown(f"<div style='margin-top:6px; font-weight:bold; color:{color_t};'>{idx_e + 1}. {ename}</div>", unsafe_allow_html=True)
                                    with col_e_prio:
                                        prio_key = f"prio_{d_idx}_{b_idx}_{eid}"
                                        if prio_key not in st.session_state:
                                            st.session_state[prio_key] = st.session_state.prio_dict.get(prio_key, False)
                                            
                                        es_prio = st.checkbox("⭐ Prioritario", key=prio_key, on_change=_save_prio, args=(prio_key,))
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

                                    ejs_bloque_info.append({"exerciseId": eid, "isPriority": es_prio})

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
                            nuevo_pin_af = str(random.randint(100000, 999999))
                            
                            # Concatenamos automáticamente el texto a los números introducidos
                            frecuencia_guardar = f"{af_frecuencia.strip()} días/semana" if af_frecuencia.strip() else ""
                            duracion_guardar = f"{af_duracion.strip()} minutos/día" if af_duracion.strip() else ""
                            
                            programs_af.append({
                                "id": str(uuid.uuid4())[:4],
                                "patientId": af_paciente,
                                "title": af_titulo,
                                "frequency": frecuencia_guardar,
                                "duration": duracion_guardar,
                                "generalNote": af_nota_gen,
                                "pin": nuevo_pin_af,
                                "daysData": dias_construidos
                            })
                            save_programs_af(programs_af)
                            st.session_state.prio_dict = {} 
                            st.success("¡Programa de AF creado con éxito!")
                            
                            nombre_p = get_patient_name(af_paciente)
                            mensaje_wa_gen = f"¡Hola {nombre_p}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{af_titulo}*.\n\n📱 Accede directamente desde tu móvil:\n{APP_URL}\n\n🔑 Tu PIN de acceso es: {nuevo_pin_af}\n\n¡A por todas!"
                            st.info("Copia el mensaje para mandarlo por WhatsApp:")
                            st.code(mensaje_wa_gen, language="markdown")

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE / FORMULARIO LOGIN
# =============================================================
else:
    if not st.session_state.logged_pin:
        st.markdown("<div style='text-align:center; margin-top:40px;'><h1 style='font-size:27px;'>🏋️ Acceso a tu Sesión o Programa</h1><p style='color:#64756e;'>Introduce tu código PIN de acceso</p></div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form", clear_on_submit=False):
                pin_input = st.text_input("PIN de acceso", type="password", label_visibility="hidden", placeholder="Ej: 785518")
                btn_login = st.form_submit_button("🔑 Acceder a mi sesión", type="primary", use_container_width=True)
                
                if btn_login and pin_input:
                    val_pin = pin_input.strip()
                    if val_pin == PASSWORD_FISIO:
                        st.session_state.admin_mode = True
                        st.rerun()
                    else:
                        st.session_state.logged_pin = val_pin
                        st.rerun()

    else:
        pin_ingresado = st.session_state.logged_pin
        
        sesion_encontrada = next((p for p in plans if str(p["pin"]) == str(pin_ingresado)), None)
        programa_af_encontrado = next((pr for pr in programs_af if str(pr["pin"]) == str(pin_ingresado)), None)
        
        col_exit1, col_exit2 = st.columns([4, 1])
        with col_exit2:
            if st.button("🚪 Cambiar PIN", key="exit_pin_btn"):
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

            for day in pr['daysData']:
                st.markdown(f"<div style='background:#103d33; color:white; padding:12px 18px; border-radius:10px; font-weight:bold; font-size:18px; margin-top:25px; margin-bottom:15px;'>{day['dayTitle']}</div>", unsafe_allow_html=True)
                
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
                    
                    for item in block['exercises']:
                        ex_data = get_exercise(item['exerciseId'])
                        if ex_data:
                            prio_badge = "<span style='background:#fff3cd; color:#856404; padding:3px 8px; border-radius:5px; font-size:12px; font-weight:bold; margin-left:8px;'>⭐ Prioritario</span>" if item.get('isPriority') else ""
                            
                            vid_url = ex_data.get('videoUrl', '').strip()
                            if vid_url:
                                btn_video = f"<a href='{vid_url}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:8px 14px; border-radius:7px; font-weight:bold; font-size:13px;'>▶ Ver Vídeo</a>"
                            else:
                                btn_video = ""
                                
                            card_af_html = f"<div style='background:#fff; border:1px solid #dce7e2; border-radius:10px; padding:14px 18px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:16px; font-weight:600; color:#103d33;'>{ex_data['name']}</span>{prio_badge}</div>{btn_video}</div>"
                            
                            st.markdown(card_af_html, unsafe_allow_html=True)

        elif sesion_encontrada:
            sesiones_del_pac = [pl for pl in plans if str(pl["patientId"]) == str(sesion_encontrada["patientId"])]
            sesion_actual = sesiones_del_pac[-1] if sesiones_del_pac else None
            
            if sesion_actual and str(sesion_actual["id"]) != str(sesion_encontrada["id"]):
                st.markdown("<div style='background:#fdecec; color:#aa3838; padding:11px 13px; border-radius:9px; text-align:center;'>⚠️ Esta sesión es antigua y ya no está disponible. Por favor, pídele a tu fisioterapeuta el PIN de tu nueva sesión.</div>", unsafe_allow_html=True)
            else:
                banner_html = f"""
                <div style='background:#e9f6f0; border: 1px solid #dce7e2; border-radius:16px; padding:25px; margin: 10px 0px 35px 0px; text-align:center;'>
                    <span style='color:#13765d; font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:1px;'>TU SESIÓN DE HOY</span>
                    <h2 style='color:#103d33 !important; font-size:32px; font-weight:800; margin:10px 0px 5px 0px; line-height:1.2;'>{sesion_encontrada['title']}</h2>
                </div>
                """
                st.markdown(banner_html, unsafe_allow_html=True)

                if not sesion_encontrada["exerciseIds"]:
                    st.info("No hay ejercicios para esta sesión.")
                
                st.markdown("<h3 style='margin-bottom:20px; font-size:22px; color:#103d33 !important;'>🎥 Lista de Ejercicios</h3>", unsafe_allow_html=True)
                
                # RECORRIDO CON ENUMERATE PARA SACAR EL ÍNDICE (1, 2, 3...)
                for idx, ex_id in enumerate(sesion_encontrada["exerciseIds"]):
                    ex_data = get_exercise(ex_id)
                    inst_data = sesion_encontrada["exerciseInstructions"].get(ex_id, {})
                    
                    if ex_data:
                        series = inst_data.get("series", "-")
                        reps = inst_data.get("reps", "-")
                        notes = inst_data.get("notes", "")
                        
                        vid_url = ex_data.get("videoUrl", "").strip()
                        btn_video_ses = f"<a href='{vid_url}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:10px 18px; border-radius:8px; font-weight:bold; font-size:14px; text-align:center;'>▶ Ver Vídeo</a>" if vid_url else ""

                        # NUEVA ESTRUCTURA HTML SEGÚN TUS INDICACIONES
                        card_html = f"""
                        <div style='background:#fff; border:1px solid #dce7e2; border-radius:12px; padding:20px; margin-bottom:15px; box-shadow:0px 4px 15px rgba(0,0,0,0.02);'>
                            <div style='margin-bottom:15px;'>
                                <h4 style='margin:0; font-size:18px; color:#103d33 !important;'>{idx + 1}. {ex_data['name']}</h4>
                            </div>
                            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #f0f4f2; padding-bottom:15px;'>
                                <div>{btn_video_ses}</div>
                                <div><span style='background:#e9f6f0; color:#13765d; padding:4px 8px; border-radius:5px; font-size:12px; font-weight:600;'>{ex_data['category']}</span></div>
                            </div>
                            <div style='display:flex; gap:20px;'>
                                <div style='background:#f6f8f6; padding:10px 15px; border-radius:8px; flex:1;'>
                                    <span style='color:#64756e; font-size:12px; text-transform:uppercase;'>Series</span><br>
                                    <span style='font-size:18px; font-weight:bold; color:#103d33;'>{series}</span>
                                </div>
                                <div style='background:#f6f8f6; padding:10px 15px; border-radius:8px; flex:1;'>
                                    <span style='color:#64756e; font-size:12px; text-transform:uppercase;'>Repeticiones</span><br>
                                    <span style='font-size:18px; font-weight:bold; color:#103d33;'>{reps}</span>
                                </div>
                            </div>
                        """
                        if notes:
                            card_html += f"<div style='margin-top:15px; background:#fff8e1; border-left:4px solid #fbc02d; padding:10px; border-radius:0 8px 8px 0; color:#103d33; font-size:14px;'>💡 {notes}</div>"
                        card_html += "</div>"
                        
                        st.markdown(card_html, unsafe_allow_html=True)
                
                st.divider()
                st.markdown("<h3 style='margin-top:20px; color:#103d33 !important;'>✅ Terminar Sesión</h3>", unsafe_allow_html=True)
                st.write("¿Cómo ha ido? Por favor, reporta la intensidad para tu fisioterapeuta.")
                with st.form(f"checkin_form_{sesion_encontrada['id']}"):
                    eva = st.slider("Dolor (EVA): 0 (Nada) a 10 (Máximo)", 0, 10, 0)
                    borg = st.slider("Fatiga (Borg): 0 (Reposo) a 10 (Extenuante)", 0, 10, 0)
                    comentarios = st.text_area("¿Alguna molestia o comentario? (Opcional)")
                    
                    if st.form_submit_button("Enviar Reporte a mi Fisio", type="primary"):
                        save_checkin_item(sesion_encontrada["id"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), eva, borg, comentarios)
                        st.success("¡Enviado con éxito! Tu fisio ya puede verlo.")
        else:
            st.error("PIN incorrecto o no encontrado.")
            if st.button("Intentar de nuevo"):
                st.session_state.logged_pin = None
                st.rerun()
