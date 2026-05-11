param(
    [string]$InputPath,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $InputPath) {
    $InputPath = Join-Path $projectRoot "solutions\all_solutions.md"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $projectRoot "solutions\all_solutions.pdf"
}

$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $pandoc) {
    $pandoc = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter pandoc.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pandoc) {
    throw "Pandoc not found. Please install pandoc and ensure it is on PATH."
}

$xelatex = Get-Command xelatex -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $xelatex) {
    throw "xelatex not found. Please install TeX Live or MiKTeX and ensure it is on PATH."
}

if (-not (Test-Path $InputPath)) {
    throw "Input file not found: $InputPath"
}

$inputFullPath = (Resolve-Path $InputPath).Path
$outputDir = Split-Path -Parent $OutputPath
if ([string]::IsNullOrWhiteSpace($outputDir)) {
    $outputDir = "."
}
if (-not (Test-Path $outputDir)) {
    throw "Output directory not found: $outputDir"
}

& $pandoc $inputFullPath `
    -o $OutputPath `
    --from markdown+tex_math_dollars+raw_tex `
    --pdf-engine=xelatex `
    -V documentclass=ctexart `
    -V geometry:margin=2.2cm

if (-not $?) {
    throw "Pandoc conversion failed."
}

Get-Item $OutputPath | Select-Object FullName, Length, LastWriteTime
