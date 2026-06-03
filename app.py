import streamlit as st
import pandas as pd
import io
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False

def limpiar_texto(texto):
    """Elimina tildes, convierte Ñ en ni y normaliza texto."""
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

def extraer_y_formatear_nombre(celda):
    """Extrae el primer nombre del formato 'Apellido, Nombre' y lo normaliza."""
    s = str(celda).strip()
    if "," in s:
        parte_nombre = s.split(",")[1].strip()
    else:
        parte_nombre = s
    primer_nombre = parte_nombre.split()[0] if parte_nombre.split() else ""
    return primer_nombre.capitalize()

def normalizar_id(valor):
    """Limpia puntos, decimales y espacios para cruces exactos sin romper vinculación."""
    if pd.isna(valor): return ""
    s = str(valor).split('.')[0].strip()
    return s.replace(',', '')

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0
if 'procesado' not in st.session_state:
    st.session_state.procesado = False

# --- INTERFAZ INICIAL ---
st.title("🛠️ Herramienta de Tutoría Inteligente")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR (DESPLEGABLE DINÁMICO) ---
st.markdown("### 📥 Carga de archivos")
with st.expander("1 - Obtené la base necesaria. Instrucciones aquí."):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Obtener el primer archivo (CSV):**
            * Ingresa a la materia en **Canvas** > **Calificaciones** o descarga el reporte de entregas. 
            * Aplica los filtros necesarios. 
            * Selecciona **Exportar** > **Vista actual**. 
            * ⚠️ **Importante:** No modifiques el nombre del archivo generado.

        2. **Obtener el segundo archivo (XLSX):**
            * En tu **Base de Invitaciones / Query de Avance**, filtra la materia objetivo.
            * Asegúrate de incluir los encabezados **id_alumno** y **dni**.
        """)
    else:
        st.markdown("""
        * Ingresa a la materia en **Canvas** > **Calificaciones** o descarga el reporte de entregas. 
        * Aplica los filtros necesarios. 
        * Selecciona **Exportar** > **Vista actual**. 
        * ⚠️ **Importante:** No modifiques el nombre del archivo generado.
        """)

# --- CARGA DE ARCHIVOS DINÁMICA ---
if opcion_base == "Base para HubSpot":
    st.write("Sube los archivos 👇 y luego haz clic en descargar")
    col1, col2 = st.columns(2)
    with col1:
        archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
    with col2:
        archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")
else:
    st.write("Sube el archivo 👇 y luego haz clic en descargar")
    col1, col2 = st.columns(2)
    with col1:
        archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_wsp_{st.session_state.count}")
    with col2:
        archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_wsp_{st.session_state.count}")

# --- PROCESAMIENTO GENERAL ---
if archivo_csv and archivo_xlsx:
    try:
        # Lectura robusta inicial
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_xlsx = pd.read_excel(archivo_xlsx)
        
        # Normalización estandarizada de columnas
        df_csv.columns = df_csv.columns.str.strip()
        cols_csv_lower = [c.lower() for c in df_csv.columns]
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
        
        # Detección del tipo de archivo CSV
        es_submissions = 'sis user id' in cols_csv_lower and 'assignment name' in cols_csv_lower

        # --- CASO A: REPORTE SUBMISSIONS (ENTREGAS) ---
        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado automáticamente.**")
            df_csv.columns = cols_csv_lower
            df_csv = df_csv.dropna(subset=['user name', 'sis user id'])
            
            # Restauramos filtros avanzados y agrupaciones agrupadas por materia y actividad
            st.markdown("### 🎛️ Filtros Avanzados de Segmentación")
            
            materias_disponibles = sorted(df_csv['course name'].dropna().unique())
            materias_seleccionadas = st.multiselect(
                "1. Filtrar por Materias (Deja vacío para seleccionar todas):", 
                materias_disponibles, 
                default=[]
            )
            
            # Filtrar dataframe temporal según materias seleccionadas para actualizar actividades válidas
            if materias_seleccionadas:
                df_filtrado_mat = df_csv[df_csv['course name'].isin(materias_seleccionadas)]
            else:
                df_filtrado_mat = df_csv
                
            actividades_disponibles = sorted(df_filtrado_mat['assignment name'].dropna().unique())
            actividad_objetivo = st.selectbox("2. Selecciona la actividad a reclamar:", actividades_disponibles)
            
            if st.button("🔍 Filtrar y Calcular Deudores", type="primary"):
                # Normalización de IDs para el cruce exacto
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_filtrado_mat['id_match'] = df_filtrado_mat['sis user id'].apply(normalizar_id)
                
                # Llave única Alumno + Materia para evitar falsos cumplidores en materias paralelas
                df_filtrado_mat['llave_alumno_materia'] = df_filtrado_mat['id_match'] + "_" + df_filtrado_mat['course name'].str.strip().str.upper()
                
                # Universo de análisis
                universo = df_filtrado_mat[['id_match', 'user name', 'course name', 'llave_alumno_materia']].drop_duplicates()
                
                # Alumnos con entregas válidas
                entregaron = df_filtrado_mat[
                    (df_filtrado_mat['assignment name'] == actividad_objetivo) & 
                    (df_filtrado_mat['workflow state'].isin(['submitted', 'graded']))
                ]
                llaves_entregaron = entregaron['llave_alumno_materia'].unique()
                
                # Identificación matemática precisa por combinación
                deudores = universo[~universo['llave_alumno_materia'].isin(llaves_entregaron)].copy()
                
                # Merge definitivo con Excel para capturar el DNI real
                df_final = pd.merge(deudores, df_xlsx[['id_match', 'dni']], on='id_match', how='inner')
                
                # Formateo y limpieza requerida
                df_final['nombre'] = df_final['user name'].apply(extraer_y_formatear_nombre)
                df_final['materia'] = df_final['course name'].apply(limpiar_texto)
                
                st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- CASO B: REPORTE CALIFICACIONES ESTÁNDAR ---
        else:
            st.info("📂 **Reporte de Calificaciones estándar detectado automáticamente.**")
            
            if st.button("🔍 Generar Base para Descargar", type="primary"):
                # Limpieza de filas técnicas de Canvas
                df_csv = df_csv[df_csv['Student'].str.contains('Points|Possible', case=False, na=False) == False]
                
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_csv['id_match'] = df_csv['SIS Login ID'].apply(normalizar_id)
                
                # Cruce con Excel
                df_final = pd.merge(df_csv, df_xlsx[['id_match', 'dni']], on='id_match', how='inner')
                df_final['nombre'] = df_final['Student'].apply(extraer_y_formatear_nombre)
                
                # Extracción de la materia usando el nombre original del archivo
                try:
                    materia_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
                except:
                    materia_archivo = "Materia"
                
                df_final['materia'] = limpiar_texto(materia_archivo)
                
                st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
                st.session_state.nombre_base = f"Base_{materia_archivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- SECCIÓN DINÁMICA DE DESCARGA (CON PARTICIÓN MÁX 100 FILAS) ---
        if st.session_state.procesado:
            df_res = st.session_state.df_resultado
            total_filas = len(df_res)
            
            if not df_res.empty:
                st.success(f"✅ ¡Proceso completado! Se detectaron {total_filas} registros que cumplen las condiciones.")
                
                # Parámetros según el destino seleccionado por interfaz
                header_bool = True if opcion_base == "Base para HubSpot" else False
                suffix = "HUB" if opcion_base == "Base para HubSpot" else "WSP"
                
                st.write("### 📥 Descargar Archivos Excel")
                grid_descargas = st.columns(3)
                
                for i in range(0, total_filas, 100):
                    chunk = df_res.iloc[i : i + 100]
                    parte = (i // 100) + 1
                    
                    # Nomenclatura solicitada (_2, _3 para extras)
                    nombre_archivo = f"{st.session_state.nombre_base}-{suffix}.xlsx" if parte == 1 else f"{st.session_state.nombre_base}-{suffix}_{parte}.xlsx"
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        chunk.to_excel(writer, index=False, header=header_bool)
                    
                    with grid_descargas[i//100 % 3]:
                        st.download_button(
                            label=f"📥 Parte {parte} ({len(chunk)} filas)",
                            data=output.getvalue(),
                            file_name=nombre_archivo,
                            key=f"btn_dl_{i}_{st.session_state.count}",
                            type="primary"
                        )
                
                st.write("### 👁️ Vista previa de los datos:")
                st.dataframe(df_res)
            else:
                st.warning("⚠️ El filtro seleccionado no arrojó ningún alumno deudor. Verifica los criterios.")

    except Exception as e:
        st.error(f"Error crítico durante el análisis: {e}")

# --- RESETEO CONTROLADO ---
st.divider()
if st.button("➕ Limpiar Pantalla y Nueva Carga", type="secondary"):
    reiniciar_aplicacion()
    st.rerun()
