import streamlit as st
import datetime

# Configuración básica de la app
st.set_page_config(page_title="FisioControl - Gestión de Pacientes", layout="wide", page_icon="🩺")

# --- SIMULACIÓN DE BASE DE DATOS (En memoria) ---
if 'catalogo_ejercicios' not in st.session_state:
    st.session_state.catalogo_ejercicios = [
        {"id": 1, "nombre": "Sentadilla isométrica en pared", "zona": "Rodilla / Cuádriceps", "url": "https://www.youtube.com/watch?v=y-wV4Venusw"},
        {"id": 2, "nombre": "Puente de glúteo unilateral", "zona": "Cadera / Cadena Posterior", "url": "https://www.youtube.com/watch?v=wPM8icPu6H8"},
        {"id": 3, "nombre": "Movilidad torácica con foam roller", "zona": "Espalda alta", "url": "https://www.youtube.com/watch?v=2TzR3A031E0"},
        {"id": 4, "nombre": "Excéntrico de gemelo en escalón", "zona": "Tobillo / Tendón de Aquiles", "url": "https://www.youtube.com/watch?v=2TzR3A031E0"}
    ]

if 'pautas_pacientes' not in st.session_state:
    st.session_state.pautas_pacientes = {
        "Juan Pérez": [1, 2] # IDs de ejercicios asignados a Juan
    }

if 'historial_feedback' not in st.session_state:
    st.session_state.historial_feedback = []

# --- NAVEGACIÓN EN LA BARRA LATERAL ---
st.sidebar.title("🩺 FisioControl")
modo = st.sidebar.radio("Selecciona la vista:", ["👨‍⚕️ Panel Fisioterapeuta", "🏋️ Vista del Paciente"])

# =============================================================
# MÓDULO 1: PANEL DEL FISIOTERAPEUTA
# =============================================================
if modo == "👨‍⚕️ Panel Fisioterapeuta":
    st.title("Panel de Control del Fisioterapeuta")
    
    tab1, tab2, tab3 = st.tabs(["📌 Asignar Pauta a Paciente", "➕ Añadir Vídeo al Catálogo", "📊 Ver Registro de Cargas"])
    
    # 1. Asignar pauta
    with tab1:
        st.subheader("Crear o modificar pauta de ejercicios")
        
        pacientes_existentes = list(st.session_state.pautas_pacientes.keys()) + ["Crear Nuevo Paciente..."]
        paciente_sel = st.selectbox("Selecciona un paciente:", pacientes_existentes)
        
        if paciente_sel == "Crear Nuevo Paciente...":
            nuevo_nombre = st.text_input("Nombre del nuevo paciente:")
            if nuevo_nombre:
                paciente_sel = nuevo_nombre
                if nuevo_nombre not in st.session_state.pautas_pacientes:
                    st.session_state.pautas_pacientes[nuevo_nombre] = []
        
        # Selección múltiple de ejercicios del catálogo
        opciones_ejercicios = {ej["id"]: f"{ej['nombre']} ({ej['zona']})" for ej in st.session_state.catalogo_ejercicios}
        
        ejercicios_actuales = st.session_state.pautas_pacientes.get(paciente_sel, [])
        
        seleccionados_ids = st.multiselect(
            "Selecciona los ejercicios para este paciente (puedes elegir los que quieras):",
            options=list(opciones_ejercicios.keys()),
            format_func=lambda x: opciones_ejercicios[x],
            default=ejercicios_actuales
        )
        
        if st.button("💾 Guardar Pauta del Paciente"):
            st.session_state.pautas_pacientes[paciente_sel] = seleccionados_ids
            st.success(f"Pauta actualizada con éxito para {paciente_sel} ({len(seleccionados_ids)} ejercicios).")

    # 2. Añadir ejercicios al catálogo (Hasta 400+)
    with tab2:
        st.subheader("Registrar nuevo vídeo en tu catálogo")
        nombre_ej = st.text_input("Nombre del Ejercicio:")
        zona_ej = st.text_input("Zona anatómica / Patología asociada:")
        url_ej = st.text_input("Enlace del vídeo (YouTube / Vimeo):")
        
        if st.button("Guardar en Catálogo"):
            if nombre_ej and url_ej:
                nuevo_id = len(st.session_state.catalogo_ejercicios) + 1
                st.session_state.catalogo_ejercicios.append({
                    "id": nuevo_id, "nombre": nombre_ej, "zona": zona_ej, "url": url_ej
                })
                st.success(f"¡Ejercicio '{nombre_ej}' añadido al catálogo con ID {nuevo_id}!")
            else:
                st.error("Por favor completa al menos el nombre y la URL del vídeo.")

    # 3. Ver respuestas de los pacientes
    with tab3:
        st.subheader("Control de cargas y respuestas recibidas")
        if not st.session_state.historial_feedback:
            st.info("Aún no hay registros de pacientes.")
        else:
            for item in reversed(st.session_state.historial_feedback):
                with st.expander(f"📅 {item['fecha']} - {item['paciente']} | EVA: {item['eva']} | Borg: {item['borg']}"):
                    st.write(f"**Ejercicios que más costaron:** {item['dificiles']}")
                    st.write(f"**Molestias o comentarios:** {item['comentarios']}")

# =============================================================
# MÓDULO 2: VISTA DEL PACIENTE & CONTROL DE CARGAS
# =============================================================
else:
    st.title("🏋️ Tu Pauta de Ejercicios")
    
    # Identificación del paciente
    pacientes_lista = list(st.session_state.pautas_pacientes.keys())
    paciente_actual = st.selectbox("Selecciona tu nombre para ver tu pauta:", pacientes_lista)
    
    if paciente_actual:
        ids_asignados = st.session_state.pautas_pacientes.get(paciente_actual, [])
        
        if not ids_asignados:
            st.warning("Aún no tienes ejercicios asignados. Consulta con tu fisioterapeuta.")
        else:
            st.info(f"Tienes **{len(ids_asignados)} ejercicios** pautados para tu sesión de hoy.")
            
            # Mostrar los vídeos pautados
            for idx, ej_id in enumerate(ids_asignados, 1):
                ej_data = next((item for item in st.session_state.catalogo_ejercicios if item["id"] == ej_id), None)
                if ej_data:
                    st.markdown(f"### {idx}. {ej_data['nombre']}")
                    st.caption(f"Objetivo: {ej_data['zona']}")
                    # Muestra el reproductor de vídeo directamente
                    st.video(ej_data['url'])
                    st.divider()

            # FORMULARIO DE CONTROL DE CARGAS (EVA, BORG, COMENTARIOS)
            st.subheader("📝 Registro de Sensaciones tras el Entrenamiento")
            with st.form("form_feedback"):
                col1, col2 = st.columns(2)
                
                with col1:
                    eva = st.slider("Escala EVA (Percepción del dolor de 0 a 10):", 0, 10, 2, 
                                    help="0 = Sin dolor, 10 = Máximo dolor insoportable")
                
                with col2:
                    borg = st.slider("Escala de Borg (Fatiga / Esfuerzo de 0 a 10):", 0, 10, 5, 
                                     help="0 = Reposo absoluto, 10 = Esfuerzo máximo")
                
                ej_dificiles = st.text_input("¿Qué ejercicios te han costado más o menos?")
                comentarios = st.text_area("¿Has sentido alguna molestia en particular o quieres comentarme algo?")
                
                enviado = st.form_submit_button("📩 Enviar Registro al Fisioterapeuta")
                
                if enviado:
                    st.session_state.historial_feedback.append({
                        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "paciente": paciente_actual,
                        "eva": eva,
                        "borg": borg,
                        "dificiles": ej_dificiles,
                        "comentarios": comentarios
                    })
                    st.balloons()
                    st.success("¡Registro enviado correctamente a tu fisioterapeuta!")