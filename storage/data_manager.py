"""PitApex kullanici verisi klasoru: Belgeler/PitApex"""
import json
import os
import shutil

from storage.atomic import atomic_write_json, read_json
from storage.paths import get_documents_dir

SUBDIRS = ("records", "sessions", "settings", "profiles", "backups")
MARKER = ".pitapex_data"


class DataManager:
    def __init__(self, root=None):
        self.warning = ""
        self.root = root or self._default_root()
        for sub in SUBDIRS:
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)
        self.marker_path = os.path.join(self.root, MARKER)
        self.meta = self._read_marker()

    # --- konum ---
    def _default_root(self):
        docs = get_documents_dir()
        candidates = []
        if docs:
            candidates.append(os.path.join(docs, "PitApex"))
        else:
            self.warning = "Belgeler klasoru bulunamadi."
        for env in ("LOCALAPPDATA", "APPDATA"):
            if os.environ.get(env):
                candidates.append(os.path.join(os.environ[env], "PitApex"))
        candidates.append(os.path.join(os.path.expanduser("~"), "PitApex"))
        for i, c in enumerate(candidates):
            try:
                os.makedirs(c, exist_ok=True)
                probe = os.path.join(c, ".yazma_testi")
                with open(probe, "w") as f:
                    f.write("ok")
                os.remove(probe)
                if i > 0 and docs:
                    self.warning = "Belgeler/PitApex olusturulamadi, su klasor kullaniliyor: " + c
                return c
            except OSError:
                continue
        raise RuntimeError("PitApex veri klasoru olusturulamadi.")

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    @property
    def backup_dir(self):
        return self.path("backups")

    # --- ust bilgi dosyasi ---
    def _read_marker(self):
        data, _ = read_json(self.marker_path, None, None, lambda d: isinstance(d, dict))
        if data is None:
            data = {"app": "PitApex", "legacy_migrated": False}
            atomic_write_json(self.marker_path, data)
        return data

    def _write_marker(self):
        atomic_write_json(self.marker_path, self.meta)

    # --- eski surumden ice aktarma (bir kez) ---
    def migrate_legacy(self, legacy_dirs):
        """Eski PedalHaptic'in exe/py yanindaki ayarlar.json ve profiller/ dosyalarini KOPYALAR
        (eskiler silinmez). Sadece bir kez ve yeni dosya yoksa. legacy_dirs: klasor ya da klasor listesi;
        icinde eski dosya bulunan ILK klasor kullanilir."""
        if self.meta.get("legacy_migrated"):
            return []
        if isinstance(legacy_dirs, str):
            legacy_dirs = [legacy_dirs]
        legacy_dir = next((d for d in legacy_dirs if os.path.isfile(os.path.join(d, "ayarlar.json"))
                           or os.path.isdir(os.path.join(d, "profiller"))), None)
        done = []
        try:
            if legacy_dir is None:
                raise StopIteration
            old = os.path.join(legacy_dir, "ayarlar.json")
            new = self.path("settings", "pedal_settings.json")
            if os.path.isfile(old) and not os.path.exists(new):
                with open(old, "r", encoding="utf-8") as f:
                    json.load(f)  # bozuk dosyayi kopyalama
                shutil.copy2(old, new)
                done.append("ayarlar.json")
            pdir = os.path.join(legacy_dir, "profiller")
            if os.path.isdir(pdir):
                for fn in os.listdir(pdir):
                    src, dst = os.path.join(pdir, fn), self.path("profiles", fn)
                    if fn.lower().endswith(".json") and not os.path.exists(dst):
                        try:
                            with open(src, "r", encoding="utf-8") as f:
                                json.load(f)
                            shutil.copy2(src, dst)
                            done.append("profiller/" + fn)
                        except Exception:
                            pass
        except StopIteration:
            return done              # eski dosya yok: isareti koyma, sonra bulunursa alinsin
        except Exception:
            pass
        self.meta["legacy_migrated"] = True
        self._write_marker()
        return done

    # --- tum kullanici verisini silme ---
    def is_safe_to_wipe(self):
        return os.path.isfile(self.marker_path) and os.path.isdir(self.root)

    def wipe_user_data(self):
        """records/sessions/settings/profiles/backups ICERIGINI siler (program dosyalarina dokunmaz).
        (silinen_dosya_sayisi, hatalar) dondurur. Klasor yapisi bos olarak yeniden kurulur."""
        if not self.is_safe_to_wipe():
            raise RuntimeError("Guvenlik: bu klasor PitApex veri klasoru olarak dogrulanamadi.")
        removed, errors = 0, []
        for sub in SUBDIRS:
            d = self.path(sub)
            if not os.path.isdir(d):
                continue
            for entry in os.scandir(d):
                try:
                    if entry.is_symlink() or entry.is_file():
                        os.remove(entry.path)
                    else:
                        shutil.rmtree(entry.path)
                    removed += 1
                except OSError as e:
                    errors.append("%s: %s" % (entry.name, e))
        for sub in SUBDIRS:
            os.makedirs(self.path(sub), exist_ok=True)
        # eski surum dosyalari geri gelmesin
        self.meta["legacy_migrated"] = True
        self._write_marker()
        return removed, errors
