from repositories.redis_repo import actualizar_ultima_posicion, obtener_ultima_posicion
from repositories.mongo_repo import guardar_lectura_iot
from repositories.neo4j_repo import buscar_camino_optimo
from repositories.pg_repo import crear_factura_y_actualizar_saldo

def menu():
    while True:
        print("\n==============================================")
        print("  SISTEMA DE LOGÍSTICA POLÍGLOTA - TP BD2")
        print("==============================================")
        print("1. Registrar Telemetría IoT (Redis + MongoDB)")
        print("2. Consultar Última Posición (Redis)")
        print("3. Calcular Ruta Óptima / Grafo (Neo4j)")
        print("4. Generar Factura y Cuenta Corriente (PostgreSQL - ACID)")
        print("5. Salir")
        
        opcion = input("\nSeleccioná una opción (1-5): ")
        
        if opcion == "1":
            print("\n--- [IoT] Registrando telemetría ---")
            mac = input("Ingresá la MAC del sensor [Ej: AA:BB:CC:11:22:33]: ") or "AA:BB:CC:11:22:33"
            try:
                lat = float(input("Latitud [Ej: -34.6037]: ") or -34.6037)
                lon = float(input("Longitud [Ej: -58.3683]: ") or -58.3683)
                temp = float(input("Temperatura °C [Ej: -18.2]: ") or -18.2)
                bateria = int(input("Batería % [Ej: 92]: ") or 92)
            except ValueError:
                print("⚠️ Error: Ingresá valores numéricos válidos.")
                continue
            
            # 1. Actualizar caché rápida en tiempo real (Redis)
            actualizar_ultima_posicion(mac, lat, lon, temp, bateria)
            
            # 2. Guardar registro histórico inmutable con soporte geoespacial (MongoDB)
            guardar_lectura_iot(
                contenedor_id=1, 
                envio_id=1, 
                sensor_mac=mac, 
                lat=lat, 
                lon=lon, 
                metricas={"temperatura_c": temp, "bateria_pct": bateria}
            )
            print("✅ ¡Telemetría guardada exitosamente en Redis (Caché) y MongoDB (Histórico)!")
            
        elif opcion == "2":
            print("\n--- [Redis] Consultar Última Posición ---")
            mac = input("Ingresá la MAC del sensor a consultar [Ej: AA:BB:CC:11:22:33]: ") or "AA:BB:CC:11:22:33"
            posicion = obtener_ultima_posicion(mac)
            if posicion:
                print("📍 Última posición encontrada en Caché:")
                for k, v in posicion.items():
                    print(f"   - {k}: {v}")
            else:
                print("⚠️ No se encontró telemetría reciente para esa MAC.")
                
        elif opcion == "3":
            print("\n--- [Neo4j] Calcular Ruta Óptima ---")
            origen = input("Código de Ubicación de Origen [Ej: BUE]: ").upper() or "BUE"
            destino = input("Código de Ubicación de Destino [Ej: MAD]: ").upper() or "MAD"
            
            try:
                resultados = buscar_camino_optimo(origen, destino)
                if resultados:
                    print("🚀 Ruta óptima encontrada:")
                    for res in resultados:
                        print(f"   - Secuencia de Nodos (Ruta): {res['ruta']}")
                        print(f"   - Distancia Total: {res['distancia_total']} km")
                        print(f"   - Tiempo Estimado: {res['tiempo_total']} hs")
                else:
                    print("⚠️ No se encontró un camino directo o las ubicaciones no existen en el grafo.")
            except Exception as e:
                print(f"❌ Error al consultar Neo4j: {e}")
                
        elif opcion == "4":
            print("\n--- [PostgreSQL] Facturación y Cuenta Corriente (ACID) ---")
            try:
                cliente_id = int(input("ID del Cliente [Ej: 1]: ") or 1)
                envio_id = int(input("ID del Envio [Ej: 1]: ") or 1)
                nro_factura = input("Número de Factura [Ej: FAC-2026-001]: ") or "FAC-2026-001"
                monto = float(input("Monto total [Ej: 15000.50]: ") or 15000.50)
                
                fact_id = crear_factura_y_actualizar_saldo(cliente_id, envio_id, nro_factura, monto)
                print(f"✅ ¡Transacción exitosa! Factura creada con ID interno: {fact_id} y cuenta corriente actualizada.")
            except Exception as e:
                print(f"❌ Error en la transacción ACID (Rollback ejecutado): {e}")
                
        elif opcion == "5":
            print("\n👋 ¡Saliendo del sistema de logística políglota. Suerte con el TP!")
            break
        else:
            print("⚠️ Opción inválida. Por favor, elegí un número entre 1 y 5.")

if __name__ == "__main__":
    menu()