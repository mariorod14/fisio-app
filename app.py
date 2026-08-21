import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import random
import uuid
import json

# Configuración básica
st.set_page_config(page_title="FisioSesión", layout="wide", initial_sidebar_state="collapsed")

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
    .stTextInput input, .stTextArea textarea, .stMultiSelect div[data-baseweb="select"] { border: 1px solid var(--line) !important; border-radius: 9px !important; }
    [data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 15px !important; }
</style>
"""
st.markdown(estilo_css, unsafe_allow_html=True)

if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False

# =============================================================
# URL DIRECTA DE LA HOJA DE CÁLCULO
# =============================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1aoQuXwdTdY-AdcI6zetr5p2BbgN5gwxhBXbVQLhU0GI/edit"

# =============================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# =============================================================
def get_patients():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="pacientes", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            p_id = str(r.get("id", ""))
            if p_id.endswith(".0"): p_id = p_id[:-2]
            records.append({"id": p_id, "name": str(r.get("name", "")), "notes": str(r.get("notes", ""))})
        return records
    except Exception as e:
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
            e_id = str(r.get("id", ""))
            if e_id.endswith(".0"): e_id = e_id[:-2]
            records.append({"id": e_id, "name": str(r.get("name", "")), "videoUrl": str(r.get("videoUrl", "")), "category": str(r.get("category", ""))})
        return records
    except Exception as e:
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
            p_id = str(r.get("id", ""))
            if p_id.endswith(".0"): p_id = p_id[:-2]
            pat_id = str(r.get("patientId", ""))
            if pat_id.endswith(".0"): pat_id = pat_id[:-2]
            pin_val = str(r.get("pin", ""))
            if pin_val.endswith(".0"): pin_val = pin_val[:-2]
            
            ex_ids_raw = r.get("exerciseIds", "[]")
            if isinstance(ex_ids_raw, str) and ex_ids_raw.startswith("["):
                try:
                    ex_ids = json.loads(ex_ids_raw)
                    ex_ids = [str(x)[:-2] if str(x).endswith(".0") else str(x) for x in ex_ids]
                except:
                    ex_ids = []
            else:
                ex_ids = []

            inst_raw = r.get("exerciseInstructions", "{}")
            if isinstance(inst_raw, str) and inst_raw.startswith("{"):
                try:
                    insts = json.loads(inst_raw)
                    cleaned_insts = {}
                    for k, v in insts.items():
                        clean_k = str(k)[:-2] if str(k).endswith(".0") else str(k)
                        cleaned_insts[clean_k] = v
                    insts = cleaned_insts
                except:
                    insts = {}
            else:
                insts = {}

            plans.append({
                "id": p_id, 
                "patientId": pat_id, 
                "title": str(r.get("title", "")),
                "exerciseIds": ex_ids, 
                "exerciseInstructions": insts,
                "pin": pin_val
            })
        return plans
    except Exception as e:
        return []

def save_plans(plans_list):
    formatted = []
    for p in plans_list:
        formatted.append({
            "id": str(p["id"]), 
            "patientId": str(p["patientId"]), 
            "title": str(p["title"]),
            "exerciseIds": json.dumps(p["exerciseIds"]), 
            "exerciseInstructions": json.dumps(p["exerciseInstructions"]),
            "pin": str(p["pin"])
        })
    conn.update(spreadsheet=SHEET_URL, worksheet="sesiones", data=pd.DataFrame(formatted))
    st.cache_data.clear()

def get_checkins():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="checkins", ttl=600)
        if df.empty: return []
        df = df.dropna(how="all")
        records = []
        for _, r in df.iterrows():
            c_id = str(r.get("id", ""))
            if c_id.endswith(".0"): c_id = c_id[:-2]
            p_id = str(r.get("planId", ""))
            if p_id.endswith(".0"): p_id = p_id[:-2]
            records.append({"id": c_id, "planId": p_id, "date": str(r.get("date", "")), "eva": str(r.get("eva", "")), "borg": str(r.get("borg", "")), "comment": str(r.get("comment", ""))})
        return records
    except Exception as e:
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
    if st.sidebar.button("🔒 Cerrar Sesión Segura", type="primary"):
        st.session_state.admin_mode = False
        st.rerun()

    st.markdown("<h1>Panel de Control Clínico</h1>", unsafe_allow_html=True)
    
    tab_pac, tab_ej, tab_pau, tab_res = st.tabs(["👥 Pacientes", "🎥 Ejercicios", "📁 Sesiones", "📊 Check-ins"])
    
    # --- PESTAÑA PACIENTES ---
    with tab_pac:
        with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
            with st.form("nuevo_paciente_form", clear_on_submit=True):
                new_p_name = st.text_input("Nombre completo:")
                new_p_notes = st.text_area("Notas clínicas:")
                if st.form_submit_button("Guardar Paciente Nuevo", type="primary"):
                    if new_p_name:
                        patients.append({"id": str(uuid.uuid4())[:4], "name": new_p_name, "notes": new_p_notes})
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
            with st.expander(f"👤 {p['name']}"):
                st.markdown("#### 📋 Sesiones Asignadas")
                sesiones_del_paciente = [pl for pl in plans if str(pl["patientId"]) == str(p["id"])]
                
                if sesiones_del_paciente:
                    sesion_actual = sesiones_del_paciente[-1]
                    historial = sesiones_del_paciente[:-1]
                    
                    st.markdown("<div style='background:#eaf7f0; color:#13765d; padding:11px; border-radius:9px; margin-bottom:10px;'><b>🟢 Sesión Actual</b></div>", unsafe_allow_html=True)
                    st.write(f"- **{sesion_actual['title']}** (PIN: {sesion_actual['pin']})")
                    
                    if historial:
                        st.markdown("<div style='background:#f6f8f6; color:#64756e; padding:11px; border-radius:9px; margin-top:10px; margin-bottom:10px;'><b>⚪ Historial (Antiguas)</b></div>", unsafe_allow_html=True)
                        for pi in reversed(historial): 
                            nombres_ejercicios = []
                            for eid in pi['exerciseIds']:
                                ej_data = get_exercise(eid)
                                if ej_data: nombres_ejercicios.append(ej_data['name'])
                            
                            ejs_str = ", ".join(nombres_ejercicios) if nombres_ejercicios else "Sin ejercicios"
                            st.write(f"- **{pi['title']}** *(Ejercicios: {ejs_str})*")
                else:
                    st.write("No tiene ninguna sesión todavía.")

                st.divider()
                st.markdown("#### ⚙️ Ajustes del Paciente")
                edit_name = st.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                edit_notes = st.text_area("Notas clínicas", value=p["notes"], key=f"notes_{p['id']}")
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Actualizar", key=f"upd_{p['id']}", type="primary"):
                    p["name"] = edit_name; p["notes"] = edit_notes; save_patients(patients); st.rerun()
                if c2.button("🗑️ Borrar", key=f"del_{p['id']}"):
                    patients = [x for x in patients if str(x["id"]) != str(p["id"])]
                    save_patients(patients); st.rerun()

    # --- PESTAÑA EJERCICIOS (NUEVA VERSIÓN TABLA COMPACTA) ---
    with tab_ej:
        st.markdown("<h3 style='margin-top:10px;'>🎥 Base de Datos de Ejercicios</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:14px; color:var(--muted); margin-top:-10px;'>💡 <b>Doble clic en cualquier celda</b> para editar el nombre, enlace o categoría. <br>Para crear un nuevo ejercicio, haz doble clic en la última fila vacía de abajo. Para borrar, selecciona la parte izquierda de la fila y pulsa la tecla Suprimir.</p>", unsafe_allow_html=True)

        df_ex = pd.DataFrame(exercises)
        if df_ex.empty:
            df_ex = pd.DataFrame(columns=["id", "name", "videoUrl", "category"])
        else:
            # Forzamos el orden de las columnas: id, name, videoUrl, category
            df_ex = df_ex[["id", "name", "videoUrl", "category"]]

        # Mostrar tabla editable (súper compacta)
        edited_df = st.data_editor(
            df_ex,
            column_config={
                "id": None, # Ocultamos el ID interno al usuario
                "name": st.column_config.TextColumn("Nombre del Ejercicio", required=True, width="medium"),
                "videoUrl": st.column_config.TextColumn("Enlace de YouTube", required=True, width="large"),
                "category": st.column_config.SelectboxColumn("Categoría", options=["CORE", "EEII", "EESS", "Estiramientos y movilidad"], required=True, width="small")
            },
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_ejercicios_v1"
        )
        
        # Lógica para detectar cambios y guardar
        df_ex_str = df_ex.fillna("").astype(str)
        edited_df_str = edited_df.fillna("").astype(str)
        
        if not df_ex_str.equals(edited_df_str):
            st.markdown("<div style='background:#fff3cd; color:#856404; padding:10px; border-radius:8px; margin-bottom:10px;'>⚠️ <b>Tienes cambios sin guardar.</b> Pulsa el botón de abajo para confirmarlos.</div>", unsafe_allow_html=True)
            if st.button("💾 Guardar Cambios en Ejercicios", type="primary"):
                nuevos_ejercicios = []
                for _, r in edited_df.iterrows():
                    eid = r.get("id")
                    if not eid or pd.isna(eid) or eid == "":
                        eid = str(uuid.uuid4())[:4]
                    
                    # Solo guardamos filas que tengan al menos nombre o URL
                    if str(r.get("name", "")) != "nan" or str(r.get("videoUrl", "")) != "nan":
                        nuevos_ejercicios.append({
                            "id": str(eid),
                            "name": str(r.get("name", "")).replace("nan", ""),
                            "videoUrl": str(r.get("videoUrl", "")).replace("nan", ""),
                            "category": str(r.get("category", "")).replace("nan", "")
                        })
                save_exercises(nuevos_ejercicios)
                st.success("¡Base de datos de ejercicios actualizada!")
                st.rerun()

    # --- PESTAÑA SESIONES ---
    with tab_pau:
        sub_gestionar, sub_crear = st.tabs(["⚙️ Sesiones Actuales", "📝 Crear Nueva Sesión"])
        
        with sub_gestionar:
            search_query = st.text_input("🔍 Buscar sesión por título o nombre del paciente:")
            
            sesiones_actuales = {}
            for pl in plans:
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
                                
        with sub_crear:
            if not patients:
                st.warning("Añade pacientes primero.")
            else:
                paciente_sel = st.selectbox("1. Paciente:", options=[p["id"] for p in patients], format_func=get_patient_name)
                titulo_sesion = st.text_input("2. Título de la Sesión:")
                
                # --- NUEVA SELECCIÓN Y ORDENACIÓN DE EJERCICIOS ---
                st.markdown("**3. Selecciona y ordena los ejercicios:**")
                st.markdown("<p style='font-size: 13px; color: var(--muted); margin-top:-10px;'>Haz clic para buscarlos y añadirlos. <b>Aparecerán en el orden en que los cliques</b>. Puedes arrastrar las etiquetas grises para reordenarlos.</p>", unsafe_allow_html=True)
                
                # Preparamos las opciones con un formato bonito: "Nombre (Categoría)"
                ej_options = {f"{e['name']}  ({e['category']})": e['id'] for e in exercises}
                
                selected_names = st.multiselect(
                    "Buscador de ejercicios",
                    options=list(ej_options.keys()),
                    label_visibility="collapsed",
                    placeholder="Escribe aquí o selecciona de la lista..."
                )
                
                # Recuperamos los IDs basándonos en los nombres seleccionados, RESPETANDO EL ORDEN del multiselect
                ejercicios_sel = [ej_options[name] for name in selected_names]
                
                instrucciones_dict = {}
                if ejercicios_sel:
                    st.markdown("**4. Configuración (El orden mostrado es el que verá el paciente):**")
                    # Iteramos respetando el orden elegido por el fisio
                    for idx, e_id in enumerate(ejercicios_sel):
                        ej_name = get_exercise(e_id)['name']
                        # Mostramos el número de orden delante del nombre
                        st.markdown(f"**{idx + 1}. {ej_name}**") 
                        col_s, col_r, col_n = st.columns([1, 1, 2])
                        with col_s:
                            s = st.text_input("Series", key=f"ser_{e_id}", placeholder="Ej: 3")
                        with col_r:
                            r = st.text_input("Reps", key=f"rep_{e_id}", placeholder="Ej: 10")
                        with col_n:
                            n = st.text_input("Notas extra", key=f"not_{e_id}", placeholder="Ej: banda elástica")
                        
                        instrucciones_dict[e_id] = {"series": s, "reps": r, "notes": n}
                        
                if st.button("💾 Generar Sesión", type="primary"):
                    if titulo_sesion and ejercicios_sel:
                        nuevo_pin = str(random.randint(100000, 999999))
                        plans.append({
                            "id": str(uuid.uuid4())[:4], "patientId": paciente_sel, "title": titulo_sesion,
                            "exerciseIds": ejercicios_sel, "exerciseInstructions": instrucciones_dict,
                            "pin": nuevo_pin
                        })
                        save_plans(plans)
                        st.success("¡Sesión guardada! Las sesiones antiguas de este paciente han pasado al historial.")
                        
                        nombre_paciente = get_patient_name(paciente_sel)
                        mensaje_whatsapp = f"¡Hola {nombre_paciente}! 👋\n\nAquí tienes tu nueva sesión de fisioterapia: *{titulo_sesion}*.\n\n📱 Para ver tus ejercicios y vídeos, entra en este enlace:\n{APP_URL}\n\n🔑 Tu código de acceso (PIN) es: {nuevo_pin}\n\n¡A por ello!"
                        st.info("Copia el mensaje a continuación para enviarlo por WhatsApp:")
                        st.code(mensaje_whatsapp, language="markdown")
                    elif not ejercicios_sel:
                        st.warning("Debes seleccionar al menos un ejercicio.")

    # --- PESTAÑA CHECK-INS ---
    with tab_res:
        st.markdown("<h1>Control de Cargas</h1>", unsafe_allow_html=True)
        if not checkins:
            st.info("Aún no hay reportes registrados por pacientes.")
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

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE
# =============================================================
else:
    st.markdown("<div style='text-align:center; margin-top:40px;'><h1 style='font-size:27px;'>🏋️ Acceso a tu Sesión</h1><p style='color:#64756e;'>Introduce tu código PIN</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pin_input = st.text_input("PIN de acceso", type="password", label_visibility="hidden", placeholder="Ej: 785518")
    
    if pin_input:
        if pin_input == PASSWORD_FISIO:
            st.session_state.admin_mode = True
            st.rerun()
        else:
            sesion_encontrada = next((p for p in plans if str(p["pin"]) == str(pin_input).strip()), None)
            
            if sesion_encontrada:
                sesiones_del_pac = [pl for pl in plans if str(pl["patientId"]) == str(sesion_encontrada["patientId"])]
                sesion_actual = sesiones_del_pac[-1] if sesiones_del_pac else None
                
                if sesion_actual and str(sesion_actual["id"]) != str(sesion_encontrada["id"]):
                    st.markdown("<div style='background:#fdecec; color:#aa3838; padding:11px 13px; border-radius:9px; text-align:center;'>⚠️ Esta sesión es antigua y ya no está disponible. Por favor, pídele a tu fisioterapeuta el PIN de tu nueva sesión.</div>", unsafe_allow_html=True)
                else:
                    banner_html = f"""
                    <div style='background:#e9f6f0; border: 1px solid #dce7e2; border-radius:16px; padding:25px; margin: 25px 0px 35px 0px; text-align:center;'>
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
                col2.error("PIN incorrecto.")
