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
    """Elimina tildes, convierte Ñ en ni, quita espacios extras y pasa a mayúsculas."""
    if not isinstance(texto, str):
        return str(texto).strip().upper()
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab).strip().upper()

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
    """Limpia puntos, decimales y espacios para cruces exactos."""
    if pd.isna(valor): return ""
    s = str(valor).split('.')[0].strip()
    return s.replace(',', '')

def homologar_actividad(nombre_tarea):
    """Normaliza las variaciones de nombres de Canvas a un estándar limpio."""
    if pd.isna(nombre_tarea):
        return "OTRO"
    
    n = str(nombre_tarea).upper().strip()
    
    if "API1" in n or "API 1" in n or "AP1" in n or "AI1" in n:
        return "API 1"
    if "API2" in n or "API 2" in n or "AP2" in n or "AI2" in n:
        return "API 2"
    if "API3" in n or "API 3" in n or "AP3" in n or "AI3" in n:
        return "API 3"
    if "API4" in n or "API 4" in n or "AP4" in n or "AI4" in n:
        return "API 4"
        
    if "AE1" in n or "AE 1" in n:
        return "AE 1"
    if "AE2" in n or "AE 2" in n:
        return "AE 2"
    if "AE3" in n or "AE 3" in n:
        return "AE 3"
    if "AE4" in n or "AE 4" in n:
        return "AE 4"
        
    return "OTRO"

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

st.markdown("### 📥 Carga de archivos")
with st.expander("1 - Obtené la base necesaria. Instrucciones aquí."):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Obtener el primer archivo (CSV):**
            * Ingresa a Canvas > Reporte de entregas (Submissions) o Calificaciones.
        2. **Obtener el segundo archivo (XLSX):**
            * Asegúrate de incluir los encabezados **id_alumno**, **dni** y **nombres** (o student).
        """)
    else:
        st.markdown("""
        * Sube ambos archivos requeridos para realizar el cruce de deudores absolutos.
        """)

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos / Query Avance (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO GENERAL ---
if archivo_csv and archivo_xlsx:
    try:
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_xlsx = pd.read_excel(archivo_xlsx)
        
        df_csv.columns = df_csv.columns.str.strip()
        cols_csv_lower = [c.lower() for c in df_csv.columns]
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
        
        es_submissions = 'sis user id' in cols_csv_lower and 'assignment name' in cols_csv_lower

        # --- CASO A: REPORTE SUBMISSIONS (ENTREGAS) ---
        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado automáticamente.**")
            df_csv.columns = cols_csv_lower
            df_csv = df_csv.dropna(subset=['user name', 'sis user id'])
            
            df_csv['actividad_limpia'] = df_csv['assignment name'].apply(homologar_actividad)
            
            # Normalizamos nombres de materia para visualización y filtrado
            if 'materia' in df_xlsx.columns:
                df_xlsx['materia_limpia_filtro'] = df_xlsx['materia'].astype(str).str.strip().str.upper()
                materias_disponibles = sorted(df_xlsx['materia_limpia_filtro'].dropna().unique())
            else:
                df_csv['materia_limpia_filtro'] = df_csv['course name'].astype(str).str.strip().str.upper()
                materias_disponibles = sorted(df_csv['materia_limpia_filtro'].dropna().unique())
                
            st.markdown("### 🎛️ Filtros Avanzados de Segmentación")
            materias_seleccionadas = st.multiselect(
                "1. Filtrar por Materias (Deja vacío para seleccionar todas):", 
                materias_disponibles, 
                default=[]
            )
            
            actividades_validas = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"]
            actividad_objetivo = st.selectbox("2. Selecciona la actividad a reclamar:", actividades_validas)
            
            if st.button("🔍 Filtrar y Calcular Deudores", type="primary"):
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_csv['id_match'] = df_csv['sis user id'].apply(normalizar_id)
                
                # Filtrar Universo Base (Excel)
                df_universo = df_xlsx.copy()
                if materias_seleccionadas:
                    df_universo = df_universo[df_universo['materia_limpia_filtro'].isin(materias_seleccionadas)]
                
                if 'nombres' in df_universo.columns:
                    col_nombre_origen = 'nombres'
                elif 'student' in df_universo.columns:
                    col_nombre_origen = 'student'
                else:
                    col_nombre_origen = df_universo.columns[2]
                
                # Llaves compuestas con texto limpio
                df_universo['materia_key'] = df_universo['materia'].apply(limpiar_texto)
                df_universo['llave_alumno_materia'] = df_universo['id_match'] + "_" + df_universo['materia_key']
                
                # CORRECCIÓN DE ENTRREGAS: Consideramos entregado ÚNICAMENTE si está calificado o enviado formalmente
                entregaron = df_csv[
                    (df_csv['actividad_limpia'] == actividad_objetivo) & 
                    (df_csv['workflow state'].isin(['submitted', 'graded'])) &
                    (df_csv['submission date'].notna() | df_csv['score'].notna())
                ].copy()
                
                entregaron['materia_key'] = entregaron['course name'].apply(limpiar_texto)
                entregaron['llave_alumno_materia'] = entregaron['id_match'] + "_" + entregaron['materia_key']
                llaves_entregaron = entregaron['llave_alumno_materia'].unique()
                
                # Exclusión final estricta
                df_deudores = df_universo[~df_universo['llave_alumno_materia'].isin(llaves_entregaron)].copy()
                
                # Formateo visual
                df_deudores['nombre_final'] = df_deudores[col_nombre_origen].apply(extraer_y_formatear_nombre)
                df_deudores['materia_final'] = df_deudores['materia'].astype(str).str.strip().str.upper()
                
                st.session_state.df_resultado = df_deudores[['dni', 'nombre_final', 'materia_final']].rename(
                    columns={'nombre_final': 'nombre', 'materia_final': 'materia'}
                ).drop_duplicates()
                
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- CASO B: REPORTE CALIFICACIONES ESTÁNDAR ---
        else:
            st.info("📂 **Reporte de Calificaciones estándar detectado automáticamente.**")
            if st.button("🔍 Generar Base para Descargar", type="primary"):
                df_csv = df_csv[df_csv['Student'].str.contains('Points|Possible', case=False, na=False) == False]
                
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_csv['id_match'] = df_csv['SIS Login ID'].apply(normalizar_id)
                
                df_final = pd.merge(df_csv, df_xlsx[['id_match', 'dni']], on='id_match', how='inner')
                df_final['nombre'] = df_final['Student'].apply(extraer_y_formatear_nombre)
                
                try:
                    materia_archivo = archivo_csv.name.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
                except:
                    materia_archivo = "Materia"
                
                df_final['materia'] = materia_archivo.strip().upper()
                st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
                st.session_state.nombre_base = f"Base_{materia_archivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- SECCIÓN DE DESCARGA DIFERENCIADA ---
        if st.session_state.procesado:
            df_res = st.session_state.df_resultado
            total_filas = len(df_res)
            
            if not df_res.empty:
                st.success(f"✅ ¡Proceso completado con éxito! Se detectaron {total_filas} registros deudores reales.")
                st.write("### 📥 Descargar Archivos Excel")
                
                if opcion_base == "Base para HubSpot":
                    nombre_archivo = f"{st.session_state.nombre_base}-HUB.xlsx"
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_res.to_excel(writer, index=False, header=True)
                    
                    st.download_button(
                        label=f"📥 Descargar Base Completa para HubSpot ({total_filas} filas)",
                        data=output.getvalue(),
                        file_name=nombre_archivo,
                        key=f"btn_hub_{st.session_state.count}",
                        type="primary"
                    )
                else:
                    grid_descargas = st.columns(3)
                    for i in range(0, total_filas, 100):
                        chunk = df_res.iloc[i : i + 100]
                        parte = (i // 100) + 1
                        nombre_archivo = f"{st.session_state.nombre_base}-WSP.xlsx" if parte == 1 else f"{st.session_state.nombre_base}-WSP_{parte}.xlsx"
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            chunk.to_excel(writer, index=False, header=False)
                        
                        with grid_descargas[i//100 % 3]:
                            st.download_button(
                                label=f"📥 Parte {parte} ({len(chunk)} filas)",
                                data=output.getvalue(),
                                file_name=nombre_archivo,
                                key=f"btn_wsp_{i}_{st.session_state.count}",
                                type="primary"
                            )
                
                st.write("### 👁️ Vista previa de los datos:")
                st.dataframe(df_res)
            else:
                st.warning("⚠️ No se encontraron deudores con los criterios seleccionados.")

    except Exception as e:
        st.error(f"Error crítico durante el análisis: {e}")

st.divider()
if st.button("➕ Limpiar Pantalla y Nueva Carga", type="secondary"):
    reiniciar_aplicacion()
    st.rerun()
