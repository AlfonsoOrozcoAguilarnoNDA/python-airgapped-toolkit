# Cheat Sheet: Equivalencias de Sintaxis (C# / PHP → Python)
### Control de Registro Interno: C:\aoa\documentacion\JT-001-SINTAXIS.md

Este documento sirve como referencia rápida de mapeo lógico para el desarrollo en el entorno local con Python 3 y Flask, tomando como base la experiencia previa en arquitecturas C# (.NET) y PHP.

---

## 1. Estructuras de Datos Fundamentales

### Arreglos Asociativos / Diccionarios
* **PHP:** `$usuario = ["id" => 1, "nombre" => "Alfonso"];`
* **C#:** `var usuario = new Dictionary<string, object> { {"id", 1}, {"nombre", "Alfonso"} };`
* **Python:** 
```python
usuario = {"id": 1, "nombre": "Alfonso"}
# Acceso: usuario["nombre"]
# Agregar: usuario["rol"] = "admin"
```

### Listas / Arreglos Indexados
* **PHP:** `$frutas = ["manzana", "pera"];`
* **C#:** `var frutas = new List<string> { "manzana", "pera" };`
* **Python:** 
```python
frutas = ["manzana", "pera"]
# Agregar: frutas.append("plátano")
# Acceso: frutas[0]
```

---

## 2. Estructuras de Control e Indentación
*Nota crítica: En Python no existen las llaves `{}` para bloques de código ni el punto y coma `;` al final de las líneas. Todo se rige por la indentación (4 espacios).*

### Bucles (Foreach)
* **PHP:** `foreach ($frutas as $fruta) { ... }`
* **C#:** `foreach (var fruta in frutas) { ... }`
* **Python:**
```python
for fruta in frutas:
    print(fruta)  # Bloque indentado
```

### Condicionales
* **PHP / C#:** `if (X) { ... } else if (Y) { ... } else { ... }`
* **Python:**
```python
if x > 10:
    print("Mayor")
elif x == 10:  # En lugar de else if
    print("Igual")
else:
    print("Menor")
```

---

## 3. Operaciones Comunes y Strings

### Concatenación e Interpolación (F-Strings)
* **PHP:** `"Hola " . $nombre;` o `"Hola $nombre";`
* **C#:** `$"Hola {nombre}";`
* **Python:**
```python
# F-Strings (Equivalente al $"" de C#)
mensaje = f"Hola {nombre}, tu ID es {usuario['id']}"
```

### Manejo de Valores Nulos
* **PHP:** `null`
* **C#:** `null`
* **Python:** `None` (Con la primera letra mayúscula)
```python
variable = None
if variable is None:
    print("Es nulo")
```

---

## 4. Control de Excepciones y Conectividad (MySQL)

### Bloques Try/Catch
* **PHP / C#:** `try { ... } catch (Exception $e) { ... }`
* **Python:**
```python
try:
    # Código que puede fallar
    conexion = pymysql.connect(host='127.0.0.1', user='root', password='')
except pymysql.MySQLError as e:
    # Equivalente al catch
    print(f"Error de base de datos: {e}")
finally:
    # Siempre se ejecuta (igual que en C# / PHP)
    if 'conexion' in locals():
        conexion.close()
```

### Equivalencia de PDO / ADO.NET con PyMySQL
Cuando ejecutas consultas en Python, necesitas un objeto llamado **Cursor** (similar al `PDOStatement` o al `SqlDataReader`).

```python
import pymysql

# 1. Conexión
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='mi_password',
    database='practica_recargas',
    cursorclass=pymysql.cursors.DictCursor # Importante: Devuelve los datos como diccionarios (estilo PDO::FETCH_ASSOC)
)

try:
    with conn.cursor() as cursor:
        # 2. Preparar y ejecutar (Previene Inyección SQL automáticamente con %s)
        sql = "SELECT * FROM usuarios WHERE email = %s AND estatus = %s"
        cursor.execute(sql, ('alfonso@correo.com', 1))
        
        # 3. Recuperar datos
        resultado = cursor.fetchone() # Un solo registro
        todos = cursor.fetchall()    # Todos los registros
finally:
    conn.close()
```

---

## 5. El Entorno Flask (Comparado con ruteo clásico)

Si recuerdas cómo manejabas las rutas en un controlador de C# o en un framework de PHP, Flask usa **decoradores** (`@app.route`):

```python
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Definición de Ruta con Métodos (Equivalente a HttpGet / HttpPost)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Obtener datos del formulario (Equivalente a \$_POST['input'] o Request.Form["input"])
        usuario = request.form.get('txt_usuario')
        return redirect(url_for('dashboard')) # Redirección segura
        
    # Renderizar vista (Equivalente a return View() o include 'vista.php')
    return render_template('login.html') 

if __name__ == '__main__':
    app.run(port=5000)
```
