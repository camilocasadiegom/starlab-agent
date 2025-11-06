Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Ensure-Dir([string]$p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Path $p | Out-Null } }
function Test-Port([string]$ip,[int]$port){
  try{ $c = New-Object System.Net.Sockets.TcpClient; $c.SendTimeout=500; $c.ReceiveTimeout=500
       $a = $c.BeginConnect($ip,$port,$null,$null)
       if(-not $a.AsyncWaitHandle.WaitOne(500,$false)){ $c.Close(); return $false }
       $c.EndConnect($a)|Out-Null; $c.Close(); return $true } catch { return $false }
}
function Wait-ForPort([string]$ip,[int]$port,[int]$ms=30000){
  $deadline = (Get-Date).AddMilliseconds($ms)
  while((Get-Date) -lt $deadline){ if(Test-Port $ip $port){ return $true }; Start-Sleep -Milliseconds 500 }
  return $false
}

$ProjectRoot = "C:\Users\Camilo C\Documents\starlab-agent"
$Host = '127.0.0.1'
$Port = 8000
$LocalUrl = "http://$Host:$Port"
$Logs = Join-Path $ProjectRoot 'logs'
Ensure-Dir $Logs

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$uvOut = Join-Path $Logs "uvicorn_$ts.out.log"
$uvErr = Join-Path $Logs "uvicorn_$ts.err.log"

Set-Location $ProjectRoot

if(-not (Test-Port $Host $Port)){
  Write-Host "[INFO] Iniciando backend $LocalUrl..." -ForegroundColor Cyan
  Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList @('-m','uvicorn','main:app','--host',$Host,'--port',"$Port",'--reload') `
    -RedirectStandardOutput $uvOut -RedirectStandardError $uvErr `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
}

if(Wait-ForPort $Host $Port 30000){
  Write-Host "[OK] Backend activo: $LocalUrl" -ForegroundColor Green
  try{ Start-Process $LocalUrl | Out-Null }catch{}
  $cfOut = Join-Path $Logs "cloudflared_$ts.out.log"
  $cfErr = Join-Path $Logs "cloudflared_$ts.err.log"
  $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue) ?? (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)
  if($cf){
    $p = Start-Process -FilePath $cf.Source -ArgumentList @('tunnel','--no-autoupdate','--url',$LocalUrl) `
      -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr -WindowStyle Hidden -PassThru
    if($p){ Write-Host "[INFO] TÃºnel Cloudflare iniciado (PID $($p.Id))." -ForegroundColor Gray }
  }else{
    Write-Host "[INFO] cloudflared no instalado." -ForegroundColor Yellow
  }
}else{
  Write-Host "[ERR] El backend no respondiÃ³ en $LocalUrl. Revisa logs:" -ForegroundColor Red
  Write-Host "     $uvOut" -ForegroundColor DarkGray
  Write-Host "     $uvErr" -ForegroundColor DarkGray
  exit 1
}
