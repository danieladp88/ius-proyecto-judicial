from pathlib import Path
import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

paquete = joblib.load(
    BASE_DIR / "modelo_judicial.joblib"
)

if paquete.get("tipo") != "judicial-duracion-v1":
    raise RuntimeError(
        "El archivo no contiene el modelo judicial esperado"
    )

modelo = paquete["modelo"]
variables = paquete["variables"]
categorias = paquete["categorias"]
metricas = paquete["metricas"]

antecedentes = pd.DataFrame(
    paquete["antecedentes"]
)

combinaciones = (
    antecedentes
    .groupby(variables)
    .size()
    .reset_index(name="cantidad_antecedentes")
    .sort_values(variables)
)

ejemplo = {
    variable: str(
        combinaciones.iloc[0][variable]
    )
    for variable in variables
}


def predecir(entrada: dict):

    for variable in variables:
        if entrada[variable] not in categorias[variable]:
            raise ValueError(
                    f"Valor fuera del alcance en {variable}. "
                    "Consultá /opciones"
            )

    mismo_juzgado = (
        (
            antecedentes["localidad_nombre"]
            == entrada["localidad_nombre"]
        )
        & (
            antecedentes["juzgado_numero"]
            == entrada["juzgado_numero"]
        )
    )

    if not mismo_juzgado.any():
        raise ValueError(
                "La combinación de localidad y juzgado "
                "no tiene antecedentes en ajuste"
        )

    fila = pd.DataFrame(
        [entrada],
        columns=variables,
    )

    dias = float(
        modelo.predict(fila)[0]
    )

    coincidencias = pd.Series(
        True,
        index=antecedentes.index,
    )

    for variable in variables:
        coincidencias &= (
            antecedentes[variable]
            == entrada[variable]
        )

    grupo = antecedentes.loc[
        coincidencias,
        "duracion_dias",
    ]

    cantidad = len(grupo)

    avisos = list(
        metricas["limitaciones"]
    )

    if cantidad < 5:
        avisos.append(
            "La combinación exacta tiene menos de cinco "
            "antecedentes de ajuste. "
            "La estimación tiene soporte limitado"
        )

    return {
        "provincia": "Buenos Aires",
        "entrada": entrada,

        "duracion_estimada_dias": round(
            dias,
            1,
        ),

        "duracion_estimada_meses": round(
            dias / 30.44,
            1,
        ),

        "antecedentes_combinacion": cantidad,

        "mediana_historica_combinacion_dias": (
            round(
                float(grupo.median()),
                1,
            )
            if cantidad
            else None
        ),

        "mae_global_prueba_dias": round(
            metricas["mae_modelo_prueba_dias"],
            1,
        ),

        "periodo_fuente": (
            metricas["periodo_finalizacion"]
        ),

        "modelo": metricas["modelo_elegido"],

        "advertencias": avisos,
    }



def generar_informe(entrada: dict):
    resultado = predecir(entrada)

    periodo = resultado["periodo_fuente"]

    texto = (
        "INFORME DE DURACIÓN HISTÓRICA\n\n"

        "Provincia: Buenos Aires\n"

        f"Localidad: {entrada['localidad_nombre']}\n"

        f"Juzgado: {entrada['juzgado_numero']}\n"

        f"Objeto: "
        f"{entrada['causa_objeto_litigio_descripcion']}\n\n"

        f"Duración total estimada: "
        f"{resultado['duracion_estimada_dias']} "
        "días corridos.\n"

        f"Meses aproximados: "
        f"{resultado['duracion_estimada_meses']}.\n"

        f"Antecedentes de la combinación: "
        f"{resultado['antecedentes_combinacion']}.\n"

        f"MAE global en prueba: "
        f"{resultado['mae_global_prueba_dias']} días. "

        "Este error medio no es un margen "
        "garantizado para el caso.\n\n"

        "Fuente: Ministerio de Justicia, "
        "Oralidad en los procesos civiles - Buenos Aires.\n"

        "https://datos.jus.gob.ar/dataset/"
        "oralidad-en-los-procesos-civiles\n"

        f"Finalizaciones observadas: "
        f"{periodo['desde']} a {periodo['hasta']}.\n\n"

        "LIMITACIONES\n"

        + "\n".join(
            f"- {aviso}"
            for aviso in resultado["advertencias"]
        )
    )

    return {
        "texto": texto,
        "estimacion": resultado,
    }
