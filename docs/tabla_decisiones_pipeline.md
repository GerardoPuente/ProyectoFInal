# Tabla de decisiones de mi pipeline

Este documento es el corazon de la entrega: no se califica cuantos controles
pusiste, sino que puedas justificar cada uno.

ClipShare deja que cualquier usuario registrado **suba un archivo** que despues
un worker **abre y decodifica con ffmpeg** dentro de un contenedor, y guarda ese
archivo en **S3** y sus datos en **RDS**. De ahi salen los riesgos de abajo.

## Riesgos que introduce MI aplicacion

| # | Riesgo concreto de mi app | Que control lo cubre | Por que ese control |
|---|---|---|---|
| 1 | El usuario controla el archivo que sube: puede mandar un `.exe` renombrado, un "video" que es texto, un archivo de gigas o un clip de horas que agote disco y CPU del worker. | Reglas de validacion (extension, MIME, tamano maximo en la API; ffprobe y duracion maxima en el worker) vigiladas por **pytest** en la etapa 3 y por **Bandit** en la etapa 2. | Las reglas son codigo mio y se pueden romper en silencio con un cambio futuro; las pruebas fijan el comportamiento (9 casos: extension doble `.mp4.php`, ruta `../../`, audio sin video, 900 s). Bandit revisa que no use `subprocess` con `shell=True`, `eval`, SQL armado con texto, etc. |
| 2 | Mi app usa llaves de S3 y la clave del RDS: el error mas comun es dejarlas escritas en el codigo o en un `.env` subido. | **Gitleaks** (etapa 1) sobre exactamente lo que git subiria (respeta `.gitignore`). | Es el unico control que ataca el riesgo "credencial filtrada"; un `.env` forzado con `git add -f` aparece como tracked y lo detecta. En EC2 ademas no hay llaves: se usa el rol de la instancia. |
| 3 | La API parsea formularios multipart de archivos grandes y el worker ejecuta **ffmpeg sobre archivos no confiables** (los decodificadores de ffmpeg son una fuente historica de CVE). Una libreria vulnerable aqui es explotable por cualquier usuario registrado. | **Trivy** sobre dependencias Python (etapa 4) y sobre las **imagenes ya construidas** (etapa 7), que es donde viven ffmpeg y libexpat. | El `requirements.txt` solo cubre lo que yo declaro; las CVE de ffmpeg y de la libreria del sistema estan en la imagen. Por eso hacen falta las dos etapas. |
| 4 | El bucket guarda videos de usuarios y el RDS sus cuentas. Un bucket publico, sin cifrar, o un RDS publico seria una fuga directa. | **Trivy config** (etapa 5) sobre `infra/*.tf`, mas la API de AWS en la consola (capturas 1.4 y 1.5). | Revisa el `.tf` antes de crear nada: public access block, cifrado con llave propia, `publicly_accessible=false`, reglas de grupo de seguridad. |
| 5 | Si alguien explota ffmpeg dentro del contenedor, lo que pueda hacer depende del usuario y de las capacidades del contenedor (root + escritura en disco seria peor). | **Politica de Dockerfile** (etapa 6): version fija, USER no root, HEALTHCHECK, sin secretos en `ENV`/`ARG`; y en `docker-compose.yml`: `read_only`, `cap_drop: ALL`, `no-new-privileges`. | Son los requisitos del curso, pero ademas son la contencion real si el riesgo 3 se materializa. Trivy solo detecta la etiqueta `:latest`; exigir una version concreta, USER y HEALTHCHECK a mi manera lo valido con un script propio. |
| 6 | Cuando salga una CVE nueva de ffmpeg o de una libreria, necesito saber en minutos si mi app la contiene. | **SBOM CycloneDX** (etapa 8) de la imagen del worker (superconjunto de la del API). | Sin inventario no hay respuesta a "¿me afecta?". Se genera en cada corrida, asi que siempre corresponde a la imagen que se evaluo. |

## Mis etapas y sus umbrales

Todas las etapas corren siempre (aunque una falle) para ver todos los hallazgos
juntos, y al final hay **un solo veredicto**: si falla cualquiera, el despliegue
queda BLOQUEADO.

| Etapa | Herramienta | Que revisa | Umbral que bloquea | Por que ese umbral |
|---|---|---|---|---|
| 1. Secretos | Gitleaks v8.30.1 | Llaves/contrasenas en el codigo que se subiria | **Cualquier** hallazgo (0 tolerados) | Un secreto no tiene "severidad baja": una sola llave filtrada ya es un incidente y hay que rotarla. Tolerar "algunos" lo vuelve ruido. |
| 2. SAST | Bandit 1.9.4 | Patrones inseguros en mi codigo Python | Severidad **ALTA** (`-lll`). Las MEDIA se imprimen pero no bloquean | Las MEDIA en un contenedor suelen ser falsos positivos (p. ej. escuchar en `0.0.0.0`, que es necesario dentro de Docker). Bloquear por ellas haria que el equipo ignore el pipeline. |
| 3. Pruebas | pytest 9.1.1 | Las reglas de validacion de clips y la autenticacion | **1 prueba fallida** | Estas reglas son mi defensa del riesgo 1; si una falla, el control ya no existe. |
| 4. Dependencias | Trivy fs 0.74.0 | CVE en `app/requirements.txt` | **HIGH o CRITICAL con parche disponible** (`--ignore-unfixed`) | LOW/MEDIUM no justifican frenar un despliegue. Una CVE sin parche no se puede remediar y bloquear por ella congelaria la app sin salida; esas quedan visibles en el SBOM para vigilarlas. |
| 5. IaC y configuracion | Trivy config | `infra/*.tf`, Dockerfiles | **HIGH o CRITICAL** de configuracion | Es la barrera previa a crear un bucket/RDS inseguro. Con CRITICAL solo me dejaria pasar un bucket sin llave propia (HIGH), que si quiero atrapar. |
| 6. Politica Dockerfile | `politica_dockerfile.py` | FROM con version fija, USER no root, HEALTHCHECK, sin secretos | **Cualquier** regla incumplida | Cada regla es binaria y viene del requisito del curso; no hay "casi cumple" un HEALTHCHECK. |
| 7. Imagenes | docker build + Trivy image | CVE del sistema base, ffmpeg y librerias Python dentro de las imagenes de **api** y **worker** | **HIGH o CRITICAL con parche disponible** en cualquiera de las dos | Mismo criterio que la etapa 4, pero aplicado a lo que realmente se despliega. Es el control que paro mi primera corrida (ver abajo). |
| 8. SBOM | Trivy (CycloneDX) | Inventario de la imagen del worker | SBOM invalido o con **0 componentes** | Un SBOM vacio daria falsa confianza; valido formato y que tenga contenido. |

### Excepciones aceptadas (en `.trivyignore.yaml`)

| Regla | Donde | Justificacion |
|---|---|---|
| AWS-0104 (CRITICAL): egreso a `0.0.0.0/0` | `aws_security_group.app` | La instancia necesita salir a S3, SSM y repositorios cuyas IP cambian. Ya lo reduje a **los puertos 443 y 80** (apt de Debian usa HTTP; y 5432 dentro de la VPC). Riesgo residual: exfiltracion por 443 si la instancia se compromete. Con mas tiempo: VPC endpoints para S3/SSM y egreso cerrado. |

AWS-0132 (bucket sin llave propia, HIGH) **no** se ignoro: lo corregi creando una
llave KMS administrada por mi con rotacion automatica.

## Lo que se vio en las corridas reales

- **Corrida roja** (`reportes/corrida_roja.txt`): bloqueo por (a) Gitleaks
  detecto una llave de AWS falsa que plante a proposito en
  `app/clipshare/config_temporal.py` para demostrar el control, y (b) Trivy
  encontro **6 CVE HIGH en `libexpat1`** (CVE-2024-28757, CVE-2025-59375,
  CVE-2026-25210, ...) dentro de la imagen del worker, con parche disponible.
  El hallazgo (b) **no lo plante**: aparecio solo.
- **Remediacion**: borre el archivo con la llave. Para libexpat intente primero
  `apt-get upgrade`, pero **no funciono**: Debian 12 aun no publicaba el parche
  `deb12u4` en sus repositorios. Lo resolvi cambiando la imagen base de
  `python:3.12.14-slim-bookworm` a `python:3.12.14-slim-trixie` (Debian 13).
- **Corrida verde** (`reportes/corrida_verde.txt`): 8 de 8 etapas, veredicto
  DESPLIEGUE PERMITIDO.

## Lo que decidi NO cubrir

| Riesgo que dejo fuera | Por que lo dejo fuera | Que haria si tuviera mas tiempo |
|---|---|---|
| Archivos con **malware** (un MP4 valido para ffprobe que lleva carga maliciosa) | ffprobe valida que sea video, no que sea inocuo. Un antivirus de subida (ClamAV) es un servicio mas con su propia memoria en una instancia chica. | Escanear con ClamAV en el worker antes de marcar `listo`, y transcodificar siempre a un formato conocido. |
| **HTTPS**: la app se sirve en HTTP puerto 8000, asi que el token de sesion viaja sin cifrar | El Learner Lab no da dominio ni certificado ACM facil; el acceso esta limitado a una sola IP por grupo de seguridad. | ALB con ACM (o Caddy con Let's Encrypt) y HSTS. |
| **Fuerza bruta** en `/login` y registro masivo | Es un riesgo de disponibilidad/abuso, no de despliegue; la rubrica pide identificar usuarios, no endurecer cuentas. | Limite de intentos por IP/usuario y bloqueo temporal. |
| Token de sesion en `localStorage` (un XSS lo robaria) | El front es HTML plano; escapo todo lo que pinta (`esc()`), pero no es una defensa en profundidad. | Cookie `HttpOnly` + `SameSite` + cabecera CSP. |
| **DAST** contra la app corriendo (ZAP) | Necesita levantar toda la pila con RDS/S3 reales dentro del pipeline; supera el tiempo disponible. | Etapa que levante el compose en QA y corra ZAP baseline contra `/`. |
| Secretos en el **historial** de git (Gitleaks revisa el arbol actual) | El repo es nuevo y de un solo autor; el arbol actual es lo que se despliega. | `gitleaks git` sobre todo el historial en el CI. |
| Firma y procedencia de imagenes (cosign) y `terraform plan` en el pipeline | No hay registro de imagenes propio; las imagenes se construyen en la propia instancia. | Publicar en ECR firmado y bloquear si la imagen no tiene firma. |
| CVE **sin parche** (`--ignore-unfixed`) | No son remediables hoy; bloquear congelaria el despliegue. Quedan visibles en el SBOM. | Revisarlas cada semana contra el SBOM y fijar fecha limite de aceptacion. |
