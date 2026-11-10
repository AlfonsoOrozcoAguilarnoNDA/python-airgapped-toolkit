"""
diagnostico.py - Ficha técnica del entorno (ejercicio de fogueo 3)

Muestra: versión de Python, de Flask (y demás paquetes), de MySQL/MariaDB,
si MySQL está en modo ESTRICTO (sql_mode), la(s) IP del equipo y si tiene dominio.

Formas de usarlo:
    python diagnostico.py            -> página web en http://127.0.0.1:5002  (solo esta máquina)
    python diagnostico.py --red      -> igual, pero visible desde otras máquinas de la red (0.0.0.0)
    python diagnostico.py --texto    -> imprime todo en la consola, SIN navegador y SIN Flask
                                        (sirve incluso si Flask aún no está instalado)
    python diagnostico.py --verificar -> revisa la instalación y da una lista OK / AVISO / FALLA
                                        (código de salida 0 si no hay FALLA, 1 si la hay)
    La página también ofrece /diagnostico.json

Requisitos: pip install flask pymysql  (para --texto y --verificar no hace falta ni Flask)
Configuración por variables de entorno (opcionales): DB_HOST, DB_PORT, DB_USER, DB_PASSWORD.
Librerías locales en static/vendor/ (mismas rutas que los otros ejercicios).

OJO: esta página revela información del servidor y NO pide login. Úsala en tu equipo o en
una red de confianza; no la dejes publicada.
"""
import importlib
import os
import platform
import secrets
import socket
import struct
import sys
import threading
import time
from datetime import datetime
from importlib import metadata as md

try:
    import pymysql
    import pymysql.cursors
except ImportError:                      # el diagnóstico debe funcionar aunque falte
    pymysql = None

# ----------------------------------------------------------------------------
# Configuración (sin base de datos: basta conectarse al servidor)
# ----------------------------------------------------------------------------
DB_CFG = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    charset="utf8mb4",
    connect_timeout=3,
)
PUERTO = 5002

PAQUETES = ["flask", "werkzeug", "jinja2", "markupsafe", "itsdangerous", "click",
            "blinker", "pymysql", "pip"]
# Con estos modos activos, MySQL RECHAZA datos inválidos en vez de "arreglarlos" en silencio.
MODOS_ESTRICTOS = ("STRICT_TRANS_TABLES", "STRICT_ALL_TABLES")


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def version_de(nombre):
    """Versión instalada de un paquete (sin importarlo), o None."""
    try:
        return md.version(nombre)
    except md.PackageNotFoundError:
        return None


def con_timeout(fn, seg=2, defecto=None):
    """Corre fn() en un hilo y espera máximo 'seg' segundos.
    Las consultas DNS en una red sin internet pueden quedarse colgadas; así no te congelan."""
    res = {}

    def corre():
        try:
            res["v"] = fn()
        except Exception:
            pass

    t = threading.Thread(target=corre, daemon=True)
    t.start()
    t.join(seg)
    return res.get("v", defecto)


def ip_principal():
    """IP con la que este equipo saldría a la red. El socket UDP NO envía nada:
    solo hace que el sistema operativo elija la interfaz de salida."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def todas_las_ips(host):
    infos = socket.getaddrinfo(host, None)
    return sorted({i[4][0] for i in infos})


# ----------------------------------------------------------------------------
# Recolección
# ----------------------------------------------------------------------------
def info_python():
    return {
        "version": sys.version.split()[0],
        "detalle": sys.version.replace("\n", " "),
        "implementacion": platform.python_implementation(),
        "bits": struct.calcsize("P") * 8,
        "ejecutable": sys.executable,
        "venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "sistema": platform.platform(),
    }


def info_paquetes():
    return [{"nombre": n, "version": version_de(n)} for n in PAQUETES]


def info_mysql():
    if pymysql is None:
        return {"error": "PyMySQL no está instalado (pip install pymysql)."}
    try:
        con = pymysql.connect(**DB_CFG)
    except Exception as e:
        return {"error": f"No se pudo conectar: {type(e).__name__}: {e}"}
    try:
        with con.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""SELECT VERSION() AS v, @@version_comment AS c,
                                  @@session.sql_mode AS sm, @@global.sql_mode AS gm,
                                  @@max_allowed_packet AS p, @@character_set_server AS cs,
                                  @@collation_server AS co, @@time_zone AS tz,
                                  @@system_time_zone AS stz, CURRENT_USER() AS u,
                                  @@port AS port, @@hostname AS host""")
            r = cur.fetchone()
    except Exception as e:
        return {"error": f"Falló la consulta: {type(e).__name__}: {e}"}
    finally:
        con.close()

    sesion = [m for m in (r["sm"] or "").split(",") if m]
    glob = [m for m in (r["gm"] or "").split(",") if m]
    return {
        "error": None,
        "version": r["v"],
        "motor": "MariaDB" if "mariadb" in (r["v"] or "").lower() else "MySQL",
        "comentario": r["c"],
        "modos_sesion": sesion,
        "modos_global": glob,
        "estricto": any(m in MODOS_ESTRICTOS for m in sesion),
        "max_packet_mb": round(float(r["p"]) / 1048576, 1),
        "charset": r["cs"],
        "collation": r["co"],
        "zona": f'{r["tz"]} (sistema: {r["stz"]})',
        "usuario": r["u"],
        "puerto": r["port"],
        "host": r["host"],
    }


def info_red(req=None):
    nombre = socket.gethostname()
    fqdn = con_timeout(socket.getfqdn, defecto=None)
    ip = ip_principal()
    ips = con_timeout(lambda: todas_las_ips(nombre), defecto=[]) or []
    if ip and ip not in ips:
        ips.insert(0, ip)
    inverso = None
    if ip:
        inverso = con_timeout(lambda: socket.gethostbyaddr(ip)[0], defecto=None)

    # Dominio: el FQDN solo cuenta si realmente trae un punto distinto del nombre del equipo
    dominio = None
    if fqdn and "." in fqdn and fqdn.lower() != nombre.lower():
        dominio = fqdn.split(".", 1)[1]

    return {
        "equipo": nombre,
        "fqdn": fqdn,
        "dominio": dominio,
        "ip_principal": ip,
        "ips": ips,
        "dns_inverso": inverso,
        "cliente_ip": req.remote_addr if req else None,
        "host_header": req.host if req else None,
    }


def info_entorno():
    ahora = datetime.now().astimezone()
    return {
        "hora": ahora.strftime("%d/%m/%Y %H:%M:%S %z"),
        "zona": time.tzname[0],
        "carpeta": __import__("os").getcwd(),
        "archivo": __import__("os").path.abspath(__file__),
    }


def recopilar(req=None):
    return {
        "python": info_python(),
        "paquetes": info_paquetes(),
        "mysql": info_mysql(),
        "red": info_red(req),
        "entorno": info_entorno(),
    }


# ----------------------------------------------------------------------------
# Salida en consola (--texto)
# ----------------------------------------------------------------------------
def imprimir_texto(d):
    def titulo(t):
        print("\n=== " + t + " " + "=" * max(3, 60 - len(t)))

    def fila(k, v):
        print(f"  {k:<26} {v if v not in (None, '', []) else '-'}")

    p = d["python"]
    titulo("PYTHON")
    fila("Version", p["version"])
    fila("Implementacion", f'{p["implementacion"]} {p["bits"]} bits')
    fila("Ejecutable", p["ejecutable"])
    fila("Entorno virtual", "si" if p["venv"] else "no")
    fila("Sistema", p["sistema"])

    titulo("PAQUETES")
    for x in d["paquetes"]:
        fila(x["nombre"], x["version"] or "NO INSTALADO")

    m = d["mysql"]
    titulo("MYSQL / MARIADB")
    if m["error"]:
        fila("ERROR", m["error"])
    else:
        fila("Servidor", f'{m["motor"]} {m["version"]}')
        fila("Comentario", m["comentario"])
        fila("Modo estricto", "SI (estricto)" if m["estricto"] else "NO (permisivo)")
        fila("sql_mode (sesion)", ",".join(m["modos_sesion"]))
        if m["modos_global"] != m["modos_sesion"]:
            fila("sql_mode (global)", ",".join(m["modos_global"]))
        fila("max_allowed_packet", f'{m["max_packet_mb"]} MB')
        fila("Charset / collation", f'{m["charset"]} / {m["collation"]}')
        fila("Zona horaria", m["zona"])
        fila("Usuario / puerto", f'{m["usuario"]} / {m["puerto"]}')
        fila("Hostname MySQL", m["host"])

    r = d["red"]
    titulo("RED")
    fila("Equipo", r["equipo"])
    fila("Nombre completo (FQDN)", r["fqdn"])
    fila("Dominio", r["dominio"] or "sin dominio configurado")
    fila("IP principal", r["ip_principal"])
    fila("Todas las IP", ", ".join(r["ips"]))
    fila("DNS inverso", r["dns_inverso"])

    e = d["entorno"]
    titulo("ENTORNO")
    fila("Hora del equipo", e["hora"])
    fila("Carpeta actual", e["carpeta"])
    fila("Este archivo", e["archivo"])
    print()


# ----------------------------------------------------------------------------
# Web
# ----------------------------------------------------------------------------
PLANTILLA = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnóstico del entorno</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap-4.6.2/css/bootstrap.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/fontawesome-5.15.4/css/all.min.css') }}">
  <style>
    :root { --ink:#0f3d3e; --accent:#0f766e; }
    body { background:#f3f6f6; color:#25302f; }
    .navbar { background:var(--ink); }
    .card { border:0; border-radius:.6rem; box-shadow:0 1px 3px rgba(15,61,62,.10); }
    .card-header { background:#fff; font-weight:600; border-bottom:1px solid #e4eded; border-radius:.6rem .6rem 0 0; }
    .card-header i { color:var(--accent); }
    th { width:34%; color:#667a79; font-weight:500; }
    td { word-break:break-word; }
    .modo { font-family:SFMono-Regular,Menlo,Consolas,monospace; font-size:.75rem; }
    .modo.on { background:#d1fae5; color:#065f46; }
    .modo.off { background:#eef2f2; color:#51605f; }
  </style>
</head>
<body>
<nav class="navbar navbar-dark mb-4">
  <span class="navbar-brand"><i class="fas fa-stethoscope mr-2"></i>Diagnóstico del entorno</span>
  <a class="btn btn-sm btn-outline-light" href="{{ url_for('como_json') }}"><i class="fas fa-code mr-1"></i>JSON</a>
</nav>
<div class="container pb-5">
  <div class="row">

    <div class="col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-header"><i class="fab fa-python mr-2"></i>Python y paquetes</div>
        <div class="card-body">
          <table class="table table-sm mb-3">
            <tr><th>Versión</th><td><strong>{{ d.python.version }}</strong> ({{ d.python.implementacion }}, {{ d.python.bits }} bits)</td></tr>
            <tr><th>Ejecutable</th><td>{{ d.python.ejecutable }}</td></tr>
            <tr><th>Entorno virtual</th><td>{{ 'Sí' if d.python.venv else 'No' }}</td></tr>
            <tr><th>Sistema</th><td>{{ d.python.sistema }}</td></tr>
          </table>
          <table class="table table-sm mb-0">
            {% for x in d.paquetes %}
            <tr><th>{{ x.nombre }}</th>
                <td>{% if x.version %}{{ x.version }}{% else %}<span class="badge badge-light">no instalado</span>{% endif %}</td></tr>
            {% endfor %}
          </table>
        </div>
      </div>
    </div>

    <div class="col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-header"><i class="fas fa-database mr-2"></i>MySQL / MariaDB</div>
        <div class="card-body">
          {% if d.mysql.error %}
            <div class="alert alert-danger mb-0">{{ d.mysql.error }}</div>
          {% else %}
          <table class="table table-sm mb-2">
            <tr><th>Servidor</th><td><strong>{{ d.mysql.motor }} {{ d.mysql.version }}</strong></td></tr>
            <tr><th>Comentario</th><td>{{ d.mysql.comentario }}</td></tr>
            <tr><th>Modo estricto</th>
                <td>{% if d.mysql.estricto %}<span class="badge badge-success">ESTRICTO</span>
                    {% else %}<span class="badge badge-warning">NO estricto</span>{% endif %}</td></tr>
            <tr><th>sql_mode (sesión)</th>
                <td>{% for m in d.mysql.modos_sesion %}<span class="badge modo mr-1 mb-1 {{ 'on' if m in ('STRICT_TRANS_TABLES','STRICT_ALL_TABLES') else 'off' }}">{{ m }}</span>{% else %}<em>(vacío)</em>{% endfor %}</td></tr>
            {% if d.mysql.modos_global != d.mysql.modos_sesion %}
            <tr><th>sql_mode (global)</th>
                <td>{% for m in d.mysql.modos_global %}<span class="badge modo off mr-1 mb-1">{{ m }}</span>{% else %}<em>(vacío)</em>{% endfor %}</td></tr>
            {% endif %}
            <tr><th>max_allowed_packet</th><td>{{ d.mysql.max_packet_mb }} MB</td></tr>
            <tr><th>Charset / collation</th><td>{{ d.mysql.charset }} / {{ d.mysql.collation }}</td></tr>
            <tr><th>Zona horaria</th><td>{{ d.mysql.zona }}</td></tr>
            <tr><th>Usuario / puerto</th><td>{{ d.mysql.usuario }} / {{ d.mysql.puerto }}</td></tr>
            <tr><th>Hostname</th><td>{{ d.mysql.host }}</td></tr>
          </table>
          <small class="text-muted">
            En modo estricto, un dato inválido (texto demasiado largo, fecha 0000-00-00) provoca un error.
            Sin él, MySQL lo recorta o lo ajusta en silencio y el problema aparece después.
          </small>
          {% endif %}
        </div>
      </div>
    </div>

    <div class="col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-header"><i class="fas fa-network-wired mr-2"></i>Red</div>
        <div class="card-body">
          <table class="table table-sm mb-0">
            <tr><th>Equipo</th><td>{{ d.red.equipo }}</td></tr>
            <tr><th>Nombre completo (FQDN)</th><td>{{ d.red.fqdn or '—' }}</td></tr>
            <tr><th>Dominio</th>
                <td>{% if d.red.dominio %}<strong>{{ d.red.dominio }}</strong>
                    {% else %}<span class="badge badge-light">sin dominio configurado</span>{% endif %}</td></tr>
            <tr><th>IP principal</th><td><strong>{{ d.red.ip_principal or '—' }}</strong></td></tr>
            <tr><th>Todas las IP</th><td>{{ d.red.ips|join(', ') or '—' }}</td></tr>
            <tr><th>DNS inverso</th><td>{{ d.red.dns_inverso or '—' }}</td></tr>
            <tr><th>Tu IP (cliente)</th><td>{{ d.red.cliente_ip or '—' }}</td></tr>
            <tr><th>Entraste como (Host)</th><td>{{ d.red.host_header or '—' }}</td></tr>
          </table>
        </div>
      </div>
    </div>

    <div class="col-lg-6 mb-4">
      <div class="card h-100">
        <div class="card-header"><i class="fas fa-folder-open mr-2"></i>Entorno</div>
        <div class="card-body">
          <table class="table table-sm mb-0">
            <tr><th>Hora del equipo</th><td>{{ d.entorno.hora }}</td></tr>
            <tr><th>Carpeta actual</th><td>{{ d.entorno.carpeta }}</td></tr>
            <tr><th>Este archivo</th><td>{{ d.entorno.archivo }}</td></tr>
          </table>
        </div>
      </div>
    </div>

  </div>
</div>
</body>
</html>
"""


# ----------------------------------------------------------------------------
# Verificación (--verificar): lista OK / AVISO / FALLA
# ----------------------------------------------------------------------------
MIN_PY = (3, 8)
PUERTOS = [5000, 5001, 5002]
VENDOR = [
    "static/vendor/bootstrap-4.6.2/css/bootstrap.min.css",
    "static/vendor/bootstrap-4.6.2/js/bootstrap.bundle.min.js",
    "static/vendor/fontawesome-5.15.4/css/all.min.css",
    "static/vendor/fontawesome-5.15.4/webfonts",
    "static/vendor/jquery/jquery.min.js",
    "static/vendor/datatables/css/dataTables.bootstrap4.min.css",
    "static/vendor/datatables/js/jquery.dataTables.min.js",
    "static/vendor/datatables/js/dataTables.bootstrap4.min.js",
]


def puerto_libre(p):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p))
        return True
    except OSError:
        return False
    finally:
        s.close()


def prueba_flask():
    """Flask real en memoria: ruta, Jinja2 y sesión firmada (sin abrir ningún puerto)."""
    from flask import Flask, render_template_string, session
    app = Flask(__name__)
    app.secret_key = "prueba"

    @app.route("/")
    def i():
        session["ok"] = 1
        return render_template_string("hola {{ n|upper }}", n="mundo")

    r = app.test_client().get("/")
    if r.status_code != 200 or r.get_data(as_text=True) != "hola MUNDO":
        raise RuntimeError(f"respuesta inesperada (HTTP {r.status_code})")
    if "session=" not in r.headers.get("Set-Cookie", ""):
        raise RuntimeError("no se generó la cookie de sesión")


def prueba_hash():
    from werkzeug.security import check_password_hash, generate_password_hash
    h = generate_password_hash("Clave-de-prueba-1", method="pbkdf2:sha256")
    if not (check_password_hash(h, "Clave-de-prueba-1") and not check_password_hash(h, "otra")):
        raise RuntimeError("el hash no verifica correctamente")


def prueba_escritura():
    """Crea una BD temporal, una tabla, guarda 1 MB binario y texto con acentos, lo lee y lo borra."""
    nombre = "diag_tmp_" + secrets.token_hex(4)
    con = pymysql.connect(**DB_CFG)
    con.autocommit(True)
    try:
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4")
            try:
                cur.execute(f"USE `{nombre}`")
                cur.execute("CREATE TABLE t (id INT AUTO_INCREMENT PRIMARY KEY, "
                            "txt VARCHAR(50), b MEDIUMBLOB) ENGINE=InnoDB")
                datos = os.urandom(1024 * 1024)
                texto = "áéíóúñ ÁÉÍÓÚÑ €"
                cur.execute("INSERT INTO t (txt, b) VALUES (%s, %s)", (texto, datos))
                cur.execute("SELECT txt, b FROM t")
                fila = cur.fetchone()
                if fila[0] != texto or bytes(fila[1]) != datos:
                    raise RuntimeError("lo leído no coincide con lo escrito")
            finally:
                cur.execute(f"DROP DATABASE IF EXISTS `{nombre}`")
    finally:
        con.close()


def verificar():
    """Imprime la lista de comprobaciones. Devuelve 0 si no hay FALLA, 1 si la hay."""
    conteo = {"OK": 0, "AVISO": 0, "FALLA": 0}

    def anota(nivel, texto, ayuda=""):
        conteo[nivel] += 1
        print(f"[{nivel:^5}] {texto}")
        if ayuda:
            print(f"         -> {ayuda}")

    def seccion(t):
        print("\n--- " + t + " " + "-" * max(3, 56 - len(t)))

    print("VERIFICACION DE LA INSTALACION")
    print("=" * 60)

    # 1. Python
    seccion("Python")
    v = sys.version.split()[0]
    bits = struct.calcsize("P") * 8
    if sys.version_info[:2] >= MIN_PY:
        anota("OK", f"Python {v} ({bits} bits)")
    else:
        anota("FALLA", f"Python {v} es menor al mínimo {MIN_PY[0]}.{MIN_PY[1]}",
              "Instala una versión más reciente.")
    if version_de("pip"):
        anota("OK", f"pip {version_de('pip')}")
    else:
        anota("AVISO", "pip no aparece instalado", "Sin pip no puedes instalar paquetes (python -m ensurepip).")

    # 2. Paquetes
    seccion("Paquetes")
    flask_ok = pymysql_ok = False
    for etiqueta, modulo in (("Flask", "flask"), ("PyMySQL", "pymysql")):
        try:
            importlib.import_module(modulo)
            anota("OK", f"{etiqueta} {version_de(modulo) or '?'} importa correctamente")
            if modulo == "flask":
                flask_ok = True
            else:
                pymysql_ok = True
        except Exception as e:
            anota("FALLA", f"{etiqueta} no se puede importar: {type(e).__name__}: {e}",
                  "Instala con: pip install --no-index --find-links=wheels flask pymysql")
    if flask_ok:
        try:
            prueba_flask()
            anota("OK", "Flask responde, Jinja2 renderiza y la sesión firmada funciona (prueba en memoria)")
        except Exception as e:
            anota("FALLA", f"Prueba de Flask: {type(e).__name__}: {e}")
        try:
            prueba_hash()
            anota("OK", "Hash de contraseñas (pbkdf2:sha256) funciona")
        except Exception as e:
            anota("FALLA", f"Hash de contraseñas: {type(e).__name__}: {e}")

    # 3. MySQL
    seccion("MySQL / MariaDB")
    if not pymysql_ok:
        anota("FALLA", "Sin PyMySQL no se puede probar la base de datos")
    else:
        m = info_mysql()
        if m["error"]:
            anota("FALLA", m["error"],
                  "Revisa que el servicio esté encendido y las variables DB_HOST / DB_USER / DB_PASSWORD.")
        else:
            anota("OK", f'Conexión correcta: {m["motor"]} {m["version"]}')
            if m["estricto"]:
                anota("OK", "Modo estricto activo (los datos inválidos dan error)")
            else:
                anota("AVISO", "Modo estricto NO activo",
                      "MySQL recorta o ajusta datos inválidos en silencio. Revísalo antes de tocar datos.")
            if m["max_packet_mb"] >= 8:
                anota("OK", f'max_allowed_packet = {m["max_packet_mb"]} MB (alcanza para fotos de 8 MB)')
            else:
                anota("AVISO", f'max_allowed_packet = {m["max_packet_mb"]} MB',
                      "Menor a 8 MB: usuarios.py fallará al guardar fotos grandes.")
            if m["charset"] != "utf8mb4":
                anota("AVISO", f'Charset del servidor: {m["charset"]}',
                      "Las apps crean sus BD en utf8mb4, pero otras BD podrían no ser compatibles.")
            try:
                prueba_escritura()
                anota("OK", "Crear BD temporal, tabla, guardar 1 MB y acentos, leer y borrar: correcto")
            except Exception as e:
                anota("FALLA", f"Prueba de escritura: {type(e).__name__}: {e}",
                      "El usuario de MySQL necesita permiso para crear y borrar bases de datos.")

    # 4. Librerías front-end
    seccion("Archivos estáticos (static/vendor)")
    base = os.path.dirname(os.path.abspath(__file__))
    faltan = [r for r in VENDOR if not os.path.exists(os.path.join(base, *r.split("/")))]
    if not faltan:
        anota("OK", f"Están las {len(VENDOR)} rutas de Bootstrap, Font Awesome, jQuery y DataTables")
    else:
        anota("AVISO", f"Faltan {len(faltan)} de {len(VENDOR)} rutas en static/vendor",
              "Las páginas se verán sin estilos. Ver README (sección de librerías).")
        for r in faltan:
            print("            falta: " + r)

    # 5. Puertos
    seccion("Puertos locales")
    for p in PUERTOS:
        if puerto_libre(p):
            anota("OK", f"Puerto {p} libre")
        else:
            anota("AVISO", f"Puerto {p} en uso", "¿Ya hay otro programa (o esta misma app) corriendo ahí?")

    # Resumen
    print("\n" + "=" * 60)
    print(f'Resultado: {conteo["OK"]} OK, {conteo["AVISO"]} avisos, {conteo["FALLA"]} fallas')
    if conteo["FALLA"]:
        print("ESTADO: HAY FALLAS. Corrige las marcadas [FALLA] y vuelve a correr --verificar.")
        return 1
    if conteo["AVISO"]:
        print("ESTADO: FUNCIONAL, con avisos. Revísalos según lo que vayas a usar.")
    else:
        print("ESTADO: TODO CORRECTO.")
    return 0


def crear_app():
    # Flask se importa aquí para que --texto funcione aunque Flask no esté instalado.
    from flask import Flask, jsonify, render_template_string, request

    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(PLANTILLA, d=recopilar(request))

    @app.route("/diagnostico.json")
    def como_json():
        return jsonify(recopilar(request))

    return app


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    if "--verificar" in sys.argv:
        sys.exit(verificar())
    elif "--texto" in sys.argv:
        imprimir_texto(recopilar())
    else:
        abierto = "--red" in sys.argv
        if abierto:
            print("AVISO: accesible desde toda la red, sin login. Ciérralo al terminar.")
        crear_app().run(host="0.0.0.0" if abierto else "127.0.0.1", port=PUERTO, debug=False)
