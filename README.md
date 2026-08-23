# RefreshBrowser

Refresca navegadores (Chrome, Edge, Firefox, Brave) en intervalos configurables, con aviso 30 segundos antes del refresco.

## Requisitos

- **Windows**
- **Python 3.11** (no usar 3.12+ ni 3.14; las dependencias están fijadas para 3.11)

```powershell
py -3.11 --version
```

Si no lo tienes instalado:

```powershell
winget install Python.Python.3.11
```

## Instalación

```powershell
git clone https://github.com/carolus-dev/RefreshBrowser.git
cd RefreshBrowser

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

## Ejecutar

```powershell
python main.py
```

## Tests

```powershell
pytest tests/ -v
```

## Compilar .exe

```powershell
pyinstaller RefreshBrowser.spec
```

El ejecutable queda en `dist\RefreshBrowser.exe`.
