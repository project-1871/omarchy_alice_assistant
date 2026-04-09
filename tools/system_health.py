"""
System Health Check Tool
Full check: OS, hardware (CPU/RAM/GPU), disk space, drive SMART health, filesystem errors, services.
"""

import subprocess
import os
import glob
from .base import Tool


class SystemHealthTool(Tool):
    name = "system_health"
    description = "Full system health check — OS, hardware, disk space, drive health, services"
    triggers = [
        "full system health", "system health check", "health check",
        "check my system", "check system", "system diagnostic", "diagnose system",
        "full health", "health report", "drive health", "hard drive health",
        "ssd health", "smart check", "how is my system doing",
        "check everything", "full check"
    ]

    def execute(self, query: str = "", **kwargs) -> str:
        sections = []
        sections.append(self._os_info())
        sections.append(self._cpu_info())
        sections.append(self._memory_info())
        sections.append(self._gpu_info())
        sections.append(self._disk_space())
        sections.append(self._drive_health())
        sections.append(self._filesystem_errors())
        sections.append(self._services())
        return "\n\n".join(s for s in sections if s)

    # ── helpers ──────────────────────────────────────────────

    def _run(self, cmd, timeout=10):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    def _run_any(self, cmd, timeout=10):
        """Run and return stdout regardless of exit code."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip()
        except Exception:
            return ""

    # ── OS ───────────────────────────────────────────────────

    def _os_info(self) -> str:
        parts = ["OS"]
        try:
            with open('/etc/os-release') as f:
                osrel = {}
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        osrel[k] = v.strip('"')
            distro = osrel.get('PRETTY_NAME', osrel.get('NAME', 'Linux'))
            parts.append(f"  Distro   : {distro}")
        except Exception:
            pass

        kernel = self._run(['uname', '-r'])
        if kernel:
            parts.append(f"  Kernel   : {kernel}")

        uptime = self._run(['uptime', '-p'])
        if uptime:
            parts.append(f"  Uptime   : {uptime}")

        return "\n".join(parts)

    # ── CPU ──────────────────────────────────────────────────

    def _cpu_info(self) -> str:
        parts = ["CPU"]

        # Load average
        try:
            with open('/proc/loadavg') as f:
                load = f.read().split()[:3]
            parts.append(f"  Load avg : {load[0]} / {load[1]} / {load[2]}  (1/5/15 min)")
        except Exception:
            pass

        # Core count
        try:
            with open('/proc/cpuinfo') as f:
                cores = sum(1 for l in f if l.startswith('processor'))
            parts.append(f"  Cores    : {cores}")
        except Exception:
            pass

        # Current frequency
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq') as f:
                freq_mhz = int(f.read().strip()) // 1000
            parts.append(f"  Frequency: {freq_mhz} MHz")
        except Exception:
            pass

        # Temperature (Intel coretemp or AMD k10temp)
        temp = self._hwmon_temp('coretemp') or self._hwmon_temp('k10temp')
        if temp:
            parts.append(f"  Temp     : {temp}°C")

        return "\n".join(parts)

    def _hwmon_temp(self, chip: str) -> str | None:
        for hwmon_dir in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
            try:
                with open(os.path.join(hwmon_dir, 'name')) as f:
                    if chip not in f.read().strip():
                        continue
                # Use temp1_input (first/package sensor)
                t_file = os.path.join(hwmon_dir, 'temp1_input')
                if os.path.exists(t_file):
                    with open(t_file) as f:
                        return str(int(f.read().strip()) // 1000)
            except Exception:
                continue
        return None

    # ── Memory ───────────────────────────────────────────────

    def _memory_info(self) -> str:
        parts = ["Memory"]
        try:
            mem = {}
            with open('/proc/meminfo') as f:
                for line in f:
                    k, v = line.split(':', 1)
                    if k in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
                        mem[k] = int(v.split()[0])

            total = mem['MemTotal'] / 1024 / 1024
            avail = mem['MemAvailable'] / 1024 / 1024
            used = total - avail
            pct = used / total * 100
            parts.append(f"  RAM      : {used:.1f} GB / {total:.1f} GB used  ({pct:.0f}%)")

            swap_t = mem.get('SwapTotal', 0)
            if swap_t > 0:
                swap_u = (swap_t - mem.get('SwapFree', swap_t)) / 1024 / 1024
                parts.append(f"  Swap     : {swap_u:.1f} GB / {swap_t/1024/1024:.1f} GB used")
            else:
                parts.append("  Swap     : none")
        except Exception as e:
            parts.append(f"  (error: {e})")
        return "\n".join(parts)

    # ── GPU (AMD sysfs) ───────────────────────────────────────

    def _gpu_info(self) -> str:
        parts = ["GPU"]
        found = False

        for card_dev in sorted(glob.glob('/sys/class/drm/card*/device')):
            try:
                vals = {}

                busy = os.path.join(card_dev, 'gpu_busy_percent')
                if os.path.exists(busy):
                    with open(busy) as f:
                        vals['usage'] = f.read().strip() + '%'

                mu = os.path.join(card_dev, 'mem_info_vram_used')
                mt = os.path.join(card_dev, 'mem_info_vram_total')
                if os.path.exists(mu) and os.path.exists(mt):
                    with open(mu) as f:
                        used_gb = int(f.read().strip()) / 1024**3
                    with open(mt) as f:
                        total_gb = int(f.read().strip()) / 1024**3
                    vals['vram'] = f"{used_gb:.1f} GB / {total_gb:.1f} GB"

                # Temps from hwmon under this card
                for hwmon in sorted(glob.glob(os.path.join(card_dev, 'hwmon', 'hwmon*'))):
                    for idx in range(1, 5):
                        t_in = os.path.join(hwmon, f'temp{idx}_input')
                        t_lb = os.path.join(hwmon, f'temp{idx}_label')
                        if os.path.exists(t_in):
                            with open(t_in) as f:
                                deg = int(f.read().strip()) // 1000
                            label = 'temp'
                            if os.path.exists(t_lb):
                                with open(t_lb) as f:
                                    label = f.read().strip()
                            vals[f'temp_{label}'] = f"{deg}°C"

                if vals:
                    if 'usage' in vals:
                        parts.append(f"  Usage    : {vals['usage']}")
                    if 'vram' in vals:
                        parts.append(f"  VRAM     : {vals['vram']}")
                    for k, v in vals.items():
                        if k.startswith('temp_'):
                            label = k[5:]
                            parts.append(f"  Temp ({label}): {v}")
                    found = True
                    break
            except Exception:
                continue

        if not found:
            parts.append("  (GPU sysfs info not available)")
        return "\n".join(parts)

    # ── Disk space ───────────────────────────────────────────

    def _disk_space(self) -> str:
        parts = ["Disk Space"]
        try:
            # Use df with device column to deduplicate (btrfs subvolumes share same device)
            result = subprocess.run(
                ['df', '-h', '--output=source,target,size,used,avail,pcent',
                 '-x', 'tmpfs', '-x', 'devtmpfs', '-x', 'overlay', '-x', 'squashfs'],
                capture_output=True, text=True, timeout=5
            )
            rows = result.stdout.strip().split('\n')[1:]
            seen_devices = set()
            for row in rows:
                cols = row.split()
                if len(cols) >= 6:
                    device, mount, size, used, avail, pct = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5]
                    # Skip duplicate devices (btrfs subvolumes)
                    if device in seen_devices:
                        continue
                    seen_devices.add(device)
                    bar = self._usage_bar(pct)
                    parts.append(f"  {mount:<22} {used:>6}/{size:<6}  ({pct:>4} used, {avail} free)  {bar}")
        except Exception as e:
            parts.append(f"  (error: {e})")
        return "\n".join(parts)

    def _usage_bar(self, pct_str: str) -> str:
        try:
            pct = int(pct_str.strip('%'))
            filled = pct // 10
            bar = '█' * filled + '░' * (10 - filled)
            warn = ' ⚠️' if pct >= 85 else (' ⚠' if pct >= 70 else '')
            return f"[{bar}]{warn}"
        except Exception:
            return ""

    # ── Drive SMART health ───────────────────────────────────

    def _drive_health(self) -> str:
        parts = ["Drive Health (SMART)"]

        drives = sorted(
            glob.glob('/dev/sd?') +
            glob.glob('/dev/nvme?n?') +
            glob.glob('/dev/hd?')
        )

        if not drives:
            parts.append("  No physical drives detected.")
            return "\n".join(parts)

        smartctl_ok = self._run(['which', 'smartctl']) is not None

        for drive in drives:
            if not smartctl_ok:
                parts.append(f"  {drive} : smartctl not installed  (install: sudo pacman -S smartmontools)")
                continue

            # Try without sudo first
            r = subprocess.run(
                ['smartctl', '-H', '-A', drive],
                capture_output=True, text=True, timeout=15
            )
            output = r.stdout + r.stderr

            # If permission denied, try sudo -n (non-interactive)
            if 'Permission denied' in output or 'Operation not permitted' in output:
                r2 = subprocess.run(
                    ['sudo', '-n', 'smartctl', '-H', '-A', drive],
                    capture_output=True, text=True, timeout=15
                )
                if r2.returncode == 0 or 'SMART' in r2.stdout:
                    output = r2.stdout + r2.stderr

            if 'overall-health' in output.lower():
                # Health status
                for line in output.split('\n'):
                    if 'overall-health' in line.lower():
                        status = 'PASSED ✅' if 'PASSED' in line else 'FAILED ❌'
                        parts.append(f"  {drive} : {status}")

                # Key SMART attributes
                watch = {
                    'Reallocated_Sector_Ct': 'Reallocated sectors',
                    'Pending_Sector_Count': 'Pending sectors',
                    'Offline_Uncorrectable': 'Uncorrectable sectors',
                    'UDMA_CRC_Error_Count': 'CRC errors',
                    'Power_On_Hours': 'Power-on hours',
                    'Temperature_Celsius': 'Temperature',
                    'SSD_Life_Left': 'SSD life left',
                    'Wear_Leveling_Count': 'Wear leveling',
                    'Media_Wearout_Indicator': 'Wearout indicator',
                    'Percentage_Used': 'Percentage used',
                }
                for line in output.split('\n'):
                    for attr, label in watch.items():
                        if attr in line:
                            cols = line.split()
                            raw = cols[-1] if cols else '?'
                            parts.append(f"    {label:<28}: {raw}")
                            break
            elif not output.strip():
                parts.append(f"  {drive} : no data (add to sudoers for full SMART access)")
            else:
                # Pull any meaningful line
                for line in output.split('\n'):
                    low = line.lower()
                    if any(x in low for x in ['health', 'error', 'warning', 'failed', 'passed']):
                        parts.append(f"  {drive} : {line.strip()}")
                        break
                else:
                    parts.append(f"  {drive} : SMART read failed (no sudo access?)")

        return "\n".join(parts)

    # ── Filesystem errors ────────────────────────────────────

    def _filesystem_errors(self) -> str:
        parts = ["Filesystem Errors (last 24h)"]

        result = subprocess.run(
            ['journalctl', '-k', '--since', '24 hours ago', '--no-pager', '-q'],
            capture_output=True, text=True, timeout=15
        )

        errors = []
        for line in result.stdout.split('\n'):
            low = line.lower()
            if any(x in low for x in ['i/o error', 'ext4-fs error', 'btrfs error', 'xfs error',
                                        'corrupt', 'ata error', 'medium error', 'bad block']):
                errors.append('  ' + line.strip())

        if errors:
            parts.extend(errors[:10])
        else:
            parts.append("  No disk/filesystem errors detected.")

        return "\n".join(parts)

    # ── Services ─────────────────────────────────────────────

    def _is_process_running(self, name: str) -> bool:
        """Check if a process is running by name."""
        r = subprocess.run(['pgrep', '-x', name], capture_output=True, timeout=5)
        if r.returncode == 0:
            return True
        # Also try partial match for things like 'ollama serve'
        r2 = subprocess.run(['pgrep', '-f', name], capture_output=True, timeout=5)
        return r2.returncode == 0

    def _services(self) -> str:
        parts = ["Key Services"]

        # System services (systemd system)
        system_svcs = [
            ('NetworkManager',     'Network'),
            ('waydroid-container', 'Waydroid'),
        ]
        for svc, label in system_svcs:
            r = subprocess.run(
                ['systemctl', 'is-active', '--quiet', svc],
                capture_output=True, timeout=5
            )
            status = '✅ active' if r.returncode == 0 else '❌ inactive'
            parts.append(f"  {label:<22}: {status}")

        # Process-based checks (user-session daemons / manually started)
        proc_checks = [
            ('pipewire',    'PipeWire (audio)'),
            ('ollama',      'Ollama (AI)'),
        ]
        for proc, label in proc_checks:
            running = self._is_process_running(proc)
            status = '✅ running' if running else '❌ not running'
            parts.append(f"  {label:<22}: {status}")

        # Failed system units
        r = subprocess.run(
            ['systemctl', '--failed', '--no-legend', '--no-pager'],
            capture_output=True, text=True, timeout=5
        )
        failed = [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
        if failed:
            parts.append(f"  Failed units: {', '.join(failed[:5])}")
        else:
            parts.append("  Failed units: none ✅")

        return "\n".join(parts)
