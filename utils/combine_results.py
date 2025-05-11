#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
from pathlib import Path
import os
import unicodedata
import re

class ResultsCombiner:

    def __init__(self):
        """Inicializa el combinador de resultados."""
        self.combined_results = {}
        self.stats = {
            "total_combined": 0,
            "conflicts": 0,
            "conflict_resolution": 0,
            "added_from_file1": 0,
            "added_from_file2": 0,
            "better_matches": 0
        }

    def normalize_title(self, title):
        """Normaliza un título para comparación."""
        if not title:
            return ""
        title = str(title).lower().strip()
        title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def load_json(self, file_path):
        """Carga un archivo JSON y devuelve su contenido."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Cargados {len(data)} registros de {file_path}")
            return data
        except Exception as e:
            print(f"Error al cargar {file_path}: {e}")
            return {}

    def is_better_match(self, entry1, entry2):
        """
        Determina cuál entrada es mejor basado en criterios como:
        - Si tiene ID y URL (prioridad alta)
        - Mayor similitud
        - Presencia de título vs None
        
        Returns:
            int: 1 si entry1 es mejor, 2 si entry2 es mejor, 0 si son iguales
        """
        # Si uno tiene ID y URL y el otro no
        if (entry1.get('id') and entry1.get('url')) and not (entry2.get('id') and entry2.get('url')):
            return 1
        if not (entry1.get('id') and entry1.get('url')) and (entry2.get('id') and entry2.get('url')):
            return 2
            
        # Si uno tiene título y el otro no
        if entry1.get('title') and not entry2.get('title'):
            return 1
        if not entry1.get('title') and entry2.get('title'):
            return 2
            
        # Comparar similitud si ambos tienen valor de similitud
        if entry1.get('similarity', 0) > entry2.get('similarity', 0) + 0.05:  # 5% mejor
            return 1
        if entry2.get('similarity', 0) > entry1.get('similarity', 0) + 0.05:  # 5% mejor
            return 2
            
        # Si llegamos aquí, consideramos que son similares en calidad
        return 0

    def merge_metadata(self, entry1, entry2):
        """
        Combina los metadatos (áreas y catálogos) de dos entradas.
        Mantiene los datos principales de la entrada mejor.
        """
        # Combinar áreas sin duplicados
        areas = list(set(entry1.get('areas', []) + entry2.get('areas', [])))
        
        # Combinar catálogos sin duplicados
        catalogos = list(set(entry1.get('catalogos', []) + entry2.get('catalogos', [])))
        
        # Determinar cuál entrada usar como base
        better_entry = entry1 if self.is_better_match(entry1, entry2) != 2 else entry2
        
        # Crear una nueva entrada combinada
        combined = dict(better_entry)
        combined['areas'] = areas
        combined['catalogos'] = catalogos
        
        return combined

    def combine_results(self, file1_path, file2_path, output_path):
        """
        Combina los resultados de dos archivos JSON en uno solo.
        
        Args:
            file1_path: Ruta al primer archivo JSON
            file2_path: Ruta al segundo archivo JSON
            output_path: Ruta donde guardar el archivo combinado
        """
        print(f"Combinando resultados de {file1_path} y {file2_path}...")
        
        # Cargar ambos archivos
        results1 = self.load_json(file1_path)
        results2 = self.load_json(file2_path)
        
        # Extraer IDs de las URLs para ambos conjuntos de resultados
        for results in [results1, results2]:
            for journal_name, entry in results.items():
                if entry.get('url'):
                    # Buscar el ID en la URL usando una expresión regular
                    url = entry['url']
                    id_match = re.search(r'[?&]q=(\d+)&', url)
                    if id_match:
                        entry['id'] = id_match.group(1)
        
        # Iniciar el proceso de combinación
        for journal_title, entry1 in results1.items():
            normalized_title = self.normalize_title(journal_title)
            
            # Si la revista no está en el segundo archivo, agregar directamente
            if journal_title not in results2:
                self.combined_results[journal_title] = entry1
                self.stats["added_from_file1"] += 1
                continue
                
            # Si la revista está en ambos archivos
            entry2 = results2[journal_title]
            
            # Verificar si hay conflicto (información diferente para la misma revista)
            if (entry1.get('id') != entry2.get('id') or 
                entry1.get('title') != entry2.get('title')):
                self.stats["conflicts"] += 1
                
                # Determinar cuál es mejor y combinar metadatos
                better_result = self.is_better_match(entry1, entry2)
                if better_result != 0:
                    self.stats["conflict_resolution"] += 1
                    self.stats["better_matches"] += 1
                    
                self.combined_results[journal_title] = self.merge_metadata(entry1, entry2)
            else:
                # No hay conflicto, solo combinar metadatos
                self.combined_results[journal_title] = self.merge_metadata(entry1, entry2)
        
        # Agregar revistas que solo están en el segundo archivo
        for journal_title, entry2 in results2.items():
            if journal_title not in self.combined_results:
                self.combined_results[journal_title] = entry2
                self.stats["added_from_file2"] += 1
        
        # Actualizar estadísticas
        self.stats["total_combined"] = len(self.combined_results)
        
        # Guardar el resultado combinado
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.combined_results, f, ensure_ascii=False, indent=2)
        
        print(f"Archivo combinado guardado en: {output_file}")
        self.print_stats()
    
    def print_stats(self):
        """Imprime estadísticas del proceso de combinación."""
        print("\n=== Estadísticas de combinación ===")
        print(f"Total de revistas en archivo combinado: {self.stats['total_combined']}")
        print(f"Revistas agregadas solo del archivo 1: {self.stats['added_from_file1']}")
        print(f"Revistas agregadas solo del archivo 2: {self.stats['added_from_file2']}")
        print(f"Conflictos encontrados: {self.stats['conflicts']}")
        print(f"Conflictos resueltos: {self.stats['conflict_resolution']}")
        print(f"Entradas con mejor coincidencia seleccionada: {self.stats['better_matches']}")
        print("==================================")

def analyze_json_content(file_path):
    """
    Analiza el contenido de un archivo JSON para mostrar estadísticas.
    
    Args:
        file_path: Ruta al archivo JSON a analizar
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        total_entries = len(data)
        
        # Extraer IDs de las URLs y agregar a las entradas
        for journal_name, entry in data.items():
            if entry.get('url'):
                # Buscar el ID en la URL usando una expresión regular
                url = entry['url']
                id_match = re.search(r'[?&]q=(\d+)&', url)
                if id_match:
                    entry['id'] = id_match.group(1)
        
        found_journals = sum(1 for entry in data.values() if entry.get('id'))
        missing_journals = total_entries - found_journals
        
        # Analizar duplicados potenciales
        titles = {}
        normalized_titles = {}
        
        for journal_name, entry in data.items():
            if entry.get('title'):
                title = entry['title']
                if title in titles:
                    titles[title] += 1
                else:
                    titles[title] = 1
                    
                # Normalizar y verificar duplicados normalizados
                normalized = unicodedata.normalize('NFKD', title.lower()).encode('ascii', 'ignore').decode('ascii')
                if normalized in normalized_titles:
                    normalized_titles[normalized].append(journal_name)
                else:
                    normalized_titles[normalized] = [journal_name]
        
        duplicated_titles = {t: c for t, c in titles.items() if c > 1}
        normalized_duplicates = {k: v for k, v in normalized_titles.items() if len(v) > 1}
        
        print(f"\n=== Análisis de {file_path} ===")
        print(f"Total de entradas: {total_entries}")
        print(f"Revistas encontradas (con ID): {found_journals} ({found_journals/total_entries*100:.1f}%)")
        print(f"Revistas no encontradas: {missing_journals} ({missing_journals/total_entries*100:.1f}%)")
        
        if duplicated_titles:
            print(f"Títulos duplicados: {len(duplicated_titles)}")
            for title, count in list(duplicated_titles.items())[:5]:  # Mostrar solo los primeros 5
                print(f" - '{title}': {count} veces")
            if len(duplicated_titles) > 5:
                print(f"   ... y {len(duplicated_titles) - 5} más")
        
        if normalized_duplicates:
            print(f"Títulos normalizados con duplicados: {len(normalized_duplicates)}")
            for norm_title, journals in list(normalized_duplicates.items())[:3]:  # Mostrar solo los primeros 3
                print(f" - '{norm_title}': {journals}")
            if len(normalized_duplicates) > 3:
                print(f"   ... y {len(normalized_duplicates) - 3} más")
        
        return {
            "total": total_entries,
            "found": found_journals,
            "missing": missing_journals,
            "duplicated_titles": len(duplicated_titles),
            "normalized_duplicates": len(normalized_duplicates)
        }
    except Exception as e:
        print(f"Error al analizar {file_path}: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Combina resultados de scraping de dos archivos JSON.')
    parser.add_argument('file1', help='Ruta al primer archivo JSON')
    parser.add_argument('file2', help='Ruta al segundo archivo JSON')
    parser.add_argument('--output', '-o', default='revistas_combined.json', help='Ruta para el archivo combinado')
    parser.add_argument('--analyze', '-a', action='store_true', help='Solo analizar contenido, sin combinar')
    
    args = parser.parse_args()
    
    # Asegurar rutas absolutas o relativas correctas
    file1_path = Path(args.file1)
    file2_path = Path(args.file2)
    output_path = Path(args.output)
    
    if not file1_path.exists():
        print(f"Error: No se encuentra el archivo {file1_path}")
        exit(1)
    
    if not file2_path.exists():
        print(f"Error: No se encuentra el archivo {file2_path}")
        exit(1)
    
    if args.analyze:
        print("Modo análisis: solo se mostrarán estadísticas sin combinar archivos")
        analyze_json_content(file1_path)
        analyze_json_content(file2_path)
    else:
        combiner = ResultsCombiner()
        combiner.combine_results(file1_path, file2_path, output_path)
