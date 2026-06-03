import streamlit as st
import pandas as pd
import io
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asistente de Tutoría Pro", page_icon="🎓")

def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False

def limpiar_texto(texto):
    if not isinstance(texto, str): return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

def extraer_y_formatear_nombre(celda):
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
    s = str(valor).split('.')[0].strip() # Quita el .0 si existe
    return s.replace(',', '')

# --- ESTADO DE SESIÓN ---
if 'count' not in st.session_state:
    st.session_state.count = 0
if 'procesado' not in st.session_state:
    st.session_state.procesado = False

st.title("🚀 Asistente de Tutoría v3 (Corregido)")

# --- CARGA DE ARCHIVOS ---
col_a, col_b = st.columns(2)
with col_a:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col_b:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

if archivo_csv and archivo_xlsx:
    try:
        # Lectura inicial de los datos
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_xlsx = pd.read_excel(archivo_xlsx)
        
        # Normalizar nombres de columnas a minúsculas
        df_csv.columns = df_csv.columns.str.strip()
        cols_csv_lower = [c.lower() for c in df_csv.columns]
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

        # Detectar el tipo de reporte
        es_submissions = 'sis user id' in cols_csv_lower and 'assignment name' in cols_csv_lower

        if es_submissions:
            st.success("📂 Reporte de Entregas (Submissions) detectado.")
            df_csv.columns = cols_csv_lower
            
            # Filtrar filas de metadatos o vacías en Canvas
            df_csv = df_csv.dropna(subset=['user name', 'sis user id'])
            
            # --- INTERFAZ DE FILTROS ---
            actividades = sorted(df_csv['assignment name'].dropna().unique())
            st.markdown("### 🛠️ Configuración de Filtros")
            actividad_objetivo = st.selectbox("Selecciona la actividad a reclamar:", actividades)
            
            if st.button("🔍 Generar Base para Descargar", type="primary"):
                # 1. Normalizar las claves de cruce en ambos DataFrames
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(normalizar_id)
                df_csv['id_match'] = df_csv['sis user id'].apply(normalizar_id)
                
                # 2. Crear una llave única combinando Alumno + Materia
                df_csv['llave_alumno_materia'] = df_csv['id_match'] + "_" + df_csv['course name'].str.strip().str.upper()
                
                # Universo real: Todas las combinaciones de Alumno + Materia que existen en el reporte
                universo = df_csv[['id_match', 'user name', 'course name', 'llave_alumno_materia']].drop_duplicates()
                
                # 3. Identificar quiénes SÍ entregaron la actividad en esa materia específica
                entregaron = df_csv[
                    (df_csv['assignment name'] == actividad_objetivo) & 
                    (df_csv['workflow state'].isin(['submitted', 'graded']))
                ]
                llaves_entregaron = entregaron['llave_alumno_materia'].unique()
                
                # 4. Los deudores son los que la combinación Alumno_Materia NO está en la lista de entregados
                deudores = universe_deudores = universo[~universo['llave_alumno_materia'].isin(llaves_entregaron)].copy()
                
                # 5. Cruzar con el Excel para traer el DNI correcto del alumno
                df_final = pd.merge(deudores, df_xlsx[['id_match', 'dni']], on='id_match', how='inner')
                
                # 6. Formatear campos finales para WhatsApp
                df_final['nombre'] = df_final['user name'].apply(extraer_y_formatear_nombre)
                df_final['materia'] = df_final['course name'].apply(limpiar_texto)
                
                st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        else:
            st.info("📂 Reporte de Calificaciones estándar detectado.")
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
                
                df_final['materia'] = limpiar_texto(materia_archivo)
                st.session_state.df_resultado = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
                st.session_state.nombre_base = f"Base_{materia_archivo.replace(' ', '_')}"
                st.session_state.procesado = True

        # --- ÁREA DE DESCARGA EN BLOQUES DE 100 ---
        if st.session_state.procesado:
            df_res = st.session_state.df_resultado
            total = len(df_res)
            st.success(f"✅ ¡Filtro corregido con éxito! Se generó una base con {total} registros coincidiendo con el comportamiento manual.")
            
            cols_descarga = st.columns(3)
            for i in range(0, total, 100):
                chunk = df_res.iloc[i : i + 100]
                parte = (i // 100) + 1
                nombre_archivo = f"{st.session_state.nombre_base}_{parte}.xlsx"
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    chunk.to_excel(writer, index=False, header=False)
                
                with cols_descarga[i//100 % 3]:
                    st.download_button(
                        label=f"📥 Parte {parte} ({len(chunk)})",
                        data=output.getvalue(),
                        file_name=nombre_archivo,
                        key=f"dl_{i}_{st.session_state.count}"
                    )
            st.dataframe(df_res)

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

st.divider()
st.button("➕ Limpiar y nueva carga", on_click=reiniciar_aplicacion)
