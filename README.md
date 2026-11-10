# Python air-gapped toolkit

Herramientas de un solo archivo para **comprobar que una instalación de Python + Flask + MySQL funciona**, pensadas para equipos **sin internet** (air-gapped). También sirven como ejercicios de práctica.

Sin dependencias raras: solo `flask` y `pymysql`. Todo lo demás es la librería estándar de Python.

## Contenido

| Archivo | Para qué sirve | Puerto |
|---|---|---|
| `diagnostico.py` | Ficha técnica del entorno y **verificación OK / AVISO / FALLA** | 5002 |
| `recargas.py` | Prueba de humo 1: dos tablas, formularios, filtros, DataTables, patrón POST → redirect | 5000 |
| `usuarios.py` | Prueba de humo 2: login/logout, contraseñas con hash, subida de JPG a BLOB, baja lógica, CSRF | 5001 |
| `requirements.txt` | Paquetes a instalar | |
| `static/vendor/` | Aquí van las librerías front-end (se descargan aparte, ver abajo) | |

Si `recargas.py` y `usuarios.py` corren bien, quedan probados Flask, la conexión a MySQL, las plantillas, las sesiones, la subida de archivos y los archivos estáticos.

**Probado con:** Python 3.12, Flask 3.1, PyMySQL 1.2, MariaDB 10.11.

## Requisitos

- Python 3.8 o superior
- MySQL 5.7+ / 8.x o MariaDB 10.x, con un usuario que pueda crear bases de datos
- `pip install flask pymysql`

## Instalación

### Con internet

```
pip install -r requirements.txt
```

### Sin internet (con USB)

En una máquina **con internet** y, de preferencia, **la misma versión de Python y el mismo sistema operativo** que la de destino:

```
pip download -r requirements.txt -d wheels
```

Se crea la carpeta `wheels/` con varios archivos `.whl` (Flask arrastra otras librerías). Cópiala al USB. En la máquina sin internet:

```
pip install --no-index --find-links=wheels -r requirements.txt
```

Si la máquina de destino tiene otra versión de Python o es de otro sistema operativo, indícalo al descargar. Por ejemplo, para Windows de 64 bits con Python 3.11:

```
pip download -r requirements.txt -d wheels --only-binary=:all: --platform win_amd64 --python-version 3.11
```

En Debian, para crear entornos virtuales puede hacer falta el paquete `python3-venv` (confírmalo antes de quedarte sin internet).

## Librerías front-end (descarga aparte)

Estas librerías **no se incluyen** porque tienen licencias propias. Colócalas con estas rutas dentro de `static/vendor/`:

```
static/vendor/
├── bootstrap-4.6.2/
│   ├── css/bootstrap.min.css
│   └── js/bootstrap.bundle.min.js
├── fontawesome-5.15.4/
│   ├── css/all.min.css
│   └── webfonts/            (carpeta completa, junto a css/)
├── jquery/
│   └── jquery.min.js
└── datatables/
    ├── css/dataTables.bootstrap4.min.css
    └── js/
        ├── jquery.dataTables.min.js
        └── dataTables.bootstrap4.min.js
```

Versiones usadas: Bootstrap 4.6.2, Font Awesome Free 5.15.4, jQuery 3.x, DataTables 1.13.x. Cada una conserva su licencia original; al redistribuirlas, incluye sus avisos.

Después de copiarlas, `python diagnostico.py --verificar` te dice cuáles faltan.

## Configuración

Por variables de entorno (todas opcionales):

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | Servidor MySQL |
| `DB_PORT` | `3306` | Puerto de MySQL |
| `DB_USER` | `root` | Usuario de MySQL |
| `DB_PASSWORD` | *(vacía)* | Contraseña de MySQL |
| `SECRET_KEY` | un texto de ejemplo | Firma de las sesiones (`recargas.py` y `usuarios.py`). **Cámbiala.** |

Windows (CMD): `set DB_PASSWORD=mi_clave`
Windows (PowerShell): `$env:DB_PASSWORD="mi_clave"`
Linux: `export DB_PASSWORD=mi_clave`

La variable solo vale para esa ventana de consola.

## Uso

### 1. Verificar la instalación (lo primero)

```
python diagnostico.py --verificar
```

Imprime una lista de comprobaciones:

```
[ OK  ] Python 3.12.3 (64 bits)
[ OK  ] Flask 3.1.3 importa correctamente
[ OK  ] Flask responde, Jinja2 renderiza y la sesión firmada funciona (prueba en memoria)
[ OK  ] Conexión correcta: MariaDB 10.11.14
[ OK  ] Modo estricto activo (los datos inválidos dan error)
[ OK  ] Crear BD temporal, tabla, guardar 1 MB y acentos, leer y borrar: correcto
[AVISO] Faltan 8 de 8 rutas en static/vendor
```

| Nivel | Significado |
|---|---|
| `OK` | Funciona. |
| `AVISO` | Funciona, pero algo conviene revisar según lo que vayas a usar (por ejemplo, faltan estilos o MySQL no es estricto). |
| `FALLA` | Algo no funciona. Corrígelo y vuelve a correr. |

El código de salida es `0` si no hay `FALLA` y `1` si la hay, por si lo quieres usar en un script.

Las pruebas de MySQL crean una base temporal (`diag_tmp_...`), escriben datos de prueba y la borran al terminar. No tocan tus bases existentes, pero el usuario necesita permiso para crear y borrar bases de datos.

### 2. Ficha técnica

```
python diagnostico.py --texto     # en consola, sin navegador ni Flask
python diagnostico.py             # página en http://127.0.0.1:5002
python diagnostico.py --red       # visible desde otras máquinas de la red
```

Muestra versiones de Python, Flask y demás paquetes; versión de MySQL/MariaDB, `sql_mode` y si es **estricto**; IP(s) del equipo y dominio, si existe. La página también ofrece `/diagnostico.json`.

### 3. Ejercicios

```
python recargas.py     # http://127.0.0.1:5000
python usuarios.py     # http://127.0.0.1:5001
```

Cada uno crea su propia base de datos (`practica_recargas`, `practica_usuarios`) y sus tablas la primera vez.

`usuarios.py` crea el usuario `admin` con una **contraseña aleatoria que se imprime una sola vez en la consola**. Cópiala en ese momento.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `No module named flask` | No se instaló desde los wheels, o se usa otro Python que el que tiene los paquetes. |
| Error 1045 *Access denied* | Usuario o contraseña incorrectos; revisa `DB_USER` y `DB_PASSWORD`. |
| Error 2003 *Can't connect* | El servicio MySQL está apagado, o `DB_HOST` / `DB_PORT` son incorrectos. |
| Páginas sin estilos ni íconos | Faltan archivos en `static/vendor/`. |
| `Got a packet bigger than 'max_allowed_packet'` al subir una foto | Sube `max_allowed_packet` en MySQL a 16M o más. |
| Aviso de modo estricto | MySQL recorta o ajusta datos inválidos en silencio. Es importante saberlo antes de trabajar con datos reales. |
| Acentos raros en la consola de Windows | Ejecuta `chcp 65001` antes. |
| Puerto en uso | Ya hay un programa (o esa misma app) corriendo en ese puerto. |

## Seguridad

- Estas herramientas usan el servidor de desarrollo de Flask: sirven para pruebas, **no para producción**.
- `diagnostico.py` **no pide login** y revela datos del equipo. Por defecto solo escucha en `127.0.0.1`; usa `--red` solo en redes de confianza y ciérralo al terminar.
- Cambia `SECRET_KEY` y no dejes la base con la contraseña vacía.
- **No subas a ningún repositorio salidas de `diagnostico.py` de equipos reales** (IP, nombres de equipo, dominios).

## Licencia

Código bajo licencia [MIT](LICENSE). Las librerías de terceros (Flask, PyMySQL, Bootstrap, jQuery, DataTables, Font Awesome) conservan sus propias licencias.
