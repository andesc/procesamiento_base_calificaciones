import streamlit as st
import pandas as pd
import io
import os

# Configuración de la página
st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")


# Instrucciones con formato mejorado
st.markdown("### 📥 Carga de archivos")
st.markdown("Sube el **CSV de calificaciones** y luego el **Excel de invitaciones**.")

st.markdown("""
**Pasos a seguir:**

1. **Obtener el primer archivo (CSV):**
    * Ingresa a la materia en **Canvas** > **Calificaciones**. 
    * Aplica los filtros necesarios (Ejemplo: *Módulos / Módulo 3*, *Grupo de Tareas / Actividades*, *Estado / Faltante*). 
    * Selecciona **Exportar** > **Vista actual**. 
    * ⚠️ **Importante:** No modifiques el nombre del archivo generado para que el sistema pueda extraer la fecha y materia automáticamente.

2. **Obtener el segundo archivo (XLSX):**
    * En tu **Base de Invitaciones**, filtra la materia objetivo.
    * Puedes usar el archivo completo o crear uno nuevo que contenga, al menos, las columnas **dni** y **email**.
    * Si creas un archivo nuevo, asegúrate de incluir los encabezados correctamente.

3. **Sube los archivos utilizando los botones de la parte inferior 👇. Luego de procesarlos, clic en "Descargar" para obtener la base lista para hubspot**    
""")

st.divider() # Línea divisoria visual
# --- ETAPA 1: Carga de archivos desde la interfaz web ---
col1, col2 = st.columns(2)

with col1:
    archivo_csv = st.file_uploader("1. Reporte de Calificaciones (CSV)", type=["csv"])

with col2:
    archivo_xlsx = st.file_uploader("2. Base de Alumnos (XLSX)", type=["xlsx"])

if archivo_csv and archivo_xlsx:
    try:
        # --- Lógica de Nombres de Archivo ---
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]
        
        # Extraer fecha DD-MM y Materia del nombre del CSV
        # Ejemplo: 2026-04-30... -> 30-04
        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            if "Calificaciones-" in nombre_sin_ext:
                materia = nombre_sin_ext.split("Calificaciones-")[1]
            else:
                materia = "Procesado"
        except:
            fecha = "SinFecha"
            materia = "Materia"
            
        nombre_salida = f"{materia}-{fecha}.xlsx"

        # --- Procesamiento de Datos ---
        # Leemos los archivos directamente desde la memoria de la web
        df_csv = pd.read_csv(archivo_csv)
        df_xlsx = pd.read_excel(archivo_xlsx)

        # Limpiar encabezados
        df_csv.columns = df_csv.columns.str.strip()
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

        # Normalizar DNI / SIS ID para que coincidan (quitando .0 y espacios)
        df_csv["SIS Login ID"] = (df_csv["SIS Login ID"]
                                  .astype(str)
                                  .str.strip()
                                  .str.replace('.0', '', regex=False))
        
        df_xlsx["dni"] = (df_xlsx["dni"]
                          .astype(str)
                          .str.strip()
                          .str.replace('.0', '', regex=False))

        # Merge (Cruce de datos)
        df_unido = pd.merge(
            df_csv, 
            df_xlsx[['dni', 'email']], 
            left_on="SIS Login ID", 
            right_on="dni", 
            how="inner"
        )

        # --- RESULTADOS Y DESCARGA ---
        if not df_unido.empty:
            df_final = df_unido[['email']].drop_duplicates()
            
            st.success(f"✅ ¡Éxito! Se encontraron {len(df_final)} alumnos coincidentes.")
            
            # Crear el archivo Excel en memoria para la descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Excel de Emails",
                data=output.getvalue(),
                file_name=nombre_salida,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Vista previa para el usuario
            st.write("Vista previa de los correos encontrados:")
            st.dataframe(df_final)
           # Justo después del botón de descarga exitosa
            st.balloons() # ¡Un poco de festejo visual por el trabajo terminado!
            st.success("Proceso finalizado con éxito.")
            
            if st.button("➕ Generar nueva base", type="primary"):
                st.rerun()
            
        else:
            st.warning("⚠️ No se encontraron coincidencias entre el SIS Login ID y el DNI.")

    except Exception as e:
        st.error(f"Hubo un error al procesar los archivos: {e}")
       
