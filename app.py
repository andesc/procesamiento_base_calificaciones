import streamlit as st
import pandas as pd
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️", layout="wide")

# --- FUNCIONES DE UTILERÍA ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False
    if 'df_resultado' in st.session_state: del st.session_state.df_resultado
    if 'nombre_base' in st.session_state: del st.session_state.nombre_base

def limpiar_texto(texto):
    """Elimina tildes, eñes, espacios extras y pasa a mayúsculas para un cruce ciego y perfecto."""
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
    texto = texto.replace('Ñ', 'NI').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    return texto

def extraer_primer_nombre(celda):
    """Extrae el primer nombre propio limpiando el formato 'Apellido, Nombre'."""
    s = str(celda).strip()
    if "," in s:
        parte_nombre = s.split(",")[1].strip()
    else:
        parte_nombre = s
    primer_nombre = parte_nombre.split()[0] if parte_nombre.split() else ""
    return primer_nombre.capitalize()

def forzar_id_string(valor):
    """Transforma los IDs de Canvas/Excel en strings numéricos limpios sin decimales."""
    if pd.isna(valor): 
        return ""
    try:
        return str(int(float(str(valor).strip())))
    except:
        return str(valor).strip()

def homologar_actividad(nombre_tarea):
    """Identifica el tipo de actividad sin importar cómo esté tipiada en Canvas."""
    if pd.isna(nombre_tarea): return "OTRO"
    n = str(nombre_tarea).upper().strip()
    
    if "API1" in n or "API 1" in n or "AP1" in n: return "API 1"
    if "API2" in n or "API 2" in n or "AP2" in n: return "API 2"
    if "API3" in n or "API 3" in n or "AP3" in n: return "API 3"
    if "API4" in n or "API 4" in n or "AP4" in n: return "API 4"
    
    if "AE1" in n or "AE 1" in n: return "AE 1"
    if "AE2" in n or "AE 2" in n: return "AE 2"
    if "AE3" in n or "AE 3" in n: return "AE 3"
    if "AE4" in n or "AE 4" in n: return "AE 4"
    return "OTRO"

# --- LISTA NEGRA DE MATERIAS PARA EXCLUSIÓN EN APIS ---
MATERIAS_EXCLUIR_API = [
    "ADMINISTRACIÓN GENERAL DE LA EMPRESA AGRARIA",
    "CEREMONIAL Y PROTOCOLO",
    "CIBERCAPACIDADES",
    "COMERCIALIZACIÓN Y REVENUE MANAGEMENT",
    "CULTURA DEL TRABAJO CALIDAD Y EQUIPOS",
    "DECISIONES Y RESOLUCIONES EFICIENTES",
    "GESTIÓN DE LA PRODUCCIÓN ANIMAL",
    "GESTIÓN DE PERSONAS",
    "LEARNING AGILITY",
    "MULTIMEDIOS",
    "TOMA DE DECISIONES PARA LA ACCIÓN",
    "ALIMENTOS BEBIDAS Y EVENTOS",
    "DISEÑO DE SERVICIO AL CLIENTE",
    "GESTIÓN DE CULTIVOS EXTENSIVOS",
    "RESOLUCIÓN DE PROBLEMAS",
    "COMUNICACIÓN EFECTIVA",
    "ORGANIZACIÓN DEL TIEMPO Y DEL TRABAJO",
    "MATEMÁTICA Y ESTADÍSTICA",
    "PROCESO Y ESTRATEGIA DE MEJORA",
    "GESTIÓN DE PROYECTOS"
]

LISTA_NEGRA_LIMPIA = [limpiar_texto(m) for m in MATERIAS_EXCLUIR_API]

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state: st.session_state.count = 0
if 'procesado' not in st.session_state: st.session_state.procesado = False

# --- INTERFAZ ---
st.title("🛠️ Generador de bases")

def al_cambiar_modo():
    st.session_state.procesado = False
    if 'df_resultado' in st.session_state: del st.session_state.df_resultado
    if 'nombre_base' in st.session_state: del st.session_state.nombre_base

opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:", 
    ["Base para HubSpot", "Base para Whatsapp"], 
    key="radio_opcion",
    on_change=al_cambiar_modo
)

st.divider()

st.markdown("### 📥 Carga de archivos")
with st.expander("📌 Instrucciones de uso - LEER AQUÍ"):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        **Para generar la Base de HubSpot (Solo columna Email):**
        * **Reporte de Canvas (CSV):** Subí el archivo de Canvas.
        * **Base de Alumnos (XLSX):** Subí el Excel de invitaciones. Es obligatorio para extraer el correo.
        * El archivo resultante contendrá únicamente la columna `email` con encabezado.
        """)
    else:
        st.markdown("""
        **Para generar la Base de WhatsApp (Segmentada de a 100):**
        * **Reporte de Canvas (CSV):** Subí tu archivo de Canvas.
        * **Base de Alumnos (XLSX - Opcional para Calificaciones):** Permite cruzar datos más completos.
        * El archivo resultante organizará las columnas como `dni`, `nombre`, `materia` siempre sin encabezados.
        """)

col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

if archivo_csv:
    df_canvas = None
    try:
        contenido = archivo_csv.read()
        try:
            df_canvas = pd.read_csv(io.BytesIO(contenido), sep=',', engine='python', on_bad_lines='skip')
            if df_canvas.shape[1] <= 1: raise ValueError
        except:
            df_canvas = pd.read_csv(io.BytesIO(contenido), sep=';', engine='python', on_bad_lines='skip')
    except Exception as e:
        st.error(f"Error crítico al leer el archivo CSV de Canvas: {e}")

    if df_canvas is not None:
        df_canvas.columns = df_canvas.columns.str.strip().str.lower()
        
        # Identificación estricta de Submissions usando la columna en minúscula completa
        es_submissions = 'canvas user id' in df_canvas.columns and 'assignment name' in df_canvas.columns

        # ==================================================
        # --- CASO 1: REPORTE DE ENTREAS (SUBMISSIONS) ---
        # ==================================================
        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado con éxito.**")
            
            df_canvas = df_canvas.dropna(subset=['canvas user id'])
            df_canvas['id_match'] = df_canvas['canvas user id'].apply(forzar_id_string)
            df_canvas['actividad_limpia'] = df_canvas['assignment name'].apply(homologar_actividad)
            df_canvas['materia_match'] = df_canvas['course name'].apply(limpiar_texto)
            
            materias_seleccionadas = []
            if archivo_xlsx:
                df_excel = pd.read_excel(archivo_xlsx)
                df_excel.columns = df_excel.columns.str.strip().str.lower()
                
                # Forzar enlace estricto con 'canvas_id' desde el Excel
                col_id_excel = 'canvas_id' if 'canvas_id' in df_excel.columns else 'dni'
                df_excel['id_match'] = df_excel[col_id_excel].apply(forzar_id_string)
                df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                
                materias_disponibles = sorted(df_excel['materia'].dropna().unique())
                materias_seleccionadas = st.multiselect("Seleccionar Materias a evaluar (Vacío = Todas):", materias_disponibles)
            
            actividad_objetivo = st.selectbox("Selecciona la actividad a reclamar:", ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"])
            
            ejecutar_calculo = False
            if opcion_base == "Base para HubSpot" and not archivo_xlsx:
                st.warning("⚠️ Para HubSpot, el archivo XLSX de invitaciones es obligatorio para extraer el correo.")
            else:
                if st.button("🔍 Calcular Deudores Reales", type="primary"):
                    ejecutar_calculo = True
            
            if ejecutar_calculo:
                if not archivo_xlsx:
                    # LÓGICA DIRECTA CANVAS (WhatsApp sin Excel)
                    cumplidores = df_canvas[
                        (df_canvas['actividad_limpia'] == actividad_objetivo) & 
                        (df_canvas['workflow state'].isin(['submitted', 'graded']))
                    ]['id_match'].unique()
                    
                    df_deudores = df_canvas[~df_canvas['id_match'].isin(cumplidores)].copy()
                    
                    col_user_name = 'user name' if 'user name' in df_deudores.columns else df_deudores.columns[0]
                    df_deudores['nombre'] = df_deudores[col_user_name].apply(extraer_primer_nombre)
                    df_deudores['materia'] = df_deudores['course name'].astype(str).str.strip().str.upper()
                    df_deudores['dni'] = df_deudores['id_match']
                    
                    if "API" in actividad_objetivo.upper():
                        df_deudores = df_deudores[~df_deudores['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                    
                    df_base_wsp = df_deudores.drop_duplicates(subset=['dni', 'materia']).copy()
                    st.session_state.df_resultado = df_base_wsp[['dni', 'nombre', 'materia']]
                else:
                    # CRUCE AVANZADO CON EXCEL
                    df_universo = df_excel.copy()
                    
                    # Aplicar filtro selectivo de materias si se seleccionó alguna en el componente
                    if materias_seleccionadas:
                        df_universo = df_universo[df_universo['materia'].isin(materias_seleccionadas)]
                    
                    if "API" in actividad_objetivo.upper():
                        df_universo = df_universo[~df_universo['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                    
                    df_universo['llave_cruce'] = df_universo['id_match'] + "_" + df_universo['materia_match']
                    
                    entregas_validas = df_canvas[
                        (df_canvas['actividad_limpia'] == actividad_objetivo) & 
                        (df_canvas['workflow state'].isin(['submitted', 'graded']))
                    ].copy()
                    entregas_validas['llave_cruce'] = entregas_validas['id_match'] + "_" + entregas_validas['materia_match']
                    lista_cumplidores = entregas_validas['llave_cruce'].unique()
                    
                    df_deudores = df_universo[~df_universo['llave_cruce'].isin(lista_cumplidores)].copy()
                    
                    col_nombre = 'nombres' if 'nombres' in df_deudores.columns else ('student' if 'student' in df_deudores.columns else df_deudores.columns[2])
                    df_deudores['nombre'] = df_deudores[col_nombre].apply(extraer_primer_nombre)
                    df_deudores['materia'] = df_deudores['materia'].astype(str).str.strip().str.upper()
                    df_deudores['dni'] = df_deudores['id_match']

                    if opcion_base == "Base para HubSpot":
                        st.session_state.df_resultado = df_deudores[['email']].dropna().drop_duplicates()
                    else:
                        df_base_wsp = df_deudores.drop_duplicates(subset=['dni', 'materia']).copy()
                        st.session_state.df_resultado = df_base_wsp[['dni', 'nombre', 'materia']]
                    
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # ========================================================
        # --- CASO 2: REPORTE DE CALIFICACIONES ESTÁNDAR MATERIA ---
        # ========================================================
        else:
            st.success("📂 **Reporte de Calificaciones estándar detectado con éxito.**")
            df_canvas = df_canvas[~df_canvas['student'].str.contains('Points|Possible', case=False, na=False)]
            
            col_id_canvas = 'sis login id' if 'sis login id' in df_canvas.columns else ('sis user id' if 'sis user id' in df_canvas.columns else df_canvas.columns[1])
            df_canvas['id_match'] = df_canvas[col_id_canvas].apply(forzar_id_string)
            
            try:
                materia_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
            except:
                materia_archivo = "MATERIA_DETECTADA"
                
            materia_archivo_limpia = limpiar_texto(materia_archivo)
            aplicar_exclusion = any(x in materia_archivo_limpia for x in ["API", "AP"])
            
            ejecutar_calculo = False
            if opcion_base == "Base para HubSpot" and not archivo_xlsx:
                st.warning("⚠️ Para HubSpot, el archivo XLSX de invitaciones es obligatorio para extraer el correo.")
            else:
                if st.button("🔍 Calcular Deudores Reales (Calificaciones)", type="primary"):
                    ejecutar_calculo = True

            if ejecutar_calculo:
                if not archivo_xlsx:
                    if aplicar_exclusion and materia_archivo_limpia in LISTA_NEGRA_LIMPIA:
                        st.warning(f"🚫 La materia '{materia_archivo.upper()}' pertenece a la lista de exclusión automática.")
                        df_final = pd.DataFrame(columns=['dni', 'nombre', 'materia'])
                    else:
                        df_canvas['dni'] = df_canvas['id_match']
                        df_canvas['nombre'] = df_canvas['student'].apply(extraer_primer_nombre)
                        df_canvas['materia'] = materia_archivo.strip().upper()
                        df_final = df_canvas.drop_duplicates(subset=['dni']).copy()
                    
                    st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']]
                else:
                    df_excel = pd.read_excel(archivo_xlsx)
                    df_excel.columns = df_excel.columns.str.strip().str.lower()
                    
                    col_id_excel = 'canvas_id' if 'canvas_id' in df_excel.columns else ('dni' if 'dni' in df_excel.columns else df_excel.columns[0])
                    df_excel['id_match'] = df_excel[col_id_excel].apply(forzar_id_string)
                    df_excel['materia_match']
