param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$nodeCommand=Get-Command node.exe -ErrorAction SilentlyContinue
$nodePath=if($nodeCommand){$nodeCommand.Source}else{throw 'Node.js is required; install it and retry.'}
if(!(Test-Path -LiteralPath $nodePath)){throw '未找到Node.js，请安装Node.js后重试。'}
if(!(Test-Path -LiteralPath (Join-Path $projectRoot 'node_modules\remotion'))){throw '依赖尚未安装，请先在工程目录运行 npm install。'}
$available=$false
try{$reply=Invoke-RestMethod 'http://127.0.0.1:3210/api/templates' -TimeoutSec 1;$available=($reply.Count -gt 0)}catch{}
if(!$available){
  $dataFolder=Join-Path $projectRoot 'data'
  New-Item -ItemType Directory -Force -Path $dataFolder | Out-Null
  $serverScript=Join-Path $projectRoot 'scripts\server.mjs'
  Start-Process -FilePath $nodePath -ArgumentList @('"'+$serverScript+'"') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataFolder 'server.stdout.log') -RedirectStandardError (Join-Path $dataFolder 'server.stderr.log') | Out-Null
}
if(!$NoBrowser){Start-Process 'http://127.0.0.1:3210'}
Write-Output '剪辑工作台：http://127.0.0.1:3210'
Write-Output '工程预览：http://127.0.0.1:3211/BattleEdit'
