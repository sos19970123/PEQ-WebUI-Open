# Extract ALL FR curves from RAA canvas-drawing scripts (ATH-E40 report) — v3
# Generalized: auto-detect dB-axis column & freq-axis row by label clustering.
# Palette (confirmed via legend swatches): #094A78=E40 measured, #ffc882=Harman raw, #BB6B03=Harman smoothed
$ErrorActionPreference = 'Stop'
$dir = "F:\Hermes-Deepseek\headphone-lab\measurements\raa-e40"
$html = [System.IO.File]::ReadAllText("$dir\raa-e40-page.html")
Get-ChildItem "$dir\RAA_E40_*.csv" | Remove-Item -Force

$series = @(
    @{ col = '#094A78'; tag = 'E40' },
    @{ col = '#ffc882'; tag = 'HarmanRaw' },
    @{ col = '#BB6B03'; tag = 'HarmanSmooth' }
)
$scripts = [regex]::Matches($html, "<script name='FR-SCRIPT'>([\s\S]*?)</script>")
$report = @()

function Fit([double[]]$u, [double[]]$v) {
    $n = $u.Length; $su = ($u | Measure-Object -Sum).Sum; $sv = ($v | Measure-Object -Sum).Sum
    $suu = (($u | ForEach-Object { $_ * $_ }) | Measure-Object -Sum).Sum
    $suv = 0.0; for ($i = 0; $i -lt $n; $i++) { $suv += $u[$i] * $v[$i] }
    $a = ($n * $suv - $su * $sv) / ($n * $suu - $su * $su)
    return @($a, ($sv - $a * $su) / $n)
}

for ($s = 0; $s -lt $scripts.Count; $s++) {
    $js = $scripts[$s].Groups[1].Value
    $cidHit = [regex]::Match($js, 'getElementById\("myCanvasv(\d*)"\)').Groups[1].Value
    # only the two clean summary charts (cid-tagged inline canvases); skip redundant variants w/ polluted axes
    if (-not ($cidHit -match '^\d+$')) { continue }
    $titleHit = [regex]::Match($js, 'fillText\("([^"]{15,90})"')
    $slug = ($titleHit.Groups[1].Value -replace '^Audio-Technica ATH-E40\s*-?\s*', '' -replace '[^\w]+', '_').Trim('_')
    if ($slug.Length -gt 30) { $slug = $slug.Substring(0, 30) }

    # numeric labels: value,x,y
    $labs = @()
    foreach ($m in [regex]::Matches($js, 'fillText\("(-?[\d.]+)", (-?[\d.]+), (-?[\d.]+)\)')) {
        $labs += [pscustomobject]@{ v = [double]$m.Groups[1].Value; x = [double]$m.Groups[2].Value; y = [double]$m.Groups[3].Value }
    }
    if ($labs.Count -lt 4) { continue }
    # dB axis: cluster by x, take cluster with max x that has >=3 members
    $dbGrp = $labs | Group-Object { [math]::Round($_.x, 0) } | Where-Object { $_.Count -ge 3 } | Sort-Object { [double]$_.Name } | Select-Object -Last 1
    # freq axis: cluster by y, take cluster with max y that has >=3 members
    $fGrp = $labs | Group-Object { [math]::Round($_.y, 0) } | Where-Object { $_.Count -ge 3 } | Sort-Object { [double]$_.Name } | Select-Object -Last 1
    if (-not $dbGrp -or -not $fGrp) { continue }
    # linear fits (inline least squares: value = a*coord + b)
    $dbL = @($dbGrp.Group | Sort-Object y)
    $su = 0.0; $sv = 0.0; $suu = 0.0; $suv = 0.0
    foreach ($o in $dbL) { $su += $o.y; $sv += $o.v; $suu += $o.y * $o.y; $suv += $o.y * $o.v }
    $nn = $dbL.Count
    $abA = ($nn * $suv - $su * $sv) / ($nn * $suu - $su * $su)
    $abB = ($sv - $abA * $su) / $nn
    $fL = @($fGrp.Group | Sort-Object x)
    $su = 0.0; $sv = 0.0; $suu = 0.0; $suv = 0.0
    foreach ($o in $fL) { $lf = [math]::Log10($o.v); $su += $o.x; $sv += $lf; $suu += $o.x * $o.x; $suv += $o.x * $lf }
    $nn = $fL.Count
    $cfC = ($nn * $suv - $su * $sv) / ($nn * $suu - $su * $su)
    $cfD = ($sv - $cfC * $su) / $nn

    foreach ($se in $series) {
        # collect ALL segments for this color, keep the one with most points
        $best = $null; $idx = 0
        while (($idx = $js.IndexOf($se.col, $idx)) -ge 0) {
            $nx = $js.IndexOf('strokeStyle', $idx + 10); if ($nx -lt 0) { $nx = $js.Length }
            $seg = $js.Substring($idx, $nx - $idx)
            $pts = @()
            foreach ($m in [regex]::Matches($seg, '(?:moveTo|lineTo)\(([-\d.]+),\s*([-\d.]+)\)')) {
                $freq = [math]::Pow(10, $cfC * [double]$m.Groups[1].Value + $cfD)
                $db = $abA * [double]$m.Groups[2].Value + $abB
                $pts += [pscustomobject]@{ freq = [math]::Round($freq, 2); db = [math]::Round($db, 2) }
            }
            if ($pts.Count -ge 10 -and (-not $best -or $pts.Count -gt $best.Count)) { $best = $pts }
            $idx += 10
        }
        if (-not $best) { continue }
        $csv = "$dir\RAA_E40_c$cidHit`_$slug`_$($se.tag).csv"
        $lines = 'freq,dB'; foreach ($p in $best) { $lines += "`n$($p.freq),$($p.db)" }
        [System.IO.File]::WriteAllText($csv, $lines)
        $v1k = ($best | Sort-Object { [math]::Abs($_.freq - 1000) } | Select-Object -First 1).db
        $report += [pscustomobject]@{ Canvas = $cidHit; Chart = $slug; Series = $se.tag; Pts = $best.Count; At20 = $best[0].db; At1k = $v1k; AtLast = $best[-1].db }
    }
}
$report | Sort-Object Canvas, Series | Format-Table -AutoSize | Out-String -Width 200
