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
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans(
        "áéíóúÁÉÍÓÚ",
        "aeiouAEIOU"
    )
    return texto.translate(trans_tab)

# --- INICIALIZACIÓN ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- INTERFAZ ---
st.title("🛠️ Generador de bases")

opcion_base = st.radio(
    "Selecciona el tipo de base que deseas generar:",
    ["Base para Hubspot", "Base para Whatsapp"]
)

st.divider()

texto_destino = "Hubspot" if opcion_base == "Base para Hubspot" else "Whatsapp"

st.markdown("### 📥 Carga de archivos")

# --- INSTRUCCIONES ---
if opcion_base == "Base para Whatsapp":
    st.markdown("""
1. **Obtener el primer archivo (CSV):**
    * Ingresa a la materia en **Canvas** > **Calificaciones**. 
    * Aplica los filtros necesarios. 
    * Selecciona **Exportar** > **Vista actual**. 
    * ⚠️ **Importante:** No modifiques el nombre del archivo generado.

2. **Sube el archivo utilizando el botón de la parte inferior 👇    
Luego de procesarlo, clic en "Descargar base" (si son varios, clic en cada uno)**
""")
else:
    st.markdown("""
**Pasos a seguir:**
1. Subir CSV de Canvas
2. Subir Excel de base de alumnos
3. Descargar resultado
""")

st.divider()

# --- CARGA DE ARCHIVOS ---
archivo_csv = st.file_uploader(
    "1. Reporte de Calificaciones (CSV)", 
    type=["csv"], 
    key=f"csv_{st.session_state.count}"
)

archivo_xlsx = None

if opcion_base == "Base para Hubspot":
    archivo_xlsx = st.file_uploader(
        "2. Base de Alumnos (XLSX)", 
        type=["xlsx"], 
        key=f"xlsx_{st.session_state.count}"
    )

# --- PROCESAMIENTO ---
if archivo_csv and (archivo_xlsx is not None or opcion_base == "Base para Whatsapp"):
    try:
        nombre_original = archivo_csv.name
        nombre_sin_ext = os.path.splitext(nombre_original)[0]

        try:
            fecha = f"{nombre_sin_ext[8:10]}-{nombre_sin_ext[5:7]}"
            materia_nom = nombre_sin_ext.split("Calificaciones-")[1]
        except:
            fecha, materia_nom = "SinFecha", "Materia"

        suffix = "HUB" if opcion_base == "Base para Hubspot" else "WSP"
        nombre_base = f"{materia_nom}-{fecha}-{suffix}"

        df_csv = pd.read_csv(archivo_csv)
        df_csv.columns = df_csv.columns.str.strip()

        # --- HUBSPOT ---
        if opcion_base == "Base para Hubspot":
            df_xlsx = pd.read_excel(archivo_xlsx)
            df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()

            df_csv["SIS Login ID"] = df_csv["SIS Login ID"].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_xlsx["dni"] = df_xlsx["dni"].astype(str).str.strip().str.replace('.0', '', regex=False)

            df_unido = pd.merge(
                df_csv,
                df_xlsx[['dni', 'email']],
                left_on="SIS Login ID",
                right_on="dni",
                how="inner"
            )

            df_final = df_unido[['email']].drop_duplicates()

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, header=True)

            st.download_button(
                label="📥 Descargar base Hubspot",
                data=output.getvalue(),
                file_name=f"{nombre_base}.xlsx"
            )

       # --- WHATSAPP ---
else:
    # --- LIMPIEZA CSV (Canvas) ---
    df_csv = pd.read_csv(archivo_csv)

    # Eliminar segunda fila (índice 1)
    df_csv = df_csv.drop(index=1).reset_index(drop=True)

    # Reasignar correctamente encabezados
    df_csv.columns = df_csv.iloc[0]
    df_csv = df_csv[1:].reset_index(drop=True)

    # Normalizar columnas
    df_csv.columns = df_csv.columns.astype(str).str.strip()

    # --- EXTRAER MATERIA DESDE NOMBRE ---
    materia_csv = nombre_sin_ext.split("Calificaciones-")[1]
    materia_csv = limpiar_texto(materia_csv.replace("_", " "))

    # --- LIMPIAR DNI ---
    df_csv["SIS Login ID"] = df_csv["SIS Login ID"].astype(str).str.strip()

    # --- EXTRAER PRIMER NOMBRE DESDE "Student" ---
    def obtener_primer_nombre(texto):
        if pd.isna(texto):
            return ""
        
        texto = str(texto)

        # Formato típico: "Apellido, Nombre ..."
        if "," in texto:
            nombre = texto.split(",")[1].strip()
        else:
            nombre = texto.strip()

        # Tomar solo la primera palabra
        nombre = nombre.split()[0]

        return nombre

    df_csv["nombres"] = df_csv["Student"].apply(obtener_primer_nombre)

    # --- BASE FINAL ---
    df_final = df_csv[["SIS Login ID", "nombres"]].drop_duplicates()
    df_final["materia"] = materia_csv

    df_final.columns = ["dni", "nombres", "materia"]

    # Limpiar texto
    for col in ['nombres', 'materia']:
        df_final[col] = df_final[col].apply(limpiar_texto)

    # --- DIVISIÓN EN BLOQUES ---
    chunk_size = 100
    total = len(df_final)

    st.success(f"✅ Se generaron {total} registros")

    for i in range(0, total, chunk_size):
        chunk = df_final.iloc[i:i + chunk_size]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            chunk.to_excel(writer, index=False, header=False)

        parte = (i // chunk_size) + 1
        sufijo = f"_{parte}" if parte > 1 else ""

        nombre_archivo = f"{nombre_base}{sufijo}.xlsx"

        st.download_button(
            label=f"📥 Descargar {nombre_archivo}",
            data=output.getvalue(),
            file_name=nombre_archivo
        )
        st.write("Vista previa:")
        st.dataframe(df_final)

        st.divider()
        if st.button("➕ Nueva carga", on_click=reiniciar_aplicacion):
            pass

    except Exception as e:
        st.error(f"Error: {e}")
