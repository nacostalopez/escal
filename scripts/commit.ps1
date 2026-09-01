<#
Fixes pending issues and commits, by invoking Claude Code headlessly with the
QuickCommit / ComitChanges skills (see ~/.claude/skills/). Both skills fix
lint/format issues, obvious bugs, and failing tests caused by the pending
change before committing; they differ only in where the commit message comes
from.

Usage (from any directory):
    .\scripts\commit.ps1                       # ComitChanges: message auto-drafted
    .\scripts\commit.ps1 "fix login bug"        # QuickCommit: your exact message

Runs with --permission-mode bypassPermissions so it doesn't stop to ask for
approval on every git/edit/test command — that's the point of a one-shot
terminal command. It only touches the current repo; review what it did
afterward with `git log -1` / `git show`.
#>

param(
    [Parameter(Position = 0)]
    [string]$Message
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    if ($Message) {
        $prompt = "/QuickCommit $Message"
    } else {
        $prompt = "/ComitChanges"
    }

    & claude -p $prompt --permission-mode bypassPermissions
} finally {
    Pop-Location
}
