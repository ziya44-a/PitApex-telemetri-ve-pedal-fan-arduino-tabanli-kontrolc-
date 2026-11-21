"""Windows'un GERCEK Belgeler klasorunu bulur (OneDrive yonlendirmesi dahil)."""
import ctypes
import os
import sys


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


def _guid(s):
    import uuid
    u = uuid.UUID(s)
    g = _GUID()
    g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
    for i, b in enumerate(u.bytes[8:]):
        g.Data4[i] = b
    return g


def _known_folder_documents():
    """SHGetKnownFolderPath(FOLDERID_Documents): kullanici Belgeler'i tasidiysa (OneDrive dahil)
    tasinmis gercek yolu verir."""
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), ctypes.c_uint32,
                                             ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    fid = _guid("FDD39AD0-238F-46AF-ADB4-6C85480369C7")
    out = ctypes.c_wchar_p()
    hr = shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out))
    try:
        if hr != 0 or not out.value:
            return None
        return out.value
    finally:
        if out:
            ole32.CoTaskMemFree(out)


def _registry_documents():
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
    try:
        val, _ = winreg.QueryValueEx(key, "Personal")
    finally:
        winreg.CloseKey(key)
    return os.path.expandvars(val)


def get_documents_dir():
    """Belgeler klasorunun yolu. Bulunamazsa None."""
    override = os.environ.get("PITAPEX_DOCUMENTS")      # testler icin
    if override:
        return override
    candidates = []
    if os.name == "nt":
        for fn in (_known_folder_documents, _registry_documents):
            try:
                p = fn()
                if p:
                    candidates.append(p)
            except Exception:
                pass
    candidates.append(os.path.join(os.path.expanduser("~"), "Documents"))
    for p in candidates:
        if p and os.path.isdir(p):
            return p
    return None


def app_dir():
    """Program dosyalarinin klasoru (kullanici verisi BURAYA yazilmaz; sadece eski ayarlari ice aktarmak icin okunur)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    """Paketlenmis (PyInstaller) veya normal calismada program kaynaklarinin yolu."""
    base = getattr(sys, "_MEIPASS", None) or app_dir()
    return os.path.join(base, *parts)
