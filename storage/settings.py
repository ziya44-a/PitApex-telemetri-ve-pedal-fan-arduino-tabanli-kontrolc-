"""Kullanici tercihleri, pedal ayarlari ve profiller (hepsi Belgeler/PitApex altinda)."""
import copy
import os
import threading

from core.led_matrix import DEFAULT_LED
from hardware.fan import default_fans
from storage.atomic import atomic_write_json, read_json

PREF_DEFAULTS = {
    "version": 1,
    "theme": "dark",
    "language": "tr",
    "last_tab": 0,
    "overlay_geometry": {},
    # Iki fan yuvasi: her biri kendi cikisi (output: 0=secilmedi, 1..4=M1..M4) ve hiz egrisiyle.
    # Eski tek-fan kaydi (duz sozluk) hardware.fan.normalize_fans ile Fan 1'e tasinir.
    "fan": {"fans": default_fans()},
    # LED aydinlatma (MAX7219 8x8 matris, ayri Arduino): vites gostergesi vb.
    "led": copy.deepcopy(DEFAULT_LED),
}


def _deep_merge(base, over):
    out = copy.deepcopy(base)
    if isinstance(over, dict):
        for k, v in over.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
    return out


class Preferences:
    def __init__(self, dm):
        self.dm = dm
        self.path = dm.path("settings", "preferences.json")
        self.lock = threading.RLock()
        self.status = "ok"
        data, self.status = read_json(self.path, dm.backup_dir, None, lambda d: isinstance(d, dict))
        self.data = _deep_merge(PREF_DEFAULTS, data or {})

    def get(self, key, default=None):
        with self.lock:
            return copy.deepcopy(self.data.get(key, default))

    def set(self, key, value):
        with self.lock:
            self.data[key] = copy.deepcopy(value)
            self.save()

    def save(self):
        with self.lock:
            try:
                atomic_write_json(self.path, self.data, self.dm.backup_dir)
            except OSError:
                self.status = "write_error"

    def reset(self):
        with self.lock:
            self.data = copy.deepcopy(PREF_DEFAULTS)


class PedalSettings:
    """Eski ayarlar.json ile ayni icerik (efektler, _motors, _source, _auto)."""

    def __init__(self, dm):
        self.dm = dm
        self.path = dm.path("settings", "pedal_settings.json")

    def load(self):
        data, status = read_json(self.path, self.dm.backup_dir, None, lambda d: isinstance(d, dict))
        return data

    def save(self, data):
        try:
            atomic_write_json(self.path, data, self.dm.backup_dir)
            return True
        except OSError:
            return False


class Profiles:
    def __init__(self, dm):
        self.dm = dm
        self.dir = dm.path("profiles")

    @staticmethod
    def safe_name(name):
        return "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip()

    def names(self):
        os.makedirs(self.dir, exist_ok=True)
        return sorted(f[:-5] for f in os.listdir(self.dir) if f.endswith(".json"))

    def save(self, name, data):
        safe = self.safe_name(name)
        if not safe:
            raise ValueError("gecersiz profil adi")
        atomic_write_json(os.path.join(self.dir, safe + ".json"), data, None)
        return safe

    def load(self, name):
        safe = self.safe_name(name)
        data, status = read_json(os.path.join(self.dir, safe + ".json"), None, None,
                                 lambda d: isinstance(d, dict))
        return data


def export_configuration(prefs, pedal_settings, destination):
    """Export settings only; no records or session history."""
    import json
    from datetime import datetime, timezone
    payload = {"format": "PitApex-settings", "version": 1,
               "exported_at": datetime.now(timezone.utc).isoformat(),
               "preferences": copy.deepcopy(prefs.data),
               "pedals": pedal_settings.load() or {}}
    with open(destination, "w", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2)


def import_configuration(prefs, pedal_settings, source):
    """Validate before writing. Import never touches lap records or sessions."""
    import json
    with open(source, encoding="utf-8") as inp:
        data = json.load(inp)
    if not isinstance(data, dict) or data.get("format") != "PitApex-settings" or data.get("version") != 1:
        raise ValueError("Unsupported PitApex settings file")
    if not isinstance(data.get("preferences"), dict) or not isinstance(data.get("pedals"), dict):
        raise ValueError("Invalid settings payload")
    new_prefs = _deep_merge(PREF_DEFAULTS, data["preferences"])
    if new_prefs.get("language") not in ("tr", "en") or new_prefs.get("theme") not in ("dark", "light"):
        raise ValueError("Invalid language or theme")
    if not pedal_settings.save(data["pedals"]):
        raise OSError("Could not save pedal settings")
    with prefs.lock:
        prefs.data = new_prefs
        prefs.save()
