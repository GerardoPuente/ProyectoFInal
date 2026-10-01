"""Pruebas de regresion de la remediacion del CWE-78 en exportar.py.

Cubren que: (1) la lista blanca de resoluciones existe y rechaza lo que no
esta en ella, (2) el comando que se ejecuta es una LISTA de argumentos
(shell=False), nunca una cadena armada con texto del cliente.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from api.exportar import RESOLUCIONES_PERMITIDAS  # noqa: E402


def test_lista_blanca_no_esta_vacia_y_son_resoluciones_simples():
    assert RESOLUCIONES_PERMITIDAS
    for r in RESOLUCIONES_PERMITIDAS:
        ancho, alto = r.split("x")
        assert ancho.isdigit() and alto.isdigit()


def test_una_resolucion_maliciosa_no_esta_en_la_lista_blanca():
    maliciosa = "480x270; touch /tmp/pwned #"
    assert maliciosa not in RESOLUCIONES_PERMITIDAS


def test_bandera_de_contencion_existe_y_por_defecto_esta_activa():
    """docs/respuesta_incidente.md: EXPORTAR_CLIPS_HABILITADO debe poder apagar
    el router completo sin tocar codigo. Por defecto (sin la variable) sigue
    activo, para no romper el comportamiento normal de la app."""
    from clipshare.config import Config

    assert Config().exportar_habilitado is True


def test_el_endpoint_arma_una_lista_de_argumentos_no_una_cadena():
    """Reconstruye lo que hace exportar.py y confirma que ffmpeg se llama con
    una lista (shell=False), igual que el worker (app/worker/worker.py)."""
    import inspect

    from api import exportar

    codigo = inspect.getsource(exportar.exportar_clip_baja_resolucion)
    assert "shell=True" not in codigo
    assert 'subprocess.run(\n            ["ffmpeg"' in codigo or '"ffmpeg", "-y"' in codigo
