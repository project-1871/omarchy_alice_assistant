"""System stats tool - CPU, RAM, disk, battery"""

import subprocess
from tools.base import Tool


class SystemTool(Tool):
    name = "system"
    description = "Get system stats like CPU, RAM, disk usage"
    triggers = [
        "cpu", "ram", "memory", "disk", "storage", "battery",
        "system stats", "how's my system", "system status",
        "disk space", "free space", "memory usage"
    ]

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        try:
            if "cpu" in query_lower or "processor" in query_lower:
                return self._get_cpu()
            elif "ram" in query_lower or "memory" in query_lower:
                return self._get_memory()
            elif "disk" in query_lower or "storage" in query_lower or "space" in query_lower:
                return self._get_disk()
            elif "battery" in query_lower:
                return self._get_battery()
            else:
                # Return all stats
                return self._get_all()
        except Exception as e:
            return f"Couldn't get system stats: {e}"

    def _get_cpu(self) -> str:
        """Get CPU usage and load"""
        # Get load average
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]

        # Get CPU usage via top (1 iteration)
        result = subprocess.run(
            ['grep', '-c', '^processor', '/proc/cpuinfo'],
            capture_output=True, text=True
        )
        cores = result.stdout.strip()

        # Get current frequency
        try:
            result = subprocess.run(
                ['cat', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'],
                capture_output=True, text=True
            )
            freq_mhz = int(result.stdout.strip()) // 1000
            freq_str = f" running at {freq_mhz} MHz"
        except:
            freq_str = ""

        return f"CPU: {cores} cores{freq_str}. Load average: {load[0]}, {load[1]}, {load[2]} over 1, 5, 15 minutes."

    def _get_memory(self) -> str:
        """Get RAM usage"""
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()

        mem = {}
        for line in lines:
            parts = line.split()
            if parts[0] in ['MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:']:
                mem[parts[0]] = int(parts[1])

        total_gb = mem['MemTotal:'] / 1024 / 1024
        avail_gb = mem['MemAvailable:'] / 1024 / 1024
        used_gb = total_gb - avail_gb
        percent = (used_gb / total_gb) * 100

        return f"RAM: {used_gb:.1f} GB used of {total_gb:.1f} GB ({percent:.0f}% used). {avail_gb:.1f} GB available."

    def _get_disk(self) -> str:
        """Get disk usage for main partitions"""
        result = subprocess.run(
            ['df', '-h', '--output=target,size,used,avail,pcent', '/home', '/'],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')[1:]  # Skip header

        disks = []
        seen = set()
        for line in lines:
            parts = line.split()
            mount, size, used, avail, percent = parts[0], parts[1], parts[2], parts[3], parts[4]
            if mount not in seen:
                seen.add(mount)
                disks.append(f"{mount}: {used} used of {size} ({percent}), {avail} free")

        return "Disk: " + ". ".join(disks) + "."

    def _get_battery(self) -> str:
        """Get battery status"""
        try:
            # Try using /sys/class/power_supply
            with open('/sys/class/power_supply/BAT0/capacity', 'r') as f:
                capacity = f.read().strip()
            with open('/sys/class/power_supply/BAT0/status', 'r') as f:
                status = f.read().strip()
            return f"Battery: {capacity}% ({status.lower()})."
        except FileNotFoundError:
            return "No battery detected. This is probably a desktop."

    def _get_all(self) -> str:
        """Get all system stats"""
        parts = []
        parts.append(self._get_cpu())
        parts.append(self._get_memory())
        parts.append(self._get_disk())
        return " ".join(parts)
