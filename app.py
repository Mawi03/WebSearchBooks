from flask import Flask, render_template, request, jsonify
import json
import os
from pathlib import Path

app = Flask(__name__)

# Cargar datos de revistas
BASE_DIR = Path(__file__).parent
REVISTAS_JSON = BASE_DIR / 'datos' / 'json' / 'revistas.json'
SCIMAGOJR_JSON = BASE_DIR / 'datos' / 'json' / 'revistas_scimagojr.json'

def cargar_datos():
    with open(REVISTAS_JSON, 'r', encoding='utf-8') as f:
        revistas = json.load(f)
    with open(SCIMAGOJR_JSON, 'r', encoding='utf-8') as f:
        scimagojr = json.load(f)
    return revistas, scimagojr

# Rutas principales
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/areas')
def areas():
    revistas, scimagojr = cargar_datos()
    # Obtener lista única de áreas
    areas = set()
    for revista in revistas.values():
        areas.update(revista['areas'])
    return render_template('areas.html', areas=sorted(areas))

@app.route('/area/<area>')
def area_detalle(area):
    revistas, scimagojr = cargar_datos()
    # Filtrar revistas por área
    revistas_area = {
        titulo: info for titulo, info in revistas.items()
        if area in info['areas']
    }
    return render_template('area_detalle.html', area=area, revistas=revistas_area, scimagojr=scimagojr)

@app.route('/catalogos')
def catalogos():
    revistas, _ = cargar_datos()
    # Obtener lista única de catálogos
    catalogos = set()
    for revista in revistas.values():
        catalogos.update(revista['catalogos'])
    return render_template('catalogos.html', catalogos=sorted(catalogos))

@app.route('/catalogo/<catalogo>')
def catalogo_detalle(catalogo):
    revistas, scimagojr = cargar_datos()
    # Filtrar revistas por catálogo
    revistas_catalogo = {
        titulo: info for titulo, info in revistas.items()
        if catalogo in info['catalogos']
    }
    return render_template('catalogo_detalle.html', catalogo=catalogo, revistas=revistas_catalogo, scimagojr=scimagojr)

@app.route('/explorar')
def explorar():
    return render_template('explorar.html')

@app.route('/explorar/<letra>')
def explorar_letra(letra):
    revistas, scimagojr = cargar_datos()
    # Filtrar revistas por letra inicial
    revistas_letra = {
        titulo: info for titulo, info in revistas.items()
        if titulo.lower().startswith(letra.lower())
    }
    return render_template('explorar_letra.html', letra=letra, revistas=revistas_letra, scimagojr=scimagojr)

@app.route('/buscar')
def buscar():
    query = request.args.get('q', '').lower()
    if not query:
        return render_template('buscar.html', revistas={})
    
    revistas, scimagojr = cargar_datos()
    # Buscar revistas que contengan la consulta
    resultados = {
        titulo: info for titulo, info in revistas.items()
        if query in titulo.lower()
    }
    return render_template('buscar.html', revistas=resultados, scimagojr=scimagojr, query=query)

@app.route('/revista/<titulo>')
def revista_detalle(titulo):
    revistas, scimagojr = cargar_datos()
    revista_info = revistas.get(titulo, {})
    scimagojr_info = scimagojr.get(titulo, {})
    return render_template('revista_detalle.html', 
                         titulo=titulo, 
                         revista=revista_info, 
                         scimagojr=scimagojr_info)

@app.route('/creditos')
def creditos():
    return render_template('creditos.html')

if __name__ == '__main__':
    app.run(debug=True)
