$projectRoot=$PSScriptRoot
$stateFile=Join-Path $projectRoot 'data\processes.local.json'
if(Test-Path -LiteralPath $stateFile){
  $state=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
  foreach($processNumber in @($state.render,$state.studio,$state.server)){
    if(!$processNumber){continue}
    $item=Get-CimInstance Win32_Process -Filter "ProcessId=$processNumber" -ErrorAction SilentlyContinue
    if($item -and $item.CommandLine -and $item.CommandLine.Contains($projectRoot)){Stop-Process -Id $processNumber -ErrorAction SilentlyContinue}
  }
}
Write-Output '本工程后台服务已关闭。'
