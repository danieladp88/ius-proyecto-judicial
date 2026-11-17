"""Integración Flask -> FastAPI -> modelo real, con transporte de prueba en memoria.
Ejecutar desde la raíz: python tests/probar_interfaz.py
No sustituye la comprobación visual del navegador ni Docker.
"""
from pathlib import Path
import sys
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'api'))
from fastapi.testclient import TestClient
from api import app as api_app
sys.path.insert(0,str(root/'interfaz'))
from app import app as front_app
api=TestClient(api_app)
front=front_app.test_client()
def transportar(metodo,url,json=None,timeout=None):
    r=api.request(metodo,'/'+url.split('/',3)[3],json=json)
    # Adaptador: HTTPX no expone .ok, que sí ofrece requests
    r.ok=r.is_success
    return r
with patch('app.requests.request',side_effect=transportar):
    inicio=front.get('/api/inicio');assert inicio.status_code==200
    entrada={'localidad_nombre':'MORON','juzgado_numero':'7','causa_objeto_litigio_descripcion':'DAÑOS Y PERJ.AUTOM. C/LES. O MUERTE (EXC.ESTADO)'}
    informe=front.post('/api/informe',json=entrada);assert informe.status_code==200
    assert informe.json['estimacion']['duracion_estimada_dias']==758.4
    ctx={}
    for msg in ['Quiero consultar en Morón, juzgado 7',entrada['causa_objeto_litigio_descripcion'],'Confirmar estimación']:
        r=front.post('/api/chat',json={'mensaje':msg,'contexto':ctx});assert r.status_code==200;ctx=r.json['contexto']
    assert r.json['informe']==informe.json
    assert front.post('/api/informe',json={**entrada,'localidad_nombre':'INEXISTENTE'}).status_code==422
    assert front.get('/').status_code==200
    print('OK: formulario y chat consultan el modelo real, coinciden en el informe y rechazan categorías inválidas.')
