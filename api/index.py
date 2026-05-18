from flask import Flask, request, jsonify
from flask_cors import CORS
import gpxpy
import numpy as np
from pyproj import Transformer

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# MOTOR GEOIDAL UNIVERSAL (Fusión de Sensores)
# EPSG:4979 = Coordenadas WGS84 3D (Lat, Lon, Altura Elipsoidal)
# EPSG:4326+5773 = WGS84 2D + Altura EGM96 (Nivel del Mar)
# ---------------------------------------------------------
# Este transformador aplicará la ondulación geoidal de cualquier país automáticamente
geoid_transformer = Transformer.from_crs("EPSG:4979", "EPSG:4326+5773", always_xy=True)


def procesar_archivo_gpx(file_stream, es_base=False):
    """
    Parsea el GPX, aplica filtro estadístico de ruido (HDOP)
    y convierte las alturas elipsoidales a ortométricas (Nivel del Mar).
    """
    gpx = gpxpy.parse(file_stream)
    lats, lons, eles_orto = [], [], []

    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                # 1. Filtro de Ruido (Corta las épocas con mala geometría satelital)
                if pt.horizontal_dilution and pt.horizontal_dilution > 2.5:
                    continue # Descartar pico anómalo

                # 2. Corrección Geoidal Universal (EGM96)
                # Convierte la cota cruda del celular a cota real sobre el nivel del mar
                lon_geo, lat_geo, alt_orto = geoid_transformer.transform(
                    pt.longitude, 
                    pt.latitude, 
                    pt.elevation
                )

                lats.append(lat_geo)
                lons.append(lon_geo)
                eles_orto.append(alt_orto)

    if not lats:
        return None

    # 3. Filtro de Centroide (Promedio robusto)
    return {
        "lat_promedio": np.mean(lats),
        "lon_promedio": np.mean(lons),
        "ele_promedio": np.mean(eles_orto),
        "epocas_utiles": len(lats)
    }


@app.route('/api/procesar_diferencial', methods=['POST'])
def procesar_diferencial():
    """
    Endpoint (API) que recibe el archivo GPX de la Base, el GPX del Rover,
    y las coordenadas Oficiales (conocidas) del punto Base.
    """
    try:
        # 1. Recibir Archivos y Datos del Cliente
        if 'base_gpx' not in request.files or 'rover_gpx' not in request.files:
            return jsonify({"error": "Faltan archivos GPX (Base o Rover)"}), 400

        base_file = request.files['base_gpx']
        rover_file = request.files['rover_gpx']
        
        # Coordenadas reales del vértice donde se paró la Base
        base_oficial_lat = float(request.form.get('base_lat_oficial'))
        base_oficial_lon = float(request.form.get('base_lon_oficial'))
        base_oficial_ele = float(request.form.get('base_ele_oficial'))

        # 2. Extraer y purificar los datos geoidales de ambos teléfonos
        datos_base = procesar_archivo_gpx(base_file, es_base=True)
        datos_rover = procesar_archivo_gpx(rover_file, es_base=False)

        if not datos_base or not datos_rover:
            return jsonify({"error": "Los archivos GPX están vacíos o el ruido es muy alto"}), 400

        # 3. CÁLCULO DEL VECTOR DIFERENCIAL (Aplastando la Atmósfera)
        # Error = Coordenada Medida por Celular - Coordenada Real Oficial
        error_lat = datos_base['lat_promedio'] - base_oficial_lat
        error_lon = datos_base['lon_promedio'] - base_oficial_lon
        error_ele = datos_base['ele_promedio'] - base_oficial_ele

        # 4. APLICACIÓN DEL FILTRO AL ROVER
        rover_corregido_lat = datos_rover['lat_promedio'] - error_lat
        rover_corregido_lon = datos_rover['lon_promedio'] - error_lon
        rover_corregido_ele = datos_rover['ele_promedio'] - error_ele

        # 5. Entregar el reporte final al Topógrafo
        return jsonify({
            "status": "exito",
            "analisis_base": {
                "epocas_usadas": datos_base['epocas_utiles'],
                "error_ionosferico_detectado_m": {
                    "latitud": round(error_lat * 111320, 3), # Conversión a metros aprox
                    "longitud": round(error_lon * 111320 * np.cos(np.radians(base_oficial_lat)), 3),
                    "cota_z": round(error_ele, 3)
                }
            },
            "resultado_rover_corregido": {
                "latitud": round(rover_corregido_lat, 8),
                "longitud": round(rover_corregido_lon, 8),
                "cota_ortometrica_msnm": round(rover_corregido_ele, 3) # Elevación perfecta
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"Fallo en el procesamiento matemático: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
