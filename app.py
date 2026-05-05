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
    # Reemplazo específico de Ñ/ñ antes de normalizar
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    # Eliminar tildes
    trans_tab = str.maketrans(
        "áéíóúÁÉÍÓÚ",
        "aeiouAEIOU"
    )
    return texto.translate(trans_tab)

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ INICIAL ---
st.title("🛠️ Herramienta de Tutoría")
opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Base para Hubspot", "Base para Whatsapp"],
    help="Hubspot genera solo emails. Whatsapp genera DNI, Nombre y Materia sin encabezados."
)

st.divider()

# Instrucciones dinámicas según la opción
st.markdown("### 📥 Carga de archivos")
texto_destino = "Hubspot" if opcion_base == "Base para Hubspot" else "Whatsapp"
st.markdown(f"Sube los archivos para generar la base de **{texto_destino}**.")

st.markdown("""
**Pasos a seguir:**
1. **Archivo CSV (Canvas):** Exportar 'Vista actual' desde Calificaciones. No cambies el nombre.
2. **Archivo XLSX (Base):** Filtra tu materia. Asegúrate de que tenga las columnas necesarias.
3. **Procesamiento:** Sube los archivos 👇 y luego haz clic en descargar.
""")

st.divider()

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)

with col1:
    archivo_csv = st.file_uploader("1. Reporte de Calificaciones (CSV)", 
                                   type=["csv"], 
                                   key=f"csv_{st.session_state.count}")

with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", 
                                    type=["xlsx"], 
                                    key=f"xlsx_{st.session_state.count}")

if archivo_csv and archivo_xlsx:
    try:
        # --- Lógica de Nombres de Salida ---
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia_nom = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
        except:
            fecha, materia_nom = "SinFecha", "Materia"
        
        suffix = "HUB" if opcion_base == "Base para Hubspot" else "WSP"
        nombre_salida = f"{materia_nom}-{fecha}-{suffix}.xlsx"

        # --- Lectura y Normalización ---
        df_csv = pd.read_csv(archivo_csv)
        df_xlsx = pd.read_excel(archivo_xlsx)

        df_csv.columns = df_csv.columns.str.strip()
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

        # Normalizar IDs de cruce
        df_csv["SIS Login ID"] = df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
        df_xlsx["dni"] = df_xlsx["dni"].astype(str).str.strip().str.replace('.0', '', regex=False)

        # --- CRUCE DE DATOS ---
        # Para Hubspot solo necesitamos email. Para Whatsapp necesitamos mas datos del XLSX.
        cols_xlsx = ['dni', 'email'] if opcion_base == "Base para Hubspot" else ['dni', 'nombres', 'materia']
        
        df_unido = pd.merge(df_csv, df_xlsx[cols_xlsx], left_on="SIS Login ID", right_on="dni", how="inner")

        if not df_unido.empty:
            if opcion_base == "Base para Hubspot":
                # Lógica Original
                df_final = df_unido[['email']].drop_duplicates()
                header_bool = True
            else:
                # Lógica para Whatsapp
                # 1. Tomar solo el primer nombre
                df_unido['nombres'] = df_unido['nombres'].astype(str).str.split().str[0]
                # 2. Seleccionar columnas requeridas
                df_final = df_unido[['dni', 'nombres', 'materia']].drop_duplicates()
                # 3. Limpiar caracteres especiales (tildes y ñ)
                for col in ['nombres', 'materia']:
                    df_final[col] = df_final[col].apply(limpiar_texto)
                header_bool = False # Sin encabezados

            st.success(f"✅ ¡Éxito! Se encontraron {len(df_final)} alumnos coincidentes.")
            
            # --- GENERACIÓN DE EXCEL ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, header=header_bool)
            
            st.download_button(label=f"📥 Descargar base {texto_destino}", 
                               data=output.getvalue(), 
                               file_name=nombre_salida)
            
            st.write("Vista previa de los datos:")
            st.dataframe(df_final)
        else:
            st.warning("⚠️ No se encontraron coincidencias entre los archivos.")

        # --- BOTÓN DE REINICIO ---
        st.divider()
        st.write("¿Deseas procesar otra materia?")
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")
