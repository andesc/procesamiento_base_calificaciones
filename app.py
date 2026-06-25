import streamlit as st
import pandas as pd
import io

# Configuración de página
st.set_page_config(page_title="Procesador de Reportes Canvas", layout="wide")
st.title("📊 Procesador de Reportes de Alumnos - Canvas")

# Funciones de ayuda y limpieza
def forzar_id_string(val):
    if pd.isna(val):
        return ""
    try:
        # Quitamos espacios y parte decimal si se importó como float
        s = str(val).strip().split('.')[0]
        return s
    except:
        return str(val).strip()

def extraer_primer_nombre(nombre_completo):
    if pd.isna(nombre_completo):
        return ""
    # Si viene en formato "Apellido, Nombre"
    if "," in str(nombre_completo):
        partes = str(nombre_completo).split(",")
        nombre = partes[1].strip()
    else:
        nombre = str(nombre_completo).strip()
    # Retornamos solo la primera palabra del nombre
    return nombre.split(" ")[0].upper()

def limpiar_texto(txt):
    if not txt:
        return ""
    import unicodedata
    # Pasar a minúsculas, quitar acentos y espacios extras
    txt = str(txt).lower().strip()
    txt = "".join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
    return txt

# Constantes de exclusión
LISTA_NEGRA_LIMPIA = ["practica profesional", "seminario de practica", "taller de insercion"]

# Interfaz de Usuario
col1, col2 = st.columns(2)

with col1:
    archivo_csv = st.file_uploader("1. Subir reporte de Canvas (.csv)", type=["csv"])
with col2:
    archivo_xlsx = st.file_uploader("2. Subir Base de Alumnos (.xlsx) [Opcional]", type=["xlsx"])

opcion_base = st.radio("Seleccionar tipo de salida:", ["Base para WhatsApp", "Base para HubSpot"], horizontal=True)

if archivo_csv:
    if st.button("🔍 Calcular Deudores Reales"):
        # Detectar codificación leyendo los primeros bytes
        bytes_data = archivo_csv.read()
        archivo_csv.seek(0)
        
        encoding_detectado = 'utf-8'
        try:
            bytes_data.decode('utf-8')
        except UnicodeDecodeError:
            encoding_detectado = 'latin1'
            
        # Intentar leer el CSV de Canvas
        try:
            df_canvas_raw = pd.read_csv(archivo_csv, encoding=encoding_detectado)
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {e}")
            st.stop()
            
        cols_lower = [c.lower() for c in df_canvas_raw.columns]
        df_canvas_raw.columns = cols_lower

        # ------------------------------------------------------------------
        # CASO A: Reporte de Entregas (proserv_student_submissions_csv)
        # ------------------------------------------------------------------
        if 'canvas user id' in cols_lower and 'assignment name' in cols_lower:
            st.info("📝 Reporte de entregas (Submissions) detectado.")
            
            # Limpieza básica
            df_canvas = df_canvas_raw[df_canvas_raw['user name'].notna()]
            df_canvas = df_canvas[~df_canvas['user name'].str.contains('Points|Possible|solo lectura', case=False, na=False)]
            
            col_dni_canvas = 'sis user id' if 'sis user id' in cols_lower else 'canvas user id'
            df_canvas['id_match'] = df_canvas[col_dni_canvas].apply(forzar_id_string)
            
            # Identificar deudores (entregas en estado 'unsubmitted')
            df_deudores = df_canvas[df_canvas['workflow state'].str.lower() == 'unsubmitted'].copy()
            
            # Filtrar materias excluidas de manera global
            df_deudores['materia_limpia'] = df_deudores['course name'].apply(limpiar_texto)
            df_deudores = df_deudores[~df_deudores['materia_limpia'].astype(str).apply(lambda m: any(x in m for x in LISTA_NEGRA_LIMPIA))]
            
            if not archivo_xlsx:
                # Si no hay Excel, armamos base cruda directo de Canvas
                df_f = pd.DataFrame()
                df_f['dni'] = df_deudores['id_match']
                df_f['nombre'] = df_deudores['user name'].apply(extraer_primer_nombre)
                df_f['materia'] = df_deudores['course name'].str.strip().upper()
                df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])
                st.session_state.nombre_base = "Base_Deudores_Submissions"
            else:
                df_excel = pd.read_excel(archivo_xlsx)
                df_excel.columns = df_excel.columns.str.strip().str.lower()
                
                if 'dni' in df_excel.columns:
                    col_id_e = 'dni'
                elif 'id_alumno' in df_excel.columns:
                    col_id_e = 'id_alumno'
                else:
                    col_id_e = df_excel.columns[0]
                    
                df_excel['id_match'] = df_excel[col_id_e].apply(forzar_id_string)
                df_excel_unicos = df_excel.drop_duplicates(subset=['id_match'])
                
                df_cruce = pd.merge(df_deudores, df_excel_unicos, on='id_match', how='inner')
                
                if opcion_base == "Base para HubSpot":
                    df_resultado_crudo = df_cruce[['email']].dropna().drop_duplicates()
                else:
                    df_f = pd.DataFrame()
                    df_f['dni'] = df_cruce['id_match']
                    df_f['nombre'] = df_cruce['user name'].apply(extraer_primer_nombre)
                    df_f['materia'] = df_cruce['course name'].str.strip().upper()
                    df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])
                
                st.session_state.nombre_base = "Base_Deudores_Submissions_Cruza"

        # ------------------------------------------------------------------
        # CASO B: Reporte de Calificaciones Estándar (Por Materia)
        # ------------------------------------------------------------------
        else:
            st.info("📉 Reporte de libro de calificaciones estándar detectado.")
            
            # Limpiamos filas innecesarias y cabeceras duplicadas
            df_canvas = df_canvas_raw[df_canvas_raw['student'].notna()].copy()
            df_canvas = df_canvas[~df_canvas['student'].str.contains('Points|Possible|solo lectura|read only', case=False, na=False)]
            
            # Asignación fija a SIS Login ID donde se encuentra el DNI
            if 'sis login id' in cols_lower:
                col_dni_canvas = 'sis login id'
            elif 'login id' in cols_lower:
                col_dni_canvas = 'login id'
            else:
                col_dni_canvas = 'sis user id' if 'sis user id' in cols_lower else df_canvas.columns[1]
            
            df_canvas['id_match'] = df_canvas[col_dni_canvas].apply(forzar_id_string)
            
            # Intentar extraer el nombre de la materia desde el nombre del archivo
            try: 
                m_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
            except: 
                m_archivo = "MATERIA DETECTADA"
            
            m_limpia = limpiar_texto(m_archivo)
            excluir = any(x in m_limpia for x in LISTA_NEGRA_LIMPIA)

            if not archivo_xlsx:
                if excluir:
                    st.warning(f"🚫 Materia '{m_archivo.upper()}' excluida por configuración global.")
                    df_resultado_crudo = pd.DataFrame(columns=['dni', 'nombre', 'materia'])
                else:
                    df_f = pd.DataFrame()
                    df_f['dni'] = df_canvas['id_match']
                    df_f['nombre'] = df_canvas['student'].apply(extraer_primer_nombre)
                    df_f['materia'] = m_archivo.strip().upper()
                    df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])
            else:
                df_excel = pd.read_excel(archivo_xlsx)
                df_excel.columns = df_excel.columns.str.strip().str.lower()
                
                if 'dni' in df_excel.columns:
                    col_id_e = 'dni'
                elif 'id_alumno' in df_excel.columns:
                    col_id_e = 'id_alumno'
                else:
                    col_id_e = df_excel.columns[0]
                    
                df_excel['id_match'] = df_excel[col_id_e].apply(forzar_id_string)
                
                # CORRECCIÓN CLAVE: Removemos duplicados del Excel por DNI antes de cruzar
                # Esto evita filtrados o reducciones incorrectas basadas en texto de materia cruzado
                df_excel_unicos = df_excel.drop_duplicates(subset=['id_match'])
                
                # Realizamos el cruce directo basándonos únicamente en el DNI válido de Canvas
                df_cruce = pd.merge(df_canvas, df_excel_unicos, on='id_match', how='inner')
                
                if opcion_base == "Base para HubSpot":
                    df_resultado_crudo = df_cruce[['email']].dropna().drop_duplicates()
                else:
                    df_f = pd.DataFrame()
                    df_f['dni'] = df_cruce['id_match']
                    df_f['nombre'] = df_cruce['student'].apply(extraer_primer_nombre)
                    df_f['materia'] = m_archivo.strip().upper()
                    df_resultado_crudo = df_f.drop_duplicates(subset=['dni', 'materia'])

            st.session_state.nombre_base = f"Base_{m_archivo.replace(' ', '_')}"

        # Mostrar resultados en pantalla y habilitar descarga
        if 'df_resultado_crudo' in locals() and not df_resultado_crudo.empty:
            st.success(f"✅ ¡Proceso completado! Se encontraron {len(df_resultado_crudo)} registros.")
            st.dataframe(df_resultado_crudo)
            
            # Conversión a Excel en memoria para la descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_resultado_crudo.to_excel(writer, index=False, sheet_name='Datos')
            data_excel = output.getvalue()
            
            st.download_button(
                label="📥 Descargar Archivo Excel",
                data=data_excel,
                file_name=f"{st.session_state.nombre_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ No se generaron registros. Verifica las exclusiones o que los DNIs del reporte coincidan con los de la base.")
