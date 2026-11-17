import json
import platform

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).resolve().parent

VARIABLES = [
    "localidad_nombre",
    "juzgado_numero",
    "causa_objeto_litigio_descripcion",
]

CLAVE_CAUSA = [
    "provincia_id",
    "localidad_nombre",
    "juzgado_numero",
    "causa_id",
]

OBJETIVO = "duracion_dias"


def crear_pipeline(estimador):
    preparacion = ColumnTransformer(
        [
            (
                "categorias",
                OneHotEncoder(
                    handle_unknown="ignore",
                ),
                VARIABLES,
            )
        ]
    )

    return Pipeline(
        [
            ("preparacion", preparacion),
            ("modelo", estimador),
        ]
    )


def main():
    origen = (
        BASE_DIR
        / "datos"
        / "causas_limpias_buenos_aires.csv"
    )

    datos = pd.read_csv(
        origen,
        dtype="string",
        encoding="utf-8-sig",
    )

    requeridas = set(
        VARIABLES
        + CLAVE_CAUSA
        + ["fecha_fin", OBJETIVO]
    )

    faltantes = requeridas - set(datos.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {faltantes}"
        )

    if datos[list(requeridas)].isna().any().any():
        raise ValueError(
            "Hay valores faltantes. "
            "Revisá la preparación de datos."
        )

    if datos.duplicated(CLAVE_CAUSA).any():
        raise ValueError(
            "Hay causas duplicadas."
        )

    datos[OBJETIVO] = pd.to_numeric(
        datos[OBJETIVO],
        errors="raise",
    )

    if (
        not np.isfinite(datos[OBJETIVO]).all()
        or (datos[OBJETIVO] < 0).any()
    ):
        raise ValueError(
            "Hay duraciones inválidas."
        )

    datos["fecha_fin"] = pd.to_datetime(
        datos["fecha_fin"],
        format="%Y-%m-%d",
        errors="raise",
    )

    datos = (
        datos
        .sort_values(
            ["fecha_fin"] + CLAVE_CAUSA
        )
        .reset_index(drop=True)
    )

    if len(datos) < 100:
        raise ValueError(
            "Hay muy pocas causas para esta evaluación."
        )

    # Los cortes se hacen por fecha para evitar
    # compartir una misma fecha entre particiones.
    corte_validacion = datos["fecha_fin"].iloc[
        int(len(datos) * 0.60)
    ]

    corte_prueba = datos["fecha_fin"].iloc[
        int(len(datos) * 0.80)
    ]

    entrenamiento = datos.loc[
        datos["fecha_fin"] < corte_validacion
    ]

    validacion = datos.loc[
        (datos["fecha_fin"] >= corte_validacion)
        & (datos["fecha_fin"] < corte_prueba)
    ]

    prueba = datos.loc[
        datos["fecha_fin"] >= corte_prueba
    ]

    if min(
        len(entrenamiento),
        len(validacion),
        len(prueba),
    ) < 20:
        raise ValueError(
            "Alguna partición tiene muy pocos registros"
        )

    candidatos = {
        "BaseMediana": DummyRegressor(
            strategy="median",
        ),
        "RandomForest": RandomForestRegressor(
            n_estimators=120,
            criterion="absolute_error",
            min_samples_leaf=5,
            random_state=42,
            n_jobs=2,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=120,
            criterion="absolute_error",
            min_samples_leaf=5,
            random_state=42,
            n_jobs=2,
        ),
    }

    resultados_validacion = {}

    print(
        "Comparando modelos en validación...",
        flush=True,
    )

    for nombre, estimador in candidatos.items():
        pipeline = crear_pipeline(estimador)

        pipeline.fit(
            entrenamiento[VARIABLES],
            entrenamiento[OBJETIVO],
        )

        prediccion = pipeline.predict(
            validacion[VARIABLES]
        )

        mae = float(
            mean_absolute_error(
                validacion[OBJETIVO],
                prediccion,
            )
        )

        resultados_validacion[nombre] = mae

        print(
            f"{nombre}: MAE = {mae:.2f} días",
            flush=True,
        )

    elegido = min(
        resultados_validacion,
        key=resultados_validacion.get,
    )


    ajuste = pd.concat(
        [entrenamiento, validacion],
        ignore_index=True,
    )

    modelo = crear_pipeline(
        candidatos[elegido]
    )

    modelo.fit(
        ajuste[VARIABLES],
        ajuste[OBJETIVO],
    )

    base = DummyRegressor(
        strategy="median",
    )

    base.fit(
        ajuste[VARIABLES],
        ajuste[OBJETIVO],
    )

    predicciones = modelo.predict(
        prueba[VARIABLES]
    )

    predicciones_base = base.predict(
        prueba[VARIABLES]
    )

    mae_modelo = float(
        mean_absolute_error(
            prueba[OBJETIVO],
            predicciones,
        )
    )

    mae_base = float(
        mean_absolute_error(
            prueba[OBJETIVO],
            predicciones_base,
        )
    )

    mejora = (
        100 * (mae_base - mae_modelo) / mae_base
        if mae_base > 0
        else None
    )

    categorias = {
        variable: sorted(
            ajuste[variable].unique().tolist()
        )
        for variable in VARIABLES
    }

    categorias_conocidas = pd.Series(
        True,
        index=prueba.index,
    )

    for variable in VARIABLES:
        categorias_conocidas &= (
            prueba[variable].isin(
                categorias[variable]
            )
        )

    cobertura_categorias = float(
        categorias_conocidas.mean() * 100
    )

    metricas = {
        "modelo_elegido": elegido,
        "causas_totales": len(datos),

        "particion": {
            "entrenamiento": len(entrenamiento),
            "validacion": len(validacion),
            "prueba": len(prueba),
            "inicio_validacion": (
                corte_validacion.date().isoformat()
            ),
            "inicio_prueba": (
                corte_prueba.date().isoformat()
            ),
            "criterio": (
                "Separación temporal por finalización "
                "Selección en validación y evaluación "
                "final en prueba."
            ),
        },

        "mae_validacion": resultados_validacion,
        "mae_modelo_prueba_dias": mae_modelo,
        "mae_base_prueba_dias": mae_base,
        "mejora_mae_porcentaje": mejora,

        "cumple_mejora_10_por_ciento": bool(
            mejora is not None
            and mejora >= 10
        ),

        "cobertura_categorias_conocidas_porcentaje": (
            cobertura_categorias
        ),

        "definicion_cobertura_categorias": (
            "Porcentaje de causas de prueba cuyos "
            "valores de localidad, juzgado y objeto "
            "aparecieron individualmente en ajuste. "
            "No exige antecedentes de la combinación "
            "exacta ni garantiza precisión"
        ),

        "periodo_finalizacion": {
            "desde": (
                datos["fecha_fin"]
                .min()
                .date()
                .isoformat()
            ),
            "hasta": (
                datos["fecha_fin"]
                .max()
                .date()
                .isoformat()
            ),
        },

        "variables": VARIABLES,

        "versiones": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },

        "limitaciones": [
            "Solo datos históricos de Buenos Aires.",
            "Solo causas con finalización informada",
            (
                "Excluir causas sin cierre puede sesgar "
                "las duraciones observadas."
            ),
            (
                "La evaluación no demuestra capacidad "
                "para estimar plazos actuales."
            ),
            (
                "Se estima duración total histórica, "
                "no tiempo restante de causas abiertas"
            ),
        ],
    }

    paquete = {
        "tipo": "judicial-duracion-v1",
        "modelo": modelo,
        "variables": VARIABLES,
        "categorias": categorias,
        "metricas": metricas,
        "antecedentes": (
            ajuste[VARIABLES + [OBJETIVO]]
            .to_dict(orient="records")
        ),
    }

    joblib.dump(
        paquete,
        BASE_DIR / "modelo_judicial.joblib",
    )

    (BASE_DIR / "metricas_judiciales.json").write_text(
        json.dumps(
            metricas,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    evaluacion = prueba[
        CLAVE_CAUSA
        + ["fecha_fin", OBJETIVO]
    ].copy()

    evaluacion["prediccion_modelo_dias"] = (
        predicciones
    )

    evaluacion["prediccion_base_dias"] = (
        predicciones_base
    )

    evaluacion["categorias_conocidas"] = (
        categorias_conocidas
    )

    evaluacion.to_csv(
        BASE_DIR / "predicciones_prueba.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\nRESULTADO DEL MODELO JUDICIAL\n"
    )

    print(
        json.dumps(
            metricas,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        "\nModelo guardado en "
        "api/modelo_judicial.joblib",
        flush=True,
    )


if __name__ == "__main__":
    main()
