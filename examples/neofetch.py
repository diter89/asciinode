import getpass
import os
import platform
import shutil
import subprocess
from pathlib import Path
from time import perf_counter, sleep, time as current_time
from typing import Dict, Iterable, List, Tuple

import psutil
from rich import print
from rich.live import Live
from rich.panel import Panel

from asciinode.ascii_diagram import Diagram


def _read_os_release() -> Dict[str, str]:
    data: Dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def _read_first_line(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.readline().strip()
    except OSError:
        return None


def _make_bar(percent: float, width: int = 12) -> str:
    capped = max(0.0, min(100.0, percent))
    filled = int(round((capped / 100.0) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _format_rate(bytes_per_second: float) -> str:
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    value = bytes_per_second
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:6.1f} {unit}"
        value /= 1024
    return f"{bytes_per_second:.1f} B/s"


def _to_mib(value: float) -> float:
    return value / (1024 * 1024)


def _format_storage(used: float, total: float) -> str:
    gib = 1024 * 1024 * 1024
    return f"{used / gib:.1f} GiB / {total / gib:.1f} GiB"


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "Unknown"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _get_uptime() -> float | None:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            raw = handle.read().split()
        return float(raw[0])
    except (OSError, ValueError, IndexError):
        return None


def _count_packages() -> str:
    commands: Iterable[Tuple[List[str], str]] = (
        (["dpkg-query", "-f", "${binary:Package}\n", "-W"], "dpkg"),
        (["rpm", "-qa"], "rpm"),
    )
    for cmd, label in commands:
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
        count = sum(1 for line in result.stdout.splitlines() if line.strip())
        if count:
            return f"{count} ({label})"
    return "Unknown"


def _get_shell() -> str:
    return os.environ.get("SHELL") or shutil.which("bash") or "Unknown"


def _get_terminal() -> str:
    term = os.environ.get("TERM")
    if term:
        return term
    size = shutil.get_terminal_size(fallback=(0, 0))
    if size.columns and size.lines:
        return f"tty {size.columns}x{size.lines}"
    return "Unknown"


def _get_cpu_model() -> str:
    path = Path("/proc/cpuinfo")
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[-1].strip()
    return platform.processor() or "Unknown"


def _get_memory() -> str:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return "Unknown"
    info: Dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parts = value.strip().split()
        if not parts:
            continue
        try:
            info[key] = int(parts[0])
        except ValueError:
            continue
    total = info.get("MemTotal")
    available = info.get("MemAvailable")
    if not total or not available:
        return "Unknown"
    used = total - available
    def to_mib(kib: int) -> float:
        return kib / 1024
    return f"{to_mib(used):.0f} MiB / {to_mib(total):.0f} MiB"


def _get_resolution() -> str:
    size = shutil.get_terminal_size(fallback=(0, 0))
    if size.columns and size.lines:
        return f"{size.columns}x{size.lines} (terminal)"
    return "Unknown"


def _get_environment() -> Tuple[str, str]:
    de = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")
    wm = os.environ.get("XDG_SESSION_TYPE")
    return de or "Unknown", wm or "Unknown"


def _get_host_model() -> str:
    for path in (
        "/sys/devices/virtual/dmi/id/product_name",
        "/sys/devices/virtual/dmi/id/board_name",
    ):
        value = _read_first_line(path)
        if value:
            return value
    return "Unknown"


def gather_info() -> Dict[str, List[Tuple[str, str]]]:
    os_release = _read_os_release()
    os_name = os_release.get("PRETTY_NAME") or platform.platform()
    kernel = platform.release()
    packages = _count_packages()
    shell = _get_shell()
    terminal = _get_terminal()
    resolution = _get_resolution()
    desktop, session = _get_environment()
    cpu = _get_cpu_model()
    memory = _get_memory()
    host_model = _get_host_model()

    return {
        "System": [
            ("OS", os_name),
            ("Host", host_model),
            ("Kernel", kernel),
            ("Packages", packages),
        ],
        "Environment": [
            ("Shell", shell),
            ("Terminal", terminal),
            ("Resolution", resolution),
            ("DE", desktop),
            ("Session", session),
        ],
        "Hardware": [
            ("CPU", cpu),
            ("Memory", memory),
        ],
    }


def _format_block(title: str, items: List[Tuple[str, str]]) -> str:
    lines = [title]
    lines.extend(f"{label}: {value}" for label, value in items)
    return "\n".join(lines)


def _format_hardware(metrics: Dict[str, float]) -> str:
    lines = [
        "Hardware",
        (
            "CPU: "
            f"{metrics['cpu_percent']:5.1f}% [green]{_make_bar(metrics['cpu_percent'])}[/green]"
        ),
        (
            "Memory: "
            f"{metrics['memory_percent']:5.1f}% "
            f"{metrics['memory_used_mib']:.0f} MiB / {metrics['memory_total_mib']:.0f} MiB"
        ),
        (
            "Disk: "
            f"{metrics['disk_percent']:5.1f}% "
            f"{_format_storage(metrics['disk_used'], metrics['disk_total'])}"
        ),
    ]
    return "\n".join(lines)


def _format_metrics(metrics: Dict[str, object]) -> str:
    lines = [
        "Metrics",
        f"Uptime: {metrics['uptime']}",
        f"Processes: {metrics['processes']}",
        f"Load avg: {metrics['load_avg']}",
        f"Net ↑: {_format_rate(float(metrics['net_up']))}",
        f"Net ↓: {_format_rate(float(metrics['net_down']))}",
    ]
    return "\n".join(lines)


def _format_status(metrics: Dict[str, object]) -> str:
    cpu = float(metrics['cpu_percent'])
    if cpu > 85:
        cpu_state = "CPU Status: HIGH"
    elif cpu > 65:
        cpu_state = "CPU Status: MODERATE"
    else:
        cpu_state = "CPU Status: NORMAL"

    lines = [
        "Status",
        cpu_state,
        f"Memory: {metrics['memory_percent']:.1f}%",
        f"Disk: {metrics['disk_percent']:.1f}%",
    ]
    return "\n".join(lines)


def _create_diagram(title: str, static_info: Dict[str, List[Tuple[str, str]]], metrics: Dict[str, object]) -> Diagram:
    diagram = Diagram(
        title,
        horizontal_spacing=2,
        vertical_spacing=2,
        max_box_width=60,
        box_style="square",
        canvas_height=120,
        allow_intersections=False,
    )

    system_node = diagram.add_right(_format_block("System", static_info["System"]))
    system_node.add_bottom(_format_block("Environment", static_info["Environment"]))
    hardware_node = diagram.add_left(_format_hardware(metrics))
    hardware_node.add_bottom(_format_metrics(metrics))
    diagram.add_bottom(_format_status(metrics))
    return diagram


def _collect_dynamic(prev_net, prev_time: float):
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    try:
        net_now = psutil.net_io_counters()
    except Exception:
        net_now = None

    now = perf_counter()
    up_rate = 0.0
    down_rate = 0.0
    if net_now and prev_net:
        interval = max(now - prev_time, 1e-6)
        up_rate = (net_now.bytes_sent - prev_net.bytes_sent) / interval
        down_rate = (net_now.bytes_recv - prev_net.bytes_recv) / interval

    uptime_seconds: float | None = None
    if hasattr(psutil, "boot_time"):
        try:
            uptime_seconds = max(current_time() - psutil.boot_time(), 0.0)
        except Exception:
            uptime_seconds = None
    if uptime_seconds is None:
        uptime_seconds = _get_uptime()

    load_avg = "n/a"
    if hasattr(os, "getloadavg"):
        try:
            load = os.getloadavg()
        except OSError:
            load = None
        if load is not None:
            load_avg = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"

    metrics: Dict[str, object] = {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_mib": _to_mib(memory.used),
        "memory_total_mib": _to_mib(memory.total),
        "disk_percent": disk.percent,
        "disk_used": float(disk.used),
        "disk_total": float(disk.total),
        "net_up": up_rate,
        "net_down": down_rate,
        "uptime": _format_uptime(uptime_seconds),
        "processes": len(psutil.pids()),
        "load_avg": load_avg,
    }

    next_net = net_now if net_now is not None else prev_net

    return metrics, next_net, now


def main() -> None:
    user = os.environ.get("USER") or getpass.getuser()
    host = platform.node() or "unknown-host"
    header = f"{user}@{host}"
    title = f"{header}\n{'-' * len(header)}"

    static_info = gather_info()

    print("Starting Live NeoFetch dashboard...")
    print("Press Ctrl+C to stop.\n")

    psutil.cpu_percent(interval=None)
    try:
        prev_net = psutil.net_io_counters()
    except Exception:
        prev_net = None
    prev_time = perf_counter()

    try:
        with Live(refresh_per_second=2, screen=False) as live:
            while True:
                loop_start = perf_counter()

                metrics, prev_net, prev_time = _collect_dynamic(prev_net, prev_time)

                diagram = _create_diagram(title, static_info, metrics)

                render_start = perf_counter()
                rendered = diagram.render(include_markup=True)
                render_time = (perf_counter() - render_start) * 1000
                loop_time = (perf_counter() - loop_start) * 1000

                panel_text = f"{rendered}\n\nRender: {render_time:.1f} ms | Loop: {loop_time:.1f} ms"
                live.update(panel_text)

                sleep(1)
    except KeyboardInterrupt:
        print("\nStopped live monitoring.")


if __name__ == "__main__":
    main()
