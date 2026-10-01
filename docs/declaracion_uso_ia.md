# Declaracion de uso de inteligencia artificial

Las Notas de Ensenanza del curso permiten usar IA como apoyo, no como
sustituto. Esta declaracion es obligatoria y forma parte de la entrega.

## Que genere con ayuda de IA

| Parte del proyecto | Herramienta de IA | Que le pedi | Que cambie yo despues |
|---|---|---|---|
| Aplicacion: API FastAPI, worker, reglas de validacion, front HTML | Claude Code (Claude Sonnet 5.5) | Construir el tema 1 (clips cortos) con registro/login, subida a S3, datos en RDS y un worker asincrono, siguiendo las instrucciones del reto | [COMPLETAR: que revisaste o modificaste tu] |
| Dockerfiles y docker-compose | Claude Code | Imagenes endurecidas (version fija, sin root, HEALTHCHECK) y dos servicios separados | [COMPLETAR] |
| Terraform (S3, KMS, RDS, grupos de seguridad, EC2) | Claude Code | Describir bucket privado y cifrado, RDS privado y la instancia donde corre la app | [COMPLETAR] |
| Pipeline (`pipeline/`), pruebas y SBOM | Claude Code | Disenar 8 etapas con umbrales, un veredicto unico y las dos corridas | [COMPLETAR] |
| Documentacion (README, ADR, tabla de decisiones, diagrama) | Claude Code | Redactarla a partir de lo realmente construido y de los resultados de las corridas | [COMPLETAR] |

## Que hice sin IA

[COMPLETAR: p. ej. elegir el tema, crear y operar el entorno de AWS Academy,
entregar las credenciales, revisar el codigo, grabar el video, tomar las
capturas. Escribe solo lo que de verdad hiciste tu.]

## Algo que la IA me dio mal y tuve que corregir

Estos son errores reales que aparecieron mientras se construia el proyecto y
como se resolvieron (los detecto el propio pipeline o las pruebas, no los vi a
simple vista):

1. **Bucket cifrado, pero sin llave propia.** La IA creo el bucket con cifrado
   `AES256` (SSE-S3). Trivy lo marco como AWS-0132 (HIGH). Se corrigio creando una
   llave KMS propia con rotacion y una politica de llave.
2. **Egreso abierto en el grupo de seguridad.** La primera version permitia salida
   a cualquier puerto (AWS-0104, CRITICAL). Se limito al 443 y al 5432 de la VPC y
   la parte restante se acepto como excepcion justificada, no ignorada en silencio.
3. **`apt-get upgrade` no cerraba los CVE de libexpat.** La IA propuso actualizar
   paquetes dentro del Dockerfile; no funciono porque Debian 12 no habia publicado
   el parche. Se cambio la imagen base a Debian 13 (trixie).
4. **Configuracion de S3 innecesaria.** La IA fijo el estilo de URL `virtual` en
   boto3 sin que hiciera falta; se quito antes de probar con un S3 simulado para
   no depender de un detalle que boto3 ya resuelve por defecto.

[COMPLETAR: agrega aqui lo que TU corregiste o revisaste ademas de lo anterior.
Si no encontraste nada, probablemente no revisaste lo suficiente.]
