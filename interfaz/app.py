"""Front web: las llamadas al modelo ocurren por HTTP desde este servidor."""
import os
import requests
from flask import Flask, jsonify, render_template, request
from conversacion import conversar

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
API_URL = os.getenv('API_URL', 'http://localhost:8001').rstrip('/')

class ErrorServicio(Exception):
    def __init__(self, mensaje, estado=503):
        self.mensaje, self.estado = mensaje, estado

def consultar(metodo, ruta, datos=None):
    try:
        r = requests.request(metodo, API_URL + ruta, json=datos, timeout=30)
    except requests.RequestException as exc:
        raise ErrorServicio('No pudimos conectar con el servicio de estimación. Volvé a intentar en unos instantes') from exc
    try:
        d = r.json()
    except ValueError as exc:
        raise ErrorServicio('El servicio devolvió una respuesta inesperada', 502) from exc
    if not r.ok:
        detail = d.get('detail')
        if isinstance(detail, list):
            detail = 'Revisá los datos: hay campos incompletos o con un formato inválido'
        raise ErrorServicio(detail if isinstance(detail, str) else 'No se pudo completar la consulta', 422 if r.status_code == 422 else 502)
    return d

@app.errorhandler(ErrorServicio)
def error_servicio(exc):
    return jsonify(error=exc.mensaje), exc.estado

@app.errorhandler(413)
def demasiado_grande(exc):
    return jsonify(error='El mensaje supera el tamaño permitido'), 413

@app.get('/')
def inicio():
    return render_template('index.html')

@app.get('/api/inicio')
def inicio_datos():
    return jsonify(opciones=consultar('GET','/v1/opciones'), modelo=consultar('GET','/v1/model-info'))

@app.post('/api/informe')
def informe():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error='Completá los datos de la causa'), 400
    return jsonify(consultar('POST','/v1/informe',datos))

@app.post('/api/chat')
def chat():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not isinstance(datos.get('mensaje'), str):
        return jsonify(error='Escribí un mensaje para continuar'), 400
    mensaje = datos['mensaje'].strip()
    if not mensaje or len(mensaje) > 1500:
        return jsonify(error='El mensaje debe tener entre 1 y 1500 caracteres'), 400
    contexto = datos.get('contexto', {})
    if not isinstance(contexto, dict):
        return jsonify(error='No se pudo recuperar la conversación. Iniciá una nueva'), 400
    opciones = consultar('GET','/v1/opciones')
    info = consultar('GET','/v1/model-info')
    return jsonify(conversar(mensaje, contexto, opciones, info, consultar))

@app.after_request
def cabeceras(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8501, debug=False)
