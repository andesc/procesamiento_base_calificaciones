import streamlit as st
import pandas as pd
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

# --- FUNCIONES DE UTILIDAD ---
def reiniciar_aplicacion():
    st.session_state.count += 1
    st.session_state.procesado = False

def limpiar_texto(texto):
    """Normaliza de forma estricta los nombres de las materias para evitar fallas por tildes."""
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
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

def forzar_id_entero(valor):
    """Convierte cualquier ID en un string numérico limpio para cruzamiento directo."""
    if pd.isna(valor): 
        return ""
    try:
        s = str(valor).split('.')[0].strip()
        return str(int(s))
    except:
        return str(valor).strip()

def homologar_actividad(nombre_tarea):
    """Estandariza las variaciones de nombres que vienen de Canvas."""
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

col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("1. Reporte de Canvas (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos / Query Avance (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")

# --- PROCESAMIENTO GENERAL ---
if archivo_csv and archivo_xlsx:
    try:
        # Lectura robusta del CSV separando correctamente comas y puntos y comas
        contenido = archivo_csv.read()
        try:
            df_csv = pd.read_csv(io.BytesIO(contenido), sep=',', engine='python', on_bad_lines='skip')
            if df_csv.shape[1] <= 1: raise ValueError
        except:
            df_csv = pd.read_csv(io.BytesIO(contenido), sep=';', engine='python', on_bad_lines='skip')
            
        df_xlsx = pd.read_excel(archivo_xlsx)
        
        df_csv.columns = df_csv.columns.str.strip()
        cols_csv_lower = [c.lower() for c in df_csv.columns]
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
        
        es_submissions = 'sis user id' in cols_csv_lower and 'assignment name' in cols_csv_lower

        if es_submissions:
            st.success("📂 **Reporte de Entregas (Submissions) detectado con éxito.**")
            df_csv.columns = cols_csv_lower
            df_csv = df_csv.dropna(subset=['sis user id'])
            
            # Normalización y homologación de campos clave
            df_csv['actividad_limpia'] = df_csv['assignment name'].apply(homologar_actividad)
            df_xlsx['materia_match'] = df_xlsx['materia'].apply(limpiar_texto)
            df_csv['materia_match'] = df_csv['course name'].apply(limpiar_texto)
            
            df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(forzar_id_entero)
            df_csv['id_match'] = df_csv['sis user id'].apply(forzar_id_entero)
            
            materias_disponibles = sorted(df_xlsx['materia_match'].dropna().unique())
            
            st.markdown("### 🎛️ Filtros Avanzados de Segmentación")
            materias_seleccionadas = st.multiselect(
                "1. Filtrar por Materias (Deja vacío para seleccionar todas):", 
                materias_disponibles, 
                default=[]
            )
            
            actividades_validas = ["API 1", "API 2", "API 3", "API 4", "AE 1", "AE 2", "AE 3", "AE 4"]
            actividad_objetivo = st.selectbox("2. Selecciona la actividad a reclamar:", actividades_validas)
            
            if st.button("🔍 Filtrar y Calcular Deudores", type="primary"):
                
                # 1. Filtramos el Universo del Excel por materias elegidas
                df_universo = df_xlsx.copy()
                if materias_seleccionadas:
                    df_universo = df_universo[df_universo['materia_match'].isin(materias_seleccionadas)]
                
                # Creamos la llave compuesta estricta (ID_MATERIA) para el Universo
                df_universo['llave_cruce'] = df_universo['id_match'] + "_" + df_universo['materia_match']
                
                # 2. Aislamos a los alumnos que SÍ entregaron de manera efectiva en Canvas
                si_entregaron = df_csv[
                    (df_csv['actividad_limpia'] == actividad_objetivo) & 
                    (df_csv['workflow state'].isin(['submitted', 'graded']))
                ].copy()
                
                # Creamos la misma llave compuesta para los cumplidores
                si_entregaron['llave_cruce'] = si_entregaron['id_match'] + "_" + si_entregaron['materia_match']
                lista_cumplidores = si_entregaron['llave_cruce'].unique()
                
                # 3. EXCLUSIÓN DIRECTA: Nos quedamos con las filas del universo que NO están en los cumplidores
                df_deudores = df_universo[~df_universo['llave_cruce'].isin(lista_cumplidores)].copy()
                
                # Formateo estético final de los campos
                if 'nombres' in df_deudores.columns: col_nombre = 'nombres'
                elif 'student' in df_deudores.columns: col_nombre = 'student'
                else: col_nombre = df_deudores.columns[2]
                
                df_deudores['nombre_final'] = df_deudores[col_nombre].apply(extraer_y_formatear_nombre)
                df_deudores['materia_final'] = df_deudores['materia'].astype(str).str.strip().str.upper()
                
                # Agrupamos garantizando que si debe ambas materias aparezca dos veces (una por cada materia)
                st.session_state.df_resultado = df_deudores[['dni', 'nombre_final', 'materia_final']].rename(
                    columns={'nombre_final': 'nombre', 'materia_final': 'materia'}
                ).drop_duplicates(subset=['dni', 'materia'])
                
                st.session_state.nombre_base = f"Faltan_{actividad_objetivo.replace(' ', '_')}"
                st.session_state.procesado = True

        else:
            st.info("📂 **Reporte de Calificaciones estándar detectado automáticamente.**")
            if st.button("🔍 Generar Base para Descargar", type="primary"):
                df_csv = df_csv[df_csv['Student'].str.contains('Points|Possible', case=False, na=False) == False]
                
                df_xlsx['id_match'] = df_xlsx['id_alumno'].apply(forzar_id_entero)
                df_csv['id_match'] = df_csv['SIS Login ID'].apply(forzar_id_entero)
                
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

        # --- SECCIÓN DE DESCARGA ---
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
