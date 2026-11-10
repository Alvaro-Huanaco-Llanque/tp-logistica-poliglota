import time
from repositories.neo4j_repo import inicializar_red_hubs_neo4j, registrar_relaciones_envio_grafo
from repositories.pg_repo import (
    registrar_envio_con_contenedores_cliente
)
from repositories.mongo_repo import (
    generar_lectura_iot_coordenadas,
    registrar_incidente
)
from config.database import get_pg_connection, mongo_db, redis_client

def cargar_datos_prueba():
    print("Iniciando carga de datos de prueba...")

    # 1. Limpiar Caché Redis
    redis_client.flushall()
    print("✅ Redis limpiado.")

    # 2. Inicializar Grafo en Neo4j (coordenadas reales)
    inicializar_red_hubs_neo4j()

    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 3. Crear Cliente de Prueba (con Cuenta Corriente)
        print("Creando Cliente y Proveedores...")
        cursor.execute("""
            INSERT INTO cliente (cuit, razon_social, email, telefono, direccion, pais, estado_cliente)
            VALUES (20111111112, 'TechCorp Exports SA', 'logistica@techcorp.com', 1122334455, 'Av. Madero 1020', 'Argentina', 'ACTIVO')
            RETURNING id_cliente;
        """)
        id_cli = cursor.fetchone()[0]
        cursor.execute("INSERT INTO cuenta_corriente (id_cliente, saldo, tipo_entidad) VALUES (%s, 500000, 'CLIENTE');", (id_cli,))

        # 4. Crear Proveedor y Operador
        cursor.execute("""
            INSERT INTO proveedor (cuit, razon_social, tipo_insumo, email, estado)
            VALUES (30555555551, 'Sensitech Latam', 'SENSORES_IOT', 'ventas@sensitech.com', 'ACTIVO')
            RETURNING id_proveedor;
        """)
        id_prov = cursor.fetchone()[0]
        cursor.execute("INSERT INTO cuenta_corriente (id_proveedor, saldo, tipo_entidad) VALUES (%s, 0, 'PROVEEDOR');", (id_prov,))

        cursor.execute("""
            INSERT INTO operador_logistico (cuit_dni, nombre_completo, especialidad, email, estado)
            VALUES (20444444443, 'Carlos Chofer', 'TRANSPORTE_ULTIMA_MILLA', 'carlos@operadores.com', 'ACTIVO')
            RETURNING id_operador;
        """)
        id_op = cursor.fetchone()[0]
        cursor.execute("INSERT INTO cuenta_corriente (id_operador, saldo, tipo_entidad) VALUES (%s, 0, 'OPERADOR');", (id_op,))
        conn.commit()

        # 5. Configurar Regla IoT en MongoDB
        mongo_db["reglas_iot"].update_one(
            {"parametro": "TEMPERATURA"},
            {"$set": {"umbral_maximo": 10.0, "estado": "ACTIVA"}},
            upsert=True
        )

        # 6. Registrar Envío con Contenedores (Esto generará el Tramo, los Sensores y la Factura automáticamente)
        print("Registrando envío y generando histórico IoT...")
        contenedores = [{"codigo": "MSKU-1234", "tipo": "REFRIGERADO", "capacidad": 25000}]
        # Supongamos que TechCorp quiere mandar de Buenos Aires a Chile (SCL)
        id_envio = registrar_envio_con_contenedores_cliente(id_cli, "BUE", "SCL", "ALTA", contenedores)

        # Registrar la relación del envío en el grafo Neo4j
        registrar_relaciones_envio_grafo(id_envio, 'TechCorp Exports SA', 'Carlos Chofer', 'Sensitech Latam', "BUE", "SCL")

        # 7. Simular 3 lecturas IoT de trayecto (para popular Redis y MongoDB)
        # Obtenemos los IDs de los contenedores/sensores recién creados
        cursor.execute("SELECT id_contenedor FROM contenedor WHERE id_envio = %s;", (id_envio,))
        id_cont = cursor.fetchone()[0]
        cursor.execute("SELECT id_sensor FROM sensor_iot WHERE id_contenedor = %s;", (id_cont,))
        id_sens = cursor.fetchone()[0]

        for i in range(3):  
            generar_lectura_iot_coordenadas(id_envio, id_cont, id_sens)
            time.sleep(1) # Pausa breve para simular tiempos distintos

        # 8. Registrar un Incidente de prueba para los reportes
        registrar_incidente(id_envio, "Falla Mecánica", "ALTA", "Camión demorado en aduana de Mendoza")

        print("✅ Carga de datos inicial completada con éxito.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante el seed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    cargar_datos_prueba()