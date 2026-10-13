from config.database import mongo_db
from datetime import datetime

def guardar_lectura_iot(contenedor_id, envio_id, sensor_mac, lat, lon, metricas):
    """Inserta un documento de telemetría IoT en MongoDB con soporte geoespacial."""
    coleccion = mongo_db["lecturas_sensores"]
    documento = {
        "contenedor_id": contenedor_id,
        "envio_id": envio_id,
        "sensor_mac": sensor_mac,
        "timestamp": datetime.utcnow(),
        "ubicacion": {
            "type": "Point",
            "coordinates": [lon, lat]  # MongoDB usa formato [Longitud, Latitud]
        },
        "metricas": metricas  # Ejemplo: {"temperatura_c": -18.2, "humedad_pct": 65.0}
    }
    coleccion.insert_one(documento)