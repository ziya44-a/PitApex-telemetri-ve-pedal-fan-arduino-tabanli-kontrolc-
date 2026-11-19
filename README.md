# PitApex-telemetri-ve-pedal-fan-arduino-tabanli-kontrolc-
PitApex; Arduino tabanlı pedal titreşimi, hıza duyarlı kokpit fanı kontrolü, özelleştirilebilir arayüz katmanları (overlay), araç durumu görselleştirme ve tur rekoru takibi özelliklerini barındıran bir simülasyon yarışı telemetri ve dokunsal geri bildirim uygulamasıdır. ACC, AC, LMU ve iRacing oyunlarını destekler.


🏁 PitApex

Sim Racing Telemetry • Haptic Feedback • Cockpit Fan Control

PitApex, simülasyon yarışları için geliştirilmiş, gerçek zamanlı telemetri takibi, Arduino tabanlı pedal titreşimleri, hıza duyarlı kokpit fanı ve sürüş performansı analizini tek bir uygulamada birleştiren Windows yazılımıdır.

Yarış simülasyonlarından alınan verileri fiziksel geri bildirimlere dönüştürerek sürüş deneyimini geliştirmeyi ve pilotlara daha kapsamlı performans bilgileri sunmayı amaçlar.

🎮 Desteklenen oyunlar

Simülasyon	Telemetri
Assetto Corsa Competizione	✅
Assetto Corsa	✅
Le Mans Ultimate	✅
iRacing	✅

Telemetri desteği oyunların sağladığı verilere bağlıdır. Bazı özellikler belirli oyunlarda kullanılamayabilir.

⚙️ Özellikler

1. Pedal Haptic Feedback

Arduino ve L293D Motor Shield kullanılarak pedallara fiziksel titreşim geri bildirimi sağlanır.

Desteklenen efektler:

* ABS aktivasyonu
* Traction Control (TC)
* Tekerlek kayması
* Tekerlek kilitlenmesi
* Fren limiti uyarısı
* Vites yükseltme
* Vites düşürme

Uygulama toplam 9 bağımsız efekt kontrolü içerir.

Her efekt için motor gücü, frekans, eşik, süre ve hassasiyet gibi ayarlar özelleştirilebilir. Efektler birbirinden bağımsız açılıp kapatılabilir.

2. Hıza Duyarlı Kokpit Fanı

Araç hızına göre fan gücünü otomatik değiştiren Arduino tabanlı kontrol sistemi.

* Gerçek zamanlı hız takibi
* Özelleştirilebilir hız/fan gücü eğrisi
* Minimum ve maksimum güç sınırları
* Yumuşak hız geçişleri
* Fan kalkış desteği
* Manuel test modu
* Telemetri bağlantısı kesildiğinde güvenlik kontrolü

Fan sistemi pedal efektlerinden bağımsız kullanılabilir.

3. Gerçek Zamanlı Telemetri

Desteklenen oyunlardan alınan sürüş bilgileri tek bir arayüzde görüntülenir.

* Hız, RPM ve vites
* Gaz ve fren kullanımı
* Yakıt miktarı
* Lastik sıcaklıkları ve basınçları
* Tur ve sektör süreleri
* Pist ve araç bilgileri
* Desteklenen oyunlarda ABS ve TC bilgileri

Oyun tarafından sağlanmayan veya doğrulanamayan veriler tahmin edilmez; veri bulunamadığı belirtilir.

4. Tur Süreleri ve Rekor Sistemi

Sürüş performansını takip etmek için kalıcı tur kayıt sistemi.

* Anlık tur süresi
* Son tur süresi
* En iyi tur
* Sektör süreleri
* Pist ve araç bazlı rekorlar
* Önceki oturumların saklanması
* Geçersiz veya şüpheli turların filtrelenmesi

Rekorlar oyun, pist ve araç modeline göre ayrı saklanır.

Oyun kapatılsa bile tamamlanan oturumların verileri korunur. Oyun geçerlilik bilgisi sunmuyorsa ilgili kayıtlar doğrulanmamış olarak işaretlenebilir.

5. Özelleştirilebilir Overlay Sistemi

PitApex, oyun üzerinde kullanılabilen bağımsız bilgi pencereleri sunar.

* Hız göstergesi
* Gaz ve fren telemetrisi
* RPM ve vites göstergesi
* Tur süresi bilgileri

Birden fazla overlay aynı anda açılabilir. Pencereler taşınabilir ve konumları kaydedilir.

6. Araç Durumu ve Lastik Takibi

Araç durumunu takip etmeyi kolaylaştıran görsel paneller.

* Üstten araç görünümü
* Bölgesel hasar gösterimi
* Lastik sıcaklıkları
* Lastik basınçları
* Kademeli renk göstergeleri

Görselleştirmeler, ilgili oyunun sağladığı telemetri alanlarına göre çalışır.

7. Kullanıcı Arayüzü ve Veri Yönetimi

* Siyah ve beyaz tema
* Bağımsız özellik panelleri
* Kullanıcı profilleri
* Kalıcı ayarlar
* Oturum geçmişi
* Otomatik veri yedekleme
* Bozuk kayıtlar için kurtarma mekanizması
* Onay gerektiren veri temizleme seçeneği

💻 Sistem Gereksinimleri

* Windows
* Python 3 (kaynak koddan çalıştırmak için)
* USB bağlantısı (Arduino özellikleri için)
* Desteklenen yarış simülasyonlarından biri

Arduino donanımı yalnızca fiziksel geri bildirim özellikleri için gereklidir.

📥 Kurulum

1. Projeyi indirin

GitHub üzerinden projeyi ZIP olarak indirin ve bilgisayarınıza çıkarın.

2. Gerekli yazılımları kurun

Bilgisayarınızda Python 3 kurulu olmalıdır.

PitApex klasöründe bulunan 1_kurulum.bat dosyasını çalıştırın.

Alternatif olarak terminal üzerinden:

py -m pip install -r requirements.txt

3. Uygulamayı başlatın

2_baslat.bat dosyasını çalıştırın.

Alternatif olarak:

py main.py

4. EXE oluşturma (isteğe bağlı)

Windows üzerinde bağımsız bir çalıştırılabilir dosya oluşturmak için:

3_exe_olustur.bat

Derleme başarılı olursa PitApex.exe oluşturulur.

Bu işlem, Python kurulumu gerektirmeyen bir dağıtım dosyası oluşturmayı amaçlar.

🔌 Arduino ve Motor Kurulumu

Gerekli donanımlar

* Arduino Uno
* L293D Motor Shield
* 12V DC titreşim motorları
* Uygun 12V güç kaynağı
* İsteğe bağlı uyumlu DC fan

Firmware yükleme

1. Arduino IDE’yi açın.
2. Arduino’yu USB ile bilgisayara bağlayın.
3. firmware/PedalHaptic/PedalHaptic.ino dosyasını açın.
4. Kart ve COM portunu seçin.
5. Firmware’i Arduino’ya yükleyin.
6. PitApex’i başlatın.
7. İlgili bağlantı ve efekt ayarlarını yapılandırın.

Motor bağlantıları

Kanal	Kullanım
M1	Pedal titreşim motoru
M2	Pedal titreşim motoru
M3	Kokpit fanı (varsayılan)
M4	Alternatif fan kanalı

Fan kanalını değiştirmek için firmware içerisindeki FAN_MOTOR tanımı düzenlenebilir.

Dikkat: L293D sürücüsünün kanal başına sürekli akım kapasitesi yaklaşık 0,6 A’dir. Yüksek akımlı fanlar doğrudan bağlanmamalıdır. Fan ve güç kaynağı uyumluluğunu bağlantıdan önce kontrol edin.

📂 Veri Depolama

PitApex kullanıcı verilerini Windows Belgeler klasöründe saklar.

Belgeler/
└── PitApex/
    ├── records/
    ├── sessions/
    ├── settings/
    ├── profiles/
    └── backups/

Uygulama ayarları, oturum geçmişi, rekorlar ve yedekler bu klasörde tutulur.

Veri temizleme işlemi uygulama dosyalarını silmez.

🧪 Test ve Geliştirme Durumu

PitApex aktif geliştirme aşamasındadır.

Proje; telemetri adaptörleri, tur kayıt mantığı, pedal efektleri, fan kontrolü ve veri depolama için otomatik testler içerir.

Testleri çalıştırmak için:

py -m unittest discover -s tests -t .

Önemli: Otomatik testler gerçek oyun ve donanım testlerinin yerini tutmaz. Özellikle LMU ve iRacing entegrasyonları, overlay davranışları ve Arduino donanım uyumluluğu gerçek kullanım ortamında ayrıca doğrulanmalıdır.

🛠️ Kullanılan Teknolojiler

* Python
* Tkinter
* PySerial
* Arduino C++
* Shared Memory Telemetry
* JSON tabanlı veri depolama
* Pillow

🤝 Katkıda Bulunma

PitApex geliştirmeye ve topluluk katkılarına açıktır.

Hata bildirimleri, yeni özellik önerileri, farklı simülasyonlarla uyumluluk testleri ve kod iyileştirmeleri memnuniyetle karşılanır.

Hata ve öneriler için GitHub Issues kullanılabilir.

Bilinen hatalar
 Tur rekor sistemi geliştirme aşamasında olup düzgün çalışmama veya hiç çalışmama
 araç parça bilgi overlay penceresi oyunun sunduğu telemtri eksikliğinden çalışmamaktadır
 Ac ve Acc de test edilebilmiştir sadece 
 



PitApex — Beyond Telemetry. Feel the Race.

Turn racing data into real feedback.
