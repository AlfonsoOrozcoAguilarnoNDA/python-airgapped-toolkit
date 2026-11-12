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
