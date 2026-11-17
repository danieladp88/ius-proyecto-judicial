"""Asistente guiado determinista. No utiliza un LLM ni genera asesoramiento legal."""
import re
import unicodedata

CAMPOS = ['localidad_nombre','juzgado_numero','causa_objeto_litigio_descripcion']

def normalizar(texto):
    return re.sub(r'\s+', ' ', ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')).strip()

def menciona(texto, valor):
    return re.search(r'(?<!\w)' + re.escape(normalizar(valor)) + r'(?!\w)', texto) is not None

def conversar(mensaje, contexto, opciones, info, consultar):
    cats = opciones['categorias']
    ctx = {k:v for k,v in contexto.items() if k in CAMPOS and isinstance(v,str) and v in cats[k]}
    t = normalizar(mensaje)
    def respuesta(texto, sugerencias=None, informe=None):
        d = {'texto':texto,'contexto':ctx,'sugerencias':sugerencias or [],'modo':'guiado'}
        if informe is not None: d['informe'] = informe
        return d
    if t in ['reiniciar','nueva consulta','empezar de nuevo']:
        ctx.clear()
        return respuesta('Empecemos de nuevo. ¿En qué localidad de Buenos Aires querés consultar?', cats['localidad_nombre'])
    objeto_exacto = any(t == normalizar(x) for x in cats['causa_objeto_litigio_descripcion'])
    if not objeto_exacto and any(x in t for x in ['abogado','redacta','demanda','articulo','ley ','que debo hacer','escrito judicial','ganar el juicio']):
        return respuesta('Puedo ayudarte a consultar duración histórica y entender el modelo. No redacto escritos ni doy asesoramiento jurídico. Podemos comenzar por la localidad', ['Nueva consulta','¿Qué datos necesitás?'])
    m = info['metricas']
    if any(x in t for x in ['mae','error','precision','acierta','confiable']):
        return respuesta(f"El error absoluto medio (MAE) en prueba es {m['mae_modelo_prueba_dias']:.2f} días. Es el promedio de la distancia entre estimaciones y duraciones reales. No es un margen garantizado para tu caso ni un porcentaje de acierto. La mejora frente a la mediana es {m['mejora_mae_porcentaje']:.2f} %.", ['Continuar consulta','¿Qué limitaciones tiene?'])
    if any(x in t for x in ['limitacion','tiempo restante','actual','fecha exacta','cuando termina']):
        return respuesta('El modelo estima duración total histórica de causas finalizadas de Buenos Aires entre 2016 y 2019. No calcula tiempo restante ni una fecha asegurada de resolución. Excluir causas sin cierre puede sesgar los resultados.', ['Continuar consulta','¿Qué es el MAE?'])
    if any(x in t for x in ['datos necesitas','datos necesito','como funciona','que podes','ayuda']):
        return respuesta('Necesito localidad, juzgado y objeto del litigio. Podés escribirlos o elegir las opciones que te voy mostrando. Por ejemplo: «Quiero consultar una causa en Morón, juzgado 7». No ingreses nombres, DNI ni números de expediente.', ['Quiero consultar en Morón, juzgado 7','Nueva consulta'])
    if any(x in t for x in ['fuente','de donde','cuantos datos']):
        return respuesta(f"El modelo usa {m['causas_totales']} causas limpias del conjunto Oralidad en los procesos civiles del Ministerio de Justicia. El alcance es Buenos Aires, con finalizaciones entre 2016 y 2019. La ficha «El modelo» muestra las métricas y la fuente.", ['Continuar consulta'])
    ciudades = [v for v in cats['localidad_nombre'] if menciona(t,v)]
    if len(ciudades)>1:
        return respuesta('Mencionaste más de una localidad. Elegí una para esta consulta.',ciudades)
    nueva_ciudad = ciudades[0] if ciudades else None
    # Cuando cambia la localidad, descartar sus selecciones dependientes.
    if nueva_ciudad and nueva_ciudad != ctx.get('localidad_nombre'):
        ctx.clear(); ctx['localidad_nombre']=nueva_ciudad
    if 'localidad_nombre' not in ctx:
        return respuesta('Para empezar, elegí una localidad disponible de Buenos Aires. También podés escribir su nombre.',cats['localidad_nombre'])
    combos = [x for x in opciones['combinaciones'] if x['localidad_nombre']==ctx['localidad_nombre']]
    juzgados = sorted({x['juzgado_numero'] for x in combos}, key=lambda x:(len(x),x))
    found = re.search(r'juzgado\s*(?:numero|nro\.?|n[°º.]|n)?\s*(\d+)',t)
    numero = found.group(1) if found else (t if t.isdigit() else None)
    if numero is not None:
        if numero not in juzgados:
            ctx.pop('juzgado_numero',None);ctx.pop('causa_objeto_litigio_descripcion',None)
            return respuesta(f"No tengo ese juzgado para {ctx['localidad_nombre']}. Elegí uno de los disponibles.",[f'Juzgado {x}' for x in juzgados])
        if numero != ctx.get('juzgado_numero'):
            ctx.pop('causa_objeto_litigio_descripcion',None)
        ctx['juzgado_numero']=numero
    if ctx.get('juzgado_numero') not in juzgados:
        ctx.pop('juzgado_numero',None);ctx.pop('causa_objeto_litigio_descripcion',None)
        return respuesta(f"Localidad: {ctx['localidad_nombre']}. ¿Qué juzgado querés consultar?",[f'Juzgado {x}' for x in juzgados])
    objetos = sorted({x['causa_objeto_litigio_descripcion'] for x in combos if x['juzgado_numero']==ctx['juzgado_numero']})
    exactos = [x for x in objetos if menciona(t,x)]
    if len(exactos)==1:
        ctx['causa_objeto_litigio_descripcion']=exactos[0]
    elif t not in ['confirmar estimacion','continuar consulta'] or ctx.get('causa_objeto_litigio_descripcion') not in objetos:
        ctx.pop('causa_objeto_litigio_descripcion',None)
        terminos=[x for x in re.findall(r'[a-z]+',t) if len(x)>3 and x not in ['quiero','consultar','causa','juzgado','duracion','cuanto','tarda','para','litigio','tiene','dura','continuar','consulta','moron']]
        coincidencias=[o for o in objetos if terminos and any(x in normalizar(o) for x in terminos)]
        candidatos=coincidencias or objetos
        return respuesta('Elegí el objeto exacto del litigio. Voy a usar esa categoría para consultar el modelo.',candidatos)
    if t != 'confirmar estimacion':
        return respuesta(f"Voy a consultar: {ctx['localidad_nombre']}, juzgado {ctx['juzgado_numero']}, {ctx['causa_objeto_litigio_descripcion']}. ¿Confirmás estos datos?",['Confirmar estimación','Nueva consulta'])
    informe=consultar('POST','/v1/informe',{k:ctx[k] for k in CAMPOS})
    r=informe['estimacion']
    return respuesta(f"La duración histórica estimada es {r['duracion_estimada_dias']:.1f} días (aproximadamente {r['duracion_estimada_meses']:.1f} meses). La combinación tiene {r['antecedentes_combinacion']} antecedentes. Es duración total histórica, no tiempo restante ni una fecha garantizada.",['¿Qué es el MAE?','¿Qué limitaciones tiene?','Nueva consulta'],informe)
