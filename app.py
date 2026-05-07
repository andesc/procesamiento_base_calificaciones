import streamlit as st
import pandas as pd
import io
import os
import unicodedata

# Configuración de la página
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

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

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ INICIAL ---
st.title("🛠️ Herramienta de Tutoría")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Base para HubSpot", "Base para Whatsapp"],
    key="radio_opcion"
)

st.divider()

# --- PASOS A SEGUIR (DESPLEGABLE) ---
st.markdown("### 📥 Carga de archivos")
with st.expander("1 - Obtené la base necesaria. Instrucciones aquí."):
    if opcion_base == "Base para HubSpot":
        st.markdown("""
        1. **Obtener el primer archivo (CSV):**
            * Ingresa a la materia en **Canvas** > **Calificaciones**. 
            * Aplica los filtros necesarios. 
            * Selecciona **Exportar** > **Vista actual**. 
            * ⚠️ **Importante:** No modifiques el nombre del archivo generado.

        2. **Obtener el segundo archivo (XLSX):**
            * En tu **Base de Invitaciones**, filtra la materia objetivo.
            * Asegúrate de incluir los encabezados **dni** y **email**.
        """)
    else:
        st.markdown("""
        * Ingresa a la materia en **Canvas** > **Calificaciones**. 
        * Aplica los filtros necesarios. 
        * Selecciona **Exportar** > **Vista actual**. 
        * ⚠️ **Importante:** No modifiques el nombre del archivo generado.
        """)

# --- CARGA DE ARCHIVOS DINÁMICA ---
if opcion_base == "Base para HubSpot":
    st.write("Sube los archivos 👇 y luego haz clic en descargar")
    col1, col2 = st.columns(2)
    with col1:
        archivo_csv = st.file_uploader("1. Reporte de Calificaciones (CSV)", type=["csv"], key=f"csv_{st.session_state.count}")
    with col2:
        archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"], key=f"xlsx_{st.session_state.count}")
else:
    st.write("Sube el archivo 👇 y luego haz clic en descargar")
    archivo_csv = st.file_uploader("1. Reporte de Calificaciones (CSV)", type=["csv"], key=f"csv_wsp_{st.session_state.count}")
    archivo_xlsx = None # No se requiere para WhatsApp

# --- PROCESAMIENTO ---
if archivo_csv and (opcion_base == "Base para Whatsapp" or archivo_xlsx):
    try:
        # Lógica de Nombres y extracción de Materia del nombre del archivo
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia_bruta = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
            materia_limpia = materia_bruta.replace("_", " ")
        except:
            fecha, materia_limpia = "SinFecha", "Materia"
        
        # Procesamiento según opción
        if opcion_base == "Base para HubSpot":
            df_csv = pd.read_csv(archivo_csv)
            df_xlsx = pd.read_excel(archivo_xlsx)
            
            # Normalización
            df_csv.columns = df_csv.columns.str.strip()
            df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
            df_csv["SIS Login ID"] = df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_xlsx["dni"] = df_xlsx["dni"].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            df_unido = pd.merge(df_csv, df_xlsx[['dni', 'email']], left_on="SIS Login ID", right_on="dni", how="inner")
            df_final = df_unido[['email']].drop_duplicates()
            header_bool = True
            nombre_salida = f"{materia_limpia}-{fecha}-HUB.xlsx"
            
        else:
            # Lógica para WhatsApp (Solo CSV)
            df_csv = pd.read_csv(archivo_csv)
            df_csv.columns = df_csv.columns.str.strip()
            
            # 1. SIS Login ID (DNI)
            df_csv["dni"] = df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # 2. Student (Primer Nombre)
            # Generalmente Canvas exporta "Apellido, Nombre" o "Nombre Apellido"
            # Tomamos la primera parte después de limpiar posibles comas
            df_csv["nombre"] = df_csv["Student"].astype(str).str.replace(',', '').str.split().str[0]
            
            # 3. Materia (del nombre del archivo)
            df_csv["materia_col"] = materia_limpia
            
            # Seleccionar y limpiar texto
            df_final = df_csv[['dni', 'nombre', 'materia_col']].drop_duplicates()
            df_final['nombre'] = df_final['nombre'].apply(limpiar_texto)
            df_final['materia_col'] = df_final['materia_col'].apply(limpiar_texto)
            
            header_bool = False
            nombre_salida = f"{materia_limpia}-{fecha}-WSP.xlsx"

        # --- GENERACIÓN Y DESCARGA ---
        if not df_final.empty:
            st.success(f"✅ ¡Éxito! Se generó la base con {len(df_final)} registros.")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, header=header_bool)
            
            st.download_button(label="📥 Descargar base", 
                               data=output.getvalue(), 
                               file_name=nombre_salida)
            
            st.write("Vista previa:")
            st.dataframe(df_final)
        else:
            st.warning("⚠️ No se pudieron procesar datos. Verifica el formato de los archivos.")

        # --- BOTÓN DE REINICIO ---
        st.divider()
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error: {e}")
