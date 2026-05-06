import streamlit as st
import pandas as pd
import io
import os
import unicodedata

st.set_page_config(page_title="Procesamiento Base Calificaciones", page_icon="📧")

# --- FUNCIONES ---
def reiniciar_aplicacion():
    st.session_state.count += 1

def limpiar_texto(texto):
    if not isinstance(texto, str):
        return str(texto)
    texto = texto.replace('ñ', 'ni').replace('Ñ', 'Ni')
    trans_tab = str.maketrans("áéíóúÁÉÍÓÚ","aeiouAEIOU")
    return texto.translate(trans_tab)

def obtener_primer_nombre(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto)

    if "," in texto:
        nombre = texto.split(",")[1].strip()
    else:
        nombre = texto.strip()

    return nombre.split()[0]

# --- ESTADO ---
if 'count' not in st.session_state:
    st.session_state.count = 0

# --- UI ---
st.title("🛠️ Generador de bases")

opcion_base = st.radio(
    "Selecciona el tipo de base:",
    ["Base para Hubspot", "Base para Whatsapp"]
)

st.divider()

st.markdown("### 📥 Carga de archivos")

# --- UPLOADERS ---
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

        # =========================
        # HUBSPOT (sin cambios)
        # =========================
        if opcion_base == "Base para Hubspot":
            df_csv = pd.read_csv(archivo_csv)
            df_xlsx = pd.read_excel(archivo_xlsx)

            df_csv.columns = df_csv.columns.str.strip()
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
                df_final.to_excel(writer, index=False)

            st.download_button(
                label="📥 Descargar base Hubspot",
                data=output.getvalue(),
                file_name=f"{nombre_base}.xlsx"
            )

        # =========================
        # WHATSAPP (nuevo flujo)
        # =========================
        else:
            # Leer CSV
            df_csv = pd.read_csv(archivo_csv)

            # Eliminar segunda fila
            df_csv = df_csv.drop(index=1).reset_index(drop=True)

            # Reasignar encabezados correctamente
            df_csv.columns = df_csv.iloc[0]
            df_csv = df_csv[1:].reset_index(drop=True)

            df_csv.columns = df_csv.columns.astype(str).str.strip()

            # Extraer materia
            materia = nombre_sin_ext.split("Calificaciones-")[1]
            materia = limpiar_texto(materia.replace("_", " "))

            # Procesar columnas
            # Buscar columna de DNI dinámicamente
                       col_dni = [
                col for col in df_csv.columns
                if isinstance(col, str) and "sis" in col.lower() and "login" in col.lower()
            ]
            
            if not col_dni:
                st.error("❌ No se encontró la columna 'SIS Login ID'")
                st.write("Columnas detectadas:", df_csv.columns.tolist())
                st.stop()
            
            col_dni = col_dni[0]
            
            df_csv["dni"] = df_csv[col_dni].astype(str).str.strip()
            df_csv["nombres"] = df_csv["Student"].apply(obtener_primer_nombre)

            df_final = df_csv[["dni", "nombres"]].drop_duplicates()
            df_final["materia"] = materia

            for col in ["nombres", "materia"]:
                df_final[col] = df_final[col].apply(limpiar_texto)

            # División en bloques
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
        st.error(f"Error en el procesamiento: {e}")
