import csv, statistics

d = r'F:\MIMO-Space\AutoEq-4.1.2\AutoEq-4.1.2\results\oratory1990\over-ear\Beyerdynamic DT 900 Pro X\Beyerdynamic DT 900 Pro X.csv'
rows = []
with open(d, 'rb') as f:
    text = f.read().decode('utf-8-sig', errors='replace')
for row in csv.DictReader(text.splitlines()):
    rows.append((float(row['frequency']), float(row['raw']), float(row['smoothed']),
                 float(row['error_smoothed']), float(row['target'])))
rows.sort()

bands = [(30,'30Hz'),(60,'60Hz'),(100,'100Hz'),(200,'200Hz'),(400,'400Hz'),
         (1000,'1kHz'),(2000,'2kHz'),(3000,'3kHz'),(4000,'4kHz'),(5000,'5kHz'),
         (6000,'6kHz'),(8000,'8kHz'),(10000,'10kHz'),(12000,'12kHz')]

def at(freq):
    return rows[min(range(len(rows)), key=lambda i: abs(rows[i][0]-freq))]

print('freq     raw    sm     target  raw-target')
for f, label in bands:
    r_ = at(f)
    print(f'{label:>6} {r_[1]:7.1f} {r_[2]:7.1f} {r_[4]:7.1f} {r_[1]-r_[4]:+7.1f}')

# segment stats on raw vs target (not smoothed, to catch real peaks)
print()
print('segment       mean    peak   dip')
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,12000),(12000,20000)]
for lo, hi in seg:
    sel = [r[1]-r[4] for r in rows if lo <= r[0] < hi]
    print(f'{lo:>6}-{hi:<6}Hz  {statistics.mean(sel):+6.2f}  {max(sel):+6.2f}  {min(sel):+6.2f}')

# find biggest peak/dip positions in treble region (3k-10k) at 1/3 octave-ish granularity
print()
print('detail 3k-10k every ~200-500Hz:')
prev = None
for r in rows:
    if 3000 <= r[0] <= 10000 and (prev is None or r[0]-prev >= 300):
        print(f'{r[0]:6.0f}Hz  sm {r[2]:+7.2f}  raw-target {r[1]-r[4]:+7.2f}')
        prev = r[0]
