from config.database import mongo_db

def inicializar_colecciones_mongo():
    print("Inicializando colecciones en MongoDB...")

    # 1. Eventos Logísticos
    coleccion_eventos = mongo_db["eventos_logisticos"]
    # Crear índice por id_envio y fecha para búsquedas rápidas del historial de un envío
    coleccion_eventos.create_index([("id_envio", 1), ("fecha_y_hora", -1)])
    print("✅ Colección 'eventos_logisticos' inicializada con índices.")

    # 2. Incidentes
    coleccion_incidentes = mongo_db["incidentes"]
    # Índice para buscar rápidamente incidentes por envío o por estado (ej. buscar incidentes 'ABIERTO')
    coleccion_incidentes.create_index([("id_envio", 1)])
    coleccion_incidentes.create_index([("estado", 1)]) 
    print("✅ Colección 'incidentes' inicializada con índices.")

    # 3. Alertas
    coleccion_alertas = mongo_db["alertas"]
    # Índice por sensor y fecha
    coleccion_alertas.create_index([("id_sensor", 1), ("fecha", -1)])
    print("✅ Colección 'alertas' inicializada con índices.")

    # 4. Predicción de Riesgos
    coleccion_predicciones = mongo_db["predicciones_riesgos"]
    # Índice por envío para consultar rápidamente los riesgos asociados a un viaje
    coleccion_predicciones.create_index([("id_envio", 1)])
    print("✅ Colección 'predicciones_riesgos' inicializada con índices.")

    print("\n🚀 ¡Todas las colecciones documentales creadas exitosamente!")

if __name__ == "__main__":
    inicializar_colecciones_mongo()