"""Cache de paquetes ya vistos, para cortar los ciclos de la inundacion.

Sin esto, Flooding (y la inundacion de LSPs dentro de LSR) genera copias
infinitas de cada paquete en cualquier topologia con ciclos. El TTL por si
solo no basta: acota la vida del paquete pero no evita la explosion
exponencial de copias mientras el TTL dura.

Las entradas expiran para que un nodo que reinicia pueda volver a aceptar
identificadores que ya habia visto antes de caerse.
"""

import time


class SeenCache:
    def __init__(self, ttl=120.0, max_entries=10000):
        self.ttl = ttl
        self.max_entries = max_entries
        self._seen = {}

    def check_and_add(self, key):
        """True si el paquete es nuevo (y queda registrado); False si es duplicado."""
        now = time.monotonic()
        self._purge(now)
        if key in self._seen:
            return False
        self._seen[key] = now
        return True

    def __contains__(self, key):
        return key in self._seen

    def __len__(self):
        return len(self._seen)

    def _purge(self, now):
        if len(self._seen) < self.max_entries:
            expired = [k for k, t in self._seen.items() if now - t > self.ttl]
        else:
            # Bajo presion se descartan tambien las entradas mas antiguas.
            ordered = sorted(self._seen.items(), key=lambda kv: kv[1])
            expired = [k for k, _ in ordered[: len(ordered) // 2]]
        for key in expired:
            self._seen.pop(key, None)
