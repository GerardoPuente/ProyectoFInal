# Clasificacion del hallazgo

## El hallazgo

El parche entregado para el tema 1 (`app/api/exportar.py`, registrado como
`POST /clips/{clip_id}/exportar`) arma un comando de shell concatenando texto
y lo ejecuta con `subprocess.call(comando, shell=True)`:

```python
resolucion = request.json.get("resolucion", "480x270")  # viene del cliente, sin validar
...
comando = f"ffmpeg -y -i {origen} -vf scale={resolucion} {destino}"
subprocess.call(comando, shell=True)
```

`resolucion` llega directo del cuerpo JSON que manda quien hace la peticion y
se concatena sin ninguna validacion ni escape dentro de un comando que corre
con `shell=True` (el shell interpreta `;`, `&&`, `|`, backticks, etc.).

## Tipo

**Inyeccion de comandos de sistema operativo - CWE-78 (OS Command Injection)**,
equivalente al A03:2021 (Injection) de OWASP Top 10.

No es una inyeccion SQL (no hay una base de datos involucrada en esa linea) ni
un control de acceso roto como causa raiz, aunque el endpoint ademas carece de
autenticacion (ver "Otros problemas" abajo): la causa raiz de este hallazgo es
que un valor de entrada se interpreta como codigo de shell.

## Severidad: **Critica**

| Factor | Evaluacion |
|---|---|
| Impacto | Ejecucion de comandos arbitrarios con los privilegios del contenedor `api` (usuario `10001`, sin `root`, pero con salida de red hacia S3/RDS y las credenciales del rol de la instancia disponibles por IMDSv2). Un atacante podria leer/exfiltrar datos de S3 y RDS a traves del rol de la instancia, o usar el contenedor como punto de apoyo dentro de la VPC. |
| Facilidad de explotacion | Trivial: una sola peticion HTTP con un campo JSON malicioso. No requiere condiciones especiales ni herramientas. |
| Autenticacion requerida | **Ninguna.** El router no tiene `Depends(usuario_actual)` (a diferencia de `/clips` y `POST /clips`), asi que cualquiera que alcance el puerto 8000 puede explotarlo sin cuenta ni sesion. |
| Ambito del dano | Limitado por: `cap_drop: ALL`, `read_only: true` y `no-new-privileges` del contenedor (Avance 2), y por el grupo de seguridad que solo deja llegar al puerto 8000 desde una IP autorizada. Esto reduce pero no elimina el riesgo: el comando igual corre, solo que el atacante tiene que llegar desde esa IP y el proceso no es root ni puede escalar privilegios en el host facilmente. |

Con impacto maximo (RCE) y explotacion trivial sin autenticacion, la severidad
es Critica incluso con las mitigaciones de contenedor y red ya existentes del
Avance 2: esas mitigaciones limitan el radio de dano, no cierran la falla.

## ¿Falso positivo?

**No.** Se confirmo que es explotable:

1. **Estatico:** Bandit (parte del pipeline, etapa 2) lo marca con
   `B602:subprocess_popen_with_shell_equals_true`, severidad ALTA, apuntando
   exactamente a `app/api/exportar.py:58`. Ver `reportes/pipeline_bloqueado.txt`.
2. **Dinamico, de forma aislada y sin exponer ninguna instancia real:**
   `tests/test_exportar_vulnerabilidad.py` reproduce linea por linea la misma
   construccion de comando que hace `exportar.py`, dentro de la imagen real de
   `clipshare-api` (Linux/Debian, el mismo entorno que corre en produccion), y
   demuestra que una resolucion `480x270; touch <marcador> #` crea el archivo
   marcador: el `;` termina el comando de ffmpeg y el shell ejecuta lo que
   sigue como si lo hubiera escrito el programador. Evidencia completa en
   `reportes/prueba_concepto_exportar.txt`. No se ejecuto ningun payload
   contra la aplicacion desplegada en AWS; la prueba corre en un contenedor
   local desechable con un comando inofensivo (crear un archivo).

## Otros problemas que encontre en el mismo parche (no son el hallazgo principal, pero se documentan)

- **Sin autenticacion** (el resto de la API exige `Authorization: Bearer`).
- **Sin control de acceso**: aunque tuviera login, no valida que el clip
  pertenezca a quien hace la peticion.
- **`clip_id` sin validar formato**: se usa directo para armar una ruta de
  archivo; combinado con lo anterior podria explorarse como un segundo vector
  (no se profundizo porque el hallazgo principal ya es critico).

Estos se corrigen junto con la causa raiz en la remediacion (ver
`docs/respuesta_incidente.md`), porque dejarlos sueltos habria sido un parche
cosmetico que no cierra el riesgo real del endpoint.
