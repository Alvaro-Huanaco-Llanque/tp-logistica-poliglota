from config.database import get_pg_connection

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

def login_cliente(cuit, password):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.id_cliente, c.razon_social, c.estado_cliente, u.id_usuario 
            FROM cliente c
            JOIN usuario u ON c.id_cliente = u.id_cliente
            WHERE c.cuit = %s AND u.contrasena_encriptada = %s;
        """, (cuit, password))
        res = cursor.fetchone()
        if res:
            return {"id_cliente": res[0], "razon_social": res[1], "estado_cliente": res[2], "id_usuario": res[3]}
        return None
    finally:
        cursor.close()
        conn.close()

def login_operario(nombre, apellido, password):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id_usuario, nombre, apellido 
            FROM usuario 
            WHERE LOWER(nombre) = LOWER(%s) AND LOWER(apellido) = LOWER(%s) 
              AND contrasena_encriptada = %s AND id_rol = 1;
        """, (nombre, apellido, password))
        res = cursor.fetchone()
        if res:
            return {"id_usuario": res[0], "nombre": f"{res[1]} {res[2]}"}
        return None
    finally:
        cursor.close()
        conn.close()

def auto_registrar_cliente(cuit, razon, email, tel, direccion, pais, nombre_cont, apellido_cont, password):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Crear el cliente con estado INACTIVO
        cursor.execute("""
            INSERT INTO cliente (cuit, razon_social, email, telefono, direccion, pais, estado_cliente) 
            VALUES (%s, %s, %s, %s, %s, %s, 'INACTIVO') RETURNING id_cliente;
        """, (cuit, razon, email, tel, direccion, pais))
        id_cli = cursor.fetchone()[0]

        # 2. Crear su cuenta corriente inicial en 0
        cursor.execute("""
            INSERT INTO cuenta_corriente (id_cliente, saldo, fecha_de_actualizacion)
            VALUES (%s, 0.00, CURRENT_TIMESTAMP);
        """, (id_cli,))

        # 3. Crear su usuario asociado en la tabla usuario (id_rol = 2 -> CLIENTE, estado_usuario = false)
        cursor.execute("""
            INSERT INTO usuario (id_cliente, id_rol, nombre, apellido, email, contrasena_encriptada, estado_usuario)
            VALUES (%s, 2, %s, %s, %s, %s, false) RETURNING id_usuario;
        """, (id_cli, nombre_cont, apellido_cont, email, password))
        id_usr = cursor.fetchone()[0]

        conn.commit()
        return id_cli
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def auto_registrar_operario(nombre, apellido, email, password):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO usuario (id_rol, nombre, apellido, email, contrasena_encriptada, estado_usuario)
            VALUES (1, %s, %s, %s, %s, true) RETURNING id_usuario;
        """, (nombre, apellido, email, password))
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
               VALUES (%s, %s, CURRENT_DATE, 'EMITIDA') RETURNING id_factura;""",
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

def registrar_pago_cliente(cliente_id, id_factura, monto, medio_de_pago):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO pago (id_factura, monto, fecha, medio_de_pago) 
               VALUES (%s, %s, CURRENT_TIMESTAMP, %s);""",
            (id_factura, monto, medio_de_pago)
        )
        cursor.execute(
            """UPDATE cuenta_corriente 
               SET saldo = saldo - %s, fecha_de_actualizacion = CURRENT_TIMESTAMP 
               WHERE id_cliente = %s;""",
            (monto, cliente_id)
        )
        cursor.execute(
            "UPDATE factura SET estado_factura = 'PAGADA' WHERE id_factura = %s;",
            (id_factura,)
        )
        conn.commit()
        print(f"✅ Pago de ${monto} registrado exitosamente para la factura #{id_factura}.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al registrar pago: {e}")
    finally:
        cursor.close()
        conn.close()

def consultar_cuenta_corriente(cliente_id):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id_cuenta, saldo, fecha_de_actualizacion FROM cuenta_corriente WHERE id_cliente = %s;",
            (cliente_id,)
        )
        cuenta = cursor.fetchone()
        if cuenta:
            print(f"\n--- Estado de Cuenta Corriente ---")
            print(f"   - ID Cuenta: {cuenta[0]} | Saldo Actual: ${cuenta[1]} | Última Actualización: {cuenta[2]}")
        else:
            print("⚠️ No se encontró cuenta corriente para este cliente.")
            
        cursor.execute(
            "SELECT id_factura, importe_total, fecha_emision, estado_factura FROM factura WHERE id_cliente = %s ORDER BY id_factura ASC;",
            (cliente_id,)
        )
        facturas = cursor.fetchall()
        if facturas:
            print("\n   📄 Facturas asociadas:")
            for f in facturas:
                print(f"      Factura #{f[0]} | Importe: ${f[1]} | Fecha: {f[2]} | Estado: {f[3]}")
    except Exception as e:
        print(f"❌ Error al consultar cuenta: {e}")
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

def registrar_envio_con_contenedores_cliente(id_cliente, origen, destino, prioridad, lista_contenedores):
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Validar que el cliente esté ACTIVO
        cursor.execute("SELECT estado_cliente FROM cliente WHERE id_cliente = %s;", (id_cliente,))
        est = cursor.fetchone()
        if not est or est[0] != "ACTIVO":
            raise Exception(f"Tu cuenta está '{est[0] if est else 'INEXISTENTE'}'. Debe ser ACTIVA.")

        # 2. Crear el Envío (Administrativo)
        cursor.execute("""
            INSERT INTO envio (id_cliente, origen_envio, destino_envio, fecha_creacion, estado_envio, prioridad)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'EN_PREPARACION', %s) RETURNING id_envio;
        """, (id_cliente, origen, destino, prioridad))
        id_env = cursor.fetchone()[0]

        # 3. Iterar y crear todos los Contenedores vinculados a este id_envio
        for c in lista_contenedores:
            cursor.execute("""
                INSERT INTO contenedor (id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor)
                VALUES (%s, %s, %s, %s, 'EN_PREPARACION');
            """, (id_env, c['codigo'], c['tipo'], c['capacidad']))

        conn.commit()
        return id_env
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def abm_envio_contenedor_sensor_menu():
    while True:
        print("\n--- [ABM Envíos -> Contenedores -> Sensores] ---")
        print("1. Listar Envíos, Contenedores y Sensores")
        print("2. Asociar Sensor IoT a un Contenedor")
        print("3. Cambiar Estado de un Envío")
        print("4. Volver")
        
        try:
            op = input_seguro("Elegí una opción (1-4): ").strip()
        except KeyboardInterrupt:
            print("\n↩️ Volviendo...")
            break
        
        if op == "4":
            break
            
        conn = get_pg_connection()
        cursor = conn.cursor()
        try:
            if op == "1":
                cursor.execute("SELECT id_envio, id_cliente, origen_envio, destino_envio, estado_envio FROM envio ORDER BY id_envio ASC;")
                print("\n📦 Envíos:")
                for e in cursor.fetchall():
                    print(f"   Envío #{e[0]} | Cliente ID: {e[1]} | {e[2]} -> {e[3]} | Estado: {e[4]}")
                    
                cursor.execute("SELECT id_contenedor, id_envio, codigo_internacional, tipo_contenedor, capacidad, estado_contenedor FROM contenedor ORDER BY id_contenedor ASC;")
                print("\n🚛 Contenedores:")
                for c in cursor.fetchall():
                    print(f"   Contenedor #{c[0]} | Envío #{c[1]} | Cód: {c[2]} | Tipo: {c[3]} | Cap: {c[4]}kg | Estado: {c[5]}")
                    
                cursor.execute("SELECT id_sensor, id_contenedor, tipo_sensor, fabricante, estado_sensor FROM sensor_iot ORDER BY id_sensor ASC;")
                print("\n📡 Sensores IoT:")
                for s in cursor.fetchall():
                    estado_txt = "OPERATIVO" if s[4] else "INACTIVO"
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
                print("\n--- Cambiar Estado de un Envío ---")
                id_env = int(input_seguro("ID del Envío: "))
                print("Estados disponibles:")
                print("1. EN_PREPARACION")
                print("2. EN_TRANSITO")
                print("3. DEMORADO")
                print("4. ENTREGADO")
                
                est_op = input_seguro("Seleccioná el nuevo estado (1-4): ").strip()
                mapeo_estados = {
                    "1": "EN_PREPARACION",
                    "2": "EN_TRANSITO",
                    "3": "DEMORADO",
                    "4": "ENTREGADO"
                }
                nuevo_est = mapeo_estados.get(est_op, "EN_TRANSITO")
                
                # 1. Actualizar el estado del Envío (Administrativo)
                cursor.execute("UPDATE envio SET estado_envio = %s WHERE id_envio = %s;", (nuevo_est, id_env))
                
                # 2. Actualizar automáticamente los Contenedores asociados (Físicos)
                cursor.execute("UPDATE contenedor SET estado_contenedor = %s WHERE id_envio = %s;", (nuevo_est, id_env))
                
                conn.commit()
                print(f"✅ ¡Éxito! Envío #{id_env} y sus contenedores asociados se actualizaron a '{nuevo_est}'.")
                
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