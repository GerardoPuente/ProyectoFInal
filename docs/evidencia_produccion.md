# Evidencia: codigo remediado corriendo en Produccion

Instancia de Produccion creada con el workspace `prod` de Terraform (`infra/`,
`terraform workspace select prod`), con S3, KMS y RDS propios (sufijo `-prod`,
ver `infra/main.tf`), separados de QA. Solo recibio el codigo que ya habia
pasado el pipeline en verde (`reportes/pipeline_verde.txt`); el parche nunca
se aplico sin remediar en Produccion.

| Dato | Valor |
|---|---|
| Instancia QA (Avance 2) | `i-03dd1580329924225` (IP `100.61.141.161`) |
| Instancia Produccion (nueva) | `i-02c36913026ee9e24` (IP `3.237.242.36`) |
| Bucket S3 de Produccion | `clipshare-613855971218-prod` — acceso publico bloqueado, cifrado `aws:kms`, verificado con `aws s3api get-public-access-block` / `get-bucket-encryption` |
| RDS de Produccion | `clipshare-db-prod` — `available`, `StorageEncrypted=True`, `PubliclyAccessible=False` |
| Commit desplegado en Produccion | `93a49eb` — "Remedia la causa raiz del CWE-78 en /clips/{id}/exportar" (el ultimo de la rama, con el pipeline en verde) |

## Prueba de que corre ahi (no en QA)

Contra `http://3.237.242.36:8000` (la IP de **Produccion**, distinta de la de QA):

```
$ curl http://3.237.242.36:8000/salud
{"estado":"ok","base_de_datos":"ok"}

$ curl -XPOST http://3.237.242.36:8000/registro -H 'Content-Type: application/json' \
    -d '{"usuario":"ana_prod","password":"clave12345"}'
{"id":1,"usuario":"ana_prod"}

# Sin token -> 401. El parche ORIGINAL no tenia autenticacion; esto confirma
# que la version remediada (no la original) es la que esta corriendo.
$ curl -XPOST http://3.237.242.36:8000/clips/00000000-0000-0000-0000-000000000000/exportar \
    -H 'Content-Type: application/json' -d '{"resolucion":"480x270"}'
{"detail":"Sesion invalida o expirada"}

# Con token pero resolucion fuera de la lista blanca -> 400, nunca llega a
# ejecutar nada. El parche ORIGINAL habria pasado este valor tal cual a un
# shell. Esto confirma la remediacion (lista blanca + subprocess.run sin shell).
$ curl -XPOST http://3.237.242.36:8000/clips/00000000-0000-0000-0000-000000000000/exportar \
    -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
    -d '{"resolucion":"480x270; echo hola"}'
{"detail":"Resolucion no permitida. Usa una de: ['320x180', '480x270', '640x360']"}
```

`docker compose ps` por SSM en la instancia de Produccion:

```
NAME               IMAGE                  STATUS
clipshare-api      clipshare-api:1.0      Up About a minute (healthy)
clipshare-worker   clipshare-worker:1.0   Up About a minute (healthy)
```

## Capturas (van tambien en el documento de evidencias de la plataforma)

- [COMPLETAR] Consola de AWS: instancia de Produccion (EC2) `i-02c36913026ee9e24`, IP `3.237.242.36` — diferente InstanceId que QA (`i-03dd1580329924225`).
- [COMPLETAR] Consola de AWS: RDS `clipshare-db-prod` y bucket `clipshare-613855971218-prod`, propios de Produccion.
- [COMPLETAR] Terminal o navegador: la app respondiendo desde `http://3.237.242.36:8000`.

## Cuidado del credito del Learner Lab

Tener QA y Produccion encendidas a la vez duplica el consumo. En cuanto se
tomen estas capturas, Produccion se apaga/destruye:

```bash
terraform -chdir=infra workspace select prod
export TF_VAR_entorno=prod TF_VAR_cidr_autorizado='TU.IP/32' TF_VAR_db_password='la-de-produccion'
terraform -chdir=infra destroy -refresh=false
terraform -chdir=infra workspace select default  # vuelve a QA
```

[COMPLETAR: confirma aqui cuando ya destruiste Produccion, con la fecha/hora.]
