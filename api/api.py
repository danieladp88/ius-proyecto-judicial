from fastapi import FastAPI, HTTPException
from esquemas import Causa
import servicio_modelo as servicio

app = FastAPI(title="API de duración de causas judiciales", version="1.1.0",
              description="Prototipo histórico de causas finalizadas de Buenos Aires")

@app.get("/")
@app.get("/v1/health")
def estado():
    return {"estado": "ok", "proyecto": "Duración de causas judiciales",
            "modelo": servicio.metricas["modelo_elegido"], "provincia": "Buenos Aires",
            "periodo_finalizacion": servicio.metricas["periodo_finalizacion"]}

@app.get("/opciones")
@app.get("/v1/opciones")
def opciones():
    return {"provincia": "Buenos Aires", "ejemplo": servicio.ejemplo,
            "categorias": servicio.categorias,
            "combinaciones": servicio.combinaciones.to_dict(orient="records")}

@app.get("/metricas")
def consultar_metricas():
    return servicio.metricas

@app.get("/v1/model-info")
def informacion_modelo():
    return {"version_api": app.version, "tipo": servicio.paquete["tipo"],
            "tarea": "regresión", "objetivo": "duración total histórica en días corridos",
            "fuente": "https://datos.jus.gob.ar/dataset/oralidad-en-los-procesos-civiles",
            "metricas": servicio.metricas}

@app.post("/predecir")
@app.post("/v1/predict")
def predecir(causa: Causa):
    try:
        return servicio.predecir(causa.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/informe")
@app.post("/v1/informe")
def generar_informe(causa: Causa):
    try:
        return servicio.generar_informe(causa.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
