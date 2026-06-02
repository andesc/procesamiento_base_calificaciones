import streamlit as st
import pandas as pd
import io
import os

# Configuración de la página
st.set_page_config(page_title="Generación de Bases Calificaciones", page_icon="🛠️")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1

def limpiar_texto(texto):
    """Elimina tildes, convierte Ñ en ni y normaliza texto."""
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return texto.translate(trans_tab)

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
    """Mapea los nombres de tareas del CSV de entregas según las reglas."""
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

# --- INTERFAZ INICIAL ---
st.title("🛠️ Generación de bases")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Bases desde submissions", "Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR (DESPLEGABLE) ---
st.markdown("### 📥 Carga de archivos")
with st.expander("Instrucciones de obtención de archivos"):
    if opcion_base == "Bases desde submissions":
        st.markdown("""
        * **Archivo 1 (CSV):** Reporte de entregas (Submissions) obtenido de Canvas. Debe contener `canvas user id`, `course name` y `assignment name`.
        * **Archivo 2 (Excel/CSV):** Base general de alumnos. Debe contener `canvas_id`, `dni`, `nombres`, `email` y `celular`.
        """)
    elif opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Primer archivo (CSV):** Reporte de Calificaciones de Canvas.
        2. **Segundo archivo (XLSX/CSV):** Base de alumnos con los encabezados `dni` y `email`.
        """)
    else:
        st.markdown("""
        * **Primer archivo (CSV):** Reporte de Calificaciones de Canvas.
        * **Segundo archivo (XLSX/CSV):** Base general con la columna de nombres de alumnos.
        """)

# --- CARGA DE ARCHIVOS ESTÁNDAR ---
st.write("Sube los archivos 👇 y luego configura o descarga los resultados")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte (CSV - Submissions / Calificaciones)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (Excel / CSV)", type=["xlsx", "csv"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO ---
if archivo_csv and archivo_xlsx:
    try:
        # Intentar extraer datos del nombre para HubSpot/WhatsApp
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia_bruta = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
            materia_limpia = materia_bruta.replace("_", " ")
        except:
            fecha, materia_limpia = "SinFecha", "Materia"

        # Lectura robusta del CSV primario
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_csv.columns = df_csv.columns.str.strip().str.lower()

        # Lectura de la Base secundaria (XLSX o CSV)
        if archivo_xlsx.name.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
        df_base.columns = df_base.columns.str.strip().str.lower()

        # --- LÓGICA OPCIÓN 1: BASES DESDE SUBMISSIONS ---
        if opcion_base == "Bases desde submissions":
            cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
            cols_base_req = {'canvas_id', 'dni', 'nombres', 'email', 'celular'}
            
            if not cols_csv_req.issubset(df_csv.columns):
                st.error(f"El CSV debe contener las columnas: {cols_csv_req}")
            elif not cols_base_req.issubset(df_base.columns):
                st.error(f"La base debe contener las columnas: {cols_base_req}")
            else:
                # Estandarizar identificadores a string (LÍNEAS CORTADAS PARA PREVENIR ERRORES)
                df_csv['canvas user id'] = df_csv['canvas user id'].astype(str)
                df_csv['canvas user id'] = df_csv['canvas user id'].str.strip()
                df_csv['canvas user id'] = df_csv['canvas user id'].str.replace('.0', '', regex=False)
                
                df_base['canvas_id'] = df_base['canvas_id'].astype(str)
                df_base['canvas_id'] = df_base['canvas_id'].str.strip()
                df_base['canvas_id'] = df_base['canvas_id'].str.replace('.0', '', regex=False)
                
                df_csv['actividad_filtro'] = df_csv['assignment name'].apply(normalizar_actividad)
                
                st.divider()
                st.markdown("### 🔍 Configuración de Filtros de Deuda")
                
                actividades_disponibles = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4", "PEF"]
                actividades_seleccionadas = st.multiselect("1. Selecciona la/s Actividad/es que deseas controlar (Obligatorio):", options=actividades_disponibles)
                
                materias_disponibles = sorted(df_csv['course name'].dropna().unique())
                materias_seleccionadas = st.multiselect("2. Selecciona la/s Materia/s a evaluar (Opcional - Vacío evalúa todas):", options=materias_disponibles)
                
                if actividades_seleccionadas:
                    materias_a_procesar = materias_seleccionadas if materias_seleccionadas else materias_disponibles
                    lista_deudores_acumulados = []
                    
                    for materia in materias_a_procesar:
                        alumnos_cursando = df_csv[df_csv['course name'] == materia]['canvas user id'].unique()
                        if len(alumnos_cursando) == 0:
                            continue
                            
                        alumnos_con_entrega = df_csv[
                            (df_csv['course name'] == materia) & 
                            (df_csv['actividad_filtro'].isin(actividades_seleccionadas))
                        ]['canvas user id'].unique()
                        
                        ids_deudores = set(alumnos_cursando) - set(alumnos_con_entrega)
                        
                        if ids_deudores:
                            df_deudores_materia = df_base[df_base['canvas_id'].isin(ids_deudores)].copy()
                            df_deudores_materia['materia'] = materia
                            lista_deudores_acumulados.append(df_deudores_materia)
                    
                    if lista_deudores_acumulados:
                        df_final_deudores = pd.concat(lista_deudores_acumulados, ignore_index=True)
                        
                        # Formateos individuales seguros y en líneas cortas
                        df_final_deudores['nombre'] = df_final_deudores['nombres'].apply(extraer_primer_nombre)
                        df_final_deudores['dni'] = df_final_deudores['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                        df_final_deudores['celular'] = df_final_deudores['celular'].astype(str).str.strip().str.replace('.0', '', regex=False)
                        df_final_deudores['email'] = df_final_deudores['email'].astype(str).str.strip()
                        
                        columnas_salida = ['dni', 'nombre', 'email', 'celular', 'materia']
                        df_final = df_final_deudores[columnas_salida].drop_duplicates()
                    else:
                        df_final = pd.DataFrame()
                        
                    # Descarga dinámica para Submissions sin errores de sintaxis
                    if not df_final.empty:
                        st.success(f"✅ Se detectaron {len(df_final)} registros de deudas.")
                        output_sub = io.BytesIO()
                        with pd.ExcelWriter(output_sub, engine='xlsxwriter') as writer_sub:
                            df_final.to_excel(writer_sub, index=False)
                        
                        st.download_button(
                            label="📥 Descargar base_deudores_activos.xlsx",
                            data=output_sub.getvalue(),
                            file_name="base_deudores_activos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"btn_sub_{st.session_state.count}"
                        )
                        st.dataframe(df_final.head(10))
                    else:
                        st.info("🎉 ¡Perfecto! No se encontraron alumnos cursando que deban esas actividades.")
                else:
                    st.warning("⚠️ Por favor, selecciona al menos una actividad.")

        # --- LÓGICA OPCIÓN 2: BASE PARA HUBSPOT ---
        elif opcion_base == "Base para HubSpot":
            df_csv = df_csv[df_csv['student'].astype(str).str.contains('Points Possible|read only', case=False, na=False) == False]
            
            # Buscar el identificador de login
            col_login = [c for c in df_csv.columns if 'login id' in c or 'sis login id' in c]
            if not col_login or 'dni' not in df_base.columns:
                st.error("Verifica que el CSV tenga 'SIS Login ID' o 'Login ID' y la base posea la columna 'dni'.")
            else:
                login_key = col_login[0]
                df_csv[login_key] = df_csv[login_key].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_base['dni'] = df_base['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                
                df_unido = pd.merge(df_csv, df_base[['dni', 'email']], left_on=login_key, right_on="dni", how="inner")
                df_final = df_unido[['email']].drop_duplicates()
                
                if not df_final.empty:
                    st.success(f"✅ Se procesaron {len(df_final)} registros para HubSpot.")
                    output_hub = io.BytesIO()
                    with pd.ExcelWriter(output_hub, engine='xlsxwriter') as writer_hub:
                        df_final.to_excel(writer_hub, index=False, header=True)
                    
                    st.download_button(
                        label=f"📥 Descargar {materia_limpia}-{fecha}-HUB.xlsx",
                        data=output_hub.getvalue(),
                        file_name=f"{materia_limpia}-{fecha}-HUB.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"btn_hub_{st.session_state.count}"
                    )
                    st.dataframe(df_final.head(10))
                else:
                    st.warning("⚠️ No se encontraron registros coincidentes para exportar.")

        # --- LÓGICA OPCIÓN 3: BASE PARA WHATSAPP ---
        elif opcion_base == "Base para Whatsapp":
            df_csv = df_csv
