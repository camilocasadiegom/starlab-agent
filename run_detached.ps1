$ErrorActionPreference = 'Continue'
$Project = 'C:\Users\Camilo C\Documents\starlab-agent'
$Venv    = 'C:\Users\Camilo C\Documents\starlab-agent\.venv'
$PyExe   = 'C:\Users\Camilo C\Documents\starlab-agent\.venv\Scripts\python.exe'
$PubFile = 'C:\Users\Camilo C\Documents\starlab-agent\public_url.txt'
$Port    = 8000
$Local   = 'http://127.0.0.1:8000/'

# 1) Activar venv si existe (sino, usar python del PATH)
if (Test-Path ($Venv + '\Scripts\Activate.ps1')) { & ($Venv + '\Scripts\Activate.ps1') }

# 2) Si el puerto 8000 no está escuchando, lanzamos Uvicorn
$tcp = Test-NetConnection 127.0.0.1 -Port $Port
if (-not $tcp.TcpTestSucceeded) {
  # Argumentos uvicorn con --app-dir y WD correcto
  $uvArgs = @('-m','uvicorn','main:app','--host','0.0.0.0','--port',"$Port",'--reload','--app-dir',"$Project")
  if (Test-Path $PyExe) {
    Start-Process -FilePath $PyExe -ArgumentList $uvArgs -WorkingDirectory $Project -WindowStyle Hidden | Out-Null
  } else {
    Start-Process -FilePath 'python' -ArgumentList $uvArgs -WorkingDirectory $Project -WindowStyle Hidden | Out-Null
  }
  Start-Sleep -Seconds 2
}

# 3) Esperar hasta 90s a que el puerto responda
$ok = $false
for ($i=0; $i -lt 90; $i++) {
  $t = Test-NetConnection 127.0.0.1 -Port $Port
  if ($t.TcpTestSucceeded) { $ok = $true; break }
  Start-Sleep -Milliseconds 800
}

# 4) Lanzar cloudflared y capturar la URL pública (abrir solo la pública)
if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
  Remove-Item $PubFile -Force -ErrorAction SilentlyContinue
  $public = 
  cloudflared tunnel --url "$Local" 2>&1 | ForEach-Object {
    if (-not $public -and $_ -match 'https://[a-z0-9\-]+\.trycloudflare\.com') {
      $public = $Matches[0]
      Set-Content -Encoding UTF8 -Path $PubFile -Value $public
      # Probar /health y abrir cuando esté OK (reintentos cortos por DNS)
      for ($j=0; $j -lt 12; $j++) {
        try {
          $r = Invoke-WebRequest ("$public/health") -UseBasicParsing -TimeoutSec 6
          if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { Start-Process $public; break }
        } catch { Start-Sleep -Milliseconds 800 }
      }
    }
  }
} else {
  Write-Host "[!] cloudflared no está instalado; no se publica URL." -ForegroundColor Yellow
}
