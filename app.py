import streamlit as st
import pandas as pd
import io
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️")

# --- FUNCIONES DE UTILERÍA ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    if 'df_crudo' in st.session_state: del st.session_state.df_crudo
    if 'nombre_base' in st.session_state: del st.session_state.nombre_base
    if 'tipo_reporte' in st.session_state: del st.session_state.tipo_reporte

def limpiar_texto(texto):
    if pd.isna(texto): return ""
    texto = str(texto).upper().strip()
    return texto.replace('Ñ', 'NI').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')

def extraer_primer_nombre(celda):
    s = str(celda).strip()
    parte_nombre = s.split(",")[1].strip() if "," in s else s
    return parte_nombre.split()[0].capitalize() if parte_nombre.split() else ""

def forzar_id_string(valor):
    if pd.isna(valor): return ""
    try: return str(int(float(str(valor).strip())))
    except: return str(valor).strip()

def homologar_actividad(nombre_tarea):
    if pd.isna(nombre_tarea): return "OTRO"
    n = str(nombre_tarea).upper().strip()
    for i in range(1, 5):
        if f"API{i}" in n or f"API {i}" in n or f"AP{i}" in n: return f"API {i}"
        if f"AE{i}" in n or f"AE {i}" in n: return f"AE {i}"
    return "OTRO"

MATERIAS_EXCLUIR_API = [
    "ADMINISTRACIÓN GENERAL DE LA EMPRESA AGRARIA", "CEREMONIAL Y PROTOCOLO", "CIBERCAPACIDADES",
    "COMERCIALIZACIÓN Y REVENUE MANAGEMENT", "CULTURA DEL TRABAJO CALIDAD Y EQUIPOS",
    "DECISIONES Y RESOLUCIONES EFICIENTES", "GESTIÓN DE LA PRODUCCIÓN ANIMAL", "GESTIÓN DE PERSONAS",
    "LEARNING AGILITY", "MULTIMEDIOS", "TOMA DE DECISIONES PARA LA ACCIÓN", "ALIMENTOS BEBIDAS Y EVENTOS",
    "DISEÑO DE SERVICIO AL CLIENTE", "GESTIÓN DE CULTIVOS EXTENSIVOS", "RESOLUCIÓN DE PROBLEMAS",
    "COMUNICACIÓN EFECTIVA", "ORGANIZACIÓN DEL TIEMPO Y DEL TRABAJO", "MATEMÁTICA Y ESTADÍSTICA",
    "PROCESO Y ESTRATEGIA DE MEJORA", "GESTIÓN DE PROYECTOS"
]
LISTA_NEGRA_LIMPIA = [limpiar_texto(m) for m in MATERIAS_EXCLUIR_API]

# --- INICIALIZACIÓN DE ESTADOS PERSISTENTES ---
if 'count' not in st.session_state: st.session_state.count = 0

st.title("🛠️ Generador de bases")

opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:", 
    ["Base para HubSpot", "Base para Whatsapp"], 
    key="radio_opcion"
)

st.divider()

st.markdown("### 📥 Carga de archivos")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX - Opcional para WhatsApp)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

if archivo_csv:
    @st.cache_data
    def cargar_csv_seguro(bytes_data):
        try:
            df = pd.read_csv(io.BytesIO(bytes_data), sep=',', engine='python', on_bad_lines='skip')
            if df.shape[1] <= 1: raise ValueError
            return df
        except:
            return pd.read_csv(io.BytesIO(bytes_data), sep=';', engine='python', on_bad_lines='skip')

    bytes_csv = archivo_csv.getvalue()
    df_canvas_raw = cargar_csv_seguro(bytes_csv)
    df_canvas_raw.columns = df_canvas_raw.columns.str.strip()
    cols_lower = [c.lower() for c in df_canvas_raw.columns]
    
    es_submissions = 'sis user id' in cols_lower and 'assignment name' in cols_lower

    st.markdown("### 🔍 Parámetros de Búsqueda")
    
    with st.form("formulario_calculo"):
        if es_submissions:
            st.info("📂 **Reporte de Entregas (Submissions) detectado.**")
            idx_m = cols_lower.index('course name') if 'course name' in cols_lower else 0
            materias_disponibles = sorted(df_canvas_raw[df_canvas_raw.columns[idx_m]].dropna().unique())
            
            materias_seleccionadas = st.multiselect("Seleccionar Materias (Vacío = Todas):", options=materias_disponibles)
            actividad_objetivo = st.selectbox("Selecciona la actividad a reclamar:", ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"])
        else:
            st.info("📂 **Reporte de Calificaciones estándar detectado.**")
            st.markdown("*Este reporte procesa la materia completa de manera directa.*")
            materias_seleccionadas = []
            actividad_objetivo = ""

        botón_ejecutar = st.form_submit_button("🔍 Calcular Deudores Reales", type="primary")

    if botón_ejecutar:
        if opcion_base == "Base para HubSpot" and not archivo_xlsx:
            st.error("⚠️ Para HubSpot es obligatorio cargar el archivo Excel para obtener los correos.")
        else:
            df_canvas = df_canvas_raw.copy()
            df_canvas.columns = cols_lower

            # ==========================================
            # --- CASO 1: SUBMISSIONS ---
            # ==========================================
            if es_submissions:
                df_canvas = df_canvas.dropna(subset=['sis user id'])
                df_canvas['id_match'] = df_canvas['sis user id'].apply(forzar_id_string)
                df_canvas['materia_match'] = df_canvas['course name'].apply(limpiar_texto)
                df_canvas['actividad_limpia'] = df_canvas['assignment name'].apply(homologar_actividad)

                if materias_seleccionadas
