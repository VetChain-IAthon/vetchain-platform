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
alembic upgrade head              # crea o actualiza las tablas (migraciones)
python -m scripts.load_csv         # carga los 7 CSV de data/ (no se suben al repo)
python -m scripts.seed_users       # crea gerencia y vendedor iniciales (SEED_* en .env)
uvicorn app.main:app --reload
```

Con la API encendida:
- Documentación interactiva: http://localhost:8000/docs
- Estado general: http://localhost:8000/health
- API bajo http://localhost:8000/api/v1 (contrato en `docs/endpoints.md`)

## Pruebas

```bash
pytest
```

## Estructura

```
app/
  infrastructure/    base de datos compartida: ORM de Defontana, unidad de trabajo, consultas, cargador CSV
  main.py            punto de entrada: registra los módulos
  core/              núcleo compartido: configuración, base de datos, seguridad
  modules/           un módulo por carpeta, en capas: domain, application, infrastructure, interface
docs/                arquitectura, contrato de capas, base de datos y módulos
prompts/             textos que se envían a Gemini
scripts/             tareas sueltas: crear tablas, cargar CSV, entrenar el modelo
models/              model.json del modelo de predicción
tests/               pruebas
```

Más detalle en [`CLAUDE.md`](CLAUDE.md) y la carpeta [`docs/`](docs/).

## Despliegue en Render

El archivo [`render.yaml`](render.yaml) prepara un servicio Python en Ohio, cerca de la base de Neon.
Usa Python 3.13, verifica `/health` y ejecuta `alembic upgrade head` antes de cada despliegue.
El plan indicado es de pago; los comandos previos al despliegue no están disponibles en el plan gratuito.
Los despliegues automáticos están desactivados hasta que se configure el servicio y se elija la rama que se publicará.

Al crear el Blueprint en Render, define `DATABASE_URL` con la conexión **directa** de Neon
(`sslmode=require`, sin `-pooler`) y `CORS_ORIGINS` con el origen HTTPS exacto de Vercel, sin `/` final.
Render genera `JWT_SECRET`. Configura `GEMINI_API_KEY` solo si vas a utilizar las funciones de IA.
No copies el `.env` local a Render. Después de publicar, comprueba `https://<servicio>.onrender.com/health`.
La API ya usa los datos precargados en Neon; no vuelvas a subir los CSV a Render.

## Precarga inicial de Neon

Desde la carpeta del backend, exporta en tu terminal la **conexión directa** de Neon. Debe incluir
`sslmode=require` y no llevar `-pooler` en el host. No pegues esa URL en el repositorio ni en un comando que vayas a compartir.
Los siete CSV deben estar en `data/` o en la carpeta indicada con `--csv-dir`.

```bash
export DATABASE_URL='postgresql://USUARIO:CLAVE@HOST.neon.tech/BASE?sslmode=require'
python -m scripts.setup_neon                  # valida sin escribir
python -m scripts.setup_neon --apply          # migraciones y carga de los siete CSV
```

Para crear también los usuarios iniciales, usa las variables `SEED_*` del `.env` local de forma explícita:

```bash
python -m scripts.setup_neon --seed-users --seed-env-file .env          # valida sin escribir
python -m scripts.setup_neon --apply --seed-users --seed-env-file .env  # carga CSV y crea usuarios
```

El `.env` local contiene las credenciales iniciales acordadas para gerencia y vendedor; no se sube al repositorio.
La URL de Neon siempre debe exportarse por separado en `DATABASE_URL`: el script no toma la URL local del `.env`.
Sin `--seed-env-file`, también puedes exportar las variables `SEED_*` en la terminal.
La carga hace upsert y puede repetirse, pero si hay filas rechazadas
termina con error después de mostrar el reporte; revisa los conteos en Neon antes de continuar.
