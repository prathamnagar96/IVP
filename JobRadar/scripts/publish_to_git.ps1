param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,

    [string]$Branch = "main",

    [string]$Message = "Initial JobRadar API commit"
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path -LiteralPath ".git")) {
    git init
}

git branch -M $Branch

try {
    git remote get-url origin | Out-Null
    git remote set-url origin $RemoteUrl
}
catch {
    git remote add origin $RemoteUrl
}

git add .
git commit -m $Message
git push -u origin $Branch
