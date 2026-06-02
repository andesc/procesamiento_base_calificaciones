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
    """Extrae la primera palabra que figura en nombres."""
    s = str(celda).strip()
    if not s or s.lower() == 'nan':
        return ""
    if "," in s:
        s = s.split(",")[1].strip()
    primer_nombre = s.split()[0] if s.split() else ""
    return primer_nombre.capitalize()

def normalizar_actividad(actividad):
    """Mapea los nombres de tareas del CSV de entregas o calificaciones."""
    act_upper = str(actividad).upper().strip()
    if "AP1" in act_upper or "API1" in act_upper or "AI1" in act_upper:
        return "API 1"
    if "AP2" in act_upper or "API2" in act_upper or "AI2" in act_upper:
        return "API 2"
    if "AP3" in act_upper or "API3" in act_upper or "AI3" in act_upper:
        return "API 3"
    if "AP4" in act_upper or "API4" in act_upper or "AI4" in act_upper:
        return "API 4"
    if "AE1" in act_upper:
        return "AE 1"
    if "AE2" in act_upper:
        return "AE 2"
    if "AE3" in act_upper:
        return "AE 3"
    if "AE4" in act_upper:
        return "AE 4"
    if "PEF" in act_upper:
        return "PEF"
    return None

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ INICIAL ---
st.title("🛠️ Generación de bases v2")

col_op1, col_op2 = st.columns(2)
with col_op1:
    origen_canvas = st.radio(
        "1. Selecciona el reporte de Canvas de origen:",
        ["Bases desde Submissions", "Bases desde Calificaciones"],
        key="radio_origen"
    )
with col_op2:
    destino_base = st.radio(
        "2. Selecciona la salida que deseas generar:",
        ["Bases para HubSpot", "Bases para Whatsapp"],
        key="radio_destino"
    )

st.divider()

# --- INSTRUCCIONES DINÁMICAS DETALLADAS ---
st.markdown("### 📥 Requerimientos de Archivos")
with st.expander("Ver instrucciones detalladas de descarga", expanded=True):
    if origen_canvas == "Bases desde Submissions":
        st.markdown("**1. Reporte de Canvas (CSV de Entregas):**")
        st.write("- Obtenido desde el entorno de reportes de Canvas (Submissions).")
        st.write("- Columnas obligatorias: `Canvas User ID`, `Course Name` y `Assignment Name`.")
    else:
        st.markdown("**1. Reporte de Canvas (CSV de Calificaciones):**")
        st.write("- Descargado directamente desde el Libro de Calificaciones de la materia.")
        st.write("- Columnas obligatorias: `Student` y (`SIS Login ID` o `Login ID`).")
        
    st.markdown("---")
    if destino_base == "Bases para HubSpot":
        st.markdown("**2. Base de Alumnos secundaria:**")
        st.write("- Archivo Excel (.xlsx) o CSV con el padrón general.")
        st.write("- Debe incluir obligatoriamente las columnas: `dni` y `email`.")
        if origen_canvas == "Bases desde Submissions":
            st.write("- *Nota:* Para cruzar mediante Submissions, también debe incluir la columna `canvas_id`.")
    else:
        st.markdown("**2. Base de Alumnos secundaria:**")
        st.write("- Archivo Excel (.xlsx) o CSV con el padrón general.")
        if origen_canvas == "Bases desde Submissions":
            st.write("- Debe incluir obligatoriamente: `canvas_id`, `dni`, `nombres` y `celular`.")
        else:
            st.markdown("- Debe incluir la columna `nombres` (para complementar y limpiar el saludo).")

# --- CARGA DE ARCHIVOS ---
st.write("Sube los archivos requeridos 👇")
col_f1, col_f2 = st.columns(2)
with col_f1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col_f2:
    archivo_xlsx = st.file_uploader("2. Base General de Alumnos", type=["xlsx", "csv"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO ---
if archivo_csv and archivo_xlsx:
    try:
        # Extraer metadatos del nombre del archivo de Canvas
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            m_bruta = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
            materia_limpia = m_bruta.replace("_", " ")
        except:
            fecha, materia_limpia = "SinFecha", "Materia"

        # Lectura de fuentes
        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_csv.columns = df_csv.columns.str.strip().str.lower()

        if archivo_xlsx.name.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
        df_base.columns = df_base.columns.str.strip().str.lower()

        df_final = pd.DataFrame()

        # =================================================================
        # FLUJO A: DESDE SUBMISSIONS
        # =================================================================
        if origen_canvas == "Bases desde Submissions":
            cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
            if not cols_csv_req.issubset(df_csv.columns):
                st.error("El CSV de Submissions no tiene las columnas correctas.")
            else:
                # Normalizar IDs
                df_csv['canvas user id'] = df_csv['canvas user id'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_csv['actividad_filtro'] = df_csv['assignment name'].apply(normalizar_actividad)
                
                if 'canvas_id' in df_base.columns:
                    df_base['canvas_id'] = df_base['canvas_id'].astype(str).str.strip().str.replace('.0', '', regex=False)
                
                st.divider()
                st.markdown("### 🔍 Configuración de Control de Entregas")
                act_disp = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4", "PEF"]
                act_sel = st.multiselect("Selecciona la/s Actividad/es a controlar (Obligatorio):", options=act_disp)
                mat_disp = sorted(df_csv['course name'].dropna().unique())
                mat_sel = st.multiselect("Selecciona la/s Materia/s (Vacio evalúa todas):", options=mat_disp)
                
                if act_sel:
                    m_proc = mat_sel if mat_sel else mat_disp
                    lista_deudores = []
                    
                    for mat in m_proc:
                        al_cursando = df_csv[df_csv['course name'] == mat]['canvas user id'].unique()
                        if len(al_cursando) == 0:
                            continue
                        al_entrega = df_csv[(df_csv['course name'] == mat) & (df_csv['actividad_filtro'].isin(act_sel))]['canvas user id'].unique()
                        ids_deudores = set(al_cursando) - set(al_entrega)
                        
                        if ids_deudores and 'canvas_id' in df_base.columns:
                            df_d_mat = df_base[df_base['canvas_id'].isin(ids_deudores)].copy()
                            df_d_mat['materia_reporte'] = mat
                            lista_deudores.append(df_d_mat)
                    
                    if lista_deudores:
                        df_f_deud = pd.concat(lista_deudores, ignore_index=True)
                        
                        # PROCESAMIENTO SUBMISSIONS -> HUBSPOT
                        if destino_base == "Bases para HubSpot":
                            if 'email' in df_f_deud.columns:
                                df_f_deud['email'] = df_f_deud['email'].astype(str).str.strip()
                                df_final = df_f_deud[['email']].drop_duplicates()
                            else:
                                st.error("La base secundaria debe contener la columna 'email'.")
                        
                        # PROCESAMIENTO SUBMISSIONS -> WHATSAPP
                        else:
                            if {'dni', 'nombres', 'celular'}.issubset(df_f_deud.columns):
                                df_f_deud['nombre'] = df_f_deud['nombres'].apply(extraer_primer_nombre)
                                df_f_deud['dni'] = df_f_deud['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                                df_f_deud['celular'] = df_f_deud['celular'].astype(str).str.strip().str.replace('.0', '', regex=False)
                                df_f_deud['materia_col'] = df_f_deud['materia_reporte'].apply(limpiar_texto)
                                df_f_deud['nombre'] = df_f_deud['nombre'].apply(limpiar_texto)
                                df_final = df_f_deud[['dni', 'nombre', 'celular', 'materia_col']].drop_duplicates()
                            else:
                                st.error("Faltan columnas ('dni', 'nombres', 'celular') en la base general.")

        # =================================================================
        # FLUJO B: DESDE CALIFICACIONES
        # =================================================================
        else:
            if 'student' not in df_csv.columns:
                st.error("El CSV de calificaciones debe contener la columna 'Student'.")
            else:
                # Limpiar filas de control de Canvas
                c_stud = df_csv['student'].astype(str)
                m_filtro = c_stud.str.contains('Points|Possible|read only', case=False, na=False)
                df_csv = df_csv[~m_filtro]
                
                col_login = [c for c in df_csv.columns if 'login id' in c or 'sis login id' in c]
                if not col_login:
                    st.error("No se encontró la columna de ID (Login ID / SIS Login ID) en Canvas.")
                else:
                    l_key = col_login[0]
                    df_csv[l_key] = df_csv[l_key].astype(str).str.strip().str.replace('.0', '', regex=False)
                    
                    # PROCESAMIENTO CALIFICACIONES -> HUBSPOT
                    if destino_base == "Bases para HubSpot":
                        if 'dni' not in df_base.columns or 'email' not in df_base.columns:
                            st.error("La base general debe incluir 'dni' y 'email'.")
                        else:
                            df_base['dni'] = df_base['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                            df_unido = pd.merge(df_csv, df_base[['dni', 'email']], left_on=l_key, right_on="dni", how="inner")
                            df_final = df_unido[['email']].drop_duplicates()
                    
                    # PROCESAMIENTO CALIFICACIONES -> WHATSAPP
                    else:
                        if 'student' not in df_csv.columns:
                            st.error("Falta columna 'Student' en el reporte.")
                        else:
                            df_csv = df_csv.dropna(subset=['student', l_key])
                            df_csv["dni"] = df_csv[l_key]
                            df_csv["nombre"] = df_csv["student"].apply(extraer_primer_nombre)
                            df_csv["materia_col"] = materia_limpia
                            
                            df_res = df_csv[['dni', 'nombre', 'materia_col']].drop_duplicates()
                            df_res['nombre'] = df_res['nombre'].apply(limpiar_texto)
                            df_res['materia_col'] = df_res['materia_col'].apply(limpiar_texto)
                            df_final = df_res

        # =================================================================
        # SECCIÓN DE DESCARGA COMÚN
        # =================================================================
        if 'df_final' in locals() and not df_final.empty:
            st.success(f"✅ ¡Base generada con éxito! Se procesaron {len(df_final)} registros.")
            
            # Definir sufijo de archivo según destino
            sufijo = "HUB" if destino_base == "Bases para HubSpot" else "WSP"
            nombre_archivo = f"{materia_limpia}-{fecha}-{sufijo}.xlsx"
            
            out_bin = io.BytesIO()
            with pd.ExcelWriter(out_bin, engine='xlsxwriter') as writer:
                # HubSpot lleva encabezado, WhatsApp (generalmente crudo para masivos) se puede parametrizar
                incluir_header = True if destino_base == "Bases para HubSpot" else False
                df_final.to_excel(writer, index=False, header=incluir_header)
            
            st.download_button(
                label=f"📥 Descargar {nombre_archivo}",
                data=out_bin.getvalue(),
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download_btn_{st.session_state.count}"
            )
            st.dataframe(df_final.head(10))
        elif 'df_final' in locals() and df_final.empty and (origen_canvas != "Bases desde Submissions" or (origen_canvas == "Bases desde Submissions" and act_sel)):
            st.info("🎉 El procesamiento terminó pero no se encontraron registros coincidentes.")

        # --- BOTÓN DE REINICIO ---
        st.divider()
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error general de ejecución: {e}")
