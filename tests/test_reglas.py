import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from clipshare import reglas, seguridad  # noqa: E402


def test_extensiones_permitidas_y_rechazadas():
    assert reglas.extension_valida("fiesta.MP4")
    assert not reglas.extension_valida("virus.exe")
    assert not reglas.extension_valida("video.mp4.php")
    assert not reglas.extension_valida("")


def test_tipo_mime():
    assert reglas.tipo_valido("video/mp4")
    assert reglas.tipo_valido("video/webm; codecs=vp9")
    assert not reglas.tipo_valido("application/x-msdownload")
    assert not reglas.tipo_valido("")


def test_nombre_seguro_quita_rutas():
    assert reglas.nombre_seguro("../../etc/passwd") == "passwd"
    assert reglas.nombre_seguro("C:\\Users\\yo\\clip.mp4") == "clip.mp4"
    assert reglas.nombre_seguro("a<b>.mp4") == "a_b_.mp4"


def test_ffprobe_acepta_video_corto():
    info = {"streams": [{"codec_type": "video"}], "format": {"duration": "12.5"}}
    assert reglas.validar_resultado_ffprobe(info, 300) == (True, "")


def test_ffprobe_rechaza_audio_sin_video():
    info = {"streams": [{"codec_type": "audio"}], "format": {"duration": "10"}}
    ok, motivo = reglas.validar_resultado_ffprobe(info, 300)
    assert not ok and "video" in motivo


def test_ffprobe_rechaza_clip_largo():
    info = {"streams": [{"codec_type": "video"}], "format": {"duration": "900"}}
    ok, motivo = reglas.validar_resultado_ffprobe(info, 300)
    assert not ok and "maximo" in motivo


def test_ffprobe_rechaza_basura():
    assert not reglas.validar_resultado_ffprobe({}, 300)[0]


def test_password_hash_y_verificacion():
    h = seguridad.hashear_password("clave-segura-123")
    assert "clave-segura-123" not in h
    assert seguridad.verificar_password("clave-segura-123", h)
    assert not seguridad.verificar_password("otra", h)
    assert not seguridad.verificar_password("x", "formato-roto")


def test_token_firmado():
    t = seguridad.crear_token("secreto", 7)
    assert seguridad.leer_token("secreto", t, 1) == 7
    assert seguridad.leer_token("otro-secreto", t, 1) is None
    assert seguridad.leer_token("secreto", t + "x", 1) is None
