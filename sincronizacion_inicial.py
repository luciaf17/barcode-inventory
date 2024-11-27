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
BATCH_SIZE = 200  # Cantidad de filas que se procesarán por batch

def crear_tabla_local():
    """Crea las tablas SQLite si no existen."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Crear tabla principal para productos
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Codigo_interno INTEGER PRIMARY KEY,
            Codigo TEXT UNIQUE,
            Desc_Concatenada TEXT,
            cantidad INTEGER,
            deposito TEXT,
            pasillo TEXT,
            columna TEXT,
            estante TEXT,
            precio_cpa REAL DEFAULT 0.0,
            precio_vta REAL DEFAULT 0.0
        )
    """)

    # Crear tabla interdeposito
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interdeposito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            codigo_interno TEXT NOT NULL,
            codigo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            deposito_origen TEXT NOT NULL,
            deposito_destino TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'Remito Interno',
            numero_remito TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Tablas locales creadas o ya existen.")


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

    # Obtener encabezados
    headers = sheet.row_values(1)
    start_row = 2  # Inicio de los datos (omitir encabezados)
    total_rows = len(sheet.get_all_values()) - 1  # Excluir encabezados
    logger.info(f"Total de filas en Google Sheets: {total_rows}")

    while start_row <= total_rows + 1:
        logger.info(f"Procesando filas {start_row} a {start_row + BATCH_SIZE - 1}")
        rows = obtener_datos_sheet(sheet, start_row, BATCH_SIZE)
        if not rows:
            logger.info("No se encontraron más datos.")
            break

        # Filtrar columnas relevantes
        rows_filtradas = [
            (
                fila[headers.index("Codigo_interno")],
                fila[headers.index("Codigo")],
                fila[headers.index("Desc Concatenada")],
                fila[headers.index("cantidad")],
                fila[headers.index("deposito")],
                fila[headers.index("pasillo")],
                fila[headers.index("columna")],
                fila[headers.index("estante")],
                fila[headers.index("precio_cpa")],
                fila[headers.index("precio_vta")]
            )
            for fila in rows
        ]

        # Insertar en la base de datos local
        insertar_en_local(rows_filtradas)

        # Marcar filas como sincronizadas en Google Sheets
        for i, fila in enumerate(rows):
            row_number = start_row + i
            sheet.update_cell(row_number, headers.index("sincronizado") + 1, "1")
            logger.info(f"Fila {row_number} marcada como sincronizada.")

        start_row += BATCH_SIZE
        time.sleep(90)  # Evitar superar el límite de la API

    # Chequeo final para verificar si todas las filas están sincronizadas
    logger.info("Verificando sincronización final...")
    verificar_sincronizacion(sheet, headers)
    logger.info("Sincronización inicial completada.")


def verificar_sincronizacion(sheet, headers):
    """Verifica que todas las filas estén marcadas como sincronizadas."""
    data = sheet.get_all_values()[1:]  # Excluir encabezados
    index_sincronizado = headers.index("sincronizado")
    
    filas_no_sincronizadas = [
        (i + 2, fila)  # Índice de la fila en Google Sheets (sumar 2 para omitir encabezado)
        for i, fila in enumerate(data)
        if not fila[index_sincronizado].strip()  # Fila no sincronizada
    ]

    if filas_no_sincronizadas:
        logger.warning(f"Se encontraron {len(filas_no_sincronizadas)} filas no sincronizadas. Reintentando...")
        for row_number, fila in filas_no_sincronizadas:
            try:
                insertar_en_local([fila])
                sheet.update_cell(row_number, index_sincronizado + 1, "1")
                logger.info(f"Fila {row_number} sincronizada en el chequeo final.")
            except Exception as e:
                logger.error(f"Error al sincronizar fila {row_number}: {e}")
    else:
        logger.info("Todas las filas están correctamente sincronizadas.")

def sincronizar_clientes():
    """Sincroniza los datos de clientes desde Google Sheets a la tabla `clientes` en SQLite."""
    logger.info("Iniciando sincronización de clientes...")

    try:
        # Configuración de Google Sheets
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SPREADSHEET_KEY).worksheet("Clientes+Tipos")

        # Obtener encabezados
        headers = sheet.row_values(1)
        index_sincronizado = headers.index("sincronizado") + 1  # Ajustar a índice 1 basado en Google Sheets

        # Obtener datos de la hoja
        rows = sheet.get_all_values()[1:]  # Excluir encabezados
        data = [
            {
                "id_cliente": row[headers.index("ID_Cliente")],
                "nombre_cliente": row[headers.index("Nombre Cliente")],
                "sincronizado": row[index_sincronizado - 1] if len(row) > index_sincronizado - 1 else "",
                "row_number": i + 2  # Ajustar índice de fila para Google Sheets
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

        # Insertar o actualizar clientes
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
        sincronizar_inicial()
    except Exception as e:
        logger.error(f"Error crítico durante la sincronización inicial: {e}")

        
