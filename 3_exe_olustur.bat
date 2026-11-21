@echo off
cd /d "%~dp0"
echo Tek tikla acilan PitApex.exe olusturuluyor (birkac dakika surebilir)...
py -m pip install pyserial pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --name PitApex --icon assets\pitapex.ico --add-data "assets;assets" main.py
if exist dist\PitApex.exe (
  copy /y dist\PitApex.exe PitApex.exe >nul
  echo.
  echo Hazir: PitApex.exe bu klasorde. Artik Python gerekmez.
) else (
  echo.
  echo Olusturulamadi. Yukaridaki hata mesajini kontrol et.
)
pause
