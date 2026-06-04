#Requires -RunAsAdministrator
# fix-barco-driver.ps1
# Fix duplicate BarcoClickShareDrv causing Gen5 Button HID open failure

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Barco ClickShare Driver Fix Tool" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Find all barcoclicksharedrv entries
Write-Host "[1] Scanning installed Barco ClickShare drivers..." -ForegroundColor Yellow

$rawOutput = pnputil /enum-drivers
$blocks = ($rawOutput -join "`n") -split "(?=Published Name\s*:)"
$barcoDrivers = $blocks | Where-Object { $_ -match "barcoclickshare" }

if ($barcoDrivers.Count -eq 0) {
    Write-Host "    No Barco ClickShare driver found." -ForegroundColor Gray
} else {
    Write-Host "    Found $($barcoDrivers.Count) driver(s):" -ForegroundColor White
    $oemList = @()
    foreach ($block in $barcoDrivers) {
        $oem     = if ($block -match "Published Name\s*:\s*(\S+)")  { $Matches[1] } else { "?" }
        $orig    = if ($block -match "Original Name\s*:\s*(\S+)")   { $Matches[1] } else { "?" }
        $version = if ($block -match "Driver Version\s*:\s*(\S+(?:\s+\S+)?)")  { $Matches[1] } else { "?" }
        Write-Host "      - $oem  ($orig)  version: $version" -ForegroundColor White
        $oemList += $oem
    }
    Write-Host ""

    if ($barcoDrivers.Count -lt 2) {
        Write-Host "[!] Only one driver found, no duplicate conflict." -ForegroundColor Green
        Write-Host "    If issue persists, reinstall ClickShare Desktop App." -ForegroundColor Gray
    } else {
        Write-Host "[2] Duplicate drivers detected. Removing all versions..." -ForegroundColor Yellow
        Write-Host "    Reinstall ClickShare Desktop App after this to restore the correct driver." -ForegroundColor Gray
        Write-Host ""

        $confirm = Read-Host "    Confirm removal? (Y/N)"
        if ($confirm -ne "Y" -and $confirm -ne "y") {
            Write-Host "    Cancelled." -ForegroundColor Gray
            exit 0
        }

        foreach ($oem in $oemList) {
            Write-Host "    Removing $oem ..." -ForegroundColor Yellow
            $result = pnputil /delete-driver $oem /uninstall /force 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "      OK - removed" -ForegroundColor Green
            } else {
                Write-Host "      FAILED: $result" -ForegroundColor Red
            }
        }
    }
}

# Step 2: Show current PID:0185 interface status
Write-Host ""
Write-Host "[3] Current VID:0600 PID:0185 device interface status:" -ForegroundColor Yellow
Get-PnpDevice | Where-Object { $_.InstanceId -like "*0600*0185*" } |
    Select-Object Status, Class, FriendlyName, InstanceId |
    Format-Table -AutoSize

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Done. Replug the Button and reinstall" -ForegroundColor Cyan
Write-Host " ClickShare Desktop App." -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan