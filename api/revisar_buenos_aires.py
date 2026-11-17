from pathlib import Path
from io import BytesIO
import hashlib
import json
import unicodedata
import urllib.request

import pandas as pd


CARPETA = Path(__file__).resolve().parent / "datos"
CARPETA.mkdir(parents=True, exist_ok=True)

URL = (
    "https://datos.jus.gob.ar/dataset/"
    "85ea4aa6-6873-4583-8d8d-7b6463a901f6/resource/"
    "de4e8278-340d-4190-9f0b-c41292f673d4/download/"
    "oralidad-procesos-civiles-buenos-aires.xlsx"
)


def normalizar_columna(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre).strip())
    return "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )


def main():
    print("Descargando datos oficiales de Buenos Aires...")

    with urllib.request.urlopen(URL, timeout=120) as respuesta:
        contenido = respuesta.read()

    (CARPETA / "buenos_aires_original.xlsx").write_bytes(contenido)

    datos = pd.read_excel(
        BytesIO(contenido),
        sheet_name="oralidad-procesos-civiles",
        dtype=object,
        engine="openpyxl",
    )

    datos.columns = [
        normalizar_columna(columna)
        for columna in datos.columns
    ]

    for columna in datos.select_dtypes(include="object").columns:
        datos[columna] = datos[columna].map(
            lambda valor: valor.strip()
            if isinstance(valor, str)
            else valor
        )

    datos = datos.replace(r"^\s*$", pd.NA, regex=True)

    inicio = pd.to_datetime(
        datos["causa_fecha_recepcion"], errors="coerce"
    )
    fin = pd.to_datetime(
        datos["proceso_finalizacion_fecha"], errors="coerce"
    )
    duracion = (fin - inicio).dt.days

    observables = inicio.notna() & fin.notna() & duracion.ge(0)

    datos.to_csv(
        CARPETA / "causas_buenos_aires.csv",
        index=False,
        encoding="utf-8",
    )

    resumen = {
        "fuente": "Oralidad en los procesos civiles - Buenos Aires",
        "url": URL,
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "filas_originales": len(datos),
        "duplicados_exactos": int(datos.duplicated().sum()),
        "filas_sin_inicio_valido": int(inicio.isna().sum()),
        "filas_sin_fin_valido": int(fin.isna().sum()),
        "duraciones_negativas": int(duracion.lt(0).sum()),
        "filas_con_duracion_observable": int(observables.sum()),
        "localidades_distintas": int(
            datos["localidad_nombre"].nunique()
        ),
        "primera_finalizacion": (
            fin.min().date().isoformat()
            if fin.notna().any() else None
        ),
        "ultima_finalizacion": (
            fin.max().date().isoformat()
            if fin.notna().any() else None
        ),
        "columnas": datos.columns.tolist(),
    }

    texto = json.dumps(resumen, ensure_ascii=False, indent=2)

    (CARPETA / "revision_buenos_aires.json").write_text(
        texto, encoding="utf-8"
    )

    print("\nRESULTADO DE LA REVISIÓN\n")
    print(texto)
    print("\nLOCALIDADES MÁS FRECUENTES\n")
    print(datos["localidad_nombre"].value_counts().head(15))
    print("\nArchivos guardados en api/datos.")


if __name__ == "__main__":
    main()
