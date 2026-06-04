import streamlit as st
import pandas as pd
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Generador de bases", page_icon="🛠️")

# --- FUNCIONES DE UTILERÍA ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False

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
opcion_base = st.radio("Selecciona el tipo de base que deseas generar:", ["Base para HubSpot", "Base para Whatsapp"], key="radio_opcion")

st.divider()

st.markdown("### 📥 Carga de archivos")
with st.expander("📌 Instrucciones de uso - LEER AQUÍ"):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        **Para generar la Base de HubSpot (Deudores Absolutos):**
        1. **Reporte de Canvas (CSV):** Subí el archivo de Canvas (puede ser el reporte de *Submissions* o el de *Calificaciones estándar*).
        2. **Base de Alumnos (XLSX):** Subí el Excel de todos los alumnos (ejemplo: el de invitaciones general). El sistema detectará el formato automáticamente y cruzará los datos.
        3. El archivo resultante incluirá encabezados y mantendrá registros múltiples si un alumno adeuda más de una materia.
        """)
    else:
        st.markdown("""
        **Para generar la Base de WhatsApp (Segmentada de a 100):**
        1. Subí ambos archivos (*Canvas CSV* y *Excel de Alumnos*) siguiendo el mismo criterio.
        2. El sistema calculará la lista de deudores y te presentará bloques de **descarga fraccionados de a 100 filas**.
        3. **Importante:** Estos archivos parciales para WhatsApp se descargan **sin encabezados** y anexan la columna de celular de forma automática si existe.
        """)

col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

if archivo_csv and archivo_xlsx:
    try:
        # Lectura tolerante a fallos de codificación y separadores (, o ;)
        contenido = archivo_csv.read()
        try:
            df_canvas = pd.read_csv(io.BytesIO(contenido), sep=',', engine='python', on_bad_lines='skip')
            if df_canvas.shape[1] <= 1: raise ValueError
        except:
            df_canvas = pd.read_csv(io.BytesIO(contenido), sep=';', engine='python', on_bad_lines='skip')
            
        df_excel = pd.read_excel(archivo_xlsx)
        
        # Normalización inicial de columnas
        df_canvas.columns = df_canvas.columns.str.strip()
        df_excel.columns = df_excel.columns.str.strip().str.lower()
        cols_canvas_lower = [c.lower() for c in df_canvas.columns]
        
        # --- BIFURCACIÓN DE DETECCIÓN DE FORMATO CANVAS ---
        es_submissions = 'sis user id' in cols_canvas_lower and 'assignment name' in cols_canvas_lower

        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado con éxito.**")
            df_canvas.columns = cols_canvas_lower
            df_canvas = df_canvas.dropna(subset=['sis user id'])
            
            # Normalización absoluta
            df_excel['id_match'] = df_excel['id_alumno'].apply(forzar_id_string)
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
                
                # Regla de exclusión automática de materias de lista negra en APIs
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
                
                columnas_salida = ['dni', 'nombre_final', 'materia_final']
                columnas_renombre = {'nombre_final': 'nombre', 'materia_final': 'materia'}
                
                if opcion_base == "Base para Whatsapp" and 'celular' in df_deudores.columns:
                    columnas_salida.insert(2, 'celular')
                    df_deudores['celular'] = df_deudores['celular'].fillna('').astype(str)
                
                st.session_state.df_resultado = df_deudores[columnas_salida].rename(columns=columnas_renombre).drop_duplicates(subset=['dni', 'materia'])
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        else:
            # --- CASO: REPORTE DE CALIFICACIONES ESTÁNDAR ---
            st.success("📂 **Reporte de Calificaciones estándar detectado con éxito.**")
            # Filtrar filas de estructura/totales de Canvas
            df_canvas = df_canvas[~df_canvas['Student'].str.contains('Points|Possible', case=False, na=False)]
            
            df_excel['id_match'] = df_excel['id_alumno'].apply(forzar_id_string)
            
            # Buscar dinámicamente la columna identificadora en Calificaciones estándar
            col_id_canvas = 'SIS Login ID' if 'SIS Login ID' in df_canvas.columns else ('SIS User ID' if 'SIS User ID' in df_canvas.columns else df_canvas.columns[1])
            df_canvas['id_match'] = df_canvas[col_id_canvas].apply(forzar_id_string)
            
            # Extraer el nombre tentativo de la materia desde el nombre del archivo cargado
            try:
                materia_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
            except:
                materia_archivo = "MATERIA_DETECTADA"
                
            materia_archivo_limpia = limpiar_texto(materia_archivo)
            
            # Intentar aplicar la lista negra de APIs si corresponde al archivo de calificaciones estándar
            aplicar_exclusion = any(x in materia_archivo_limpia for x in ["API", "AP"])
            
            if st.button("🔍 Calcular Deudores Reales (Calificaciones)", type="primary"):
                df_universo = df_excel.copy()
                
                if aplicar_exclusion:
                    df_universo = df_universo[~df_universo['materia_match'].isin(LISTA_NEGRA_LIMPIA)]
                
                # Al ser calificaciones estándar de un curso, cruzamos directo quienes Sí están en Canvas como alumnos válidos
                df_final = pd.merge(df_canvas, df_universo, on='id_match', how='inner')
                df_final['nombre_final'] = df_final['Student'].apply(extraer_primer_nombre)
                df_final['materia_final'] = materia_archivo.strip().upper()
                
                columnas_salida = ['dni', 'nombre_final', 'materia_final']
                columnas_renombre = {'nombre_final': 'nombre', 'materia_final': 'materia'}
                
                if opcion_base == "Base para Whatsapp" and 'celular' in df_final.columns:
                    columnas_salida.insert(2, 'celular')
                    df_final['celular'] = df_final['celular'].fillna('').astype(str)
                    
                st.session_state.df_resultado = df_final[columnas_salida].rename(columns=columnas_renombre).drop_duplicates()
                st.session_state.nombre_base = f"Base_{materia_archivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- RENDERIZADO DE RESULTADOS ---
        if st.session_state.procesado:
            df_res = st.session_state.df_resultado
            total_filas = len(df_res)
            
            st.success(f"✅ ¡Proceso completado! Se detectaron {total_filas} registros deudores aplicables.")
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
            
            st.write("### 👁️ Vista previa de deudores:")
            st.dataframe(df_res)

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")

st.divider()
if st.button("➕ Nueva Carga"):
    reiniciar_aplicacion()
    st.rerun()
