param([ValidateSet('setup','start','run','dashboard','stop','status')][string]$Action = 'dashboard')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$linuxRoot = '/home/manee/delhi-air-lab'
$windowsRoot = $PSScriptRoot.Replace('\','/')
$linuxSource = '/mnt/' + $windowsRoot.Substring(0,1).ToLower() + $windowsRoot.Substring(2)
if ($Action -eq 'dashboard') {
    python -m streamlit run app.py --server.address 127.0.0.1
    exit $LASTEXITCODE
}
if ($Action -in @('setup','start','run','status')) {
    # WSL system services alone do not keep a distribution alive between commands.
    New-Item -ItemType Directory -Force -Path 'tmp' | Out-Null
    $keeperId = if (Test-Path 'tmp/wsl-keeper.pid') { Get-Content 'tmp/wsl-keeper.pid' } else { 0 }
    $keeper = Get-Process -Id $keeperId -ErrorAction SilentlyContinue
    if (-not $keeper -or $keeper.ProcessName -ne 'wsl') {
        $keeper = Start-Process -FilePath 'wsl.exe' -ArgumentList '-d','Ubuntu','--','sleep','28800' -WindowStyle Hidden -PassThru
        $keeper.Id | Set-Content 'tmp/wsl-keeper.pid'
    }
    $dockerReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        wsl -d Ubuntu -u root -- bash -lc '/snap/bin/docker info >/dev/null 2>&1'
        if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $dockerReady) { throw 'Docker Engine inside Ubuntu did not become ready.' }
}
if ($Action -in @('setup','start','run')) {
    # Keep the authoritative source in Windows; snap Docker uses a Linux-home copy.
    $sync = "mkdir -p '$linuxRoot'; cp -r '$linuxSource/cluster' '$linuxSource/scripts' '$linuxSource/jobs' '$linuxSource/data' '$linuxSource/compose.yaml' '$linuxRoot/'"
    wsl -d Ubuntu -u root -- bash -lc $sync
    if ($LASTEXITCODE -ne 0) { throw 'Source sync failed' }
}
switch ($Action) {
    'setup' { wsl -d Ubuntu -u root -- bash -lc "bash '$linuxRoot/scripts/setup_cluster.sh' 2>&1" }
    'start' { wsl -d Ubuntu -u root -- bash -lc "bash '$linuxRoot/scripts/start_cluster.sh' 2>&1" }
    'stop' { wsl -d Ubuntu -u root -- bash -lc "cd '$linuxRoot' && /snap/bin/docker compose stop 2>&1" }
    'status' { wsl -d Ubuntu -u root -- bash -lc "cd '$linuxRoot' && /snap/bin/docker compose ps && /snap/bin/docker compose exec -T master yarn node -list 2>&1" }
    'run' {
        wsl -d Ubuntu -u root -- bash -lc "bash '$linuxRoot/scripts/run_pipeline.sh' 2>&1"
        $pipelineExit = $LASTEXITCODE
        wsl -d Ubuntu -u root -- bash -lc "cp -r '$linuxRoot/results' '$linuxSource/'"
        $copyExit = $LASTEXITCODE
        if ($pipelineExit -ne 0) {
            if ($copyExit -ne 0) { throw "Pipeline failed and logs could not be copied. Ubuntu log: $linuxRoot/results/spark-run.log" }
            throw "Pipeline failed. Open the log: $PSScriptRoot\results\spark-run.log"
        }
        if ($copyExit -ne 0) { throw 'Spark completed, but copying results to Windows failed.' }
    }
}
if ($LASTEXITCODE -ne 0) { throw "Project action failed: $Action" }
