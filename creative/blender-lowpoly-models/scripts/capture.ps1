param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$WaitMs = 5000,
    [int]$ExitAfterFrames = 3000
)
# Starts the game, waits, captures its client area with PrintWindow (works when the window is not
# in front and never touches other windows), then closes it. Writes $Out.png, $Out.log (stderr)
# and $Out.out (stdout).
# Usage from git-bash:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/path/capture.ps1 `
#     -Exe D:\repo\target\debug\demo.exe -WorkDir D:\repo -Out C:/scratch/shot
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
}
"@
$env:ISO_EXIT_AFTER_FRAMES = "$ExitAfterFrames"   # safety exit if closing fails
$proc = Start-Process -FilePath $Exe -WorkingDirectory $WorkDir -PassThru `
    -RedirectStandardError "$Out.log" -RedirectStandardOutput "$Out.out"
Start-Sleep -Milliseconds $WaitMs
$proc.Refresh(); $h = $proc.MainWindowHandle
$r = New-Object RECT; [W]::GetClientRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap $r.Right, $r.Bottom
$g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
[W]::PrintWindow($h, $hdc, 3) | Out-Null     # PW_CLIENTONLY | PW_RENDERFULLCONTENT
$g.ReleaseHdc($hdc); $bmp.Save("$Out.png"); $g.Dispose(); $bmp.Dispose()
$proc.CloseMainWindow() | Out-Null
if (-not $proc.WaitForExit(8000)) { $proc.Kill() }
"captured $Out.png ($($r.Right)x$($r.Bottom))"
