"""Sahte tkinter ile uygulamanin bastan sona kurulup calistirildigi duman testi.
Calistirma:  PYTHONPATH=tests/fake_tk python3 tests/smoke_ui.py
(Gercek Tk yerlesimini/gorunumunu dogrulamaz; isim/mantik hatalarini yakalar.)"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "fake_tk"))
sys.path.insert(1, ROOT)

import tkinter as tk  # noqa: E402  (sahte)
from tkinter import messagebox  # noqa: E402

from core.models import TelemetryFrame  # noqa: E402
from tests.helpers import temp_dm  # noqa: E402
from ui.dialogs import WipeDialog  # noqa: E402
from ui.main_window import App  # noqa: E402

ok = []


def check(cond, name):
    ok.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


def text(row):
    return row.val._cfg.get("text")


dm = temp_dm()
root = tk.Tk()
app = App(root, dm)
for _ in range(14):
    app.tick()
check(True, "uygulama kuruldu ve 14 tick hatasiz calisti")
check(not app.banner._cfg.get("text", "").startswith("Arayüz hatası"), "tick icinde arayuz hatasi yok")

# --- sayfa gecisi ---
app.tab_var.set(2)
app.show_tab()
check(app.current == 2 and app.prefs.get("last_tab") == 2, "sekme degisimi ve son sekme kaydi")

# --- Oyun Bilgileri: manager'i durdur, kontrollu veri ver ---
app.telemetry.running = False
time.sleep(0.2)
f = TelemetryFrame(game="ACC", t=time.monotonic(), live=True, track_id="spa", track_name="Spa-Francorchamps",
                   car_id="ferrari_296_gt3", car_name="Ferrari 296 GT3", speed_kmh=187.0, rpm=7200,
                   throttle=0.8, brake=0.0, gear=3, abs_active=0.0, abs_level=4.0, tc_active=0.3, tc_level=3.0,
                   fuel_l=42.5, tyre_temp_c=[80.0, 81.0, 82.0, None], tyre_press_kpa=[189.6] * 4,
                   water_c=92.0, oil_c=None, engine_running=True, lap_count=0, lap_current_ms=100, sector_index=0,
                   lap_valid=True, in_pit=False)
app.tracker.update(f, time.monotonic())
app.telemetry._state = {"game_id": "ACC", "game_name": "Assetto Corsa Competizione", "running": True,
                        "status": "Canlı", "frame": f, "elapsed_s": 3725.0, "clock_running": True}
app.records.submit("ACC", "Assetto Corsa Competizione", "spa", "Spa-Francorchamps", "ferrari_296_gt3",
                   "Ferrari 296 GT3", 141222, (40000, 60000, 41222), True)
app.info_page.tick(True)
R = app.info_page.rows
check(text(R["speed"]) == "187 km/h", "hiz: %s" % text(R["speed"]))
check(text(R["time"]) == "01:02:05", "oyun suresi: %s" % text(R["time"]))
check(text(R["gear"]) == "3", "vites")
check(text(R["oil"]) == "Veri alınamıyor", "yag sicakligi yok -> Veri alinamiyor")
check(text(R["water"]) == "92 °C", "su sicakligi")
check("27.5 psi" in text(R["tpress"]), "lastik basinci psi: %s" % text(R["tpress"]))
check("SaA —" in text(R["ttemp"]), "eksik lastik degeri '—': %s" % text(R["ttemp"]))
check(text(R["rec"]).startswith("2:21.222"), "rekor: %s" % text(R["rec"]))
check(R["rec"].val._cfg["style"] == "Saved.TLabel" and R["speed"].val._cfg["style"] == "Live.TLabel",
      "kayitli ve canli satirlar gorsel olarak ayri stilde")
check(text(R["tc"]) == "aktivite %30 · ayar 3", "TC: %s" % text(R["tc"]))
check(text(R["engine"]) == "Çalışıyor", "motor durumu")

# oyun kapandi: son oturumun verileri ekranda KALMALI (kayitli/◆ olarak), bos/sifir olmamali
app.tracker.end()
app.telemetry._state = {"game_id": None, "game_name": None, "running": False, "status": "Desteklenen bir oyun algılanmadı",
                        "frame": None, "elapsed_s": 3725.0, "clock_running": False}
app.info_page.tick(True)
check(text(R["speed"]) == "187 km/h" and R["speed"].val._cfg["style"] == "Saved.TLabel",
      "oyun kapaninca hiz korundu ve kayitli stilde: %s" % text(R["speed"]))
check(text(R["fuel"]) == "42.5 L" and "27.5 psi" in text(R["tpress"]) and text(R["water"]) == "92 °C",
      "yakit/lastik/su korundu")
check(text(R["track"]) == "Spa-Francorchamps" and text(R["car"]) == "Ferrari 296 GT3", "pist ve arac korundu")
check(text(R["laps"]) is not None and text(R["laps"]) != "Veri alınamıyor", "tur sayisi korundu: %s" % text(R["laps"]))
check(text(R["oil"]) == "Veri alınamıyor", "okunamayan alan yine 'Veri alinamiyor' (uydurma yok)")
check("korunuyor" in app.info_page.note_a._cfg.get("text", ""), "arayuz verinin korundugunu belirtiyor")

# telemetri kesildi ama oyun acik: oturum bitmez, veriler kalir
app.tracker.update(f, time.monotonic())          # yeni oturum (eskisi arsivlendi)
sess1 = app.tracker.snapshot()
app.telemetry._state = {"game_id": "ACC", "game_name": "Assetto Corsa Competizione", "running": True,
                        "status": "Veri akmıyor", "frame": None, "elapsed_s": 100.0, "clock_running": True}
app.info_page.tick(True)
check(text(R["speed"]) == "187 km/h" and not sess1["ended"], "telemetri kesilince oturum acik, veriler korundu")
check("Telemetri akmıyor" in app.info_page.note_a._cfg.get("text", ""), "telemetri kesintisi aciklandi")

# --- fan / pedal / rekor sayfalari ---
app.fan.status = {"text": "Aktif: 187 km/h → %60", "level": "ok", "speed": 187.0, "pct": 60.0, "pwm": 190}
app.fan_page.tick(True)
check(app.fan_page.get_cfg()["fans"][0]["max_speed"] == 300.0, "fan ayarlari sozluge esitlendi")
app.engine.snap = {"t": {"gas": 0.5, "brake": 0.1, "abs": 0.0, "tc": 0.0, "speed": 120.0, "slipRatio": [0] * 4,
                         "gear": 3, "rpm_ratio": 0.7, "valid": True, "packetId": 1}, "live": True,
                   "active": {"abs": True}, "valid": True}
app.pedals_page.tick(True)
check(app.pedals_page.bars["gas"]._cfg.get("value") == 50.0, "pedal sayfasi canli telemetriyi gosterdi")
app.records_page.refresh(force=True)
check(len(app.records_page.tree._tree) == 3, "rekor agaci: oyun + pist + arac dugumleri")

# --- pedal ayari kaydi ve geri yukleme ---
app.pedals_page.vars["abs"]["intensity"].set(33.0)
app.pedals_page.save_settings()
check(os.path.exists(dm.path("settings", "pedal_settings.json")), "pedal ayari Belgeler/PitApex'a yazildi")
name = app.profiles.save("Test Profil", app.cfg)
check(name in app.profiles.names(), "profil kaydi")

# --- tema ---
app.set_theme("light")
check(app.prefs.get("theme") == "light" and app.theme.name == "light", "tema degisti ve kaydedildi")

# --- silme diyalogu ---
d = WipeDialog(root, dm.root, app.theme)
d.var.set("sil")
d._changed()
check(d.ok._cfg.get("state") == "disabled", "kucuk 'sil' dugmeyi acmaz")
d.var.set("SİL")
d._changed()
check(d.ok._cfg.get("state") == "normal", "SİL yazinca dugme acilir")
d.var.set("")
d._changed()
d._stage2()
check(d.result is False, "SİL yazilmadan silme onaylanamaz")
d.var.set("SİL")
d._stage2()
check(d.result is True and messagebox.LOG[-1][0] == "yesno" and messagebox.LOG[-1][2].get("default") == "no",
      "ikinci onay kutusu 'default=no' ile soruldu")

# --- motor yuvalari (M1-M4) ve iki fan ---
pp = app.pedals_page
check(pp.motors["abs"] == [0], "ABS varsayilan olarak M1")
pp.add_motor("abs")
check(pp.motors["abs"] == [0, 1] and app.cfg["abs"]["motors"] == [0, 1], "ABS icin ikinci motor eklendi (M2)")
pp.pick_motor("abs", 1, "M4")
check(app.cfg["abs"]["motors"] == [0, 3], "ikinci yuva M4'e cevrildi")
pp.add_motor("abs"); pp.add_motor("abs")
check(pp.motors["abs"] == [0, 3, 1, 2] and len(pp.motors["abs"]) == 4, "4 motora kadar eklenebilir")
pp.add_motor("abs")
check(len(pp.motors["abs"]) == 4, "5. motor eklenemez")
pp.remove_motor("abs", 2)
check(pp.motors["abs"] == [0, 3, 2], "ek motor kaldirildi")
pp.remove_motor("abs", 0)
check(pp.motors["abs"][0] == 0, "ilk motor kaldirilamaz")
pp.pick_motor("abs", 2, "M1")
check(pp.motors["abs"] == [0, 3, 2], "ayni motor ikinci kez secilemez")
pp._apply_cfg({"abs": {"motor": 2}})
pp.sync_cfg()
check(app.cfg["abs"]["motors"] == [0, 1] and "motor" not in app.cfg["abs"], "eski 'motor: 2' ayari [M1, M2]'ye cevrildi")
pp._apply_cfg({"abs": {"motors": [2]}})
pp.sync_cfg()
fp = app.fan_page
fp.panels[0].vars["enabled"].set(True)
fp.panels[0].vars["output"].set("M3")
fp.sync()
check("⚠ M3" in pp.slot_warnings()["abs"][0], "ayni cikis fanda da seciliyse pedal efektinde uyari")
check("M3" in fp.warnings() and "Fan 1" in fp.warnings(), "fan sayfasinda cakisma uyarisi")
fp.panels[1].vars["enabled"].set(True)
fp.panels[1].vars["output"].set("M4")
fp.sync()
cfgs = fp.get_cfg()["fans"]
check([c["output"] for c in cfgs] == [3, 4] and all(c["enabled"] for c in cfgs), "iki fan yuvasi ayri cikislarla kaydedildi")
fp.panels[1].vars["output"].set("M3")
fp.sync()
check("aynı" in fp.warnings().lower() or "birden fazla" in fp.warnings(), "iki fan ayni cikista uyarilir")
fp.load_prefs({"enabled": True, "idle_pct": 33})
check(fp.get_cfg()["fans"][0]["idle_pct"] == 33.0 and fp.get_cfg()["fans"][0]["output"] == 3
      and not fp.get_cfg()["fans"][1]["enabled"], "eski tek-fan ayari Fan 1'e tasindi")
pp._apply_cfg({"abs": {"motors": [0]}})
pp.sync_cfg()

# --- LED aydinlatma sayfasi (MAX7219, ayri Arduino) ---
lp = app.led_page
check("LED Aydınlatma" in __import__("ui.main_window", fromlist=["TABS"]).TABS and lp in app.pages, "LED Aydınlatma sekmesi var")
check(app.led_link is not app.link, "LED kartinin pedal/fan'dan ayri baglantisi var")
lp.vars["enabled"].set(True)
lp.vars["brightness"].set(9)
lp.vars["rotation"].set("90°")
lp.vars["flip_h"].set(True)
lp.vars["neutral"].set("0 rakamı")
lp.vars["no_data"].set("Çizgi (-) göster")
lp.sync()
c = lp.get_cfg()
check(c["enabled"] and c["brightness"] == 9 and c["rotation"] == 90 and c["flip_h"] and c["gear"] == {"neutral": "0", "no_data": "dash"},
      "LED ayarlari sozluge esitlendi")
app.engine.snap = {"t": {"gear": 4, "gas": 0, "brake": 0, "abs": 0, "tc": 0, "speed": 50, "slipRatio": [0] * 4,
                         "rpm_ratio": 0, "valid": True, "packetId": 3}, "live": True, "active": {}, "valid": True}
app.engine.src.NAME = "LMU"
app.led.tick(1000.0)                                   # bagli degil: hicbir sey gonderilmez, onizleme yine de hesaplanir
check(app.led.status["gear"] == 4 and app.led.status["level"] == "off", "LED bagli degilken vites onizlemesi hesaplandi")
lp.tick(True)
check("bağlı değil" in lp.status_lbl["text"], "LED sayfasi durum metni")
lp.apply(__import__("core.led_matrix", fromlist=["x"]).normalized({}))
lp.sync()
check(not lp.get_cfg()["enabled"] and lp.get_cfg()["rotation"] == 0, "LED ayarlari varsayilana dondu")
lp.load_prefs({"enabled": True, "brightness": 12, "gear": {"neutral": "0"}})
check(lp.get_cfg()["brightness"] == 12 and lp.get_cfg()["gear"]["neutral"] == "0", "LED kayitli ayari yuklendi")
lp.vars["enabled"].set(False)
lp.sync()

# --- tum veriyi temizle ---
okw, msg = app.wipe_all()
check(okw, "wipe_all basarili: " + msg)
left = [os.path.join(dp, f) for dp, _, fs in os.walk(dm.root) for f in fs]
check(all(os.path.basename(x) in (".pitapex_data",) for x in left), "klasorde sadece isaret dosyasi kaldi: %s" % [os.path.basename(x) for x in left])
check(app.records.all_records() == [] and app.theme.name == "dark", "bellek temizlendi, tema varsayilana dondu")
check(app.pedals_page.vars["abs"]["intensity"].get() == 80, "pedal ayari varsayilana dondu")
app.pedals_page.save_settings()
check(not os.path.exists(dm.path("settings", "pedal_settings.json")), "temizlik sonrasi ayar dosyasi kendiliginden geri yazilmadi")
for _ in range(7):
    app.tick()
check(not app.banner._cfg.get("text", "").startswith("Arayüz hatası"), "temizlik sonrasi uygulama calismaya devam ediyor")

# --- kapanis ---
app.on_close()
check("destroy" in root.calls, "kapanis temiz")
print("\n%d/%d gecti" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
