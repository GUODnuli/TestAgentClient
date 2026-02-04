# Set PowerShell to UTF-8 encoding
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "PowerShell encoding set to UTF-8" -ForegroundColor Green

# Start the development server
npm run dev
