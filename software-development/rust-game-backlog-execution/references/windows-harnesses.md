# Windows harnesses (PowerShell, run from git-bash)

Run with: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/path/script.ps1 -Out C:/path/x`

## Window capture without touching other windows

```powershell
param([string]$Out, [string]$Exe = "D:\repo\target\debug\game.exe")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
}
"@
$env:ISO_EXIT_AFTER_FRAMES = "900"   # safety exit
$proc = Start-Process -FilePath $Exe -WorkingDirectory "D:\repo" -PassThru `
    -RedirectStandardError "$Out.log" -RedirectStandardOutput "$Out.out"
Start-Sleep -Seconds 4
$proc.Refresh(); $h = $proc.MainWindowHandle
$r = New-Object RECT; [W]::GetClientRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap $r.Right, $r.Bottom
$g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
[W]::PrintWindow($h, $hdc, 3) | Out-Null     # PW_CLIENTONLY | PW_RENDERFULLCONTENT
$g.ReleaseHdc($hdc); $bmp.Save("$Out.png"); $g.Dispose(); $bmp.Dispose()
$proc.CloseMainWindow() | Out-Null
if (-not $proc.WaitForExit(8000)) { $proc.Kill() }
Write-Output "captured $Out.png ($($r.Right)x$($r.Bottom))"
```

The script starts the binary that is already built: `cargo build` first, at the commit or tree
the capture is meant to show.

## CPU while minimized

```powershell
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class Win { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n); }
"@
function Cpu($s) { $p.Refresh(); $t0 = $p.TotalProcessorTime.TotalMilliseconds; Start-Sleep $s
  $p.Refresh(); [math]::Round(($p.TotalProcessorTime.TotalMilliseconds - $t0) / ($s * 10), 1) }  # % of one core
# visible = Cpu 3; ShowWindow(h, 6) minimize; minimized = Cpu 5; ShowWindow(h, 9) restore; restored = Cpu 3
```

env_logger writes to stderr: redirect it to a file and grep it for pause/resume lines and wgpu
errors afterwards.

## Pixel diff of two captures

```python
import sys
from PIL import Image, ImageChops
a = Image.open(sys.argv[1]).convert("RGB")
b = Image.open(sys.argv[2]).convert("RGB")
d = ImageChops.difference(a, b).convert("L")
h = d.histogram(); n = sum(h)
changed = d.point(lambda v: 255 if v > 2 else 0)
w, ht = d.size  # the outer 40 px, where culling mistakes show first
edge = sum(changed.crop(r).histogram()[255] for r in
           [(0, 0, w, 40), (0, ht - 40, w, ht), (0, 0, 40, ht), (w - 40, 0, w, ht)])
print(f"differing {100 * sum(h[1:]) / n:.3f} %, by >2 levels {100 * sum(h[3:]) / n:.3f} %, "
      f"max {d.getextrema()[1]}, box of changes {changed.getbbox()}, border pixels {edge}")
```

`0.000 %, max 0` proves "no visual change". When anything in the scene animates, take two
before captures: their diff is the noise floor and its box shows where the animation is, and an
after capture identical to either before capture still proves no change. Changes along the
border after a culling change are things that popped. Run it with a native Python that has
Pillow, and pass `C:/...` paths.
