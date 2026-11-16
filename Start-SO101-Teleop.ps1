param(
    [string]$Port = 'COM7',
    [string]$RobotId = 'new-so101',
    [int]$Fps = 20,
    [int]$StartupTimeoutSeconds = 150,
    [switch]$Detached
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$python = Join-Path $repo '../lelab-main/.venv/Scripts/python.exe'
$tunnel = Join-Path $repo 'deploy/native/workshop/so101_live_tunnel.py'
$leader = Join-Path $repo 'deploy/native/workshop/so101_leader_client.py'
$calibration = Join-Path $repo ('../lelab-main/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/' + $RobotId + '.json')
$url = 'http://127.0.0.1:8765/status'
$tunnelProcess = $null

if (-not (Test-Path -LiteralPath $python)) { throw "LeLab Python missing: $python" }
if (-not (Test-Path -LiteralPath $calibration)) { throw "Leader calibration missing: $calibration" }
if (-not (Test-Path -LiteralPath (Join-Path $repo 'autodl-4090.md'))) {
    throw 'Local AutoDL connection note is missing.'
}
if ($StartupTimeoutSeconds -lt 10) { throw 'StartupTimeoutSeconds must be at least 10.' }
if ($Fps -lt 1 -or $Fps -gt 60) { throw 'Fps must be between 1 and 60.' }

$env:PYTHONIOENCODING = 'utf-8'
$logDir = Join-Path $env:TEMP 'so101-teleop'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$outLog = Join-Path $logDir 'tunnel.stdout.log'
$errLog = Join-Path $logDir 'tunnel.stderr.log'

if ($Detached) {
    $sessionOut = Join-Path $logDir 'session.stdout.log'
    $sessionErr = Join-Path $logDir 'session.stderr.log'
    $launcher = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-Port', $Port, '-RobotId', $RobotId, '-Fps', [string]$Fps, '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds) -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $sessionOut -RedirectStandardError $sessionErr -PassThru
    Write-Host ("Teleoperation session process: " + $launcher.Id)
    Write-Host ("Session logs: " + $sessionOut + " and " + $sessionErr)
    return
}

try {
    $existing = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if ($existing) {
        $ownerPid = $existing | Select-Object -First 1 -ExpandProperty OwningProcess
        $ownerProcess = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        $ownerWmi = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
        Write-Host ('Existing local 8765 listener PID: ' + $ownerPid + ', executable: ' + $ownerProcess.Path)
        if ($ownerWmi -and $ownerWmi.CommandLine) {
            if ($ownerWmi.CommandLine -match 'so101_live_tunnel.py|so101_leader_client.py') {
                Write-Host ('Known workshop listener: ' + $Matches[0])
            }
            else { Write-Host 'Listener is not a known workshop script.' }
        }
        try { $status = Invoke-RestMethod -Uri $url -TimeoutSec 3 }
        catch { throw ('Local port 8765 is occupied but /status failed: ' + $_.Exception.Message) }
        if ($null -eq $status.leader_online) { throw 'Local port 8765 belongs to a different service.' }
        Write-Host 'Using the existing localhost teleoperation tunnel.'
    }
    else {
        Write-Host 'Starting the 4090 simulator and localhost SSH tunnel...'
        $tunnelProcess = Start-Process -FilePath $python -ArgumentList @($tunnel, '--start-teleop', '--no-browser') -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt $StartupTimeoutSeconds; $attempt++) {
        if ($tunnelProcess -and $tunnelProcess.HasExited) {
            $detail = Get-Content -LiteralPath $errLog -Tail 8 -ErrorAction SilentlyContinue
            throw "SSH tunnel exited. See $errLog. $detail"
        }
        try {
            $status = Invoke-RestMethod -Uri $url -TimeoutSec 3
            if ($status.ready -and $null -ne $status.frame_age_seconds -and $status.frame_age_seconds -lt 10) {
                $ready = $true
                break
            }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Simulator did not become ready. Check $outLog and $errLog." }

    Write-Host ('Camera frame ' + $status.frame_seq + '; dataset: ' + $status.dataset_root)
    try { Start-Process 'http://127.0.0.1:8765/' }
    catch { Write-Warning 'Could not open a browser automatically; open http://127.0.0.1:8765/ manually.' }
    Write-Host 'Reading the physical leader. Move one joint slowly and check the camera page.'
    Write-Host 'After the page says leader online / recording ready, click Start recording.'
    Write-Host 'Press Ctrl+C here to stop the leader and this tunnel.'
    & $python $leader --lelab-cache --port $Port --robot-id $RobotId --fps $Fps
    if ($LASTEXITCODE -ne 0) { throw "Leader client exited with code $LASTEXITCODE" }
}
finally {
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -ErrorAction SilentlyContinue
    }
}
