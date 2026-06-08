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

st.markdown("### 📥 Carga de archivos")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

archivos_listos = False
df_excel_prelectura = None
periodos_disponibles = []

# Validación previa y lectura para capturar períodos
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

    # Requerir obligatoriamente el Excel si es Submissions o si queremos extraer los períodos de carrera
    if archivo_xlsx:
        try:
            df_excel_prelectura = pd.read_excel(archivo_xlsx)
            df_excel_prelectura.columns = df_excel_prelectura.columns.str.strip()
            # Buscar la columna ignorando mayúsculas/minúsculas
            col_periodo = [c for c in df_excel_prelectura.columns if c.lower() == 'periodo inicio carrera']
            if col_periodo:
                periodos_disponibles = sorted(df_excel_prelectura[col_periodo[0]].dropna().astype(str).unique())
        except Exception as e:
            st.error(f"Error al pre-leer el archivo Excel: {e}")

    # Validaciones de interfaz
    if es_submissions and not archivo_xlsx:
        st.warning("⚠️ **Archivo intermedio requerido:** Detectamos un reporte de Submissions. Por favor, carga la Base de Alumnos (XLSX) para activar los filtros y poder procesar.")
    elif not es_submissions and not archivo_xlsx:
        st.warning("⚠️ **Archivo intermedio requerido:** Para procesar Calificaciones y habilitar los filtros dinámicos (Períodos, HubSpot, etc.), es obligatorio cargar la Base de Alumnos (XLSX).")
    else:
        archivos_listos = True

    # --- SI LOS ARCHIVOS ESTÁN LISTOS, SE DESPLEGAN LOS FILTROS PREVIOS Y EL TIPO DE BASE ---
    if archivos_listos:
        st.divider()
        st.markdown("### 🎯 Filtros Previos de Cohorte (NI / RI)")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if periodos_disponibles:
                # Se preselecciona el último período indexado (usualmente el más nuevo)
                periodo_actual_sel = st.selectbox("1. Selecciona el Período / Bimestre Actual:", options=periodos_disponibles, index=len(periodos_disponibles)-1)
            else:
                st.warning("⚠️ No se encontró la columna 'Periodo inicio Carrera' en el Excel.")
                periodo_actual_sel = None
        
        with col_f2:
            filtro_ingreso = st.selectbox(
                "2. Tipo de Alumno a considerar:",
                options=["Todos los alumnos (Sin filtro)", "Solo Nuevos Ingresantes (NI)", "Solo Reingresantes (RI)"]
            )

        st.divider()
        st.markdown("### ⚙️ Configuración del Destino")
        opcion_base = st.radio(
            "Selecciona el tipo de base que deseas generar:", 
            ["Base para HubSpot", "Base para Whatsapp"], 
            key="radio_opcion"
        )

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

            # Carga y estandarización del Excel base
            df_excel = pd.read_excel(archivo_xlsx)
            df_excel.columns = df_excel.columns.str.strip()
            
            # --- NUEVA FUNCIONALIDAD: FILTRADO PREVIO NI / RI ---
            if periodo_actual_sel and idx_m != None:
                col_p_carrera = [c for c in df_excel.columns if c.lower() == 'periodo inicio carrera'][0]
                df_excel[col_p_carrera] = df_excel[col_p_carrera].astype(str).str.strip()
                
                if filtro_ingreso == "Solo Nuevos Ingresantes (NI)":
                    df_excel = df_excel[df_excel[col_p_carrera] == str(periodo_actual_sel).strip()]
                elif filtro_ingreso == "Solo Reingresantes (RI)":
                    df_excel = df_excel[df_excel[col_p_carrera] != str(periodo_actual_sel).strip()]

            # Estandarizamos minúsculas para el proceso interno
            df_excel.columns = df_excel.columns.str.lower()

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

                col_id_e = 'dni' if 'dni' in df_excel.columns else ('id_alumno' if 'id_alumno' in df_excel.columns else df_excel.columns[0])
                df_excel['id_match'] = df_excel[col_id_e].apply(forzar_id_string)
                df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                
                if excluir: df_excel = df_excel[~df_excel['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                
                df_cruce = pd.merge(df_canvas, df_excel, on='id_match', how='inner')
                
                if opcion_base == "Base para HubSpot":
                    df_resultado_crudo = df_cruce[['email']].dropna().drop_duplicates()
                else:
                    df_f = pd.DataFrame()
                    df_f['dni'] = df_cruce['id_match']
                    df_f['nombre'] = df_cruce['student'].apply(extraer_primer_nombre)
                    df_f['materia'] = m_archivo.strip().upper()
                    df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])

                st.session_state.nombre_base = f"Base_{m_archivo.replace(' ', '_')}"

            # =======================================================
            # --- APLICACIÓN DE LIMPIEZA ABSOLUTA DE CARACTERES ---
            # =======================================================
            if 'nombre' in df_resultado_crudo.columns:
                df_resultado_crudo['nombre'] = df_resultado_crudo['nombre'].apply(limpiar_caracteres_especiales)
            if 'materia' in df_resultado_crudo.columns:
                df_resultado_crudo['materia'] = df_resultado_crudo['materia'].apply(limpiar_caracteres_especiales)
            if 'email' in df_resultado_crudo.columns:
                df_resultado_crudo['email'] = df_resultado_crudo['email'].apply(limpiar_caracteres_especiales)

            if opcion_base == "Base para HubSpot":
                st.session_state.df_final_procesado = df_resultado_crudo.copy()
            else:
                df_resultado_crudo['actividad'] = limpiar_caracteres_especiales(actividad_objetivo)
                
                if params_detectados:
                    df_meta_build = pd.DataFrame()
                    df_meta_build['dni'] = df_resultado_crudo['dni']
                    
                    for p in params_detectados:
                        tipo, valor = dict_mapeo_params[p]
                        if tipo == "fijo":
                            df_meta_build[f"param_{p}"] = limpiar_caracteres_especiales(valor)
                        else:
                            df_meta_build[f"param_{p}"] = df_resultado_crudo[valor].values
                    st.session_state.df_final_procesado = df_meta_build.copy()
                else:
                    st.session_state.df_final_procesado = df_resultado_crudo[['dni', 'nombre', 'materia', 'actividad']].copy()
            
            # Guardamos sufijo en nombre del archivo indicando el filtro para no pisarse
            sufijo_cohorte = "_NI" if filtro_ingreso == "Solo Nuevos Ingresantes (NI)" else ("_RI" if filtro_ingreso == "Solo Reingresantes (RI)" else "")
            st.session_state.nombre_base += sufijo_cohorte
            st.session_state.opcion_base_guardada = opcion_base
            st.rerun()

    # --- ZONA DE RENDERIZADO DE RESULTADOS INDEPENDIENTE ---
    if 'df_final_procesado' in st.session_state:
        df_final = st.session_state.df_final_procesado.copy()
        total_filas = len(df_final)
        opcion_guardada = st.session_state.get('opcion_base_guardada', opcion_base)
        
        st.divider()
        st.success(f"✅ ¡Estructura de datos lista! Se generaron {total_filas} registros filtrados y limpios.")
        
        st.write("### 📥 Descargar Archivos")
        output = io.BytesIO()
        if opcion_guardada == "Base para HubSpot":
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
