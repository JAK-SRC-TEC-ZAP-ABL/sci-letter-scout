param(
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$cataloguePath = Join-Path $RepositoryRoot 'config/journals.json'
$outputPath = Join-Path $RepositoryRoot 'harmony/LetterScout/entry/src/main/ets/data/BuiltinJournals.ets'
$catalogue = Get-Content -LiteralPath $cataloguePath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $catalogue.journals -or $catalogue.journals.Count -eq 0) {
  throw 'Journal catalogue is empty'
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('// Generated from config/journals.json. Run scripts/generate_builtin_journals.ps1 after catalogue changes.')
$lines.Add('export interface BuiltinJournal {')
$lines.Add('  name: string;')
$lines.Add('  enabled: boolean;')
$lines.Add('  specialty: string;')
$lines.Add('}')
$lines.Add('')
$lines.Add('export const BUILTIN_JOURNALS: BuiltinJournal[] = [')
foreach ($journal in $catalogue.journals) {
  if ([string]::IsNullOrWhiteSpace($journal.name)) { throw 'Journal name is missing' }
  $specialty = if ($journal.specialty) { [string]$journal.specialty } else { 'oncology' }
  $nameLiteral = ConvertTo-Json -InputObject ([string]$journal.name) -Compress
  $specialtyLiteral = ConvertTo-Json -InputObject $specialty -Compress
  $enabledLiteral = if ($journal.enabled) { 'true' } else { 'false' }
  $lines.Add("  { name: $nameLiteral, enabled: $enabledLiteral, specialty: $specialtyLiteral },")
}
$lines.Add('];')

$parent = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
[System.IO.File]::WriteAllText($outputPath, ($lines -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Output "Generated $($catalogue.journals.Count) bundled journals in $outputPath"
