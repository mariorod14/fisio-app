import streamlit as st
import pandas as pd
import altair as alt
import json
import os
import uuid
import random
from datetime import datetime

# Configuración inicial de la página
st.set_page_config(page_title="Gestión Clínica de Fisioterapia", page_icon="🩺", layout="wide")

# -------------------------------------------------------------
# CONFIGURACIÓN Y PERSISTENCIA DE DATOS
# -------------------------------------------------------------
APP_URL = "https://tu-aplicacion.streamlit.app"  # Modifica con tu URL real
CATEGORIAS_EJ = ["Movilidad", "Fuerza", "Estiramientos", "Control Motor", "Reiteración Carga", "Cardio"]

def load_data(file_name, default_value):
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_value
    return default_value

def save_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

patients = load_data("patients.json", [])
plans = load_data("plans.json", [])
exercises = load_data("exercises.json", [])
checkins = load_data("checkins.json", [])

def save_patients(data): save_data("patients.json", data)
def save_plans(data): save_data("plans.json", data)
def save_exercises(data): save_data("exercises.json", data)
def save_checkins(data): save_data("checkins.json", data)

def get_patient_name(patient_id):
    p = next((x for x in patients if str(x["id"]) == str(patient_id)), None)
    return p["name"] if p else "Paciente Desconocido"

def get_exercise(exercise_id):
    return next((x for x in exercises if str(x["id"]) == str(exercise_id)), None)

# Modal de edición de sesión
def modal_editar_sesion(target_ses):
    st.markdown(f"### ✏️ Editando: {target_ses['title']}")
    nuevo_titulo = st.text_input("Título de la sesión:", value=target_ses["title"], key=f"edit_title_{target_ses['id']}")
    
    ej_options = {}
    for cat in CATEGORIAS_EJ:
        ej_ordenados = sorted([x for x in exercises if x.get("category") == cat], key=lambda x: x["name"].lower())
        for e in ej_ordenados:
            ej_options[f"{cat} | {e['name']}"] = e['id']
            
    ej_inversos = {v: k for k, v in ej_options.items()}
    default_selected = [ej_inversos[e_id] for e_id in target_ses["exerciseIds"] if e_id in ej_inversos]
    
    seleccionados = st.multiselect("Ejercicios de la sesión:", options=list(ej_options.keys()), default=default_selected, key=f"edit_multiselect_{target_ses['id']}")
    nuevos_ejs_ids = [ej_options[name] for name in seleccionados]
    
    c_save, c_cancel = st.columns([1, 1])
    with c_save:
        if st.button("💾 Guardar Cambios", key=f"save_edit_{target_ses['id']}", type="primary"):
            target_ses["title"] = nuevo_titulo
            target_ses["exerciseIds"] = nuevos_ejs_ids
            save_plans(plans)
            st.session_state.editing_sesion_id = None
            st.success("Sesión actualizada correctamente.")
            st.rerun()
    with c_cancel:
        if st.button("❌ Cancelar", key=f"cancel_edit_{target_ses['id']}"):
            st.session_state.editing_sesion_id = None
            st.rerun()

# -------------------------------------------------------------
# MENÚ NAVEGACIÓN
# -------------------------------------------------------------
st.sidebar.title("🩺 Menú Principal")
menu_seleccion = st.sidebar.radio("Ir a:", ["📂 Archivo", "🩺 Sesiones", "👤 Portal Paciente"])

# -------------------------------------------------------------
# VISTA 1: ARCHIVO (PACIENTES Y EJERCICIOS)
# -------------------------------------------------------------
if menu_seleccion == "📂 Archivo":
    st.markdown("<h1>📂 Gestión de Archivo</h1>", unsafe_allow_html=True)
    tab_pacientes, tab_ejercicios = st.tabs(["👤 Pacientes", "🏋️ Ejercicios"])
    
    with tab_pacientes:
        st.subheader("Añadir Nuevo Paciente")
        col_nombre, col_btn = st.columns([3, 1])
        with col_nombre:
            nombre_p = st.text_input("Nombre completo del paciente:", placeholder="Ej: Juan Pérez", label_visibility="collapsed")
        with col_btn:
            if st.button("➕ Registrar Paciente", use_container_width=True) and nombre_p.strip():
                p_id = str(uuid.uuid4())[:6]
                patients.append({"id": p_id, "name": nombre_p.strip()})
                save_patients(patients)
                st.success(f"Paciente '{nombre_p}' guardado.")
                st.rerun()
                
        st.divider()
        st.subheader("Lista de Pacientes Registrados")
        if not patients:
            st.info("No hay pacientes registrados.")
        else:
            for p in patients:
                c_p1, c_p2 = st.columns([4, 1])
                c_p1.write(f"👤 **{p['name']}** (ID: `{p['id']}`)")
                if c_p2.button("🗑️ Eliminar", key=f"del_pac_{p['id']}"):
                    patients = [x for x in patients if str(x["id"]) != str(p["id"])]
                    save_patients(patients)
                    st.rerun()

    with tab_ejercicios:
        st.subheader("Añadir Nuevo Ejercicio")
        c_e1, c_e2, c_e3 = st.columns([2, 2, 3])
        with c_e1:
            nom_ej = st.text_input("Nombre del Ejercicio:")
        with c_e2:
            cat_ej = st.selectbox("Categoría:", CATEGORIAS_EJ)
        with c_e3:
            url_ej = st.text_input("Enlace al Vídeo (YouTube/Vimeo):")
            
        if st.button("💾 Guardar Ejercicio") and nom_ej.strip():
            e_id = str(uuid.uuid4())[:6]
            exercises.append({"id": e_id, "name": nom_ej.strip(), "category": cat_ej, "videoUrl": url_ej.strip()})
            save_exercises(exercises)
            st.success("Ejercicio guardado con éxito.")
            st.rerun()
            
        st.divider()
        st.subheader("Biblioteca de Ejercicios")
        if not exercises:
            st.info("No hay ejercicios registrados.")
        else:
            for cat in CATEGORIAS_EJ:
                ejs_cat = [x for x in exercises if x.get("category") == cat]
                if ejs_cat:
                    with st.expander(f"📁 {cat} ({len(ejs_cat)})"):
                        for ej in ejs_cat:
                            ce1, ce2, ce3 = st.columns([3, 3, 1])
                            ce1.write(f"**{ej['name']}**")
                            ce2.write(f"🔗 [Ver vídeo]({ej['videoUrl']})" if ej.get('videoUrl') else "⚠️ Sin vídeo")
                            if ce3.button("🗑️", key=f"del_ej_{ej['id']}"):
                                exercises = [x for x in exercises if str(x["id"]) != str(ej["id"])]
                                save_exercises(exercises)
                                st.rerun()

# -------------------------------------------------------------
# VISTA 2: SESIONES CLÍNICAS
# -------------------------------------------------------------
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
                                st.session_state.orden_ejs[idx+1], st.session_state.orden_ejs[idx] = st.session_state.orden_ejs[idx+1], st.session_state.orden_ejs[idx]
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
                
                # Format de fecha corto para la gráfica y largo para la tabla
                df_checkins['Fecha_Corta'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y')
                df_checkins['Fecha_Larga'] = df_checkins['date_obj'].dt.strftime('%d/%m/%Y %H:%M')
                
                st.markdown("#### 📊 Gráfica de Dolor y Fatiga")
                
                # Preparar dataframe estructurado para Altair
                df_melted = df_checkins[['Fecha_Corta', 'eva', 'borg']].copy()
                df_melted = df_melted.rename(columns={'eva': 'Dolor (EVA)', 'borg': 'Fatiga (Borg)'})
                df_melted = df_melted.melt('Fecha_Corta', var_name='Métrica', value_name='Puntuación')
                
                # Creación de la gráfica con eje Y fijo y deshabilitado el zoom
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

# -------------------------------------------------------------
# VISTA 3: PORTAL DEL PACIENTE
# -------------------------------------------------------------
elif menu_seleccion == "👤 Portal Paciente":
    st.markdown("<h1>👤 Portal del Paciente</h1>", unsafe_allow_html=True)
    pin_ingresado = st.text_input("🔑 Introduce tu código PIN de acceso:", type="password")
    
    if pin_ingresado:
        plan_encontrado = next((p for p in plans if str(p["pin"]) == str(pin_ingresado.strip())), None)
        
        if not plan_encontrado:
            st.error("PIN incorrecto o no encontrado. Revisa el código proporcionado por tu fisioterapeuta.")
        else:
            st.success(f"¡Bienvenido/a! Sesión asignada: **{plan_encontrado['title']}**")
            st.markdown(f"**Paciente:** {get_patient_name(plan_encontrado['patientId'])}")
            st.divider()
            
            st.markdown("### 🏋️ Tus Ejercicios")
            instrucciones = plan_encontrado.get("exerciseInstructions", {})
            
            for idx, e_id in enumerate(plan_encontrado["exerciseIds"], 1):
                ej = get_exercise(e_id)
                if ej:
                    with st.container(border=True):
                        st.markdown(f"#### {idx}. {ej['name']}")
                        
                        # Detalles de series/reps/notas
                        inst = instrucciones.get(e_id, {})
                        s = inst.get("series", "")
                        r = inst.get("reps", "")
                        n = inst.get("notes", "")
                        
                        detalles = []
                        if s: detalles.append(f"**Series:** {s}")
                        if r: detalles.append(f"**Repeticiones:** {r}")
                        if n: detalles.append(f"**Notas:** {n}")
                        
                        if detalles:
                            st.write(" | ".join(detalles))
                            
                        if ej.get("videoUrl"):
                            st.markdown(f"▶️ [Ver Vídeo explicativo del ejercicio]({ej['videoUrl']})")
                        else:
                            st.caption("*(Sin vídeo adjunto)*")
                            
            st.divider()
            st.markdown("### 📝 Registrar Check-in diario")
            with st.form("form_checkin_paciente"):
                val_eva = st.slider("Grado de Dolor (EVA: 0 sin dolor, 10 dolor insoportable):", 0, 10, 0)
                val_borg = st.slider("Grado de Esfuerzo (Borg: 0 muy suave, 10 esfuerzo máximo):", 0, 10, 5)
                comentario_pac = st.text_area("¿Cómo te has sentido durante la sesión? (Opcional):")
                
                if st.form_submit_button("✉️ Enviar Registro al Fisio", type="primary"):
                    nuevo_checkin = {
                        "id": str(uuid.uuid4())[:6],
                        "planId": plan_encontrado["id"],
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "eva": val_eva,
                        "borg": val_borg,
                        "comment": comentario_pac
                    }
                    checkins.append(nuevo_checkin)
                    save_checkins(checkins)
                    st.success("¡Registro enviado correctamente! Muchas gracias.")
