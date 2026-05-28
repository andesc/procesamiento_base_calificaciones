import streamlit as st
import pandas as pd
import io
import os

# Configuración de la página
st.set_page_config(page_title="Generador de Bases Submissions", page_icon="🛠️")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1

def extraer_primer_nombre(celda):
    """Extrae la primera palabra que figura en nombres y le da formato Capitalize."""
    s = str(celda).strip()
    if not s or s.lower() == 'nan':
        return ""
    # Si viene con formato Apellido, Nombre (ej: "Romero, Joana Natali") tomamos lo que sigue a la coma
    if "," in s:
        s = s.split(",")[1].strip()
    
    primer_nombre = s.split()[0] if s.split() else ""
    return primer_nombre.capitalize()

def normalizar_actividad(actividad):
    """Mapea los nombres del CSV de entregas según las reglas definidas."""
    act_upper = str(actividad).upper().strip()
    
    # Mapeo de APIs
    if "AP1" in act_upper or "API1" in act_upper or "AI1" in act_upper:
        return "API 1"
    if "AP2" in act_upper or "API2" in act_upper or "AI2" in act_upper:
        return "API 2"
    if "AP3" in act_upper or "API3" in act_upper or "AI3" in act_upper:
        return "API 3"
    if "AP4" in act_upper or "API4" in act_upper or "AI4" in act_upper:
        return "API 4"
        
    # Mapeo de AEs
    if "AE1" in act_upper:
        return "AE 1"
    if "AE2" in act_upper:
        return "AE 2"
    if "AE3" in act_upper:
        return "AE 3"
    if "AE4" in act_upper:
        return "AE 4"
        
    # PEF
    if "PEF" in act_upper:
        return "PEF"
        
    return None # Si no coincide con ninguna categoría buscada

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ ---
st.title("🛠️ Generador de bases: Submissions")
st.markdown("Filtra alumnos de la base general que **adeudan** las tareas seleccionadas.")
st.divider()

# --- CARGA DE ARCHIVOS ---
st.markdown("### 📥 Carga de archivos")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Submissions (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base General de Alumnos (Excel / CSV)", type=["xlsx", "csv"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO PRINCIPAL ---
if archivo_csv and archivo_xlsx:
    try:
        # 1. Leer archivo Submissions (CSV) de forma robusta
        df_submissions = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_submissions.columns = df_submissions.columns.str.strip().str.lower()
        
        # 2. Leer archivo Base de alumnos (Soporta .xlsx o .csv según el formato en el que se suba)
        nombre_base_file = archivo_xlsx.name
        if nombre_base_file.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
            
        df_base.columns = df_base.columns.str.strip().str.lower()

        # Verificar columnas obligatorias mínimas
        cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
        cols_xlsx_req = {'canvas_id', 'dni', 'nombres', 'email', 'celular'}
        
        if not cols_csv_req.issubset(df_submissions.columns):
            st.error(f"El CSV de submissions debe contener las columnas: {cols_csv_req}")
        elif not cols_xlsx_req.issubset(df_base.columns):
            st.error(f"El archivo Base debe contener las columnas: {cols_xlsx_req}")
        else:
            # Estandarizar identificadores de Canvas a string para evitar errores de float/int
            df_submissions['canvas user id'] = df_submissions['canvas user id'].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_base['canvas_id'] = df_base['canvas_id'].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # Aplicar mapeo de filtros a las actividades en el CSV
            df_submissions['actividad_filtro'] = df_submissions['assignment name'].apply(normalizar_actividad)
            
            # Filtrar filas que tengan un mapeo válido de actividad
            df_submissions = df_submissions.dropna(subset=['actividad_filtro'])
            
            st.divider()
            st.markdown("### 🔍 Configuración de Filtros")
            
            # Obtener listas únicas para los selectores
            materias_disponibles = sorted(df_submissions['course name'].dropna().unique())
            actividades_disponibles = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4", "PEF"]
            
            # Componentes de filtrado en Streamlit
            materias_seleccionadas = st.multiselect("Selecciona la/s Materia/s a evaluar:", options=materias_disponibles)
            actividades_seleccionadas = st.multiselect("Selecciona la/s Actividad/es que deseas controlar:", options=actividades_disponibles)
            
            if materias_seleccionadas and actividades_seleccionadas:
                
                # Filtrar el universo de entregas reales con los parámetros elegidos
                entregas_filtradas = df_submissions[
                    (df_submissions['course name'].isin(materias_seleccionadas)) &
                    (df_submissions['actividad_filtro'].isin(actividades_seleccionadas))
                ]
                
                # Alumnos que SÍ entregaron (creamos un set de IDs únicos que cumplieron)
                ids_con_entrega = set(entregas_filtradas['canvas user id'].unique())
                
                # Filtrar base general: Alumnos que NO están en el grupo que entregó
                df_deudores = df_base[~df_base['canvas_id'].isin(ids_con_entrega)].copy()
                
                # Construir columnas finales solicitadas
                df_deudores['nombre'] = df_deudores['nombres'].apply(extraer_primer_nombre)
                
                # Asegurar formato de texto limpio en DNI, Celular y Mail
                df_deudores['dni'] = df_deudores['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_deudores['celular'] = df_deudores['celular'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_deudores['email'] = df_deudores['email'].astype(str).str.strip()
                
                # Seleccionar exclusivamente las columnas requeridas para el reporte final
                df_final = df_deudores[['dni', 'nombre', 'email', 'celular']].drop_duplicates()
                
                st.divider()
                
                # --- GENERACIÓN Y DESCARGA ---
                if not df_final.empty:
                    total_filas = len(df_final)
                    st.success(f"✅ Se detectaron {total_filas} alumnos que adeudan las tareas seleccionadas.")
                    
                    nombre_archivo_salida = "base_deudores_submissions.xlsx"
                    
                    # Generar Excel en memoria
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False)
                    
                    st.download_button(
                        label=f"📥 Descargar {nombre_archivo_salida}", 
                        data=output.getvalue(), 
                        file_name=nombre_archivo_salida,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"btn_descarga_{st.session_state.count}"
                    )
                    
                    st.write("**Vista previa de los alumnos deudores (Primeras 10 filas):**")
                    st.dataframe(df_final.head(10))
                else:
                    st.info("🎉 ¡Buenas noticias! No se encontraron alumnos deudores con los criterios seleccionados.")
            else:
                st.warning("⚠️ Selecciona al menos una materia y una actividad para calcular la base de deudores.")

        st.divider()
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los archivos: {e}")
