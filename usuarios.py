"""
usuarios.py - Control de usuarios con login (ejercicio de fogueo 2: Flask + MySQL)

Un solo archivo. Requisitos:
    pip install flask pymysql
(las contraseñas usan werkzeug.security, que ya viene con Flask: nada extra que llevar al air-gapped)

Librerias locales, mismas rutas que recargas.py:
    static/vendor/bootstrap-4.6.2/css/bootstrap.min.css
    static/vendor/bootstrap-4.6.2/js/bootstrap.bundle.min.js
    static/vendor/fontawesome-5.15.4/css/all.min.css      (y ../webfonts/ al lado)
    static/vendor/jquery/jquery.min.js
    static/vendor/datatables/css/dataTables.bootstrap4.min.css
    static/vendor/datatables/js/jquery.dataTables.min.js
    static/vendor/datatables/js/dataTables.bootstrap4.min.js

Correr:  python usuarios.py   ->  http://127.0.0.1:5001
La PRIMERA vez crea el usuario "admin" con una contraseña aleatoria que se imprime
en la consola UNA sola vez. Guardala.

Que se aprende aqui (con su equivalente PHP):
    password_hash / password_verify  ->  generate_password_hash / check_password_hash
    $_SESSION['uid']                 ->  session["uid"]
    if(!isset($_SESSION['uid']))     ->  decorador @login_requerido
    $_FILES['foto']                  ->  request.files["foto"]
    token CSRF a mano                ->  before_request + campo oculto "csrf"
    DELETE fisico                    ->  UPDATE activo='N' (baja logica)
"""
import calendar
import hmac
import os
import re
import secrets
from datetime import datetime
from functools import wraps

import pymysql
import pymysql.cursors
from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from jinja2 import DictLoader
from werkzeug.security import check_password_hash, generate_password_hash

# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------
DB_NAME = "practica_usuarios"
DB_CFG = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),   # define la variable de entorno DB_PASSWORD
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)

MAX_FOTO = 8 * 1024 * 1024          # 8 MB, fijo en el codigo
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
RE_USUARIO = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-serio")
# Flask rechaza (413) cualquier peticion mayor a esto; damos holgura para el resto del formulario
app.config["MAX_CONTENT_LENGTH"] = MAX_FOTO + 512 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ----------------------------------------------------------------------------
# Contraseñas
# ----------------------------------------------------------------------------
def hash_clave(clave):
    # pbkdf2:sha256 -> sal aleatoria + miles de iteraciones, todo dentro del mismo texto.
    # Se fija el metodo porque scrypt (el default nuevo) depende de como se compilo OpenSSL.
    return generate_password_hash(clave, method="pbkdf2:sha256")


# Hash de relleno: se verifica contra el cuando el usuario no existe, para que
# "usuario inexistente" y "clave mala" tarden lo mismo (no revelar que usuarios existen).
HASH_FALSO = hash_clave("no-importa")


# ----------------------------------------------------------------------------
# Base de datos
# ----------------------------------------------------------------------------
def conectar(con_bd=True):
    cfg = dict(DB_CFG)
    if con_bd:
        cfg["database"] = DB_NAME
    return pymysql.connect(**cfg)


def consulta(sql, args=(), uno=False):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if uno else cur.fetchall()
    finally:
        con.close()


def ejecuta(sql, args=()):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, args)
            return cur.lastrowid
    finally:
        con.close()


def init_db():
    con = conectar(con_bd=False)
    try:
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    finally:
        con.close()

    # id = "numero de usuario". UNIQUE en usuario: la BD es quien garantiza que no se repita.
    # ultima_ip VARCHAR(45): alcanza para IPv6 completa (incluso IPv4 mapeada).
    # foto MEDIUMBLOB: un BLOB normal solo guarda 64 KB; MEDIUMBLOB llega a 16 MB.
    ejecuta("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            usuario        VARCHAR(30)  NOT NULL UNIQUE,
            nombre_usuario VARCHAR(100) NOT NULL,
            password_hash  VARCHAR(255) NOT NULL,
            fecha_alta     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ultima_ip      VARCHAR(45)  NULL,
            ultimo_login   DATETIME     NULL,
            unidad_negocio VARCHAR(100) NOT NULL DEFAULT '',
            comentario     VARCHAR(255) NOT NULL DEFAULT '',
            mes_cumple     TINYINT      NULL,
            dia_cumple     TINYINT      NULL,
            activo         VARCHAR(1)   NOT NULL DEFAULT 'S',
            foto           MEDIUMBLOB   NULL
        ) ENGINE=InnoDB
    """)

    # Usuario base
    if consulta("SELECT COUNT(*) AS n FROM usuarios", uno=True)["n"] == 0:
        clave = secrets.token_urlsafe(9)
        ejecuta("INSERT INTO usuarios (usuario, nombre_usuario, password_hash, unidad_negocio) "
                "VALUES (%s, %s, %s, %s)",
                ("admin", "Administrador", hash_clave(clave), "Sistemas"))
        print("=" * 60)
        print(" Usuario inicial creado:  admin")
        print(" Contrasena (solo se muestra ahora):  " + clave)
        print("=" * 60)


# ----------------------------------------------------------------------------
# Filtros y utilidades de plantilla
# ----------------------------------------------------------------------------
@app.template_filter("dt")
def f_dt(v):
    return v.strftime("%d/%m/%Y %H:%M") if v else "—"


@app.template_filter("cumple")
def f_cumple(mes, dia):
    return f"{dia} de {MESES[mes - 1]}" if mes and dia else "—"


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.add_template_global(csrf_token, "csrf_token")


# ----------------------------------------------------------------------------
# Antes de cada peticion: CSRF + quien es el usuario en sesion
# ----------------------------------------------------------------------------
@app.before_request
def antes():
    if request.endpoint == "static":
        return

    # CSRF: todo POST debe traer el token que Flask guardo en la sesion.
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        esperado = session.get("csrf", "")
        if not esperado or not hmac.compare_digest(enviado.encode(), esperado.encode()):
            abort(400, "Token CSRF inválido. Recarga la página e inténtalo de nuevo.")

    # Se revisa en la BD en cada peticion: si das de baja a alguien, su sesion muere al instante.
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = consulta("SELECT id, usuario, nombre_usuario FROM usuarios "
                          "WHERE id = %s AND activo = 'S'", (uid,), uno=True)
        if not g.user:
            session.clear()


def login_requerido(f):
    @wraps(f)
    def envoltura(*a, **k):
        if not g.user:
            return redirect(url_for("login"))
        return f(*a, **k)
    return envoltura


@app.errorhandler(413)
def demasiado_grande(e):
    flash("El archivo excede el límite de 8 MB.", "danger")
    return redirect(request.referrer or url_for("index"))


# ----------------------------------------------------------------------------
# Login / logout
# ----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "")
        u = consulta("SELECT id, password_hash, activo FROM usuarios WHERE usuario = %s",
                     (usuario,), uno=True)

        ok = check_password_hash(u["password_hash"] if u else HASH_FALSO, clave)
        if u and ok and u["activo"] == "S":
            session.clear()                 # sesion nueva al entrar (evita fijacion de sesion)
            session["uid"] = u["id"]
            # remote_addr puede ser IPv4 o IPv6 (ej. "::1"). Detras de un proxy
            # inverso habria que leer X-Forwarded-For, pero solo si confias en ese proxy.
            ejecuta("UPDATE usuarios SET ultimo_login = NOW(), ultima_ip = %s WHERE id = %s",
                    (request.remote_addr, u["id"]))
            return redirect(url_for("index"))

        # Mismo mensaje para clave mala, usuario inexistente o usuario dado de baja.
        flash("Usuario o contraseña incorrectos.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------------------------------------------------------------------
# Validacion compartida por alta y edicion
# ----------------------------------------------------------------------------
def validar(form, archivos, creando):
    e = []
    d = {
        "nombre_usuario": form.get("nombre_usuario", "").strip()[:100],
        "unidad_negocio": form.get("unidad_negocio", "").strip()[:100],
        "comentario": form.get("comentario", "").strip()[:255],
        "clave": form.get("clave", ""),
    }

    if creando:
        d["usuario"] = form.get("usuario", "").strip()
        if not RE_USUARIO.match(d["usuario"]):
            e.append("El usuario debe tener de 3 a 30 caracteres: letras, números, punto, guion o guion bajo.")

    if not d["nombre_usuario"]:
        e.append("El nombre es obligatorio.")

    # Contraseña: obligatoria al crear; al editar solo si escribio algo
    if creando or d["clave"]:
        if len(d["clave"]) < 8:
            e.append("La contraseña debe tener al menos 8 caracteres.")
        elif d["clave"] != form.get("clave2", ""):
            e.append("Las contraseñas no coinciden.")

    # Cumpleaños: mes y dia juntos o ninguno. Se valida contra un año bisiesto (2024) para aceptar 29 de febrero.
    mes, dia = form.get("mes_cumple", "").strip(), form.get("dia_cumple", "").strip()
    d["mes_cumple"] = d["dia_cumple"] = None
    if mes or dia:
        try:
            m, di = int(mes), int(dia)
            if not (1 <= m <= 12 and 1 <= di <= calendar.monthrange(2024, m)[1]):
                raise ValueError
            d["mes_cumple"], d["dia_cumple"] = m, di
        except ValueError:
            e.append("Cumpleaños inválido: elige un mes y un día que existan (no hay 31 de abril).")

    # Foto: no te fies de la extension ni del Content-Type, mira los primeros bytes.
    # Un JPG siempre empieza con FF D8 FF.
    d["foto"] = None
    f = archivos.get("foto")
    if f and f.filename:
        datos = f.read(MAX_FOTO + 1)
        if len(datos) > MAX_FOTO:
            e.append("La foto excede 8 MB.")
        elif not datos.startswith(b"\xff\xd8\xff"):
            e.append("La foto debe ser un archivo JPG válido.")
        else:
            d["foto"] = datos

    return d, e


def ctx_form(**extra):
    return dict(meses=MESES, max_mb=MAX_FOTO // (1024 * 1024), **extra)


# ----------------------------------------------------------------------------
# Usuarios
# ----------------------------------------------------------------------------
@app.route("/")
@login_requerido
def index():
    estado = request.args.get("estado", "activos")
    # Este fragmento SQL sale de un dict fijo, nunca del texto del usuario.
    # (Lo que escribe el usuario siempre va con %s.)
    filtros = {"activos": "WHERE activo = 'S'", "inactivos": "WHERE activo = 'N'", "todos": ""}
    if estado not in filtros:
        estado = "todos"

    # (foto IS NOT NULL) evita traer los MB del BLOB en el listado
    usuarios = consulta(f"""
        SELECT id, usuario, nombre_usuario, unidad_negocio, mes_cumple, dia_cumple,
               activo, fecha_alta, ultimo_login, ultima_ip, (foto IS NOT NULL) AS tiene_foto
          FROM usuarios {filtros[estado]}
         ORDER BY id
    """)
    return render_template("index.html", usuarios=usuarios, estado=estado)


@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@login_requerido
def usuario_nuevo():
    u, errores = {}, []
    if request.method == "POST":
        d, errores = validar(request.form, request.files, creando=True)
        u = d
        if not errores:
            try:
                ejecuta("""INSERT INTO usuarios
                              (usuario, nombre_usuario, password_hash, unidad_negocio,
                               comentario, mes_cumple, dia_cumple, foto)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (d["usuario"], d["nombre_usuario"], hash_clave(d["clave"]),
                         d["unidad_negocio"], d["comentario"], d["mes_cumple"],
                         d["dia_cumple"], d["foto"]))
                flash(f"Usuario {d['usuario']} creado.", "success")
                return redirect(url_for("index"))          # PRG: F5 no duplica
            except pymysql.err.IntegrityError:
                errores.append(f"El usuario «{d['usuario']}» ya existe.")
        # Con errores se vuelve a pintar el formulario (sin redirect) para no perder lo escrito.
    return render_template("form.html", **ctx_form(u=u, creando=True, errores=errores))


@app.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"])
@login_requerido
def usuario_editar(uid):
    u = consulta("""SELECT id, usuario, nombre_usuario, unidad_negocio, comentario,
                           mes_cumple, dia_cumple, (foto IS NOT NULL) AS tiene_foto
                      FROM usuarios WHERE id = %s""", (uid,), uno=True)
    if not u:
        abort(404)

    errores = []
    if request.method == "POST":
        d, errores = validar(request.form, request.files, creando=False)
        if not errores:
            sets = ["nombre_usuario = %s", "unidad_negocio = %s", "comentario = %s",
                    "mes_cumple = %s", "dia_cumple = %s"]
            args = [d["nombre_usuario"], d["unidad_negocio"], d["comentario"],
                    d["mes_cumple"], d["dia_cumple"]]
            if d["clave"]:
                sets.append("password_hash = %s")
                args.append(hash_clave(d["clave"]))
            if d["foto"] is not None:
                sets.append("foto = %s")
                args.append(d["foto"])
            elif request.form.get("quitar_foto"):
                sets.append("foto = NULL")
            args.append(uid)
            # "sets" se arma solo con textos fijos de arriba; los valores van por %s.
            ejecuta("UPDATE usuarios SET " + ", ".join(sets) + " WHERE id = %s", tuple(args))
            flash("Usuario actualizado.", "success")
            return redirect(url_for("index"))
        u = {**u, **d}

    return render_template("form.html", **ctx_form(u=u, creando=False, errores=errores))


@app.route("/usuarios/<int:uid>/estado", methods=["POST"])
@login_requerido
def usuario_estado(uid):
    """Baja y reactivacion LOGICA: el registro nunca se borra."""
    nuevo = "N" if request.form.get("accion") == "baja" else "S"
    if nuevo == "N" and uid == g.user["id"]:
        flash("No puedes darte de baja a ti mismo.", "warning")
    elif not consulta("SELECT id FROM usuarios WHERE id = %s", (uid,), uno=True):
        abort(404)
    else:
        ejecuta("UPDATE usuarios SET activo = %s WHERE id = %s", (nuevo, uid))
        flash("Usuario dado de baja." if nuevo == "N" else "Usuario reactivado.", "success")
    return redirect(url_for("index", estado=request.form.get("volver", "activos")))


@app.route("/foto/<int:uid>")
@login_requerido
def foto(uid):
    r = consulta("SELECT foto FROM usuarios WHERE id = %s", (uid,), uno=True)
    if not r or not r["foto"]:
        abort(404)
    resp = Response(r["foto"], mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "private, no-cache"
    return resp


# ----------------------------------------------------------------------------
# Plantillas
# ----------------------------------------------------------------------------
BASE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Usuarios{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap-4.6.2/css/bootstrap.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/fontawesome-5.15.4/css/all.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/datatables/css/dataTables.bootstrap4.min.css') }}">
  <style>
    :root { --ink:#1e1b4b; --accent:#4f46e5; }
    body { background:#f5f6fb; color:#2b2f3a; }
    .navbar { background:var(--ink); }
    .btn-primary { background:var(--accent); border-color:var(--accent); }
    .btn-primary:hover, .btn-primary:focus { background:#4338ca; border-color:#4338ca; }
    .card { border:0; border-radius:.6rem; box-shadow:0 1px 3px rgba(30,27,75,.10); }
    .card-header { background:#fff; font-weight:600; border-bottom:1px solid #ebecf5; border-radius:.6rem .6rem 0 0; }
    .table thead th { border-top:0; color:#6b7090; font-size:.8rem; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap; }
    .avatar { width:30px; height:30px; border-radius:50%; background:#e0e7ff; color:var(--accent);
              display:inline-flex; align-items:center; justify-content:center; font-size:.8rem; }
    body.login { min-height:100vh; display:flex; align-items:center; justify-content:center;
                 background:linear-gradient(135deg,#1e1b4b 0%,#4f46e5 100%); }
    body.login .container { max-width:400px; }
  </style>
</head>
<body class="{% block bodyclass %}{% endblock %}">
  {% if g.user %}
  <nav class="navbar navbar-dark mb-4">
    <a class="navbar-brand" href="{{ url_for('index') }}"><i class="fas fa-user-shield mr-2"></i>Control de usuarios</a>
    <form method="post" action="{{ url_for('logout') }}" class="form-inline">
      <input type="hidden" name="csrf" value="{{ csrf_token() }}">
      <span class="text-light mr-3"><i class="fas fa-user-circle mr-1"></i>{{ g.user.nombre_usuario }}</span>
      <button class="btn btn-sm btn-outline-light"><i class="fas fa-sign-out-alt mr-1"></i>Salir</button>
    </form>
  </nav>
  {% endif %}
  <div class="container">
    {% with mensajes = get_flashed_messages(with_categories=true) %}
      {% for categoria, texto in mensajes %}
        <div class="alert alert-{{ categoria }} alert-dismissible fade show" role="alert">
          {{ texto }}
          <button type="button" class="close" data-dismiss="alert"><span>&times;</span></button>
        </div>
      {% endfor %}
    {% endwith %}
    {% block contenido %}{% endblock %}
  </div>

  <script src="{{ url_for('static', filename='vendor/jquery/jquery.min.js') }}"></script>
  <script src="{{ url_for('static', filename='vendor/bootstrap-4.6.2/js/bootstrap.bundle.min.js') }}"></script>
  <script src="{{ url_for('static', filename='vendor/datatables/js/jquery.dataTables.min.js') }}"></script>
  <script src="{{ url_for('static', filename='vendor/datatables/js/dataTables.bootstrap4.min.js') }}"></script>
  <script>
    var DT_ES = {
      search: "Buscar:", lengthMenu: "Mostrar _MENU_", info: "Mostrando _START_ a _END_ de _TOTAL_",
      infoEmpty: "Sin registros", infoFiltered: "(filtrado de _MAX_)", zeroRecords: "Sin resultados",
      emptyTable: "Sin datos", paginate: { first: "Primero", last: "Último", next: "Siguiente", previous: "Anterior" }
    };
  </script>
  {% block scripts %}{% endblock %}
</body>
</html>
"""

LOGIN = """{% extends "base.html" %}
{% block title %}Ingresar{% endblock %}
{% block bodyclass %}login{% endblock %}
{% block contenido %}
<div class="card">
  <div class="card-body p-4">
    <div class="text-center mb-4">
      <div class="avatar mb-2" style="width:56px;height:56px;font-size:1.5rem;"><i class="fas fa-lock"></i></div>
      <h5 class="mb-0">Iniciar sesión</h5>
    </div>
    <form method="post" action="{{ url_for('login') }}">
      <input type="hidden" name="csrf" value="{{ csrf_token() }}">
      <div class="form-group">
        <label>Usuario</label>
        <input name="usuario" class="form-control" autocomplete="username" autofocus required>
      </div>
      <div class="form-group">
        <label>Contraseña</label>
        <input type="password" name="clave" class="form-control" autocomplete="current-password" required>
      </div>
      <button class="btn btn-primary btn-block"><i class="fas fa-sign-in-alt mr-1"></i>Entrar</button>
    </form>
  </div>
</div>
{% endblock %}
"""

INDEX = """{% extends "base.html" %}
{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5 class="mb-0"><i class="fas fa-users mr-2"></i>Usuarios</h5>
  <div class="d-flex">
    <form method="get" class="mr-2">
      <select name="estado" class="form-control form-control-sm" onchange="this.form.submit()">
        <option value="activos"   {{ 'selected' if estado == 'activos' }}>Activos</option>
        <option value="inactivos" {{ 'selected' if estado == 'inactivos' }}>Dados de baja</option>
        <option value="todos"     {{ 'selected' if estado == 'todos' }}>Todos</option>
      </select>
    </form>
    <a href="{{ url_for('usuario_nuevo') }}" class="btn btn-sm btn-primary"><i class="fas fa-user-plus mr-1"></i>Nuevo</a>
  </div>
</div>

<div class="card mb-5">
  <div class="card-body">
    <div class="table-responsive">
    <table id="tbl" class="table table-hover table-sm w-100">
      <thead>
        <tr><th>Nº</th><th>Usuario</th><th>Nombre</th><th>Unidad</th><th>Cumpleaños</th>
            <th>Alta</th><th>Último login</th><th>IP</th><th>Estado</th><th></th></tr>
      </thead>
      <tbody>
        {% for u in usuarios %}
        <tr class="{{ 'text-muted' if u.activo != 'S' }}">
          <td>{{ u.id }}</td>
          <td>
            <span class="avatar mr-1"><i class="fas fa-user"></i></span>{{ u.usuario }}
            {% if u.tiene_foto %}
              <a href="#" class="ver-foto ml-1" title="Ver foto"
                 data-src="{{ url_for('foto', uid=u.id) }}" data-nombre="{{ u.nombre_usuario }}"><i class="fas fa-image"></i></a>
            {% endif %}
          </td>
          <td>{{ u.nombre_usuario }}</td>
          <td>{{ u.unidad_negocio }}</td>
          <td>{{ u.mes_cumple|cumple(u.dia_cumple) }}</td>
          <!-- data-order: valor con el que DataTables ordena (el texto dd/mm/aaaa ordenaria mal) -->
          <td data-order="{{ u.fecha_alta.isoformat() if u.fecha_alta else '' }}">{{ u.fecha_alta|dt }}</td>
          <td data-order="{{ u.ultimo_login.isoformat() if u.ultimo_login else '' }}">{{ u.ultimo_login|dt }}</td>
          <td>{{ u.ultima_ip or '—' }}</td>
          <td>
            {% if u.activo == 'S' %}<span class="badge badge-success">Activo</span>
            {% else %}<span class="badge badge-secondary">Baja</span>{% endif %}
          </td>
          <td class="text-nowrap text-right">
            <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('usuario_editar', uid=u.id) }}" title="Editar"><i class="fas fa-edit"></i></a>
            <form method="post" action="{{ url_for('usuario_estado', uid=u.id) }}" class="d-inline"
                  onsubmit="return confirm('¿Confirmas el cambio de estado de este usuario?')">
              <input type="hidden" name="csrf" value="{{ csrf_token() }}">
              <input type="hidden" name="volver" value="{{ estado }}">
              {% if u.activo == 'S' %}
                <input type="hidden" name="accion" value="baja">
                <button class="btn btn-sm btn-outline-danger" title="Dar de baja"><i class="fas fa-user-slash"></i></button>
              {% else %}
                <input type="hidden" name="accion" value="alta">
                <button class="btn btn-sm btn-outline-success" title="Reactivar"><i class="fas fa-user-check"></i></button>
              {% endif %}
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
  </div>
</div>

<div class="modal fade" id="modalFoto" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h6 class="modal-title" id="fotoTitulo"></h6>
        <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
      </div>
      <div class="modal-body text-center"><img id="fotoImg" class="img-fluid rounded" alt="Foto de perfil"></div>
    </div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
  $('#tbl').DataTable({ language: DT_ES, order: [[0, 'asc']], columnDefs: [{ orderable: false, targets: -1 }] });
  // La foto se pide al servidor solo cuando se hace clic (pueden pesar hasta 8 MB).
  $(document).on('click', '.ver-foto', function (e) {
    e.preventDefault();
    $('#fotoTitulo').text($(this).data('nombre'));
    $('#fotoImg').attr('src', $(this).data('src'));
    $('#modalFoto').modal('show');
  });
  $('#modalFoto').on('hidden.bs.modal', function () { $('#fotoImg').attr('src', ''); });
</script>
{% endblock %}
"""

FORM = """{% extends "base.html" %}
{% block title %}{{ 'Nuevo usuario' if creando else 'Editar usuario' }}{% endblock %}
{% block contenido %}
<div class="row justify-content-center">
  <div class="col-lg-8">
    <div class="card mb-5">
      <div class="card-header">
        <i class="fas fa-user-edit mr-2"></i>{{ 'Nuevo usuario' if creando else ('Editar usuario Nº ' ~ u.id) }}
      </div>
      <div class="card-body">
        {% if errores %}
        <div class="alert alert-danger">
          <ul class="mb-0 pl-3">{% for e in errores %}<li>{{ e }}</li>{% endfor %}</ul>
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data"
              action="{{ url_for('usuario_nuevo') if creando else url_for('usuario_editar', uid=u.id) }}">
          <input type="hidden" name="csrf" value="{{ csrf_token() }}">

          <div class="form-row">
            <div class="form-group col-md-5">
              <label>Usuario</label>
              <input name="usuario" class="form-control" value="{{ u.usuario }}" maxlength="30"
                     {{ 'required' if creando else 'readonly' }}>
            </div>
            <div class="form-group col-md-7">
              <label>Nombre</label>
              <input name="nombre_usuario" class="form-control" value="{{ u.nombre_usuario }}" maxlength="100" required>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group col-md-6">
              <label>Unidad de negocio</label>
              <input name="unidad_negocio" class="form-control" value="{{ u.unidad_negocio }}" maxlength="100">
            </div>
            <div class="form-group col-md-3">
              <label>Cumpleaños: mes</label>
              <select name="mes_cumple" class="form-control">
                <option value="">—</option>
                {% for m in meses %}
                  <option value="{{ loop.index }}" {{ 'selected' if u.mes_cumple|string == loop.index|string }}>{{ m|capitalize }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="form-group col-md-3">
              <label>Día</label>
              <select name="dia_cumple" class="form-control">
                <option value="">—</option>
                {% for dd in range(1, 32) %}
                  <option value="{{ dd }}" {{ 'selected' if u.dia_cumple|string == dd|string }}>{{ dd }}</option>
                {% endfor %}
              </select>
            </div>
          </div>

          <div class="form-group">
            <label>Comentario</label>
            <input name="comentario" class="form-control" value="{{ u.comentario }}" maxlength="255">
          </div>

          <div class="form-row">
            <div class="form-group col-md-6">
              <label>{{ 'Contraseña' if creando else 'Nueva contraseña (vacía = no cambiar)' }}</label>
              <input type="password" name="clave" class="form-control" autocomplete="new-password"
                     minlength="8" {{ 'required' if creando }}>
            </div>
            <div class="form-group col-md-6">
              <label>Repetir contraseña</label>
              <input type="password" name="clave2" class="form-control" autocomplete="new-password">
            </div>
          </div>

          <div class="form-group">
            <label>Foto de perfil (solo JPG, máx. {{ max_mb }} MB)</label>
            {% if not creando and u.tiene_foto %}
              <div class="mb-2">
                <img src="{{ url_for('foto', uid=u.id) }}" alt="Foto actual" class="rounded" style="max-height:120px;">
                <div class="custom-control custom-checkbox mt-2">
                  <input type="checkbox" class="custom-control-input" id="quitar" name="quitar_foto" value="1">
                  <label class="custom-control-label" for="quitar">Quitar la foto actual</label>
                </div>
              </div>
            {% endif %}
            <input type="file" name="foto" id="foto" accept=".jpg,.jpeg,image/jpeg" class="form-control-file">
          </div>

          <button class="btn btn-primary"><i class="fas fa-save mr-1"></i>Guardar</button>
          <a href="{{ url_for('index') }}" class="btn btn-light">Cancelar</a>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
  // Aviso rapido en el navegador; la validacion real siempre es la del servidor.
  $('#foto').on('change', function () {
    var f = this.files[0];
    if (f && f.size > {{ max_mb }} * 1024 * 1024) {
      alert('La foto excede {{ max_mb }} MB.');
      this.value = '';
    }
  });
</script>
{% endblock %}
"""

app.jinja_loader = DictLoader({
    "base.html": BASE,
    "login.html": LOGIN,
    "index.html": INDEX,
    "form.html": FORM,
})


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5001, debug=True)
