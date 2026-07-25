from __future__ import annotations

import hmac


def verificar_credenciales(usuario_in: str, pass_in: str,
                           usuario_real: str, pass_real: str) -> bool:
    """Compara credenciales en tiempo constante. Config vacía (sin usuario/pass
    real) => siempre False, para no dejar la app abierta por secrets ausentes."""
    if not usuario_real or not pass_real:
        return False
    u_ok = hmac.compare_digest(usuario_in or "", usuario_real)
    p_ok = hmac.compare_digest(pass_in or "", pass_real)
    return u_ok and p_ok
