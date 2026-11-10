from config.database import redis_client
from datetime import datetime

def actualizar_ultima_posicion(id_sensor, id_contenedor, id_envio, lat, lon, hub_nombre, temp, humedad, bateria):
    """Cachea en Redis (Hash) la última posición GPS real y telemetría del sensor."""
    clave = f"sensor:gps:{id_sensor}"
    datos = {
        "id_sensor": str(id_sensor),
        "id_contenedor": str(id_contenedor),
        "id_envio": str(id_envio),
        "latitud": str(round(lat, 6)),
        "longitud": str(round(lon, 6)),
        "punto_logistico": hub_nombre,
        "temperatura_c": str(temp),
        "humedad_pct": str(humedad),
        "bateria_pct": str(bateria),
        "ultima_actualizacion": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    redis_client.hset(clave, mapping=datos)
    # También indexamos por envío para consulta rápida desde el panel de monitoreo
    redis_client.hset(f"envio:last_gps:{id_envio}", mapping=datos)

def obtener_ultima_posicion_sensor(id_sensor):
    return redis_client.hgetall(f"sensor:gps:{id_sensor}")

def obtener_ultima_posicion_envio(id_envio):
    return redis_client.hgetall(f"envio:last_gps:{id_envio}")