import streamlit as io_st  # Cambiado para evitar conflictos de nombres si los hubiera
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
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX - Opcional para WhatsApp)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

if archivo_csv:
    # Lectura directa del archivo sin intermediarios de caché conflictivos
    contenido_bytes = archivo_csv.getvalue()
    try:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=',', engine='python', on_bad_lines='skip')
        if df_canvas_raw.shape[1] <= 1: raise ValueError
    except:
        df_canvas_raw = pd.read_csv(io.BytesIO(contenido_bytes), sep=';', engine='python', on_bad_lines='skip')
        
    df_canvas_raw.columns = df_canvas_raw.columns.str.strip()
    cols_lower = [c.lower() for c in df_canvas_raw.columns]
    
    es_submissions = 'sis user id' in cols_lower and 'assignment name' in cols_lower

    st.markdown("### 🔍 Parámetros de Búsqueda")
    
    # Selectores directos (sin encapsular en formularios que rompen flujos)
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

    # Botón de ejecución directo
    if st.button("🔍 Calcular Deudores Reales", type="primary"):
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

                if archivo_xlsx:
                    df_excel = pd.read_excel(archivo_xlsx)
                    df_excel.columns = df_excel.columns.str.strip().str.lower()
                    col_id = 'id_alumno' if 'id_alumno' in df_excel.columns else 'dni'
                    df_excel['id_match'] = df_excel[col_id].apply(forzar_id_string)
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
                    df_deudores['dni'] = df_deudores['id_match']
                    
                    if opcion_base == "Base para HubSpot":
                        st.session_state.df_crudo = df_deudores[['email']].dropna().drop_duplicates()
                    else:
                        st.session_state.df_crudo = df_deudores[['dni', 'nombre', 'materia']].drop_duplicates(subset=['dni', 'materia'])
                else:
                    df_canvas['llave_cruce'] = df_canvas['id_match'] + "_" + df_canvas['materia_match']
                    df_deudores = df_canvas[~df_canvas['llave_cruce'].isin(lista_cumplidores)].copy()
                    
                    df_f = pd.DataFrame()
                    df_f['dni'] = df_deudores['id_match']
                    col_u = 'user name' if 'user name' in df_deudores.columns else 'sis user id'
                    df_f['nombre'] = df_deudores[col_u].apply(extraer_primer_nombre)
                    df_f['materia'] = df_deudores['course name'].astype(str).str.strip().str.upper()
                    
                    st.session_state.df_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])

                if opcion_base == "Base para Whatsapp" and not materias_seleccionadas and 'df_crudo' in st.session_state:
                    df_t = st.session_state.df_crudo
                    mults = df_t['dni'].value_counts()
                    df_t.loc[df_t['dni'].isin(mults[mults >= 2].index), 'materia'] = "DOS MATERIAS"
                    st.session_state.df_crudo = df_t.drop_duplicates(subset=['dni', 'materia'])
                
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"

            # ==========================================
            # --- CASO 2: CALIFICACIONES ---
            # ==========================================
            else:
                df_canvas = df_canvas[~df_canvas['student'].str.contains('Points|Possible', case=False, na=False)]
                col_id_c = 'sis login id' if 'sis login id' in df_canvas.columns else ('sis user id' if 'sis user id' in df_canvas.columns else df_canvas.columns[1])
                df_canvas['id_match'] = df_canvas[col_id_c].apply(forzar_id_string)
                
                try: m_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
                except: m_archivo = "MATERIA_DETECTADA"
                
                m_limpia = limpiar_texto(m_archivo)
                excluir = any(x in m_limpia for x in ["API", "AP"])

                if not archivo_xlsx:
                    if excluir and m_limpia in LISTA_NEGRA_LIMPIA:
                        st.warning(f"🚫 Materia '{m_archivo.upper()}' excluida.")
                        st.session_state.df_crudo = pd.DataFrame(columns=['dni', 'nombre', 'materia'])
                    else:
                        df_f = pd.DataFrame()
                        df_f['dni'] = df_canvas['id_match']
                        df_f['nombre'] = df_canvas['student'].apply(extraer_primer_nombre)
                        df_f['materia'] = m_archivo.strip().upper()
                        st.session_state.df_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])
                else:
                    df_excel = pd.read_excel(archivo_xlsx)
                    df_excel.columns = df_excel.columns.str.strip().str.lower()
                    col_id_e = 'dni' if 'dni' in df_excel.columns else ('id_alumno' if 'id_alumno' in df_excel.columns else df_excel.columns[0])
                    df_excel['id_match'] = df_excel[col_id_e].apply(forzar_id_string)
                    df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                    
                    if excluir: df_excel = df_excel[~df_excel['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                    df_cruce = pd.merge(df_canvas, df_excel, on='id_match', how='inner')
                    
                    if opcion_base == "Base para HubSpot":
                        st.session_state.df_crudo = df_cruce[['email']].dropna().drop_duplicates()
                    else:
                        df_f = pd.DataFrame()
                        df_f['dni'] = df_cruce['id_match']
                        df_f['nombre'] = df_cruce['student'].apply(extraer_primer_nombre)
                        df_f['materia'] = m_archivo.strip().upper()
                        st.session_state.df_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])

                st.session_state.nombre_base = f"Base_{m_archivo.replace(' ', '_')}"

    # --- ZONA DE RENDERIZADO DE RESULTADOS ---
    if 'df_crudo' in st.session_state:
        df_final = st.session_state.df_crudo.copy()
        
        # El bloque de Meta aparece abajo solo para WhatsApp y si hay datos válidos
        if opcion_base == "Base para Whatsapp" and not df_final.empty and 'dni' in df_final.columns:
            st.divider()
            st.markdown("### 📝 Configuración opcional: Template de Meta")
            texto_template = st.text_area(
                "Pegá el contenido de tu plantilla de Meta aquí si deseas estructurar las columnas:",
                placeholder="Hola {{1}}, recordá entregar la actividad de {{2}}.",
                key="template_meta_seguro"
            )
            
            params = sorted(list(set(re.findall(r'\{\{(\d+)\}\}', texto_template))), key=int)
            if params:
                st.info(f"💡 Variables dinámicas detectadas: {len(params)}")
                cols_p = st.columns(min(len(params), 4))
                df_meta_build = pd.DataFrame()
                df_meta_build['dni'] = df_final['dni']
                
                for idx, p in enumerate(params):
                    with cols_p[idx % 4]:
                        seleccion = st.selectbox(f"Variable {{{{ {p} }}}}:", options=["dni", "nombre", "materia", "✍️ Texto Fijo"], key=f"sel_{p}")
                        if seleccion == "✍️ Texto Fijo":
                            txt_fijo = st.text_input(f"Texto fijo para {{{{ {p} }}}}:", key=f"fijo_{p}")
                            df_meta_build[f"param_{p}"] = txt_fijo
                        else:
                            df_meta_build[f"param_{p}"] = df_final[seleccion].values
                df_final = df_meta_build.copy()

        st.divider()
        total_filas = len(df_final)
        st.success(f"✅ ¡Estructura de datos lista! Se generaron {total_filas} registros.")
        
        st.write("### 📥 Descargar Archivos")
        output = io.BytesIO()
        if opcion_base == "Base para HubSpot":
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, header=True)
            st.download_button(label=f"📥 Descargar Base HubSpot ({total_filas} filas)", data=output.getvalue(), file_name=f"{st.session_state.nombre_base}-HUB.xlsx", type="primary")
        else:
            grid = st.columns(3)
            for i in range(0, total_filas, 100):
                chunk = df_final.iloc[i : i + 100]
                parte = (i // 100) + 1
                out_chunk = io.BytesIO()
                with pd.ExcelWriter(out_chunk, engine='xlsxwriter') as writer:
                    chunk.to_excel(writer, index=False, header=False)
                with grid[(i//100) % 3]:
                    st.download_button(label=f"📥 Parte {parte} ({len(chunk)} filas)", data=out_chunk.getvalue(), file_name=f"{st.session_state.nombre_base}-WSP_{parte}.xlsx")
        
        st.write("### 👁️ Vista previa de salida:")
        st.dataframe(df_final)

st.divider()
if st.button("➕ Nueva Carga"):
    reiniciar_aplicacion()
    st.rerun()
