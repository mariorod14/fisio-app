import streamlit as st
import datetime
import random
import uuid

st.set_page_config(page_title="FisioPauta", layout="wide", page_icon="🩺")

# =============================================================
# 1. BASE DE DATOS SIMULADA (Basada en el JSON original)
# =============================================================
if 'patients' not in st.session_state:
    st.session_state.patients = [
        {"id": "765d", "name": "Faico Arzoz", "notes": "trabajo de fuerza general para hacer en casa 3 dias/semana/20minutos"},
        {"id": "debc", "name": "Ana Arzoz", "notes": "trabajo de fuerza general 2 dias/semana"},
        {"id": "49a7", "name": "Eduardo Rodriguez", "notes": ""}
    ]

if 'exercises' not in st.session_state:
    # He puesto URLs de YouTube de ejemplo porque los vídeos locales (.mov/.mp4) no subirán a la nube
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
            "patientId": "49a7", # Eduardo Rodriguez
            "title": "menisco agosto",
            "instructions": "",
            "exerciseIds": ["7769", "a91f", "e033"],
            "exerciseInstructions": {
                "7769": "3 series de 8 repeticiones\nno inclinar el tronco, mantenerse recto",
                "a91f": "4 series de 6 repeticiones",
                "e033": "5 series de 10 repeticiones"
            },
            "pin": "785518",
            "checkins": [
                {"date": "2026-07-28 10:23", "eva": 2, "borg": 6, "comment": "solo he tenido un poco mas de dolor en el segundo ejercicio"},
                {"date": "2026-07-28 10:25", "eva": 8, "borg": 4, "comment": "mucho dolor, mal"}
            ]
        }
    ]

# =============================================================
# INTERFAZ Y NAVEGACIÓN
# =============================================================
st.sidebar.title("🩺 FisioPauta")
modo = st.sidebar.radio("Navegación:", ["👨‍⚕️ Área Clínica", "🏋️ Portal del Paciente"])

# Funciones de ayuda
def get_patient_name(p_id):
    for p in st.session_state.patients:
        if p["id"] == p_id: return p["name"]
    return "Desconocido"

def get_exercise(e_id):
    for e in st.session_state.exercises:
        if e["id"] == e_id: return e
    return None

# =============================================================
# MÓDULO 1: ÁREA CLÍNICA (Fisioterapeuta)
# =============================================================
if modo == "👨‍⚕️ Área Clínica":
    st.title("Panel de Control Clínico")
    
    tab_pac, tab_ej, tab_pau, tab_res = st.tabs(["👥 Pacientes", "🎥 Catálogo Ejercicios", "📝 Crear Pauta", "📊 Check-ins"])
    
    # --- PESTAÑA PACIENTES ---
    with tab_pac:
        st.subheader("Gestión de Pacientes")
        with st.expander("➕ Añadir Nuevo Paciente"):
            new_p_name = st.text_input("Nombre completo del paciente:")
            new_p_notes = st.text_area("Notas clínicas iniciales (privado):")
            if st.button("Guardar Paciente"):
                if new_p_name:
                    st.session_state.patients.append({"id": str(uuid.uuid4())[:4], "name": new_p_name, "notes": new_p_notes})
                    st.success("Paciente añadido.")
                    st.rerun()

        st.divider()
        for p in st.session_state.patients:
            st.markdown(f"**{p['name']}** - *Notas: {p['notes'] if p['notes'] else 'Sin notas'}*")

    # --- PESTAÑA EJERCICIOS ---
    with tab_ej:
        st.subheader("Catálogo de Ejercicios")
        with st.expander("➕ Añadir Nuevo Ejercicio"):
            new_e_name = st.text_input("Nombre del ejercicio:")
            new_e_cat = st.selectbox("Categoría:", ["CORE", "EEII", "EESS", "Estiramientos y movilidad"])
            new_e_url = st.text_input("URL del Vídeo (YouTube/Vimeo):")
            if st.button("Guardar Ejercicio"):
                if new_e_name and new_e_url:
                    st.session_state.exercises.append({"id": str(uuid.uuid4())[:4], "name": new_e_name, "category": new_e_cat, "videoUrl": new_e_url})
                    st.success("Ejercicio añadido.")
                    st.rerun()
                    
        st.divider()
        # Mostrar ejercicios agrupados
        for cat in ["CORE", "EEII", "EESS", "Estiramientos y movilidad"]:
            ejs_cat = [e for e in st.session_state.exercises if e['category'] == cat]
            if ejs_cat:
                st.markdown(f"### {cat}")
                for e in ejs_cat:
                    st.markdown(f"- {e['name']}")

    # --- PESTAÑA CREAR PAUTA ---
    with tab_pau:
        st.subheader("Diseñar Pauta de Tratamiento")
        
        paciente_sel = st.selectbox("1. Selecciona Paciente:", options=[p["id"] for p in st.session_state.patients], format_func=get_patient_name)
        titulo_pauta = st.text_input("2. Título de la Pauta (ej. 'Fase 1 Menisco Agosto'):")
        
        opciones_ejs = {e["id"]: f"{e['name']} ({e['category']})" for e in st.session_state.exercises}
        ejercicios_sel = st.multiselect("3. Selecciona los ejercicios:", options=list(opciones_ejs.keys()), format_func=lambda x: opciones_ejs[x])
        
        instrucciones_dict = {}
        if ejercicios_sel:
            st.markdown("**4. Instrucciones Específicas por Ejercicio:**")
            for e_id in ejercicios_sel:
                ej_name = opciones_ejs[e_id]
                instrucciones_dict[e_id] = st.text_input(f"Instrucciones para: {ej_name}", placeholder="Ej: 3 series de 10 reps, sin inclinar tronco...")
                
        if st.button("💾 Generar y Guardar Pauta", type="primary"):
            if titulo_pauta and ejercicios_sel:
                nuevo_pin = str(random.randint(100000, 999999))
                nueva_pauta = {
                    "id": str(uuid.uuid4())[:4],
                    "patientId": paciente_sel,
                    "title": titulo_pauta,
                    "exerciseIds": ejercicios_sel,
                    "exerciseInstructions": instrucciones_dict,
                    "pin": nuevo_pin,
                    "checkins": []
                }
                st.session_state.plans.append(nueva_pauta)
                st.success(f"¡Pauta guardada! El PIN de acceso para el paciente es: {nuevo_pin}")
            else:
                st.error("Rellena el título y selecciona al menos un ejercicio.")

    # --- PESTAÑA RESULTADOS (Check-ins) ---
    with tab_res:
        st.subheader("Control de Cargas (Feedback de Pacientes)")
        for plan in reversed(st.session_state.plans):
            if plan["checkins"]:
                paciente_nombre = get_patient_name(plan["patientId"])
                with st.expander(f"📁 {paciente_nombre} - Pauta: {plan['title']}"):
                    for checkin in reversed(plan["checkins"]):
                        st.markdown(f"**📅 {checkin['date']}**")
                        st.markdown(f"- **EVA:** {checkin['eva']} / 10 | **Borg:** {checkin['borg']} / 10")
                        st.markdown(f"- **Comentario:** {checkin['comment']}")
                        st.divider()

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE
# =============================================================
else:
    st.title("🏋️ Tu Pauta de Recuperación")
    
    pin_input = st.text_input("🔑 Introduce el PIN de tu pauta (Pídeselo a tu fisio):", type="password")
    
    if pin_input:
        # Buscar pauta por PIN
        pauta_encontrada = next((p for p in st.session_state.plans if p["pin"] == pin_input), None)
        
        if pauta_encontrada:
            paciente_nombre = get_patient_name(pauta_encontrada["patientId"])
            st.success(f"¡Hola {paciente_nombre}! Esta es tu pauta: **{pauta_encontrada['title']}**")
            st.divider()
            
            # Mostrar ejercicios
            for idx, e_id in enumerate(pauta_encontrada["exerciseIds"], 1):
                ej_data = get_exercise(e_id)
                if ej_data:
                    st.markdown(f"### {idx}. {ej_data['name'].upper()}")
                    instruccion = pauta_encontrada["exerciseInstructions"].get(e_id, "")
                    if instruccion:
                        st.info(f"📋 **Indicaciones:** {instruccion}")
                    st.video(ej_data["videoUrl"])
                    st.divider()
                    
            # Check-in (Control de Cargas)
            st.subheader("📝 Registrar mi entrenamiento de hoy")
            with st.form("feedback_form"):
                col1, col2 = st.columns(2)
                with col1:
                    eva = st.slider("Escala EVA (Dolor 0-10)", 0, 10, 2)
                with col2:
                    borg = st.slider("Escala Borg (Esfuerzo 0-10)", 0, 10, 5)
                
                comentario = st.text_area("Comentarios (molestias, sensaciones, etc.)", placeholder="Mucho dolor en el segundo ejercicio...")
                
                if st.form_submit_button("📩 Enviar Resultados al Fisio"):
                    nuevo_checkin = {
                        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "eva": eva,
                        "borg": borg,
                        "comment": comentario
                    }
                    pauta_encontrada["checkins"].append(nuevo_checkin)
                    st.balloons()
                    st.success("¡Registro enviado con éxito!")
        else:
            st.error("PIN incorrecto. Por favor, revisa el código o contacta con tu fisioterapeuta.")
