"""Background system monitor for STT optimisation session.

Samples CPU, RAM, and CPU frequency every second and writes to stt_sysmon.log.
Run alongside the main app:
    source venv/bin/activate && python stt_sysmon.py &
Stop with Ctrl+C or kill.
"""
import time
import psutil
import os
import signal
import sys

LOG = os.path.join(os.path.dirname(__file__), 'stt_sysmon.log')
INTERVAL = 1.0  # seconds

def main():
    print(f"[stt_sysmon] Logging to {LOG}  (Ctrl+C to stop)")
    with open(LOG, 'w') as f:
        f.write('timestamp,cpu_pct,ram_used_mb,ram_pct,cpu_freq_mhz\n')

    while True:
        ts = time.strftime('%H:%M:%S')
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        freq = psutil.cpu_freq()
        freq_mhz = round(freq.current) if freq else 0

        line = f'{ts},{cpu:.1f},{ram.used // 1024 // 1024},{ram.percent:.1f},{freq_mhz}\n'
        with open(LOG, 'a') as f:
            f.write(line)

        time.sleep(INTERVAL)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        main()
    except KeyboardInterrupt:
        print('\n[stt_sysmon] Stopped.')
