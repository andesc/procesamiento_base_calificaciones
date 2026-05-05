import pandas as pd
import io
import os
from google.colab import files

def procesar_flujo_nombres_dinamicos():
    try:
        # --- ETAPA 1: Carga y limpieza del PRIMER archivo (CSV) ---
        print("1. CARGA DEL PRIMER ARCHIVO (CSV):")
        subida_1 = files.upload()
        nombre_csv_completo = list(subida_1.keys())[0]

        # --- Lógica para el nombre del archivo de salida ---
        # Ejemplo: 2026-04-30T1730_Calificaciones-ANÁLISIS_Y_VISUALIZACIÓN_DE_DATOS.csv
        try:
            # 1. Quitamos la extensión .csv
            nombre_sin_ext = os.path.splitext(nombre_csv_completo)[0]

            # 2. Extraemos la fecha (YYYY-MM-DD) de los primeros 10 caracteres
            fecha_iso = nombre_sin_ext[:10] # "2026-04-30"
            partes_fecha = fecha_iso.split('-')
            fecha_formateada = f"{partes_fecha[2]}-{partes_fecha[1]}" # "30-04"

            # 3. Extraemos el nombre de la materia (después de "Calificaciones-")
            if "Calificaciones-" in nombre_sin_ext:
                materia = nombre_sin_ext.split("Calificaciones-")[1]
            else:
                materia = "Procesado" # Fallback si el nombre no cumple el patrón

            nombre_salida = f"{materia}-{fecha_formateada}.xlsx"
        except:
            nombre_salida = "lista_emails_final.xlsx" # Fallback general

        # Lectura del CSV
        df_primer_paso = pd.read_csv(io.BytesIO(subida_1[nombre_csv_completo]))
        df_primer_paso.columns = df_primer_paso.columns.str.strip()

        if "SIS Login ID" not in df_primer_paso.columns:
            print(f"❌ Error: No se encontró 'SIS Login ID'. Columnas: {list(df_primer_paso.columns)}")
            return

        # --- ETAPA 2: Carga del SEGUNDO archivo (XLSX) ---
        print(f"\n2. CARGA DEL SEGUNDO ARCHIVO (Base de alumnos):")
        subida_2 = files.upload()
        nombre_xlsx = list(subida_2.keys())[0]

        df_segundo = pd.read_excel(io.BytesIO(subida_2[nombre_xlsx]))
        df_segundo.columns = df_segundo.columns.str.strip().str.lower()

        # --- ETAPA 3: Merge ---
        df_primer_paso["SIS Login ID"] = (df_primer_paso["SIS Login ID"]
                                         .astype(str).str.strip().str.replace('.0', '', regex=False))
        df_segundo["dni"] = (df_segundo["dni"]
                             .astype(str).str.strip().str.replace('.0', '', regex=False))

        df_unido = pd.merge(
            df_primer_paso,
            df_segundo[['dni', 'email']],
            left_on="SIS Login ID",
            right_on="dni",
            how="inner"
        )

        # --- ETAPA 4: Verificación y Descarga ---
        if not df_unido.empty:
            print(f"\n✓ Se encontraron {len(df_unido)} coincidencias.")

            df_final = df_unido[['email']].drop_duplicates()

            print(f"Generando archivo: {nombre_salida}")
            df_final.to_excel(nombre_salida, index=False)
            files.download(nombre_salida)
        else:
            print("\n⚠️ No se encontraron coincidencias entre el SIS Login ID y el DNI.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    procesar_flujo_nombres_dinamicos()