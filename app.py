import streamlit as st
import pandas as pd
import io
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False

def limpiar_texto(texto):
    """Elimina tildes, convierte Ñ en ni y normaliza texto."""
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

def extraer_y_formatear_nombre(celda):
    """Extrae el primer nombre del formato 'Apellido, Nombre' y lo normaliza."""
    s = str(celda).strip()
    if "," in s:
        parte_nombre = s.split(",")[1].strip()
    else:
        parte_nombre = s
    primer_nombre = parte_nombre.split()[0] if parte_nombre.split() else ""
    return primer_nombre.capitalize()

def normalizar_id(valor):
    """Limpia puntos, decimales y espacios para cruces exactos sin romper vinculación."""
    if pd.isna(valor): return ""
    s = str(valor).split('.')[0].strip()
    return s.replace(',', '')

def homologar_actividad(nombre_tarea):
    """Normaliza las variaciones de nombres de Canvas a un estándar limpio."""
    if pd.isna(nombre_tarea):
        return "OTRO"
    
    n = str(nombre_tarea).upper().strip()
    
    # Criterios para APIs (API 1, API 2, etc.)
    if "API1" in n or "API 1" in n or "AP1" in n or "AI1" in n:
        return "API 1"
    if "API2" in n or "API 2" in n or "AP2" in n or "AI2" in n:
        return "API 2"
    if "API3" in n or "API 3" in n or "AP3" in n or "AI3" in n:
        return "API 3"
    if "API4" in n or "API 4" in n or "AP4" in n or "AI4" in n:
        return "API 4"
        
    # Criterios para AEs (AE 1, AE 2, etc.)
    if "AE1" in n or "AE 1" in n:
        return "AE 1"
    if "AE2" in n or "AE 2" in n:
        return "AE 2"
    if "AE3" in n or "AE 3" in n:
        return "AE 3"
    if "AE4" in n or "AE 4" in n:
        return "AE 4"
        
    return "OTRO"

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0
if 'procesado' not in st.session_state:
    st.session_state.procesado = False

# --- INTERFAZ INICIAL ---
st.title("🛠️ Herramienta de Tutoría Inteligente")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR (DESPLEGABLE DINÁMICO) ---
st.markdown("### 📥 Carga de archivos")
with st.expander("1 - Obtené la base necesaria. Instrucciones aquí."):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Obtener el primer archivo (CSV):**
            * Ingresa a la materia en **Canvas** > **Calificaciones** o descarga el reporte de entregas. 
            * Aplica los filtros necesarios. 
            * Selecciona **Exportar** > **Vista actual**. 
            * ⚠️ **Importante:** No modifiques el nombre del archivo generado.

        2. **Obtener el segundo archivo (XLSX):**
            * En tu **Base de Invitaciones / Query de Avance**, filtra la materia objetivo.
            * Asegúrate de incluir los encabezados **id_alumno** y **dni**.
        """)
    else:
        st.markdown("""
        * Ingresa a la materia en **Canvas** > **Calificaciones** o descarga el reporte de entregas. 
        * Aplica los filtros necesarios. 
        * Selecciona **Exportar** > **Vista actual**. 
        * ⚠️ **Importante:** No modifiques el nombre del archivo generado.
        """)

# --- CARGA DE ARCHIVOS DINÁMICA ---
if opcion_base == "Base para HubSpot":
    st.write("Sube los archivos 👇 y luego haz clic en descargar")
    col1, col2 = st.columns(2)
    with col1:
        archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
    with col2:
        archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")
else:
    st.write("Sube el archivo 👇 y luego haz clic en descargar")
    col1, col2 = st.columns(2)
    with col1:
        archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_wsp_{st.session_state.count}")
    with col2:
        archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_wsp_{st.session_state.count}")

# --- PROCESAMIENTO GENERAL ---
if archivo_csv and archivo_xlsx:
    try:
        # Lectura robusta inicial
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_xlsx = pd.read_excel(archivo_xlsx)
        
        # Normalización estandarizada de columnas
        df_csv.columns = df_csv.columns.str.strip()
        cols_csv_lower = [c.lower() for c in df_csv.columns]
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
        
        # Detección del tipo de archivo CSV
        es_submissions = 'sis user id' in cols_csv_lower and 'assignment name' in cols_csv_lower

        # --- CASO A: REPORTE SUBMISSIONS (ENTREGAS) ---
        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado automáticamente.**")
            df_csv.columns = cols_csv_lower
            df_csv = df_csv.dropna(subset=['user name', 'sis user id'])
            
            # --- NUEVO: HOMOLOGACIÓN DE ACTIVIDADES DE FORMA INMEDIATA ---
            df_csv['actividad_limpia'] = df_csv['assignment name'].apply(homologar_actividad)
            
            st.markdown("### 🎛️ Filtros Avanzados de Segmentación")
            
            # Filtro por Materias
            materias_disponibles = sorted(df_csv['course name'].dropna().unique())
            materias_seleccionadas = st.multiselect(
                "1. Filtrar por Materias (Deja vacío para seleccionar todas):", 
                materias_disponibles, 
                default=[]
            )
            
            if materias_seleccionadas:
                df_filtrado_mat = df_csv[df_csv['course name'].isin(materias_seleccionadas)]
            else:
                df_filtrado_mat = df_csv
                
            # Seleccionar Actividad (ahora limpia y agrupada, quitando "OTRO")
            actividades_validas = [act for act in ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"] if act in df_filtrado_mat['actividad_limpia'].unique()]
            
            if not actividades_validas:
                actividades_validas = sorted([a for a in df_filtrado_mat['actividad_limpia'].unique() if a != "OTRO"])

            actividad_objetivo = st.selectbox("2. Selecciona la actividad a reclamar:", actividades_validas)
            
            if st.button("🔍 Filtrar y Calcular Deudores", type="primary"):
                # Normalización de IDs para el cruce exacto
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_filtrado_mat['id_match'] = df_filtrado_mat['sis user id'].apply(normalizar_id)
                
                # Llave única Alumno + Materia para evitar falsos cumplidores en materias paralelas
                df_filtrado_mat['llave_alumno_materia'] = df_filtrado_mat['id_match'] + "_" + df_filtrado_mat['course name'].str.strip().str.upper()
                
                # Universo de análisis bajo las materias seleccionadas
                universo = df_filtrado_mat[['id_match', 'user name', 'course name', 'llave_alumno_materia']].drop_duplicates()
                
                # Alumnos con entregas válidas en la actividad objetivo (usando la columna limpia)
                entregaron = df_filtrado_mat[
                    (df_filtrado_mat['actividad_limpia'] == actividad_objetivo
