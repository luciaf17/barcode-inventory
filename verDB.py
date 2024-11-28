import sqlite3

# Conecta a la base de datos
conn = sqlite3.connect("ferreteria.db")
cursor = conn.cursor()

# Ejecuta una consulta para obtener datos
cursor.execute("SELECT * FROM remito_ventas")

# Recupera los resultados
rows = cursor.fetchall()

# Imprime los datos
for row in rows:
    print(row)

# Cierra la conexión
conn.close()
