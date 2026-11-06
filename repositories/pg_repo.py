from config.database import get_pg_connection
from repositories.neo4j_repo import buscar_camino_optimo  # Asegúrate de tener esta importación

def input_seguro(mensaje):
    """Permite capturar input de consola y maneja Ctrl+C de forma elegante."""
    try:
        return input(mensaje).strip()
    except KeyboardInterrupt:
        print("\n\n↩️ Operación cancelada por el usuario. Volviendo al menú...")
        raise KeyboardInterrupt

# --- UTILIDADES DE FORMATO ---
def formatear_cuit(cuit_num):
    if not cuit_num:
        return ""
    s = str(cuit_num).zfill(11)  # Asegura 11 dígitos rellenando con ceros si hace falta
    return f"{s[:2]}-{s[2:10]}-{s[10:]}"

def formatear_telefono(tel_num):
    if not tel_num:
        return ""
    s = str(tel_num)
    # Formato visual: ej. 11 5555-5555 (según longitud)
    if len(s) >= 10:
        return f"{s[:-8]} {s[-8:-4]}-{s[-4:]}"
    return s

# --- AUTENTICACIÓN Y REGISTRO ---
def registrar_inicio_sesion(id_usuario):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sesion (id_usuario, estado) VALUES (%s, 'ACTIVA') RETURNING id_sesion;",
            (id_usuario,)
        )
        id_sesion = cursor.fetchone()[0]
        conn.commit()
        return id_sesion
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def cerrar_sesion_activa(id_sesion):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE sesion SET estado = 'CERRADA', fecha_fin = CURRENT_TIMESTAMP WHERE id_sesion = %s;",
            (id_sesion,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def login_general(email_o_cuit, password):
    """
    Función de login unificada para Clientes (vía CUIT) y Operadores/Proveedores (vía Email o Nombre).
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        if str(email_o_cuit).isdigit():
            cursor.execute("""
                SELECT u.id_usuario, u.id_rol, u.nombre, u.apellido, c.estado_cliente, u.id_cliente
                FROM usuario u
                LEFT JOIN cliente c ON u.id_cliente = c.id_cliente
                WHERE c.cuit = %s AND u.contrasena_encriptada = %s;
            """, (int(email_o_cuit), password))
        else:
            cursor.execute("""
                SELECT u.id_usuario, u.id_rol, u.nombre, u.apellido, u.estado_usuario, u.id_cliente
                FROM usuario u
                WHERE u.email = %s AND u.contrasena_encriptada = %s;
            """, (str(email_o_cuit), password))
            
        res = cursor.fetchone()
        if res:
            return {
                "id_usuario": res[0], 
                "id_rol": res[1],  # 1: Operador, 2: Cliente, 3: Proveedor
                "nombre": f"{res[2]} {res[3]}".strip(),
                "estado": res[4],
                "id_cliente": res[5]
            }
        return None
    finally:
        cursor.close()
        conn.close()

def auto_registrar_usuario_general(id_rol, nombre, apellido, email, password, cuit=None, razon_social=None, telefono=None, direccion=None, pais=None):
    """Registra de forma unificada a Clientes, Operadores o Proveedores."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        id_cli = None
        
        # Si es Cliente (Rol 2), primero se registra en la tabla cliente
        if id_rol == 2:
            cursor.execute("""
                INSERT INTO cliente (cuit, razon_social, email, telefono, direccion, pais, estado_cliente) 
                VALUES (%s, %s, %s, %s, %s, %s, 'INACTIVO') RETURNING id_cliente;
            """, (cuit, razon_social, email, telefono, direccion, pais))
            id_cli = cursor.fetchone()[0]

            # Crear su cuenta corriente inicial
            cursor.execute("""
                INSERT INTO cuenta_corriente (id_cliente, saldo, fecha_de_actualizacion)
                VALUES (%s, 0.00, CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING;
            """, (id_cli,))

        # Definir estado inicial del usuario (Cliente inactivo hasta aprobación, Operadores/Proveedores activos)
        estado_inicial = False if id_rol == 2 else True

        # Crear el Usuario vinculado
        cursor.execute("""
            INSERT INTO usuario (id_cliente, id_rol, nombre, apellido, email, contrasena_encriptada, estado_usuario)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_usuario;
        """, (id_cli, id_rol, nombre, apellido, email, password, estado_inicial))
        id_usr = cursor.fetchone()[0]

        conn.commit()
        return id_usr
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


# --- FUNCIONES DE APOYO PARA ABM CLIENTES (Con Formato) ---
def listar_clientes_formateados():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_cliente, razon_social, cuit, email, telefono, estado_cliente FROM cliente ORDER BY id_cliente ASC;")
        for c in cursor.fetchall():
            cuit_fmt = formatear_cuit(c[2])
            tel_fmt = formatear_telefono(c[4])
            print(f"   ID: {c[0]} | Razón Social: {c[1]} | CUIT: {cuit_fmt} | Email: {c[3]} | Tel: {tel_fmt} | Estado: {c[5]}")
    finally:
        cursor.close()
        conn.close()

def obtener_estado_cliente(id_cliente):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT estado_cliente, razon_social FROM cliente WHERE id_cliente = %s;", (id_cliente,))
        fila = cursor.fetchone()
        if fila:
            return {"estado": fila[0], "razon_social": fila[1]}
        return None
    finally:
        cursor.close()
        conn.close()

def crear_factura_y_actualizar_saldo(cliente_id, importe_total):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO factura (id_cliente, importe_total, fecha_emision, estado_factura) 
               VALUES (%s, %s, CURRENT_DATE, 'a_pagar') RETURNING id_factura;""",
            (cliente_id, importe_total)
        )
        id_factura = cursor.fetchone()[0]
        cursor.execute(
            """UPDATE cuenta_corriente 
               SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
               WHERE id_cliente = %s;""",
            (importe_total, cliente_id)
        )
        conn.commit()
        return id_factura
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error en transacción ACID: {e}")
    finally:
        cursor.close()
        conn.close()


def registrar_envio_cliente(id_cliente, origen, destino, prioridad):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT estado_cliente FROM cliente WHERE id_cliente = %s;", (id_cliente,))
        est = cursor.fetchone()
        if not est or est[0] != "ACTIVO":
            raise Exception(f"Tu cuenta está en estado '{est[0] if est else 'INEXISTENTE'}'. Debe ser dada de alta por un operario para operar.")

        cursor.execute("""
            INSERT INTO envio (id_cliente, origen_envio, destino_envio, fecha_creacion, estado_envio, prioridad)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'EN_PREPARACION', %s) RETURNING id_envio;
        """, (id_cliente, origen, destino, prioridad))
        id_env = cursor.fetchone()[0]
        conn.commit()
        return id_env
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

# --- MENÚS DE ABM OPERARIO ---
def abm_cliente_menu():
    while True:
        print("\n--- [ABM Clientes] ---")
        print("1. Listar Clientes (con formato CUIT y Teléfono)")
        print("2. Modificar Datos de Cliente")
        print("3. Cambiar Estado (ACTIVO / SUSPENDIDO / INACTIVO)")
        print("4. Eliminar Cliente Físicamente")
        print("5. Volver")
        op = input("Elegí una opción (1-5): ").strip()
        
        if op == "5":
            break
            
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                listar_clientes_formateados()
                
            elif op == "2":
                id_cli = int(input("ID del Cliente a modificar: "))
                razon = input("Nueva Razón Social: ")
                tel = int(input("Nuevo Teléfono (solo números): "))
                dir_cli = input("Nueva Dirección: ")
                cursor.execute("""
                    UPDATE cliente SET razon_social = %s, telefono = %s, direccion = %s 
                    WHERE id_cliente = %s;
                """, (razon, tel, dir_cli, id_cli))
                conn.commit()
                print(f"✅ Cliente #{id_cli} modificado.")
                
            elif op == "3":
                id_cli = int(input("ID del Cliente: "))
                print("Estados: 1. ACTIVO (Dar de alta/operativo) | 2. SUSPENDIDO | 3. INACTIVO")
                est_op = input("Seleccioná el estado (1-3): ").strip()
                nuevo_estado = {"1": "ACTIVO", "2": "SUSPENDIDO", "3": "INACTIVO"}.get(est_op, "ACTIVO")
                
                cursor.execute("UPDATE cliente SET estado_cliente = %s WHERE id_cliente = %s;", (nuevo_estado, id_cli))
                conn.commit()
                print(f"✅ Estado del Cliente #{id_cli} cambiado a '{nuevo_estado}'.")
                
            elif op == "4":
                id_cli = int(input("ID del Cliente a eliminar físicamente: "))
                cursor.execute("DELETE FROM cuenta_corriente WHERE id_cliente = %s;", (id_cli,))
                cursor.execute("DELETE FROM usuario WHERE id_cliente = %s;", (id_cli,))
                cursor.execute("DELETE FROM cliente WHERE id_cliente = %s;", (id_cli,))
                conn.commit()
                print(f"🗑️ Cliente #{id_cli} eliminado.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {e}")
        finally:
            cursor.close()
            conn.close()
            

# --- FUNCIONES DE ENVÍOS Y CONTENEDORES PARA CLIENTES Y OPERARIOS ---

def listar_envios_cliente(id_cliente):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id_envio, origen_envio, destino_envio, estado_envio, prioridad, fecha_creacion
            FROM envio WHERE id_cliente = %s ORDER BY id_envio DESC;
        """, (id_cliente,))
        envios = cursor.fetchall()
        
        if not envios:
            print("📦 No tenés envíos registrados.")
            return
            
        for e in envios:
            print(f"\n📦 Envío #{e[0]} | {e[1]} -> {e[2]} | Estado: {e[3]} | Prioridad: {e[4]} | Creado: {e[5]}")
            cursor.execute("""
                SELECT id_contenedor, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor
                FROM contenedor WHERE id_envio = %s ORDER BY id_contenedor ASC;
            """, (e[0],))
            contenedores = cursor.fetchall()
            if contenedores:
                for c in contenedores:
                    print(f"   🚛 Contenedor #{c[0]} | Código: {c[1]} | Tipo: {c[2]} | Cap: {c[3]}kg | Estado: {c[4]}")
            else:
                print("   ⚠️ Sin contenedores asociados.")
    finally:
        cursor.close()
        conn.close()

def abm_envio_contenedor_sensor_menu():
    while True:
        print("\n--- [Gestión de Envíos, Contenedores y Sensores] ---")
        print("1. Listar Envíos, Contenedores y Sensores")
        print("2. Asociar Sensor IoT a un Contenedor")
        print("3. Cambiar Estado de un Envío (Administrativo)")
        print("4. Cambiar Estado de un Contenedor (Físico)")
        print("5. Cambiar Estado de un Sensor IoT (Activar/Desactivar)")
        print("6. Volver")
        
        try:
            op = input_seguro("Elegí una opción (1-6): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo...")
            break
        
        if op == "6":
            break
            
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                cursor.execute("SELECT id_envio, id_cliente, origen_envio, destino_envio, estado_envio FROM envio ORDER BY id_envio ASC;")
                print("\n📦 Envíos (Administrativos):")
                for e in cursor.fetchall():
                    print(f"   Envío #{e[0]} | Cliente ID: {e[1]} | {e[2]} -> {e[3]} | Estado: {e[4]}")
                    
                cursor.execute("SELECT id_contenedor, id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor FROM contenedor ORDER BY id_contenedor ASC;")
                print("\n🚛 Contenedores (Físicos):")
                for c in cursor.fetchall():
                    print(f"   Contenedor #{c[0]} | Envío #{c[1]} | Cód: {c[2]} | Tipo: {c[3]} | Cap: {c[4]}kg | Estado: {c[5]}")
                    
                cursor.execute("SELECT id_sensor, id_contenedor, tipo_sensor, fabricante, estado_sensor FROM sensor_iot ORDER BY id_sensor ASC;")
                print("\n📡 Sensores IoT:")
                for s in cursor.fetchall():
                    # Aquí cambiamos "OPERATIVO" por "ACTIVO"
                    estado_txt = "ACTIVO" if s[4] else "INACTIVO"
                    print(f"   Sensor #{s[0]} | Contenedor #{s[1]} | Tipo: {s[2]} | Fabricante: {s[3]} | Estado: {estado_txt}")
                    
            elif op == "2":
                print("\n--- Asociar Sensor IoT a un Contenedor ---")
                id_cont = int(input_seguro("ID del Contenedor donde se instala: ") or 1)
                tipo_s = input_seguro("Tipo de sensor [TEMPERATURA_GPS / HUMEDAD]: ") or "TEMPERATURA_GPS"
                fab = input_seguro("Fabricante [Enter para Sensitech]: ") or "Sensitech"
                
                cursor.execute("""
                    INSERT INTO sensor_iot (id_contenedor, tipo_sensor, fabricante, fecha_instalacion, estado_sensor)
                    VALUES (%s, %s, %s, CURRENT_DATE, TRUE) RETURNING id_sensor;
                """, (id_cont, tipo_s, fab))
                id_sens = cursor.fetchone()[0]
                conn.commit()
                print(f"✅ Sensor IoT #{id_sens} asociado exitosamente al Contenedor #{id_cont}.")
                
            elif op == "3":
                print("\n--- Cambiar Estado de un Envío (Administrativo) ---")
                id_env = int(input_seguro("ID del Envío: "))
                print("Estados: 1. EN_PREPARACION | 2. EN_TRANSITO | 3. DEMORADO | 4. ENTREGADO | 5. CANCELADO")
                est_op = input_seguro("Seleccioná (1-5): ").strip()
                mapeo_estados = {"1": "EN_PREPARACION", "2": "EN_TRANSITO", "3": "DEMORADO", "4": "ENTREGADO", "5": "CANCELADO"}
                nuevo_est = mapeo_estados.get(est_op, "EN_TRANSITO")
                
                cursor.execute("UPDATE envio SET estado_envio = %s WHERE id_envio = %s;", (nuevo_est, id_env))
                conn.commit()
                print(f"✅ Envío #{id_env} actualizado a '{nuevo_est}'.")

            elif op == "4":
                print("\n--- Cambiar Estado de un Contenedor (Físico) ---")
                id_cont = int(input_seguro("ID del Contenedor: "))
                print("Estados: 1. EN_PREPARACION | 2. EN_TRANSITO | 3. DEMORADO | 4. DESCARGADO")
                est_op = input_seguro("Seleccioná (1-4): ").strip()
                mapeo_estados = {"1": "EN_PREPARACION", "2": "EN_TRANSITO", "3": "DEMORADO", "4": "DESCARGADO"}
                nuevo_est = mapeo_estados.get(est_op, "EN_TRANSITO")
                
                cursor.execute("UPDATE contenedor SET estado_contenedor = %s WHERE id_contenedor = %s;", (nuevo_est, id_cont))
                conn.commit()
                print(f"✅ Contenedor #{id_cont} actualizado a '{nuevo_est}'.")

            elif op == "5":
                print("\n--- Cambiar Estado de un Sensor IoT ---")
                id_sens = int(input_seguro("ID del Sensor: "))
                print("Estados: 1. ACTIVO | 2. INACTIVO")
                est_op = input_seguro("Seleccioná (1-2): ").strip()
                nuevo_est_bool = True if est_op == "1" else False
                
                cursor.execute("UPDATE sensor_iot SET estado_sensor = %s WHERE id_sensor = %s;", (nuevo_est_bool, id_sens))
                conn.commit()
                txt_estado = "ACTIVO" if nuevo_est_bool else "INACTIVO"
                print(f"✅ Sensor #{id_sens} actualizado a '{txt_estado}'.")
                
        except KeyboardInterrupt:
            print("\n↩️ Operación cancelada por el usuario.")
            conn.rollback()
            continue
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {e}")
        finally:
            cursor.close()
            conn.close()


def registrar_envio_con_contenedores_cliente(id_cliente, origen, destino, prioridad, lista_contenedores):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Validar que el cliente esté ACTIVO
        cursor.execute("SELECT estado_cliente FROM cliente WHERE id_cliente = %s;", (id_cliente,))
        est = cursor.fetchone()
        if not est or est[0] != "ACTIVO":
            raise Exception(f"Tu cuenta está '{est[0] if est else 'INEXISTENTE'}'. Debe ser ACTIVA.")

        # 2. Calcular distancia aproximada y medio de transporte según tus reglas de negocio
        # (Aquí integramos la lógica de Neo4j o tarifas base por distancia)
        distancia_base = 500  # Valor por defecto si no encuentra ruta directa
        medio_transporte = "TERRESTRE"
        
        if "Malvinas" in destino or "Antártida" in destino:
            if prioridad == "BAJA":
                medio_transporte = "MIXTO (Camión + Barco)"
                distancia_base = 1200
            elif prioridad == "MEDIA":
                medio_transporte = "MARÍTIMO (Barco)"
                distancia_base = 1500
            else: # ALTA
                medio_transporte = "AÉREO (Avión)"
                distancia_base = 800
        elif prioridad == "ALTA":
            medio_transporte = "AÉREO (Avión)"
            distancia_base = 1000
            
        # Costo dinámico: Distancia * Tarifa por tipo de transporte + recargo de prioridad
        tarifa_km = {"TERRESTRE": 50, "MIXTO (Camión + Barco)": 70, "MARÍTIMO (Barco)": 90, "AÉREO (Avión)": 150}
        costo_unitario = tarifa_km.get(medio_transporte, 50)
        
        importe_total = len(lista_contenedores) * (distancia_base * costo_unitario / 10)

        # 3. Crear el Envío (Administrativo)
        cursor.execute("""
            INSERT INTO envio (id_cliente, origen_envio, destino_envio, fecha_creacion, estado_envio, prioridad)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'EN_PREPARACION', %s) RETURNING id_envio;
        """, (id_cliente, origen, destino, prioridad))
        id_env = cursor.fetchone()[0]

        # 4. Crear Contenedores vinculados
        for c in lista_contenedores:
            cursor.execute("""
                INSERT INTO contenedor (id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor)
                VALUES (%s, %s, %s, %s, 'EN_PREPARACION');
            """, (id_env, c['codigo'], c['tipo'], c['capacidad']))

        # 5. GENERACIÓN AUTOMÁTICA DE FACTURA Y ACTUALIZACIÓN DE CUENTA CORRIENTE (Transacción ACID)
        cursor.execute(
            """INSERT INTO factura (id_cliente, importe_total, fecha_emision, estado_factura) 
               VALUES (%s, %s, CURRENT_DATE, 'a_pagar') RETURNING id_factura;""",
            (id_cliente, importe_total)
        )
        id_factura = cursor.fetchone()[0]

        cursor.execute(
            """UPDATE cuenta_corriente 
               SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
               WHERE id_cliente = %s;""",
            (importe_total, id_cliente)
        )

        conn.commit()
        print(f"\n✨ [FACTURACIÓN AUTOMÁTICA APLICADA]: Envío #{id_env} calculado via {medio_transporte}.")
        print(f"📄 Se generó la Factura #{id_factura} por un total de ${importe_total} cargada a tu cuenta corriente.")
        return id_env
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


# --- ABM DE VEHÍCULOS ---

def registrar_vehiculo(tipo_vehiculo, identificacion, empresa_operadora, estado="DISPONIBLE"):
    """Permite a un proveedor registrar un nuevo vehículo físico en la flota."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO vehiculo (tipo_vehiculo, identificacion, empresa_operadora, estado_vehiculo)
            VALUES (%s, %s, %s, %s) RETURNING id_vehiculo;
        """, (tipo_vehiculo, identificacion, empresa_operadora, estado))
        
        id_vehiculo = cursor.fetchone()[0]
        conn.commit()
        print(f"✅ Vehículo registrado exitosamente con ID #{id_vehiculo}.")
        return id_vehiculo
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al registrar vehículo: {e}")
    finally:
        cursor.close()
        conn.close()

def listar_vehiculos():
    """Muestra el listado de vehículos registrados en el sistema."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_vehiculo, tipo_vehiculo, identificacion, empresa_operadora, estado_vehiculo FROM vehiculo ORDER BY id_vehiculo ASC;")
        vehiculos = cursor.fetchall()
        
        if not vehiculos:
            print("   ⚠️ No hay vehículos registrados en la flota.")
            return

        print("\n🚛 [ FLOTA DE VEHÍCULOS ]")
        for v in vehiculos:
            print(f"   - ID: {v[0]} | Tipo: {v[1]} | Patente/ID: {v[2]} | Empresa: {v[3]} | Estado: {v[4]}")
            
    except Exception as e:
        print(f"❌ Error al listar vehículos: {e}")
    finally:
        cursor.close()
        conn.close()


# --- ABM DE GRUPOS DE TRABAJO (POSTGRESQL) ---

def registrar_grupo_trabajo(nombre, integrantes):
    """Crea un nuevo grupo de trabajo (Ej. 'Operadores Puerto', 'Choferes Norte')."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO grupo_trabajo (nombre, integrantes)
            VALUES (%s, %s) RETURNING id_grupo;
        """, (nombre, integrantes))
        id_grupo = cursor.fetchone()[0]
        conn.commit()
        print(f"✅ Grupo de Trabajo '{nombre}' creado con ID #{id_grupo}.")
        return id_grupo
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al crear grupo de trabajo: {e}")
    finally:
        cursor.close()
        conn.close()

def listar_grupos_trabajo():
    """Muestra todos los grupos de trabajo registrados."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_grupo, nombre, integrantes FROM grupo_trabajo ORDER BY id_grupo ASC;")
        grupos = cursor.fetchall()
        if not grupos:
            print("   ⚠️ No hay grupos de trabajo creados.")
            return
        print("\n👥 [ GRUPOS DE TRABAJO ]")
        for g in grupos:
            print(f"   - ID: {g[0]} | Nombre: {g[1]} | Integrantes: {g[2]}")
    except Exception as e:
        print(f"❌ Error al listar grupos: {e}")
    finally:
        cursor.close()
        conn.close()


# --- REPORTES OPERATIVOS Y ANALÍTICOS (POSTGRESQL) ---


def reporte_envios_por_pais():
    """Reporte analítico: Calcula el volumen de envíos agrupados por el país/origen de salida."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # Analizamos el campo origen_envio para agrupar por origen de salida
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN origen_envio LIKE '%Argentina%' OR origen_envio LIKE '%Buenos Aires%' OR origen_envio LIKE '%Malvinas%' THEN 'Argentina'
                    WHEN origen_envio LIKE '%Colombia%' OR origen_envio LIKE '%Bogotá%' THEN 'Colombia'
                    WHEN origen_envio LIKE '%México%' OR origen_envio LIKE '%Veracruz%' THEN 'México'
                    ELSE 'Otros'
                END as pais_origen,
                COUNT(id_envio) as total_envios
            FROM envio
            GROUP BY pais_origen 
            ORDER BY total_envios DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_envios_por_estado():
    """Reporte analítico: Muestra la cantidad de envíos agrupados por su estado actual."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT estado_envio, COUNT(id_envio) as total
            FROM envio
            GROUP BY estado_envio
            ORDER BY total DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def reporte_envios_por_cliente():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, COUNT(e.id_envio)
            FROM envio e
            JOIN cliente c ON e.id_cliente = c.id_cliente
            GROUP BY c.razon_social ORDER BY COUNT(e.id_envio) DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_envios_demorados():
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_envio, id_cliente, origen_envio, destino_envio FROM envio WHERE estado_envio = 'DEMORADO';")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_tiempos_por_envio():
    """Reporte para Clientes: Muestra el tiempo estimado o real de cada envío individual (1, 2 y 3)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT e.id_envio, e.origen_envio, e.destino_envio, e.estado_envio,
                   EXTRACT(EPOCH FROM (t.fecha_de_llegada_estimada - t.fecha_de_salida))/86400 as dias_trayecto
            FROM envio e
            JOIN tramo t ON e.id_envio = t.id_envio
            ORDER BY e.id_envio ASC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def reporte_tiempos_envio_por_cliente():
    """Reporte para Proveedores/Operadores: Tiempos máximos y mínimos agrupados por cliente."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, 
                   MAX(EXTRACT(EPOCH FROM (t.fecha_de_llegada_estimada - t.fecha_de_salida))/86400) as max_dias,
                   MIN(EXTRACT(EPOCH FROM (t.fecha_de_llegada_estimada - t.fecha_de_salida))/86400) as min_dias
            FROM envio e
            JOIN cliente c ON e.id_cliente = c.id_cliente
            JOIN tramo t ON e.id_envio = t.id_envio
            GROUP BY c.razon_social;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def reporte_costos_por_tipo_transporte():
    """Reporte analítico: Calcula el uso y costo estimado por tipo de transporte usando la tabla tramo."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT medio_de_transporte, COUNT(*) as cantidad_tramos
            FROM tramo
            GROUP BY medio_de_transporte ORDER BY cantidad_tramos DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def agregar_saldo_cliente(cliente_id, monto):
    """Permite al cliente recargar fondos / agregar saldo disponible a su cuenta."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # Sumamos al saldo disponible de la cuenta corriente
        cursor.execute(
            """UPDATE cuenta_corriente 
               SET saldo = saldo + %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
               WHERE id_cliente = %s;""",
            (monto, cliente_id)
        )
        conn.commit()
        print(f"✅ ¡Recarga de ${monto} exitosa! Fondos acreditados al saldo disponible.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al recargar saldo: {e}")
    finally:
        cursor.close()
        conn.close()

def pagar_factura_cliente(cliente_id, id_factura):
    """Valida el saldo disponible, pregunta el medio de pago y abona la factura."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Consultar saldo disponible actual
        cursor.execute("SELECT saldo FROM cuenta_corriente WHERE id_cliente = %s FOR UPDATE;", (cliente_id,))
        res_cc = cursor.fetchone()
        if not res_cc:
            raise Exception("No se encontró cuenta corriente para este cliente.")
        saldo_disponible = res_cc[0]

        # 2. Consultar la factura a pagar
        cursor.execute(
            "SELECT importe_total, estado_factura FROM factura WHERE id_factura = %s AND id_cliente = %s FOR UPDATE;",
            (id_factura, cliente_id)
        )
        factura = cursor.fetchone()
        if not factura:
            raise Exception("La factura no existe o no pertenece a este cliente.")
            
        importe, estado_fac = factura[0], factura[1]
        
        if estado_fac == 'PAGADA':
            raise Exception("Esta factura ya se encuentra pagada.")

        # 3. Validar si el cliente tiene saldo disponible suficiente
        if saldo_disponible < importe:
            print(f"\n❌ Saldo insuficiente. Tu saldo disponible es de ${saldo_disponible} y la factura requiere ${importe}.")
            print(f"💡 Sugerencia: Utiliza la opción '2. Agregar Saldo / Fondos a la cuenta' para recargar dinero antes de pagar.")
            return

        # 4. Seleccionar el Medio de Pago interactivamente
        print("\n--- Seleccioná el Medio de Pago ---")
        print("1. TRANSFERENCIA BANCARIA")
        print("2. TARJETA DE CRÉDITO / DÉBITO")
        print("3. EFECTIVO / RAPIPAGO")
        op_med = input_seguro("Elegí una opción (1-3) [Enter por defecto Transferencia]: ").strip() or "1"
        mapeo_medios = {"1": "TRANSFERENCIA", "2": "TARJETA", "3": "EFECTIVO"}
        medio_pago = mapeo_medios.get(op_med, "TRANSFERENCIA")

        # 5. Registrar el pago en la tabla pago
        cursor.execute(
            """INSERT INTO pago (id_factura, monto, fecha, medio_de_pago) 
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s);""",
            (id_factura, importe, medio_pago)
        )

        # 6. Marcar la factura como PAGADA
        cursor.execute(
            "UPDATE factura SET estado_factura = 'PAGADA' WHERE id_factura = %s;",
            (id_factura,)
        )

        # 7. Descontar el importe del saldo disponible del cliente
        cursor.execute(
            """UPDATE cuenta_corriente 
               SET saldo = saldo - %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
               WHERE id_cliente = %s;""",
            (importe, cliente_id)
        )

        conn.commit()
        print(f"\n✅ ¡Pago de la Factura #{id_factura} realizado con éxito por ${importe} vía {medio_pago}!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al procesar el pago: {e}")
    finally:
        cursor.close()
        conn.close()

def consultar_cuenta_corriente(cliente_id):
    """Muestra la cuenta corriente calculando la deuda real y mostrando el saldo disponible."""
    while True:
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            # 1. Obtener cuenta corriente (saldo disponible)
            cursor.execute("SELECT id_cuenta, saldo, fecha_de_actualizacion FROM cuenta_corriente WHERE id_cliente = %s;", (cliente_id,))
            cuenta = cursor.fetchone()
            
            if not cuenta:
                cursor.execute(
                    "INSERT INTO cuenta_corriente (id_cliente, saldo, fecha_de_actualizacion) VALUES (%s, 0.00, CURRENT_TIMESTAMP) RETURNING id_cuenta, saldo, fecha_de_actualizacion;",
                    (cliente_id,)
                )
                conn.commit()
                cuenta = cursor.fetchone()

            id_cuenta = cuenta[0]
            saldo_disponible = cuenta[1]
            fecha_act = cuenta[2]

            # 2. Calcular la Deuda Acumulada (Sumamos importe_total de facturas a_pagar o vencido)
            # Usamos LOWER para asegurar que coincida sin importar cómo se guardó
            cursor.execute("""
                SELECT COALESCE(SUM(importe_total), 0) 
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) IN ('a_pagar', 'vencido');
            """, (cliente_id,))
            deuda_acumulada = cursor.fetchone()[0]

            print(f"\n=======================================================")
            print(f"   ESTADO DE CUENTA CORRIENTE (ID Cuenta: {id_cuenta})")
            print(f"   Deuda acumulada: ${deuda_acumulada}")
            print(f"   Saldo Disponible / A Favor: ${saldo_disponible}")
            print(f"   Actualizado: {fecha_act}")
            print(f"=======================================================")

            # 3. Deuda Vencida Impaga
            cursor.execute("""
                SELECT id_factura, importe_total, fecha_emision 
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) = 'vencido'
                ORDER BY fecha_emision ASC;
            """, (cliente_id,))
            vencidas = cursor.fetchall()

            print("\n🔴 [ DEUDA VENCIDA IMPAGA ]")
            if vencidas:
                for f in vencidas:
                    print(f"   - Factura ID #{f[0]} | Emitida: {f[2]} | Monto: ${f[1]}")
            else:
                print("   Sin datos.")

            # 4. Facturado a Vencer
            cursor.execute("""
                SELECT id_factura, importe_total, fecha_emision, fecha_emision + INTERVAL '30 days' as vto 
                FROM factura 
                WHERE id_cliente = %s AND LOWER(estado_factura) = 'a_pagar'
                ORDER BY fecha_emision ASC;
            """, (cliente_id,))
            a_vencer = cursor.fetchall()

            print("\n🟡 [ FACTURADO A VENCER ]")
            total_a_vencer = 0
            if a_vencer:
                for f in a_vencer:
                    total_a_vencer += f[1]
                    fecha_vto = f[3].strftime('%d/%m/%Y') if f[3] else 'Próximamente'
                    print(f"   - ID Factura #{f[0]} | Vto: {fecha_vto} | Monto: ${f[1]}")
                print(f"   ** TOTAL PRÓXIMOS VENCIMIENTOS: ${total_a_vencer} **")
            else:
                print("   Sin datos.")

            # 5. Pagos Realizados (Usamos la tabla pago, campo monto)
            cursor.execute("""
                SELECT p.id_pago, p.id_factura, p.monto, p.fecha, p.medio_de_pago 
                FROM pago p
                JOIN factura f ON p.id_factura = f.id_factura
                WHERE f.id_cliente = %s
                ORDER BY p.fecha DESC;
            """, (cliente_id,))
            pagos = cursor.fetchall()

            print("\n🟢 [ PAGOS REALIZADOS ]")
            if pagos:
                for p in pagos:
                    print(f"   - Fecha: {p[3].strftime('%d/%m/%Y')} | Recibo PA-{p[0]:04d} | Factura ID #{p[1]} | Monto: ${p[2]} | Medio: {p[4]}")
            else:
                print("   Sin datos de pagos previos.")

        except Exception as e:
            print(f"❌ Error al consultar cuenta: {e}")
            break
        finally:
            cursor.close()
            conn.close()

        # Submenú interactivo
        print("\n-------------------------------------------------------")
        print("   ACCIONES DE CUENTA CORRIENTE:")
        print("   1. Pagar una Factura por ID")
        print("   2. Agregar Saldo / Fondos a la cuenta")
        print("   3. Volver al menú anterior")
        
        op = input_seguro("Seleccioná una opción (1-3): ").strip()
        
        if op == "1":
            try:
                fid_input = input_seguro("Ingresá el ID de la factura que deseas pagar: ")
                if fid_input:
                    pagar_factura_cliente(cliente_id, int(fid_input))
            except ValueError:
                print("❌ Por favor, ingresa un ID numérico válido.")
        elif op == "2":
            try:
                monto_input = input_seguro("Ingresá el monto a agregar: ")
                if monto_input:
                    agregar_saldo_cliente(cliente_id, float(monto_input))
            except ValueError:
                print("❌ Por favor, ingresa un monto numérico válido.")
        elif op == "3":
            break
        else:
            print("⚠️ Opción inválida.")




def listar_envios_y_sensores_operario():
    """Muestra el listado completo de envíos, contenedores y sensores para el operador (Solo Lectura)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_envio, id_cliente, origen_envio, destino_envio, estado_envio FROM envio ORDER BY id_envio ASC;")
        print("\n📦 Envíos Registrados:")
        for e in cursor.fetchall():
            print(f"   - Envío #{e[0]} | Cliente ID: {e[1]} | {e[2]} -> {e[3]} | Estado: {e[4]}")
            
        cursor.execute("SELECT id_contenedor, id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor FROM contenedor ORDER BY id_contenedor ASC;")
        print("\n🚛 Contenedores Físicos:")
        for c in cursor.fetchall():
            print(f"   - Contenedor #{c[0]} | Envío #{c[1]} | Cód: {c[2]} | Tipo: {c[3]} | Cap: {c[4]}kg | Estado: {c[5]}")
            
        cursor.execute("SELECT id_sensor, id_contenedor, tipo_sensor, fabricante, estado_sensor FROM sensor_iot ORDER BY id_sensor ASC;")
        print("\n📡 Sensores IoT:")
        for s in cursor.fetchall():
            estado_txt = "ACTIVO" if s[4] else "INACTIVO"
            print(f"   - Sensor #{s[0]} | Contenedor #{s[1]} | Tipo: {s[2]} | Fabricante: {s[3]} | Estado: {estado_txt}")
    finally:
        cursor.close()
        conn.close()

def consultar_cuenta_corriente_operario(cliente_id):
    """Muestra la cuenta corriente del cliente en modo 'Solo Lectura' para auditoría del operador (Sin opciones de pago)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Obtener saldo disponible
        cursor.execute("SELECT saldo, fecha_de_actualizacion FROM cuenta_corriente WHERE id_cliente = %s;", (cliente_id,))
        cuenta = cursor.fetchone()
        
        if not cuenta:
            print(f"⚠️ El cliente #{cliente_id} no tiene una cuenta corriente registrada o no existe.")
            return

        saldo_disponible = cuenta[0]
        fecha_act = cuenta[1]

        # 2. Obtener Nombre del Cliente
        cursor.execute("SELECT razon_social FROM cliente WHERE id_cliente = %s;", (cliente_id,))
        cli = cursor.fetchone()
        nombre_cliente = cli[0] if cli else "Desconocido"

        # 3. Calcular Deuda Acumulada
        cursor.execute("""
            SELECT COALESCE(SUM(importe_total), 0) 
            FROM factura 
            WHERE id_cliente = %s AND LOWER(estado_factura) IN ('a_pagar', 'vencido');
        """, (cliente_id,))
        deuda_acumulada = cursor.fetchone()[0]

        print(f"\n=======================================================")
        print(f"   AUDITORÍA FINANCIERA - Cliente: {nombre_cliente} (ID: {cliente_id})")
        print(f"   Deuda acumulada actual: ${deuda_acumulada}")
        print(f"   Saldo Disponible / Fondos: ${saldo_disponible}")
        print(f"   Última actualización: {fecha_act}")
        print(f"=======================================================")

        # 4. Deuda Vencida Impaga
        cursor.execute("""
            SELECT id_factura, importe_total, fecha_emision 
            FROM factura 
            WHERE id_cliente = %s AND LOWER(estado_factura) = 'vencido'
            ORDER BY fecha_emision ASC;
        """, (cliente_id,))
        vencidas = cursor.fetchall()

        print("\n🔴 [ DEUDA VENCIDA IMPAGA ]")
        if vencidas:
            for f in vencidas:
                print(f"   - Factura ID #{f[0]} | Emitida: {f[2]} | Monto: ${f[1]}")
        else:
            print("   Sin datos.")

        # 5. Facturado a Vencer
        cursor.execute("""
            SELECT id_factura, importe_total, fecha_emision, fecha_emision + INTERVAL '30 days' as vto 
            FROM factura 
            WHERE id_cliente = %s AND LOWER(estado_factura) = 'a_pagar'
            ORDER BY fecha_emision ASC;
        """, (cliente_id,))
        a_vencer = cursor.fetchall()

        print("\n🟡 [ FACTURADO A VENCER ]")
        total_a_vencer = 0
        if a_vencer:
            for f in a_vencer:
                total_a_vencer += f[1]
                fecha_vto = f[3].strftime('%d/%m/%Y') if f[3] else 'Próximamente'
                print(f"   - ID Factura #{f[0]} | Vto: {fecha_vto} | Monto: ${f[1]}")
            print(f"   ** TOTAL PRÓXIMOS VENCIMIENTOS: ${total_a_vencer} **")
        else:
            print("   Sin datos.")

        # 6. Pagos Realizados
        cursor.execute("""
            SELECT p.id_pago, p.id_factura, p.monto, p.fecha, p.medio_de_pago 
            FROM pago p
            JOIN factura f ON p.id_factura = f.id_factura
            WHERE f.id_cliente = %s
            ORDER BY p.fecha DESC;
        """, (cliente_id,))
        pagos = cursor.fetchall()

        print("\n🟢 [ PAGOS REALIZADOS ]")
        if pagos:
            for p in pagos:
                print(f"   - Fecha: {p[3].strftime('%d/%m/%Y')} | Recibo PA-{p[0]:04d} | Factura ID #{p[1]} | Monto: ${p[2]} | Medio: {p[4]}")
        else:
            print("   Sin datos de pagos previos.")
            
        print("\n-------------------------------------------------------")
        input("Presioná Enter para volver al menú de finanzas...")

    except Exception as e:
        print(f"❌ Error al auditar cuenta: {e}")
    finally:
        cursor.close()
        conn.close()

def listar_clientes_deudores():
    """Reporte administrativo: Muestra los clientes con facturas vencidas y su deuda total."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.id_cliente, c.razon_social, SUM(f.importe_total) as deuda_vencida, COUNT(f.id_factura)
            FROM cliente c
            JOIN factura f ON c.id_cliente = f.id_cliente
            WHERE LOWER(f.estado_factura) = 'vencido'
            GROUP BY c.id_cliente, c.razon_social
            ORDER BY deuda_vencida DESC;
        """)
        morosos = cursor.fetchall()

        print("\n=======================================================")
        print("   ⚠️ REPORTE GLOBAL DE CLIENTES DEUDORES (VENCIDOS)")
        print("=======================================================")
        if not morosos:
            print("   ✅ Excelente: No hay clientes con facturas vencidas en el sistema.")
        else:
            for m in morosos:
                print(f"   - Cliente #{m[0]} ({m[1]}) | Deuda Vencida: ${m[2]} | Facturas impagas: {m[3]}")
    except Exception as e:
        print(f"❌ Error al generar reporte de morosos: {e}")
    finally:
        cursor.close()
        conn.close()

def ranking_clientes_por_volumen():
    """Reporte Proveedor: Suma la capacidad total de los contenedores que movió cada cliente."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.razon_social, SUM(co.capacidad) as volumen_total_kg
            FROM cliente c
            JOIN envio e ON c.id_cliente = e.id_cliente
            JOIN contenedor co ON e.id_envio = co.id_envio
            GROUP BY c.razon_social
            ORDER BY volumen_total_kg DESC;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def analisis_historico_desempeno():
    """Reporte Proveedor: Muestra cuántos envíos terminaron entregados vs demorados/cancelados."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT estado_envio, COUNT(id_envio) 
            FROM envio 
            WHERE estado_envio IN ('ENTREGADO', 'DEMORADO', 'CANCELADO')
            GROUP BY estado_envio;
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def consultar_cuenta_proveedor(nombre_proveedor):
    """Calcula los ingresos generados por los vehículos registrados a nombre del proveedor."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # Buscamos los vehículos del proveedor
        cursor.execute("""
            SELECT id_vehiculo, tipo_vehiculo, identificacion, estado_vehiculo 
            FROM vehiculo 
            WHERE empresa_operadora = %s;
        """, (nombre_proveedor,))
        vehiculos = cursor.fetchall()
        
        print("\n=======================================================")
        print(f"   CUENTA CORRIENTE DE PROVEEDOR (Cuentas por Cobrar)")
        print(f"   Titular: {nombre_proveedor}")
        print("=======================================================")

        if not vehiculos:
            print("   ⚠️ No tienes vehículos registrados operando en la plataforma.")
            print("   Tus ingresos actuales son de $0.00.")
            return

        total_ingresos = 0
        print("\n🚛 [ LIQUIDACIÓN POR USO DE FLOTA ]")
        for v in vehiculos:
            # Simulamos un ingreso fijo por vehículo según su estado para la demostración
            # (En un sistema real, esto se calcularía en base a los tramos recorridos por ese vehículo)
            ingreso_simulado = 150000.00 if v[3] == "EN USO" or v[3] == "DISPONIBLE" else 0.00
            total_ingresos += ingreso_simulado
            print(f"   - Vehículo #{v[0]} ({v[1]} | {v[2]}) -> Ingresos generados: ${ingreso_simulado}")
            
        print("-------------------------------------------------------")
        print(f"   💰 TOTAL A COBRAR (Saldo a Favor): ${total_ingresos}")
        print("-------------------------------------------------------")
        print("   * Los pagos se liquidan automáticamente a fin de mes mediante transferencia CBU.")

    except Exception as e:
        print(f"❌ Error al consultar cuenta de proveedor: {e}")
    finally:
        cursor.close()
        conn.close()

def reporte_tiempos_promedio_general():
    """Calcula el promedio global de entrega en días de todos los tramos."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (fecha_de_llegada_estimada - fecha_de_salida))/86400), 0)
            FROM tramo;
        """)
        prom = cursor.fetchone()[0]
        return round(prom, 1)
    finally:
        cursor.close()
        conn.close()

def abm_usuarios_y_sesiones_menu():
    """Cumple con ABM Usuarios/Roles (Operadores y Proveedores) y ABM Sesiones Activas."""
    while True:
        print("\n--- [ABM Usuarios, Operadores, Proveedores y Sesiones] ---")
        print("1. Listar todos los Usuarios y Roles (Clientes, Operadores, Proveedores)")
        print("2. Activar / Desactivar un Usuario (Baja lógica de Operador/Proveedor)")
        print("3. Cambiar Rol de un Usuario")
        print("4. Ver Sesiones Activas e Históricas")
        print("5. Forzar Cierre de una Sesión Activa (Baja de sesión)")
        print("6. Volver")
        op = input_seguro("Elegí una opción (1-6): ")
        if op == "6":
            break
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                cursor.execute("SELECT id_usuario, nombre, apellido, email, id_rol, estado_usuario FROM usuario ORDER BY id_usuario ASC;")
                mapeo_rol = {1: "OPERADOR", 2: "CLIENTE", 3: "PROVEEDOR"}
                print("\n👤 [ USUARIOS DEL SISTEMA ]")
                for u in cursor.fetchall():
                    est = "ACTIVO" if u[5] else "INACTIVO"
                    print(f"   - ID #{u[0]} | {u[1]} {u[2]} ({u[3]}) | Rol: {mapeo_rol.get(u[4], u[4])} | Estado: {est}")
            elif op == "2":
                uid = int(input_seguro("ID del Usuario a activar/desactivar: "))
                est_op = input_seguro("Nuevo estado (1. ACTIVO / 2. INACTIVO): ")
                nuevo_est = True if est_op == "1" else False
                cursor.execute("UPDATE usuario SET estado_usuario = %s WHERE id_usuario = %s;", (nuevo_est, uid))
                conn.commit()
                print(f"✅ Estado del Usuario #{uid} actualizado.")
            elif op == "3":
                uid = int(input_seguro("ID del Usuario: "))
                nuevo_rol = int(input_seguro("Nuevo Rol (1: Operador, 2: Cliente, 3: Proveedor): "))
                cursor.execute("UPDATE usuario SET id_rol = %s WHERE id_usuario = %s;", (nuevo_rol, uid))
                conn.commit()
                print(f"✅ Rol del Usuario #{uid} actualizado.")
            elif op == "4":
                cursor.execute("""
                    SELECT s.id_sesion, u.nombre, u.apellido, s.estado, s.fecha_inicio, s.fecha_fin
                    FROM sesion s JOIN usuario u ON s.id_usuario = u.id_usuario
                    ORDER BY s.id_sesion DESC LIMIT 15;
                """)
                print("\n🔐 [ SESIONES REGISTRADAS ]")
                for s in cursor.fetchall():
                    print(f"   - Sesión #{s[0]} | Usuario: {s[1]} {s[2]} | Estado: {s[3]} | Inicio: {s[4]} | Fin: {s[5]}")
            elif op == "5":
                sid = int(input_seguro("ID de la Sesión a cerrar: "))
                cerrar_sesion_activa(sid)
                print(f"🔒 Sesión #{sid} cerrada exitosamente.")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {e}")
        finally:
            cursor.close()
            conn.close()

def ejecutar_cierre_mensual_cuentas():
    """Cumple con Cierre mensual de cuentas corrientes: pasa facturas pendientes a vencidas y resume saldos."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE factura 
            SET estado_factura = 'vencido' 
            WHERE LOWER(estado_factura) = 'a_pagar' AND fecha_emision < CURRENT_DATE - INTERVAL '30 days'
            RETURNING id_factura;
        """)
        vencidas = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(saldo), 0) FROM cuenta_corriente;")
        resumen = cursor.fetchone()
        conn.commit()
        
        print("\n📅 [ CIERRE MENSUAL DE CUENTAS CORRIENTES EJECUTADO ]")
        print(f"   - Total de cuentas procesadas: {resumen[0]}")
        print(f"   - Balance global en cuentas corrientes: ${resumen[1]}")
        print(f"   - Facturas que pasaron a estado 'VENCIDO' en este cierre: {len(vencidas)}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en cierre mensual: {e}")
    finally:
        cursor.close()
        conn.close()







