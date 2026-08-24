import streamlit as st
import pandas as pd
import io
import re
import zipfile

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️")

# --- MAPEO DE EQUIPOS POR CARRERA ---
MAPEO_EQUIPOS = {
    "IT": [
        "DATA SCIENCE", "SEGURIDAD INFORMÁTICA", "SEGURIDAD INFORMATICA",
        "CLOUD ADMINISTRATION", "PROGRAMACIÓN", "PROGRAMACION",
        "REDES INFORMÁTICAS", "REDES INFORMATICAS", "QA"
    ],
    "COMU": [
        "PLANIFICACIÓN Y ORGANIZACIÓN DE EVENTOS", "PLANIFICACION Y ORGANIZACION DE EVENTOS",
        "PERIODISMO Y NUEVAS TECNOLOGÍAS", "PERIODISMO Y NUEVAS TECNOLOGIAS",
        "MARKETING DIGITAL", "INBOUND MARKETING", "VENTA DIRECTA",
        "CUSTOMER EXPERIENCE", "GESTIÓN HOTELERA", "GESTION HOTELERA"
    ],
    "ADMIN": [
        "RELACIONES LABORALES", "SEGUROS", "GESTIÓN CONTABLE", "GESTION CONTABLE",
        "GESTIÓN DE LA EMPRESA AGRARIA", "GESTION DE LA EMPRESA AGRARIA"
    ]
}

def obtener_equipo(carrera):
    if pd.isna(carrera): return "OTROS"
    c_limpia = str(carrera).upper().strip()
    for equipo, lista_carreras in MAPEO_EQUIPOS.items():
        for c in lista_carreras:
            if c in c_limpia:
                return equipo
    return "OTROS"

# --- FUNCIONES DE UTILERÍA ---
def reiniciar_aplicacion():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

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
    """Convierte la nota a número flotante de forma segura para validar aprobados"""
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
    st.warning("⚠️ **Archivo intermedio requerido:** Para procesar un reporte de Canvas es obligatorio cargar también la Base de Alumnos (XLSX) para obtener los datos de contacto y cohorte.")

# Prelectura del Excel para extraer períodos dinámicos
if archivo_xlsx:
    try:
        df_excel_prelectura = pd.read_excel(archivo_xlsx)
        df_excel_prelectura.columns = df_excel_prelectura.columns.str.strip()
        col_periodo = [c for c in df_excel_prelectura.columns if c.lower() == 'periodo inicio carrera']
        if col_periodo:
            periodos_disponibles = sorted(df_excel_prelectura[col_periodo[0]].dropna().astype(str).unique())
    except Exception as e:
        st.error(f"Error al pre-leer el archivo Excel: {e}")

# Prelectura del Canvas (si existe)
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


# --- INTERFAZ DINÁMICA SEGÚN EL MODO ---
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
    
    if modo_trabajo == "ACCIONES_DIARIAS":
        actividad_objetivo = st.selectbox(
            "Selecciona la actividad a reclamar:", 
            ["Módulo 1 - Autoevaluación", "Módulo 2 - Autoevaluación", "Módulo 3 - Autoevaluación", "Módulo 4 - Autoevaluación"]
        )
        materias_seleccionadas = []
    else:
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

    # --- CONFIGURACIÓN DEL TEMPLATE WHATSAPP ---
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

    # =======================================================
    # --- PROCESAMIENTO AL PRESIONAR EL BOTÓN ---
    # =======================================================
    if st.button("🔍 Calcular Deudores Reales", type="primary"):
        
        # 1. Carga del Excel Base
        df_excel = pd.read_excel(archivo_xlsx)
        df_excel.columns = df_excel.columns.str.strip()
        
        # --- NUEVAS REGLAS DE FILTRADO EN EXCEL ---
        # A) estado_baja_definitiva: solo incluir vacías
        col_baja = [c for c in df_excel.columns if c.lower() == 'estado_baja_definitiva']
        if col_baja:
            c_b = col_baja[0]
            df_excel = df_excel[df_excel[c_b].isna() | (df_excel[c_b].astype(str).str.strip() == '')]

        # B) homologada: solo incluir vacías
        col_homo = [c for c in df_excel.columns if c.lower() == 'homologada']
        if col_homo:
            c_h = col_homo[0]
            df_excel = df_excel[df_excel[c_h].isna() | (df_excel[c_h].astype(str).str.strip() == '')]

        # C) Filtro de Cohorte (NI / RI)
        if periodo_actual_sel:
            col_p_carrera = [c for c in df_excel.columns if c.lower() == 'periodo inicio carrera']
            if col_p_carrera:
                c_p = col_p_carrera[0]
                df_excel[c_p] = df_excel[c_p].astype(str).str.strip()
                
                if filtro_ingreso == "Solo Nuevos Ingresantes (NI)":
                    df_excel = df_excel[df_excel[c_p] == str(periodo_actual_sel).strip()]
                elif filtro_ingreso == "Solo Reingresantes (RI)":
                    df_excel = df_excel[df_excel[c_p] != str(periodo_actual_sel).strip()]

        # D) Identificación de Equipo según columna 'carrera'
        col_carrera = [c for c in df_excel.columns if c.lower() == 'carrera']
        if col_carrera:
            c_car = col_carrera[0]
            df_excel['equipo'] = df_excel[c_car].apply(obtener_equipo)
        else:
            df_excel['equipo'] = 'OTROS'

        # =======================================================
        # --- MODO ACCIONES DIARIAS (SOLO EXCEL) ---
        # =======================================================
        if modo_trabajo == "ACCIONES_DIARIAS":
            mapa_columnas_ae = {
                "Módulo 1 - Autoevaluación": "nota_mod_1",
                "Módulo 2 - Autoevaluación": "nota_mod_2",
                "Módulo 3 - Autoevaluación": "nota_mod_3",
                "Módulo 4 - Autoevaluación": "nota_mod_4"
            }
            columna_nota_objetivo = mapa_columnas_ae[actividad_objetivo]
            
            if columna_nota_objetivo in df_excel.columns:
                df_excel['nota_eval_num'] = df_excel[columna_nota_objetivo].apply(forzar_score_float)
                df_deudores = df_excel[df_excel[columna_nota_objetivo].isna() | (df_excel['nota_eval_num'] < 60.0)].copy()
            else:
                st.error(f"❌ No se encontró la columna '{columna_nota_objetivo}' en tu archivo Excel.")
                st.stop()
                
            df_deudores.columns = df_deudores.columns.str.lower()
            
            col_n = 'nombres' if 'nombres' in df_deudores.columns else df_deudores.columns[2]
            df_deudores['nombre'] = df_deudores[col_n].apply(extraer_primer_nombre)
            df_deudores['materia'] = df_deudores['materia'].astype(str).str.strip().str.upper()
            
            col_dni_excel = 'dni' if 'dni' in df_deudores.columns else 'documento'
            df_deudores['dni'] = df_deudores[col_dni_excel].apply(forzar_id_string)
            
            df_resultado_crudo = df_deudores.copy()
            st.session_state.nombre_base = f"Acciones_Diarias_{actividad_objetivo.replace(' ', '_')}"

        # =======================================================
        # --- MODO TRADICIONAL CRUCE (CANVAS + EXCEL) ---
        # =======================================================
        else:
            df_canvas = df_canvas_raw.copy()
            df_canvas.columns = cols_lower
            df_excel.columns = df_excel.columns.str.lower()

            # --- CASO A: SUBMISSIONS ---
            if es_submissions:
                df_canvas = df_canvas.dropna(subset=['canvas user id'])
                df_canvas['id_match'] = df_canvas['canvas user id'].apply(forzar_id_string)
                df_canvas['materia_match'] = df_canvas['course name'].apply(limpiar_texto)
                df_canvas['actividad_limpia'] = df_canvas['assignment name'].apply(homologar_actividad)

                if materias_seleccionadas:
                    df_canvas = df_canvas[df_canvas['course name'].isin(materias_seleccionadas)]
                if "API" in actividad_objetivo.upper():
                    df_canvas = df_canvas[~df_canvas['materia_match'].isin(LISTA_NEGRA_LIMPIA)]

                if "AE" in actividad_objetivo.upper():
                    df_canvas['score_num'] = df_canvas['score'].apply(forzar_score_float)
                    entregas_validas = df_canvas[
                        (df_canvas['actividad_limpia'] == actividad_objetivo) & 
                        (df_canvas['workflow state'].isin(['submitted', 'graded'])) &
                        (df_canvas['score_num'] >= 60.0)
                    ].copy()
                else:
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
                
                df_resultado_crudo = df_deudores.copy()
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"

            # --- CASO B: CALIFICACIONES ---
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
                col_dni_excel = 'dni' if 'dni' in df_cruce.columns else 'documento'
                
                df_cruce['dni'] = df_cruce[col_dni_excel].apply(forzar_id_string)
                df_cruce['nombre'] = df_cruce['student'].apply(extraer_primer_nombre)
                df_cruce['materia'] = m_archivo.strip().upper()
                
                df_resultado_crudo = df_cruce.copy()
                st.session_state.nombre_base = f"Base_{m_archivo.replace(' ', '_')}"

        # =======================================================
        # --- CONSOLIDACIÓN POR ALUMNO (DOS MATERIAS) ---
        # =======================================================
        # Si un alumno debe en más de una materia, se agrupa y se asigna "EN AMBAS MATERIAS"
        if 'dni' in df_resultado_crudo.columns and 'materia' in df_resultado_crudo.columns:
            conteo_materias = df_resultado_crudo.groupby('dni')['materia'].transform('nunique')
            df_resultado_crudo.loc[conteo_materias >= 2, 'materia'] = "EN AMBAS MATERIAS"

        # --- LIMPIEZA ABSOLUTA Y FORMATEO DE SALIDA ---
        if 'nombre' in df_resultado_crudo.columns:
            df_resultado_crudo['nombre'] = df_resultado_crudo['nombre'].apply(limpiar_caracteres_especiales)
        if 'materia' in df_resultado_crudo.columns:
            df_resultado_crudo['materia'] = df_resultado_crudo['materia'].apply(limpiar_caracteres_especiales)
        if 'email' in df_resultado_crudo.columns:
            df_resultado_crudo['email'] = df_resultado_crudo['email'].apply(limpiar_caracteres_especiales)

        # Retener columnas base necesarias
        df_resultado_crudo['actividad'] = limpiar_caracteres_especiales(actividad_objetivo)

        if opcion_base == "Base para HubSpot":
            cols_salida = ['email', 'equipo']
            df_final_pre = df_resultado_crudo.dropna(subset=['email']).drop_duplicates(subset=['email'])
        else:
            if params_detectados:
                df_meta_build = pd.DataFrame()
                df_meta_build['dni'] = df_resultado_crudo['dni']
                
                for p in params_detectados:
                    tipo, valor = dict_mapeo_params[p]
                    if tipo == "fijo":
                        df_meta_build[f"param_{p}"] = limpiar_caracteres_especiales(valor)
                    else:
                        df_meta_build[f"param_{p}"] = df_resultado_crudo[valor].values
                
                df_meta_build['equipo'] = df_resultado_crudo['equipo'].values
                df_final_pre = df_meta_build.drop_duplicates(subset=['dni'])
            else:
                df_final_pre = df_resultado_crudo[['dni', 'nombre', 'materia', 'actividad', 'equipo']].drop_duplicates(subset=['dni'])

        sufijo_cohorte = "_NI" if filtro_ingreso == "Solo Nuevos Ingresantes (NI)" else ("_RI" if filtro_ingreso == "Solo Reingresantes (RI)" else "")
        st.session_state.nombre_base += sufijo_cohorte
        st.session_state.df_final_procesado = df_final_pre.copy()
        st.session_state.opcion_base_guardada = opcion_base

    # --- ZONA DE RENDERIZADO DE RESULTADOS POR EQUIPO ---
    if 'df_final_procesado' in st.session_state:
        df_final = st.session_state.df_final_procesado.copy()
        total_filas = len(df_final)
        opcion_guardada = st.session_state.get('opcion_base_guardada', opcion_base)
        
        st.divider()
        st.success(f"✅ ¡Estructura de datos lista! Se generaron {total_filas} registros unificados por alumno y filtrados.")
        
        st.write("### 📥 Descargar Archivos por Equipo")
        
        # Agrupar por equipo (IT, COMU, ADMIN, OTROS)
        equipos_presentes = df_final['equipo'].unique()
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for eq in equipos_presentes:
                df_eq = df_final[df_final['equipo'] == eq].drop(columns=['equipo'])
                if df_eq.empty: continue
                
                if opcion_guardada == "Base para HubSpot":
                    eq_buffer = io.BytesIO()
                    with pd.ExcelWriter(eq_buffer, engine='xlsxwriter') as writer:
                        df_eq.to_excel(writer, index=False, header=True)
                    nombre_ar = f"{eq}_{st.session_state.nombre_base}-HUB.xlsx"
                    zip_file.writestr(nombre_ar, eq_buffer.getvalue())
                else:
                    for i in range(0, len(df_eq), 100):
                        chunk = df_eq.iloc[i : i + 100]
                        parte = (i // 100) + 1
                        chunk_buffer = io.BytesIO()
                        with pd.ExcelWriter(chunk_buffer, engine='xlsxwriter') as writer:
                            chunk.to_excel(writer, index=False, header=False)
                        nombre_ar = f"{eq}_{st.session_state.nombre_base}-WSP_{parte}.xlsx"
                        zip_file.writestr(nombre_ar, chunk_buffer.getvalue())

        st.download_button(
            label="📥 Descargar TODOS los Archivos de Equipos (.ZIP)",
            data=zip_buffer.getvalue(),
            file_name=f"{st.session_state.nombre_base}-TODOS_LOS_EQUIPOS.zip",
            type="primary",
            use_container_width=True
        )
        
        st.write("---")
        st.write("📂 *Archivos generados de manera individual por equipo:*")
        
        cols_eq = st.columns(len(equipos_presentes))
        for idx, eq in enumerate(equipos_presentes):
            df_eq = df_final[df_final['equipo'] == eq].drop(columns=['equipo'])
            with cols_eq[idx]:
                st.markdown(f"#### 👥 Equipo: {eq}")
                st.caption(f"Total registros: {len(df_eq)}")
                
                if opcion_guardada == "Base para HubSpot":
                    out_eq = io.BytesIO()
                    with pd.ExcelWriter(out_eq, engine='xlsxwriter') as writer:
                        df_eq.to_excel(writer, index=False, header=True)
                    st.download_button(
                        label=f"📥 {eq} - Base HubSpot",
                        data=out_eq.getvalue(),
                        file_name=f"{eq}_{st.session_state.nombre_base}-HUB.xlsx",
                        key=f"btn_{eq}_hub"
                    )
                else:
                    for i in range(0, len(df_eq), 100):
                        chunk = df_eq.iloc[i : i + 100]
                        parte = (i // 100) + 1
                        out_chunk = io.BytesIO()
                        with pd.ExcelWriter(out_chunk, engine='xlsxwriter') as writer:
                            chunk.to_excel(writer, index=False, header=False)
                        st.download_button(
                            label=f"📦 {eq} - Parte {parte} ({len(chunk)} filas)",
                            data=out_chunk.getvalue(),
                            file_name=f"{eq}_{st.session_state.nombre_base}-WSP_{parte}.xlsx",
                            key=f"btn_{eq}_wsp_{parte}"
                        )

        st.write("### 👁️ Vista previa unificada de salida:")
        st.dataframe(df_final)

st.divider()
if st.button("➕ Nueva Carga"):
    reiniciar_aplicacion()
