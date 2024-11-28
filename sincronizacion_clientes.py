import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging

def sincronizar_clientes():
    """Sincroniza los clientes desde Google Sheets a la base de datos SQLite."""
    logger = logging.getLogger("SincronizacionClientes")
    logger.info("Iniciando sincronización de clientes...")
    
    try:
        # Configuración de Google Sheets
        credentials = Credentials.from_service_account_file("wouchuk-92244b5cccc1.json", scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(credentials)
        sheet = client.open_by_key("1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk").worksheet("Clientes+Tipos")

        # Obtener encabezados
        headers = sheet.row_values(1)
        index_sincronizado = headers.index("sincronizado") + 1

        rows = sheet.get_all_values()[1:]  # Excluir encabezados
        data = [
            {
                "id_cliente": row[headers.index("ID_Cliente")],
                "nombre_cliente": row[headers.index("Nombre Cliente")],
                "sincronizado": row[index_sincronizado],
                "row_number": i + 2
            }
            for i, row in enumerate(rows)
        ]

        # Filtrar filas no sincronizadas (sincronizado vacío)
        filas_no_sincronizadas = [fila for fila in data if not fila["sincronizado"].strip()]

        logger.info(f"Filas no sincronizadas: {len(filas_no_sincronizadas)}")

        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()

        for fila in filas_no_sincronizadas:
            id_cliente = fila["id_cliente"]
            nombre_cliente = fila["nombre_cliente"]

            # Depuración adicional: Verificar los valores de id_cliente y nombre_cliente
            logger.info(f"Verificando cliente: ID={id_cliente}, Nombre={nombre_cliente}")

            # Validación para asegurar que los valores sean correctos
            if not id_cliente or not nombre_cliente:
                logger.error(f"Cliente con ID {id_cliente} tiene datos incompletos. Saltando.")
                continue

            # Asegurarse de que el ID del cliente sea un número entero
            try:
                id_cliente = int(id_cliente)  # Convertir id_cliente a entero, si no es un número, se ignora
            except ValueError:
                logger.error(f"ID de cliente {id_cliente} no es un número válido. Saltando.")
                continue

            # Insertar o actualizar clientes
            cursor.execute("""
                INSERT INTO clientes (id_cliente, nombre_cliente)
                VALUES (?, ?)
                ON CONFLICT(id_cliente) DO UPDATE SET
                nombre_cliente = excluded.nombre_cliente
            """, (id_cliente, nombre_cliente))

            # Marcar la fila como sincronizada en Google Sheets
            sheet.update_cell(fila["row_number"], index_sincronizado, "1")
            logger.info(f"Cliente ID {id_cliente} sincronizado correctamente.")

        conn.commit()
        conn.close()

        logger.info("Sincronización de clientes completada.")
    except Exception as e:
        logger.error(f"Error al sincronizar clientes: {e}")
