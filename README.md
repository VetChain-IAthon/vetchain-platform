# VetChain · Backend

API de VetChain, la plataforma de inteligencia comercial para **Mederi Pharma**, importadora veterinaria en Perú. Reúne datos de clientes, pedidos, productos, stock, cobros y vendedores de Defontana para apoyar el seguimiento comercial y los reportes de gerencia. Un pedido se presenta como pedido; no se asume que sea una venta facturada.

Este repositorio contiene la API. La aplicación web está en [vetchain-web-application](https://github.com/VetChain-IAthon/vetchain-web-application). En conjunto forman la solución; cada repositorio se instala por separado. La API está hecha con FastAPI como **monolito modular**.

## Funciones

- Sesiones y roles de gerencia y vendedor; el backend restringe la cartera visible para cada vendedor.
- Consulta de clientes, cotizaciones, reportes y reglas del negocio.
- Planificación de importación ilustrativa con cuatro laboratorios ficticios y decisiones de revisión guardadas; no genera compras. Esta fase no usa IA.
- Importación de siete CSV de Defontana con revisión y carga. Los datos reales de Mederi no se publican en Git.
- Pronóstico por producto: compara Extra Trees con un promedio móvil de seis meses para escenarios A/B y horizontes de uno o tres meses. Lee los pedidos de la base de datos y requiere cuatro artefactos privados; [guía de integración](docs/pronosticos.md).
- Envío de reportes por Resend desde un dominio propio verificado o desde el Gmail que cada usuario conecte con Google OAuth. Los PDF los genera la web.
- Identificación del origen de las cifras: `real`, `estimated`, `synthetic` o `simulated`; se avisa cuando faltan datos para una conclusión confiable.

## Requisitos
- Python 3.11 o superior
- Para datos reales, los siete CSV proporcionados por Mederi; no se incluyen en este repositorio.
- Para correo real, Resend o credenciales OAuth de Google, según el remitente. Son opcionales para levantar la API.

## Instalación y ejecución

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # cambia JWT_SECRET antes de usar cuentas reales
alembic upgrade head              # crea o actualiza las tablas (migraciones)
uvicorn app.main:app --reload
```

El ejemplo usa SQLite. Sin los CSV, las consultas comerciales estarán vacías. Si cuentas con los archivos, colócalos en `data/` o pasa la ruta de su carpeta; la carga hace *upsert* y no borra registros. Después completa `SEED_*` en `.env` y crea los usuarios iniciales. El vendedor necesita un código activo cargado desde los CSV:

```bash
python -m scripts.load_csv             # o: python -m scripts.load_csv /ruta/a/csv
python -m scripts.seed_users
```

Con la API encendida:
- Documentación interactiva: http://localhost:8000/docs
- Estado general: http://localhost:8000/health
- API bajo http://localhost:8000/api/v1 (contrato en `docs/endpoints.md`)

La web se inicia aparte siguiendo su [README](https://github.com/VetChain-IAthon/vetchain-web-application#readme) y debe apuntar a `http://localhost:8000`.

## Configuración del correo

- **Resend:** `RESEND_API_KEY` y un dominio remitente verificado. Sin clave, esos envíos solo se registran como simulación.
- **Gmail de cada usuario:** habilita Gmail API y crea un cliente OAuth web en Google Cloud. Configura `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_TOKEN_KEY`, `GOOGLE_OAUTH_REDIRECT_URI` y `FRONTEND_URL` en el servidor. En local, registra exactamente `http://localhost:8000/api/v1/gmail/callback` como URI de redirección. Cada persona conecta su cuenta desde **Mi perfil**, sin entregar contraseña SMTP; el token de actualización queda cifrado.
- `GMAIL_SMTP_EMAIL` y `GMAIL_SMTP_APP_PASSWORD` solo conservan compatibilidad con una cuenta compartida previamente autorizada; no son necesarios para Gmail personal con OAuth.

El permiso `gmail.send` puede requerir verificación de Google antes de abrir el acceso al público. Más detalle en [docs/endpoints.md](docs/endpoints.md).

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
scripts/             tareas sueltas: crear tablas y cargar CSV; entrenamiento de recompra pendiente
models/              reservado para el modelo de recompra pendiente; Extra Trees se mantiene privado fuera del repo
tests/               pruebas
alembic/             migraciones de la base de datos
```

Más detalle en [`CLAUDE.md`](CLAUDE.md) y la carpeta [`docs/`](docs/).
Los archivos `.env`, bases locales y `data/*` están excluidos por `.gitignore`. [`.env.example`](.env.example) no contiene claves reales.
Los artefactos Extra Trees no se publican en Git; configura `FORECAST_MODELS_DIR` con un directorio privado que los contenga.

## Despliegue en Render

El archivo [`render.yaml`](render.yaml) prepara un servicio Python en Ohio, cerca de la base de Neon.
Usa Python 3.13, verifica `/health` y ejecuta `alembic upgrade head` antes de cada despliegue.
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

**Enlace al repositorio:** [VetChain-IAthon/vetchain-platform](https://github.com/VetChain-IAthon/vetchain-platform).
