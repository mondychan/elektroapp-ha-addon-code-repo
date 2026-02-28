param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+([\-+][0-9A-Za-z\.\-]+)?$')]
    [string]$Version,

    [string]$NotesFile,

    [string]$Remote = "origin",

    [switch]$NoTag,
    [switch]$NoPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string[]]$Args
    )
    & git -C $Repo @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$addonConfigRel = "ha-addon/elektroapp/config.yaml"
$changelogRel = "ha-addon/elektroapp/CHANGELOG.md"
$addonConfigPath = Join-Path $repoRoot $addonConfigRel
$changelogPath = Join-Path $repoRoot $changelogRel
$notesText = ""
$allowedDirtyPaths = @{}

if (-not (Test-Path $addonConfigPath)) {
    throw "Missing file: $addonConfigPath"
}
if (-not (Test-Path $changelogPath)) {
    throw "Missing file: $changelogPath"
}

$insideRepo = (& git -C $repoRoot rev-parse --is-inside-work-tree 2>$null)
if ($LASTEXITCODE -ne 0 -or $insideRepo.Trim() -ne "true") {
    throw "Directory is not a git repository: $repoRoot"
}

if ($NotesFile) {
    $candidatePath = $NotesFile
    if (-not [System.IO.Path]::IsPathRooted($candidatePath)) {
        $candidatePath = Join-Path $repoRoot $candidatePath
    }
    if (-not (Test-Path $candidatePath)) {
        throw "Notes file not found: $candidatePath"
    }
    $resolvedNotesPath = (Resolve-Path $candidatePath).Path
    if ($resolvedNotesPath.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $notesRelative = [System.IO.Path]::GetRelativePath($repoRoot, $resolvedNotesPath).Replace("\", "/")
        $allowedDirtyPaths[$notesRelative] = $true
    }
    $notesText = [System.IO.File]::ReadAllText($resolvedNotesPath).Trim()
}

$statusOutput = @(& git -C $repoRoot status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read git status."
}

$unexpectedStatus = @()
foreach ($line in $statusOutput) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }
    $pathPart = $line.Substring(3).Trim()
    if ($pathPart.Contains(" -> ")) {
        $pathPart = $pathPart.Split(" -> ")[1].Trim()
    }
    $normalizedPath = $pathPart.Replace("\", "/")
    if ($allowedDirtyPaths.ContainsKey($normalizedPath)) {
        continue
    }
    $unexpectedStatus += $line
}
if ($unexpectedStatus.Count -gt 0) {
    throw "Working tree is not clean. Commit or stash changes before running release. Unexpected changes:`n$($unexpectedStatus -join "`n")"
}

$configRaw = [System.IO.File]::ReadAllText($addonConfigPath)
$versionRegex = [regex]::new('(?m)^version:\s*".*"$')
$addonVersionRegex = [regex]::new('(?m)^\s*ADDON_VERSION:\s*".*"$')

if (-not $versionRegex.IsMatch($configRaw)) {
    throw "Cannot find 'version' field in $addonConfigRel"
}
if (-not $addonVersionRegex.IsMatch($configRaw)) {
    throw "Cannot find 'ADDON_VERSION' field in $addonConfigRel"
}

$configRaw = $versionRegex.Replace($configRaw, "version: `"$Version`"", 1)
$configRaw = $addonVersionRegex.Replace($configRaw, "  ADDON_VERSION: `"$Version`"", 1)
Write-Utf8NoBom -Path $addonConfigPath -Content $configRaw

$changelogRaw = [System.IO.File]::ReadAllText($changelogPath)
$escapedVersion = [regex]::Escape($Version)
if ([regex]::IsMatch($changelogRaw, "(?m)^##\s+$escapedVersion\s*$")) {
    throw "Changelog already contains version $Version."
}

if (-not $notesText) {
    $notesText = "- release notes not provided"
}

$entryText = "## $Version`n$notesText`n`n"
$changelogHeaderRegex = [regex]::new('\A# Changelog[^\r\n]*\r?\n(?:\r?\n)?')
if ($changelogHeaderRegex.IsMatch($changelogRaw)) {
    $newChangelog = $changelogHeaderRegex.Replace($changelogRaw, "# Changelog`n`n$entryText", 1)
}
else {
    $newChangelog = "# Changelog`n`n$entryText$changelogRaw"
}
Write-Utf8NoBom -Path $changelogPath -Content $newChangelog

Invoke-Git -Repo $repoRoot -Args @("add", "--", $addonConfigRel, $changelogRel)
Invoke-Git -Repo $repoRoot -Args @("commit", "-m", "Release $Version")

$tagName = "v$Version"
if (-not $NoTag) {
    $existingTag = (& git -C $repoRoot tag -l $tagName)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to check existing tags."
    }
    if ($existingTag.Trim() -eq $tagName) {
        throw "Tag already exists: $tagName"
    }
    Invoke-Git -Repo $repoRoot -Args @("tag", $tagName)
}

if (-not $NoPush) {
    Invoke-Git -Repo $repoRoot -Args @("push", $Remote)
    if (-not $NoTag) {
        Invoke-Git -Repo $repoRoot -Args @("push", $Remote, $tagName)
    }
}

Write-Host "Release prepared successfully."
Write-Host "Version: $Version"
if ($NoTag) {
    Write-Host "Tag: skipped (--NoTag)"
}
else {
    Write-Host "Tag: $tagName"
}
if ($NoPush) {
    Write-Host "Push: skipped (--NoPush)"
}
else {
    Write-Host "Push: done"
}
