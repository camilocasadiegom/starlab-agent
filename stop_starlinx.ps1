# Detener Cloudflared
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Detener Uvicorn (python ejecutando uvicorn main:app en esta carpeta)
Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -like 'python*' -or $_.Name -like 'python.exe') -and
  ($_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'main:app')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
