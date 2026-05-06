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
    trans_tab = str.maketrans(
        "áéíóúÁÉÍÓÚ",
        "aeiouAEIOU"
    )
    return texto.translate(trans_tab)

# --- INICIALIZACIÓN DE ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ INICIAL ---
st.title("🛠️ Generador de bases")
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
        nombre_base = f"{materia_nom}-{fecha}-{suffix}"

        # --- LECTURA ---
        df_csv = pd.read_csv(archivo_csv)
        df_xlsx = pd.read_excel(archivo_xlsx)

        df_csv.columns = df_csv.columns.str.strip()
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

        # --- NORMALIZAR IDS ---
        df_csv["SIS Login ID"] = df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
        df_xlsx["dni"] = df_xlsx["dni"].astype(str).str.strip().str.replace('.0', '', regex=False)

        # --- FILTRO DE MATERIA SOLO PARA WHATSAPP ---
        if opcion_base == "Base para Whatsapp":
            materia_csv = ""
            if "Calificaciones-" in nombre_sin_ext:
                materia_csv = nombre_sin_ext.split("Calificaciones-")[1]

            materia_csv = materia_csv.replace("_", " ")
            materia_csv = limpiar_texto(materia_csv).lower().strip()

            df_xlsx["materia_normalizada"] = df_xlsx["materia"].apply(
                lambda x: limpiar_texto(str(x)).lower().strip()
            )

            df_xlsx = df_xlsx[df_xlsx["materia_normalizada"] == materia_csv]

        # --- CRUCE DE DATOS ---
        cols_xlsx = ['dni', 'email'] if opcion_base == "Base para Hubspot" else ['dni', 'nombres', 'materia']
        
        df_unido = pd.merge(
            df_csv,
            df_xlsx[cols_xlsx],
            left_on="SIS Login ID",
            right_on="dni",
            how="inner"
        )

        if not df_unido.empty:
            if opcion_base == "Base para Hubspot":
                df_final = df_unido[['email']].drop_duplicates()
                header_bool = True

                # Exportación única
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False, header=header_bool)

                st.download_button(
                    label=f"📥 Descargar base {texto_destino}",
                    data=output.getvalue(),
                    file_name=f"{nombre_base}.xlsx"
                )

            else:
                # =========================
                # WHATSAPP
                # =========================
            
                # Leer CSV
                df_csv = pd.read_csv(archivo_csv)
            
                # Eliminar segunda fila ("Points Possible")
                df_csv = df_csv.drop(index=0).reset_index(drop=True)
            
                # Limpiar nombres columnas
                df_csv.columns = df_csv.columns.str.strip()
            
                # Extraer materia desde nombre archivo
                materia = nombre_sin_ext.split("Calificaciones-")[1]
                materia = materia.replace("_", " ")
                materia = limpiar_texto(materia)
            
                # Función para obtener primer nombre
                def obtener_primer_nombre(texto):
                    if pd.isna(texto):
                        return ""
            
                    texto = str(texto)
            
                    # Tomar parte después de la coma
                    if "," in texto:
                        nombre = texto.split(",")[1].strip()
                    else:
                        nombre = texto.strip()
            
                    # Tomar solo primer nombre
                    return nombre.split()[0]
            
                # Crear dataframe final
                df_final = pd.DataFrame()
            
                df_final["dni"] = (
                    df_csv["SIS Login ID"]
                    .astype(str)
                    .str.replace(".0", "", regex=False)
                    .str.strip()
                )
            
                df_final["nombres"] = df_csv["Student"].apply(obtener_primer_nombre)
            
                df_final["materia"] = materia
            
                # Limpiar caracteres especiales
                for col in ["nombres", "materia"]:
                    df_final[col] = df_final[col].apply(limpiar_texto)
            
                # Eliminar duplicados
                df_final = df_final.drop_duplicates()
            
                # División en bloques
                chunk_size = 100
                total_filas = len(df_final)
            
                st.success(f"✅ ¡Éxito! Se encontraron {total_filas} alumnos.")
            
                for i in range(0, total_filas, chunk_size):
            
                    chunk = df_final.iloc[i:i + chunk_size]
            
                    output = io.BytesIO()
            
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        chunk.to_excel(
                            writer,
                            index=False,
                            header=False
                        )
            
                    parte = (i // chunk_size) + 1
            
                    sufijo = f"_{parte}" if parte > 1 else ""
            
                    nombre_archivo = f"{nombre_base}{sufijo}.xlsx"
            
                    st.download_button(
                        label=f"📥 Descargar {nombre_archivo}",
                        data=output.getvalue(),
                        file_name=nombre_archivo
                    )

            st.write("Vista previa de los datos:")
            st.dataframe(df_final)

        else:
            st.warning("⚠️ No se encontraron coincidencias entre los archivos.")

        # --- REINICIO ---
        st.divider()
        st.write("¿Deseas procesar otra materia?")
        if st.button("➕ Realizar nueva carga", type="primary", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")
