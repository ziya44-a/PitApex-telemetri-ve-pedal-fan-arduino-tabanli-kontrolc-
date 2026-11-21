"""Dort desteklenen oyundan hangisinin acik oldugunu bulur (Oyun Bilgileri icin)."""
import time

from core.winmem import SharedMap, process_start_epoch, process_table

# AC ve ACC ayni bellek adini kullanir: ayrim SADECE program adindan yapilir.
EXE_GAMES = [
    ("acs.exe", "AC"), ("acs_x86.exe", "AC"),
    ("ac2-win64-shipping.exe", "ACC"),
    ("le mans ultimate.exe", "LMU"),
]
PRIORITY = ("ACC", "AC", "LMU", "iRacing")
MEM_FALLBACK = {"iRacing": "Local\\IRSDKMemMapFileName", "LMU": "$rFactor2SMMP_Telemetry$"}


class GameDetector:
    def __init__(self):
        self.maps = {g: SharedMap(name, 0) for g, name in MEM_FALLBACK.items()}

    def detect(self, current=None):
        """(game_id, pid, baslangic_epoch) veya None. Zaten acik olan oyun varsa onu tercih eder."""
        table = process_table()
        found = {}
        for exe, gid in EXE_GAMES:
            if exe in table:
                found.setdefault(gid, table[exe])
        for name, pid in table.items():
            if name.startswith("iracingsim"):
                found.setdefault("iRacing", pid)
        if not found:      # program adi bulunamadiysa (iRacing/LMU icin) bellek varligina bak
            for gid, m in self.maps.items():
                if m.exists():
                    found.setdefault(gid, None)
        if not found:
            return None
        gid = current if current in found else next(g for g in PRIORITY if g in found)
        pid = found[gid]
        return gid, pid, process_start_epoch(pid) if pid else None
