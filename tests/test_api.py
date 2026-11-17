"""Contrato HTTP contra el modelo real incluido, sin reentrenar."""
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
from fastapi.testclient import TestClient
from api import app


class ContratoAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.opciones = cls.client.get('/v1/opciones').json()
        cls.entrada = cls.opciones['ejemplo']

    def test_salud(self):
        r = self.client.get('/v1/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['estado'], 'ok')

    def test_metadatos_coherentes_con_archivo(self):
        r = self.client.get('/v1/model-info')
        self.assertEqual(r.status_code, 200)
        esperado = json.loads((ROOT / 'api/metricas_judiciales.json').read_text())
        self.assertEqual(r.json()['metricas'], esperado)

    def test_prediccion_valida(self):
        r = self.client.post('/v1/predict', json=self.entrada)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(math.isfinite(d['duracion_estimada_dias']))
        self.assertGreaterEqual(d['duracion_estimada_dias'], 0)
        self.assertAlmostEqual(d['duracion_estimada_meses'], d['duracion_estimada_dias']/30.44, delta=0.06)
        self.assertGreater(d['antecedentes_combinacion'], 0)
        self.assertTrue(d['advertencias'])

    def test_informe_coincide_con_prediccion(self):
        r = self.client.post('/v1/informe', json=self.entrada)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['estimacion'], self.client.post('/v1/predict', json=self.entrada).json())
        self.assertIn('LIMITACIONES', r.json()['texto'])
        self.assertIn(self.entrada['localidad_nombre'], r.json()['texto'])

    def test_campo_vacio(self):
        self.assertEqual(self.client.post('/v1/predict', json={**self.entrada, 'localidad_nombre': '   '}).status_code, 422)

    def test_campo_faltante(self):
        entrada = dict(self.entrada)
        entrada.pop('juzgado_numero')
        self.assertEqual(self.client.post('/v1/predict', json=entrada).status_code, 422)

    def test_categoria_desconocida(self):
        r = self.client.post('/v1/predict', json={**self.entrada, 'localidad_nombre': 'LOCALIDAD_INEXISTENTE'})
        self.assertEqual(r.status_code, 422)
        self.assertIn('fuera del alcance', r.json()['detail'])

    def test_campo_extra_y_tipo_incorrecto(self):
        for entrada in ({**self.entrada, 'dato_extra': 1}, {**self.entrada, 'juzgado_numero': 123}):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.client.post('/v1/predict', json=entrada).status_code, 422)

    def test_combinacion_invalida(self):
        pares = {(c['localidad_nombre'], c['juzgado_numero']) for c in self.opciones['combinaciones']}
        for localidad in self.opciones['categorias']['localidad_nombre']:
            for juzgado in self.opciones['categorias']['juzgado_numero']:
                if (localidad, juzgado) not in pares:
                    entrada = {**self.entrada, 'localidad_nombre': localidad, 'juzgado_numero': juzgado}
                    r = self.client.post('/v1/predict', json=entrada)
                    self.assertEqual(r.status_code, 422)
                    self.assertIn('combinación', r.json()['detail'])
                    return
        self.skipTest('El modelo contiene todos los pares posibles')

    def test_ruta_anterior_compatible(self):
        self.assertEqual(self.client.post('/predecir', json=self.entrada).json(), self.client.post('/v1/predict', json=self.entrada).json())


if __name__ == '__main__':
    unittest.main()
