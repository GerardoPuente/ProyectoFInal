# Respuesta al incidente: inyeccion de comandos en `/clips/{id}/exportar`

Ver `docs/clasificacion_hallazgo.md` para el detalle tecnico y la evidencia de
que el hallazgo es real (no un falso positivo).

## Contencion inmediata

Esto es lo que haria **ahora mismo**, sin tocar el codigo, para frenar el
riesgo mientras preparo el arreglo real:

1. **Desactivar el endpoint con una bandera de configuracion**, sin quitar el
   codigo ni redesplegar nada:
   ```bash
   # En la EC2 de QA, variable de entorno leida por la API antes de registrar el router
   EXPORTAR_CLIPS_HABILITADO=false
   ```
   (Ver `app/clipshare/config.py`: se agrego `exportar_habilitado` leido de
   `EXPORTAR_CLIPS_HABILITADO`, por defecto `true`; en `app/api/main.py` el
   router solo se registra si esta en `true`.) Esto apaga la ruta completa sin
   tocar una sola linea de `exportar.py`.
2. **Bloquear la ruta en el grupo de seguridad / frente a la app** como
   segunda capa: el grupo de seguridad `clipshare-app` ya solo deja pasar el
   puerto 8000 desde una IP autorizada (decision del Avance 2), lo que ya
   limita quien puede siquiera intentar explotarlo mientras se prepara el fix.
3. **No hace falta rotar credenciales**: el hallazgo es ejecucion de comandos,
   no una fuga de secretos; no hubo exfiltracion conocida (el endpoint se
   aplico solo en QA y se corrio bajo el control de este ejercicio).

La contencion **no corrige nada**: si se reactiva la bandera sin haber
remediado, el riesgo vuelve exactamente igual.

## Prevencion (el arreglo real, el que sube a Produccion)

Cambios en `app/api/exportar.py` (causa raiz) y alrededor (lo que la causa
raiz dejaba expuesto):

1. **`subprocess.call(comando_de_texto, shell=True)` -> `subprocess.run(lista_de_argumentos)`**
   (sin `shell=True`). Ya no hay un shell que interprete `;`, `&&`, `|` ni
   nada mas: `ffmpeg` recibe sus argumentos uno por uno, directo del proceso,
   nunca como texto reensamblado.
2. **Lista blanca de resoluciones** (`RESOLUCIONES_PERMITIDAS = {"640x360",
   "480x270", "320x180"}`): el valor que manda el cliente se valida contra un
   conjunto fijo *antes* de usarse para cualquier cosa. Aunque el `run()` sin
   shell ya cierra la inyeccion, la lista blanca es una segunda barrera (y de
   paso evita pedir una escala arbitraria que agote CPU/memoria).
3. **Autenticacion**: el endpoint original no exigia sesion. Ahora usa la
   misma dependencia `usuario_actual` (token Bearer) que el resto de la API
   (se extrajo a `app/clipshare/auth.py` para compartirla sin crear un import
   circular entre `main.py` y `exportar.py`).
4. **Verificacion de dueno**: se consulta el clip en RDS y se compara
   `usuario_id` contra el usuario autenticado, igual que ya hacia `GET
   /clips/{id}`; si no es el dueno, `404` (no se revela que el clip existe).
5. **`clip_id` tipado como `uuid.UUID`** en la firma del endpoint: FastAPI
   rechaza automaticamente cualquier cosa que no sea un UUID valido antes de
   que el codigo lo use para nada.

La funcionalidad que pidio producto se mantiene intacta: el usuario sigue
pudiendo exportar su clip en una resolucion mas baja; solo cambio *como* se
construye y valida esa peticion.

### Por que esto es prevencion y no un parche cosmetico

No se comento la funcion, no se borro el endpoint y no se "atrapo" el error
con un `try/except` que lo esconda: la causa raiz (texto del cliente
interpretado como shell) ya no existe en el codigo. Un atacante que mande
cualquier cosa en `resolucion` hoy recibe un `400` si no esta en la lista
blanca; si estuviera, de cualquier forma llegaria a `subprocess.run` como un
argumento de lista, nunca como shell.

## Evidencia

- Corrida bloqueada (version original del parche): `reportes/pipeline_bloqueado.txt`
  — Bandit `B602:subprocess_popen_with_shell_equals_true`, severidad ALTA.
- Prueba de concepto aislada (version original, dentro de la imagen Linux real,
  sin tocar ninguna instancia desplegada): `reportes/prueba_concepto_exportar.txt`.
- Pruebas de regresion de la remediacion: `tests/test_exportar_remediado.py`.
- Corrida en verde (version remediada): `reportes/pipeline_verde.txt` — 8/8 etapas.
- Commits: ver `git log` — "Aplica parche" (vulnerable, sin tocar) seguido de
  "Remedia" (causa raiz corregida), para que el diff muestre exactamente el
  antes/despues.
