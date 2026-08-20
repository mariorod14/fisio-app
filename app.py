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
APP_URL = "https://tu-enlace.streamlit.app"  # Asegúrate de poner aquí tu URL real

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
    .stTextInput input, .stTextArea textarea { border: 1px solid var(--line) !important; border-radius: 9px !important; }
    [data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 15px !important; }
</style>
"""
st.markdown(estilo_css, unsafe_allow_html=True)

if 'admin_mode' not in st.session_state:
    st.session_state.admin_mode = False

# =============================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# =============================================================
def get_patients():
    try:
        df = conn.read(worksheet="pacientes", ttl=600) # ttl aumentado para mejorar velocidad
        return df.dropna(how="all").astype(str).to_dict("records") if not df.empty else []
    except: return []

def save_patients(patients_list):
    conn.update(worksheet="pacientes", data=pd.DataFrame(patients_list))

def get_exercises():
    try:
        df = conn.read(worksheet="ejercicios", ttl=600)
        return df.dropna(how="all").astype(str).to_dict("records") if not df.empty else []
    except: return []

def save_exercises(exercises_list):
    conn.update(worksheet="ejercicios", data=pd.DataFrame(exercises_list))

def get_plans():
    try:
        df = conn.read(worksheet="sesiones", ttl=600)
        if df.empty: return []
        plans = []
        for _, r in df.iterrows():
            plans.append({
                "id": str(r["id"]), "patientId": str(r["patientId"]), "title": str(r["title"]),
                "exerciseIds": json.loads(r["exerciseIds"]) if isinstance(r["exerciseIds"], str) and r["exerciseIds"].startswith("[") else [],
                "exerciseInstructions": json.loads(r["exerciseInstructions"]) if isinstance(r["exerciseInstructions"], str) and r["exerciseInstructions"].startswith("{") else {},
                "pin": str(r["pin"]), "active": str(r["active"]).lower() in ["true", "1", "yes"]
            })
        return plans
    except: return []

def save_plans(plans_list):
    formatted = []
    for p in plans_list:
        formatted.append({
            "id": str(p["id"]), "patientId": str(p["patientId"]), "title": str(p["title"]),
            "exerciseIds": json.dumps(p["exerciseIds"]), "exerciseInstructions": json.dumps(p["exerciseInstructions"]),
            "pin": str(p["pin"]), "active": str(p["active"])
        })
    conn.update(worksheet="sesiones", data=pd.DataFrame(formatted))

def get_checkins():
    try:
        df = conn.read(worksheet="checkins", ttl=600)
        return df.dropna(how="all").astype(str).to_dict("records") if not df.empty else []
    except: return []

def save_checkin_item(plan_id, date, eva, borg, comment):
    checkins = get_checkins()
    checkins.append({"id": str(uuid.uuid4())[:4], "planId": str(plan_id), "date": str(date), "eva": str(eva), "borg": str(borg), "comment": str(comment)})
    conn.update(worksheet="checkins", data=pd.DataFrame(checkins))

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

# --- RESTO DE TU LÓGICA DE UI (Tablas, Formularios, etc.) ---
# [MANTÉN EL RESTO DE TU CÓDIGO AQUÍ EXACTAMENTE COMO LO TENÍAS]
# El código abajo es el punto de entrada que ya tenías
if st.session_state.admin_mode:
    # ... Tu lógica de admin (tabs) ...
    pass 
else:
    # ... Tu lógica de paciente ...
    pass
