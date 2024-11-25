import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging

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
TABLE_NAME = "productos"

def sincronizar_periodica():
    """Sincroniza los productos desde Google Sheets a SQLite verificando la columna de sincronización."""
    logger.info("Iniciando sincronización periódica...")

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
                        INSERT INTO {TABLE_NAME} (Codigo_interno, Codigo, Desc_Concatenada, cantidad, deposito, pasillo, columna, estante)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(Codigo_interno) DO UPDATE SET
                            Codigo = excluded.Codigo,
                            Desc_Concatenada = excluded.Desc_Concatenada,
                            cantidad = excluded.cantidad,
                            deposito = excluded.deposito,
                            pasillo = excluded.pasillo,
                            columna = excluded.columna,
                            estante = excluded.estante
                    """, (
                        fila[index_codigo_interno],    # Codigo_interno
                        fila[index_codigo],           # Codigo
                        fila[index_desc_concatenada], # Desc Concatenada
                        fila[index_cantidad],         # cantidad
                        fila[index_deposito],         # deposito
                        fila[index_pasillo],          # pasillo
                        fila[index_columna],          # columna
                        fila[index_estante]           # estante
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
            logger.info("Sincronización periódica completada.")
        except Exception as e:
            logger.error(f"Error al procesar los datos de Google Sheets: {e}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error en la sincronización periódica: {e}")

