import hashlib
import json
import unicodedata

from pathlib import Path
from urllib.request import urlopen

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"

CATALOGO_URL = (
    "https://datos.jus.gob.ar/api/3/action/"
    "package_show?id=oralidad-en-los-procesos-civiles"
)


def normalizar_nombre(nombre):
    return "".join(
        caracter
        for caracter in unicodedata.normalize(
            "NFKD",
            nombre.strip().lower(),
        )
        if not unicodedata.combining(caracter)
    )


def convertir_fechas(columna):
    valores = columna.astype("string").str.strip()

    formato_local = valores.str.contains(
        "/",
        na=False,
    )

    fechas_iso = pd.to_datetime(
        valores.where(~formato_local),
        format="%Y-%m-%d",
        errors="coerce",
    )

    fechas_locales = pd.to_datetime(
        valores.where(formato_local),
        format="%d/%m/%Y",
        errors="coerce",
    )

    return fechas_iso.fillna(fechas_locales)


def main():
    DATOS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Consultando el catálogo oficial...",
        flush=True,
    )

    with urlopen(
        CATALOGO_URL,
        timeout=60,
    ) as respuesta:
        catalogo = json.load(respuesta)

    if not catalogo.get("success"):
        raise RuntimeError(
            "No se pudo consultar el catálogo oficial"
        )

    recurso = next(
        (
            item
            for item in catalogo["result"]["resources"]
            if item["url"].endswith(
                "oralidad-procesos-civiles-entre-rios.csv"
            )
        ),
        None,
    )

    if recurso is None:
        raise RuntimeError(
            "No se encontró el recurso de Entre Ríos "
            "El catálogo puede haber cambiado"
        )

    print(
        "Descargando datos judiciales...",
        flush=True,
    )

    with urlopen(
        recurso["url"],
        timeout=90,
    ) as respuesta:
        contenido = respuesta.read()

    if contenido.lstrip().startswith(b"<"):
        raise RuntimeError(
            "El portal devolvió una página HTML "
            "en lugar del archivo CSV."
        )

    archivo = DATOS_DIR / "causas_entre_rios.csv"
    archivo.write_bytes(contenido)

    datos = pd.read_csv(
        archivo,
        dtype="string",
        encoding="utf-8-sig",
    )

    datos.columns = [
        normalizar_nombre(columna)
        for columna in datos.columns
    ]

    requeridas = {
        "causa_fecha_recepcion",
        "proceso_finalizacion_fecha",
        "causa_objeto_litigio_descripcion",
    }

    faltantes = requeridas - set(datos.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas necesarias: {faltantes}"
        )

    filas_originales = len(datos)

    duplicados = int(
        datos.duplicated().sum()
    )

    datos = datos.drop_duplicates().copy()

    datos["fecha_inicio"] = convertir_fechas(
        datos["causa_fecha_recepcion"]
    )

    datos["fecha_fin"] = convertir_fechas(
        datos["proceso_finalizacion_fecha"]
    )

    datos["duracion_dias"] = (
        datos["fecha_fin"] - datos["fecha_inicio"]
    ).dt.days

    fechas_validas = (
        datos["fecha_inicio"].notna()
        & datos["fecha_fin"].notna()
    )

    duraciones_negativas = (
        fechas_validas
        & (datos["duracion_dias"] < 0)
    )

    observables = datos.loc[
        fechas_validas
        & (datos["duracion_dias"] >= 0)
    ].copy()

    informe = {
        "fuente": recurso["name"],
        "url": recurso["url"],
        "sha256": hashlib.sha256(
            contenido
        ).hexdigest(),
        "filas_originales": filas_originales,
        "duplicados_exactos": duplicados,
        "filas_sin_fecha_inicio_valida": int(
            datos["fecha_inicio"].isna().sum()
        ),
        "filas_sin_fecha_fin_valida": int(
            datos["fecha_fin"].isna().sum()
        ),
        "filas_con_duracion_negativa": int(
            duraciones_negativas.sum()
        ),
        "filas_con_duracion_observable": len(observables),
        "columnas_disponibles": datos.columns.tolist(),
        "definicion_duracion": (
            "Días corridos entre recepción "
            "y finalización del proceso"
        ),
    }

    if not observables.empty:
        informe["inicio_mas_antiguo"] = (
            observables["fecha_inicio"]
            .min()
            .date()
            .isoformat()
        )

        informe["ultima_finalizacion"] = (
            observables["fecha_fin"]
            .max()
            .date()
            .isoformat()
        )

        informe["mediana_duracion_dias"] = float(
            observables["duracion_dias"].median()
        )

        informe["duracion_maxima_dias"] = int(
            observables["duracion_dias"].max()
        )

        resumen = (
            observables
            .groupby("causa_objeto_litigio_descripcion")
            ["duracion_dias"]
            .agg(
                cantidad="count",
                mediana_dias="median",
            )
            .sort_values(
                "cantidad",
                ascending=False,
            )
        )

        resumen.to_csv(
            DATOS_DIR / "resumen_por_objeto.csv"
        )

    destino = DATOS_DIR / "informe_datos.json"

    destino.write_text(
        json.dumps(
            informe,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\nRESULTADO DE LA REVISIÓN\n",
        flush=True,
    )

    print(
        json.dumps(
            informe,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        "\nArchivos guardados en api/datos.",
        flush=True,
    )


if __name__ == "__main__":
    main()