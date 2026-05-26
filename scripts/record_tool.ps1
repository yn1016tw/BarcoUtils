# record_tool.ps1 — Screen recording tool using ffmpeg gdigrab
# Detects all connected displays and records selected display(s) to MP4.

Add-Type -AssemblyName System.Windows.Forms

$FFMPEG      = "C:\Tools\ffmpeg\bin\ffmpeg.exe"
$FRAMERATE   = 30
$SCRIPT_DIR  = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUTPUT_DIR  = Join-Path $SCRIPT_DIR "..\logs\recordings"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Get-EvenSize($w, $h) {
    # yuv420p requires even dimensions
    if ($w % 2 -ne 0) { $w-- }
    if ($h % 2 -ne 0) { $h-- }
    return $w, $h
}

function Get-Displays {
    $screens = [System.Windows.Forms.Screen]::AllScreens | Sort-Object { $_.Bounds.X }
    $displays = @()
    $i = 1
    foreach ($s in $screens) {
        $w, $h = Get-EvenSize $s.Bounds.Width $s.Bounds.Height
        $displays += [PSCustomObject]@{
            Index   = $i
            Name    = $s.DeviceName -replace '\\\\.\\', 'DISPLAY' -replace '\\\.\\', ''
            Width   = $w
            Height  = $h
            OffsetX = $s.Bounds.X
            OffsetY = $s.Bounds.Y
            Primary = $s.Primary
        }
        $i++
    }
    return $displays
}

function Get-VirtualDesktop {
    $vd = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $w, $h = Get-EvenSize $vd.Width $vd.Height
    return [PSCustomObject]@{
        Width   = $w
        Height  = $h
        OffsetX = $vd.X
        OffsetY = $vd.Y
    }
}

function Start-FfmpegRecording($offsetX, $offsetY, $width, $height, $outputFile) {
    $args = "-f gdigrab -framerate $FRAMERATE " +
            "-offset_x $offsetX -offset_y $offsetY " +
            "-video_size ${width}x${height} " +
            "-i desktop " +
            "-c:v libx264 -preset veryfast -pix_fmt yuv420p -movflags +faststart " +
            "`"$outputFile`""

    $psi                       = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName              = $FFMPEG
    $psi.Arguments             = $args
    $psi.UseShellExecute       = $false
    $psi.RedirectStandardInput = $true
    $psi.CreateNoWindow        = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    return $proc
}

function Stop-FfmpegRecording($proc) {
    if ($proc -and -not $proc.HasExited) {
        try {
            $proc.StandardInput.Write('q')
            $proc.StandardInput.Flush()
            $proc.WaitForExit(8000) | Out-Null
        } catch {}
        if (-not $proc.HasExited) { $proc.Kill() }
    }
}

# ---------------------------------------------------------------------------
# Main menu loop
# ---------------------------------------------------------------------------

function Show-Menu {
    # Check ffmpeg
    if (-not (Test-Path $FFMPEG)) {
        Write-Host ""
        Write-Host "  ERROR: ffmpeg not found at:" -ForegroundColor Red
        Write-Host "    $FFMPEG" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Update `$FFMPEG path in record_tool.ps1 or install ffmpeg." -ForegroundColor Yellow
        Write-Host ""
        Read-Host "  Press Enter to exit"
        return
    }

    $displays = Get-Displays
    $vd       = Get-VirtualDesktop

    while ($true) {
        Clear-Host
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host "          Screen Recording Tool  (ffmpeg gdigrab)" -ForegroundColor Cyan
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host ("  {0,-5} {1,-18} {2,-18} {3}" -f "No.", "Resolution", "Offset (x,y)", "Device")
        Write-Host ("  " + "-" * 60)
        foreach ($d in $displays) {
            $tag = if ($d.Primary) { "  *primary" } else { "" }
            Write-Host ("  [{0}]   {1,-18} {2,-18} {3}{4}" -f `
                $d.Index,
                "$($d.Width)x$($d.Height)",
                "($($d.OffsetX), $($d.OffsetY))",
                $d.Name,
                $tag)
        }
        Write-Host ("  [A]   {0,-18} {1,-18} All displays (virtual desktop)" -f `
            "$($vd.Width)x$($vd.Height)", "($($vd.OffsetX), $($vd.OffsetY))")
        Write-Host ""
        Write-Host "  Output dir : $OUTPUT_DIR" -ForegroundColor DarkGray
        Write-Host "  Framerate  : $FRAMERATE fps" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [R] Refresh display list"
        Write-Host "  [O] Change output directory"
        Write-Host "  [0] Exit"
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Cyan
        $choice = Read-Host "  Select display to record"

        if ($choice -eq '0') { break }

        if ($choice -eq 'R' -or $choice -eq 'r') {
            $displays = Get-Displays
            $vd       = Get-VirtualDesktop
            continue
        }

        if ($choice -eq 'O' -or $choice -eq 'o') {
            $newDir = Read-Host "  Enter output directory"
            if ($newDir -and $newDir.Trim()) { $OUTPUT_DIR = $newDir.Trim() }
            continue
        }

        # Build list of targets to record
        $targets = @()

        if ($choice -eq 'A' -or $choice -eq 'a') {
            $targets += [PSCustomObject]@{
                Label   = "AllDisplays"
                OffsetX = $vd.OffsetX
                OffsetY = $vd.OffsetY
                Width   = $vd.Width
                Height  = $vd.Height
            }
        } else {
            $idx = $choice -as [int]
            if ($idx -ge 1 -and $idx -le $displays.Count) {
                $d = $displays[$idx - 1]
                $targets += [PSCustomObject]@{
                    Label   = "Display$($d.Index)_$($d.Name)"
                    OffsetX = $d.OffsetX
                    OffsetY = $d.OffsetY
                    Width   = $d.Width
                    Height  = $d.Height
                }
            } else {
                Write-Host "  Invalid option." -ForegroundColor Red
                Start-Sleep -Seconds 1
                continue
            }
        }

        # Ensure output directory exists
        if (-not (Test-Path $OUTPUT_DIR)) {
            New-Item -ItemType Directory -Path $OUTPUT_DIR | Out-Null
        }

        # Start recording(s)
        $procs   = @()
        $outFiles = @()
        foreach ($t in $targets) {
            $ts      = Get-Date -Format "yyyyMMdd_HHmmss"
            $outFile = Join-Path $OUTPUT_DIR "$($t.Label)_$ts.mp4"
            $outFiles += $outFile
            Write-Host ""
            Write-Host "  Recording  : $outFile" -ForegroundColor Green
            Write-Host "  Size       : $($t.Width)x$($t.Height)  Offset: ($($t.OffsetX), $($t.OffsetY))" -ForegroundColor DarkGray
            $proc = Start-FfmpegRecording $t.OffsetX $t.OffsetY $t.Width $t.Height $outFile
            $procs += $proc
        }

        Write-Host ""
        Write-Host "  Recording in progress..." -ForegroundColor Yellow
        Write-Host "  Press Enter to STOP recording." -ForegroundColor Yellow
        Read-Host | Out-Null

        # Stop all recordings
        foreach ($proc in $procs) {
            Stop-FfmpegRecording $proc
        }

        Write-Host ""
        Write-Host "  Recording stopped. Saved file(s):" -ForegroundColor Green
        foreach ($f in $outFiles) {
            Write-Host "    $f" -ForegroundColor White
        }
        Write-Host ""
        Read-Host "  Press Enter to return to menu"
    }
}

Show-Menu
