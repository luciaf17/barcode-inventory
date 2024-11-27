from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import re
import logging
import socket
import math
import datetime
import hashlib
import sqlite3
from functools import wraps
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from fpdf import FPDF
import os



app = Flask(__name__, static_folder='static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app.secret_key = 'your_secret_key'  # Cambia esto a algo seguro en producción
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365*100)  # Dura 100 años

# Configuración de credenciales de Google Sheets y hojas
scopes = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
          "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_service_account_file('wouchuk-92244b5cccc1.json', scopes=scopes)
client = gspread.authorize(credentials)

sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').sheet1
depositos_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Deposito")
pasillos_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Pasillo")
columnas_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Columna")
estantes_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Estante")
interdeposito_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Interdeposito")
stock_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Stock")
usuarios_sheet = client.open_by_key('1GRtJhJitw1nY4U8ZcNDJozIeMU5yMa_0pfw4hCED-hk').worksheet("Usuarios")



def obtener_opciones(worksheet):
    return [row[0] for row in worksheet.get_all_values()]

import random

logger = logging.getLogger(__name__)

def obtener_datos_de_google(codigo):
    api_key = "AIzaSyCj_8KdMBBWdlCZwZUD59LbuXC0m-Qkbis"  # Reemplaza con tu clave de API
    search_engine_id = "c2fe79724f3994723"  # Reemplaza con el ID de tu motor de búsqueda

    url = f"https://www.googleapis.com/customsearch/v1?q={codigo}&key={api_key}&cx={search_engine_id}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        
        # Obtén el título del primer resultado
        if "items" in data and len(data["items"]) > 0:
            titulo = data["items"][0]["title"]
            # Limpia el título eliminando cualquier información extra después de ciertos caracteres
            titulo_texto = re.split(r' - | \(|\[|\{', titulo)[0].strip()
            titulo_texto = titulo_texto.capitalize()
            return titulo_texto
        else:
            return "Artículo no encontrado"
    else:
        print(f"Error en la búsqueda: {response.status_code}")
        return "Error en la búsqueda"

    
def verificar_descripcion_existente(descripcion):
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if fila[11].strip().lower() == descripcion.strip().lower():  # Compara por descripción
            return i + 1, fila  # Devuelve el índice de la fila y los datos existentes
    return None, None


def verificar_codigo_existente(codigo):
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if fila[1] == codigo:
            return i + 1, {
                "codigo_interno": fila[0],
                "codigo": fila[1],
                "descripcion": fila[11],
                "cantidad": fila[3],
                "deposito": fila[4],
                "pasillo": fila[5],
                "columna": fila[6],
                "estante": fila[7]
            }
    return None, None

@app.route('/verificar_producto', methods=['GET'])
def verificar_producto():
    codigo = request.args.get('code')
    fila, producto = verificar_codigo_existente(codigo)
    if producto:
        # Producto existente en la base de datos
        return jsonify({"producto": producto}), 200
    else:
        # Producto nuevo, obtener datos mediante scrapping
        descripcion = obtener_datos_de_google(codigo) or "Artículo no encontrado"
        return jsonify({"producto": {
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad": "",
            "deposito": "",
            "pasillo": "",
            "columna": "",
            "estante": ""
        }}), 200

# Agrega una función en tu backend para obtener los datos del último producto
def obtener_ultimo_producto():
    productos = sheet.get_all_records()  # Obtiene todos los registros
    if productos:
        ultimo_producto = productos[-1]  # Obtiene el último producto
        
        # Limpia el campo 'estante' si existe y comienza con un apóstrofe o comilla
        if "estante" in ultimo_producto:
            ultimo_producto["estante"] = str(ultimo_producto["estante"]).strip("'\"")
        
        return ultimo_producto
    return None


@app.route('/ingresar_datos')
def ingresar_datos():
    # Obtener opciones para los selects
    depositos = obtener_opciones(depositos_sheet)
    pasillos = obtener_opciones(pasillos_sheet)
    columnas = obtener_opciones(columnas_sheet)
    estantes = obtener_opciones(estantes_sheet)
    
    # Obtener el último producto
    ultimo_producto = obtener_ultimo_producto()

    return render_template(
        'form.html', 
        depositos=depositos, 
        pasillos=pasillos, 
        columnas=columnas, 
        estantes=estantes,
        ultimo_producto=ultimo_producto  # Pasar el último producto a la plantilla
    )

@app.route('/formulario_manual')
def formulario_manual():
    depositos = obtener_opciones(depositos_sheet)
    pasillos = obtener_opciones(pasillos_sheet)
    columnas = obtener_opciones(columnas_sheet)
    estantes = obtener_opciones(estantes_sheet)
    return render_template('form_manual.html', depositos=depositos, pasillos=pasillos, columnas=columnas, estantes=estantes)

@app.route('/eliminar_producto', methods=['DELETE'])
def eliminar_producto():
    codigo_interno = request.args.get('codigo_interno')

    if not codigo_interno:
        return jsonify({"success": False, "error": "Código interno no proporcionado."}), 400

    try:
        # Buscar el índice del producto en Google Sheets
        cell = sheet.find(codigo_interno, in_column=1)  # Supone que 'Codigo_interno' está en la primera columna
        if cell:
            sheet.delete_rows(cell.row)
            logger.info(f"Producto con Codigo_interno {codigo_interno} eliminado de Google Sheets.")
        else:
            logger.warning(f"Producto con Codigo_interno {codigo_interno} no encontrado en Google Sheets.")

        # Eliminar el producto en SQLite
        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM productos WHERE Codigo_interno = ?", (codigo_interno,))
        conn.commit()
        conn.close()
        logger.info(f"Producto con Codigo_interno {codigo_interno} eliminado de SQLite.")

        return jsonify({"success": True, "message": "Producto eliminado correctamente."}), 200
    except Exception as e:
        logger.error(f"Error al eliminar producto con Codigo_interno {codigo_interno}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/editar_producto', methods=['POST'])
def editar_producto():
    data = request.get_json()
    codigo_interno = data.get('codigo_interno')
    descripcion = data.get('descripcion')
    cantidad = data.get('cantidad')
    deposito = data.get('deposito')
    pasillo = data.get('pasillo')
    columna = data.get('columna')
    estante = data.get('estante')
    precio_cpa = data.get('precio_cpa')
    precio_vta = data.get('precio_vta')

    if not codigo_interno:
        return jsonify({"success": False, "error": "Código interno no proporcionado."}), 400

    try:
        # Buscar la fila en Google Sheets por código interno
        cell = sheet.find(codigo_interno, in_column=1)  # Buscar por Código Interno (Columna 1)
        if cell:
            row = cell.row

            # Actualizar cada columna específica para evitar sobrescribir fórmulas
            updates = [
                ("C", descripcion),  # Columna C: Descripción
                ("D", cantidad),     # Columna D: Cantidad
                ("E", deposito),     # Columna E: Depósito
                ("F", pasillo),      # Columna F: Pasillo
                ("G", columna),      # Columna G: Columna
                ("H", estante),      # Columna H: Estante
                ("O", precio_cpa),   # Columna O: Precio CPA
                ("P", precio_vta)    # Columna P: Precio VTA
            ]

            # Realizar actualizaciones específicas
            for col, value in updates:
                if value is not None:
                    # Los valores deben ser una lista de listas para la API de Google Sheets
                    sheet.update(f"{col}{row}", [[value]])
            logger.info(f"Producto con Codigo_interno {codigo_interno} actualizado en Google Sheets.")
        else:
            logger.warning(f"Producto con Codigo_interno {codigo_interno} no encontrado en Google Sheets.")

        # Actualizar en SQLite
        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE productos
            SET Desc_Concatenada = ?, cantidad = ?, deposito = ?, pasillo = ?, columna = ?, estante = ?, precio_cpa = ?, precio_vta = ?
            WHERE Codigo_interno = ?
        """, (descripcion, cantidad, deposito, pasillo, columna, estante, precio_cpa, precio_vta, codigo_interno))
        conn.commit()
        conn.close()
        logger.info(f"Producto con Codigo_interno {codigo_interno} actualizado en SQLite.")

        return jsonify({"success": True, "message": "Producto actualizado correctamente."}), 200
    except Exception as e:
        logger.error(f"Error al actualizar producto con Codigo_interno {codigo_interno}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/buscar_productos')
def buscar_productos():
    # Conexión a la base de datos local
    conn = sqlite3.connect('ferreteria.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    page = request.args.get('page', 1, type=int)
    per_page = 25
    search_codigo = str(request.args.get('search_codigo', '')).strip().lower()
    search_descripcion = str(request.args.get('search_descripcion', '')).strip().lower()
    filtro_deposito = str(request.args.get('filtro_deposito', '')).strip().lower()
    filtro_pasillo = str(request.args.get('filtro_pasillo', '')).strip().lower()
    filtro_columna = str(request.args.get('filtro_columna', '')).strip().lower()
    filtro_estante = str(request.args.get('filtro_estante', '')).strip().lower()

    # Construir la consulta SQL con filtros dinámicos
    query = "SELECT * FROM productos WHERE 1=1"
    params = {}

    if search_codigo:
        query += " AND LOWER(Codigo) LIKE :search_codigo"
        params['search_codigo'] = f"%{search_codigo}%"
    
    if search_descripcion:
        keywords = search_descripcion.split()
        for i, keyword in enumerate(keywords):
            query += f" AND LOWER(Desc_Concatenada) LIKE :keyword_{i}"
            params[f'keyword_{i}'] = f"%{keyword}%"
    
    if filtro_deposito:
        query += " AND LOWER(deposito) = :filtro_deposito"
        params['filtro_deposito'] = filtro_deposito
    
    if filtro_pasillo:
        query += " AND LOWER(pasillo) = :filtro_pasillo"
        params['filtro_pasillo'] = filtro_pasillo
    
    if filtro_columna:
        query += " AND LOWER(columna) = :filtro_columna"
        params['filtro_columna'] = filtro_columna
    
    if filtro_estante:
        query += " AND LOWER(estante) = :filtro_estante"
        params['filtro_estante'] = filtro_estante

    # Obtener la cantidad total de productos después del filtrado
    total_products = cursor.execute(query, params).fetchall()
    total_pages = math.ceil(len(total_products) / per_page)

    # Agregar paginación
    query += " LIMIT :limit OFFSET :offset"
    params['limit'] = per_page
    params['offset'] = (page - 1) * per_page

    productos_paginados = cursor.execute(query, params).fetchall()

    # Calcular rangos de paginación
    start_page = max(page - 8, 1)
    end_page = min(page + 8, total_pages)

    productos = [
        {
            "Codigo_interno": producto["Codigo_interno"],
            "Codigo": producto["Codigo"],
            "descripcion": producto["Desc_Concatenada"],
            "cantidad": producto["cantidad"],
            "deposito": producto["deposito"],
            "pasillo": producto["pasillo"],
            "columna": producto["columna"],
            "estante": producto["estante"],
            "precio_cpa": producto["precio_cpa"],
            "precio_vta": producto["precio_vta"]
        }
        for producto in productos_paginados
    ]

    # Obtener opciones para los filtros
    depositos = [row[0] for row in cursor.execute("SELECT DISTINCT deposito FROM productos WHERE deposito IS NOT NULL AND TRIM(deposito) != ''").fetchall()]
    pasillos = [row[0] for row in cursor.execute("SELECT DISTINCT pasillo FROM productos WHERE pasillo IS NOT NULL AND TRIM(pasillo) != ''").fetchall()]
    columnas = [row[0] for row in cursor.execute("SELECT DISTINCT columna FROM productos WHERE columna IS NOT NULL AND TRIM(columna) != ''").fetchall()]
    estantes = [row[0] for row in cursor.execute("SELECT DISTINCT estante FROM productos WHERE estante IS NOT NULL AND TRIM(estante) != ''").fetchall()]

    conn.close()

    return render_template(
        'buscar_productos.html',
        productos=productos,
        depositos=depositos,
        pasillos=pasillos,
        columnas=columnas,
        estantes=estantes,
        page=page,
        total_pages=total_pages,
        search_codigo=search_codigo,
        start_page=start_page,
        end_page=end_page,
        search_descripcion=search_descripcion,
        filtro_deposito=filtro_deposito,
        filtro_pasillo=filtro_pasillo,
        filtro_columna=filtro_columna,
        filtro_estante=filtro_estante
    )


def obtener_datos_producto(codigo):
    """
    Busca los datos de un producto en la base de datos local SQLite.
    
    Args:
        codigo (str): El código del producto a buscar.
    
    Returns:
        tuple: (Codigo_interno, Codigo, Desc_Concatenada) si se encuentra el producto,
               o (None, None, None) si no se encuentra.
    """
    import sqlite3

    # Conexión a la base de datos local
    conn = sqlite3.connect('ferreteria.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ejecutar la consulta para buscar el producto por su código
    query = "SELECT Codigo_interno, Codigo, Desc_Concatenada FROM productos WHERE Codigo = ?"
    cursor.execute(query, (codigo,))
    producto = cursor.fetchone()

    conn.close()

    if producto:
        return producto["Codigo_interno"], producto["Codigo"], producto["Desc_Concatenada"]
    return None, None, None


@app.route('/interdeposito_manual')
def interdeposito_manual():
    codigo_interno = request.args.get('codigo_interno')
    print("Código interno recibido en /interdeposito_manual:", codigo_interno)

    if not codigo_interno:
        return "Código interno no encontrado en la solicitud", 400
    
    producto = next((p for p in sheet.get_all_records() if str(p.get("Codigo_interno")) == str(codigo_interno)), None)
    
    if producto is None:
        return "El producto no está registrado en la hoja de productos", 404

    descripcion = producto.get("Desc Concatenada", "")
    codigo = producto.get("Codigo", "")
    depositos = obtener_opciones(depositos_sheet)

    return render_template('interdeposito.html', 
                           codigo=codigo, 
                           codigo_interno=codigo_interno, 
                           descripcion=descripcion, 
                           depositos=depositos)

@app.route('/agregar', methods=['POST'])
def agregar_codigo():
    data = request.get_json()
    codigo = data.get('code')
    cantidad = data.get('cantidad')
    deposito = data.get('deposito')
    pasillo = data.get('pasillo')
    columna = data.get('columna')
    estante = data.get('estante')
    descripcion = data.get('descripcion')

    if not codigo:
        return jsonify({"error": "Se requiere un código"}), 400

    fila, producto_existente = verificar_codigo_existente(codigo)
    if fila:
        descripcion_actualizada = producto_existente.get("descripcion", "Artículo no encontrado") if not descripcion else descripcion
        try:
            sheet.update(f"B{fila}:H{fila}", [[codigo, descripcion_actualizada, cantidad, deposito, pasillo, columna, estante]])
            return jsonify({"message": "Producto existente actualizado con éxito"}), 200
        except Exception as e:
            logger.error(f"Error al actualizar en Google Sheets: {e}")
            return jsonify({"error": "Error al actualizar en Google Sheets"}), 500
    else:
        rows = sheet.get_all_values()
        if len(rows) > 1:
            max_codigo_interno = max(int(row[0]) for row in rows[1:] if row[0].isdigit())
        else:
            max_codigo_interno = 0
        nuevo_codigo_interno = max_codigo_interno + 1

        titulo = descripcion if descripcion else obtener_datos_de_google(codigo) or "Artículo no encontrado"
        
        try:
            sheet.append_row([nuevo_codigo_interno, codigo, titulo, cantidad, deposito, pasillo, columna, estante])
            return jsonify({"message": "Producto nuevo agregado con éxito", "request_description": titulo == "Artículo no encontrado"}), 200
        except Exception as e:
            logger.error(f"Error al escribir en Google Sheets: {e}")
            return jsonify({"error": "Error al escribir en Google Sheets"}), 500

@app.route('/agregar_manual', methods=['POST'])
def agregar_manual():
    data = request.get_json()
    descripcion = data.get('descripcion')
    cantidad = data.get('cantidad')
    deposito = data.get('deposito')
    pasillo = data.get('pasillo')
    columna = data.get('columna')
    estante = data.get('estante')

    if not descripcion:
        return jsonify({"error": "Se requiere una descripción"}), 400

    fila, producto_existente = verificar_descripcion_existente(descripcion)
    
    if fila:
        try:
            sheet.update(f"C{fila}:H{fila}", [[descripcion, cantidad, deposito, pasillo, columna, estante]])
            return jsonify({"message": "Producto existente actualizado con éxito"}), 200
        except Exception as e:
            logger.error(f"Error al actualizar Google Sheets: {e}")
            return jsonify({"error": "Error al actualizar en Google Sheets"}), 500
    else:
        rows = sheet.get_all_values()
        if len(rows) > 1:
            max_codigo_interno = max(int(row[0]) for row in rows[1:] if row[0].isdigit())
        else:
            max_codigo_interno = 0
        nuevo_codigo_interno = max_codigo_interno + 1

        try:
            sheet.append_row([nuevo_codigo_interno, "", descripcion, cantidad, deposito, pasillo, columna, estante])
            return jsonify({"message": "Producto nuevo agregado con éxito"}), 200
        except Exception as e:
            logger.error(f"Error al escribir en Google Sheets: {e}")
            return jsonify({"error": "Error al escribir en Google Sheets"}), 500
        

@app.route('/opciones')
def opciones():
    codigo = request.args.get('code')
    print("Código recibido en /opciones:", codigo)  # Esto imprimirá el código en la consola
    
    if not codigo:
        return "Código no encontrado", 400
    
    return render_template('opciones.html', codigo=codigo)




# Ruta para el formulario de Interdeposito
@app.route('/interdeposito')
def interdeposito():
    codigo = request.args.get('code')  # Captura el código desde la URL
    print("Código recibido en /interdeposito:", codigo)  # Verificar en consola
    
    if not codigo:
        return "Código no encontrado en la solicitud", 400
    
    # Buscar el producto en la hoja de Productos
    codigo_interno, codigo, descripcion = obtener_datos_producto(codigo)
    
    
    depositos = obtener_opciones(depositos_sheet)  # Opciones para el dropdown de depósitos

    return render_template('interdeposito.html', 
                           codigo=codigo, 
                           codigo_interno=codigo_interno, 
                           descripcion=descripcion, 
                           depositos=depositos)

@app.route('/remito_interdeposito')
def remito_interdeposito():
    """Renderiza el formulario para remito interdepósito."""
    return render_template('remito_interdeposito.html')

@app.route('/buscar_producto_interdeposito', methods=['GET'])
def buscar_producto_interdeposito():
    """Busca productos por código o descripción en la base de datos, permitiendo palabras clave."""
    query = request.args.get('query', '').lower()

    if not query or len(query) < 2:
        return jsonify({"success": False, "error": "Debe ingresar al menos 2 caracteres."}), 400

    conn = sqlite3.connect("ferreteria.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Dividir la consulta en palabras clave
        keywords = query.split()

        # Construir una consulta dinámica para buscar cada palabra clave
        conditions = " AND ".join(
            f"(LOWER(Codigo) LIKE ? OR LOWER(Desc_Concatenada) LIKE ?)"
            for _ in keywords
        )
        params = [f"%{kw}%" for kw in keywords for _ in range(2)]  # Duplicar para `Codigo` y `Desc_Concatenada`

        # Consulta SQL dinámica
        query_sql = f"""
            SELECT Codigo_interno, Codigo, Desc_Concatenada AS descripcion, deposito 
            FROM productos 
            WHERE {conditions}
        """
        cursor.execute(query_sql, params)
        productos = cursor.fetchall()

        # Convertir los resultados a un formato JSON
        resultados = [
            {
                "codigo_interno": producto["Codigo_interno"],
                "codigo": producto["Codigo"],
                "descripcion": producto["descripcion"],
                "deposito_origen": producto["deposito"]
            }
            for producto in productos
        ]

        return jsonify({"success": True, "productos": resultados})
    except Exception as e:
        logger.error(f"Error al buscar productos: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# Ruta para cargar un remito existente
@app.route('/cargar_remito', methods=['GET'])
def cargar_remito():
    numero = request.args.get('numero')
    if not numero:
        return jsonify({"success": False, "error": "Debe proporcionar un número de remito."}), 400

    try:
        rows = interdeposito_sheet.get_all_values()
        productos = [
            {
                "codigo_interno": row[1],
                "codigo": row[2],
                "descripcion": row[3],
                "deposito_origen": row[4],
                "deposito_destino": row[5],
                "cantidad": row[6],
            }
            for row in rows if row[9] == numero.zfill(6)
        ]

        if not productos:
            return jsonify({"success": False, "error": f"No se encontró el remito #{numero}."})

        return jsonify({"success": True, "productos": productos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/guardar_interdeposito', methods=['POST'])
def guardar_interdeposito():
    """Guarda o actualiza un remito interdepósito y genera el PDF."""
    data = request.get_json()
    productos = data.get('productos', [])
    numero_remito = data.get('numero')  # Número asociado del remito

    if len(productos) > 19:
        return jsonify({"success": False, "error": "No puedes agregar más de 19 productos."}), 400

    try:
        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()

        if numero_remito:  # Si se proporciona un número, editar
            rows = interdeposito_sheet.get_all_values()
            indices = [i + 1 for i, row in enumerate(rows) if row[9] == numero_remito.zfill(6)]
            for index in reversed(indices):
                interdeposito_sheet.delete_rows(index)

            # Eliminar también de la base de datos
            cursor.execute("DELETE FROM interdeposito WHERE numero_remito = ?", (numero_remito,))
        else:  # Generar nuevo número
            rows = interdeposito_sheet.get_all_values()
            ultimo_nro_asociado = max([int(row[9]) for row in rows[1:]]) if len(rows) > 1 else 0
            numero_remito = str(ultimo_nro_asociado + 1).zfill(6)

        # Guardar productos en Google Sheets y en la base de datos
        for producto in productos:
            # Insertar en Google Sheets
            interdeposito_sheet.append_row([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                producto['codigo_interno'],
                producto['codigo'],
                producto['descripcion'],
                producto['deposito_origen'],
                producto['deposito_destino'],
                producto['cantidad'],
                "",
                "Remito Interno",
                numero_remito
            ])

            # Insertar en la base de datos
            cursor.execute("""
                INSERT INTO interdeposito (
                    fecha, codigo_interno, codigo, descripcion,
                    deposito_origen, deposito_destino, cantidad, tipo, numero_remito
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                producto['codigo_interno'],
                producto['codigo'],
                producto['descripcion'],
                producto['deposito_origen'],
                producto['deposito_destino'],
                producto['cantidad'],
                "Remito Interno",
                numero_remito
            ))

        conn.commit()

        # Generar PDF
        fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf_file = generar_pdf_remito(productos, numero_remito, fecha_actual)

        return jsonify({"success": True, "pdf_file": pdf_file, "numero_remito": numero_remito})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        conn.close()


def generar_pdf_remito(productos, nro_remito, fecha):
    import os
    from math import ceil

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Registrar fuentes DejaVu con variantes
    pdf.add_font('DejaVu', '', 'static/fonts/DejaVuSansCondensed.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'static/fonts/DejaVuSansCondensed-Bold.ttf', uni=True)

    # Encabezado
    logo_path = "static/wouchuk-logo.png"
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(200, 10, f"Remito Interdepósito - #{nro_remito}", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font('DejaVu', '', 10)
    pdf.cell(200, 10, f"Fecha: {fecha}", ln=True, align="R")
    pdf.ln(10)

    # Configuración de la tabla
    pdf.set_fill_color(0, 150, 0)  # Verde del encabezado
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('DejaVu', 'B', 8)

    ancho_total_pagina = 190  # A4 menos márgenes
    ancho_total_tabla = 170  # Ancho total de la tabla
    margen_izquierdo = (ancho_total_pagina - ancho_total_tabla) / 2

    pdf.set_x(margen_izquierdo)  # Centrar la tabla

    # Encabezados
    pdf.cell(15, 10, "ID", border=1, align="C", fill=True)
    pdf.cell(35, 10, "Barcode", border=1, align="C", fill=True)
    pdf.cell(60, 10, "Descripción", border=1, align="C", fill=True)
    pdf.cell(20, 10, "D.Origen", border=1, align="C", fill=True)
    pdf.cell(20, 10, "D.Destino", border=1, align="C", fill=True)
    pdf.cell(20, 10, "Cantidad", border=1, align="C", fill=True)
    pdf.ln()

    # Filas de la tabla
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('DejaVu', '', 8)

    for producto in productos:
        pdf.set_x(margen_izquierdo)

        # Calcular altura para la descripción (máximo de líneas necesarias)
        max_lineas = ceil(pdf.get_string_width(producto['descripcion']) / 60)  # Ajusta el divisor según el ancho de la celda
        altura_fila = max_lineas * 5  # Altura de cada línea

        # Celda para ID
        pdf.cell(15, altura_fila, producto['codigo_interno'], border=1, align="C")
        # Celda para Barcode
        pdf.cell(35, altura_fila, producto['codigo'], border=1, align="C")
        
        # Celda para descripción como multi_cell
        x, y = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(60, 5, producto['descripcion'], border=1, align="L")
        pdf.set_xy(x + 60, y)  # Ajustar la posición después de multi_cell

        # Celdas para los depósitos y cantidad
        pdf.cell(20, altura_fila, producto['deposito_origen'], border=1, align="C")
        pdf.cell(20, altura_fila, producto['deposito_destino'], border=1, align="C")
        pdf.cell(20, altura_fila, str(producto['cantidad']), border=1, align="C")
        pdf.ln()

    # Guardar PDF
    pdf_dir = "static/remitos"
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)

    pdf_path = os.path.join(pdf_dir, f"remito_{nro_remito}.pdf")
    pdf.output(pdf_path)

    return f"remitos/remito_{nro_remito}.pdf"




@app.route('/obtener_numero_remito', methods=['GET'])
def obtener_numero_remito():
    """Obtiene el próximo número de remito disponible basado en el mayor número actual."""
    try:
        rows = interdeposito_sheet.get_all_values()
        # Extraer los valores de la columna del número de remito (columna 10, índice 9)
        numeros_remitos = [int(row[9]) for row in rows[1:] if row[9].isdigit()]
        
        # Encontrar el mayor número de remito
        max_nro_remito = max(numeros_remitos) if numeros_remitos else 0
        
        # Generar el próximo número
        nuevo_nro_remito = str(max_nro_remito + 1).zfill(6)
        return jsonify({"success": True, "numero_remito": nuevo_nro_remito})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})



@app.route('/obtener_depositos', methods=['GET'])
def obtener_depositos():
    """Obtiene la lista de depósitos desde la hoja Deposito."""
    try:
        depositos = [row[0] for row in depositos_sheet.get_all_values() if row[0].strip()]
        return jsonify({"success": True, "depositos": depositos})
    except Exception as e:
        logger.error(f"Error al obtener depósitos: {e}")
        return jsonify({"success": False, "error": str(e)})
    

# Función para obtener los usuarios desde la hoja
def obtener_usuarios():
    usuarios = usuarios_sheet.get_all_records()
    return {user['Username']: user['Password'] for user in usuarios}

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Captura la URL original completa desde donde se solicitó el login
    next_url = request.args.get('next') or request.referrer  # Usa 'next' o, si no, la URL de referencia

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuarios = obtener_usuarios()  # Diccionario de usuarios con contraseñas hasheadas

        if username in usuarios and check_password_hash(usuarios[username], password):
            session['username'] = username  # Establecer el nombre de usuario en la sesión
            session.permanent = True

            # Redirige a la URL original (con parámetros) o al índice
            return redirect(next_url or url_for('index'))
        else:
            # Muestra mensaje de error si las credenciales no son correctas
            return render_template('login.html', error_message="Credenciales incorrectas", next=next_url)
    
    # Renderiza la página de login y pasa la URL original al formulario
    return render_template('login.html', next=next_url)


# Ruta de cierre de sesión
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


# Ruta principal protegida
@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
