"""PitApex interface translations; untranslated technical labels stay unchanged."""
TRANSLATIONS = {
 'Sim racing donanım ve telemetri merkezi':'Sim racing hardware and telemetry center',
 '⚙ Ayarlar':'⚙ Settings', 'Pedallar':'Pedals', 'Oyun Bilgileri':'Game Info',
 'Kaydedilen Rekorlar':'Saved Records', 'İstatistikler':'Statistics',
 'Overlay Yönetimi':'Overlay Management', 'Arduino bağlantısı (pedal + fan ortak)':'Arduino connection (shared by pedals and fan)',
 'Yenile':'Refresh', 'Bağlan':'Connect', 'Kes':'Disconnect', 'Bağlı değil':'Disconnected',
 'Bağlı':'Connected', 'Gecikme: -':'Latency: -', 'Görünüm':'Appearance',
 'Veri konumu':'Data location', 'Klasörü aç':'Open folder',
 'Tehlikeli İşlemler':'Danger Zone', 'Tüm verilerimi temizle…':'Delete all my data…',
 'Dil':'Language', 'Türkçe':'Turkish', 'İngilizce':'English',
 'Koyu tema':'Dark theme', 'Açık tema':'Light theme',
 'Pratik':'Practice', 'Sıralama':'Qualifying', 'Yarış':'Race',
 'Geçerli':'Valid', 'Geçersiz':'Invalid', 'Bilinmiyor':'Unknown',
 'Pist':'Track', 'Araç':'Car', 'Oyun':'Game', 'Süre':'Duration',
 'En hızlı tur':'Fastest lap', 'Tur':'Lap', 'Turlar':'Laps',
 'Tarih':'Date', 'Oturum':'Session', 'Oturum türü':'Session type',
 'Rekorlar, oturum geçmişi, ayarlar, profiller ve yedekler dahil bütün kullanıcı verilerini siler. Geri alınamaz.':
 'Deletes all user data including records, session history, settings, profiles and backups. This cannot be undone.',
 'Önce bir port seç.':'Select a port first.',
 'Bağlanılamadı:':'Connection failed:',
 'Arduino hazırlanıyor...':'Initializing Arduino...',
 '● Bağlandı':'● Connected', '● Bağlantı kesildi':'● Connection lost', '● Veri bekleniyor':'● Waiting for data',
 'Yeni rekor:':'New personal best:', 'Tur:':'Lap:',
 'Ayarlar yüklendi.':'Settings imported.', 'Ayar yedekleme / Settings backup':'Settings backup',
 'JSON dışa aktar / Export':'Export JSON', 'JSON içe aktar / Import':'Import JSON',
}


# Extended UI strings: preserve programmatic identifiers and stored data.
TRANSLATIONS.update({
 'Overlay pencerelerini ayrı ayrı yönet. Pencereyi sürükleyerek taşı; sağ alt köşeden boyutlandır.':'Manage overlay windows individually. Drag to move; resize from the bottom-right corner.',
 'Pedal göstergesi':'Pedal display','Araç Durumu':'Vehicle status','Parça Durumu':'Component status','Hız göstergesi':'Speed display','Devir ve vites':'RPM and gear','Tur bilgisi':'Lap information',
 'Overlay penceresini göster':'Show overlay window','Gaz / Fren':'Throttle / Brake','Arka plan saydamlığı (%)':'Background transparency (%)',
 'Artınca arka plan kaybolur; yazılar ve göstergeler net kalır. %0 = tam opak.':'Higher values hide the background while keeping text and gauges visible. 0% = fully opaque.',
 'Genişlik':'Width','Yükseklik':'Height','Boyutu uygula':'Apply size','Grafik geçmişi (saniye)':'Graph history (seconds)','Grafik süresini uygula':'Apply graph duration',
 'Efektler (kutucukla aç; detaylar açılınca görünür)':'Effects (enable with checkbox; details appear when enabled)',
 'Motor ince ayarı':'Motor fine tuning','İnce ayar':'Fine tuning','Güç %':'Power %','Motor':'Motor','Kontrol':'Control',
 'Hıza bağlı fan kontrolü açık':'Speed-dependent fan control enabled','Hız → fan gücü eğrisi':'Speed → fan power curve',
 'Fan testi (oyun gerekmez)':'Fan test (game not required)','Telemetri yokken:':'When telemetry is unavailable:',
 'Oyun (pedal titreşimi için telemetri kaynağı)':'Game (telemetry source for pedal haptics)',
 'Otomatik algıla':'Auto detect','Oyun algılanmadı':'No game detected','Veri bekleniyor':'Waiting for data',
 'Bekleniyor...':'Waiting...','Kaydet':'Save','Kaydedildi.':'Saved.','Kaydedilmedi — %s':'Not saved — %s',
 'Yükle':'Load','Uygula':'Apply','Durdur':'Stop','Varsayılana dön':'Restore defaults','Profiller':'Profiles',
 'Tümünü aç':'Enable all','Tümünü kapat':'Disable all','Test (1 sn)':'Test (1 sec)','Test (5 sn)':'Test (5 sec)',
 'Canlı telemetri':'Live telemetry','Oyun:':'Game:','Oturum İstatistikleri':'Session statistics',
 'Tümü':'All','Tür':'Type','Tur süresi':'Lap time','Fark':'Delta','Durum':'Status','Açıklama':'Description',
 'Seçilen oturumun turları  •  Yeşil: geçerli  •  Kırmızı: geçersiz  •  Gri: eski kayıtta durum bilinmiyor':'Selected session laps  •  Green: valid  •  Red: invalid  •  Gray: status unavailable for old records',
 "Oturum türü oyun telemetrisinden alınamadığında 'Bilinmiyor' gösterilir.":"When the game does not report session type, 'Unknown' is displayed.",
 'Doğrulandı':'Verified','Filtrelerle kabul edildi':'Accepted by filters','Eski kayıt':'Legacy record',
 'Turun bireysel doğrulama bilgisi saklanmamış':'Individual lap validation was not saved',
 'Oturum:':'Session:','Pist:':'Track:','Araç:':'Car:',
 'Siyah tema':'Dark theme','Beyaz tema':'Light theme','İPTAL':'CANCEL','Verileri sil':'Delete data',
 'Lastik sıcaklığı renkleri':'Tyre temperature colors','Oyun tip vermezse':'When game does not report tyre type',
 'Seri gecikme:':'Serial latency:','Gecikme: - | döngü: %d Hz':'Latency: - | loop: %d Hz',
 'Arayüz hatası:':'UI error:','Oyun  ›  Pist  ›  Araç modeli':'Game  ›  Track  ›  Car model',
 'PITAPEX · PEDALS':'PITAPEX · PEDALS','PEDALLAR':'PEDALS','HIZ':'SPEED','DEVİR / VİTES':'RPM / GEAR','TUR BİLGİSİ':'LAP INFO',
 'Yeni kişisel rekor!':'New personal best!','Bağlantı kesildi':'Disconnected',
})

def translate(text, language):
    if language != 'en' or not isinstance(text, str):
        return text
    if text in TRANSLATIONS:
        return TRANSLATIONS[text]
    for tr, en in sorted(TRANSLATIONS.items(), key=lambda x: -len(x[0])):
        if text.startswith(tr) and (tr.endswith((':', '\n', ' ')) or (len(tr) >= 6 and text.startswith(tr + ':'))):
            return en + text[len(tr):]
    return text


def apply_language(widget, language):
    """Translate visible widget text and table headers; tolerate non-text widgets."""
    try:
        if 'text' in widget.keys():
            current = widget.cget('text')
            old = getattr(widget, '_pitapex_original_text', None)
            if old is None or current not in (old, translate(old, 'en')):
                old = current
                widget._pitapex_original_text = old
            translated = translate(old, language)
            if current != translated:
                widget.configure(text=translated)
        if widget.winfo_class() == 'Treeview':
            for col in widget['columns']:
                heading = widget.heading(col)
                current = heading.get('text', '')
                original = getattr(widget, '_pitapex_headings', {})
                old = original.get(col)
                if old is None or current not in (old, translate(old, 'en')):
                    old = current
                    original[col] = old
                    widget._pitapex_headings = original
                translated = translate(old, language)
                if current != translated:
                    widget.heading(col, text=translated)
    except (AttributeError, KeyError, TypeError, ValueError, __import__('tkinter').TclError):
        pass
    try:
        children = widget.winfo_children()
    except __import__('tkinter').TclError:
        children = ()
    for child in children:
        apply_language(child, language)

# Additional runtime messages and overlay captions.
TRANSLATIONS.update({
 'veri kaynağı bulunamadı':'telemetry source not found',
 'veri yapısı uyuşmuyor!':'incompatible telemetry format!',
 'bağlı, veri akmıyor (pist/pause?)':'connected, no telemetry (track/paused?)',
 'canlı veri':'live telemetry',
 'Telemetri bekleniyor':'Waiting for telemetry',
 'PITAPEX\nTelemetri bekleniyor':'PITAPEX\nWaiting for telemetry',
 'HIZ\n':'SPEED\n', 'DEVİR / VİTES\n':'RPM / GEAR\n',
 'TUR BİLGİSİ\n':'LAP INFO\n',
 'Tur ':'Lap ', 'Anlık ':'Current ', 'En iyi ':'Best ',
 'Gaz ':'Throttle ', 'Fren ':'Brake ',
 'Hız':'Speed', 'Vites':'Gear', 'RPM / Vites':'RPM / Gear',
 'Üstten araç, lastikler ve desteklenen hasar verileri':'Top-down vehicle, tyres and supported damage data',
 'Desteklenen mekanik durum verileri':'Supported mechanical condition data',
 'Veri yok':'No data', 'Bağlantı yok':'No connection',
 'Arayüz hatası:':'UI error:',
})

# Effect configuration, status and dynamically populated captions.
TRANSLATIONS.update({
 'Gaz':'Throttle', 'Fren':'Brake', 'Kayma':'Wheel slip',
 'Tekerlek kilitlenme':'Wheel lockup', 'Devir sınırı':'Rev limiter',
 'Vites geçişi':'Gear shift', 'Vites yükseltme (Gear Up)':'Shift up (Gear Up)',
 'Vites düşürme (Gear Down)':'Shift down (Gear Down)',
 'Motor gücü / şiddet %':'Motor power / intensity %',
 'Motor gücü / şiddet':'Motor power / intensity',
 'Minimum güç %':'Minimum power %', 'Maksimum güç %':'Maximum power %',
 'Frekans Hz (0=sürekli)':'Frequency Hz (0=continuous)',
 'Darbe oranı %':'Duty cycle %', 'Aktivasyon eşiği':'Activation threshold',
 'Tutma süresi ms':'Hold duration ms', 'Hassasiyet % (50=varsayılan)':'Sensitivity % (50=default)',
 'Hassasiyet: kayma eşiği aşıldığında şiddetin ne kadar hızlı tam güce çıktığı.':'Sensitivity: how quickly intensity reaches full power after the slip threshold is exceeded.',
 'Fren motoru (M1)':'Brake motor (M1)', 'Gaz motoru (M2)':'Throttle motor (M2)',
 'Bağlı değil':'Disconnected', 'Bağlı':'Connected', 'Bağlan':'Connect', 'Kes':'Disconnect',
 'Arduino hazırlanıyor...':'Initializing Arduino...',
 'fan için v3 kodu gerekli':'fan requires v3 firmware',
 'Arduino kodu eski/uyumsuz! PedalHaptic.ino\'yu yeniden yükle':'Arduino firmware outdated/incompatible! Reflash PedalHaptic.ino',
 'Oyun algılanmadı':'Game not detected', 'Bekleniyor...':'Waiting...',
 'Önce bir port seç.':'Select a port first.',
 'Serial Monitor açıksa kapat.':'Close Serial Monitor if it is open.',
 'Bazı dosyalar silinemedi:':'Some files could not be deleted:',
 'Tüm kullanıcı verileri temizlendi. PitApex temiz veriyle çalışmaya devam ediyor.':'All user data deleted. PitApex continues with clean data.',
})

TRANSLATIONS.update({
 'Fan yuvaları ve çıkışlar':'Fan slots and outputs','Yuva':'Slot','Açık':'On','Çıkış (motor shield)':'Output (motor shield)',
 'Seçilmedi':'Not selected','Motor(lar)':'Motor(s)','＋ Motor ekle':'＋ Add motor',
 'Telemetri yokken:':'When telemetry is unavailable:',
})
TRANSLATIONS.update({'LED Aydınlatma':'LED Lighting','LED kartı bağlantısı (ayrı Arduino)':'LED board connection (separate Arduino)','Gösterilecek bilgi':'Displayed information','Ekran ayarları':'Display settings','Önizleme':'Preview','LED aydınlatma açık':'LED lighting enabled'})


# LED matrix: new flags, proximity alerts, settings, tests and help text.
TRANSLATIONS.update({
    'LED kartı bağlı değil':'LED board disconnected',
    'Açılışta otomatik bağlan':'Connect automatically at startup',
    'Özellik:':'Feature:',
    'Vites göstergesi':'Gear display',
    'Vites verisi, pedal sayfasında seçili/algılanan oyundan gelir (R, N, 1-9; 10+ için '+').': 'Gear data comes from the game selected/detected on the pedals page (R, N, 1-9; 10+ shown as +).',
    'Boştayken (N) göster:':'Show in neutral (N):',
    'Oyun verisi yokken:':'When game data is unavailable:',
    'Bağımsız LED özellikleri ve renkler':'Independent LED features and colors',
    'Yarış bayrakları':'Racing flags',
    'Yan araç uyarısı':'Nearby car warning',
    'Öncelik: yan araç > bayrak > vites. Renkler MAX7219 üzerinde değil, yalnızca önizlemede görünür.':'Priority: nearby car > flag > gear. Colors are visible only in the preview, not on MAX7219.',
    'Mavi':'Blue', 'Yeşil':'Green', 'Sarı':'Yellow', 'Çift sarı':'Double yellow',
    'Beyaz':'White', 'Siyah-beyaz uyarı':'Black-and-white warning',
    'Mekanik arıza':'Mechanical failure', 'Siyah':'Black', 'Pit':'Pit',
    'Son tur':'Final lap', 'Kırmızı':'Red', 'Damalı':'Checkered',
    'Sol araç':'Car on left', 'Sağ araç':'Car on right',
    'Renk':'Color', 'Test':'Test', 'Parlaklık (0-15)':'Brightness (0-15)',
    'Dönme (saat yönü)':'Rotation (clockwise)',
    'Yatay ayna':'Mirror horizontally', 'Dikey ayna':'Mirror vertically',
    'Test (oyun gerekmez)':'Test (no game required)',
    'Yön testi (R)':'Orientation test (R)',
    "Tüm LED'ler açık":'All LEDs on',
    'Testler 4 saniye sürer. Harf düzgün okunuyorsa yön doğrudur.':'Tests run for 4 seconds. If the letter is readable, the orientation is correct.',
    'LED önizleme rengi: ':'LED preview color: ',
    'Donanım notları':'Hardware notes',
    'N harfi':'Letter N', '0 rakamı':'Digit 0',
    'Ekran boş kalsın':'Leave display blank', 'Çizgi (-) göster':'Show dash (-)',
    'Bayrak: ':'Flag: ', 'Yan araç: ':'Nearby car: ', 'Vites: ':'Gear: ',
    'Veri yok (çizgi)':'No data (dash)', 'Veri yok (boş)':'No data (blank)',
    'sol':'left', 'sağ':'right',
})

TRANSLATIONS['Donanım notları\n• LED kartı, pedal/fan Arduino\'sundan AYRI bir Arduino\'ya bağlanır (kendi USB portu). Arduino\'ya firmware/LedMatrix/LedMatrix.ino yüklenir; Arduino IDE\'de "LedControl" kütüphanesi gerekir.\n• Varsayılan bağlantı: MAX7219 VCC→5V, GND→GND, DIN→D12, CLK→D11, CS→D10 (kodun başındaki PIN_* satırlarıyla değiştirilir).\n• Modüllerin kablolaması farklı olabilir: harf yan ya da ters görünürse "Yön testi"ni kullanıp dönme ve ayna ayarını harf düzgün görünene kadar değiştir.\n• Parlaklığı düşük tutmak (2-6) hem gözü yormaz hem Arduino USB gücüyle daha güvenli çalışır; tüm LED\'ler yanık ve parlaklık yüksekse modül yaklaşık 300 mA çekebilir.\n• PC kapanır ya da USB kopar ise LED kartı 3 saniye sonra ekranı kendiliğinden temizler.'] = 'Hardware notes\
• Connect the LED matrix to a SEPARATE Arduino from the pedal/fan controller (its own USB port). Upload firmware/LedMatrix/LedMatrix.ino; install the LedControl library in Arduino IDE.\
• Default MAX7219 wiring: VCC→5V, GND→GND, DIN→D12, CLK→D11, CS→D10. You can change these in the PIN_* definitions.\
• If letters are mirrored or rotated, use the orientation test and adjust rotation/mirroring until readable.\
• Keep brightness low (2–6) for comfort and safer USB power. With all LEDs lit at high brightness, the module may draw around 300 mA.\
• If the PC turns off or USB disconnects, the matrix clears itself after 3 seconds.'

# Additional English coverage for LED controls, tooltips and recently added features.
TRANSLATIONS.update({'Bağımsız LED özellikleri ve renkler': 'Independent LED features and colors', 'Özellik:': 'Feature:', 'Vites': 'Gear', 'Yarış bayrakları': 'Race flags', 'Yan araç uyarısı': 'Nearby car warning', 'Sol araç': 'Car on left', 'Sağ araç': 'Car on right', 'İki tarafta araç': 'Cars on both sides', 'Arkadan araç': 'Car behind', 'Renk / Color': 'Color', 'Özelleştir / Customize': 'Customize', 'Araç ayarı değişiklikleri / In-car adjustments': 'In-car adjustment changes', "Değişiklikleri LED'de göster / Show changes": 'Show adjustment changes on LED', 'Gösterim süresi (sn) / Duration': 'Display duration (sec)', 'Animasyonlar / Animations': 'Animations', 'Yarış bayrakları / Flags': 'Race flags', 'Yan araç / Proximity': 'Nearby cars', ' - Yanıp sönsün / Blink': ' - Blink', 'Hız / Speed (1-10)': 'Speed (1–10)', 'Yalnızca LED ayarları / LED settings only': 'LED settings only', "LED'i sıfırla / Reset LED": 'Reset LED', 'LED Pixel Mapping / LED piksel atama': 'LED pixel mapping', 'Yön testi (R)': 'Orientation test (R)', "Tüm LED'ler açık": 'All LEDs on', 'Önizleme': 'Preview', 'Boştayken (N) göster:': 'Display in neutral (N):', 'Oyun verisi yokken:': 'When game data is unavailable:', "Vites verisi, pedal sayfasında seçili/algılanan oyundan gelir (R, N, 1-9; 10+ için '+').": 'Gear data comes from the game selected/detected on the pedal page (R, N, 1–9; + for 10+).', 'Öncelik: yan araç > bayrak > vites. Renkler MAX7219 üzerinde değil, yalnızca önizlemede görünür.': 'Priority: nearby car > flag > gear. Colors appear only in the preview, not on MAX7219 hardware.', '8×8 çözünürlük nedeniyle ayar adları gösterilmez; yalnızca yeni sayı gösterilir.': 'Due to the 8×8 resolution, adjustment names are hidden; only the new number is shown.', 'Yeşil = değer artırıldı; kırmızı = değer azaltıldı (iyi/kötü anlamına gelmez).': 'Green = value increased; red = value decreased (not good/bad).', "BB (Brake Bias) gösterilmez: 55.8 gibi ondalıklı değerler 8×8'de okunaklı değildir.": 'BB (Brake Bias) is hidden: decimal values such as 55.8 are not legible on 8×8.', 'Öncelik: yan araç > bayrak > değişen ayar > vites. Veri yoksa gösterilmez.': 'Priority: nearby car > flag > adjustment change > gear. No display without data.', 'Yalnızca LED ayarları silinir; tur kayıtları, pedal, fan ve diğer ayarlar korunur.': 'Only LED settings are reset; lap records, pedals, fans, and other settings remain unchanged.', 'Testler 4 saniye sürer. Harf düzgün okunuyorsa yön doğrudur.': 'Tests last 4 seconds. Orientation is correct when the letter is readable.', 'Özelleştirilecek değer / Value (0–99):': 'Value to customize (0–99):', 'Vites / Gear (1-9, N, R, +, -):': 'Gear (1–9, N, R, +, -):', 'Geçersiz vites / Invalid gear': 'Invalid gear', "Click each pixel to toggle / Her LED'e tıklayarak değiştir": 'Click a pixel to toggle it', 'Tümünü yak': 'Turn all on', 'Tümünü temizle': 'Clear all', 'Varsayılanı yükle': 'Load defaults', 'Kaydet ve kapat': 'Save and close', 'LED ayarları': 'LED settings', 'LED bağlantısı': 'LED connection', 'Yanıp sönme': 'Blink', 'Çift sarı': 'Double yellow', 'Son tur': 'Final lap', 'Damalı': 'Checkered', 'Siyah-turuncu': 'Black-orange', 'Siyah-beyaz': 'Black-white', 'Mavi bayrak': 'Blue flag', 'Yeşil bayrak': 'Green flag', 'Sarı bayrak': 'Yellow flag', 'Kırmızı bayrak': 'Red flag', 'Beyaz bayrak': 'White flag', 'Siyah bayrak': 'Black flag', 'Pit bayrağı': 'Pit flag', 'Siyah-turuncu bayrak': 'Black-orange flag', 'Çift sarı bayrak': 'Double yellow flag', 'Ayarları kaydet': 'Save settings', 'LED testi': 'LED test', 'Sıfırla': 'Reset'})

TRANSLATIONS.update({'Özelleştir': 'Customize', 'Renk': 'Color', 'Araç ayarı değişiklikleri': 'In-car adjustment changes', "Değişiklikleri LED'de göster": 'Show adjustment changes on LED', 'Gösterim süresi (sn)': 'Display duration (sec)', 'Animasyonlar': 'Animations', 'Yan araç': 'Nearby cars', ' - Yanıp sönsün': ' - Blink', 'Hız (1-10)': 'Speed (1–10)', 'Yalnızca LED ayarları': 'LED settings only', "LED'i sıfırla": 'Reset LED', 'LED piksel atama': 'LED pixel mapping', 'Özelleştirilecek değer (0–99):': 'Value to customize (0–99):', 'Vites (1-9, N, R, +, -):': 'Gear (1–9, N, R, +, -):'})
