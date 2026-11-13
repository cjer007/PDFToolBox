# 一键打包两个版本
$py = "python"
if (Test-Path "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-next-primary-runtime\dependencies\python\python.exe") {
  $py = "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-next-primary-runtime\dependencies\python\python.exe"
}
Set-Location $PSScriptRoot

Write-Host "打包完整版…"
& $py -m PyInstaller --noconfirm --onedir --console --name PDFToolBox `
  --version-file version_info.txt --manifest app.manifest `
  --exclude-module onnxruntime --exclude-module pandas --exclude-module matplotlib `
  --exclude-module scipy --exclude-module IPython --exclude-module pytest `
  --exclude-module torch --exclude-module tensorflow --exclude-module PyQt5 main.py

Write-Host "打包精简版…"
& $py -m PyInstaller --noconfirm --onedir --console --name PDFToolBoxLite `
  --version-file version_info.txt --manifest app.manifest `
  --exclude-module pdf2docx --exclude-module cv2 --exclude-module numpy `
  --exclude-module onnxruntime --exclude-module pandas --exclude-module matplotlib `
  --exclude-module scipy --exclude-module IPython --exclude-module pytest `
  --exclude-module torch --exclude-module tensorflow --exclude-module PyQt5 main.py

Write-Host "完成，产物在 dist\"
