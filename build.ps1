$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv/Scripts/python.exe")) {
    throw ".venv not found. Please create venv and install dependencies first."
}

& .venv/Scripts/python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name TodoList `
    main.py

Write-Host "Build complete: dist/TodoList.exe"
