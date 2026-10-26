# PowerShell 7; local files only. Never changes Host configuration or credentials.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Verify','Install','Check','Uninstall')][string]$Action,
    [Parameter(Mandatory)][string]$BundleDir,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedManifestSha256,
    [string]$SkillsDir
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Assert-NoLink([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item=Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked paths are refused' }
        }
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
}
function Get-Digest([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Installed([string]$Target,$Manifest) {
    Assert-NoLink $Target
    $actual=@(Get-ChildItem -LiteralPath $Target -Force -Recurse)
    foreach ($item in $actual) { if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installed content' } }
    $files=@($actual | Where-Object { !$_.PSIsContainer })
    if ($files.Count -ne 4) { throw 'Extra or missing installed files; no changes made' }
    foreach ($name in $Manifest.files.Keys) {
        $path=Join-Path $Target $name
        if ((Get-Digest $path) -ne $Manifest.files[$name].sha256 -or (Get-Item -LiteralPath $path).Length -ne $Manifest.files[$name].bytes) { throw 'Installed drift; no changes made' }
    }
    # Empty custom directories are user content too.
    $dirs=@($actual | Where-Object PSIsContainer | ForEach-Object { [IO.Path]::GetRelativePath($Target,$_.FullName).Replace('\','/') } | Sort-Object)
    if (($dirs -join '|') -ne 'references|templates') { throw 'Extra or missing installed directories; no changes made' }
}
$ownedTarget=$null
try {
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 required' }
    $bundle=[IO.Path]::GetFullPath($BundleDir);Assert-NoLink $bundle
    $manifestPath=Join-Path $bundle 'manifest.json'
    if ((Get-Digest $manifestPath) -ne $ExpectedManifestSha256.ToLowerInvariant()) { throw 'Manifest checksum differs' }
    $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
    $expected=@('SKILL.md','references/deliverables.md','references/workflow.md','templates/design-record-template.md')
    if ($manifest.schema -ne 1 -or $manifest.name -ne 'ecommerce-detailpage-creator' -or $manifest.source_commit -cnotmatch '^[0-9a-f]{40}$' -or $manifest.version -cnotmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') { throw 'Unsupported manifest' }
    if ($manifest.files.Count -ne 4 -or @(Compare-Object -CaseSensitive @($manifest.files.Keys) $expected).Count) { throw 'Manifest inventory differs' }
    if ($manifest.zip -cne "$($manifest.name)-$($manifest.version).zip") { throw 'Unexpected ZIP name' }
    $zipPath=Join-Path $bundle $manifest.zip
    if ((Get-Digest $zipPath) -ne $manifest.zip_sha256) { throw 'ZIP checksum differs' }
    $archive=[IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        if ($archive.Entries.Count -ne 4) { throw 'Duplicate, extra or missing ZIP entries' }
        $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($entry in $archive.Entries) {
            $relative=$entry.FullName
            if (!$relative.StartsWith($manifest.name+'/',[StringComparison]::Ordinal)) { throw 'ZIP prefix differs' }
            $name=$relative.Substring($manifest.name.Length+1)
            if ($name -cnotin $expected -or !$seen.Add($name)) { throw 'Unsafe or duplicate ZIP entry' }
            if ($entry.Length -ne $manifest.files[$name].bytes -or $entry.Length -gt 1048576) { throw 'ZIP size differs' }
            $mode=($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($mode -ne 0x8000) { throw 'Non-regular ZIP entry' }
            $stream=$entry.Open()
            try { $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant() } finally { $stream.Dispose() }
            if ($hash -ne $manifest.files[$name].sha256) { throw 'ZIP content differs' }
        }
        if ($Action -ne 'Verify') {
            if (!$SkillsDir) { throw 'SkillsDir must be the chosen Host skill parent directory' }
            $parent=[IO.Path]::GetFullPath($SkillsDir);Assert-NoLink $parent
            if (!(Test-Path -LiteralPath $parent -PathType Container)) { throw 'SkillsDir must already exist' }
            $target=[IO.Path]::GetFullPath((Join-Path $parent $manifest.name))
            if ([IO.Path]::GetDirectoryName($target) -ne $parent.TrimEnd([IO.Path]::DirectorySeparatorChar)) { throw 'Target escapes skill parent' }
            if ($Action -eq 'Install') {
                # Atomic ownership claim; an existing target is never overwritten.
                $null=New-Item -ItemType Directory -Path $target -ErrorAction Stop
                $ownedTarget=$target
                foreach ($entry in $archive.Entries) {
                    $name=$entry.FullName.Substring($manifest.name.Length+1);$dest=Join-Path $target $name
                    $null=[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($dest))
                    $inputStream=$entry.Open();$outputStream=[IO.File]::Open($dest,[IO.FileMode]::CreateNew)
                    try { $inputStream.CopyTo($outputStream) } finally { $inputStream.Dispose();$outputStream.Dispose() }
                }
                Assert-Installed $target $manifest
                $ownedTarget=$null
            } else {
                Assert-Installed $target $manifest
                if ($Action -eq 'Uninstall') {
                    # Re-resolve the exact checked owned package before removal.
                    Assert-NoLink $target
                    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($target)) -ne $parent.TrimEnd([IO.Path]::DirectorySeparatorChar)) { throw 'Removal target escaped' }
                    foreach ($name in $expected) { Remove-Item -LiteralPath (Join-Path $target $name) -Force }
                    # A concurrent new file must survive. Non-recursive removal
                    # fails on nonempty directories, reporting partial uninstall.
                    foreach ($dir in @('references','templates')) { [IO.Directory]::Delete((Join-Path $target $dir),$false) }
                    [IO.Directory]::Delete($target,$false)
                }
            }
        }
    } finally { $archive.Dispose() }
    @{ passed=$true; action=$Action; version=$manifest.version; source_commit=$manifest.source_commit; files=4; host_verified=$false } | ConvertTo-Json -Compress
    exit 0
} catch {
    # Preserve any partial installation for diagnosis; never print stale success.
    $detail=if ($ownedTarget) { "; partial installation preserved at $ownedTarget" } else { '' }
    [Console]::Error.WriteLine("FAIL: $($_.Exception.Message)$detail")
    exit 1
}
