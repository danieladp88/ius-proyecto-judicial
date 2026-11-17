from pathlib import Path
import json
import re

import pandas as pd


CARPETA = Path(__file__).resolve().parent / "datos"

ENTRADA = CARPETA / "causas_buenos_aires.csv"
SALIDA = CARPETA / "causas_limpias_buenos_aires.csv"

CLAVE_CAUSA = [
    "provincia_id",
    "localidad_nombre",
    "juzgado_numero",
    "causa_id",
]

VARIABLES = [
    "localidad_nombre",
    "juzgado_numero",
    "causa_objeto_litigio_descripcion",
]


def limpiar_texto(valor):
    if pd.isna(valor):
        return pd.NA

    texto = re.sub(r"\s+", " ", str(valor)).strip()
    return texto.upper() if texto else pd.NA


def main():
    if not ENTRADA.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ENTRADA}"
        )

    datos = pd.read_csv(ENTRADA, dtype="string")
    filas_originales = len(datos)

    requeridas = set(
        CLAVE_CAUSA
        + VARIABLES
        + ["causa_fecha_recepcion", "proceso_finalizacion_fecha"]
    )

    faltantes = requeridas.difference(datos.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas necesarias: {sorted(faltantes)}"
        )

    # Normalizamos espacios y mayúsculas
    for columna in set(CLAVE_CAUSA + VARIABLES):
        datos[columna] = datos[columna].map(limpiar_texto)

    # Evitamos identificadores como "1.0" cuando representan "1"
    for columna in ["provincia_id", "juzgado_numero"]:
        datos[columna] = datos[columna].str.replace(
            r"^(\d+)\.0$", r"\1", regex=True
        )

    duplicados = int(datos.duplicated().sum())
    datos = datos.drop_duplicates().copy()

    # La duración se mide desde recepción hasta finalización
    datos["fecha_inicio"] = pd.to_datetime(
        datos["causa_fecha_recepcion"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    datos["fecha_fin"] = pd.to_datetime(
        datos["proceso_finalizacion_fecha"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    fechas_invalidas = (
        datos["fecha_inicio"].isna()
        | datos["fecha_fin"].isna()
    )

    excluidas_fechas = int(fechas_invalidas.sum())

    datos = datos.loc[~fechas_invalidas].copy()

    datos["duracion_dias"] = (
        datos["fecha_fin"] - datos["fecha_inicio"]
    ).dt.days

    negativas = datos["duracion_dias"].lt(0)
    excluidas_negativas = int(negativas.sum())

    datos = datos.loc[~negativas].copy()

    incompletas = datos[
        list(dict.fromkeys(CLAVE_CAUSA + VARIABLES))
    ].isna().any(axis=1)

    excluidas_incompletas = int(incompletas.sum())
    datos = datos.loc[~incompletas].copy()

    # Una causa repetida puede tener registros contradictorios
    campos_comparacion = [
        "causa_objeto_litigio_descripcion",
        "fecha_inicio",
        "fecha_fin",
    ]

    diferencias = datos.groupby(
        CLAVE_CAUSA
    )[campos_comparacion].transform("nunique")

    conflictivas = diferencias.gt(1).any(axis=1)

    revision = datos.loc[conflictivas].copy()

    cantidad_conflictos = len(
        revision[CLAVE_CAUSA].drop_duplicates()
    )

    revision.to_csv(
        CARPETA / "buenos_aires_causas_a_revisar.csv",
        index=False,
        encoding="utf-8",
    )

    datos = datos.loc[~conflictivas].copy()

    # Si objeto y fechas coinciden, conservamos una sola fila
    repeticiones_coherentes = int(
        datos.duplicated(subset=CLAVE_CAUSA).sum()
    )

    datos = datos.drop_duplicates(
        subset=CLAVE_CAUSA
    ).copy()

    if datos.empty:
        raise ValueError(
            "No quedaron causas utilizables. Revisá los archivos."
        )

    datos["duracion_dias"] = datos["duracion_dias"].astype(int)

    datos = datos.sort_values(
        ["fecha_fin"] + CLAVE_CAUSA
    ).reset_index(drop=True)

    datos.to_csv(
        SALIDA,
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d",
    )

    resumen = {
        "provincia": "Buenos Aires",
        "filas_originales": filas_originales,
        "duplicados_eliminados_tras_normalizar": duplicados,
        "filas_excluidas_por_fechas": excluidas_fechas,
        "duraciones_negativas_excluidas": excluidas_negativas,
        "filas_excluidas_por_datos_faltantes": excluidas_incompletas,
        "causas_con_datos_conflictivos": cantidad_conflictos,
        "filas_conflictivas_excluidas": len(revision),
        "repeticiones_coherentes_eliminadas": repeticiones_coherentes,
        "causas_limpias": len(datos),
        "localidades_con_causas_limpias": int(
            datos["localidad_nombre"].nunique()
        ),
        "primera_finalizacion": (
            datos["fecha_fin"].min().date().isoformat()
        ),
        "ultima_finalizacion": (
            datos["fecha_fin"].max().date().isoformat()
        ),
        "mediana_duracion_dias": float(
            datos["duracion_dias"].median()
        ),
        "duracion_maxima_dias": int(
            datos["duracion_dias"].max()
        ),
        "definicion_duracion": (
            "Días corridos entre recepción y finalización."
        ),
        "criterio_repeticiones": (
            "Entre registros con fechas y variables completas, "
            "se conserva una fila por causa cuando coinciden "
            "objeto y fechas. Las contradicciones se separan "
            "para revisión."
        ),
        "limitacion": (
            "La muestra incluye solamente causas con fechas "
            "observables y finalización informada. No permite "
            "estimar directamente el tiempo restante de causas abiertas."
        ),
    }

    texto = json.dumps(
        resumen, ensure_ascii=False, indent=2
    )

    (CARPETA / "limpieza_buenos_aires.json").write_text(
        texto, encoding="utf-8"
    )

    print("\nRESULTADO DE LA LIMPIEZA\n")
    print(texto)

    print("\nOBJETOS DE LITIGIO MÁS FRECUENTES\n")

    tabla = (
        datos.groupby("causa_objeto_litigio_descripcion")
        ["duracion_dias"]
        .agg(
            cantidad="size",
            mediana_dias="median",
            minimo_dias="min",
            maximo_dias="max",
        )
        .sort_values("cantidad", ascending=False)
    )

    tabla.to_csv(
        CARPETA / "resumen_objetos_buenos_aires.csv",
        encoding="utf-8",
    )

    print(tabla.head(15).to_string())
    print(f"\nDatos preparados en: {SALIDA.name}")


if __name__ == "__main__":
    main()