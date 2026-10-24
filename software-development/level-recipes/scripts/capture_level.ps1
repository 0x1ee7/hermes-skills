param(
    [string]$Out,
    [int]$WaitMs = 5000,
    [string]$Exe = "D:\dev\iso-engine\target\debug\demo.exe",
    [string]$WorkDir = "D:\dev\iso-engine",
    [string]$Level = ""
)
# Captures the demo's client area with PrintWindow (works when the window is not in front; never
# touches other windows), then closes the game. -Level is passed as the demo's level argument.
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
}
"@
$env:ISO_EXIT_AFTER_FRAMES = "3000"   # safety exit
if ($Level -ne "") {
    $proc = Start-Process -FilePath $Exe -ArgumentList @($Level) -WorkingDirectory $WorkDir -PassThru `
        -RedirectStandardError "$Out.log" -RedirectStandardOutput "$Out.out"
} else {
    $proc = Start-Process -FilePath $Exe -WorkingDirectory $WorkDir -PassThru `
        -RedirectStandardError "$Out.log" -RedirectStandardOutput "$Out.out"
}
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
