# Build script for AndroidMirror to EXE
# Uses PyInstaller to bundle the app into a single file with custom branding

$CTK_PATH = "C:\Users\ZENBOOK\AppData\Roaming\Python\Python313\site-packages\customtkinter"

Write-Host "Building AndroidMirror.exe with Professional Branding..." -ForegroundColor Cyan

pyinstaller --noconfirm --onefile --windowed `
    --add-data "$($CTK_PATH);customtkinter/" `
    --add-data "icon.ico;." `
    --icon "icon.ico" `
    --name "AndroidMirror" `
    main.py

Write-Host "Build Complete! Check the 'dist' folder." -ForegroundColor Green
