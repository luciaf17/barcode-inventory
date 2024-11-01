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
from functools import wraps
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__, static_folder='static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app.secret_key = 'your_secret_key'  # Cambia esto a algo seguro en producción
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Establece el tiempo de sesión (ejemplo: 30 minutos)

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

# Definir el decorador login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def obtener_opciones(worksheet):
    return [row[0] for row in worksheet.get_all_values()]

def obtener_datos_de_google(codigo):
    url = f"https://www.google.com/search?q={codigo}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        titulo = soup.find('h3')
        titulo_texto = titulo.text if titulo else None
        if titulo_texto:
            titulo_texto = re.split(r' - | \(|\[|\{', titulo_texto)[0].strip()
            titulo_texto = titulo_texto.capitalize()
        return titulo_texto
    else:
        return None
    
def verificar_descripcion_existente(descripcion):
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if fila[2].strip().lower() == descripcion.strip().lower():  # Compara por descripción
            return i + 1, fila  # Devuelve el índice de la fila y los datos existentes
    return None, None


def verificar_codigo_existente(codigo):
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if fila[1] == codigo:
            return i + 1, {
                "codigo_interno": fila[0],
                "codigo": fila[1],
                "descripcion": fila[2],
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

@app.route('/ingresar_datos')
@login_required
def ingresar_datos():
    depositos = obtener_opciones(depositos_sheet)
    pasillos = obtener_opciones(pasillos_sheet)
    columnas = obtener_opciones(columnas_sheet)
    estantes = obtener_opciones(estantes_sheet)
    return render_template('form.html', depositos=depositos, pasillos=pasillos, columnas=columnas, estantes=estantes)


@app.route('/formulario_manual')
@login_required
def formulario_manual():
    depositos = obtener_opciones(depositos_sheet)
    pasillos = obtener_opciones(pasillos_sheet)
    columnas = obtener_opciones(columnas_sheet)
    estantes = obtener_opciones(estantes_sheet)
    return render_template('form_manual.html', depositos=depositos, pasillos=pasillos, columnas=columnas, estantes=estantes)

@app.route('/eliminar_producto', methods=['DELETE'])
def eliminar_producto():
    codigo_interno = request.args.get('codigo_interno')
    
    # Buscar el índice del producto a eliminar
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if str(fila[0]) == str(codigo_interno):  # Comparar con código interno
            try:
                sheet.delete_rows(i + 1)  # Google Sheets usa índices basados en 1
                return jsonify({"success": True}), 200
            except Exception as e:
                logger.error(f"Error al eliminar en Google Sheets: {e}")
                return jsonify({"success": False, "error": "Error al eliminar en Google Sheets"}), 500

    return jsonify({"success": False, "error": "Producto no encontrado"}), 404

@app.route('/editar_producto', methods=['POST'])
@login_required
def editar_producto():
    data = request.get_json()
    codigo_interno = data.get('codigo_interno')
    descripcion = data.get('descripcion')
    cantidad = data.get('cantidad')
    deposito = data.get('deposito')
    pasillo = data.get('pasillo')
    columna = data.get('columna')
    estante = data.get('estante')

    # Buscar el índice del producto a actualizar
    celdas = sheet.get_all_values()
    for i, fila in enumerate(celdas):
        if str(fila[0]) == str(codigo_interno):  # Comparar con código interno
            try:
                # Actualizar en Google Sheets
                sheet.update(f"C{i+1}:H{i+1}", [[descripcion, cantidad, deposito, pasillo, columna, estante]])
                return jsonify({"success": True}), 200
            except Exception as e:
                logger.error(f"Error al actualizar en Google Sheets: {e}")
                return jsonify({"success": False, "error": "Error al actualizar en Google Sheets"}), 500

    return jsonify({"success": False, "error": "Producto no encontrado"}), 404

@app.route('/buscar_productos')
@login_required
def buscar_productos():
    page = request.args.get('page', 1, type=int)
    per_page = 25
    search_codigo = request.args.get('search_codigo', '').lower()
    search_descripcion = request.args.get('search_descripcion', '').lower()
    filtro_deposito = request.args.get('filtro_deposito', '')
    filtro_pasillo = request.args.get('filtro_pasillo', '')
    filtro_columna = request.args.get('filtro_columna', '')
    filtro_estante = request.args.get('filtro_estante', '')

    productos_raw = sheet.get_all_records()

    productos_filtrados = [
        producto for producto in productos_raw
        if (search_codigo in str(producto.get("Codigo", "")).lower()) and
           (search_descripcion in producto.get("Titulo", "").lower())
    ]

    # Aplicar filtros adicionales
    if filtro_deposito:
        productos_filtrados = [producto for producto in productos_filtrados if producto.get("deposito") == filtro_deposito]
    if filtro_pasillo:
        productos_filtrados = [producto for producto in productos_filtrados if producto.get("pasillo") == filtro_pasillo]
    if filtro_columna:
        productos_filtrados = [producto for producto in productos_filtrados if producto.get("columna") == filtro_columna]
    if filtro_estante:
        productos_filtrados = [producto for producto in productos_filtrados if producto.get("estante") == filtro_estante]

    total_products = len(productos_filtrados)
    total_pages = math.ceil(total_products / per_page)
    start = (page - 1) * per_page
    end = start + per_page
    productos_paginados = productos_filtrados[start:end]

    productos = [
        {
            "Codigo_interno": producto.get("Codigo_interno"),
            "Codigo": producto.get("Codigo"),
            "descripcion": producto.get("Titulo"),
            "cantidad": producto.get("cantidad"),
            "deposito": producto.get("deposito"),
            "pasillo": producto.get("pasillo"),
            "columna": producto.get("columna"),
            "estante": producto.get("estante")
        }
        for producto in productos_paginados
    ]

    depositos = obtener_opciones(depositos_sheet)
    pasillos = obtener_opciones(pasillos_sheet)
    columnas = obtener_opciones(columnas_sheet)
    estantes = obtener_opciones(estantes_sheet)

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
        search_descripcion=search_descripcion,
        filtro_deposito=filtro_deposito,
        filtro_pasillo=filtro_pasillo,
        filtro_columna=filtro_columna,
        filtro_estante=filtro_estante
    )

def obtener_datos_producto(codigo):
    celdas = sheet.get_all_records()
    for fila in celdas:
        if str(fila.get("Codigo")) == str(codigo):
            return fila.get("Codigo_interno"), fila.get("Codigo"), fila.get("Titulo")
    return None, None, None

@app.route('/buscar_producto_interdeposito')
def buscar_producto_interdeposito():
    query = request.args.get('query', '').lower()
    productos_raw = sheet.get_all_records()

    # Añade un print para depuración y revisar la estructura de productos_raw
    print("productos_raw:", productos_raw)

    # Filtrar productos que coincidan con la descripción
    productos = [
        {
            "codigo_interno": producto.get("Codigo_interno") or producto.get("codigo_interno"),
            "codigo": producto.get("Codigo") or producto.get("codigo"),
            "descripcion": producto.get("Titulo") or producto.get("titulo")
        }
        for producto in productos_raw if query in producto.get("Titulo", "").lower() or query in producto.get("titulo", "").lower()
    ]

    # Añade otro print para ver cómo se han estructurado los productos después del filtrado
    print("productos encontrados:", productos)

    return jsonify({"productos": productos})


@app.route('/interdeposito_manual')
@login_required
def interdeposito_manual():
    codigo_interno = request.args.get('codigo_interno')
    print("Código interno recibido en /interdeposito_manual:", codigo_interno)

    if not codigo_interno:
        return "Código interno no encontrado en la solicitud", 400
    
    producto = next((p for p in sheet.get_all_records() if str(p.get("Codigo_interno")) == str(codigo_interno)), None)
    
    if producto is None:
        return "El producto no está registrado en la hoja de productos", 404

    descripcion = producto.get("Titulo", "")
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
@login_required
def opciones():
    codigo = request.args.get('code')
    print("Código recibido en /opciones:", codigo)  # Esto imprimirá el código en la consola
    
    if not codigo:
        return "Código no encontrado", 400
    
    return render_template('opciones.html', codigo=codigo)




# Ruta para el formulario de Interdeposito
@app.route('/interdeposito')
@login_required
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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuarios = obtener_usuarios()  # Obteniendo usuarios desde la hoja de cálculo (diccionario con hashes)

        if username in usuarios and check_password_hash(usuarios[username], password):
            session['username'] = username  # Establecer el nombre de usuario en la sesión
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error_message="Credenciales incorrectas")
    return render_template('login.html')



# Ruta de cierre de sesión
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Decorador para proteger rutas que requieran autenticación
from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta principal protegida
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.before_request
def require_login():
    # Rutas que no necesitan autenticación
    allowed_routes = ['login', 'logout', 'static']
    if 'username' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login', next=request.url))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
