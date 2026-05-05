import streamlit as st
import pandas as pd
import io
import os

# Configuración de la página
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

# --- NUEVA LÓGICA DE LIMPIEZA ---
# Si no existe un 'contador' en la sesión, lo creamos. 
# Cambiar este número reseteará los componentes de carga.
if 'count' not in st.session_state:
    st.session_state.count = 0

def reiniciar_aplicacion():
    st.session_state.count += 1

# Instrucciones
st.markdown("### 📥 Carga de archivos")
st.markdown("Sube el **CSV de calificaciones** y luego el **Excel de invitaciones**.")

st.markdown("""
**Pasos a seguir:**

1. **Obtener el primer archivo (CSV):**
    * Ingresa a la materia en **Canvas** > **Calificaciones**. 
    * Aplica los filtros necesarios. 
    * Selecciona **Exportar** > **Vista actual**. 
    * ⚠️ **Importante:** No modifiques el nombre del archivo generado.

2. **Obtener el segundo archivo (XLSX):**
    * En tu **Base de Invitaciones**, filtra la materia objetivo.
    * Asegúrate de incluir los encabezados **dni** y **email**.

3. **Sube los archivos utilizando los botones de la parte inferior 👇   
Luego de procesarlos, clic en "Descargar base", para obtener el archivo listo para hubspot.**    
      
""")

st.divider()

# --- ETAPA 1: Carga de archivos con KEY DINÁMICA ---
col1, col2 = st.columns(2)

with col1:
    # Agregamos la clave dinámica basada en el contador
    archivo_csv = st.file_uploader("1. Reporte de Calificaciones (CSV)", 
                                   type=["csv"], 
                                   key=f"csv_{st.session_state.count}")

with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", 
                                    type=["xlsx"], 
                                    key=f"xlsx_{st.session_state.count}")

if archivo_csv and archivo_xlsx:
    try:
        # --- Lógica de Nombres ---
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia = nombre_sin_ext.split("Calificaciones-")[1] if "Calificaciones-" in nombre_sin_ext else "Procesado"
        except:
            fecha, materia = "SinFecha", "Materia"
            
        nombre_salida = f"{materia}-{fecha}.xlsx"

        # --- Procesamiento ---
        df_csv = pd.read_csv(archivo_csv)
        df_xlsx = pd.read_excel(archivo_xlsx)

        df_csv.columns = df_csv.columns.str.strip()
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

        df_csv["SIS Login ID"] = (df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False))
        df_xlsx["dni"] = (df_xlsx["dni"].astype(str).str.strip().str.replace('.0', '', regex=False))

        df_unido = pd.merge(df_csv, df_xlsx[['dni', 'email']], left_on="SIS Login ID", right_on="dni", how="inner")

        # --- RESULTADOS ---
        if not df_unido.empty:
            df_final = df_unido[['email']].drop_duplicates()
            st.success(f"✅ ¡Éxito! Se encontraron {len(df_final)} alumnos coincidentes.")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            
            st.download_button(label="📥 Descargar base", data=output.getvalue(), file_name=nombre_salida)
            st.write("Vista previa:")
            st.dataframe(df_final)
        else:
            st.warning("⚠️ No se encontraron coincidencias.")

        # --- BOTÓN DE REINICIO MEJORADO ---
        st.divider()
        st.write("¿Deseas procesar otra materia?")
        
        # Al hacer clic, Streamlit ejecuta la función y recarga automáticamente
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error: {e}")
