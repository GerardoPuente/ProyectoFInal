# ADR-001: Decisiones tecnicas de ClipShare

Fecha: 2026-09-30
Estado: aceptada

## Contexto

ClipShare es una plataforma de clips cortos (tema 1): los usuarios se registran,
suben videos de pocos minutos y los ven. La pieza distintiva obligatoria es un
**worker asincrono en su propio contenedor** que procesa cada clip despues de
subirlo (valida el formato, registra la duracion y genera una miniatura).

Restricciones: una sola persona, tiempo limitado, una cuenta de AWS Academy
(Learner Lab, rol `LabRole`, sin crear roles IAM propios), una instancia EC2
chica (2 GB de RAM) donde deben convivir dos contenedores y ffmpeg, y la
obligacion de justificar cada control del pipeline.

## Decisiones

### 1. Framework del backend

**Elegi:** FastAPI 0.142 sobre Python 3.12.
**Por que:** valida la entrada con tipos (Pydantic) y por defecto devuelve
errores JSON claros, lo que simplifica el codigo de registro/login y de subida.
Genera la documentacion de la API sola (`/docs`) y su rendimiento sobra para
este volumen.
**Que descarte y por que:** Flask. Es igual de valido y mas conocido, pero para
la subida de archivos y la validacion habria escrito a mano lo que FastAPI da
hecho. Django: demasiado framework (ORM, admin, plantillas) para 6 endpoints.

### 2. Separacion en servicios

**Elegi:** dos contenedores propios con `docker compose`:
`api` (FastAPI, expone el puerto 8000, atiende a los usuarios) y `worker`
(sin puerto; procesa clips con ffprobe/ffmpeg). Comparten el paquete
`clipshare/` (config, reglas, almacenamiento) pero tienen **imagenes distintas**.
**Por que:** el corte sigue el riesgo. ffmpeg y sus decodificadores procesan
archivos no confiables, asi que viven solo en el worker; la imagen del API no
los incluye (menos paquetes, menos CVE, menos superficie). Tambien permite
reiniciar o escalar el worker sin tocar la API: si un clip malicioso lo tumba,
los usuarios siguen viendo y subiendo clips.
**Como se comunican:** sin broker. El API inserta el clip en RDS con estado
`pendiente`; el worker lo toma con `SELECT ... FOR UPDATE SKIP LOCKED`, lo pasa a
`procesando` y despues a `listo` o `rechazado`. La base de datos funciona como
cola.
**Que descarte y por que:** (a) SQS o Redis como cola: es lo "correcto" para
escalar, pero agrega otro servicio, otra credencial y otro punto de falla para
un volumen que RDS maneja de sobra; `SKIP LOCKED` ya permite varios workers sin
pisarse. (b) Procesar dentro del request de subida: bloquearia la API y no
cumpliria el requisito de pieza separada. (c) Un solo contenedor con hilos: se
pierde el aislamiento de ffmpeg.

### 3. Almacenamiento

**Elegi:** los **bytes** van a S3 (clip original y miniatura) y los **datos**
a RDS PostgreSQL 15 (usuarios con hash scrypt, y por cada clip: titulo, autor,
estado, duracion, resolucion, codec, ruta en S3). El bucket es privado, con
acceso publico bloqueado, solo TLS, versionado y cifrado con una llave KMS
propia. El navegador reproduce con **URL firmadas de 15 minutos**; nunca hay
objetos publicos. El RDS esta cifrado, `publicly_accessible=false` y su grupo de
seguridad solo acepta el 5432 desde el grupo de la EC2.
**Por que:** un video no cabe razonablemente en una fila SQL, y S3 sirve el
archivo directo al navegador sin pasar por mi API (ahorra ancho de banda y CPU
de la instancia). En cambio, el estado del procesamiento y los usuarios son
datos relacionales que necesitan transacciones (por eso `SKIP LOCKED`).
**Acceso a AWS sin llaves:** la EC2 usa el perfil `LabInstanceProfile`; boto3 toma
las credenciales del rol. Por eso el `.env` no lleva llaves de AWS.
**Que descarte y por que:** MySQL/Aurora (PostgreSQL da `SKIP LOCKED` y UUID
nativos); DynamoDB (no necesito su escala y perderia las transacciones); guardar
los videos en el disco de la EC2 (se pierden con la instancia y no cumple el
requisito de S3); servir el video a traves de la API (consume el ancho de banda
de una instancia pequena).

### 4. Autenticacion

**Elegi:** registro y login propios; contrasenas con `scrypt` (libreria
estandar) y sesion como token firmado (`itsdangerous`) enviado en el encabezado
`Authorization`.
**Por que:** el requisito pide distinguir quien hace que, no un sistema de
identidad completo. Evita dependencias de criptografia extra (menos superficie
en el SBOM).
**Que descarte y por que:** Cognito (mas configuracion y permisos de los que da
el Learner Lab), JWT con PyJWT (equivalente, una dependencia mas).

### 5. Donde corre la aplicacion

**Elegi:** una EC2 `t3.small` en la VPC por defecto, creada con Terraform, con
Docker y Compose instalados por `user_data`. Sin SSH abierto: el acceso
administrativo es por SSM.
**Por que:** el RDS es privado y "alcanzable solo desde mi instancia", asi que la
app **tiene** que correr dentro de AWS; desde mi laptop no podria hablar con el.
Esa misma instancia es el entorno de QA que se reutilizara en la entrega final.
**Que descarte y por que:** ECS/Fargate o EKS (el Learner Lab limita permisos y
el requisito pide docker-compose); abrir el RDS al publico para probar desde la
laptop (viola el requisito de seguridad).

### 6. Imagen base

**Elegi:** `python:3.12.14-slim-trixie` (Debian 13), version fija.
**Por que:** mi primera corrida del pipeline bloqueo la imagen del worker por 6
CVE HIGH de `libexpat1` en `python:3.12.14-slim-bookworm`. `apt-get upgrade` no
las cerraba porque Debian 12 aun no publicaba el parche; trixie ya incluia la
version corregida.
**Que descarte y por que:** `alpine` (musl complica ffmpeg y los wheels de
psycopg), y quedarme en bookworm con una excepcion en Trivy (habria ocultado un
riesgo real en la imagen que procesa archivos de usuarios).

## Consecuencias

**Se facilito:** el worker basado en la base de datos no necesito ninguna
infraestructura extra y es facil de probar localmente con un Postgres y un S3
simulado. Separar API y worker hizo evidente que ffmpeg solo debia estar en una
imagen. Usar el rol de la instancia elimino el manejo de llaves de AWS.

**Se complico:**
- La app solo se puede probar de extremo a extremo dentro de AWS (el RDS es
  privado); para desarrollar local use un Postgres en contenedor
  (`docker-compose.local.yml`) y un S3 simulado, que no son identicos al real.
- El polling de la base de datos (cada 3 s) no escala como una cola real y
  agrega consultas constantes al RDS; es aceptable aqui y es el primer cambio
  que haria para produccion.
- La app va por HTTP, sin TLS; es una deuda declarada en la tabla de
  decisiones del pipeline.
- Las credenciales del Learner Lab son temporales: la sesion caduca y hay que
  renovar las variables de entorno para volver a usar la consola o Terraform.
- El SBOM se genera solo de la imagen del worker (superconjunto del API); no es
  un SBOM por servicio.
