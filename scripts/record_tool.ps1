# record_tool.ps1 - Screen recording tool using ffmpeg gdigrab
# Detects all connected displays and records selected display(s) to MP4.

$ErrorActionPreference = 'Continue'
try {
    Add-Type -AssemblyName System.Windows.Forms
} catch {
    Write-Host "ERROR: Failed to load System.Windows.Forms: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

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
    # AllScreens is a cached static field — clear it to force re-enumeration
    $f = [System.Windows.Forms.Screen].GetField('screens',
        [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Static)
    if ($f) { $f.SetValue($null, $null) }
    $screens = [System.Windows.Forms.Screen]::AllScreens | Sort-Object { $_.Bounds.X }
    $displays = @()
    $i = 1
    foreach ($s in $screens) {
        $w, $h = Get-EvenSize $s.Bounds.Width $s.Bounds.Height
        $displays += [PSCustomObject]@{
            Index   = $i
            Name    = "Display $i"
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
        Write-Host "  +----------------------------------------------------------+" -ForegroundColor Red
        Write-Host "  |  ERROR: ffmpeg not found                                  |" -ForegroundColor Red
        Write-Host "  +----------------------------------------------------------+" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Path : $FFMPEG" -ForegroundColor Yellow
        Write-Host "  Fix  : Update `$FFMPEG in record_tool.ps1" -ForegroundColor DarkGray
        Write-Host ""
        Read-Host "  Press Enter to exit"
        return
    }

    $displays = Get-Displays
    $vd       = Get-VirtualDesktop

    while ($true) {
        Clear-Host
        $W      = 66
        $border = "-" * $W
        $thick  = "=" * $W

        Write-Host "  +$thick+" -ForegroundColor Cyan
        Write-Host "  |$("  Screen Recording Tool  -  ffmpeg gdigrab".PadRight($W))|" -ForegroundColor Cyan
        Write-Host "  +$thick+" -ForegroundColor Cyan

        # Display table header
        Write-Host "  |$(''.PadRight($W))|"
        Write-Host "  |  $("  KEY   RESOLUTION           DEVICE".PadRight($W-2))|" -ForegroundColor DarkGray
        Write-Host "  |  $("  ---   ------------------   ------------------".PadRight($W-2))|" -ForegroundColor DarkGray

        foreach ($d in $displays) {
            $primary = if ($d.Primary) { "  [primary]" } else { "" }
            $line = "  [{0}]   {1,-22} {2}{3}" -f `
                $d.Index,
                "$($d.Width) x $($d.Height)",
                $d.Name,
                $primary
            Write-Host "  |  $($line.PadRight($W-2))|" -ForegroundColor White
        }

        $allLine = "  [A]   {0,-22} All displays (virtual desktop)" -f "$($vd.Width) x $($vd.Height)"
        Write-Host "  |  $($allLine.PadRight($W-2))|" -ForegroundColor Yellow

        Write-Host "  |$(''.PadRight($W))|"
        Write-Host "  +$border+" -ForegroundColor Cyan

        # Actions
        Write-Host "  |$("  [R]  Refresh display list".PadRight($W))|"
        Write-Host "  |$("  [E]  Open recordings folder".PadRight($W))|"
        Write-Host "  |$("  [C]  Clear all recordings".PadRight($W))|"
        Write-Host "  |$("  [0]  Exit".PadRight($W))|"
        Write-Host "  +$thick+" -ForegroundColor Cyan
        Write-Host ""
        $choice = Read-Host "  Select"

        if ($choice -eq '0') { break }

        if ($choice -eq 'R' -or $choice -eq 'r') {
            $displays = Get-Displays
            $vd       = Get-VirtualDesktop
            continue
        }

        if ($choice -eq 'E' -or $choice -eq 'e') {
            if (-not (Test-Path $OUTPUT_DIR)) {
                New-Item -ItemType Directory -Path $OUTPUT_DIR | Out-Null
            }
            Start-Process explorer.exe $OUTPUT_DIR
            continue
        }

        if ($choice -eq 'C' -or $choice -eq 'c') {
            $mp4s = @(Get-ChildItem -Path $OUTPUT_DIR -Filter "*.mp4" -ErrorAction SilentlyContinue)
            if ($mp4s.Count -eq 0) {
                Write-Host "  No recordings found in $OUTPUT_DIR" -ForegroundColor DarkGray
            } else {
                Write-Host ""
                Write-Host "  Found $($mp4s.Count) file(s) in $OUTPUT_DIR" -ForegroundColor Yellow
                $confirm = Read-Host "  Delete all? [y/N]"
                if ($confirm -eq 'y' -or $confirm -eq 'Y') {
                    $mp4s | Remove-Item -Force
                    Write-Host "  Deleted $($mp4s.Count) file(s)." -ForegroundColor Green
                } else {
                    Write-Host "  Cancelled." -ForegroundColor DarkGray
                }
            }
            Start-Sleep -Seconds 1
            continue
        }

        # Build list of targets to record
        $targets = @()

        if ($choice -eq 'A' -or $choice -eq 'a') {
            $targets += [PSCustomObject]@{
                Label   = "All Displays"
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
                    Label   = $d.Name
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
        $procs    = @()
        $outFiles = @()
        Clear-Host
        Write-Host ""
        Write-Host "  +==================================================================+" -ForegroundColor Green
        Write-Host "  |  [REC] RECORDING                                                 |" -ForegroundColor Green
        Write-Host "  +------------------------------------------------------------------+" -ForegroundColor Green
        foreach ($t in $targets) {
            $ts      = Get-Date -Format "yyyyMMdd_HHmmss"
            $outFile = Join-Path $OUTPUT_DIR "$($t.Label)_$ts.mp4"
            $outFiles += $outFile
            Write-Host "  |  Target : $($t.Label.PadRight(56))|" -ForegroundColor White
            Write-Host "  |  Size   : $("$($t.Width) x $($t.Height)".PadRight(56))|" -ForegroundColor DarkGray
            Write-Host "  |  File   : $(([System.IO.Path]::GetFileName($outFile)).PadRight(56))|" -ForegroundColor DarkGray
            Write-Host "  |$(''.PadRight(66))|" -ForegroundColor Green
            $proc = Start-FfmpegRecording $t.OffsetX $t.OffsetY $t.Width $t.Height $outFile
            $procs += $proc
        }
        Write-Host "  |  Press Enter to STOP...$(''.PadRight(42))|" -ForegroundColor Yellow
        Write-Host "  +==================================================================+" -ForegroundColor Green
        Write-Host ""
        Read-Host | Out-Null

        # Stop all recordings
        Write-Host "  Stopping... please wait." -ForegroundColor Yellow
        foreach ($proc in $procs) {
            Stop-FfmpegRecording $proc
        }

        Write-Host ""
        Write-Host "  +==================================================================+" -ForegroundColor Cyan
        Write-Host "  |  DONE - Recording saved                                          |" -ForegroundColor Cyan
        Write-Host "  +------------------------------------------------------------------+" -ForegroundColor Cyan
        foreach ($f in $outFiles) {
            Write-Host "  |  $([System.IO.Path]::GetFileName($f).PadRight(64))|" -ForegroundColor White
            Write-Host "  |  $($f.PadRight(64))|" -ForegroundColor DarkGray
        }
        Write-Host "  +==================================================================+" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "  Press Enter to return to menu"
    }
}

try {
    Show-Menu
} catch {
    Write-Host ""
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Write-Host "  $($_.ScriptStackTrace)" -ForegroundColor DarkGray
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}
