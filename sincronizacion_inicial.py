import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging
import time

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SincronizacionInicial")

# Configuración de Google Sheets
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

CREDENTIALS_FILE = "wouchuk-92244b5cccc1.json"  # Cambia esto al nombre de tu archivo JSON
SPREADSHEET_KEY = "1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk"  # Reemplaza con el ID de tu hoja de Google Sheets

# Configuración de la base de datos SQLite
DB_FILE = "ferreteria.db"
TABLE_NAME = "productos"
BATCH_SIZE = 299  # Cantidad de filas que se procesarán por batch

def crear_tabla_local():
    """Crea la tabla SQLite si no existe."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Codigo_interno INTEGER PRIMARY KEY,
            Codigo TEXT UNIQUE,
            Desc_Concatenada TEXT,
            cantidad INTEGER,
            deposito TEXT,
            pasillo TEXT,
            columna TEXT,
            estante TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Tabla local creada o ya existe.")

def obtener_datos_sheet(sheet, start_row, batch_size):
    """Obtiene datos en lotes desde Google Sheets."""
    try:
        # Ajustar el rango dinámicamente
        end_row = start_row + batch_size - 1
        rango = f"{start_row}:{end_row}"  # Rango dinámico para las filas
        
        # Obtener todas las filas en el rango especificado
        data = sheet.get(rango)
        
        # Obtener encabezados de la primera fila de la hoja
        headers = sheet.row_values(1)  # Encabezados desde la fila 1
        
        # Crear un diccionario mapeando encabezados a valores
        rows = [dict(zip(headers, row)) for row in data if row]  # Ignorar filas vacías
        
        return rows
    except Exception as e:
        logger.warning(f"Error al obtener datos desde Google Sheets: {e}")
        return []

def insertar_en_local(rows):
    """Inserta los datos obtenidos en la base de datos SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for row in rows:
        try:
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (Codigo_interno, Codigo, Desc_Concatenada, cantidad, deposito, pasillo, columna, estante)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(Codigo) DO NOTHING
            """, (
                row.get("Codigo_interno"),
                row.get("Codigo"),
                row.get("Desc Concatenada"),
                row.get("cantidad"),
                row.get("deposito"),
                row.get("pasillo"),
                row.get("columna"),
                row.get("estante")
            ))
        except Exception as e:
            logger.error(f"Error al insertar fila {row}: {e}")
    conn.commit()
    conn.close()

def sincronizar_inicial():
    """Sincroniza todos los datos desde Google Sheets a la base de datos SQLite."""
    logger.info("Iniciando sincronización inicial...")
    
    # Configuración de Google Sheets
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_KEY).sheet1

    crear_tabla_local()

    start_row = 2  # Inicio de los datos (omitir encabezados)
    total_rows = len(sheet.get_all_values()) - 1  # Excluir encabezados
    logger.info(f"Total de filas en Google Sheets: {total_rows}")

    while start_row <= total_rows + 1:
        logger.info(f"Procesando filas {start_row} a {start_row + BATCH_SIZE - 1}")
        rows = obtener_datos_sheet(sheet, start_row, BATCH_SIZE)
        if not rows:
            logger.info("No se encontraron más datos.")
            break
        insertar_en_local(rows)
        start_row += BATCH_SIZE
        time.sleep(70)  # Evitar superar el límite de la API

    logger.info("Sincronización inicial completada.")


if __name__ == "__main__":
    try:
        sincronizar_inicial()
    except Exception as e:
        logger.error(f"Error crítico durante la sincronización inicial: {e}")
