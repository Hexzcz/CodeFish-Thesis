$Url = "http://localhost:8000"

Write-Host "Starting browser-opener background task..." -ForegroundColor Cyan

# Create a background job to check server status and open the browser
$jobCode = {
    param($Url)
    $MaxWaitSeconds = 60
    $WaitCount = 0
    $ServerReady = $false

    while ($WaitCount -lt $MaxWaitSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -Method Get -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $ServerReady = $true
                break
            }
        } catch {
            # Server not ready yet
        }
        Start-Sleep -Seconds 1
        $WaitCount++
    }

    if ($ServerReady) {
        # Open the default browser
        Start-Process $Url
    }
}

# Start the background job
Start-Job -ScriptBlock $jobCode -ArgumentList $Url | Out-Null

Write-Host "Starting the CodeFish server (Backend & Frontend)..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow

# Start the Python server in the foreground so you can see the logs
try {
    python -m uvicorn backend.main:app --reload
} finally {
    # Clean up jobs when the server is stopped
    Get-Job | Remove-Job -Force
}
