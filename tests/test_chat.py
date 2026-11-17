import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'interfaz'))
from conversacion import conversar

class ChatGuiado(unittest.TestCase):
    def setUp(self):
        self.o={'categorias':{'localidad_nombre':['MORON','TANDIL'],'juzgado_numero':['7','2'],'causa_objeto_litigio_descripcion':['DAÑOS AUTOMOTOR','AMPARO']},'combinaciones':[{'localidad_nombre':'MORON','juzgado_numero':'7','causa_objeto_litigio_descripcion':'DAÑOS AUTOMOTOR'},{'localidad_nombre':'TANDIL','juzgado_numero':'2','causa_objeto_litigio_descripcion':'AMPARO'}]}
        self.info={'metricas':{'mae_modelo_prueba_dias':395.95,'mejora_mae_porcentaje':10.57,'causas_totales':8752}}
        self.call=Mock(return_value={'texto':'informe','estimacion':{'duracion_estimada_dias':758.4,'duracion_estimada_meses':24.9,'antecedentes_combinacion':126}})
    def talk(self,msg,ctx=None):return conversar(msg,ctx or {},self.o,self.info,self.call)
    def test_guia_y_confirmacion(self):
        a=self.talk('Una causa en Morón, juzgado 7');self.assertEqual(a['sugerencias'],['DAÑOS AUTOMOTOR'])
        b=self.talk('DAÑOS AUTOMOTOR',a['contexto']);self.assertIn('Confirmar estimación',b['sugerencias']);self.call.assert_not_called()
        c=self.talk('Confirmar estimación',b['contexto']);self.assertIn('informe',c);self.call.assert_called_once()
    def test_cambia_localidad_limpia_dependencias(self):
        a=self.talk('Tandil',{'localidad_nombre':'MORON','juzgado_numero':'7','causa_objeto_litigio_descripcion':'DAÑOS AUTOMOTOR'})
        self.assertEqual(a['contexto'],{'localidad_nombre':'TANDIL'});self.call.assert_not_called()
    def test_juzgado_invalido(self):
        a=self.talk('Morón juzgado 99');self.assertIn('No tengo ese juzgado',a['texto']);self.call.assert_not_called()
    def test_contexto_fabricado_no_predice(self):
        a=self.talk('Confirmar estimación',{'localidad_nombre':'MORON','juzgado_numero':'2','causa_objeto_litigio_descripcion':'AMPARO','admin':True})
        self.assertNotIn('informe',a);self.call.assert_not_called()
    def test_no_inventa_para_desconocidos(self):
        a=self.talk('Quiero consultar en Rosario');self.assertNotIn('informe',a);self.assertEqual(a['contexto'],{})
    def test_explicacion_mae(self):
        a=self.talk('¿Qué es el MAE?');self.assertIn('395.95',a['texto']);self.call.assert_not_called()
    def test_fuera_de_alcance(self):
        a=self.talk('Redacta una demanda');self.assertIn('No redacto',a['texto']);self.call.assert_not_called()
    def test_ambiguedad_localidad(self):
        a=self.talk('Morón o Tandil');self.assertEqual(a['sugerencias'],['MORON','TANDIL']);self.call.assert_not_called()

class ContratoFront(unittest.TestCase):
    def setUp(self):
        from app import app
        self.c=app.test_client()
    def test_pagina_y_assets(self):
        self.assertEqual(self.c.get('/').status_code,200)
        with self.c.get('/static/app.js') as r:
            self.assertEqual(r.status_code,200)
    def test_chat_valida_json(self):
        for body in [None,{}, {'mensaje':''}, {'mensaje':2},{'mensaje':'hola','contexto':[]},{'mensaje':'x'*1501}]:
            with self.subTest(body=body):self.assertEqual(self.c.post('/api/chat',json=body).status_code,400)
    def test_payload_grande(self):
        self.assertEqual(self.c.post('/api/chat',json={'mensaje':'x'*20000}).status_code,413)
    def test_falla_api(self):
        from unittest.mock import patch
        import requests
        with patch('app.requests.request',side_effect=requests.ConnectionError):
            r=self.c.get('/api/inicio');self.assertEqual(r.status_code,503);self.assertIn('conectar',r.json['error'])

if __name__=='__main__':unittest.main()
