# ClipShare

> Avance 2 del Reto - LSCA2314 - Periodo AD26
> Alumno: [COMPLETAR]   |   Matricula: [COMPLETAR]   |   Tema elegido: 1 - Clips cortos

## Que hace esta aplicacion

ClipShare es una plataforma donde los usuarios se registran, inician sesion,
suben videos de pocos minutos y los ven. Despues de cada subida, un **worker
asincrono** (contenedor aparte) valida que el archivo sea realmente un video,
registra su duracion, resolucion y codec, y genera una miniatura; mientras tanto
el clip aparece como `pendiente`/`procesando` y al terminar pasa a `listo` o
`rechazado` (con el motivo).

## Como se levanta

En la instancia EC2 de AWS (donde el RDS privado es alcanzable):

```bash
cp .env.ejemplo .env     # y llena tus valores
docker compose up --build
```

La aplicacion queda en http://localhost:8000 (en la EC2: `http://<ip-publica>:8000`)
y su endpoint de salud responde en `/salud` (devuelve 200 si la API y el RDS
contestan, 503 si no).

Para desarrollar en tu laptop (no hay acceso al RDS privado desde fuera de AWS),
se agrega un Postgres local:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

La infraestructura de AWS se crea con Terraform (ver `infra/`):

```bash
export TF_VAR_db_password='...'            # nunca se escribe en un archivo
export TF_VAR_cidr_autorizado='TU.IP/32'   # unica IP que puede abrir la API
terraform -chdir=infra init && terraform -chdir=infra apply
```

**Nota del Learner Lab:** una politica de organizacion (SCP) niega
`s3:GetBucketObjectLockConfiguration`, que el provider de Terraform lee al tocar
el bucket. Por eso el primer `apply` crea todo pero falla al final en el bucket;
las 4 piezas de configuracion del bucket se aplican con
`terraform -chdir=infra apply -refresh=false -target=aws_s3_bucket_public_access_block.clips -target=aws_s3_bucket_server_side_encryption_configuration.clips -target=aws_s3_bucket_versioning.clips -target=aws_s3_bucket_policy.solo_tls`
(revisa antes con `plan`). El `destroy` tambien requiere `-refresh=false`.

Despliegue de la app en la EC2 (por SSM, sin SSH; requiere las credenciales de AWS
cargadas y tu `.env` con `DB_HOST` del output `db_host`):

```bash
./infra/desplegar.sh <instancia_id>     # sube el codigo + .env, hace docker compose up y borra el paquete
```

## Arquitectura

El navegador habla con el contenedor **api** (FastAPI, puerto 8000), que registra
usuarios y clips en **RDS PostgreSQL** y guarda el archivo subido en **S3**. El
contenedor **worker** no tiene puerto: consulta el RDS cada 3 segundos, toma los
clips `pendiente` con `FOR UPDATE SKIP LOCKED`, baja el original de S3, lo valida
con ffprobe, genera la miniatura con ffmpeg, la sube a S3 y actualiza el estado en
RDS. Para reproducir, el API entrega al navegador una URL firmada de 15 minutos
y el video se baja directo de S3 (el bucket nunca es publico). Ambos contenedores
corren en una EC2 y acceden a S3 con el rol de la instancia, sin llaves.

Ver el diagrama en `docs/diagrama_arquitectura.png`.

## Servicios de AWS que usa

| Servicio | Para que lo uso | Como lo asegure |
|---|---|---|
| S3 | Guarda el video original y la miniatura de cada clip (`clips/<usuario>/<id>/`). | Privado, `block_public_acls/policy` y `restrict_public_buckets` activos, cifrado SSE-KMS con llave propia (rotacion anual), politica que niega todo acceso sin TLS, versionado. |
| RDS (PostgreSQL 15) | Usuarios y metadatos de los clips (estado, duracion, resolucion, codec). | `storage_encrypted = true`, `publicly_accessible = false`, grupo de seguridad que solo acepta el 5432 desde el grupo de la EC2. |
| EC2 (t3.small) | Ejecuta `docker compose` con los dos contenedores. | Sin SSH (se administra por SSM), el puerto 8000 solo abre a una IP autorizada, IMDSv2 obligatorio, disco cifrado, rol de la instancia en lugar de llaves. |
| KMS | Llave propia que cifra el bucket. | Rotacion automatica activada; politica de llave limitada a la cuenta y al rol del laboratorio. |

## Requisitos minimos del tema

| Requisito de mi tema | Donde se cumple |
|---|---|
| Worker asincrono en su propio contenedor que procesa el clip despues de subirlo | `Dockerfile.worker` + servicio `worker` en `docker-compose.yml`; logica en `app/worker/worker.py` (ffprobe: valida formato y duracion; ffmpeg: miniatura). |
| Backend en Python (FastAPI) | `app/api/main.py` |
| Al menos 2 contenedores propios | `api` y `worker` en `docker-compose.yml` (imagenes `clipshare-api` y `clipshare-worker`) |
| Registro e inicio de sesion | `POST /registro`, `POST /login` (scrypt + token firmado) |
| Endpoint `/salud` | `GET /salud` en `app/api/main.py` |
| Bucket S3 real, privado y cifrado, usado por la app | `infra/main.tf` (`aws_s3_bucket*`); lo usa `app/clipshare/storage.py` |
| RDS real, cifrado y sin acceso publico | `infra/main.tf` (`aws_db_instance`); lo usa `app/clipshare/db.py` |
| Cero credenciales en el codigo | Todo por variables de entorno (`app/clipshare/config.py`); `.env` en `.gitignore`; Gitleaks en el pipeline |
| Dockerfile endurecido | `Dockerfile.api`, `Dockerfile.worker`: version fija, `USER 10001`, `HEALTHCHECK`; validado por `pipeline/politica_dockerfile.py` |
| IaC | `infra/*.tf` (S3, KMS, RDS, grupos de seguridad, EC2) |

## Entrega Final: parche, hallazgo y remediacion

Se aplico el parche entregado por el docente (exportar clip en baja
resolucion) tal cual, se dejo que el pipeline lo detuviera, se clasifico el
hallazgo y se remedio la causa raiz. Ver:

- `docs/clasificacion_hallazgo.md` — tipo (CWE-78), severidad y evidencia.
- `docs/respuesta_incidente.md` — contencion inmediata vs. prevencion.
- `reportes/pipeline_bloqueado.txt` / `reportes/pipeline_verde.txt` — las dos corridas.
- Commits `Aplica parche` -> `Detecta y clasifica` -> `Remedia la causa raiz` en el historial de git.

El codigo remediado se desplego primero en la instancia de **QA** (la misma
EC2 del Avance 2) y, ya en verde, se promovio a una instancia de
**Produccion** nueva, creada con su propio workspace de Terraform:

```bash
terraform -chdir=infra workspace new prod   # una sola vez
terraform -chdir=infra workspace select prod
export TF_VAR_db_password='...' TF_VAR_cidr_autorizado='TU.IP/32' TF_VAR_entorno='prod'
terraform -chdir=infra apply                # crea un S3/RDS/EC2 propios, con sufijo -prod

./infra/desplegar.sh <instancia_id_de_produccion>
```

Ver `docs/evidencia_produccion.md` para la prueba de que corre ahi.

## Como se corre el pipeline

Requiere Docker en ejecucion y Python 3 (descarga las herramientas como contenedores).

```bash
./pipeline/run_pipeline.sh reportes/corrida_actual.txt   # termina en BLOQUEADO (exit 1) o PERMITIDO (exit 0)
./pipeline/demo_rojo.sh                                  # demostracion: planta una llave falsa y debe BLOQUEAR
```

Ocho etapas (secretos, SAST, pruebas, dependencias, IaC, politica de Dockerfile,
imagenes, SBOM) y un unico veredicto final. Los umbrales y su justificacion estan
en `docs/tabla_decisiones_pipeline.md`. Evidencia: `reportes/corrida_roja.txt`,
`reportes/corrida_verde.txt` y `reportes/sbom_cyclonedx.json`.

Pruebas unitarias aparte: `pip install -r requirements-dev.txt && pytest tests`.
