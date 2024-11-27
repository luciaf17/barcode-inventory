import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging
import time

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SincronizacionPeriodica")

# Configuración de Google Sheets
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

CREDENTIALS_FILE = "wouchuk-92244b5cccc1.json"  # Archivo de credenciales
SPREADSHEET_KEY = "1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk"  # ID de la hoja de Google Sheets

# Configuración de la base de datos SQLite
DB_FILE = "ferreteria.db"
TABLE_PRODUCTOS = "productos"
TABLE_CLIENTES = "clientes"

def sincronizar_productos():
    """Sincroniza los productos desde Google Sheets a SQLite verificando la columna de sincronización."""
    logger.info("Iniciando sincronización periódica de productos...")

    try:
        # Autorización y acceso a Google Sheets
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SPREADSHEET_KEY).sheet1

        # Conexión a la base de datos local
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            # Obtener los encabezados y datos de la hoja
            celdas = sheet.get_all_values()
            headers = celdas[0]  # Encabezados
            data = celdas[1:]    # Datos

            # Índices de las columnas relevantes
            index_sincronizado = headers.index("sincronizado")
            index_codigo_interno = headers.index("Codigo_interno")
            index_codigo = headers.index("Codigo")
            index_desc_concatenada = headers.index("Desc Concatenada")
            index_cantidad = headers.index("cantidad")
            index_deposito = headers.index("deposito")
            index_pasillo = headers.index("pasillo")
            index_columna = headers.index("columna")
            index_estante = headers.index("estante")
            index_precio_cpa = headers.index("precio_cpa")
            index_precio_vta = headers.index("precio_vta")

            filas_sincronizar = []

            # Filtrar filas que no están sincronizadas
            for i, fila in enumerate(data):
                sincronizado = fila[index_sincronizado].strip() if len(fila) > index_sincronizado else ""
                if not sincronizado:  # Solo procesar filas no sincronizadas
                    filas_sincronizar.append((i + 2, fila))  # Guardar índice real y datos

            # Procesar las filas para insertar o actualizar en SQLite
            for row_number, fila in filas_sincronizar:
                try:
                    cursor.execute(f"""
                        INSERT INTO {TABLE_PRODUCTOS} (Codigo_interno, Codigo, Desc_Concatenada, cantidad, deposito, pasillo, columna, estante, precio_cpa, precio_vta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(Codigo_interno) DO UPDATE SET
                            Codigo = excluded.Codigo,
                            Desc_Concatenada = excluded.Desc_Concatenada,
                            cantidad = excluded.cantidad,
                            deposito = excluded.deposito,
                            pasillo = excluded.pasillo,
                            columna = excluded.columna,
                            estante = excluded.estante,
                            precio_cpa = excluded.precio_cpa,
                            precio_vta = excluded.precio_vta
                    """, (
                        fila[index_codigo_interno],    # Codigo_interno
                        fila[index_codigo],           # Codigo
                        fila[index_desc_concatenada], # Desc Concatenada
                        fila[index_cantidad],         # cantidad
                        fila[index_deposito],         # deposito
                        fila[index_pasillo],          # pasillo
                        fila[index_columna],          # columna
                        fila[index_estante],          # estante
                        fila[index_precio_cpa],       # precio_cpa
                        fila[index_precio_vta]        # precio_vta
                    ))

                    # Marcar la fila como sincronizada en Google Sheets
                    sheet.update_cell(row_number, index_sincronizado + 1, "1")
                    logger.info(f"Producto con Codigo_interno {fila[index_codigo_interno]} sincronizado correctamente.")
                except sqlite3.IntegrityError as e:
                    logger.error(f"Error de integridad al insertar/actualizar producto: {e}")
                except Exception as e:
                    logger.error(f"Error al procesar fila {row_number}: {e}")

            # Confirmar cambios en SQLite
            conn.commit()
            logger.info("Sincronización periódica de productos completada.")
        except Exception as e:
            logger.error(f"Error al procesar los datos de Google Sheets: {e}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error en la sincronización periódica de productos: {e}")

def sincronizar_clientes():
    """Sincroniza los datos de clientes desde Google Sheets a SQLite."""
    logger.info("Iniciando sincronización periódica de clientes...")

    try:
        # Configuración de Google Sheets
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SPREADSHEET_KEY).worksheet("Clientes+Tipos")

        # Obtener encabezados
        headers = sheet.row_values(1)
        index_sincronizado = headers.index("sincronizado") + 1  # Índice basado en Google Sheets

        # Obtener datos de la hoja
        rows = sheet.get_all_values()[1:]  # Excluir encabezados
        data = [
            {
                "id_cliente": row[headers.index("ID_Cliente")],
                "nombre_cliente": row[headers.index("Nombre Cliente")],
                "sincronizado": row[index_sincronizado - 1] if len(row) > index_sincronizado - 1 else "",
                "row_number": i + 2  # Índice de fila en Google Sheets
            }
            for i, row in enumerate(rows)
        ]

        # Filtrar filas no sincronizadas
        filas_no_sincronizadas = [fila for fila in data if not fila["sincronizado"].strip()]

        # Conexión a SQLite
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Crear tabla `clientes` si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id_cliente INTEGER PRIMARY KEY,
                nombre_cliente TEXT
            )
        """)

        # Insertar o actualizar datos
        for fila in filas_no_sincronizadas:
            id_cliente = fila["id_cliente"]
            nombre_cliente = fila["nombre_cliente"]

            if id_cliente and nombre_cliente:
                cursor.execute("""
                    INSERT INTO clientes (id_cliente, nombre_cliente)
                    VALUES (?, ?)
                    ON CONFLICT(id_cliente) DO UPDATE SET
                    nombre_cliente = excluded.nombre_cliente
                """, (id_cliente, nombre_cliente))

                # Marcar la fila como sincronizada en Google Sheets
                sheet.update_cell(fila["row_number"], index_sincronizado, "1")
                logger.info(f"Cliente ID {id_cliente} sincronizado correctamente.")

        # Confirmar cambios en SQLite
        conn.commit()
        conn.close()

        logger.info("Sincronización de clientes completada.")
    except Exception as e:
        logger.error(f"Error al sincronizar clientes: {e}")


if __name__ == "__main__":
    try:
        sincronizar_productos()
        sincronizar_clientes()
    except Exception as e:
        logger.error(f"Error crítico durante la sincronización periódica: {e}")
