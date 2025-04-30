import sqlite3

# Crear la base de datos alimentos.db si no existe
def crear_base_de_datos():
    conn = sqlite3.connect('alimentos.db')
    cursor = conn.cursor()

    # Crear la tabla de alimentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            calorias REAL,
            carbohidratos REAL,
            proteinas REAL,
            grasas REAL
        )
    ''')

    conn.commit()
    conn.close()

# Llamamos a la función para crear la base de datos
crear_base_de_datos()
