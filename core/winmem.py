"""Windows'a ozgu dusuk seviye erisim: paylasimli bellek, surec listesi.
Bu dosya Windows disinda import edilebilir (testler icin); orada k32 = None olur."""
import ctypes
import os
import time

k32 = None
if os.name == "nt":
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    k32.OpenFileMappingW.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_uint32, ctypes.c_size_t]
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32FirstW.restype = ctypes.c_int
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32NextW.restype = ctypes.c_int
    try:
        ctypes.WinDLL("winmm").timeBeginPeriod(1)
    except Exception:
        pass
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_void_p]
    k32.GetProcessTimes.restype = ctypes.c_int
    k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    k32.VirtualQuery.restype = ctypes.c_size_t



class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32),
                ("th32ProcessID", ctypes.c_uint32), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.c_uint32), ("cntThreads", ctypes.c_uint32),
                ("th32ParentProcessID", ctypes.c_uint32), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_uint32), ("szExeFile", ctypes.c_wchar * 260)]


def running_processes():
    """Calisan program adlari (kucuk harf). Hata olursa bos kume doner."""
    names = set()
    if os.name != "nt":
        return names
    try:
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return names
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            names.add(pe.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
        k32.CloseHandle(snap)
    except Exception:
        pass
    return names


def process_table():
    """{kucuk_harf_exe_adi: pid} - ayni adli birden fazla surec varsa ilki."""
    table = {}
    if os.name != "nt":
        return table
    try:
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return table
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            table.setdefault(pe.szExeFile.lower(), pe.th32ProcessID)
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
        k32.CloseHandle(snap)
    except Exception:
        pass
    return table


def process_start_epoch(pid):
    """Surecin baslama zamani (epoch saniye). Alinamazsa None."""
    if os.name != "nt" or not pid:
        return None
    try:
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            c, e, k, u = (ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64())
            if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                return None
            epoch = c.value / 1e7 - 11644473600  # FILETIME -> epoch
            if epoch <= 0 or epoch > time.time() + 5:
                return None
            return epoch
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


class _MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_uint32), ("PartitionId", ctypes.c_uint16),
                ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_uint32),
                ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32)]


class SharedMap:
    """Salt-okunur paylasimli bellek. Oyun yokken hicbir sey olusturmaz; yoksa read() None doner."""

    def __init__(self, name, size):
        self.name, self.size = name, size
        self.handle = None
        self.ptr = None
        self.last_try = 0.0
        self.region = None

    def close(self):
        if os.name != "nt":
            return
        if self.ptr:
            k32.UnmapViewOfFile(self.ptr)
        if self.handle:
            k32.CloseHandle(self.handle)
        self.ptr = None
        self.handle = None

    def exists(self):
        if os.name != "nt":
            return False
        h = k32.OpenFileMappingW(0x4, False, self.name)
        if h:
            k32.CloseHandle(h)
            return True
        return False

    def _ensure_mapped(self):
        if os.name != "nt":
            return False
        if self.ptr:
            return True
        if time.time() - self.last_try < 0.5:
            return False
        self.last_try = time.time()
        h = k32.OpenFileMappingW(0x4, False, self.name)
        if not h:
            return False
        p = k32.MapViewOfFile(h, 0x4, 0, 0, 0)  # 0 -> haritanin tamami (boyut tasmasi olmaz)
        if not p:
            k32.CloseHandle(h)
            return False
        self.handle, self.ptr = h, p
        self.region = None
        try:
            mbi = _MBI()
            if k32.VirtualQuery(p, ctypes.byref(mbi), ctypes.sizeof(mbi)):
                self.region = int(mbi.RegionSize)
        except Exception:
            self.region = None
        return True

    def read_at(self, offset, size):
        """offset'ten size bayt. Haritanin otesine asla okumaz (kisa donebilir). Yoksa None."""
        if not self._ensure_mapped():
            return None
        try:
            if self.region is not None:
                if offset >= self.region:
                    return b""
                size = min(size, self.region - offset)
            return ctypes.string_at(self.ptr + offset, size)
        except Exception:
            self.close()
            return None

    def read(self, size=None):
        return self.read_at(0, size or self.size)
