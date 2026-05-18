from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np

app = Flask(__name__)
CORS(app)

def procesar_archivo_gpx(file_stream):
    """Parsea el GPX y calcula el promedio geométrico puro filtrando el ruido."""
    try:
        gpx = gpxpy.parse(file_stream)
        lats, lons, eles = [], [], []

        for track in gpx.tracks:
            for segment in track.segments:
                for pt in segment.points:
                    # Filtro de Ruido (Corta las épocas con mala geometría)
                    if pt.horizontal_dilution and pt.horizontal_dilution > 3.0:
                        continue 
                    lats.append(pt.latitude)
                    lons.append(pt.longitude)
                    eles.append(pt.elevation)

        if not lats:
            return None

        return {
            "lat_promedio": np.mean(lats),
            "lon_promedio": np.mean(lons),
            "ele_promedio": np.mean(eles),
            "epocas_utiles": len(lats)
        }
    except Exception as e:
        return None

# Usamos un catch-all para asegurar que cualquier ruta de tu frontend funcione
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def procesar(path):
    # Respuesta a las verificaciones de seguridad de Chrome
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        # Detectar qué archivos envió el frontend
        has_base = 'base_gpx' in request.files
        has_rover = 'rover_gpx' in request.files

        # ESCENARIO 0: No envió nada
        if not has_base and not has_rover:
            # Devolvemos 200 para que tu frontend no diga "Servidor no responde"
            return jsonify({"error": "No se recibió ningún archivo GPX"}), 200

        # ESCENARIO 1: Modo "Un Solo Teléfono" (El que estás probando ahora)
        if has_base and not has_rover:
            base_file = request.files['base_gpx']
            datos_base = procesar_archivo_gpx(base_file)
            
            if not datos_base:
                return jsonify({"error": "El archivo GPX está vacío o tiene demasiado ruido."}), 200
            
            return jsonify({
                "status": "exito",
                "modo": "posicionamiento_absoluto",
                "resultado": {
                    "latitud": round(datos_base['lat_promedio'], 8),
                    "longitud": round(datos_base['lon_promedio'], 8),
                    "cota_z": round(datos_base['ele_promedio'], 3),
                    "epocas_usadas": datos_base['epocas_utiles']
                }
            }), 200

        # ESCENARIO 2: Modo Diferencial (Cuando tengas los 2 teléfonos)
        if has_base and has_rover:
            base_file = request.files['base_gpx']
            rover_file = request.files['rover_gpx']
            
            def parse_float_seguro(val):
                try: return float(val) if val else 0.0
                except: return 0.0

            base_oficial_lat = parse_float_seguro(request.form.get('base_lat_oficial'))
            base_oficial_lon = parse_float_seguro(request.form.get('base_lon_oficial'))
            base_oficial_ele = parse_float_seguro(request.form.get('base_ele_oficial'))

            datos_base = procesar_archivo_gpx(base_file)
            datos_rover = procesar_archivo_gpx(rover_file)

            if not datos_base or not datos_rover:
                return jsonify({"error": "Uno de los archivos GPX tiene errores o mucho ruido."}), 200

            # Vector de error
            error_lat = datos_base['lat_promedio'] - base_oficial_lat
            error_lon = datos_base['lon_promedio'] - base_oficial_lon
            error_ele = datos_base['ele_promedio'] - base_oficial_ele

            # Aplicar corrección
            rover_corregido_lat = datos_rover['lat_promedio'] - error_lat
            rover_corregido_lon = datos_rover['lon_promedio'] - error_lon
            rover_corregido_ele = datos_rover['ele_promedio'] - error_ele

            return jsonify({
                "status": "exito",
                "modo": "diferencial_dos_telefonos",
                "analisis_base": {
                    "epocas_usadas": datos_base['epocas_utiles'],
                    "error_detectado_m": {
                        "latitud_y": round(error_lat * 111320, 3), 
                        "longitud_x": round(error_lon * 111320 * np.cos(np.radians(base_oficial_lat)), 3),
                        "cota_z": round(error_ele, 3)
                    }
                },
                "resultado_rover_corregido": {
                    "latitud": round(rover_corregido_lat, 8),
                    "longitud": round(rover_corregido_lon, 8),
                    "cota_z": round(rover_corregido_ele, 3) 
                }
            }), 200

    except Exception as e:
        return jsonify({
            "error": "Error de procesamiento en Python",
            "detalle": str(e)
        }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
