param([string]$Port = 'COM6')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..\firmware')
try {
    # Use native >>> (Ctrl+D from robot>) before uploading. Updating files
    # inside aiorepl's raw compatibility mode does not reload imported code.
    python -m mpremote connect $Port mip install aiorepl
    if ($LASTEXITCODE -ne 0) { throw 'aiorepl installation failed' }
    $makeMessages = @'
import os
try:
    os.mkdir('messages')
except OSError as error:
    if error.args[0] != 17:
        raise
'@
    python -m mpremote connect $Port exec $makeMessages
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create messages directory' }
    foreach ($definition in Get-ChildItem -LiteralPath messages -Filter '*.py' -File) {
        python -m mpremote connect $Port fs cp $definition.FullName ":messages/$($definition.Name)"
        if ($LASTEXITCODE -ne 0) { throw "Upload failed: $($definition.Name)" }
    }
    foreach ($file in @('message_bus.py', 'virtual_imu.py', 'example_task.py', 'robot.py', 'main.py')) {
        python -m mpremote connect $Port fs cp $file ":$file"
        if ($LASTEXITCODE -ne 0) { throw "Upload failed: $file" }
    }
    python -m mpremote connect $Port reset
    if ($LASTEXITCODE -ne 0) { throw 'Reset failed' }
} finally {
    Pop-Location
}
