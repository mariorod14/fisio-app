import streamlit as st
import datetime
import random
import uuid

# Configuración básica
st.set_page_config(page_title="FisioSesión", layout="wide", initial_sidebar_state="collapsed")

# =============================================================
# VARIABLES GLOBALES DE TU CLÍNICA
# =============================================================
PASSWORD_FISIO = "FISIO123"

# PON AQUÍ TU ENLACE REAL DE STREAMLIT (ej: "https://fisiosesion.streamlit.app")
APP_URL = "https://xj2xjmcpyuweucfq3b7axg.streamlit.app/" 

# =============================================================
# INYECCIÓN DE CSS PERSONALIZADO 
# =============================================================
estilo_css = """
<style>
    :root {
        --ink: #17352e;
        --muted: #64756e;
        --green: #13765d;
        --dark: #103d33;
        --mint: #e9f6f0;
        --line: #dce7e2;
        --bg: #f6f8f6;
        --danger: #aa3838;
    }
    .stApp { background-color: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif; }
    h1, h2, h3, h4, p, span, label { color: var(--ink) !important; }
    button[data-testid="baseButton-primary"] { background-color: var(--green) !important; color: white !important; border: none !important; border-radius: 9px !important; font-weight: 700 !important; padding: 11px 14px !important; }
    button[data-testid="baseButton-secondary"] { background-color: var(--mint) !important; color: var(--green) !important; border: none !important; border-radius: 9px !important; font-weight: 700 !important; padding: 11px 14px !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stNumberInput input { border: 1px solid var(--line) !important; border-radius: 9px !important; background-color: #fff !important; color: var(--ink) !important; padding: 11px !important; }
    [data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 15px !important; }
    .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--line); gap: 5px; }
    .stTabs [data-baseweb="tab"] { background: transparent; color: var(--muted) !important; border-radius: 7px 7px 0 0 !important; }
    .stTabs [aria-selected="true"] { background: var(--mint) !important; color: var(--green) !important; font-weight: bold !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 15px !important; padding: 15px !important; }
</style>
"""
st.markdown(estilo_css, unsafe_allow_html=True)

# Control de sesión
if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False

# =============================================================
# BASE DE DATOS SIMULADA
# =============================================================
if 'patients' not in st.session_state:
    st.session_state.patients = [
        {"id": "765d", "name": "Faico Arzoz", "notes": "trabajo de fuerza general 3 dias/semana"},
        {"id": "debc", "name": "Ana Arzoz", "notes": "trabajo de fuerza general 2 dias/semana"},
        {"id": "49a7", "name": "Eduardo Rodriguez", "notes": ""}
    ]

if 'exercises' not in st.session_state:
    st.session_state.exercises = [
        {"id": "fc59", "name": "dead bug", "category": "CORE", "videoUrl": "https://www.youtube.com/watch?v=4XLEnwUr1d8"},
        {"id": "7769", "name": "abd cadera con goma (BIPE)", "category": "EEII", "videoUrl": "https://www.youtube.com/watch?v=wPM8icPu6H8"},
        {"id": "a91f", "name": "plancha lateral + abd cadera", "category": "EEII", "videoUrl": "https://www.youtube.com/watch?v=2TzR3A031E0"},
        {"id": "afca", "name": "flexiones", "category": "EESS", "videoUrl": "https://www.youtube.com/watch?v=IODxDxX7oi4"},
        {"id": "e033", "name": "movilidad de cadera 90-90", "category": "Estiramientos y movilidad", "videoUrl": "https://www.youtube.com/watch?v=2TzR3A031E0"}
    ]

if 'plans' not in st.session_state:
    st.session_state.plans = [
        {
            "id": "fdf8",
            "patientId": "49a7",
            "title": "menisco agosto",
            "exerciseIds": ["7769", "a91f"],
            "exerciseInstructions": {
                "7769": {"series": "3", "reps": "12", "notes": "Goma verde"}, 
                "a91f": {"series": "4", "reps": "8", "notes": "Sin prisa"}
            },
            "pin": "785518",
            "active": True,
            "checkins": []
        }
    ]

def get_patient_name(p_id):
    for p in st.session_state.patients:
        if p["id"] == p_id: return p["name"]
    return "Paciente Eliminado"

def get_exercise(e_id):
    for e in st.session_state.exercises:
        if e["id"] == e_id: return e
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
                        st.session_state.patients.append({"id": str(uuid.uuid4())[:4], "name": new_p_name, "notes": new_p_notes})
                        st.success("¡Paciente añadido correctamente!")

        total_pacs = len(st.session_state.patients)
        st.markdown(f"<h3 style='margin-top:20px;'>Directorio y Perfiles ({total_pacs})</h3>", unsafe_allow_html=True)
        search_pac = st.text_input("🔍 Buscar paciente por nombre:")
        
        pacs_filtrados = st.session_state.patients
        if search_pac:
            q_pac = search_pac.lower()
            pacs_filtrados = [p for p in pacs_filtrados if q_pac in p["name"].lower()]

        if not pacs_filtrados:
            st.info("No se han encontrado pacientes con ese nombre.")
            
        for p in pacs_filtrados:
            with st.expander(f"👤 {p['name']}"):
                st.markdown("#### 📋 Sesiones Asignadas")
                sesiones_del_paciente = [pl for pl in st.session_state.plans if pl["patientId"] == p["id"]]
                sesiones_activas = [pl for pl in sesiones_del_paciente if pl.get("active", True)]
                sesiones_inactivas = [pl for pl in sesiones_del_paciente if not pl.get("active", True)]
                
                if sesiones_activas:
                    st.markdown("<div style='background:#eaf7f0; color:#13765d; padding:11px; border-radius:9px; margin-bottom:10px;'><b>🟢 Sesiones Activas</b></div>", unsafe_allow_html=True)
                    for pa in sesiones_activas:
                        st.write(f"- **{pa['title']}** (PIN: {pa['pin']})")
                else:
                    st.write("No tiene ninguna sesión activa.")

                if sesiones_inactivas:
                    st.markdown("<div style='background:#f6f8f6; color:#64756e; padding:11px; border-radius:9px; margin-top:10px; margin-bottom:10px;'><b>⚪ Historial (Desactivadas)</b></div>", unsafe_allow_html=True)
                    for pi in sesiones_inactivas:
                        st.write(f"- {pi['title']} (PIN: {pi['pin']})")

                st.divider()
                st.markdown("#### ⚙️ Ajustes del Paciente")
                edit_name = st.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                edit_notes = st.text_area("Notas clínicas", value=p["notes"], key=f"notes_{p['id']}")
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Actualizar", key=f"upd_{p['id']}", type="primary"):
                    p["name"] = edit_name; p["notes"] = edit_notes; st.rerun()
                if c2.button("🗑️ Borrar", key=f"del_{p['id']}"):
                    st.session_state.patients.remove(p); st.rerun()

    # --- PESTAÑA EJERCICIOS ---
    with tab_ej:
        with st.expander("➕ Añadir Nuevo Ejercicio", expanded=False):
            with st.form("nuevo_ejercicio_form", clear_on_submit=True):
                new_e_name = st.text_input("Nombre del ejercicio:")
                new_e_cat = st.selectbox("Categoría:", ["CORE", "EEII", "EESS", "Estiramientos y movilidad"])
                new_e_url = st.text_input("URL del Vídeo:")
                submitted_ej = st.form_submit_button("Guardar Ejercicio", type="primary")
                
                if submitted_ej:
                    if new_e_name and new_e_url:
                        st.session_state.exercises.append({"id": str(uuid.uuid4())[:4], "name": new_e_name, "category": new_e_cat, "videoUrl": new_e_url})
                        st.success("¡Ejercicio guardado correctamente!")
                    else:
                        st.error("Rellena el nombre y la URL.")
        
        total_ejs = len(st.session_state.exercises)
        st.markdown(f"<h3 style='margin-top:20px;'>Catálogo de Ejercicios ({total_ejs})</h3>", unsafe_allow_html=True)
        search_ej = st.text_input("🔍 Buscar ejercicio por nombre:")
        
        for cat in ["CORE", "EEII", "EESS", "Estiramientos y movilidad"]:
            ejs_cat = [e for e in st.session_state.exercises if e["category"] == cat]
            
            if search_ej:
                q_ej = search_ej.lower()
                ejs_cat = [e for e in ejs_cat if q_ej in e["name"].lower()]
            
            with st.expander(f"📁 {cat} ({len(ejs_cat)})"):
                if not ejs_cat:
                    st.write("No hay ejercicios que coincidan con la búsqueda en esta categoría.")
                for e in ejs_cat:
                    c1, c2, c3 = st.columns([2.5, 1, 1])
                    c1.write(f"🔹 {e['name']}")
                    c2.markdown(f"[🔗 Ver vídeo]({e['videoUrl']})")
                    with c3:
                        editar_modo = st.toggle("⚙️ Editar", key=f"tgl_{e['id']}")
                    
                    if editar_modo:
                        with st.container(border=True):
                            ed_name = st.text_input("Nombre", value=e["name"], key=f"en_{e['id']}")
                            ed_cat = st.selectbox("Cat", ["CORE", "EEII", "EESS", "Estiramientos y movilidad"], index=["CORE", "EEII", "EESS", "Estiramientos y movilidad"].index(e["category"]), key=f"ec_{e['id']}")
                            ed_url = st.text_input("URL", value=e["videoUrl"], key=f"eu_{e['id']}")
                            bc1, bc2 = st.columns(2)
                            if bc1.button("💾 Actualizar", type="primary", key=f"esv_{e['id']}"):
                                e["name"] = ed_name; e["category"] = ed_cat; e["videoUrl"] = ed_url; st.rerun()
                            if bc2.button("🗑️ Borrar", key=f"edl_{e['id']}"):
                                st.session_state.exercises.remove(e); st.rerun()
                    st.divider()

    # --- PESTAÑA SESIONES ---
    with tab_pau:
        sub_gestionar, sub_crear = st.tabs(["⚙️ Sesiones Creadas", "📝 Crear Nueva Sesión"])
        
        with sub_gestionar:
            search_query = st.text_input("🔍 Buscar sesión por título o nombre del paciente:")
            
            planes_filtrados = list(reversed(st.session_state.plans))
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
                        
                        pl["active"] = st.toggle("Sesión Activa", value=pl.get("active", True), key=f"tgl_{pl['id']}")
                            
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            ed_tit = st.text_input("Cambiar Título:", value=pl["title"], key=f"tit_{pl['id']}")
                            if st.button("💾 Guardar Título", key=f"sav_{pl['id']}", type="primary"):
                                pl["title"] = ed_tit; st.rerun()
                        with c2:
                            st.write(""); st.write("")
                            if st.button("🗑️ Eliminar", key=f"del_{pl['id']}"):
                                st.session_state.plans.remove(pl); st.rerun()
                                
        with sub_crear:
            if not st.session_state.patients:
                st.warning("Añade pacientes primero.")
            else:
                paciente_sel = st.selectbox("1. Paciente:", options=[p["id"] for p in st.session_state.patients], format_func=get_patient_name)
                titulo_sesion = st.text_input("2. Título de la Sesión:")
                
                st.markdown("**3. Selecciona los ejercicios:**")
                ejercicios_sel = []
                for cat in ["CORE", "EEII", "EESS", "Estiramientos y movilidad"]:
                    ejs_cat = [e for e in st.session_state.exercises if e['category'] == cat]
                    if ejs_cat:
                        st.markdown(f"<span style='font-size:11px; padding:5px 7px; background:#e9f6f0; color:#13765d; border-radius:50px; font-weight:bold;'>{cat}</span>", unsafe_allow_html=True)
                        for e in ejs_cat:
                            if st.checkbox(e["name"], key=f"chk_{e['id']}"):
                                ejercicios_sel.append(e["id"])
                
                instrucciones_dict = {}
                if ejercicios_sel:
                    st.markdown("**4. Configuración de Ejercicios:**")
                    for e_id in ejercicios_sel:
                        ej_name = get_exercise(e_id)['name']
                        st.markdown(f"**{ej_name}**")
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
                        st.session_state.plans.append({
                            "id": str(uuid.uuid4())[:4], "patientId": paciente_sel, "title": titulo_sesion,
                            "exerciseIds": ejercicios_sel, "exerciseInstructions": instrucciones_dict,
                            "pin": nuevo_pin, "active": True, "checkins": []
                        })
                        st.success(f"¡Sesión guardada! Lista para enviar.")
                        
                        # NUEVO: CAJA DE MENSAJE PARA WHATSAPP
                        nombre_paciente = get_patient_name(paciente_sel)
                        mensaje_whatsapp = f"¡Hola {nombre_paciente}! 👋\n\nAquí tienes tu nueva sesión de fisioterapia: *{titulo_sesion}*.\n\n📱 Para ver tus ejercicios y vídeos, entra en este enlace:\n{APP_URL}\n\n🔑 Tu código de acceso (PIN) es: {nuevo_pin}\n\n¡A por ello!"
                        
                        st.info("Copia el siguiente mensaje pulsando el icono de copiar (arriba a la derecha del recuadro) y pégalo en WhatsApp:")
                        st.code(mensaje_whatsapp, language="markdown")

    # --- PESTAÑA CHECK-INS ---
    with tab_res:
        st.markdown("<h1>Control de Cargas</h1>", unsafe_allow_html=True)
        for plan in reversed(st.session_state.plans):
            if plan.get("checkins"):
                with st.expander(f"📁 {get_patient_name(plan['patientId'])} - {plan['title']}"):
                    for checkin in reversed(plan["checkins"]):
                        st.markdown(f"**📅 {checkin['date']}**")
                        st.markdown(f"**EVA:** {checkin['eva']} / 10 | **Borg:** {checkin['borg']} / 10")
                        st.markdown(f"*{checkin['comment']}*")
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
            sesion_encontrada = next((p for p in st.session_state.plans if p["pin"] == pin_input), None)
            
            if sesion_encontrada:
                if not sesion_encontrada.get("active", True):
                    st.markdown("<div style='background:#fdecec; color:#aa3838; padding:11px 13px; border-radius:9px;'>⚠️ Esta sesión ha sido desactivada.</div>", unsafe_allow_html=True)
                else:
                    banner_html = f"""
                    <div style='background:#e9f6f0; border: 1px solid #dce7e2; border-radius:16px; padding:25px; margin:22px 0;'>
                        <h1 style='color:#103d33 !important; font-size:26px; margin:8px 0;'>¡Hola {get_patient_name(sesion_encontrada["patientId"])}!</h1>
                        <p style='color:#13765d !important; margin:0; font-size:18px; font-weight:bold;'>Sesión: {sesion_encontrada['title']}</p>
                    </div>
                    """
                    st.markdown(banner_html, unsafe_allow_html=True)
                    
                    for idx, e_id in enumerate(sesion_encontrada["exerciseIds"], 1):
                        ej_data = get_exercise(e_id)
                        if ej_data:
                            st.markdown(f"<h2 style='font-size:20px; margin:20px 0 10px;'>{idx}. {ej_data['name'].upper()}</h2>", unsafe_allow_html=True)
                            
                            inst_data = sesion_encontrada.get("exerciseInstructions", {}).get(e_id, {})
                            
                            if isinstance(inst_data, dict):
                                s = inst_data.get("series", "")
                                r = inst_data.get("reps", "")
                                n = inst_data.get("notes", "")
                                
                                detalles = []
                                if s: detalles.append(f"<b>Series:</b> {s}")
                                if r: detalles.append(f"<b>Reps:</b> {r}")
                                if n: detalles.append(f"<b>Comentarios del fisio:</b> {n}")
                                
                                if detalles:
                                    info_html = " | ".join(detalles)
                                    st.markdown(f"<div style='color:#103d33; font-size:18px; margin-bottom:15px; background:#fff; border: 2px solid #e9f6f0; padding:15px; border-radius:10px;'>{info_html}</div>", unsafe_allow_html=True)
                            elif isinstance(inst_data, str) and inst_data:
                                st.markdown(f"<div style='color:#103d33; font-size:18px; margin-bottom:15px; background:#fff; border: 2px solid #e9f6f0; padding:15px; border-radius:10px;'>{inst_data}</div>", unsafe_allow_html=True)
                            
                            col_vid1, col_vid2 = st.columns([1.5, 1])
                            with col_vid1:
                                st.video(ej_data["videoUrl"])
                                
                            st.divider()
                            
                    st.markdown("<h2 style='font-size:19px; margin:24px 0 13px;'>📝 Reporte de entrenamiento</h2>", unsafe_allow_html=True)
                    with st.form("feedback_form"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            eva = st.slider("Escala EVA (Dolor 0-10)", 0, 10, 2)
                        with col_b:
                            borg = st.slider("Escala Borg (Esfuerzo 0-10)", 0, 10, 5)
                        comentario = st.text_area("Comentarios (molestias, sensaciones)")
                        
                        if st.form_submit_button("Enviar Resultados", type="primary"):
                            if "checkins" not in sesion_encontrada:
                                sesion_encontrada["checkins"] = []
                            sesion_encontrada["checkins"].append({
                                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "eva": eva, "borg": borg, "comment": comentario
                            })
                            st.success("¡Registro enviado correctamente!")
            else:
                st.markdown("<div style='background:#fdecec; color:#aa3838; padding:11px 13px; border-radius:9px; text-align:center;'>PIN incorrecto.</div>", unsafe_allow_html=True)
