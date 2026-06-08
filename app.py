import streamlit as st
import pandas as pd
import io
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️")

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
        1. **Reporte de Canvas (CSV):** Subí el archivo de Canvas.
        2. **Base de Alumnos (XLSX):** Subí el Excel de invitaciones. Es obligatorio para extraer el correo.
        3. El archivo resultante contendrá **únicamente la columna `email`** con encabezado.
        """)
    else:
        st.markdown("""
        **Para generar la Base de WhatsApp (Segmentada de a 100):**
        1. **Reporte de Canvas (CSV):** Subí tu archivo de Canvas.
        2. **Base de Alumnos (XLSX - Opcional para Calificaciones):** Permite cruzar datos más completos.
        3. El archivo resultante organizará las columnas como **`dni`, `nombre`, `materia`** siempre sin encabezados.
        """)

col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX - Opcional para Calificaciones en WhatsApp)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

# --- ENTRADA DE TEMPLATE DE META (SOLO PARA WHATSAPP) ---
config_template = {}
if opcion_base == "Base para Whatsapp" and archivo_csv:
    st.markdown("### 📝 Configuración de Template de Meta")
    texto_template = st.text_area(
        "Pegá acá el contenido de tu plantilla de Meta:",
        placeholder="Hola {{1}}, recordá entregar la actividad de {{2}} para evitar quedar libre."
    )
    
    params = sorted(list(set(re.findall(r'\{\{(\d+)\}\}', texto_template))), key=int)
    
    if params:
        st.info(f"💡 Se detectaron {len(params)} variables dinámicas. Definí el mapeo de columnas para el archivo resultante:")
        cols_p = st.columns(min(len(params), 4))
        for idx, p in enumerate(params):
            with cols_p[idx % 4]:
                seleccion = st.selectbox(
                    f"Variable {{{{ {p} }}}}:",
                    options=["dni", "nombre", "materia", "✍️ Texto Fijo"],
                    key=f"param_meta_{p}"
                )
                val_manual = ""
                if seleccion == "✍️ Texto Fijo":
                    val_manual = st.text_input(f"Ingresá el texto fijo para {{{{ {p} }}}}:", key=f"manual_meta_{p}")
                config_template[p] = {"tipo": seleccion, "manual": val_manual}
        st.divider()

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
        df_canvas.columns = df_canvas.columns.str.strip()
        cols_canvas_lower = [c.lower() for c in df_canvas.columns]
        
        # Determinar tipo de reporte de Canvas
        es_submissions = 'sis user id' in cols_canvas_lower and 'assignment name' in cols_canvas_lower

        # ==========================================
        # --- CASO 1: REPORTE DE ENTREGAS (SUBMISSIONS) ---
        # ==========================================
        if es_submissions:
            if not archivo_xlsx:
                st.warning("⚠️ El reporte detectado es de **Submissions (Entregas)**. Para este formato, el archivo '2. Base de Alumnos (XLSX)' es obligatorio para poder calcular las exclusiones.")
            else:
                st.success("📂 **Reporte de Entregas (Submissions) detectado con éxito.**")
                df_excel = pd.read_excel(archivo_xlsx)
                df_excel.columns = df_excel.columns.str.strip().str.lower()
                df_canvas.columns = cols_canvas_lower
                df_canvas = df_canvas.dropna(subset=['sis user id'])
                
                col_id_excel = 'id_alumno' if 'id_alumno' in df_excel.columns else 'dni'
                df_excel['id_match'] = df_excel[col_id_excel].apply(forzar_id_string)
                df_canvas['id_match'] = df_canvas['sis user id'].apply(forzar_id_string)
                
                df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                df_canvas['materia_match'] = df_canvas['course name'].apply(limpiar_texto)
                df_canvas['actividad_limpia'] = df_canvas['assignment name'].apply(homologar_actividad)
                
                materias_disponibles = sorted(df_excel['materia'].dropna().unique())
                materias_seleccionadas = st.multiselect("1. Seleccionar Materias a evaluar (Vacío = Todas):", materias_disponibles)
                actividad_objetivo = st.selectbox("2. Selecciona la actividad a reclamar:", ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"])
                
                if st.button("🔍 Calcular Deudores Reales", type="primary"):
                    df_universo = df_excel.copy()
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
                    df_deudores['nombre_final'] = df_deudores[col_nombre].apply(extraer_primer_nombre)
                    df_deudores['materia_final'] = df_deudores['materia'].astype(str).str.strip().str.upper()
                    
                    if 'dni' not in df_deudores.columns:
                        df_deudores['dni'] = df_deudores['id_match']

                    if opcion_base == "Base para HubSpot":
                        st.session_state.df_resultado = df_deudores[['email']].dropna().drop_duplicates()
                    else:
                        if not materias_seleccionadas:
                            conteos = df_deudores['dni'].value_counts()
                            dnis_multiples = conteos[conteos >= 2].index
                            df_deudores.loc[df_deudores['dni'].isin(dnis_multiples), 'materia_final'] = "DOS MATERIAS"
                        
                        df_final_wsp = df_deudores.rename(columns={'nombre_final': 'nombre', 'materia_final': 'materia'}).drop_duplicates(subset=['dni', 'materia']).copy()
                        
                        if config_template:
                            columnas_salida = ['dni']
                            for p in sorted(config_template.keys(), key=int):
                                col_p = f"param_{p}"
                                if config_template[p]["tipo"] == "✍️ Texto Fijo":
                                    df_final_wsp[col_p] = config_template[p]["manual"]
                                else:
                                    df_final_wsp[col_p] = df_final_wsp[config_template[p]["tipo"]].values
                                columnas_salida.append(col_p)
                            st.session_state.df_resultado = df_final_wsp[columnas_salida]
                        else:
                            st.session_state.df_resultado = df_final_wsp[['dni', 'nombre', 'materia']]
                    
                    st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                    st.session_state.procesado = True

        # ==========================================
        # --- CASO 2: REPORTE DE CALIFICACIONES ESTÁNDAR ---
        # ==========================================
        else:
            st.success("📂 **Reporte de Calificaciones estándar detectado con éxito.**")
            df_canvas = df_canvas[~df_canvas['Student'].str.contains('Points|Possible', case=False, na=False)]
            
            col_id_canvas = 'SIS Login ID' if 'SIS Login ID' in df_canvas.columns else ('SIS User ID' if 'SIS User ID' in df_canvas.columns else df_canvas.columns[1])
            df_canvas['id_match'] = df_canvas[col_id_canvas].apply(forzar_id_string)
            
            try:
                materia_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
            except:
                materia_archivo = "MATERIA_DETECTADA"
                
            materia_archivo_limpia = limpiar_texto(materia_archivo)
            aplicar_exclusion = any(x in materia_archivo_limpia for x in ["API", "AP"])
            
            ejecutar_calculo = False
            if opcion_base == "Base para HubSpot" and not archivo_xlsx:
                st.warning("⚠️ Para generar una base estructurada para **HubSpot**, es necesario que cargues el Excel para mapear la columna de Email obligatoria.")
            else:
                if st.button("🔍 Calcular Deudores Reales (Calificaciones)", type="primary"):
                    ejecutar_calculo = True

            if ejecutar_calculo:
                if not archivo_xlsx:
                    if aplicar_exclusion and materia_archivo_limpia in LISTA_NEGRA_LIMPIA:
                        st.warning(f"🚫 La materia '{materia_archivo.upper()}' está en la lista de exclusión de APIs.")
                        df_final_wsp = pd.DataFrame(columns=['dni', 'nombre', 'materia'])
                    else:
                        df_canvas['dni'] = df_canvas['id_match']
                        df_canvas['nombre'] = df_canvas['Student'].apply(extraer_primer_nombre)
                        df_canvas['materia'] = materia_archivo.strip().upper()
                        df_final_wsp = df_canvas[['dni', 'nombre', 'materia']].drop_duplicates().copy()
                    
                    if opcion_base == "Base para Whatsapp" and config_template and not df_final_wsp.empty:
                        columnas_salida = ['dni']
                        for p in sorted(config_template.keys(), key=int):
                            col_p = f"param_{p}"
                            if config_template[p]["tipo"] == "✍️ Texto Fijo":
                                df_final_wsp[col_p] = config_template[p]["manual"]
                            else:
                                df_final_wsp[col_p] = df_final_wsp[config_template[p]["tipo"]].values
                            columnas_salida.append(col_p)
                        st.session_state.df_resultado = df_final_wsp[columnas_salida]
                    else:
                        st.session_state.df_resultado = df_final_wsp
                else:
                    df_excel = pd.read_excel(archivo_xlsx)
                    df_excel.columns = df_excel.columns.str.strip().str.lower()
                    
                    col_id_excel = 'dni' if 'dni' in df_excel.columns else ('id_alumno' if 'id_alumno' in df_excel.columns else df_excel.columns[0])
                    df_excel['id_match'] = df_excel[col_id_excel].apply(forzar_id_string)
                    df_excel['materia_match'] = df_excel['materia'].apply(limpiar_texto)
                    
                    df_universo = df_excel.copy()
                    if aplicar_exclusion:
                        df_universo = df_universo[~df_universo['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                    
                    df_cruce = pd.merge(df_canvas, df_universo, on='id_match', how='inner')
                    df_cruce['dni_final'] = df_cruce['id_match']  
                    df_cruce['nombre_final'] = df_cruce['Student'].apply(extraer_primer_nombre)
                    df_cruce['materia_final'] = materia_archivo.strip().upper()
                    
                    if opcion_base == "Base para HubSpot":
                        st.session_state.df_resultado = df_cruce[['email']].dropna().drop_duplicates()
                    else:
                        df_final_wsp = df_cruce.rename(columns={'dni_final': 'dni', 'nombre_final': 'nombre', 'materia_final': 'materia'}).drop_duplicates(subset=['dni', 'materia']).copy()
                        
                        if config_template:
                            columnas_salida = ['dni']
                            for p in sorted(config_template.keys(), key=int):
                                col_p = f"param_{p}"
                                if config_template[p]["tipo"] == "✍️ Texto Fijo":
                                    df_final_wsp[col_p] = config_template[p]["manual"]
                                else:
                                    df_final_wsp[col_p] = df_final_wsp[config_template[p]["tipo"]].values
                                columnas_salida.append(col_p)
                            st.session_state.df_resultado = df_final_wsp[columnas_salida]
                        else:
                            st.session_state.df_resultado = df_final_wsp[['dni', 'nombre', 'materia']]
                
                st.session_state.nombre_base = f"Base_{materia_archivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- RENDERIZADO Y DESCARGA DE RESULTADOS ---
        if st.session_state.procesado and 'df_resultado' in st.session_state:
            df_res = st.session_state.df_resultado
            total_filas = len(df_res)
            
            st.success(f"✅ ¡Proceso completado! Se detectaron {total_filas} registros válidos.")
            st.write("### 📥 Descargar Archivos Excel")
            
            output = io.BytesIO()
            if opcion_base == "Base para HubSpot":
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_res.to_excel(writer, index=False, header=True)
                st.download_button(label=f"📥 Descargar Base HubSpot ({total_filas} filas)", data=output.getvalue(), file_name=f"{st.session_state.nombre_base}-HUB.xlsx", type="primary")
            else:
                grid = st.columns(3)
                for i in range(0, total_filas, 100):
                    chunk = df_res.iloc[i : i + 100]
                    parte = (i // 100) + 1
                    out_chunk = io.BytesIO()
                    with pd.ExcelWriter(out_chunk, engine='xlsxwriter') as writer:
                        chunk.to_excel(writer, index=False, header=False)
                    with grid[(i//100) % 3]:
                        st.download_button(label=f"📥 Parte {parte} ({len(chunk)} filas)", data=out_chunk.getvalue(), file_name=f"{st.session_state.nombre_base}-WSP_{parte}.xlsx")
            
            st.write("### 👁️ Vista previa de los datos generados:")
            st.dataframe(df_res)

st.divider()
if st.button("➕ Nueva Carga"):
    reiniciar_aplicacion()
    st.rerun()
