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
        
    return None

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ ---
st.title("🛠️ Generador de bases: Submissions")
st.markdown("Filtra alumnos que **cursan** una materia pero **adeudan** la actividad seleccionada.")
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
        # 1. Leer archivo Submissions (CSV)
        df_submissions = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_submissions.columns = df_submissions.columns.str.strip().str.lower()
        
        # 2. Leer archivo Base de alumnos (.xlsx o .csv)
        nombre_base_file = archivo_xlsx.name
        if nombre_base_file.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
            
        df_base.columns = df_base.columns.str.strip().str.lower()

        # Verificar columnas obligatorias
        cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
        cols_xlsx_req = {'canvas_id', 'dni', 'nombres', 'email', 'celular'}
        
        if not cols_csv_req.issubset(df_submissions.columns):
            st.error(f"El CSV de submissions debe contener las columnas: {cols_csv_req}")
        elif not cols_xlsx_req.issubset(df_base.columns):
            st.error(f"El archivo Base debe contener las columnas: {cols_xlsx_req}")
        else:
            # Estandarizar identificadores de Canvas a string
            df_submissions['canvas user id'] = df_submissions['canvas user id'].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_base['canvas_id'] = df_base['canvas_id'].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # Aplicar mapeo de filtros
            df_submissions['actividad_filtro'] = df_submissions['assignment name'].apply(normalizar_actividad)
            
            st.divider()
            st.markdown("### 🔍 Configuración de Filtros")
            
            # 1. FILTRO DE ACTIVIDADES (Primero y Obligatorio)
            actividades_disponibles = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4", "PEF"]
            actividades_seleccionadas = st.multiselect("1. Selecciona la/s Actividad/es que deseas controlar (Obligatorio):", options=actividades_disponibles)
            
            # 2. FILTRO DE MATERIAS (Segundo y Opcional)
            # Obtenemos las materias presentes en las entregas para mapear cursado real
            materias_disponibles = sorted(df_submissions['course name'].dropna().unique())
            materias_seleccionadas = st.multiselect("2. Selecciona la/s Materia/s a evaluar (Opcional - Si dejas vacío evalúa todas):", options=materias_disponibles)
            
            if actividades_seleccionadas:
                # Si se seleccionaron materias, filtramos el universo por ellas. Si no, tomamos todas.
                materias_a_procesar = materias_seleccionadas if materias_seleccionadas else materias_disponibles
                
                lista_deudores_acumulados = []
                
                # Iteramos materia por materia para asegurar que solo evaluamos a los que "cursan" cada una
                for materia in materias_a_procesar:
                    # Alumnos que están cursando esta materia según el reporte de submissions (hicieron al menos alguna entrega en ella)
                    alumnos_cursando_materia = df_submissions[df_submissions['course name'] == materia]['canvas user id'].unique()
                    
                    if len(alumnos_cursando_materia) == 0:
                        continue
                        
                    # De los que cursan esta materia, vemos quiénes sí entregaron la/s actividad/es seleccionada/s
                    alumnos_con_entrega = df_submissions[
                        (df_submissions['course name'] == materia) & 
                        (df_submissions['actividad_filtro'].isin(actividades_seleccionadas))
                    ]['canvas user id'].unique()
                    
                    # Los deudores de ESTA materia son los que están cursando pero NO entregaron la actividad
                    ids_deudores_materia = set(alumnos_cursando_materia) - set(alumnos_con_entrega)
                    
                    if ids_deudores_materia:
                        # Extraemos los datos de estos deudores desde la base general
                        df_deudores_materia = df_base[df_base['canvas_id'].isin(ids_deudores_materia)].copy()
                        # Le asignamos la materia correspondiente a la deuda
                        df_deudores_materia['materia'] = materia
                        lista_deudores_acumulados.append(df_deudores_materia)
                
                # Consolidar todos los deudores encontrados
                if lista_deudores_acumulados:
                    df_final_deudores = pd.concat(lista_deudores_acumulados, ignore_index=True)
                    
                    # Formatear columnas de salida requeridas
                    df_final_deudores['nombre'] = df_final_deudores['nombres'].apply(extraer_primer_nombre)
                    df_final_deudores['dni'] = df_final_deudores['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                    df_final_deudores['celular'] = df_final_deudores['celular'].astype(str).str.strip().str.replace('.0', '', regex=False)
                    df_final_deudores['email'] = df_final_deudores['email'].astype(str).str.strip()
                    
                    # Seleccionar y ordenar las columnas finales incluyendo 'materia'
                    df_final = df_final_deudores[['dni', 'nombre', 'email', 'celular', 'materia']].drop_duplicates()
                else:
                    df_final = pd.DataFrame()
                
                st.divider()
                
                # --- GENERACIÓN Y DESCARGA ---
                if not df_final.empty:
                    total_filas = len(df_final)
                    st.success(f"✅ Se detectaron {total_filas} registros de deudas de alumnos activos en cursado.")
                    
                    nombre_archivo_salida = "base_deudores_activos.xlsx"
                    
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
                    
                    st.write("**Vista previa de deudores activos (Primeras 10 filas
