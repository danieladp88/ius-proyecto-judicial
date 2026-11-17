import json

from pathlib import Path

import pandas as pd

from revisar_datos import (
    convertir_fechas,
    normalizar_nombre,
)


BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"

CLAVE_CAUSA = [
    "provincia_id",
    "localidad_nombre",
    "juzgado_numero",
    "causa_id",
]

COLUMNAS_TEXTO = [
    "provincia_id",
    "provincia_nombre",
    "localidad_nombre",
    "juzgado_numero",
    "causa_id",
    "causa_objeto_litigio_descripcion",
]

# Corrección explícita de una variante encontrada en la fuente
CORRECCIONES_OBJETO = {
    "ORDINARIO DAÑ‘OS Y PERJUICIOS": (
        "ORDINARIO DAÑOS Y PERJUICIOS"
    ),
}


def main():
    origen = DATOS_DIR / "causas_entre_rios.csv"

    if not origen.exists():
        raise FileNotFoundError(
            "Falta api/datos/causas_entre_rios.csv "
            "Ejecutá primero revisar_datos.py"
        )

    datos = pd.read_csv(
        origen,
        dtype="string",
        encoding="utf-8-sig",
    )

    datos.columns = [
        normalizar_nombre(columna)
        for columna in datos.columns
    ]

    requeridas = set(
        COLUMNAS_TEXTO
        + [
            "causa_fecha_recepcion",
            "proceso_finalizacion_fecha",
        ]
    )

    faltantes = requeridas - set(datos.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas necesarias: {faltantes}"
        )

    informe = {
        "filas_originales": len(datos),
    }

    informe["duplicados_exactos_eliminados"] = int(
        datos.duplicated().sum()
    )

    datos = datos.drop_duplicates().copy()

    for columna in COLUMNAS_TEXTO:
        datos[columna] = (
            datos[columna]
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True,
            )
            .replace("", pd.NA)
        )

    objeto = "causa_objeto_litigio_descripcion"

    informe["filas_con_objeto_corregido"] = int(
        datos[objeto]
        .isin(CORRECCIONES_OBJETO.keys())
        .sum()
    )

    datos[objeto] = datos[objeto].replace(
        CORRECCIONES_OBJETO
    )

    datos["fecha_inicio"] = convertir_fechas(
        datos["causa_fecha_recepcion"]
    )

    datos["fecha_fin"] = convertir_fechas(
        datos["proceso_finalizacion_fecha"]
    )

    sin_fechas = (
        datos[["fecha_inicio", "fecha_fin"]]
        .isna()
        .any(axis=1)
    )

    informe["filas_excluidas_por_fechas"] = int(
        sin_fechas.sum()
    )

    datos = datos.loc[~sin_fechas].copy()

    datos["duracion_dias"] = (
        datos["fecha_fin"] - datos["fecha_inicio"]
    ).dt.days

    negativas = datos["duracion_dias"] < 0

    informe["duraciones_negativas_excluidas"] = int(
        negativas.sum()
    )

    datos = datos.loc[~negativas].copy()

    sin_datos_requeridos = (
        datos[CLAVE_CAUSA + [objeto]]
        .isna()
        .any(axis=1)
    )

    informe["filas_excluidas_por_datos_faltantes"] = int(
        sin_datos_requeridos.sum()
    )

    datos = datos.loc[
        ~sin_datos_requeridos
    ].copy()

    comprobacion = (
        datos
        .groupby(CLAVE_CAUSA)[
            [
                objeto,
                "fecha_inicio",
                "fecha_fin",
            ]
        ]
        .nunique(dropna=False)
    )

    claves_conflictivas = comprobacion.index[
        comprobacion.gt(1).any(axis=1)
    ]

    filas_conflictivas = (
        pd.MultiIndex.from_frame(
            datos[CLAVE_CAUSA]
        )
        .isin(claves_conflictivas)
    )

    informe["causas_con_datos_conflictivos"] = len(
        claves_conflictivas
    )

    informe["filas_conflictivas_excluidas"] = int(
        filas_conflictivas.sum()
    )

    datos.loc[filas_conflictivas].to_csv(
        DATOS_DIR / "causas_a_revisar.csv",
        index=False,
        encoding="utf-8-sig",
    )

    datos = datos.loc[
        ~filas_conflictivas
    ].copy()

    informe["repeticiones_coherentes_eliminadas"] = int(
        datos.duplicated(CLAVE_CAUSA).sum()
    )

    datos = datos.drop_duplicates(
        subset=CLAVE_CAUSA
    ).copy()

    if datos.empty:
        raise ValueError(
            "No quedaron causas utilizables "
            "después de la limpieza"
        )

    datos["duracion_dias"] = (
        datos["duracion_dias"].astype(int)
    )

    columnas_salida = CLAVE_CAUSA + [
        "provincia_nombre",
        objeto,
        "fecha_inicio",
        "fecha_fin",
        "duracion_dias",
    ]

    datos = (
        datos[columnas_salida]
        .sort_values(
            [
                "fecha_fin",
                "localidad_nombre",
                "causa_id",
            ]
        )
        .reset_index(drop=True)
    )

    if datos.duplicated(CLAVE_CAUSA).any():
        raise ValueError(
            "Quedaron causas duplicadas"
        )

    datos.to_csv(
        DATOS_DIR / "causas_limpias.csv",
        index=False,
        encoding="utf-8-sig",
    )

    resumen = (
        datos
        .groupby(objeto)["duracion_dias"]
        .agg(
            cantidad="count",
            mediana_dias="median",
            minimo_dias="min",
            maximo_dias="max",
        )
        .sort_values(
            "cantidad",
            ascending=False,
        )
    )

    resumen.to_csv(
        DATOS_DIR / "resumen_limpio.csv",
        encoding="utf-8-sig",
    )

    informe["causas_limpias"] = len(datos)

    informe["correcciones_objeto"] = (
        CORRECCIONES_OBJETO
    )

    informe["definicion_duracion"] = (
        "Días corridos entre recepción "
        "y finalización del proceso"
    )

    informe["criterio_causas_repetidas"] = (
        "Se conserva una fila si coinciden objeto "
        "y fechas. Si difieren, la causa se separa "
        "para revisión"
    )

    (DATOS_DIR / "informe_limpieza.json").write_text(
        json.dumps(
            informe,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\nRESULTADO DE LA LIMPIEZA\n"
    )

    print(
        json.dumps(
            informe,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        "\nOBJETOS DE LITIGIO MÁS FRECUENTES\n"
    )

    print(
        resumen.head(10).to_string()
    )


if __name__ == "__main__":
    main()