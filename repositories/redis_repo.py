from config.database import redis_client

def actualizar_ultima_posicion(sensor_mac, lat, lon, temp, bateria):
    """Guarda o actualiza la última telemetría de un sensor en una estructura Hash de Redis."""
    clave = f"sensor:last_telemetry:{sensor_mac}"
    redis_client.hset(clave, mapping={
        "lat": lat,
        "lon": lon,
        "temperatura": temp,
        "bateria": bateria
    })

def obtener_ultima_posicion(sensor_mac):
    """Obtiene la última posición y métricas cacheadas de un sensor."""
    clave = f"sensor:last_telemetry:{sensor_mac}"
    return redis_client.hgetall(clave)