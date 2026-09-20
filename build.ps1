[CmdletBinding()]
param(
    [string]$PythonExecutable
)

$ErrorActionPreference = "Stop"

if (-not $PythonExecutable) {
    $venvPython = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
    $PythonExecutable = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
}

# Resolve the interpreter before changing directories, including a caller-supplied path.
$pythonCommand = Get-Command $PythonExecutable -CommandType Application -ErrorAction Stop |
    Select-Object -First 1
$resolvedPython = $pythonCommand.Source
$outputPath = Join-Path $PSScriptRoot "dist/TodoList.exe"

Push-Location $PSScriptRoot
try {
    & $resolvedPython -m PyInstaller --noconfirm --clean TodoList.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed (exit code $LASTEXITCODE). Install requirements.txt with the selected Python interpreter."
    }
    if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        throw "PyInstaller did not produce the expected executable: $outputPath"
    }
    Write-Host "Build complete: $outputPath"
}
finally {
    Pop-Location
}
