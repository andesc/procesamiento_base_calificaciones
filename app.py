import streamlit as st
import pandas as pd
import io
import re
import zipfile
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️")

# --- FUNCIONES DE UTILERÍA ---
def reiniciar_aplicacion():
    if 'df_final_procesado' in st.session_state: del st.session_state.df_final_procesado
    if 'nombre_base' in st.session_state: del st.session_state.nombre_base
    if 'opcion_base_guardada' in st.session_state: del st.session_state.opcion_base_guardada
    st.session_state.count += 1

def limpiar_texto(texto):
    if pd.isna(texto): return ""
    texto = str(texto).upper().strip()
    return texto.replace('Ñ', 'NI').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')

def limpiar_caracteres_especiales(val):
    """Limpia tildes y convierte la Ñ en N para compatibilidad estricta con HubSpot y Meta (WhatsApp)"""
    if pd.isna(val): return ""
    s = str(val).strip()
    s = s.replace('Ñ', 'N').replace('ñ', 'n')
    remplazos = {
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Ü': 'U', 'ü': 'u'
    }
    for orig, dest in remplazos.items():
        s = s.replace(orig, dest)
    return s

def extraer_primer_nombre(celda):
    s = str(celda).strip()
    parte_nombre = s.split(",")[1].strip() if "," in s else s
    return parte_nombre.split()[0].capitalize() if parte_nombre.split() else ""

def forzar_id_string(valor):
    if pd.isna(valor): return ""
    try: return str(int(float(str(valor).strip())))
    except: return str(valor).strip()

def forzar_score_float(valor):
    if pd.isna(valor): return 0.0
    try: return float(str(valor).strip())
    except: return 0.0

def homologar_actividad(nombre_tarea):
    if pd.isna(nombre_tarea): return "OTRO"
    n = str(nombre_tarea).upper().strip()
    for i in range(1, 5):
        if f"API{i}" in n or f"API {i}" in n or f"AP{i}" in n: return f"API {i}"
        if f"AE{i}" in n or f"AE {i}" in n: return f"AE {i}"
    return "OTRO"

def normalizar_nombre_actividad_wsp(actividad_original):
    """Transforma nombres de actividades a formatos limpios tipo 'Autoevaluacion 1' para WhatsApp"""
    act_up = actividad_original.upper()
    for i in range(1, 5):
        if f"AE {i}" in act_up or f"AE{i}" in act_up or f"MÓDULO {i}" in act_up or f"MODULO {i}" in act_up:
            return f"Autoevaluacion {i}"
        if f"API {i}" in act_up or f"API{i}" in act_up:
            return f"API {i}"
    return actividad_original

# --- DICCIONARIO INTERNO FIJO DE MATERIAS POR ÁREA ---
MATERIAS_POR_AREA_DICT = {
    # AREA: ADMIN
    "ADMINISTRACION GENERAL DE LA EMPRESA AGRARIA": "ADMIN",
    "AGRICULTURA DIGITAL": "ADMIN",
    "ANALISIS DEL RIESGO": "ADMIN",
    "BENEFICIOS Y COMPENSACIONES": "ADMIN",
    "CIRCUITOS ADMINISTRATIVOS CONTABLES CLAVES": "ADMIN",
    "CONTABILIDAD PATRIMONIAL": "ADMIN",
    "CONTRATO DE SEGUROS": "ADMIN",
    "CULTURA DEL TRABAJO CALIDAD Y EQUIPOS": "ADMIN",
    "CULTURA DEL TRABAJO, CALIDAD Y EQUIPOS": "ADMIN",
    "ESTRATEGIA Y PLANIFICACION COMERCIAL": "ADMIN",
    "ESTRATEGIAS DE VENTA DIRECTA": "ADMIN",
    "GESTION DE LA PRODUCCION ANIMAL": "ADMIN",
    "GESTION DE PROYECTOS": "ADMIN",
    "HERRAMIENTAS COMERCIALES": "ADMIN",
    "INCENTIVOS Y FORMACION DE EQUIPOS DE VENTA": "ADMIN",
    "REMUNERACIONES E INDEMNIZACIONES": "ADMIN",
    "RESPONSABILIDAD EMPRESARIAL": "ADMIN",
    "SEGUROS ESPECIFICOS 2": "ADMIN",
    "TECNICA IMPOSITIVA": "ADMIN",
    "TECNOLOGIA PARA LA GESTION CONTABLE": "ADMIN",
    "TRANSFORMACION DIGITAL Y EL NEGOCIO DEL SEGURO": "ADMIN",
    "TRANSFORMACION E INNOVACION ORGANIZACIONAL": "ADMIN",
    "GESTION DE PRESUPUESTOS": "ADMIN",
    "GESTION DE PERSONAS": "ADMIN",
    
    # AREA: COMU
    "BASES OPERATIVAS DE EXPERIENCIA DEL CLIENTE": "COMU",
    "CEREMONIAL Y PROTOCOLO": "COMU",
    "COMERCIALIZACION Y REVENUE MANAGEMENT": "COMU",
    "COMERCIALIZACION  Y REVENUE MANAGEMENT": "COMU",
    "COMUNICACION DE EVENTOS Y NUEVAS TECNOLOGIAS": "COMU",
    "DECISIONES Y RESOLUCIONES EFICIENTES": "COMU",
    "EMPRENDIMIENTO E INNOVACION EN EVENTOS": "COMU",
    "ESTRATEGIA DE PLANIFICACION DE INBOUND MARKETING": "COMU",
    "ESTRATEGIAS DE MARKETING DIGITAL": "COMU",
    "ESTRATEGIAS DE TRANSFORMACION DIGITAL": "COMU",
    "EXPERIENCIA DE LAS PERSONAS": "COMU",
    "EXPERIENCIA DEL HUESPED": "COMU",
    "GESTION DE MARCA": "COMU",
    "HOUSEKEEPING": "COMU",
    "MARKETING PARA E-COMMERCE": "COMU",
    "METODOLOGIA DE INBOUND MARKETING": "COMU",
    "MONETIZACION PUBLICITARIA": "COMU",
    "MULTIMEDIOS": "COMU",
    "NUEVO PERIODISMO": "COMU",
    "PERIODISMO DE DATOS": "COMU",
    "PLANIFICACION DE EVENTOS": "COMU",
    "PLANIFICACION ESTRATEGICA DE EXPERIENCIA AL CLIENTE": "COMU",
    "REDACCION PERIODISTICA EN LA ERA DIGITAL": "COMU",
    "SISTEMAS DE GENERACION Y CONVERSION": "COMU",
    "TOMA DE DECISIONES PARA LA ACCION": "COMU",
    
    # AREA: IT
    "ADMINISTRACION DE SISTEMAS EN LA NUBE (SYSOPS ADMINISTRATION)": "IT",
    "ARQUITECTURA DE SOLUCIONES": "IT",
    "AUTOMATIZACION Y PROGRAMABILIDAD DE REDES": "IT",
    "BASE DE DATOS": "IT",
    "CIBERCAPACIDADES": "IT",
    "DESARROLLO DE TESTS": "IT",
    "EXPERIENCIA DE USUARIO": "IT",
    "HACKING ETICO": "IT",
    "INTELIGENCIA DE ATAQUES": "IT"
}

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

# --- INICIALIZACIÓN DE ESTADOS ---
if 'count' not in st.session_state: st.session_state.count = 0

st.title("🛠️ Generador de bases")

st.markdown("### 📥 Carga de archivos")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV - Opcional)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

# --- DETECCIÓN DEL MODO DE TRABAJO ---
modo_trabajo = None
archivos_listos = False
periodos_disponibles = []
df_canvas_raw = None
cols_lower = []
es_submissions = False

if archivo_csv and archivo_xlsx:
    modo_trabajo = "TRADICIONAL_CRUCE"
    archivos_listos = True
elif archivo_xlsx and not archivo_csv:
    modo_trabajo = "ACCIONES_DIARIAS"
    archivos_listos = True
elif archivo_csv and not archivo_xlsx:
    st.warning("⚠️ **Archivo intermedio requerido:** Para procesar un reporte de Canvas es obligatorio cargar también la Base de Alumnos (XLSX).")

if archivo_xlsx:
    try:
        df_excel_prelectura = pd.read_excel(archivo_xlsx)
        df_excel_prelectura.columns = df_excel_prelectura.columns.str.strip()
        col_periodo = [c for c in df_excel_prelectura.columns if c.lower() == 'periodo inicio carrera']
        if col_periodo:
            periodos_disponibles = sorted(df_excel_prelectura[col_periodo[0]].dropna().astype(str).unique())
    except Exception as e:
        st.error(f"Error al pre-leer el archivo Excel: {e}")

if archivo_csv and modo_trabajo == "TRADICIONAL_CRUCE":
    contenido_bytes = archivo_csv.getvalue()
    try:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=',', engine='python', on_bad_lines='skip')
        if df_canvas_raw.shape[1] <= 1: raise ValueError
    except:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=';', engine='python', on_bad_lines='skip')
        
    df_canvas_raw.columns = df_canvas_raw.columns.str.strip()
    cols_lower = [c.lower() for c in df_canvas_raw.columns]
    es_submissions = 'canvas user id' in cols_lower and 'assignment name' in cols_lower


# --- INTERFAZ DINÁMICA ---
if archivos_listos:
    st.divider()
    if modo_trabajo == "ACCIONES_DIARIAS":
        st.info("💡 **Subiste solo el excel 'base...', trabajaré en modo 'Bases acciones diarias'. Nos concentraremos en Actividades del módulo que selecciones a continuación.**")
    else:
        st.success("🔄 **Modo de Cruce Avanzado activado (Canvas + Base de Alumnos).**")

    st.markdown("### 🎯 Filtros Previos de Cohorte (NI / RI)")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        if periodos_disponibles:
            periodo_actual_sel = st.selectbox("1. Selecciona el Período / Bimestre Actual:", options=periodos_disponibles, index=len(periodos_disponibles)-1)
        else:
            st.warning("⚠️ No se encontró la columna 'Periodo inicio Carrera' en el Excel.")
            periodo_actual_sel = None
    
    with col_f2:
        filtro_ingreso = st.selectbox(
            "2. Tipo de Alumno a considerar:",
            options=
