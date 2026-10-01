"""Prueba de concepto AISLADA de la inyeccion de comandos (CWE-78) de la version
ORIGINAL de exportar.py, tal como la entrego el docente (antes de remediar;
ver docs/clasificacion_hallazgo.md). exportar.py ya NO tiene este patron (ver
tests/test_exportar_remediado.py); esta prueba se deja como evidencia
permanente del hallazgo, no corre contra el codigo actual.

No llama a ningun endpoint ni a ninguna instancia desplegada: reproduce, en un
proceso Python de prueba, exactamente la misma construccion de comando que
hacia la version original de `exportar.py` linea por linea, y demuestra con un
comando INOFENSIVO (crear un archivo marcador) que el valor de "resolucion"
que vendria del cliente se interpretaba como shell y no como un simple
parametro de ffmpeg. Asi se confirma el hallazgo de Bandit sin exponer ni
atacar ninguna instancia real.
"""
import os
import subprocess
import sys
import tempfile

import pytest


def _comando_tal_como_lo_arma_exportar(origen: str, resolucion: str, destino: str) -> str:
    # Copia exacta de la linea vulnerable de la version ORIGINAL de exportar.py
    return f"ffmpeg -y -i {origen} -vf scale={resolucion} {destino}"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="shell=True en Windows invoca cmd.exe (separador '&', no ';'); el contenedor real "
    "usa un shell POSIX. La prueba equivalente dentro de la imagen Linux real esta en "
    "reportes/prueba_concepto_exportar.txt.",
)
def test_resolucion_maliciosa_inyecta_un_comando_adicional():
    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "clip.mp4")
        destino = os.path.join(tmp, "salida.mp4")
        marcador = os.path.join(tmp, "PRUEBA_DE_INYECCION.txt")
        open(origen, "w").close()  # no hace falta que sea un video real: el ; corta el comando antes

        # Esto es exactamente lo que el cliente podria mandar en el campo "resolucion"
        resolucion_maliciosa = f"480x270; touch {marcador} #"
        comando = _comando_tal_como_lo_arma_exportar(origen, resolucion_maliciosa, destino)

        assert not os.path.exists(marcador)
        subprocess.call(comando, shell=True)  # mismo patron que exportar.py: shell=True + texto concatenado

        # El "comando" de ffmpeg (que fallara, el origen no es un video real) se corto en el ";"
        # y el shell ejecuto el segundo comando como si el programador lo hubiera escrito el mismo.
        assert os.path.exists(marcador), (
            "La resolucion maliciosa debia inyectar y ejecutar un comando adicional (CWE-78); "
            "si esto falla, revisa que shell=True siga concatenando texto sin sanear."
        )


def test_una_resolucion_normal_no_dispara_nada_raro():
    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "clip.mp4")
        destino = os.path.join(tmp, "salida.mp4")
        open(origen, "w").close()
        comando = _comando_tal_como_lo_arma_exportar(origen, "480x270", destino)
        assert comando == f"ffmpeg -y -i {origen} -vf scale=480x270 {destino}"
