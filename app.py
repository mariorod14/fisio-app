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
# CONEXIÓN OPTIMIZADA
# =============================================================
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_conn()

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
    /* Ajustes para el menú lateral */
    section[data-testid="stSidebar"] { background-color: white; border-right: 1px solid var(--line); }
    .stRadio p { font-size: 16px !important; font-weight: 500 !important; }
</style>
"""
st.markdown(estilo_css, unsafe_allow_html=True)

# Estado de sesión
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False
if 'logged_pin' not in st.session_state:
    st.session_state.logged_pin = None

# =============================================================
# URL DIRECTA DE LA HOJA DE CÁLCULO
# =============================================================
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
        return []

def save_patients(patients_list):
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
        return []

def save_exercises(exercises_list):
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
                try:
                    ex_ids = json.loads(ex_ids_raw)
                    ex_ids = [clean_str(x) for x in ex_ids]
                except: ex_ids = []
            else: ex_ids = []

            inst_raw = r.get("exerciseInstructions", "{}")
            if isinstance(inst_raw, str) and inst_raw.startswith("{"):
                try:
                    insts = json.loads(inst_raw)
                    cleaned_insts = {clean_str(k): v for k, v in insts.items()}
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
        return []

def save_plans(plans_list):
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
        return []

def save_programs_af(programs_list):
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
        return []

def save_checkin_item(plan_id, date, eva, borg, comment):
    checkins = get_checkins()
    checkins.append({"id": str(uuid.uuid4())[:4], "planId": str(plan_id), "date": str(date), "eva": str(eva), "borg": str(borg), "comment": str(comment)})
    conn.update(spreadsheet=SHEET_URL, worksheet="checkins", data=pd.DataFrame(checkins))
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
    
    st.sidebar.markdown("<h2 style='color:#13765d !important;'>🩺 FisioSesión</h2>", unsafe_allow_html=True)
    
    # NAVEGACIÓN LATERAL
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
    # VISTA 1: ARCHIVO (PACIENTES Y EJERCICIOS)
    # -------------------------------------------------------------
    if menu_seleccion == "📁 Archivo":
        st.markdown("<h1>📁 Base de Datos y Archivo</h1>", unsafe_allow_html=True)
        tab_pac, tab_ej = st.tabs(["👥 Pacientes", "🎥 Ejercicios"])
        
        # --- PESTAÑA PACIENTES ---
        with tab_pac:
            with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
                with st.form("nuevo_paciente_form", clear_on_submit=True):
                    c_np1, c_np2 = st.columns([3, 1])
                    new_p_name = c_np1.text_input("Nombre completo:")
                    new_p_phone = c_np2.text_input("Teléfono:")
                    
                    new_p_ana = st.text_area("Anamnesis (preguntas, historia...):")
                    new_p_ins = st.text_area("Inspección física (coloración, palpación, inspección visual...):")
                    new_p_mov = st.text_area("Movilidad activa y pasiva:")
                    new_p_fue = st.text_area("Fuerza:")
                    
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
                            st.write(f"- 🏋️ {pr['title']} (PIN: {pr['pin']})")

                    if not sesiones_del_paciente and not progs_del_paciente:
                        st.write("No tiene planes ni programas asignados todavía.")

                    st.divider()
                    st.markdown("#### ⚙️ Datos Clínicos del Paciente")
                    
                    ce1, ce2 = st.columns([3, 1])
                    edit_name = ce1.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                    edit_phone = ce2.text_input("Teléfono", value=p.get("phone", ""), key=f"phone_{p['id']}")
                    
                    edit_ana = st.text_area("Anamnesis", value=p.get("anamnesis", ""), key=f"ana_{p['id']}")
                    edit_ins = st.text_area("Inspección física", value=p.get("inspeccion", ""), key=f"ins_{p['id']}")
                    edit_mov = st.text_area("Movilidad activa y pasiva", value=p.get("movilidad", ""), key=f"mov_{p['id']}")
                    edit_fue = st.text_area("Fuerza", value=p.get("fuerza", ""), key=f"fue_{p['id']}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("💾 Actualizar Datos", key=f"upd_{p['id']}", type="primary"):
                        p["name"] = edit_name; p["phone"] = edit_phone
                        p["anamnesis"] = edit_ana; p["inspeccion"] = edit_ins
                        p["movilidad"] = edit_mov; p["fuerza"] = edit_fue
                        save_patients(patients); st.rerun()
                    if c2.button("🗑️ Borrar Paciente", key=f"del_{p['id']}"):
                        patients = [x for x in patients if str(x["id"]) != str(p["id"])]
                        save_patients(patients); st.rerun()

        # --- PESTAÑA EJERCICIOS ---
        with tab_ej:
            total_ej = len(exercises)
            st.markdown(f"<h3 style='margin-top:10px;'>🎥 Base de Datos de Ejercicios (Total: {total_ej})</h3>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:14px; color:var(--muted); margin-top:-10px;'>💡 Añade un nuevo ejercicio arriba, o edita directamente en los recuadros de cada línea. Pulsa <b>Guardar Todos los Cambios</b> abajo del todo al terminar.</p>", unsafe_allow_html=True)

            with st.form("form_editar_ejercicios"):
                st.markdown("<div style='color:var(--green); font-weight:bold; font-size:16px; margin: 0 0 10px 0;'>➕ AÑADIR NUEVO EJERCICIO</div>", unsafe_allow_html=True)
                cn1, cn2, cn3, cn4 = st.columns([4, 4, 3, 1])
                with cn1:
                    new_n = st.text_input("new_n", placeholder="Nombre del ejercicio...", label_visibility="collapsed")
                with cn2:
                    new_u = st.text_input("new_u", placeholder="Enlace de YouTube...", label_visibility="collapsed")
                with cn3:
                    new_c = st.selectbox("new_c", CATEGORIAS_EJ, label_visibility="collapsed")
                
                st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
                
                nuevos_datos = {}
                ids_borrar = []
                
                c_h1, c_h2, c_h3, c_h4 = st.columns([4, 4, 3, 1])
                c_h1.caption("NOMBRE")
                c_h2.caption("ENLACE YOUTUBE")
                c_h3.caption("CATEGORÍA")
                c_h4.caption("BORRAR")
                
                for cat in CATEGORIAS_EJ:
                    ej_cat = [e for e in exercises if e.get("category") == cat]
                    ej_cat = sorted(ej_cat, key=lambda x: x["name"].lower())
                    
                    if ej_cat:
                        st.markdown(f"<div style='color:var(--dark); font-weight:bold; font-size:16px; margin: 15px 0 5px 0; border-bottom: 1px solid var(--line);'>{cat} (Total: {len(ej_cat)})</div>", unsafe_allow_html=True)
                        for e in ej_cat:
                            eid = e["id"]
                            c1, c2, c3, c4 = st.columns([4, 4, 3, 1])
                            with c1:
                                n = st.text_input("n", value=e["name"], key=f"n_{eid}", label_visibility="collapsed")
                            with c2:
                                u = st.text_input("u", value=e["videoUrl"], key=f"u_{eid}", label_visibility="collapsed")
                            with c3:
                                idx = CATEGORIAS_EJ.index(e["category"]) if e["category"] in CATEGORIAS_EJ else 0
                                c = st.selectbox("c", CATEGORIAS_EJ, index=idx, key=f"c_{eid}", label_visibility="collapsed")
                            with c4:
                                b = st.checkbox("🗑️", key=f"del_{eid}")
                                
                            nuevos_datos[eid] = {"id": eid, "name": n, "videoUrl": u, "category": c}
                            if b: ids_borrar.append(eid)
                            
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True):
                    lista_final = []
                    for e in exercises:
                        eid = e["id"]
                        if eid not in ids_borrar:
                            lista_final.append(nuevos_datos[eid])
                    
                    if new_n.strip():
                        lista_final.append({
                            "id": str(uuid.uuid4())[:4],
                            "name": new_n.strip(),
                            "videoUrl": new_u.strip(),
                            "category": new_c
                        })
                        
                    save_exercises(lista_final)
                    st.success("¡Base de datos de ejercicios actualizada!")
                    st.rerun()

    # -------------------------------------------------------------
    # VISTA 2: SESIONES CLÍNICAS (MÁS CHECK-INS)
    # -------------------------------------------------------------
    elif menu_seleccion == "🩺 Sesiones":
        st.markdown("<h1>🩺 Sesiones Clínicas</h1>", unsafe_allow_html=True)
        tab_ses_act, tab_checkins, tab_crear_ses = st.tabs(["⚙️ Sesiones Actuales", "📊 Check-ins", "📝 Crear Nueva Sesión"])
        
        # --- PESTAÑA: SESIONES ACTUALES ---
        with tab_ses_act:
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

                        c1, c2 = st.columns([3, 1])
                        with c1:
                            ed_tit = st.text_input("Cambiar Título:", value=pl["title"], key=f"tit_{pl['id']}")
                            if st.button("💾 Guardar Título", key=f"sav_{pl['id']}", type="primary"):
                                pl["title"] = ed_tit; save_plans(plans); st.rerun()
                        with c2:
                            st.write(""); st.write("")
                            if st.button("🗑️ Eliminar", key=f"del_{pl['id']}"):
                                plans = [x for x in plans if str(x["id"]) != str(pl["id"])]
                                save_plans(plans); st.rerun()

        # --- PESTAÑA: CHECK-INS ---
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

        # --- PESTAÑA: CREAR SESIÓN ---
        with tab_crear_ses:
            if not patients:
                st.warning("Añade pacientes en el apartado 'Archivo' primero.")
            else:
                paciente_sel = st.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
                titulo_sesion = st.text_input("2. Título de la Sesión:")
                
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
                if st.session_state.orden_ejs:
                    st.markdown("**4. Configuración y Orden:**")
                    st.caption("Usa las flechas (⬆️/⬇️) para cambiar el orden en el que le saldrán al paciente.")
                    
                    c_th, c_sh, c_rh, c_nh, c_x1, c_x2 = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                    c_th.caption("EJERCICIO")
                    c_sh.caption("SERIES")
                    c_rh.caption("REPS")
                    c_nh.caption("NOTAS EXTRA")
                    
                    for idx, e_id in enumerate(st.session_state.orden_ejs):
                        ej_obj = get_exercise(e_id)
                        ej_name = ej_obj['name'] if ej_obj else "Ejercicio"
                        col_t, col_s, col_r, col_n, col_up, col_dn = st.columns([4, 1.5, 1.5, 2.5, 0.6, 0.6])
                        
                        with col_t:
                            st.markdown(f"<div style='margin-top:8px; font-weight:bold; font-size:14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{idx + 1}. {ej_name}</div>", unsafe_allow_html=True)
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
                        
                if st.button("💾 Generar Sesión", type="primary"):
                    if titulo_sesion and st.session_state.orden_ejs:
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
                    elif not st.session_state.orden_ejs:
                        st.warning("Debes seleccionar al menos un ejercicio.")

    # -------------------------------------------------------------
    # VISTA 3: PROGRAMAS DE AF
    # -------------------------------------------------------------
    elif menu_seleccion == "🏋️ Programas de AF":
        st.markdown("<h1>🏋️ Programas de Actividad Física</h1>", unsafe_allow_html=True)
        tab_gest_af, tab_crear_af = st.tabs(["⚙️ Programas Activos", "📝 Crear Nuevo Programa AF"])
        
        # --- PESTAÑA: PROGRAMAS ACTIVOS ---
        with tab_gest_af:
            st.markdown("<h3 style='margin-top:10px;'>Programas de Fuerza y AF Activos</h3>", unsafe_allow_html=True)
            if not programs_af:
                st.info("No hay programas de AF creados todavía.")
            else:
                for pr in reversed(programs_af):
                    with st.container(border=True):
                        st.markdown(f"#### 🏋️ {pr['title']}")
                        st.markdown(f"<span style='background:#e9f6f0; color:#13765d; padding:7px 10px; border-radius:7px; font-size:12px; font-weight:bold;'>PIN: {pr['pin']}</span>", unsafe_allow_html=True)
                        st.write(f"👤 **Paciente:** {get_patient_name(pr['patientId'])}")
                        st.write(f"⏱️ **Frecuencia:** {pr['frequency']} | **Duración:** {pr['duration']}")
                        
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            mensaje_wa = f"¡Hola {get_patient_name(pr['patientId'])}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{pr['title']}*.\n\n📱 Accede directamente desde aquí:\n{APP_URL}\n\n🔑 Tu código PIN de acceso es: {pr['pin']}\n\n¡A entrenar!"
                            st.text_area("Mensaje de WhatsApp para el paciente:", value=mensaje_wa, height=100, key=f"wa_{pr['id']}")
                        with c2:
                            st.write(""); st.write("")
                            if st.button("🗑️ Eliminar Programa", key=f"del_af_{pr['id']}"):
                                programs_af = [x for x in programs_af if str(x["id"]) != str(pr["id"])]
                                save_programs_af(programs_af)
                                st.rerun()

        # --- PESTAÑA: CREAR NUEVO PROGRAMA AF ---
        with tab_crear_af:
            if not patients:
                st.warning("Añade pacientes en el apartado 'Archivo' primero.")
            else:
                st.markdown("### 📝 Diseñador de Programa Semanal de AF")
                
                col_p, col_t = st.columns([1, 2])
                af_paciente = col_p.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name, key="af_pac")
                af_titulo = col_t.text_input("2. Título del programa:", placeholder="Ej: Trabajo de fuerza ANA")
                
                col_f, col_d = st.columns(2)
                af_frecuencia = col_f.text_input("3. Frecuencia semanal:", placeholder="Ej: 3 días a la semana")
                af_duracion = col_d.text_input("4. Duración por sesión:", placeholder="Ej: 20-30 minutos al día")
                
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

                for d_idx in range(st.session_state.num_dias):
                    st.markdown(f"<div style='background:#f6f8f6; padding:15px; border-radius:12px; border:1px solid #dce7e2; margin-top:15px;'><h4 style='color:#13765d !important; margin:0;'>DÍA {d_idx + 1}</h4></div>", unsafe_allow_html=True)
                    
                    d_titulo = st.text_input(f"Título del Día {d_idx + 1}:", value=f"DÍA {d_idx + 1}: extremidad superior + CORE" if d_idx==0 else f"DÍA {d_idx + 1}", key=f"dtit_{d_idx}")
                    
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
                            
                            # Filtrar ejercicios EXCLUSIVAMENTE de la categoría elegida
                            ej_cat_filtrados = sorted([e for e in exercises if e.get("category") == b_cat], key=lambda x: x["name"].lower())
                            ej_options_block = {e["name"]: e["id"] for e in ej_cat_filtrados}
                            
                            b_selected_names = st.multiselect(
                                f"Ejercicios de {b_cat}:", 
                                options=list(ej_options_block.keys()), 
                                key=f"bejs_{d_idx}_{b_idx}",
                                placeholder=f"Selecciona ejercicios de {b_cat}..."
                            )
                            
                            # Gestión de orden dinámico con botones ⬆️ / ⬇️
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
                                    
                                    col_e_name, col_e_prio, col_e_up, col_e_dn = st.columns([4, 2, 0.6, 0.6])
                                    with col_e_name:
                                        st.markdown(f"<div style='margin-top:6px; font-weight:bold;'>{idx_e + 1}. {ename}</div>", unsafe_allow_html=True)
                                    with col_e_prio:
                                        es_prio = st.checkbox("⭐ Prioritario", key=f"prio_{d_idx}_{b_idx}_{eid}")
                                    with col_e_up:
                                        if st.button("⬆️", key=f"up_{d_idx}_{b_idx}_{eid}"):
                                            if idx_e > 0:
                                                st.session_state[key_order_af][idx_e-1], st.session_state[key_order_af][idx_e] = st.session_state[key_order_af][idx_e], st.session_state[key_order_af][idx_e-1]
                                                st.rerun()
                                    with col_e_dn:
                                        if st.button("⬇️", key=f"dn_{d_idx}_{b_idx}_{eid}"):
                                            if idx_e < len(st.session_state[key_order_af]) - 1:
                                                st.session_state[key_order_af][idx_e+1], st.session_state[key_order_af][idx_e] = st.session_state[key_order_af][idx_e], st.session_state[key_order_af][idx_e+1]
                                                st.rerun()

                                    ejs_bloque_info.append({"exerciseId": eid, "isPriority": es_prio})

                            bloques_dia.append({
                                "blockTitle": b_nombre_completo,
                                "exercises": ejs_bloque_info
                            })

                    dias_construidos.append({
                        "dayTitle": d_titulo,
                        "blocks": bloques_dia
                    })

                st.divider()
                if st.button("💾 Guardar y Crear Programa de AF", type="primary", use_container_width=True):
                    if af_titulo and dias_construidos:
                        nuevo_pin_af = str(random.randint(100000, 999999))
                        programs_af.append({
                            "id": str(uuid.uuid4())[:4],
                            "patientId": af_paciente,
                            "title": af_titulo,
                            "frequency": af_frecuencia,
                            "duration": af_duracion,
                            "generalNote": af_nota_gen,
                            "pin": nuevo_pin_af,
                            "daysData": dias_construidos
                        })
                        save_programs_af(programs_af)
                        st.success("¡Programa de AF creado con éxito!")
                        
                        nombre_p = get_patient_name(af_paciente)
                        mensaje_wa_gen = f"¡Hola {nombre_p}! 👋\n\nAquí tienes tu programa de entrenamiento de fuerza: *{af_titulo}*.\n\n📱 Accede directamente desde tu móvil:\n{APP_URL}\n\n🔑 Tu PIN de acceso es: {nuevo_pin_af}\n\n¡A por todas!"
                        st.info("Copia el mensaje para mandarlo por WhatsApp:")
                        st.code(mensaje_wa_gen, language="markdown")

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE / FORMULARIO LOGIN
# =============================================================
else:
    # SI NO SE HA INICIADO SESIÓN -> PANTALLA DE ACCESO
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

    # SI YA SE HA INICIADO SESIÓN -> SE OCULTA EL FORMULARIO Y SE MUESTRA EL CONTENIDO DIRECTAMENTE
    else:
        pin_ingresado = st.session_state.logged_pin
        
        # Buscar en Sesiones Clínicas Tradicionales
        sesion_encontrada = next((p for p in plans if str(p["pin"]) == str(pin_ingresado)), None)
        # Buscar en Programas de AF
        programa_af_encontrado = next((pr for pr in programs_af if str(pr["pin"]) == str(pin_ingresado)), None)
        
        # Botón sutil para salir si se equivocó de PIN
        col_exit1, col_exit2 = st.columns([4, 1])
        with col_exit2:
            if st.button("🚪 Cambiar PIN", key="exit_pin_btn"):
                st.session_state.logged_pin = None
                st.rerun()

        # --- VISTA PROGRAMA DE AF ---
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
                    st.markdown(f"<h4 style='color:#13765d !important; margin: 15px 0 10px 0;'>📌 {block['blockTitle']}</h4>", unsafe_allow_html=True)
                    
                    for item in block['exercises']:
                        ex_data = get_exercise(item['exerciseId'])
                        if ex_data:
                            prio_badge = "<span style='background:#fff3cd; color:#856404; padding:3px 8px; border-radius:5px; font-size:12px; font-weight:bold; margin-left:8px;'>⭐ Prioritario</span>" if item.get('isPriority') else ""
                            
                            # Todo el HTML comprimido para que el Markdown de Streamlit no se rompa con espacios vacíos
                            card_af_html = f"<div style='background:#fff; border:1px solid #dce7e2; border-radius:10px; padding:14px 18px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:16px; font-weight:600; color:#103d33;'>{ex_data['name']}</span>{prio_badge}</div><a href='{ex_data['videoUrl']}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:8px 14px; border-radius:7px; font-weight:bold; font-size:13px;'>▶ Ver Vídeo</a></div>"
                            
                            st.markdown(card_af_html, unsafe_allow_html=True)

        # --- VISTA SESIÓN CLÍNICA TRADICIONAL ---
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
                
                for ex_id in sesion_encontrada["exerciseIds"]:
                    ex_data = get_exercise(ex_id)
                    inst_data = sesion_encontrada["exerciseInstructions"].get(ex_id, {})
                    
                    if ex_data:
                        series = inst_data.get("series", "-")
                        reps = inst_data.get("reps", "-")
                        notes = inst_data.get("notes", "")

                        card_html = f"""
                        <div style='background:#fff; border:1px solid #dce7e2; border-radius:12px; padding:20px; margin-bottom:15px; box-shadow:0px 4px 15px rgba(0,0,0,0.02);'>
                            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #f0f4f2; padding-bottom:15px;'>
                                <div>
                                    <h4 style='margin:0 0 5px 0; font-size:18px; color:#103d33 !important;'>{ex_data['name']}</h4>
                                    <span style='background:#e9f6f0; color:#13765d; padding:4px 8px; border-radius:5px; font-size:12px; font-weight:600;'>{ex_data['category']}</span>
                                </div>
                                <a href='{ex_data['videoUrl']}' target='_blank' style='background:#13765d; color:white; text-decoration:none; padding:10px 18px; border-radius:8px; font-weight:bold; font-size:14px; text-align:center;'>▶ Ver Vídeo</a>
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
