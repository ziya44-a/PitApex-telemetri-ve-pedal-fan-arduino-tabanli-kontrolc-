"""Guvenli (atomik) JSON yazma/okuma + yedekleme.

Yazma: gecici dosyaya yaz -> diske zorla (fsync) -> os.replace ile degistir. Elektrik kesilse
bile dosya ya eski ya yeni halindedir, yarim kalmaz.
Okuma: dosya bozuksa yan tarafa tasinir ve en yeni saglam yedekten geri yuklenir."""
import json
import os
import shutil
import time

BACKUP_MIN_INTERVAL = 300      # ayni dosyanin yedegi en fazla 5 dakikada bir alinir
BACKUP_KEEP = 10


def _ts():
    return time.strftime("%Y%m%d-%H%M%S")


def _backups_of(backup_dir, name):
    if not backup_dir or not os.path.isdir(backup_dir):
        return []
    pre = name + "."
    items = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
             if f.startswith(pre) and f.endswith(".bak")]
    items.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return items


def make_backup(path, backup_dir, force=False):
    """path'in anlik kopyasini backup_dir'e alir (hizli tekrar yedek almaz). Alinan yolu dondurur."""
    if not backup_dir or not os.path.isfile(path):
        return None
    os.makedirs(backup_dir, exist_ok=True)
    name = os.path.basename(path)
    existing = _backups_of(backup_dir, name)
    if existing and not force and time.time() - os.path.getmtime(existing[0]) < BACKUP_MIN_INTERVAL:
        return None
    dst = os.path.join(backup_dir, "%s.%s.bak" % (name, _ts()))
    n = 1
    while os.path.exists(dst):
        dst = os.path.join(backup_dir, "%s.%s-%d.bak" % (name, _ts(), n))
        n += 1
    shutil.copy2(path, dst)
    for old in _backups_of(backup_dir, name)[BACKUP_KEEP:]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


def atomic_write_json(path, data, backup_dir=None):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    json.loads(payload)  # yazmadan once geri okunabildigini dogrula
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if os.path.isfile(path):
            try:
                make_backup(path, backup_dir)
            except OSError:
                pass     # yedek alinamamasi kaydi engellemesin
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _load(path, validator):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if validator and not validator(data):
        raise ValueError("beklenmeyen veri yapisi")
    return data


def read_json(path, backup_dir=None, default=None, validator=None):
    """(veri, durum) dondurur. durum: 'ok' | 'missing' | 'restored' | 'reset'."""
    if not os.path.exists(path):
        return default, "missing"
    try:
        return _load(path, validator), "ok"
    except Exception:
        pass
    # bozuk: yan tarafa al (silme), yedekten dene
    try:
        shutil.move(path, "%s.corrupt-%s" % (path, _ts()))
    except OSError:
        pass
    for b in _backups_of(backup_dir, os.path.basename(path)):
        try:
            data = _load(b, validator)
        except Exception:
            continue
        try:
            shutil.copy2(b, path)
        except OSError:
            pass
        return data, "restored"
    return default, "reset"
