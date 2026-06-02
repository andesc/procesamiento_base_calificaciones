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
    """Mapea los nombres de tareas del CSV de entregas."""
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
st.title("🛠️ Generación de bases")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Bases desde submissions", "Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR ---
st.markdown("### 📥 Carga de archivos")
with st.expander("Instrucciones"):
    if opcion_base == "Bases desde submissions":
        st.write("CSV: Reporte entregas (Canvas User ID, Course Name, Assignment Name).")
        st.write("Excel/CSV: Base general (canvas_id, dni, nombres, email, celular).")
    elif opcion_base == "Base para HubSpot":
        st.write("1. CSV Calificaciones Canvas. 2. Base Alumnos (dni, email).")
    else:
        st.write("1. CSV Calificaciones Canvas. 2. Base con nombres.")

# --- CARGA DE ARCHIVOS ---
st.write("Sube los archivos 👇")
col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. CSV", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base", type=["xlsx", "csv"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO ---
if archivo_csv and archivo_xlsx:
    try:
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            m_bruta = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
            materia_limpia = m_bruta.replace("_", " ")
        except:
            fecha, materia_limpia = "SinFecha", "Materia"

        df_csv = pd.read_csv(archivo_csv, sep=None, engine='python', on_bad_lines='skip')
        df_csv.columns = df_csv.columns.str.strip().str.lower()

        if archivo_xlsx.name.endswith('.csv'):
            df_base = pd.read_csv(archivo_xlsx, sep=None, engine='python', on_bad_lines='skip')
        else:
            df_base = pd.read_excel(archivo_xlsx)
        df_base.columns = df_base.columns.str.strip().str.lower()

        # --- OPCIÓN 1: SUBMISSIONS ---
        if opcion_base == "Bases desde submissions":
            cols_csv_req = {'canvas user id', 'course name', 'assignment name'}
            cols_base_req = {'canvas_id', 'dni', 'nombres', 'email', 'celular'}
            
            if not cols_csv_req.issubset(df_csv.columns):
                st.error("CSV sin columnas requeridas.")
            elif not cols_base_req.issubset(df_base.columns):
                st.error("Base sin columnas requeridas.")
            else:
                df_csv['canvas user id'] = df_csv['canvas user id'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_base['canvas_id'] = df_base['canvas_id'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_csv['actividad_filtro'] = df_csv['assignment name'].apply(normalizar_actividad)
                
                st.divider()
                st.markdown("### 🔍 Filtros de Deuda")
                act_disp = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4", "PEF"]
                act_sel = st.multiselect("1. Actividades (Obligatorio):", options=act_disp)
                mat_disp = sorted(df_csv['course name'].dropna().unique())
                mat_sel = st.multiselect("2. Materias (Opcional):", options=mat_disp)
                
                if act_sel:
                    m_proc = mat_sel if mat_sel else mat_disp
                    lista_deudores = []
                    
                    for mat in m_proc:
                        al_cursando = df_csv[df_csv['course name'] == mat]['canvas user id'].unique()
                        if len(al_cursando) == 0:
                            continue
                        al_entrega = df_csv[(df_csv['course name'] == mat) & (df_csv['actividad_filtro'].isin(act_sel))]['canvas user id'].unique()
                        ids_deudores = set(al_cursando) - set(al_entrega)
                        
                        if ids_deudores:
                            df_d_mat = df_base[df_base['canvas_id'].isin(ids_deudores)].copy()
                            df_d_mat['materia'] = mat
                            lista_deudores.append(df_d_mat)
                    
                    if lista_deudores:
                        df_f_deud = pd.concat(lista_deudores, ignore_index=True)
                        df_f_deud['nombre'] = df_f_deud['nombres'].apply(extraer_primer_nombre)
                        df_f_deud['dni'] = df_f_deud['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                        df_f_deud['celular'] = df_f_deud['celular'].astype(str).str.strip().str.replace('.0', '', regex=False)
                        df_f_deud['email'] = df_f_deud['email'].astype(str).str.strip()
                        df_final = df_f_deud[['dni', 'nombre', 'email', 'celular', 'materia']].drop_duplicates()
                    else:
                        df_final = pd.DataFrame()
                        
                    if not df_final.empty:
                        st.success(f"✅ Detectados {len(df_final)} registros.")
                        out_sub = io.BytesIO()
                        with pd.ExcelWriter(out_sub, engine='xlsxwriter') as w_sub:
                            df_final.to_excel(w_sub, index=False)
                        st.download_button(
                            label="📥 Descargar Excel",
                            data=out_sub.getvalue(),
                            file_name="base_deudores_activos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"b_sub_{st.session_state.count}"
                        )
                        st.dataframe(df_final.head(10))
                    else:
                        st.info("🎉 ¡No se encontraron deudores!")
                else:
                    st.warning("⚠️ Selecciona una actividad.")

        # --- OPCIÓN 2: HUBSPOT ---
        elif opcion_base == "Base para HubSpot":
            c_stud = df_csv['student'].astype(str)
            m_filtro = c_stud.str.contains('Points Possible|read only', case=False, na=False)
            df_csv = df_csv[~m_filtro]
            
            col_login = [c for c in df_csv.columns if 'login id' in c or 'sis login id' in c]
            if not col_login or 'dni' not in df_base.columns:
                st.error("Columnas faltantes en archivos.")
            else:
                l_key = col_login[0]
                df_csv[l_key] = df_csv[l_key].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_base['dni'] = df_base['dni'].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_unido = pd.merge(df_csv, df_base[['dni', 'email']], left_on=l_key, right_on="dni", how="inner")
                df_final = df_unido[['email']].drop_duplicates()
                
                if not df_final.empty:
                    st.success(f"✅ Procesados {len(df_final)} registros.")
                    out_hub = io.BytesIO()
                    with pd.ExcelWriter(out_hub, engine='xlsxwriter') as w_hub:
                        df_final.to_excel(w_hub, index=False, header=True)
                    st.download_button(
                        label="📥 Descargar HUB",
                        data=out_hub.getvalue(),
                        file_name=f"{materia_limpia}-{fecha}-HUB.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"b_hub_{st.session_state.count}"
                    )
                    st.dataframe(df_final.head(10))
                else:
                    st.warning("⚠️ Sin coincidencias.")

        # --- OPCIÓN 3: WHATSAPP ---
        elif opcion_base == "Base para Whatsapp":
            c_stud = df_csv['student'].astype(str)
            m_filtro = c_stud.str.contains('Points|Possible', case=False, na=False)
            df_csv = df_csv[~m_filtro]
            
            col_login = [c for c in df_csv.columns if 'login id' in c or 'sis login id' in c]
            if not col_login or 'student' not in df_csv.columns:
                st.error("Faltan columnas requeridas.")
            else:
                l_key = col_login[0]
                df_csv = df_csv.dropna(subset=['student', l_key])
                df_csv["dni"] = df_csv[l_key].astype(str).str.strip().str.replace('.0', '', regex=False)
                df_csv["nombre"] = df_csv["student"].apply(extraer_primer_nombre)
                df_csv["materia_col"] = materia_limpia
                
                df_final = df_csv[['dni', 'nombre', 'materia_col']].drop_duplicates()
                df_final['nombre'] = df_final['nombre'].apply(limpiar_texto)
                df_final['materia_col'] = df_final['materia_col'].apply(limpiar_texto)
                
                if not df_final.empty:
                    st.success(f"✅ Procesados {len(df_final)} registros.")
                    out_wsp = io.BytesIO()
                    with pd.ExcelWriter(out_wsp, engine='xlsxwriter') as w_wsp:
                        df_final.to_excel(w_wsp, index=False, header=False)
                    st.download_button(
                        label="📥 Descargar WSP",
                        data=out_wsp.getvalue(),
                        file_name=f"{materia_limpia}-{fecha}-WSP.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"b_wsp_{st.session_state.count}"
                    )
                    st.dataframe(df_final.head(10))
                else:
                    st.warning("⚠️ Sin datos válidos.")

        # --- BOTÓN DE REINICIO ---
        st.divider()
        if st.button("➕ Nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error general: {e}")
