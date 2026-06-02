import streamlit as st
import pandas as pd
import io
import os

# Configuración de la página
st.set_page_config(page_title="Generación de Bases Calificaciones", page_icon="🛠️")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1

def limpiar_texto(texto):
    """Elimina tildes, convierte Ñ en ni y normaliza texto."""
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

def extraer_primer_nombre(celda):
    """Extrae la primera palabra que figura en nombres y le da formato Capitalize."""
    s = str(celda).strip()
    if not s or s.lower() == 'nan':
        return ""
    if "," in s:
        s = s.split(",")[1].strip()
    
    primer_nombre = s.split()[0] if s.split() else ""
    return primer_nombre.capitalize()

def normalizar_actividad(actividad):
    """Mapea los nombres de tareas del CSV de entregas según las reglas."""
    act_upper = str(actividad).upper().strip()
    
    # Mapeo de APIs
    if "AP1" in act_upper or "API1" in act_upper or "AI1" in act_upper:
        return "API 1"
    if "AP2" in act_upper or "API2" in act_upper or "AI2" in act_upper:
        return "API 2"
    if "AP3" in act_upper or "API3" in act_upper or "AI3" in act_upper:
        return "API 3"
    if "AP4" in act_upper or "API4" in act_upper or "AI4" in act_upper:
        return "API 4"
        
    # Mapeo de AEs
    if "AE1" in act_upper:
        return "AE 1"
    if "AE2" in act_upper:
        return "AE 2"
    if "AE3" in act_upper:
        return "AE 3"
    if "AE4" in act_upper:
        return "AE 4"
        
    # PEF
    if "PEF" in act_upper:
        return "PEF"
        
    return None

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ INICIAL ---
st.title("🛠️ Generación de bases")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Bases desde submissions", "Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR (DESPLEGABLE) ---
st.markdown("### 📥 Carga de archivos")
with st.expander("Instrucciones de obtención de archivos"):
    if opcion_base == "Bases desde submissions":
        st.markdown("""
        * **Archivo 1 (CSV):** Reporte de entregas (Submissions) obtenido de Canvas. Debe contener `canvas user id`, `course name` y `assignment name`.
        * **Archivo 2 (Excel/CSV):** Base general de alumnos. Debe contener `canvas_id`, `dni`, `nombres`, `email` y `celular`.
        """)
    elif opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Primer archivo (CSV):** Reporte de Calificaciones de Canvas.
        2. **Segundo archivo (XLSX/CSV):** Base de alumnos con los encabezados `dni` y `email`.
        """)
    else:
        st.markdown("""
        * **Primer archivo (CSV):** Reporte de Calificaciones de Canvas.
        * **Segundo archivo (XLSX/CSV):** Base general con la columna de nombres de alumnos.
        """)

# --- CARGA DE ARCHIVOS ESTÁNDAR ---
st.write("Sube los archivos 👇 y luego configura o descarga los resultados")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte (CSV - Submissions / Calificaciones)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (Excel / CSV)", type=["xlsx", "csv"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO ---
if archivo_csv and archivo_xlsx:
    try:
        # Intentar extraer datos del nombre para HubSpot/WhatsApp
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia_bruta = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
            materia_limpia = materia_bruta.replace("_", " ")
        except:
            fecha, materia_limpia = "SinFecha", "Materia"

        # Lectura robusta del CSV primario
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_csv.columns = df_csv.columns.str.strip().str.lower()

        # Lectura de la Base secundaria (XLSX o CSV)
        if archivo_xlsx.name.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
        df_base.columns = df_base.columns.str.strip().str.lower()

        # --- LÓGICA OPCIÓN 1: BASES DESDE SUBMISSIONS ---
        if opcion_base == "Bases desde submissions":
            cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
            cols_base_req = {'canvas_id', 'dni', 'nombres', 'email', 'celular'}
            
            if not cols_csv_req.issubset(df_csv.columns):
                st.error(f"El CSV debe contener las columnas: {cols_csv_req}")
            elif not cols_base_req.issubset(df_base.columns):
                st.error(f"La base debe contener las columnas: {cols_base_req}")
            else:
                # Estandarizar identificadores a string
                df_csv['canvas user id'] = df_csv['canvas user id'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_base['canvas_id'] = df_base
