import streamlit as st
import pandas as pd
import io
import os

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Tutoría IA - Procesador", page_icon="🚀")

def reiniciar_aplicacion():
    st.session_state.count += 1

def limpiar_texto(texto):
    if not isinstance(texto, str): return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

def extraer_y_formatear_nombre(celda):
    s = str(celda).strip()
    # Maneja "Apellido , Nombre" o "Apellido, Nombre"
    if "," in s:
        parte_nombre = s.split(",")[1].strip()
    else:
        parte_nombre = s
    primer_nombre = parte_nombre.split()[0] if parte_nombre.split() else ""
    return primer_nombre.capitalize()

# --- ESTADO DE SESIÓN ---
if 'count' not in st.session_state:
    st.session_state.count = 0

st.title("🛠️ Asistente de Tutoría Inteligente")
st.markdown("Carga cualquier reporte de Canvas y el sistema detectará el formato.")

# --- CARGA DE ARCHIVO ---
archivo_csv = st.file_uploader("Sube el archivo CSV de Canvas", type=["csv"], key=f"uploader_{st.session_state.count}")

if archivo_csv:
    try:
        # Lectura robusta para evitar errores de tokenización
        df_raw = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_raw.columns = df_raw.columns.str.strip()
        cols_lower = [c.lower() for c in df_raw.columns]
        
        # --- DETECCIÓN DE TIPO DE REPORTE ---
        es_submissions = 'sis user id' in cols_lower and 'assignment name' in cols_lower
        
        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado.**")
            # Normalizar columnas para Submissions
            df_raw.columns = cols_lower
            
            # Filtro de seguridad: eliminar filas vacías
            df_raw = df_raw.dropna(subset=['user name', 'sis user id'])
            
            # 1. Obtener lista de actividades disponibles en el archivo
            actividades_disponibles = sorted(df_raw['assignment name'].unique())
            
            st.markdown("### 🔍 Configuración del Reclamo")
            actividad_objetivo = st.selectbox("¿Qué actividad quieres reclamar?", actividades_disponibles)
            
            # 2. Lógica de filtrado: ¿Quiénes NO entregaron la actividad?
            # Obtenemos el universo de alumnos y materias
            universo = df_raw[['sis user id', 'user name', 'course name']].drop_duplicates()
            
            # Obtenemos quiénes SÍ entregaron la actividad seleccionada
            entregaron = df_raw[df_raw['assignment name'] == actividad_objetivo]
            entregaron = entregaron[entregaron['workflow state'].isin(['submitted', 'graded'])]
            ids_entregaron = entregaron['sis user id'].unique()
            
            # El resto son los deudores
            df_final = universo[~universo['sis user id'].isin(ids_entregaron)].copy()
            
            # 3. Formatear para la salida
            df_final['dni'] = df_final['sis user id'].astype(str).str.replace('.0', '', regex=False)
            df_final['nombre'] = df_final['user name'].apply(extraer_y_formatear_nombre)
            df_final['materia'] = df_final['course name'].apply(limpiar_texto)
            
            df_descarga = df_final[['dni', 'nombre', 'materia']].drop_duplicates()
            nombre_base = f"Faltan-{actividad_objetivo.replace(' ', '_')}"
            header_bool = False # Formato WhatsApp solicitado
            
        else:
            # --- LÓGICA DE CALIFICACIONES (ESTÁNDAR ANTERIOR) ---
            st.info("📂 **Reporte de Calificaciones estándar detectado.**")
            
            # Filtro de fila "Points Possible"
            df_raw = df_raw[df_raw['Student'].str.contains('Points|Possible', case=False, na=False) == False]
            
            df_raw["dni"] = df_raw["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_raw["nombre"] = df_raw["Student"].apply(extraer_y_formatear_nombre)
            
            # Materia desde el nombre del archivo
            nombre_file = archivo_csv.name
            try:
                materia_archivo = nombre_file.split("Calificaciones-")[1].split(".")[0].replace("_", " ")
            except:
                materia_archivo = "Materia"
            
            df_raw["materia"] = limpiar_texto(materia_archivo)
            df_descarga = df_raw[['dni', 'nombre', 'materia']].drop_duplicates()
            nombre_base = f"Base-Calificaciones-{materia_archivo.replace(' ', '_')}"
            header_bool = False

        # --- GENERACIÓN DE ARCHIVOS (MÁX 100 FILAS) ---
        if not df_descarga.empty:
            total = len(df_descarga)
            st.success(f"✅ Se encontraron {total} alumnos para comunicar.")
            
            st.divider()
            st.write("### 📥 Descargar Bases")
            
            for i in range(0, total, 100):
                chunk = df_descarga.iloc[i : i + 100]
                parte = (i // 100) + 1
                nombre_archivo = f"{nombre_base}_{parte}.xlsx" if total > 100 else f"{nombre_base}.xlsx"
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    chunk.to_excel(writer, index=False, header=header_bool)
                
                st.download_button(
                    label=f"Descargar Parte {parte} ({len(chunk)} registros)",
                    data=output.getvalue(),
                    file_name=nombre_archivo,
                    key=f"btn_{i}_{st.session_state.count}",
                    type="primary"
                )
            
            st.write("Vista previa de los datos:")
            st.dataframe(df_descarga.head(10))
        else:
            st.warning("No se encontraron alumnos que cumplan con el criterio.")

    except Exception as e:
        st.error(f"Error al procesar: {e}")

# --- BOTÓN REINICIO ---
st.divider()
if st.button("➕ Realizar nueva carga", on_click=reiniciar_aplicacion):
    pass
