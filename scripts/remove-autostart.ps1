$ErrorActionPreference = "Stop"
$TaskName = "NixLMs User Runtime"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Inicialização automática removida."
} else {
    Write-Host "Nenhuma tarefa de inicialização da NixLMs foi encontrada."
}
