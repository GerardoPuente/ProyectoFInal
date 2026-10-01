import hashlib
import hmac
import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_N, _R, _P = 2**14, 8, 1


def hashear_password(password: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
    return f"scrypt${sal.hex()}${h.hex()}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        _, sal_hex, h_hex = guardado.split("$")
        h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(sal_hex), n=_N, r=_R, p=_P)
        return hmac.compare_digest(h.hex(), h_hex)
    except ValueError:
        return False


def crear_token(secret: str, usuario_id: int) -> str:
    return URLSafeTimedSerializer(secret, salt="sesion").dumps({"uid": usuario_id})


def leer_token(secret: str, token: str, max_horas: int) -> int | None:
    try:
        datos = URLSafeTimedSerializer(secret, salt="sesion").loads(token, max_age=max_horas * 3600)
        return int(datos["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        return None
