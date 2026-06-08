import streamlit as st
import pandas as pd
import io
import re

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
    # Reemplazo estricto de Ñ/ñ por N/n para evitar rebotes en Meta
    s = s.replace('Ñ', 'N').replace('ñ', 'n')
    # Remover tildes manteniendo el caso (mayúscula/minúscula)
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

# --- INICIALIZACIÓN DE ESTADOS ---
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
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX - Requerido para Submissions)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

archivos_listos = False

if archivo_csv:
    contenido_bytes = archivo_csv.getvalue()
    try:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=',', engine='python', on_bad_lines='skip')
        if df_canvas_raw.shape[1] <= 1: raise ValueError
    except:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=';', engine='python', on_bad_lines='skip')
        
    df_canvas_raw.columns = df_canvas_raw.columns.str.strip()
    cols_lower = [c.lower() for c in df_canvas_raw.columns]
    
    es_submissions = 'canvas user id' in cols_lower and 'assignment name' in cols_lower

    if es_submissions and not archivo_xlsx:
        st.warning("⚠️ **Archivo intermedio requerido:** Detectamos un reporte de Submissions. Por favor, carga la Base de Alumnos (XLSX) para activar los filtros y poder procesar.")
    elif not es_submissions and opcion_base == "Base para HubSpot" and not archivo_xlsx:
        st.warning("⚠️ **Archivo intermedio requerido:** Para generar bases de HubSpot desde Calificaciones es obligatorio cargar el archivo Excel para obtener los correos.")
    else:
        archivos_listos = True

    if archivos_listos:
        st.markdown("### 🔍 Parámetros de Búsqueda")
        
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
            actividad_objetivo = "Materia Completa"

        # --- CONFIGURACIÓN DEL TEMPLATE ---
        texto_template = ""
        dict_mapeo_params = {}
        params_detectados = []

        if opcion_base == "Base para Whatsapp":
            st.markdown("---")
            st.markdown("### 📝 Configuración opcional: Template de Meta")
            texto_template = st.text_area(
                "Pegá el contenido de tu plantilla de Meta aquí si deseas estructurar las columnas de salida:",
                placeholder="Hola {{1}}, recordá entregar la actividad de {{2}}.",
                key="template_meta_antepuesto"
            )
            
            params_detectados = sorted(list(set(re.findall(r'\{\{(\d+)\}\}', texto_template))), key=int)
            if params_detectados:
                st.info(f"💡 Variables dinámicas detectadas: {len(params_detectados)}")
                cols_p = st.columns(min(len(params_detectados), 4))
                
                for idx, p in enumerate(params_detectados):
                    with cols_p[idx % 4]:
                        seleccion = st.selectbox(
                            f"Variable {{{{ {p} }}}}:", 
                            options=["dni", "nombre", "materia", "actividad", "✍️ Texto Fijo"], 
                            key=f"sel_{p}"
                        )
                        if seleccion == "✍️ Texto Fijo":
                            txt_fijo = st.text_input(f"Texto fijo para {{{{ {p} }}}}:", key=f"fijo_{p}")
                            dict_mapeo_params[p] = ("fijo", txt_fijo)
                        else:
                            dict_mapeo_params[p] = ("columna", seleccion)
            st.markdown("---")

        if st.button("🔍 Calcular Deudores Reales", type="primary"):
            df_canvas = df_canvas_raw.copy()
            df_canvas.columns = cols_lower

            # ==========================================
            # --- CASO 1: SUBMISSIONS ---
            # ==========================================
            if es_submissions:
                df_canvas = df_canvas.dropna(subset=['canvas user id'])
                df_canvas['id_match'] = df_canvas['canvas user id'].apply(forzar_id_string)
                df_canvas['materia_match'] = df_canvas['course name'].apply(limpiar_texto)
                df_canvas['actividad_limpia'] = df_canvas['assignment name'].apply(homologar_actividad)

                if materias_seleccionadas:
                    df_canvas = df_canvas[df_canvas['course name'].isin(materias_seleccionadas)]
                if "API" in actividad_objetivo.upper():
                    df_canvas = df_canvas[~df_canvas['materia_match'].isin(LISTA_NEGRA_LIMPIA)]

                entregas_validas = df_canvas[
                    (df_canvas['actividad_limpia'] == actividad_objetivo) & 
                    (df_canvas['workflow state'].isin(['submitted', 'graded']))
                ].copy()
                entregas_validas['llave_cruce'] = entregas_validas['id_match'] + "_" + entregas_validas['materia_match']
                lista_cumplidores = entregas_validas['llave_cruce'].unique()

                df_excel = pd.read_excel(archivo_xlsx)
                df_excel.columns = df_excel.columns.str.strip().str.lower()
                
                col_canvas_excel = 'canvas_id' if 'canvas_id' in df_excel.columns else ('canvas id' if 'canvas id' in df_excel.columns else 'id_alumno')
                col_dni_excel = 'dni' if 'dni' in df_excel.columns else 'documento'
                
                df_excel['id_match'] = df_excel[col_canvas_excel].apply(forzar_id_string)
                df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                
                df_universo = df_excel.copy()
                if materias_seleccionadas:
                    df_universo = df_universo[df_universo['materia'].isin(materias_seleccionadas)]
                if "API" in actividad_objetivo.upper():
                    df_universo = df_universo[~df_universo['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                
                df_universo['llave_cruce'] = df_universo['id_match'] + "_" + df_universo['materia_match']
                df_deudores = df_universo[~df_universo['llave_cruce'].isin(lista_cumplidores)].copy()
                
                col_n = 'nombres' if 'nombres' in df_deudores.columns else ('student' if 'student' in df_deudores.columns else df_deudores.columns[2])
                df_deudores['nombre'] = df_deudores[col_n].apply(extraer_primer_nombre)
                df_deudores['materia'] = df_deudores['materia'].astype(str).str.strip().str.upper()
                df_deudores['dni'] = df_deudores[col_dni_excel].apply(forzar_id_string)
                
                if opcion_base == "Base para HubSpot":
                    df_resultado_crudo = df_deudores[['email']].dropna().drop_duplicates()
                else:
                    df_resultado_crudo = df_deudores[['dni', 'nombre', 'materia']].drop_duplicates(subset=['dni', 'materia'])
                    if not materias_seleccionadas:
                        mults = df_resultado_crudo['dni'].value_counts()
                        df_resultado_crudo.loc[df_resultado_crudo['dni'].isin(mults[mults >= 2].index), 'materia'] = "DOS MATERIAS"
                        df_resultado_crudo = df_resultado_crudo.drop_duplicates(subset=['dni', 'materia'])

                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"

            # ==========================================
            # --- CASO 2: CALIFICACIONES ---
            # ==========================================
            else:
                df_canvas = df_canvas[~df_canvas['student'].str.contains('Points|Possible', case=False, na=False)]
                
                col_dni_canvas = 'sis login id' if 'sis login id' in cols_lower else ('sis user id' if 'sis user id' in cols_lower else df_canvas.columns[1])
                df_canvas['id_match'] = df_canvas[col_dni_canvas].apply(forzar_id_string)
                
                try: m_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
                except: m_archivo = "MATERIA_DETECTADA"
                
                m_limpia = limpiar_texto(m_archivo)
                excluir = any(x in m_limpia for x in ["API", "AP"])

                if not archivo_xlsx:
                    if excluir and m_limpia in LISTA_NEGRA_LIMPIA:
                        st.warning(f"🚫 Materia '{m_archivo.upper()}' excluida.")
                        df_resultado_crudo = pd.DataFrame(columns=['dni', 'nombre', 'materia'])
                    else:
                        df_f = pd.DataFrame()
                        df_f['dni'] = df_canvas['id_match']
                        df_f['nombre'] = df_canvas['student'].apply(extraer_primer_nombre)
                        df_f['materia'] = m_archivo.strip().upper()
                        df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])
                else:
                    df_excel = pd.read_excel(archivo_xlsx)
                    df_excel.columns = df_excel.columns.str
