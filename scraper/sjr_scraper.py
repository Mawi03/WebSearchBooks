import os
import json
import time
import requests
import argparse
import threading
from bs4 import BeautifulSoup

# Obtener la ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configurar rutas absolutas
INPUT_JSON = os.path.join(BASE_DIR, 'datos', 'json', 'revistas.json')
OUTPUT_JSON = os.path.join(BASE_DIR, 'datos', 'json', 'revistas_scimagojr.json')
BACKUP_JSON = os.path.join(BASE_DIR, 'datos', 'json', 'revistas_scimagojr_backup.json')

# Configurar argumentos de línea de comandos
parser = argparse.ArgumentParser(description='Scraper de ScimagoJR con punto de inicio configurable')
parser.add_argument('--inicio', type=int, default=0, help='Índice desde donde empezar a procesar (default: 0)')
parser.add_argument('--fin', type=int, help='Índice donde terminar de procesar (opcional)')
parser.add_argument('--reverso', action='store_true', help='Procesar las revistas en orden inverso')
args = parser.parse_args()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/123.0.0.0 Safari/537.36'
}

SCIMAGO_BASE_URL = 'https://www.scimagojr.com'
SEARCH_URL = SCIMAGO_BASE_URL + '/journalsearch.php?q='

# Constantes para símbolos de log
LOG_SUCCESS = "✅"
LOG_ERROR = "❌"
LOG_INFO = "ℹ️"
LOG_WARNING = "⚠️"
LOG_PROCESSING = "🔄"

def save_data_safely(data, titulo=""):
    """Guarda los datos en el archivo principal y en el backup de forma segura"""
    try:
        # Primero intentamos guardar en el backup
        with open(BACKUP_JSON, 'w', encoding='utf-8') as archivo_backup:
            json.dump(data, archivo_backup, indent=4, ensure_ascii=False)
        
        # Si el backup fue exitoso, guardamos en el archivo principal
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as archivo_salida:
            json.dump(data, archivo_salida, indent=4, ensure_ascii=False)
        
        if titulo:
            print(f"{LOG_SUCCESS} Información guardada exitosamente: {titulo}")
        return True
    except Exception as save_error:
        print(f"{LOG_ERROR} Error al guardar los datos: {str(save_error)}")
        return False

# Cargar revistas ya obtenidas
if os.path.exists(OUTPUT_JSON):
    with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
        revistas_data = json.load(f)
elif os.path.exists(BACKUP_JSON):
    print(f"{LOG_INFO} Recuperando datos del archivo de respaldo...")
    with open(BACKUP_JSON, 'r', encoding='utf-8') as f:
        revistas_data = json.load(f)
else:
    revistas_data = {}

def scrap(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} en {url}")
    return response

def find_journal_url(journal_title):
    search = SEARCH_URL + journal_title.replace(" ", "+")
    soup = BeautifulSoup(scrap(search).text, 'html.parser')
    result = soup.select_one('span.jrnlname')
    if result:
        return SCIMAGO_BASE_URL + '/' + result.find_parent('a')['href']
    return None

def obtenerimagen(soup):
    try:
        img = soup.find('img', class_='imgwidget')
        if img and 'src' in img.attrs:
            return 'https://www.scimagojr.com/' + img['src']
    except Exception as e:
        print(f"Error al extraer imagen: {e}")
    return None

def extract_subject_area(soup):
    section = soup.find("h2", string="Subject Area and Category")
    if not section:
        return None
    table = section.find_next("table")
    if not table:
        return None
    items = table.find_all("td")
    categories = [td.get_text(strip=True) for td in items if td]
    return ', '.join(categories)

def scrape_journal_data(url):
    soup = BeautifulSoup(scrap(url).text, 'html.parser')

    # Obtener H-Index
    try:
        h_index_section = soup.find('h2', string=lambda s: s and 'H-Index' in s)
        h_index = h_index_section.find_next_sibling('p').text.strip() if h_index_section else None
    except Exception as e:
        print(f"Error al extraer H-Index: {e}")
        h_index = None

    # Obtener Homepage
    try:
        homepage_section = soup.find('a', string='Homepage')
        homepage_link = homepage_section['href'] if homepage_section else None
    except Exception as e:
        print(f"Error al extraer Homepage: {e}")
        homepage_link = None

    # Obtener Publisher
    try:
        publisher_section = soup.find('h2', string=lambda s: s and 'Publisher' in s)
        publisher = publisher_section.find_next_sibling('p').text.strip() if publisher_section else None
    except Exception as e:
        print(f"Error al extraer Publisher: {e}")
        publisher = None

    # Obtener ISSN
    try:
        issn_section = soup.find('h2', string=lambda s: s and 'ISSN' in s)
        issn = issn_section.find_next_sibling('p').text.strip() if issn_section else None
    except Exception as e:
        print(f"Error al extraer ISSN: {e}")
        issn = None

    # Obtener imagen del widget
    widget_url = obtenerimagen(soup)

    # Obtener Publication Type
    try:
        publication_type_section = soup.find('h2', string=lambda s: s and 'Publication type' in s)
        publication_type = publication_type_section.find_next_sibling('p').text.strip() if publication_type_section else None
    except Exception as e:
        print(f"Error al extraer Publication type: {e}")
        publication_type = None

    return {
        "site": homepage_link,
        "h_index": h_index,
        "subject_area_category": extract_subject_area(soup),
        "publisher": publisher,
        "issn": issn,
        "widget": widget_url,
        "publication_type": publication_type,
        "url": url
    }

# Cargar títulos a procesar
with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    revistas_input = json.load(f)

# Calcular el rango de revistas a procesar
inicio = args.inicio
fin = args.fin if args.fin is not None else len(revistas_input)
revistas_items = list(revistas_input.items())

# Si es en reverso, invertimos el orden
if args.reverso:
    revistas_items = revistas_items[::-1]
    # Ajustamos inicio y fin para mantener la lógica con el orden invertido
    if args.fin is not None:
        temp_inicio = len(revistas_items) - fin
        temp_fin = len(revistas_items) - inicio
        inicio = temp_inicio
        fin = temp_fin

revistas_a_procesar = revistas_items[inicio:fin]

print(f"{LOG_INFO} Procesando {'en reverso ' if args.reverso else ''}desde el índice {inicio} hasta {fin}")
print(f"{LOG_INFO} Total de revistas a procesar: {len(revistas_a_procesar)}")

# Variable global para pausar el proceso
is_paused = False

def toggle_pause():
    """Alterna el estado de pausa."""
    global is_paused
    is_paused = not is_paused
    estado = "pausado" if is_paused else "reanudado"
    print(f"{LOG_INFO} Proceso {estado}.")

def contar_archivos_json():
    """Cuenta los elementos JSON en el archivo revistas_scimagojr.json."""
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return len(data)
    return 0

# Hilo para escuchar comandos de pausa
def escuchar_comandos():
    while True:
        comando = input("Escribe 'pausar' para pausar/reanudar el proceso: ").strip().lower()
        if comando == 'pausar':
            toggle_pause()

# Iniciar el hilo de comandos
threading.Thread(target=escuchar_comandos, daemon=True).start()

procesados_count = 0
for titulo_revista, _ in revistas_a_procesar:
    while is_paused:
        print(f"{LOG_INFO} Proceso en pausa. Archivos JSON generados: {contar_archivos_json()}")
        time.sleep(5)  # Esperar mientras está pausado

    if titulo_revista in revistas_data:
        print(f"{LOG_INFO} Revista ya procesada anteriormente: {titulo_revista}")
        continue

    print(f"{LOG_PROCESSING} Buscando información de la revista: {titulo_revista} (índice: {inicio + procesados_count})")
    try:
        url_revista = find_journal_url(titulo_revista)
        if not url_revista:
            print(f"{LOG_ERROR} No se encontró la revista en Scimago: {titulo_revista}")
            continue

        datos_revista = scrape_journal_data(url_revista)
        revistas_data[titulo_revista] = datos_revista
        
        # Guardar progreso después de cada revista procesada exitosamente
        save_data_safely(revistas_data, titulo_revista)
        
        procesados_count += 1
        time.sleep(2)
    except Exception as error:
        print(f"{LOG_ERROR} Error al procesar la revista {titulo_revista}: {str(error)}")

# Asegurar que los datos finales estén guardados
save_data_safely(revistas_data)
print(f"{LOG_SUCCESS} Proceso finalizado. Nuevas revistas procesadas: {procesados_count}")
print(f"{LOG_INFO} Rango procesado: {inicio} - {fin}")