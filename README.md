!!Ac de çalışma hatası vermektedir sorunu en kısa sürede çözeceğim, AC de oyuna bağlanmadan motor arduino bağlantısını kesmeniz önerilir
# 🏁 PitApex
### Open-Source Sim Racing Telemetry & Hardware Control

**PitApex**, sim racing deneyimini geliştirmek için tasarlanmış, açık kaynaklı bir Windows uygulamasıdır.

Pedal titreşim sistemleri, hıza duyarlı kokpit fanları, 8×8 LED göstergeler, yarış telemetrisi, oyun içi overlay pencereleri ve tur rekorlarını tek bir uygulama üzerinden yönetmeyi amaçlar.

PitApex; özelleştirilebilir donanım kontrolü, sade bir kullanıcı arayüzü ve modüler yazılım mimarisi üzerine geliştirilmiştir.

**Platform:** Windows  
**Dil:** Türkçe / English  
**Geliştirme durumu:** Aktif geliştirme
Yapay zeka yardımıyla üretilmiştir
Yerelde çalısıp hiçbir sekilde internete bağlanmamaktadır
---

## Desteklenen Simülasyonlar

- Assetto Corsa Competizione (ACC)
- Assetto Corsa (AC)
- Le Mans Ultimate (LMU)
- iRacing
- Testler AC ve ACC de yapıldı, LMU da yapılacaktrı
- Oyunların telemetri altyapıları farklıdır. Bazı özellikler yalnızca belirli oyunlarda kullanılabilir.
- Deneysel entegrasyonların gerçek oyun ortamında doğrulansa bile sorunsuz çalışması için daha uğrasılmaktadır.

---
 ZİP sürümünde hazır şekilde hepsi vardır, ve yaptığım gücellemeleri en sonda belirtiyor olacağım(V6 açık kodlu sürümdür) güncellemeler ve hata düzeltmelerini ayrı ZİP dosyası olarak(V7 veya daha üstü) ekleyeceğim. biriklmesi ve önemli olduğu durumda yeni sürüm olarak paylaşacağım.
 Açık kodlar güncellenmeyecek yeni sürüme kadar
## ⚙️ Temel Özellikler

### 1. Pedal Haptic Feedback

Arduino ve motor sürücü kartlarıyla çalışan pedal titreşim sistemi.

Desteklenen efektler:

- ABS aktivasyonu
- Traction Control (TC)
- Tekerlek kayması
- Tekerlek kilitlenmesi
- Brake Limiter
- Vites yükseltme (Gear Up)
- Vites düşürme (Gear Down)

Her efekt bağımsız olarak açılıp kapatılabilir.

Kullanıcı; motor gücü, aktivasyon eşiği, hassasiyet, titreşim süresi ve motor çıkışlarını özelleştirebilir.

Motor çıkışları M1–M4 üzerinden yönetilebilir. Aynı motor çıkışının birden fazla fiziksel cihaz tarafından kullanılmasına karşı çakışma kontrolü bulunur.

### 2. Speed-Based Fan Control

Araç hızına göre çalışan kokpit fan sistemi.

Özellikler:

- Araç hızına bağlı otomatik fan kontrolü
- İki bağımsız fan desteği
- Özelleştirilebilir fan hız eğrileri
- Minimum ve maksimum güç ayarları
- Fan test sistemi
- Telemetri kesildiğinde güvenli davranış seçenekleri

Fan kontrolü için uygun Arduino motor sürücüsü ve fan donanımı gereklidir.

### 3. 8×8 LED Matrix System

PitApex, MAX7219 tabanlı 8×8 LED matrisleri için bağımsız bir kontrol sistemi içerir.

**Vites göstergesi**

- R, N ve 1–9 vitesleri
- Özelleştirilebilir LED desenleri
- Parlaklık ve ekran yönü ayarları

**Yarış bayrakları**

- Yeşil, sarı ve çift sarı
- Mavi, beyaz, kırmızı ve siyah
- Siyah-beyaz uyarı ve siyah-turuncu mekanik arıza
- Son tur ve damalı bayrak
- Bağımsız test ve desen seçenekleri

**Araç yakınlık uyarıları**

- Soldan araç: `[` deseni
- Sağdan araç: `]` deseni
- Her iki taraftan araç: `[ ]`
- Arkadan araç: En alt LED sırası

**Araç ayarı değişiklikleri**

TC, ABS, TC2 ve ECU Map gibi desteklenen sayısal ayar değişiklikleri LED üzerinde gösterilebilir.

- Yeşil: Değer artırıldı
- Kırmızı: Değer azaltıldı

Brake Bias, 8×8 matris üzerinde ondalıklı değerlerin okunabilirlik sınırı nedeniyle bu göstergeden çıkarılmıştır.

**LED özelleştirme**

- Her LED pikselini ayrı düzenleme
- Gösterge bazında bağımsız renk ve test seçenekleri
- Yanıp sönme ayarları
- Sabit LED önizlemesi
- Yalnızca LED ayarlarını sıfırlama

**Donanım notu:** Standart MAX7219 tek renkli matrislerde RGB renk değişimi mümkün değildir. Renk seçenekleri yazılım önizlemesinde gösterilir. Fiziksel çok renkli görüntü için farklı RGB donanımı ve uygun firmware gerekir.

Oyun içi bayrak ve yakınlık olaylarının otomatik algılanması, oyun bazında telemetri desteğine bağlıdır.

### 4. Live Telemetry

PitApex, oyunların sunduğu telemetri verilerini okuyarak aşağıdaki bilgileri görüntülemeyi hedefler:

- Anlık hız ve vites
- Motor devri
- Gaz ve fren yüzdesi
- Tur ve sektör süreleri
- Yakıt bilgileri
- Lastik sıcaklıkları ve basınçları
- Desteklenen araç durum bilgileri

Bir oyun belirli bir telemetri alanını sunmuyorsa PitApex o bilgiyi tahmin ederek üretmez.

### 5. In-Game Overlays

Oyun üzerinde kullanılabilen bağımsız bilgi pencereleri:

- Pedal telemetrisi
- Hız ve devir bilgileri
- Vites göstergesi
- Tur zamanları
- Desteklenen hava ve lastik verileri

Overlay pencereleri taşınabilir ve konumları kaydedilebilir.

**Not:** Exclusive fullscreen modunda overlay görünürlüğü garanti edilmez. Borderless Windowed modu önerilir.

### 6. Lap Records & Session Management

Tur ve oturum yönetimi özellikleri:

- Anlık ve tamamlanan tur süreleri
- Kişisel pist rekorları
- Araç ve pist bazında kayıt
- Oturum geçmişi
- Önceki tur kayıtlarını koruma
- Geçersiz tur filtreleme
- Kalıcı veri depolama

Oyun telemetrisi kesildiğinde son oturum bilgileri korunacak şekilde tasarlanmıştır.

### 7. Customizable Interface

- Koyu ve açık tema
- Türkçe ve İngilizce arayüz
- Kaydırılabilir ayar sayfaları
- Bağımsız donanım kontrol sekmeleri
- LED piksel editörü
- Kayıtlı ayarlar ve profiller
- PitApex özel uygulama logosu

---

# 💻 Installation / Kurulum

## 1. Sistem Gereksinimleri

**İşletim sistemi:** Windows 10 veya Windows 11  
**Python:** Python 3 (kaynak koddan çalıştırmak için)  
**Bağlantı:** USB üzerinden Arduino (donanım özellikleri için)

Python paketleri:

- pyserial
- Pillow
- PyInstaller (yalnızca EXE oluşturmak için)

### 2. Dosyaları İndirin

GitHub deposundan en güncel sürümü ZIP olarak indirin veya depoyu bilgisayarınıza klonlayın.

ZIP dosyasını çıkardıktan sonra `PitApex` klasörünü açın.

### 3. Gerekli Paketleri Kurun

Önce Python 3'ün bilgisayarınızda kurulu olduğundan emin olun.

Ardından proje klasöründe terminal açarak:

```bash
py -m pip install -r requirements.txt
```

komutunu çalıştırın.

Alternatif olarak `1_kurulum.bat` dosyasını çalıştırabilirsiniz. Ancak bu dosya mevcut sürümde yalnızca `pyserial` kurar. Pillow için yukarıdaki komut önerilir.

### 4. Uygulamayı Başlatın

`2_baslat.bat` dosyasına çift tıklayın.

Alternatif:

```bash
py main.py
```

Uygulama açıldığında istediğiniz oyun, donanım ve telemetri ayarlarını yapılandırabilirsiniz.

---

# 🔌 Arduino Setup

## Pedal ve Fan Sistemi

1. Arduino IDE'yi kurun.
2. `firmware/PedalHaptic/PedalHaptic.ino` dosyasını açın.
3. Arduino kartınızı ve COM portunu seçin.
4. Firmware'i karta yükleyin.
5. Arduino'yu USB üzerinden bilgisayara bağlayın.
6. PitApex içerisinden uygun seri portu seçin.
7. Dosyalar içinde arduino kodu bulunmaktadır elle kurulum gerekebilir
8. <img width="1066" height="68" alt="Ekran görüntüsü 2026-11-20 125422" src="https://github.com/user-attachments/assets/b215ea11-7393-402c-bcdc-394e03e5b69c" />


Motorların ve fanların bağlantısını kullandığınız motor sürücü kartının elektriksel sınırlarına uygun yapın.

**Uyarı:** L293D motor sürücüsüne yüksek akım çeken fanları veya motorları doğrudan bağlamayın 12v öalısan FAN ve Motorlar önerilir. Uygun harici sürücü kullanın.

## LED Matrix Kurulumu

LED matrisi için ayrı bir Arduino kullanılır.

Gerekli bileşenler:

- Arduino uyumlu kontrol kartı
- 8×8 LED matris
- USB bağlantı kablosu
- Bağlantı kabloları


Arduino IDE üzerinden **LedControl** kütüphanesini kurun.

Ardından:

`firmware/LedMatrix/LedMatrix.ino`

dosyasını Arduino'ya yükleyin.

PitApex içerisindeki LED sekmesinden COM portunu seçerek bağlantıyı kurun.

Bağlantı pinleri kullanılan karta göre değiştirilebilir. Arduino firmware'indeki pin tanımlarını kontrol edin.

---
<img width="2559" height="1392" alt="Ekran görüntüsü 2026-11-20 125325" src="https://github.com/user-attachments/assets/cecf6159-6f92-4e79-b820-d6b2cbe8d5fa" />


#  EXE Oluşturma

Python kurulu bir Windows bilgisayarda:

`3_exe_olustur.bat`

dosyasını çalıştırın.

Bu işlem PyInstaller kullanarak tek dosyalı bir uygulama oluşturur.

Başarılı olduğunda proje klasöründe:

`PitApex.exe`

dosyası bulunur.

EXE oluşturma işlemi Python kaynak kodundan yapılır. Arduino firmware'inin ayrıca yüklenmesi gerekir.

---

# 📁 Data Storage

PitApex kullanıcı verilerini varsayılan olarak Windows Belgeler klasöründe saklar:

```text
Documents/
└── PitApex/
    ├── records/
    ├── sessions/
    ├── settings/
    ├── profiles/
    └── backups/
```

Kayıt sistemi; tur rekorlarını, oturum geçmişini, ayarları ve profilleri uygulama dosyalarından ayrı tutar.

Yeni sürüm yüklemeden önce kullanıcı verilerinizin yedeğini almanız önerilir.

---

# 🧪 Testing & Compatibility

Proje içerisinde otomatik testler bulunur.

Testleri çalıştırmak için:

```bash
py -m unittest discover -s tests -t .
```

Bu testler; telemetri işleme, kayıt sistemi, LED desenleri, pedal efektleri ve çeşitli yazılım bileşenlerini kontrol etmek için kullanılır.

**Önemli:** Otomatik testlerin başarılı olması gerçek Arduino, motor, fan, LED matrisi veya desteklenen oyunların tamamında sorunsuz çalışmayı garanti etmez.

Özellikle ACC, AC, LMU ve iRacing telemetri bağlantıları ile yeni LED uyarılarının oyun içi davranışları gerçek kullanımda ayrıca doğrulanmalıdır.

---


#  Language Support

PitApex supports Turkish and English.

The interface language can be changed from the application settings.

Some translations or newly introduced interface elements may still require additional verification.

---

#  Development Roadmap

Gelecek geliştirmeler için hedefler:

- Oyunlar arası telemetri uyumluluğunu artırmak
- Otomatik yarış bayrağı algılamasını tamamlamak
- Yan ve arka araç uyarılarını gerçek spotter verilerine bağlamak
- LED gösterge önceliklerini geliştirmek
- Daha kapsamlı overlay özelleştirmesi
- Donanım bağlantı güvenilirliğini artırmak
- Arayüz performansını ve çoklu dil desteğini iyileştirmek
- Gerçek donanım test kapsamını genişletmek

---

# 🤝 Open Source

PitApex, sim racing topluluğunun kullanımına ve geliştirme katkılarına açık bir proje olarak hazırlanmıştır.

Hata bildirimleri, iyileştirme önerileri ve katkılar GitHub Issues ve Pull Requests üzerinden paylaşılabilir.

---

**PitApex — Control Your Hardware. Understand Your Race.**

Bilinen hatalar
 Tur rekor sistemi geliştirme aşamasında olup düzgün çalışmama veya hiç çalışmama
 
 araç parça bilgi overlay penceresi oyunun sunduğu telemtri eksikliğinden çalışmamaktadır
 
 Ac ve Acc de test edilebilmiştir sadece 
 
 Led kısmında da geliştirmeler devam etmektedir

 Araç hasar durumu göstergesi üzerine tıklandığında gri ekran kalması sorunu var kapat aç yapınca düzelmekte 
 ilerleyen güncellemelerde düzeltilecektir
 
Uygulamanın il sürümü https://github.com/ziya44-a/pedal-ffb-motor-yaz-l-m- buradaki gibidir
 ve sadece pedal ffb kitinde ABS TC Tekerlek kayması ve kilitlenmesi vardır

PitApex — Beyond Telemetry. Feel the Race.

Turn racing data into real feedback.


<img width="2559" height="1389" alt="Ekran görüntüsü 2026-11-20 125253" src="https://github.com/user-attachments/assets/58d4d0ed-1be3-404a-a7e4-f1d5c35fceab" />
<img width="1090" height="926" alt="Ekran görüntüsü 2026-11-20 125235" src="https://github.com/user-attachments/assets/cb888d0f-aa88-4a96-ae39-f089d64a5761" />
<img width="2559" height="1392" alt="Ekran görüntüsü 2026-11-20 125325" src="https://github.com/user-attachments/assets/bb13d1fb-f603-4b3a-887a-591b2223e9ae" />
<img width="2559" height="1382" alt="Ekran görüntüsü 2026-11-20 125341" src="https://github.com/user-attachments/assets/c284b016-4960-4065-86ed-e21128b49cca" />
<img width="2559" height="1385" alt="Ekran görüntüsü 2026-11-20 125347" src="https://github.com/user-attachments/assets/bcd35b46-12d7-43c0-87c5-fe9966d8eb32" />
<img width="2559" height="1392" alt="Ekran görüntüsü 2026-11-20 125401" src="https://github.com/user-attachments/assets/ee9fe451-71bb-4af3-af50-2147bbce394c" />
<img width="2559" height="1393" alt="Ekran görüntüsü 2026-11-20 125336" src="https://github.com/user-attachments/assets/13216824-d57d-4632-b55c-5f1e4932c0e3" />
<img width="1997" height="426" alt="Ekran görüntüsü 2026-11-20 130823" src="https://github.com/user-attachments/assets/442c5c02-499e-418e-a7bd-135a9e26a9dd" />
