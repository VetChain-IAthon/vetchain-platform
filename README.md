# VetChain · Backend

API de VetChain, la plataforma de inteligencia comercial para Mederi (importadora veterinaria, Perú).
Está hecha con FastAPI como **monolito modular**: una sola API con módulos independientes.

## Requisitos
- Python 3.11 o superior

## Instalación y ejecución

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # y completa los valores
python -m scripts.create_tables   # crea las tablas en la base
uvicorn app.main:app --reload
```

Con la API encendida:
- Documentación interactiva: http://localhost:8000/docs
- Estado general: http://localhost:8000/health

## Pruebas

```bash
pytest
```

## Estructura

```
app/
  main.py            punto de entrada: registra los módulos
  core/              núcleo compartido: configuración, base de datos, seguridad
  modules/           un módulo por carpeta (router, service, schemas, models)
docs/                arquitectura, base de datos y módulos
prompts/             textos que se envían a Gemini
scripts/             tareas sueltas: crear tablas, cargar CSV, entrenar el modelo
models/              model.json del modelo de predicción
tests/               pruebas
```

Más detalle en [`CLAUDE.md`](CLAUDE.md) y la carpeta [`docs/`](docs/).

## Despliegue en Render
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Variables de entorno: `DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `CORS_ORIGINS`
- Render publica solo cada vez que se sube código a la rama `main`.
