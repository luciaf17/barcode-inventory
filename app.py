from flask import Flask, request, jsonify, render_template, session, redirect, url_for
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

    if not codigo_interno:
        return jsonify({"success": False, "error": "Código interno no proporcionado."}), 400

    try:
        # Actualizar en Google Sheets
        cell = sheet.find(codigo_interno, in_column=1)  # Buscar por Código Interno (Columna 1)
        if cell:
            sheet.update(f"C{cell.row}:H{cell.row}", [[descripcion, cantidad, deposito, pasillo, columna, estante]])
            logger.info(f"Producto con Codigo_interno {codigo_interno} actualizado en Google Sheets.")
        else:
            logger.warning(f"Producto con Codigo_interno {codigo_interno} no encontrado en Google Sheets.")

        # Actualizar en SQLite
        conn = sqlite3.connect("ferreteria.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE productos
            SET Desc_Concatenada = ?, cantidad = ?, deposito = ?, pasillo = ?, columna = ?, estante = ?
            WHERE Codigo_interno = ?
        """, (descripcion, cantidad, deposito, pasillo, columna, estante, codigo_interno))
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
        # Dividir la descripción en palabras clave
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
            "estante": producto["estante"]
        }
        for producto in productos_paginados
    ]

    # Obtener opciones para los filtros
    depositos = [row[0] for row in cursor.execute("SELECT DISTINCT deposito FROM productos WHERE deposito IS NOT NULL").fetchall()]
    pasillos = [row[0] for row in cursor.execute("SELECT DISTINCT pasillo FROM productos WHERE pasillo IS NOT NULL").fetchall()]
    columnas = [row[0] for row in cursor.execute("SELECT DISTINCT columna FROM productos WHERE columna IS NOT NULL").fetchall()]
    estantes = [row[0] for row in cursor.execute("SELECT DISTINCT estante FROM productos WHERE estante IS NOT NULL").fetchall()]

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

@app.route('/buscar_producto_interdeposito')
def buscar_producto_interdeposito():
    query = request.args.get('query', '').lower()
    productos_raw = sheet.get_all_records()

    # Divide la consulta en palabras clave
    keywords = query.split()

    # Filtrar productos que coincidan con todas las palabras clave
    productos = [
        {
            "codigo_interno": producto.get("Codigo_interno") or producto.get("codigo_interno"),
            "codigo": producto.get("Codigo") or producto.get("codigo"),
            "descripcion": producto.get("Desc Concatenada") or producto.get("Desc Concatenada")
        }
        for producto in productos_raw
        if all(keyword in (producto.get("Desc Concatenada", "").lower() or producto.get("Desc Concatenada", "").lower()) for keyword in keywords)
    ]

    return jsonify({"productos": productos})



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

# Ruta para procesar y guardar el movimiento de Interdeposito
@app.route('/guardar_interdeposito', methods=['POST'])
def guardar_interdeposito():
    codigo = request.form.get('codigo')
    codigo_interno = request.form.get('codigo_interno')
    descripcion = request.form.get('descripcion')
    deposito_origen = request.form.get('deposito_origen')
    deposito_destino = request.form.get('deposito_destino')
    cantidad = int(request.form.get('cantidad'))
    observaciones = request.form.get('observaciones', '')
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar el registro en la hoja de "Interdeposito"
    try:
        interdeposito_sheet.append_row([fecha, codigo_interno, codigo, descripcion, deposito_origen, deposito_destino, cantidad, observaciones])
        return jsonify({"message": "Movimiento registrado con éxito"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al actualizar Google Sheets: {e}"}), 500

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
    
