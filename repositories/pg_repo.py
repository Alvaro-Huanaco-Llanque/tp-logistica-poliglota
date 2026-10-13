from config.database import get_pg_connection

def crear_factura_y_actualizar_saldo(cliente_id, envio_id, numero_factura, monto):
    """Genera una factura y actualiza la cuenta corriente del cliente en una transacción atómica (ACID)."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        # 1. Insertar la factura
        cursor.execute(
            """
            INSERT INTO facturas (numero_factura, cliente_id, envio_id, monto_total, fecha_vencimiento) 
            VALUES (%s, %s, %s, %s, CURRENT_DATE + INTERVAL '30 days') 
            RETURNING id
            """,
            (numero_factura, cliente_id, envio_id, monto)
        )
        factura_id = cursor.fetchone()[0]

        # 2. Actualizar el saldo de la cuenta corriente del cliente
        cursor.execute(
            """
            UPDATE cuentas_corrientes 
            SET saldo_actual = saldo_actual + %s, ultima_actualizacion = CURRENT_TIMESTAMP 
            WHERE cliente_id = %s
            """,
            (monto, cliente_id)
        )
        
        # Confirmar transacción completa
        conn.commit()
        return factura_id
    except Exception as e:
        # Si algo falla, se revierte todo (Rollback)
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()