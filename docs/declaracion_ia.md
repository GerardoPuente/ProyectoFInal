# Declaracion de uso de inteligencia artificial — Entrega Final

"Se espera que los estudiantes utilicen herramientas de inteligencia artificial
como un recurso de apoyo... estas herramientas no deben sustituir su
participacion ni la elaboracion personal de las actividades."

Esta entrega continua sobre `docs/declaracion_uso_ia.md` del Avance 2 (sigue
vigente para esa parte del proyecto). Aqui declaro el uso de IA especifico de
esta Entrega Final.

## Que genere con ayuda de IA

| Parte | Herramienta de IA | Que le pedi | Que cambie yo despues |
|---|---|---|---|
| Integracion del parche entregado (`app/api/exportar.py`, traducido de Flask a FastAPI) | Claude Code (Claude Sonnet 5 / 5.5) | Registrar el endpoint entregado por el docente en mi app, tal cual, sin corregirlo | [COMPLETAR] |
| Deteccion con el pipeline y confirmacion del hallazgo | Claude Code | Correr mi pipeline del Avance 2 sobre el codigo con el parche y, si lo atrapaba, confirmar que el hallazgo era real | [COMPLETAR] |
| Clasificacion del hallazgo (`docs/clasificacion_hallazgo.md`) | Claude Code | Redactar el tipo (CWE), la severidad y su justificacion, y revisar si algo era falso positivo | [COMPLETAR] |
| Remediacion de la causa raiz (`app/api/exportar.py`, `app/clipshare/auth.py`, bandera de contencion) | Claude Code | Corregir `shell=True` con texto concatenado por `subprocess.run` con lista de argumentos, agregar lista blanca, autenticacion y verificacion de dueno | [COMPLETAR] |
| Documentacion de contencion y prevencion (`docs/respuesta_incidente.md`) | Claude Code | Separar que haria de inmediato (apagar el endpoint) de la correccion real | [COMPLETAR] |
| Infraestructura de Produccion (workspace `prod` de Terraform) y despliegue | Claude Code | Crear una segunda instancia con sus propios S3/RDS, sin tocar QA, y desplegar ahi solo el codigo ya remediado | [COMPLETAR] |

## Que hice sin IA

[COMPLETAR: p. ej. entender el codigo del parche antes de aprobarlo, decidir
autorizar el despliegue en AWS, verificar manualmente que el endpoint
remediado sigue funcionando, revisar el diff de la remediacion, tomar las
capturas, vigilar el saldo del Learner Lab, terminar la instancia de
Produccion despues de capturar la evidencia.]

## Algo que la IA me dio mal (o que tuve que decidir yo) y tuve que corregir

1. **Primer intento de "prueba de explotacion" se hizo en Windows y fallo en
   silencio por una razon equivocada.** `subprocess.call(..., shell=True)` en
   Windows invoca `cmd.exe`, cuyo separador de comandos es `&`, no `;` como en
   un shell POSIX. La primera corrida de la prueba de concepto parecia decir
   "no es explotable" cuando en realidad el problema era el shell equivocado,
   no la ausencia de la falla. Se corrigio ejecutando la prueba dentro de la
   imagen real de `clipshare-api` (Linux/Debian) y marcando la prueba para que
   se salte en Windows con una razon explicita en vez de fallar de forma
   confusa.
2. **La integracion inicial de la autenticacion al endpoint remediado usaba un
   `lambda` envolviendo la dependencia de FastAPI, que no habria extraido el
   encabezado `Authorization` correctamente** (FastAPI inspecciona la firma de
   la dependencia, y el lambda no declaraba el parametro con `Header(...)`).
   Se corrigio extrayendo la dependencia de autenticacion a un modulo
   compartido (`app/clipshare/auth.py`) en vez de intentar importarla de forma
   indirecta entre `main.py` y `exportar.py`.
3. **Decision mia, no de la IA:** que la "prueba de explotacion" se hiciera de
   forma aislada (un contenedor local desechable con un comando inofensivo),
   en vez de mandar el payload contra la instancia de QA ya desplegada en
   internet. Aunque el grupo de seguridad limita el acceso a una sola IP, no
   quise ejecutar una inyeccion de comandos real contra un servidor vivo en la
   nube, ni siquiera un comando inofensivo.

[COMPLETAR: agrega lo que tu revisaste o decidiste ademas de lo anterior.]
