"""
recargas.py - Control de recargas de celulares (ejercicio de fogueo Flask + MySQL)

Un solo archivo. Requisitos (todo instalable offline con wheels):
    pip install flask pymysql

Estructura esperada junto a este archivo (librerias locales, sin CDN):
    static/vendor/bootstrap-4.6.2/css/bootstrap.min.css
    static/vendor/bootstrap-4.6.2/js/bootstrap.bundle.min.js
    static/vendor/fontawesome-5.15.4/css/all.min.css      (y ../webfonts/ al lado)
    static/vendor/jquery/jquery.min.js
    static/vendor/datatables/css/dataTables.bootstrap4.min.css
    static/vendor/datatables/js/jquery.dataTables.min.js
    static/vendor/datatables/js/dataTables.bootstrap4.min.js

Correr:  python recargas.py   ->  http://127.0.0.1:5000

Comparativo rapido con PHP (para ubicarte):
    $_GET / $_POST            ->  request.args / request.form
    header('Location: ...')   ->  return redirect(url_for(...))
    $_SESSION['msg']          ->  flash(...) y get_flashed_messages() (usa session por dentro)
    include / plantillas      ->  Jinja2 ({% extends %}, {% block %}, {{ var }})
    htmlspecialchars()        ->  Jinja2 lo hace SOLO (autoescape)
    PDO prepare/execute       ->  cursor.execute(sql, (args,))  con %s
"""
import os
from datetime import date
from decimal import Decimal, InvalidOperation

import pymysql
import pymysql.cursors
from flask import (Flask, abort, flash, redirect, render_template,
                   request, url_for)
from jinja2 import DictLoader

# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------
DB_NAME = "practica_recargas"
DB_CFG = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),   # define la variable de entorno DB_PASSWORD
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,   # filas como diccionarios (como PDO::FETCH_ASSOC)
    autocommit=True,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-serio")   # necesaria para session/flash


# ----------------------------------------------------------------------------
# Base de datos
# ----------------------------------------------------------------------------
def conectar(con_bd=True):
    cfg = dict(DB_CFG)
    if con_bd:
        cfg["database"] = DB_NAME
    return pymysql.connect(**cfg)


def consulta(sql, args=(), uno=False):
    """SELECT. Devuelve lista de dicts (o un dict / None si uno=True)."""
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if uno else cur.fetchall()
    finally:
        con.close()


def ejecuta(sql, args=()):
    """INSERT/UPDATE/DELETE. Devuelve el id insertado."""
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(sql, args)
            return cur.lastrowid
    finally:
        con.close()


def init_db():
    """Crea la BD y las dos tablas si no existen."""
    con = conectar(con_bd=False)
    try:
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    finally:
        con.close()

    ejecuta("""
        CREATE TABLE IF NOT EXISTS celulares (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            telefono   VARCHAR(15)  NOT NULL UNIQUE,
            comentario VARCHAR(255) NOT NULL DEFAULT '',
            creado     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    ejecuta("""
        CREATE TABLE IF NOT EXISTS recargas (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            celular_id INT           NOT NULL,
            fecha      DATE          NOT NULL,
            importe    DECIMAL(10,2) NOT NULL,
            comentario VARCHAR(255)  NOT NULL DEFAULT '',
            creado     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_celular_fecha (celular_id, fecha),
            FOREIGN KEY (celular_id) REFERENCES celulares(id)
        ) ENGINE=InnoDB
    """)


# ----------------------------------------------------------------------------
# Filtro de plantilla: {{ valor|mxn }}
# ----------------------------------------------------------------------------
@app.template_filter("mxn")
def mxn(valor):
    return "${:,.2f}".format(valor or 0)


# ----------------------------------------------------------------------------
# Rutas
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    celulares = consulta("""
        SELECT c.id, c.telefono, c.comentario,
               MAX(r.fecha)                AS ultima,
               COUNT(r.id)                 AS n_recargas,
               COALESCE(SUM(r.importe), 0) AS total
          FROM celulares c
          LEFT JOIN recargas r ON r.celular_id = c.id
         GROUP BY c.id
         ORDER BY c.telefono
    """)
    return render_template("index.html", celulares=celulares, hoy=date.today().isoformat())


@app.route("/celular", methods=["POST"])
def celular_nuevo():
    telefono = request.form.get("telefono", "").strip()
    comentario = request.form.get("comentario", "").strip()[:255]

    if not (telefono.isdigit() and len(telefono) == 10):
        flash("El teléfono debe tener 10 dígitos.", "danger")
        return redirect(url_for("index"))
    try:
        ejecuta("INSERT INTO celulares (telefono, comentario) VALUES (%s, %s)",
                (telefono, comentario))
        flash(f"Celular {telefono} registrado.", "success")
    except pymysql.err.IntegrityError:
        flash(f"El teléfono {telefono} ya existe.", "warning")

    # PRG: despues de un POST SIEMPRE redirect. Asi F5 repite el GET, no el POST.
    return redirect(url_for("index"))


@app.route("/recarga", methods=["POST"])
def recarga_nueva():
    try:
        celular_id = int(request.form.get("celular_id", ""))
        fecha = date.fromisoformat(request.form.get("fecha", ""))
        importe = Decimal(request.form.get("importe", "").replace(",", "")).quantize(Decimal("0.01"))
        if importe <= 0:
            raise ValueError("importe")
    except (ValueError, InvalidOperation):
        flash("Revisa los datos: celular, fecha e importe (mayor a 0).", "danger")
        return redirect(url_for("index"))

    if not consulta("SELECT id FROM celulares WHERE id = %s", (celular_id,), uno=True):
        flash("Ese celular no existe.", "danger")
        return redirect(url_for("index"))

    comentario = request.form.get("comentario", "").strip()[:255]
    ejecuta("INSERT INTO recargas (celular_id, fecha, importe, comentario) VALUES (%s, %s, %s, %s)",
            (celular_id, fecha, importe, comentario))
    flash(f"Recarga de {mxn(importe)} registrada.", "success")
    return redirect(url_for("index"))


@app.route("/historial/<int:celular_id>")
def historial(celular_id):
    cel = consulta("SELECT * FROM celulares WHERE id = %s", (celular_id,), uno=True)
    if not cel:
        abort(404)

    # Filtros por GET (opcionales): ?desde=2026-01-01&hasta=2026-12-31
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()

    sql = "SELECT id, fecha, importe, comentario FROM recargas WHERE celular_id = %s"
    args = [celular_id]
    try:
        if desde:
            args.append(date.fromisoformat(desde)); sql += " AND fecha >= %s"
        if hasta:
            args.append(date.fromisoformat(hasta)); sql += " AND fecha <= %s"
    except ValueError:
        flash("Fecha de filtro inválida.", "warning")
        return redirect(url_for("historial", celular_id=celular_id))
    sql += " ORDER BY fecha DESC, id DESC"

    filas = consulta(sql, tuple(args))
    total = sum((f["importe"] for f in filas), Decimal("0"))
    return render_template("historial.html", cel=cel, filas=filas, total=total,
                           desde=desde, hasta=hasta)


# ----------------------------------------------------------------------------
# Plantillas (Jinja2). Van en un dict para mantener TODO en un solo archivo.
# ----------------------------------------------------------------------------
BASE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Recargas{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap-4.6.2/css/bootstrap.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/fontawesome-5.15.4/css/all.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/datatables/css/dataTables.bootstrap4.min.css') }}">
  <style>
    body { background:#f4f6f9; color:#2b3440; }
    .navbar { background:#1f2d3d; }
    .card { border:0; box-shadow:0 1px 3px rgba(0,0,0,.08); }
    .card-header { background:#fff; font-weight:600; border-bottom:1px solid #e9edf2; }
    .table thead th { border-top:0; color:#5b6b7b; font-size:.85rem; text-transform:uppercase; letter-spacing:.03em; }
    .num { text-align:right; font-variant-numeric:tabular-nums; }
  </style>
</head>
<body>
  <nav class="navbar navbar-dark mb-4">
    <a class="navbar-brand" href="{{ url_for('index') }}"><i class="fas fa-mobile-alt mr-2"></i>Control de recargas</a>
  </nav>
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
    // Idioma de DataTables embebido (evita cargar el archivo i18n)
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

INDEX = """{% extends "base.html" %}
{% block contenido %}
<div class="row">
  <div class="col-md-5 mb-4">
    <div class="card h-100">
      <div class="card-header"><i class="fas fa-plus-circle mr-2 text-primary"></i>Nuevo celular</div>
      <div class="card-body">
        <form method="post" action="{{ url_for('celular_nuevo') }}">
          <div class="form-group">
            <label>Teléfono (10 dígitos)</label>
            <input name="telefono" class="form-control" maxlength="10" pattern="[0-9]{10}" required>
          </div>
          <div class="form-group">
            <label>Comentario</label>
            <input name="comentario" class="form-control" maxlength="255">
          </div>
          <button class="btn btn-primary"><i class="fas fa-save mr-1"></i>Guardar</button>
        </form>
      </div>
    </div>
  </div>

  <div class="col-md-7 mb-4">
    <div class="card h-100">
      <div class="card-header"><i class="fas fa-coins mr-2 text-success"></i>Registrar recarga</div>
      <div class="card-body">
        <form method="post" action="{{ url_for('recarga_nueva') }}">
          <div class="form-row">
            <div class="form-group col-md-6">
              <label>Celular</label>
              <select name="celular_id" class="form-control" required>
                <option value="">— elige —</option>
                {% for c in celulares %}
                  <option value="{{ c.id }}">{{ c.telefono }}{% if c.comentario %} · {{ c.comentario }}{% endif %}</option>
                {% endfor %}
              </select>
            </div>
            <div class="form-group col-md-3">
              <label>Fecha</label>
              <input type="date" name="fecha" class="form-control" value="{{ hoy }}" required>
            </div>
            <div class="form-group col-md-3">
              <label>Importe</label>
              <input name="importe" class="form-control num" inputmode="decimal" placeholder="0.00" required>
            </div>
          </div>
          <div class="form-group">
            <label>Comentario</label>
            <input name="comentario" class="form-control" maxlength="255">
          </div>
          <button class="btn btn-success"><i class="fas fa-check mr-1"></i>Registrar</button>
        </form>
      </div>
    </div>
  </div>
</div>

<div class="card mb-5">
  <div class="card-header"><i class="fas fa-list mr-2"></i>Celulares</div>
  <div class="card-body">
    <table id="tbl" class="table table-hover table-sm w-100">
      <thead>
        <tr><th>Teléfono</th><th>Comentario</th><th>Última recarga</th>
            <th class="num">Recargas</th><th class="num">Total</th><th></th></tr>
      </thead>
      <tbody>
        {% for c in celulares %}
        <tr>
          <td>{{ c.telefono }}</td>
          <td>{{ c.comentario }}</td>
          <td>{{ c.ultima or '—' }}</td>
          <td class="num">{{ c.n_recargas }}</td>
          <td class="num">{{ c.total|mxn }}</td>
          <td class="text-right">
            <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('historial', celular_id=c.id) }}">
              <i class="fas fa-history mr-1"></i>Historial</a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
  $('#tbl').DataTable({ language: DT_ES, pageLength: 10, columnDefs: [{ orderable: false, targets: 5 }] });
</script>
{% endblock %}
"""

HISTORIAL = """{% extends "base.html" %}
{% block title %}Historial {{ cel.telefono }}{% endblock %}
{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h5 class="mb-0"><i class="fas fa-history mr-2"></i>Historial de {{ cel.telefono }}
    {% if cel.comentario %}<small class="text-muted"> · {{ cel.comentario }}</small>{% endif %}</h5>
  <a href="{{ url_for('index') }}" class="btn btn-sm btn-outline-secondary"><i class="fas fa-arrow-left mr-1"></i>Volver</a>
</div>

<div class="card mb-3">
  <div class="card-body py-3">
    <!-- Filtro por GET: la URL queda compartible y F5 no re-envia nada -->
    <form method="get" class="form-inline">
      <label class="mr-2">Desde</label>
      <input type="date" name="desde" value="{{ desde }}" class="form-control form-control-sm mr-3">
      <label class="mr-2">Hasta</label>
      <input type="date" name="hasta" value="{{ hasta }}" class="form-control form-control-sm mr-3">
      <button class="btn btn-sm btn-primary mr-2"><i class="fas fa-filter mr-1"></i>Filtrar</button>
      <a class="btn btn-sm btn-light" href="{{ url_for('historial', celular_id=cel.id) }}">Limpiar</a>
    </form>
  </div>
</div>

<div class="card mb-5">
  <div class="card-body">
    <table id="tbl" class="table table-hover table-sm w-100">
      <thead><tr><th>Fecha</th><th class="num">Importe</th><th>Comentario</th></tr></thead>
      <tbody>
        {% for f in filas %}
        <tr>
          <td>{{ f.fecha }}</td>
          <td class="num">{{ f.importe|mxn }}</td>
          <td>{{ f.comentario }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr><th>Total ({{ filas|length }})</th><th class="num">{{ total|mxn }}</th><th></th></tr>
      </tfoot>
    </table>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
  // order: columna 0 (fecha) descendente. Las fechas ISO ordenan bien como texto.
  $('#tbl').DataTable({ language: DT_ES, order: [[0, 'desc']], pageLength: 25 });
</script>
{% endblock %}
"""

app.jinja_loader = DictLoader({
    "base.html": BASE,
    "index.html": INDEX,
    "historial.html": HISTORIAL,
})


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
