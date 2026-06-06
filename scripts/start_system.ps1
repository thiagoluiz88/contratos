$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runDir = Join-Path $projectRoot ".codex-run"

if (-not (Test-Path $python)) {
    throw "Ambiente virtual nao encontrado em .venv. Execute: python -m venv .venv"
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Get-ChildItem $runDir -Filter "uvicorn*.log" -ErrorAction SilentlyContinue | ForEach-Object {
    Clear-Content -LiteralPath $_.FullName -ErrorAction SilentlyContinue
}

$port = 8000
while ($port -lt 8100) {
    $inUse = netstat -ano | Select-String ":$port\s"
    if (-not $inUse) {
        break
    }
    $port++
}

if ($port -ge 8100) {
    throw "Nenhuma porta livre encontrada entre 8000 e 8099."
}

$stdout = Join-Path $runDir "uvicorn-$port.out.log"
$stderr = Join-Path $runDir "uvicorn-$port.err.log"

$process = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port" `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$healthUrl = "http://127.0.0.1:$port/health"
$loginUrl = "http://127.0.0.1:$port/login"
$deadline = (Get-Date).AddSeconds(20)
$successfulChecks = 0

do {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $successfulChecks++
            if ($successfulChecks -ge 2) {
                Write-Output "Sistema iniciado."
                Write-Output "PID: $($process.Id)"
                Write-Output "Login: $loginUrl"
                exit 0
            }
        }
    } catch {
        $successfulChecks = 0
        if ($process.HasExited) {
            break
        }
    }
} while ((Get-Date) -lt $deadline)

Write-Output "Falha ao confirmar inicializacao."
Write-Output "PID: $($process.Id)"
Write-Output "Erro recente:"
Get-Content $stderr -Tail 30 -ErrorAction SilentlyContinue
exit 1
