# Duración histórica de causas judiciales — entrega final

Brian Barbizan y Daniela Palazzo · Práctica Profesional

Prototipo para un estudio jurídico: permite consultar la duración total histórica de causas civiles finalizadas de Buenos Aires, según localidad, juzgado y objeto del litigio. Sirve como referencia exploratoria para una conversación inicial. No estima tiempo restante ni demuestra capacidad para predecir plazos actuales

## Inicio con Docker (Windows, Linux o macOS)

Con Docker Desktop iniciado, abrí una terminal en esta carpeta, donde está `docker-compose.yml`:

```bash
docker compose up --build
```

- Interfaz: http://localhost:8501
- Documentación de la API: http://localhost:8001/docs
- Estado: http://localhost:8001/v1/health

Esperá a que la API esté saludable y la interfaz quede disponible. El primer build descarga dependencias. El modelo ya está incluido: no se vuelve a entrenar al construir la imagen.

Para detener: `docker compose down`. Para diagnosticar: `docker compose ps` y `docker compose logs api interfaz`

## Inicio sin Docker

Usar Python 3.12 y un entorno virtual. Desde la raíz:

```bash
python -m venv .venv
```

En PowerShell: `.venv\Scripts\Activate.ps1`. En Linux/macOS: `source .venv/bin/activate`.

```bash
python -m pip install -r api/requirements.txt -r interfaz/requirements.txt -r tests/requirements.txt
python -m uvicorn api:app --app-dir api --host 127.0.0.1 --port 8001
```

En otra terminal, con el mismo entorno activado:

```bash
python interfaz/app.py
```

`API_URL` es opcional: por defecto la interfaz consulta `http://localhost:8001`. En Docker usa `http://api:8000`, el nombre del servicio dentro de la red interna

## Cómo se usa

La pantalla tiene cuatro secciones:

1. **Nueva consulta:** elegir localidad, juzgado y objeto. Estimar duración y descargar el informe.
2. **Asistente:** escribir «Quiero consultar en Morón, juzgado 7», elegir el objeto sugerido y confirmar. Las estimaciones salen de la misma API.
3. **Historial:** revisar hasta 30 consultas realizadas por formulario o chat. Solo vive en la memoria de la página y se elimina al recargar.
4. **El modelo:** ver error medio, comparación con la base, particiones, fuente y limitaciones.

El asistente es **guiado por reglas**, no es un LLM ni un chatbot jurídico general. Reconoce localidades y juzgados del catálogo, ofrece categorías válidas y responde preguntas previstas sobre métricas y alcance. No necesita claves ni un servicio de IA de pago. No redacta escritos ni genera asesoramiento jurídico

## Organización

| Archivo/carpeta | Responsabilidad |
|---|---|
| `api/api.py` | Rutas HTTP y traducción de errores a respuestas 422 |
| `api/esquemas.py` | Contrato de entrada y validación de tipos y longitudes |
| `api/servicio_modelo.py` | Carga del artefacto, inferencia, antecedentes e informe |
| `api/modelo_judicial.joblib` | Pipeline entrenado incluido en la tercera entrega |
| `api/metricas_judiciales.json` | Evaluación correspondiente a ese modelo |
| `api/entrenar.py` y `api/datos/` | Reproducción del entrenamiento, separada del despliegue |
| `interfaz/app.py` | Servidor Flask; consume FastAPI por HTTP, no carga joblib |
| `tests/` | Pruebas del contrato con el modelo real |
| `doc/` | Integración, contrato, presentación y evidencias previas |
| `interfaz/conversacion.py` | Diálogo guiado, validación del contexto y consulta de estimación |
| `interfaz/templates/` y `interfaz/static/` | HTML, CSS adaptable y JavaScript del navegador |

## Pruebas

Desde la raíz, luego de instalar las dependencias:

```bash
python -m unittest discover -s tests -v
```

No hace falta levantar un servidor para estas pruebas: TestClient ejecuta la aplicación FastAPI real en el proceso de prueba. Ver `doc/VALIDACION.md` para el alcance de la verificación realizada

## Modelo de la tercera entrega

Esta versión utiliza exactamente el archivo `modelo_judicial.joblib` de `Tercera_entrega_judicial(3).zip`, sin reentrenarlo. Se mantienen sus métricas, predicciones de prueba y dataset. Se incluye la notebook original en `antecedentes/`.

Random Forest: MAE de prueba **395,95 días**, base **442,73 días**, mejora **10,57 %**. Finalizaciones observadas: 2016-08-12 a 2019-09-30. Total: 8.752 causas.

Las dependencias del modelo coinciden con las declaradas en esa entrega: pandas 2.2.3, numpy 2.4.6, scikit-learn 1.6.1 y joblib 1.6.0. El entorno original declara Python 3.13.18. La integración se verificó con Python 3.12.14 y el Dockerfile conserva 3.12.10: esa diferencia de Python está documentada y el contenedor debe validarse en la computadora de exposición. Se contrastaron las 1.756 predicciones guardadas: diferencia máxima de 2,3 × 10^-13 días, atribuible a representación numérica.

El script `api/entrenar.py` queda como alternativa de reproducción del proyecto. Ejecutarlo reemplaza el artefacto y exige volver a validar métricas. Para presentar esta versión, usar el archivo persistido incluido sin reentrenar

## Documentación para entregar

- `doc/INTEGRACION.md`: caso de uso, escenarios, arquitectura y requisitos
- `doc/CONTRATO_API.md`: entradas, salidas y errores
- `doc/PRESENTACION.md`: guion de 7–10 minutos y demostración
- `doc/VALIDACION.md`: comprobaciones y pendientes reales

Las capturas de `doc/evidencias/` son las recibidas con el proyecto; conviene actualizarlas al ejecutar esta versión. No se publicaron servicios en Internet. El Docker Compose mantiene los puertos limitados a esta computadora

## Entrega final del módulo 17/11 y 19/11

Empezar por `doc/ENTREGA_FINAL.md`. La presentación editable y su copia PDF están en `presentacion/`. El guion propone un reparto entre ambos integrantes y dura 8 minutos 30 segundos.

La guía Docker pide publicar la API en Docker Hub y verificar su ejecución por un compañero. Ver `doc/DOCKER_HUB.md`: estos pasos externos están pendientes y requieren tu cuenta y una prueba real en otro equipo

## Actualizar desde la versión anterior

Extraer este ZIP en una carpeta nueva. Detener la versión anterior desde su carpeta con `docker compose down` para liberar los puertos. En la carpeta nueva, ejecutar `docker compose up --build`. No usar los contenedores anteriores sin reconstruir: el front ahora es Flask + HTML/CSS/JavaScript.

El puerto de la interfaz se conserva: http://localhost:8501. En Docker se usa Gunicorn. Fuera de Docker, `python interfaz/app.py` inicia el servidor de desarrollo local

## Qué se comprobó

22 pruebas de API/chat/front aprobadas. Integración de Flask con FastAPI y modelo real comprobada en memoria. La prueba del código JavaScript con DOM simulado pasó. La revisión visual en navegador y la ejecución en Docker de esta versión quedaron pendientes por restricciones del entorno de revisión
