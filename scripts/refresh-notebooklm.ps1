# Refreshes the NotebookLM session and pushes it to the GitHub secret.
#
# Runs `notebooklm auth check --test` (which refreshes the cookies in
# storage_state.json), and if the session is still valid, updates the
# NOTEBOOKLM_AUTH_JSON secret. If the session has expired, it notifies you to
# run `notebooklm login` manually and exits without touching the secret.
#
# Schedule this via Task Scheduler; only re-login by hand when told to.

$ErrorActionPreference = "Stop"

$profilePath = "$env:USERPROFILE\.notebooklm\profiles\default\storage_state.json"

function Show-Toast($message) {
    # Best-effort Windows notification; falls back to console if unavailable.
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $texts = $template.GetElementsByTagName("text")
        $texts.Item(0).AppendChild($template.CreateTextNode("Daily Drive podcast")) | Out-Null
        $texts.Item(1).AppendChild($template.CreateTextNode($message)) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("NotebookLM").Show($toast)
    } catch {
        Write-Warning $message
    }
}

Write-Host "Checking NotebookLM auth..."
# auth check --test hits NotebookLM and refreshes storage_state.json on success.
notebooklm auth check --test
if ($LASTEXITCODE -ne 0) {
    Show-Toast "NotebookLM session expired. Run: notebooklm login"
    Write-Warning "Auth check failed. Run 'notebooklm login', then re-run this script."
    exit 1
}

if (-not (Test-Path $profilePath)) {
    throw "storage_state.json not found at $profilePath"
}

Write-Host "Auth OK. Pushing refreshed token to GitHub secret..."
$auth = Get-Content -Raw $profilePath
$auth | gh secret set NOTEBOOKLM_AUTH_JSON
if ($LASTEXITCODE -ne 0) {
    throw "gh secret set failed (is 'gh' authenticated? run 'gh auth status')."
}

Write-Host "Done: NOTEBOOKLM_AUTH_JSON updated $(Get-Date -Format 'yyyy-MM-dd HH:mm')."
