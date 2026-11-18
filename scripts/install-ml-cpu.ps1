[CmdletBinding()]
param(
    [switch]$InstallTorch,
    [switch]$SkipCorePackages
)

$ErrorActionPreference = "Stop"
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python não encontrado no PATH. Instale Python 3.11+ e tente novamente."
}

$Version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$Parts = $Version.Split('.')
if ([int]$Parts[0] -lt 3 -or ([int]$Parts[0] -eq 3 -and [int]$Parts[1] -lt 11)) {
    throw "O stack opcional atual recomenda Python 3.11+. Python detectado: $Version"
}

Write-Host "NixLMs — instalação opcional de frameworks CPU"
Write-Host "Ambiente atual: $(& python -c 'import sys; print(sys.executable)')"
Write-Warning "Use um ambiente virtual. PyTorch e modelos podem ocupar bastante disco/RAM."
Write-Host "Este script instala pacotes, mas NÃO baixa modelos nem datasets."

& python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip." }

if ($InstallTorch) {
    Write-Host "Instalando PyTorch CPU pelo índice oficial..."
    & python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw "Falha na instalação de PyTorch CPU." }
} else {
    Write-Host "PyTorch não será instalado. Use -InstallTorch para autorizar essa etapa."
}

if (-not $SkipCorePackages) {
    & python -m pip install -r (Join-Path $PSScriptRoot "..\requirements-ml-cpu.txt")
    if ($LASTEXITCODE -ne 0) { throw "Falha na instalação dos pacotes opcionais CPU." }
}

Write-Host "Verificando inventário..."
& python -m nixlms_core.framework_registry --all
if ($LASTEXITCODE -ne 0) { throw "Falha ao executar inventário." }
Write-Host "Concluído. Nenhum modelo foi baixado."
