import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging

def sincronizar_productos():
    """Sincroniza los productos desde Google Sheets a la base de datos SQLite."""
    logger = logging.getLogger("SincronizacionProductos")
    logger.info("Iniciando sincronización de productos...")
    
    try:
        credentials = Credentials.from_service_account_file("wouchuk-92244b5cccc1.json", scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(credentials)
        sheet = client.open_by_key("1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk").worksheet("Productos")  # Nombre de la hoja

        headers = sheet.row_values(1)
        index_sincronizado = headers.index("sincronizado") + 1

        rows = sheet.get_all_values()[1:]  # Excluir encabezados
        data = [
            {
                "Codigo_interno": row[headers.index("Codigo_interno")],
                "Codigo": row[headers.index("Codigo")],
                "Desc Concatenada": row[headers.index("Desc Concatenada")],
                "cantidad": row[headers.index("cantidad")],
                "deposito": row[headers.index("deposito")],
                "pasillo": row[headers.index("pasillo")],
                "columna": row[headers.index("columna")],
                "estante": row[headers.index("estante")],
                "precio_cpa": row[headers.index("precio_cpa")],
                "precio_vta": row[headers.index("precio_vta")],
                "sincronizado": row[index_sincronizado - 1],
                "row_number": i + 2  # Ajustar índice de fila para Google Sheets
            }
            for i, row in enumerate(rows)
        ]

        # Filtrar filas no sincronizadas
        filas_no_sincronizadas = [fila for fila in data if not fila["sincronizado"].strip()]

        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()

        for fila in filas_no_sincronizadas:
            cursor.execute("""
                INSERT INTO productos (Codigo_interno, Codigo, Desc_Concatenada, cantidad, deposito, pasillo, columna, estante, precio_cpa, precio_vta)
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
                fila["Codigo_interno"], fila["Codigo"], fila["Desc Concatenada"], fila["cantidad"],
                fila["deposito"], fila["pasillo"], fila["columna"], fila["estante"],
                fila["precio_cpa"], fila["precio_vta"]
            ))

            # Marcar la fila como sincronizada en Google Sheets
            sheet.update_cell(fila["row_number"], index_sincronizado, "1")
            logger.info(f"Producto {fila['Codigo_interno']} sincronizado correctamente.")

        conn.commit()
        conn.close()

        logger.info("Sincronización de productos completada.")
    except Exception as e:
        logger.error(f"Error al sincronizar productos: {e}")
