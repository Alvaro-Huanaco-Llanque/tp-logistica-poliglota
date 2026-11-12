import time
from datetime import datetime
from repositories.neo4j_repo import inicializar_red_hubs_neo4j
from repositories.pg_repo import registrar_envio_con_contenedores_cliente, emitir_factura_por_entrega
from repositories.mongo_repo import (
    generar_lectura_iot_coordenadas,
    registrar_evento_logistico,
    registrar_incidente,
    registrar_prediccion_riesgo,
    enviar_mensaje
)
from config.database import get_pg_connection, mongo_db, redis_client

def cargar_datos_prueba():
    print("🧹 1. Limpiando bases de datos (Redis, MongoDB, Neo4j y PostgreSQL)...")
    redis_client.flushall()
    for col in mongo_db.list_collection_names():
        mongo_db[col].delete_many({})
    inicializar_red_hubs_neo4j()

    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            TRUNCATE TABLE 
                pago, factura, cuenta_corriente, 
                sensor_iot, contenedor, tramo, envio, 
                vehiculo, grupo_trabajo, sesion, 
                cliente, proveedor, operador_logistico, usuario, rol
            RESTART IDENTITY CASCADE;
        """)

        # 2. Insertar los 4 Roles y Empleados del ERP con apellidos reales
        cursor.execute("""
            INSERT INTO rol (id_rol, descripcion, nivel_de_permisos) VALUES
            (1, 'GERENTE_OPERACIONES', 100),
            (2, 'GESTOR_TRAFICO_IOT', 80),
            (3, 'ANALISTA_FINANZAS', 80),
            (4, 'ANALISTA_REPORTES', 60);

            INSERT INTO usuario (id_rol, nombre, apellido, email, contrasena_encriptada, estado_usuario) VALUES
            (1, 'Alvaro', 'Gómez', 'alvaro@logistica.com', '1234', TRUE),
            (2, 'Licha', 'Fernández', 'licha@logistica.com', '1234', TRUE),
            (3, 'Sofía', 'López', 'sofia@logistica.com', '1234', TRUE),
            (4, 'Martín', 'Martínez', 'martin@logistica.com', '1234', TRUE);
        """)

        # 3. Crear Clientes
        cursor.execute("""
            INSERT INTO cliente (cuit, razon_social, email, telefono, direccion, pais, estado_cliente) VALUES
            (30710011223, 'TechCorp Exports S.A.', 'comex@techcorp.com', 1143219999, 'Av. Leandro N. Alem 1050, CABA', 'Argentina', 'ACTIVO'),
            (30689900114, 'AgroPampa Cereales S.R.L.', 'logistica@agropampa.com', 3415558877, 'Bv. Oroño 450, Rosario', 'Argentina', 'ACTIVO');
        """)
        cursor.execute("INSERT INTO cuenta_corriente (id_cliente, saldo, tipo_entidad) VALUES (1, 0.00, 'CLIENTE'), (2, 0.00, 'CLIENTE');")

        # 4. Crear Proveedores
        cursor.execute("""
            INSERT INTO proveedor (cuit, razon_social, tipo_insumo, email, telefono, direccion, estado) VALUES
            (30551122339, 'Maersk Containers Latam S.A.', 'CONTENEDORES', 'leasing@maersk.com', 1140001111, 'Dársena Norte Puerto BsAs', 'ACTIVO'),
            (30664455668, 'Sensitech IoT Argentina S.A.', 'SENSORES_IOT', 'soporte@sensitech.com', 1140002222, 'Parque Patricios Tech 240', 'ACTIVO');
        """)
        cursor.execute("INSERT INTO cuenta_corriente (id_proveedor, saldo, tipo_entidad) VALUES (1, 0.00, 'PROVEEDOR'), (2, 0.00, 'PROVEEDOR');")

        # 5. Crear Operadores Logísticos (Carlos y Lucía)
        cursor.execute("""
            INSERT INTO operador_logistico (cuit_dni, nombre_completo, especialidad, email, telefono, estado) VALUES
            (20334455667, 'Carlos', 'DESPACHANTE_ADUANA', 'carlos@operadores.com', 2614445566, 'ACTIVO'),
            (27359988771, 'Lucía', 'CARGA_DESCARGA_PUERTO', 'lucia@operadores.com', 1143334444, 'ACTIVO');
        """)
        cursor.execute("INSERT INTO cuenta_corriente (id_operador, saldo, tipo_entidad) VALUES (1, 0.00, 'OPERADOR'), (2, 0.00, 'OPERADOR');")
        conn.commit()

        # 6. Configurar Reglas IoT en MongoDB (MAXIMO para Temperatura y MINIMO para Batería)
        mongo_db["reglas_iot"].insert_many([
            {"parametro": "TEMPERATURA", "condicion": "MAXIMO", "umbral": 8.0, "estado": "ACTIVA", "actualizado": datetime.now()},
            {"parametro": "BATERIA", "condicion": "MINIMO", "umbral": 15.0, "estado": "ACTIVA", "actualizado": datetime.now()}
        ])

        # 7. Crear Envío #1 (Internacional: Buenos Aires -> Santiago de Chile con Operador Carlos)
        contenedores_env1 = [{
            "codigo": "MSKU-9081",
            "tipo": "REFRIGERADO",
            "capacidad": 24000,
            "id_proveedor_contenedor": 1,
            "tipo_sensor": "TEMPERATURA_GPS",
            "id_proveedor_sensor": 2
        }]
        id_env1 = registrar_envio_con_contenedores_cliente(1, "Buenos Aires", "Santiago de Chile", "ALTA", contenedores_env1, id_operador=1)

        # Crear Envío #2 (Nacional Terrestre: Buenos Aires -> Rosario, sin operador externo)
        contenedores_env2 = [{
            "codigo": "CONT-4410",
            "tipo": "ESTANDAR",
            "capacidad": 18000,
            "id_proveedor_contenedor": 1,
            "tipo_sensor": "HUMEDAD_GPS",
            "id_proveedor_sensor": 2
        }]
        id_env2 = registrar_envio_con_contenedores_cliente(2, "Buenos Aires", "Rosario", "MEDIA", contenedores_env2, id_operador=None)

        # Marcar Envío #1 como ENTREGADO para disparar su facturación automática al Cliente #1
        cursor.execute("UPDATE envio SET estado_envio = 'ENTREGADO' WHERE id_envio = %s;", (id_env1,))
        cursor.execute("UPDATE contenedor SET estado_contenedor = 'DESCARGADO' WHERE id_envio = %s;", (id_env1,))
        emitir_factura_por_entrega(cursor, id_env1)

        cursor.execute("UPDATE envio SET estado_envio = 'EN_TRANSITO' WHERE id_envio = %s;", (id_env2,))
        cursor.execute("UPDATE contenedor SET estado_contenedor = 'EN_TRANSITO' WHERE id_envio = %s;", (id_env2,))
        conn.commit()

        # 8. Generar Lecturas IoT, Eventos, Incidentes y Predicciones
        for _ in range(3):
            generar_lectura_iot_coordenadas(id_env1, 1)
            time.sleep(0.1)
        generar_lectura_iot_coordenadas(id_env2, 2)

        registrar_evento_logistico(id_env1, "Carga iniciada", "Puerto Buenos Aires", "Consolidación y precintado del contenedor")
        registrar_evento_logistico(id_env1, "Aduana", "Mendoza", "Despacho de exportación liberado por Carlos")
        registrar_evento_logistico(id_env1, "Entregado", "Santiago de Chile", "Descarga completada en destino")

        registrar_incidente(id_env1, "Climático", "MEDIA", "Viento blanco en cruce de cordillera generó 4 hs de espera")
        registrar_prediccion_riesgo(id_env1, 75, "ALTO", "MEDIO")
        registrar_prediccion_riesgo(id_env2, 25, "BAJO", "BAJO")

        enviar_mensaje("Alvaro Gómez", "Cliente: TechCorp Exports S.A.", "Confirmamos recepción de solicitud de flete Buenos Aires -> Santiago de Chile.")
        enviar_mensaje("Licha Fernández", "Operador: Carlos", "Enviar documentación aduanera para liberación en Mendoza.")

        print("\n🎉 ¡Base de datos cuádruple inicializada y sembrada con éxito!")
        print("👉 Ejecutá 'python main.py' para probar los cambios.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante el seed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    cargar_datos_prueba()