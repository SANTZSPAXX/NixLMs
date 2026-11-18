[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Install,
    [switch]$InstallTorchCpu,
    [switch]$InstallTorch,
    [switch]$SkipCorePackages
)
$ErrorActionPreference = "Stop"
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "Python não encontrado. Ative o ambiente virtual e tente novamente." }
$InstallModes = @($Install, $InstallTorchCpu, $InstallTorch) | Where-Object { $_ }
if ($InstallModes.Count -gt 1 -or ($Plan -and $InstallModes.Count -gt 0)) {
    throw "Escolha somente um modo: -Plan, -Install, -InstallTorchCpu ou -InstallTorch."
}
if ($SkipCorePackages -and -not $InstallTorch) {
    throw "-SkipCorePackages só pode ser usado com -InstallTorch."
}
function Invoke-NixFrameworkInstaller {
    param([string[]]$Arguments)
    & python -m nixlms_core.framework_install @Arguments
    return $LASTEXITCODE
}
if ($InstallTorch) {
    # Compatibilidade legada: duas etapas e duas confirmações independentes.
    $Code = Invoke-NixFrameworkInstaller @("--install-torch-cpu")
    if ($Code -ne 0) { exit $Code }
    if (-not $SkipCorePackages) {
        $Code = Invoke-NixFrameworkInstaller @("--install")
        if ($Code -ne 0) { exit $Code }
    }
    exit 0
}
if ($InstallTorchCpu) {
    $Code = Invoke-NixFrameworkInstaller @("--install-torch-cpu")
    exit $Code
}
if ($Install) {
    $Code = Invoke-NixFrameworkInstaller @("--install")
    exit $Code
}
$Code = Invoke-NixFrameworkInstaller @("--plan")
exit $Code
