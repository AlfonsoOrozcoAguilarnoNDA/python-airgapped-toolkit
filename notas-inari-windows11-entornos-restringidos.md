# Guía de Entorno: Windows 11 (desarrollo/red interna) y Debian 13 (producción)

> **Objetivo**: Documentar cómo montar el entorno en una máquina Windows 11 con
> políticas restrictivas (sin WAMP/XAMPP funcional), y cómo debe verse la misma
> aplicación en un servidor Debian 13 de producción.
>
> **Filosofía**: En Windows se instala a mano, paquete por paquete, verificando
> cada paso. En Linux se replica con `requirements.txt` y usuarios de sistema
> separados. La idea es poder ir instalando manualmente lo que falta si no hay
> `venv` disponible, y entender qué hace cada comando.

---

## Parte 1 — Windows 11 (desarrollo / red interna)

### 1.1 Contexto

Esta máquina puede tener:
- Python instalado desde **Microsoft Store** (no recomendado para desarrollo).
- Políticas que bloquean instaladores como WAMP/XAMPP.
- Alias de ejecución que redirigen `python` a la Store.

Por eso se usa **Inari (SushiBox)** como servidor portable (Nginx + PHP + MySQL),
y **Python con `venv`** para el backend Flask.

### 1.2 Requisitos previos

| Componente | Cómo verificarlo | Nota |
|---|---|---|
| Python oficial (python.org) | `python --version` | Si abre la Store, desactivar alias en "Administrar alias de ejecución de aplicaciones" |
| `pip` funcional | `python -m pip --version` | Usar siempre `python -m pip`, no `pip` a secas |
| Inari descargado | — | Ver `README` de este repo para el enlace/respaldo |
| MySQL (si se usa) | Servicio `MySQL80` en ejecución | Instalar con MySQL Installer oficial |

### 1.3 Crear el entorno virtual e instalar dependencias

```bash
# Crear el venv
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# Instalar todo desde el archivo de requerimientos
python -m pip install -r requirements.txt

### NOTAS DE INSTALACIÓN Y TROUBLESHOOTING

Inari en entornos restringidos: Windows 11 sin administrador y redes internas segmentadas

Objetivo: Documentar cómo montar el entorno en una máquina Windows 11 con
políticas restrictivas (sin WAMP/XAMPP funcional), y cómo debe verse la misma
aplicación en un servidor Debian 13 de producción.

Filosofía: En Windows se instala a mano, paquete por paquete, verificando cada
paso. En Linux se replica con requirements.txt y usuarios de sistema separados.
La idea es poder ir instalando manualmente lo que falta si no hay venv
disponible, y entender qué hace cada comando.


=====================================================================
PARTE 1 - WINDOWS 11 (DESARROLLO / RED INTERNA)
=====================================================================

### 1.1 CONTEXTO

Esta máquina puede tener:
- Python instalado desde Microsoft Store (no recomendado para desarrollo).
- Políticas que bloquean instaladores como WAMP/XAMPP.
- Alias de ejecución que redirigen python a la Store.

Por eso se usa Inari (SushiBox) como servidor portable (Nginx + PHP + MySQL),
y Python con venv para el backend Flask.

1.2 REQUISITOS PREVIOS

Componente              Cómo verificarlo                          Nota
----------------------  ----------------------------------------  ------------------------------------------
Python oficial          python --version                          Si abre la Store, desactivar alias en
(python.org)                                                      "Administrar alias de ejecución de aplicaciones"
pip funcional           python -m pip --version                   Usar siempre python -m pip, no pip a secas
Inari descargado        (ver README del repo)                     Ver enlace/respaldo en este repositorio
MySQL (si se usa)       Servicio MySQL80 en ejecución             Instalar con MySQL Installer oficial

1.3 CREAR EL ENTORNO VIRTUAL E INSTALAR DEPENDENCIAS

python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt

Si NO hay venv o se quiere instalar manualmente paquete por paquete:

python -m pip install Flask
python -m pip install flask-cors
python -m pip install SQLAlchemy
python -m pip install Flask-SQLAlchemy
python -m pip install PyMySQL
python -m pip install fpdf2
python -m pip install "qrcode[pil]"
python -m pip install python-dotenv
python -m pip install pycryptodome
python -m pip install PyJWT
python -m pip install numpy
python -m pip install pandas
python -m pip install pysftp-ng
python -m pip install msoffcrypto-tool

IMPORTANTE: usar python -m pip garantiza que el paquete se instala en el
Python del venv activo, no en el de la Store ni en el global.

1.4 VERIFICAR CADA PAQUETE

python -c "import flask; print(flask.__version__)"
python -c "import flask_cors; print('flask-cors OK')"
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
python -c "import pymysql; print(pymysql.__version__)"
python -c "from fpdf import FPDF; print('fpdf2 OK')"
python -c "import qrcode; print('qrcode OK')"
python -c "import dotenv; print(dotenv.__version__)"
python -c "from Crypto.Cipher import AES; print('pycryptodome OK')"
python -c "import jwt; print(jwt.__version__)"
python -c "import numpy; print(numpy.__version__)"
python -c "import pandas; print(pandas.__version__)"
python -c "import pysftp; print('pysftp-ng OK')"
python -c "import msoffcrypto; print('msoffcrypto OK')"

1.5 ARRANCAR EL SISTEMA

1. Abrir Inari y activar Nginx + PHP (+ MySQL si aplica).
2. Copiar el frontend PHP a sites/default (o el web root configurado).
3. Lanzar el backend Flask:
   python app.py
   Debe mostrar: Running on http://0.0.0.0:5006 (o el puerto configurado).
4. Abrir en el navegador:
   http://127.0.0.1:8080/login.php

1.6 VERIFICAR QUE EL FLASK ESTÁ CORRIENDO

netstat -ano | findstr :5006
tasklist /FI "PID eq NUMERO_DE_PID"

Si aparece LISTENING y python.exe, está activo.

1.7 PROBLEMAS CONOCIDOS EN WINDOWS

Síntoma                              Causa                          Solución
-----------------------------------  -----------------------------  ------------------------------------------
ModuleNotFoundError: flask_cors      pip instaló en otro Python     Usar python -m pip install flask-cors
python abre la Store                 Alias de ejecución activo      Desactivar alias en Configuración
pysftp da ImportError: DSSKey        Paquete original obsoleto      Instalar pysftp-ng
Firewall bloquea desde otra máquina  Regla de entrada faltante      Permitir Python en Firewall de Windows


=====================================================================
PARTE 2 - DEBIAN 13 (PRODUCCIÓN)
=====================================================================

2.1 ESTRUCTURA INICIAL

/var/www/mi-app/
  frontend/          PHP (servido por Nginx + PHP-FPM)
    login.php
  backend/           Flask
    app.py
    requirements.txt
    venv/
  .env               Variables de entorno (NO en git)

2.2 PAQUETES DEL SISTEMA (APT)

sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx php-fpm php-mysql python3 python3-venv python3-pip mysql-server

apt gestiona el SISTEMA OPERATIVO (kernel, librerías del sistema).
NO gestiona las dependencias de tu aplicación Python; para eso está pip
dentro del venv.

2.3 BACKEND FLASK

cd /var/www/mi-app/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

NOTA: gunicorn también debe estar en requirements.txt o instalarse
explícitamente en el venv de producción.

2.4 SERVICIO SYSTEMD PARA GUNICORN (EJEMPLO)

Archivo: /etc/systemd/system/mi-app.service

[Unit]
Description=Mi App Flask
After=network.target

[Service]
User=flaskapp
Group=flaskapp
WorkingDirectory=/var/www/mi-app/backend
Environment="PATH=/var/www/mi-app/backend/venv/bin"
ExecStart=/var/www/mi-app/backend/venv/bin/gunicorn -w 4 -b 127.0.0.1:5006 app:app
Restart=always

[Install]
WantedBy=multi-user.target

sudo systemctl daemon-reload
sudo systemctl enable --now mi-app

2.5 NGINX COMO PROXY INVERSO

Archivo: /etc/nginx/sites-available/mi-app

server {
    listen 80;
    server_name _;

    root /var/www/mi-app/frontend;
    index login.php index.php;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5006/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

sudo ln -s /etc/nginx/sites-available/mi-app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

2.6 PERMISOS (EL FIN DEL "FRANKESTEIN")

sudo chown -R www-data:www-data /var/www/mi-app/frontend
sudo find /var/www/mi-app/frontend -type d -exec chmod 755 {} \;
sudo find /var/www/mi-app/frontend -type f -exec chmod 644 {} \;

sudo useradd -r -s /bin/false flaskapp
sudo chown -R flaskapp:flaskapp /var/www/mi-app/backend

REGLA DE ORO: nunca chmod 777. Directorios 755, archivos 644.
Solo las carpetas de escritura (uploads/storage) van a 775 para el grupo.

2.7 SOBRE HTTPS EN RED PRIVADA

La red privada reduce el riesgo externo, pero NO cifra las credenciales de
login.php si viajan por HTTP. Opciones:

1. Certificado autofirmado en Nginx (rápido, el navegador advierte).
2. CA interna: generar una CA propia y distribuir el certificado raíz a las
   máquinas de la red (sin advertencias).


=====================================================================
PARTE 3 - NOTAS SOBRE VERSIONES Y RESPONSABILIDADES
=====================================================================

3.1 LAS VERSIONES DEPENDEN DE requirements.txt

Las versiones de Python, Flask, SQLAlchemy, pandas, numpy, etc. que se
instalan en el venv NO se eligen al azar: deben ser las que estén fijadas
en requirements.txt, que a su vez es responsabilidad del desarrollador.

- El desarrollador decide y fija las versiones (probándolas en desarrollo).
- Producción solo ejecuta pip install -r requirements.txt.
- El sistema operativo (Debian 13) aporta Python 3.11/3.12 y las librerías
  del sistema; no las versiones de las librerías de la aplicación.

3.2 LAS VERSIONES DE APACHE/NGINX/SO SON INDEPENDIENTES

Las versiones de Nginx, Apache, PHP-FPM y del sistema operativo (Debian 13)
las define el administrador del servidor, no el requirements.txt. Lo que sí
debe coincidir es la compatibilidad:

Componente            Quién decide la versión              Dónde se documenta
--------------------  -----------------------------------  ---------------------------
Python (intérprete)   Desarrollador (.python-version)      README del repo
Librerías Python      Desarrollador (requirements.txt)     requirements.txt
Nginx / PHP-FPM       Administrador del servidor           Documentación de infraestructura
MySQL / MariaDB       Administrador del servidor           Documentación de infraestructura
SO (Debian 13)        Administrador del servidor           Documentación de infraestructura

EN RESUMEN: requirements.txt manda sobre las librerías Python. El sistema
operativo y el servidor web son un contrato aparte entre desarrollo e
infraestructura. Si una versión de Python del SO no es compatible con una
librería del requirements.txt, se resuelve instalando la versión de Python
adecuada (por ejemplo, con pyenv o los repositorios oficiales de Python),
no "actualizando todo" a ciegas.


=====================================================================
PARTE 4 - REFERENCIA RÁPIDA DE COMANDOS
=====================================================================

Comando                                              Para qué sirve
---------------------------------------------------  ------------------------------------------
python -m venv venv                                  Crea el entorno virtual aislado
venv\Scripts\activate (Win)                          Activa el venv
source venv/bin/activate (Linux)                     Activa el venv
python -m pip install -r requirements.txt            Instala las dependencias fijadas
python -m pip freeze > requirements.txt              Congela las versiones instaladas
python -c "import X"                                 Verifica que un paquete se importa
netstat -ano | findstr :5006 (Win)                   Verifica que el puerto está escuchando
systemctl status mi-app (Linux)                      Verifica el servicio Gunicorn
nginx -t (Linux)                                     Valida la configuración de Nginx
