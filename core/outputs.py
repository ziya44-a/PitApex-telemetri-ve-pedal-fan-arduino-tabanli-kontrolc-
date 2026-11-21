"""Motor shield cikislari (M1..M4) icin ortak mantik: hangi cikis neyde kullaniliyor, cakisma var mi.
Tk'dan bagimsizdir (test edilebilir). Cikis numaralari 1 tabanlidir (M1=1 ... M4=4); 0 = secilmedi (yalniz fan)."""
from core.engine import EFFECTS, MOTOR_NAMES, effect_motors

NONE_LABEL = "Seçilmedi"


def out_name(n):
    """1..4 -> 'M1'..'M4'; 0/None -> 'Seçilmedi'."""
    return MOTOR_NAMES[n - 1] if isinstance(n, int) and 1 <= n <= len(MOTOR_NAMES) else NONE_LABEL


def pedal_outputs(cfg, only_enabled=True):
    """Pedal efektlerinin kullandigi cikislar: {cikis_no(1..4): [efekt_anahtari, ...]}."""
    used = {}
    for k in EFFECTS:
        ck = cfg.get(k) if isinstance(cfg, dict) else None
        if not isinstance(ck, dict) or (only_enabled and not ck.get("enabled")):
            continue
        for m in effect_motors(ck, k):
            used.setdefault(m + 1, []).append(k)
    return used


def fan_outputs(fans, only_enabled=True):
    """Fanlarin kullandigi cikislar: {cikis_no: [fan_no(1 tabanli), ...]} (yalniz secili ve - varsayilan - acik olanlar)."""
    used = {}
    for i, f in enumerate(fans or []):
        n = f.get("output", 0) if isinstance(f, dict) else 0
        if only_enabled and not (isinstance(f, dict) and f.get("enabled")):
            continue
        if isinstance(n, int) and 1 <= n <= 4:
            used.setdefault(n, []).append(i + 1)
    return used


def conflicts(pedal_cfg, fans, only_enabled=True):
    """Ayni cikisin hem pedal efektinde hem fanda ya da iki fanda kullanildigi durumlar.
    [(cikis_no, 'pedal+fan' | 'fan+fan', ayrinti_metni)]"""
    p, f = pedal_outputs(pedal_cfg, only_enabled), fan_outputs(fans, only_enabled)
    out = []
    for n in sorted(set(p) | set(f)):
        if n in p and n in f:
            out.append((n, "pedal+fan", "%s hem pedal efektinde hem Fan %s'de seçili" % (out_name(n), "/".join(map(str, f[n])))))
        if len(f.get(n, [])) > 1:
            out.append((n, "fan+fan", "%s birden fazla fan için seçili" % out_name(n)))
    return out


def needs_v4(pedal_cfg, fans, only_enabled=True):
    """Arduino kodu v4 gerektiren secimler (pedal M3/M4, fan icin yuva secimi/ikinci fan)."""
    reasons = []
    if any(n >= 3 for n in pedal_outputs(pedal_cfg, only_enabled)):
        reasons.append("pedal efektinde M3/M4")
    f = fan_outputs(fans, only_enabled)
    if len(f) > 1 or (f and 1 in f) or (f and 2 in f):
        reasons.append("fan için seçilebilir çıkış / ikinci fan")
    return reasons
