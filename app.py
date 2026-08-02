import streamlit as st
import datetime
import random
import uuid

st.set_page_config(page_title="FisioPauta", layout="wide", page_icon="🩺")

# =============================================================
# 1. BASE DE DATOS SIMULADA
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
            "instructions": "",
            "exerciseIds": ["7769", "a91f", "e033"],
            "exerciseInstructions": {"7769": "3 series de 8", "a91f": "4 series de 6"},
            "pin": "785518",
            "active": True,  # Nuevo campo para activar/desactivar
            "checkins": []
        }
    ]

# Funciones de ayuda
def get_patient_name(p_id):
    for p in st.session_state.patients:
        if p["id"] == p_id: return p["name"]
    return "Paciente Eliminado"

def get_exercise(e_id):
    for e in st.session_state.exercises:
        if e["id"] == e_id: return e
    return None

# =============================================================
# INTERFAZ Y NAVEGACIÓN
# =============================================================
st.sidebar.title("🩺 FisioPauta")
modo = st.sidebar.radio("Navegación:", ["👨‍⚕️ Área Clínica", "🏋️ Portal del Paciente"])

# =============================================================
# MÓDULO 1: ÁREA CLÍNICA (Fisioterapeuta)
# =============================================================
if modo == "👨‍⚕️ Área Clínica":
    st.title("Panel de Control Clínico")
    
    tab_pac, tab_ej, tab_pau, tab_res = st.tabs(["👥 Pacientes", "🎥 Ejercicios", "📁 Mis Pautas", "📊 Check-ins"])
    
    # -------------------------------------------------------------
    # PESTAÑA 1: PACIENTES (Añadir, Perfil, Historial, Editar, Borrar)
    # -------------------------------------------------------------
    with tab_pac:
        with st.expander("➕ Añadir Nuevo Paciente", expanded=False):
            new_p_name = st.text_input("Nombre completo:")
            new_p_notes = st.text_area("Notas clínicas:")
            if st.button("Guardar Paciente Nuevo"):
                if new_p_name:
                    st.session_state.patients.append({"id": str(uuid.uuid4())[:4], "name": new_p_name, "notes": new_p_notes})
                    st.success("Paciente añadido.")
                    st.rerun()

        st.subheader("Directorio y Perfiles de Pacientes")
        for p in st.session_state.patients:
            with st.expander(f"👤 {p['name']}"):
                
                # --- HISTORIAL Y PAUTAS ACTUALES ---
                st.markdown("### 📋 Pautas Asignadas")
                pautas_del_paciente = [pl for pl in st.session_state.plans if pl["patientId"] == p["id"]]
                pautas_activas = [pl for pl in pautas_del_paciente if pl.get("active", True)]
                pautas_inactivas = [pl for pl in pautas_del_paciente if not pl.get("active", True)]
                
                if pautas_activas:
                    st.success("**🟢 Pauta(s) Actual(es) / Activa(s)**")
                    for pa in pautas_activas:
                        st.write(f"- **{pa['title']}** (PIN: {pa['pin']})")
                        nombres_ej = [get_exercise(eid)["name"] for eid in pa["exerciseIds"] if get_exercise(eid)]
                        st.caption(f"Ejercicios: {', '.join(nombres_ej)}")
                else:
                    st.info("No tiene ninguna pauta activa ahora mismo.")

                if pautas_inactivas:
                    st.warning("**⚪ Historial (Pautas Desactivadas)**")
                    for pi in pautas_inactivas:
                        st.write(f"- {pi['title']} (PIN: {pi['pin']})")
                        nombres_ej = [get_exercise(eid)["name"] for eid in pi["exerciseIds"] if get_exercise(eid)]
                        st.caption(f"Ejercicios: {', '.join(nombres_ej)}")

                st.divider()
                # --- EDITAR Y BORRAR PACIENTE ---
                st.markdown("### ⚙️ Ajustes del Paciente")
                edit_name = st.text_input("Nombre del paciente", value=p["name"], key=f"name_{p['id']}")
                edit_notes = st.text_area("Notas clínicas", value=p["notes"], key=f"notes_{p['id']}")
                
                col1, col2 = st.columns(2)
                if col1.button("💾 Actualizar Datos", key=f"upd_{p['id']}"):
                    p["name"] = edit_name
                    p["notes"] = edit_notes
                    st.success("Actualizado")
                    st.rerun()
                if col2.button("🗑️ Borrar Paciente", type="primary", key=f"del_{p['id']}"):
                    st.session_state.patients.remove(p)
                    # Opcional: Borrar también las pautas asociadas a él
                    st.session_state.plans = [pl for pl in st.session_state.plans if pl["patientId"] != p["id"]]
                    st.rerun()

    # -------------------------------------------------------------
    # PESTAÑA 2: EJERCICIOS (Añadir, Editar, Borrar)
    # -------------------------------------------------------------
    with tab_ej:
        with st.expander("➕ Añadir Nuevo Ejercicio", expanded=False):
            new_e_name = st.text_input("Nombre del ejercicio:")
            new_e_cat = st.selectbox("Categoría:", ["CORE", "EEII", "EESS", "Estiramientos y movilidad"])
            new_e_url = st.text_input("URL del Vídeo:")
            if st.button("Guardar Ejercicio"):
                if new_e_name and new_e_url:
                    st.session_state.exercises.append({"id": str(uuid.uuid4())[:4], "name": new_e_name, "category": new_e_cat, "videoUrl": new_e_url})
                    st.rerun()
                    
        st.subheader("Catálogo y Gestión")
        ej_opciones = {"": "Selecciona un ejercicio para editar/borrar..."}
        ej_opciones.update({e["id"]: f"{e['name']} ({e['category']})" for e in st.session_state.exercises})
        
        ej_selec = st.selectbox("Editar o borrar ejercicio:", options=list(ej_opciones.keys()), format_func=lambda x: ej_opciones[x])
        
        if ej_selec:
            ej_to_edit = get_exercise(ej_selec)
            if ej_to_edit:
                ed_name = st.text_input("Nombre", value=ej_to_edit["name"])
                ed_cat = st.selectbox("Cat", ["CORE", "EEII", "EESS", "Estiramientos y movilidad"], index=["CORE", "EEII", "EESS", "Estiramientos y movilidad"].index(ej_to_edit["category"]))
                ed_url = st.text_input("URL", value=ej_to_edit["videoUrl"])
                c1, c2 = st.columns(2)
                if c1.button("💾 Actualizar Ejercicio"):
                    ej_to_edit["name"] = ed_name
                    ej_to_edit["category"] = ed_cat
                    ej_to_edit["videoUrl"] = ed_url
                    st.rerun()
                if c2.button("🗑️ Borrar Ejercicio", type="primary"):
                    st.session_state.exercises.remove(ej_to_edit)
                    st.rerun()

    # -------------------------------------------------------------
    # PESTAÑA 3: PAUTAS (Crear y Gestionar/Desactivar)
    # -------------------------------------------------------------
    with tab_pau:
        sub_crear, sub_gestionar = st.tabs(["📝 Crear Nueva", "⚙️ Gestionar Creadas"])
        
        # --- CREAR PAUTA ---
        with sub_crear:
            if not st.session_state.patients:
                st.warning("Primero debes añadir pacientes.")
            else:
                paciente_sel = st.selectbox("1. Paciente:", options=[p["id"] for p in st.session_state.patients], format_func=get_patient_name)
                titulo_pauta = st.text_input("2. Título de la Pauta:")
                
                opciones_ejs = {e["id"]: f"{e['name']} ({e['category']})" for e in st.session_state.exercises}
                ejercicios_sel = st.multiselect("3. Selecciona los ejercicios:", options=list(opciones_ejs.keys()), format_func=lambda x: opciones_ejs[x])
                
                instrucciones_dict = {}
                if ejercicios_sel:
                    st.markdown("**4. Instrucciones Específicas:**")
                    for e_id in ejercicios_sel:
                        instrucciones_dict[e_id] = st.text_input(f"Instrucciones para: {opciones_ejs[e_id]}")
                        
                if st.button("💾 Generar Pauta"):
                    if titulo_pauta and ejercicios_sel:
                        nuevo_pin = str(random.randint(100000, 999999))
                        st.session_state.plans.append({
                            "id": str(uuid.uuid4())[:4],
                            "patientId": paciente_sel, "title": titulo_pauta,
                            "exerciseIds": ejercicios_sel, "exerciseInstructions": instrucciones_dict,
                            "pin": nuevo_pin, "active": True, "checkins": []
                        })
                        st.success(f"¡Guardada! PIN: {nuevo_pin}")
                    else:
                        st.error("Rellena el título y selecciona ejercicios.")

        # --- GESTIONAR PAUTAS ---
        with sub_gestionar:
            if not st.session_state.plans:
                st.info("No hay pautas creadas.")
            else:
                pau_opciones = {"": "Selecciona una pauta..."}
                pau_opciones.update({pl["id"]: f"{pl['title']} (Paciente: {get_patient_name(pl['patientId'])})" for pl in st.session_state.plans})
                
                pau_selec = st.selectbox("Pautas existentes:", options=list(pau_opciones.keys()), format_func=lambda x: pau_opciones[x])
                
                if pau_selec:
                    pl_to_edit = next(pl for pl in st.session_state.plans if pl["id"] == pau_selec)
                    
                    st.write(f"**PIN de acceso:** {pl_to_edit['pin']}")
                    
                    # Activar o Desactivar
                    nuevo_estado = st.toggle("Pauta Activa (Si se apaga, el paciente no podrá entrar con este PIN)", value=pl_to_edit.get("active", True))
                    if nuevo_estado != pl_to_edit.get("active", True):
                        pl_to_edit["active"] = nuevo_estado
                        st.rerun()
                        
                    # Editar título o Borrar
                    ed_tit = st.text_input("Cambiar Título:", value=pl_to_edit["title"])
                    c1, c2 = st.columns(2)
                    if c1.button("💾 Guardar Título"):
                        pl_to_edit["title"] = ed_tit
                        st.rerun()
                    if c2.button("🗑️ Eliminar Pauta Completa", type="primary"):
                        st.session_state.plans.remove(pl_to_edit)
                        st.rerun()

    # -------------------------------------------------------------
    # PESTAÑA 4: CHECK-INS
    # -------------------------------------------------------------
    with tab_res:
        st.subheader("Control de Cargas (Feedback de Pacientes)")
        hay_checkins = False
        for plan in reversed(st.session_state.plans):
            if plan.get("checkins"):
                hay_checkins = True
                paciente_nombre = get_patient_name(plan["patientId"])
                with st.expander(f"📁 {paciente_nombre} - Pauta: {plan['title']}"):
                    for checkin in reversed(plan["checkins"]):
                        st.markdown(f"**📅 {checkin['date']}**")
                        st.markdown(f"- **EVA:** {checkin['eva']} / 10 | **Borg:** {checkin['borg']} / 10")
                        st.markdown(f"- **Comentario:** {checkin['comment']}")
                        st.divider()
        if not hay_checkins:
            st.info("Aún no hay registros de pacientes.")

# =============================================================
# MÓDULO 2: PORTAL DEL PACIENTE
# =============================================================
else:
    st.title("🏋️ Tu Pauta de Recuperación")
    
    pin_input = st.text_input("🔑 Introduce el PIN de tu pauta:", type="password")
    
    if pin_input:
        pauta_encontrada = next((p for p in st.session_state.plans if p["pin"] == pin_input), None)
        
        if pauta_encontrada:
            if not pauta_encontrada.get("active", True):
                st.error("⚠️ Esta pauta ha sido desactivada y ya no está vigente. Si crees que es un error, contacta con tu fisioterapeuta.")
            else:
                paciente_nombre = get_patient_name(pauta_encontrada["patientId"])
                st.success(f"¡Hola {paciente_nombre}! Esta es tu pauta: **{pauta_encontrada['title']}**")
                st.divider()
                
                for idx, e_id in enumerate(pauta_encontrada["exerciseIds"], 1):
                    ej_data = get_exercise(e_id)
                    if ej_data:
                        st.markdown(f"### {idx}. {ej_data['name'].upper()}")
                        instruccion = pauta_encontrada.get("exerciseInstructions", {}).get(e_id, "")
                        if instruccion:
                            st.info(f"📋 **Indicaciones:** {instruccion}")
                        st.video(ej_data["videoUrl"])
                        st.divider()
                        
                st.subheader("📝 Registrar mi entrenamiento de hoy")
                with st.form("feedback_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        eva = st.slider("Escala EVA (Dolor 0-10)", 0, 10, 2)
                    with col2:
                        borg = st.slider("Escala Borg (Esfuerzo 0-10)", 0, 10, 5)
                    comentario = st.text_area("Comentarios (molestias, sensaciones, etc.)")
                    
                    if st.form_submit_button("📩 Enviar Resultados al Fisio"):
                        if "checkins" not in pauta_encontrada:
                            pauta_encontrada["checkins"] = []
                        pauta_encontrada["checkins"].append({
                            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "eva": eva, "borg": borg, "comment": comentario
                        })
                        st.balloons()
                        st.success("¡Registro enviado con éxito!")
        else:
            st.error("PIN incorrecto.")
