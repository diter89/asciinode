import psutil
from time import perf_counter, sleep, time

from rich.live import Live
from rich.panel import Panel

from asciinode.ascii_diagram import Diagram


def _make_bar(percent: float, width: int = 20) -> str:
    capped = max(0.0, min(100.0, percent))
    filled = int(round((capped / 100.0) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def get_cpu_metrics() -> dict:
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    return {
        "cpu": cpu_percent,
        "memory": memory.percent,
    }


def main():
    print("Starting Simple CPU Monitor...")
    print("Press Ctrl+C to exit\n")

    try:
        net_prev = psutil.net_io_counters()
        time_prev = perf_counter()

        with Live(refresh_per_second=2, screen=False) as live:
            while True:
                loop_start = perf_counter()
                metrics = get_cpu_metrics()

                disk = psutil.disk_usage("/")
                uptime_hours = 0.0
                if hasattr(psutil, "boot_time"):
                    uptime_hours = max(time() - psutil.boot_time(), 0.0) / 3600

                net_now = psutil.net_io_counters()
                now = perf_counter()
                interval = max(now - time_prev, 1e-6)
                up_rate = (net_now.bytes_sent - net_prev.bytes_sent) / interval
                down_rate = (net_now.bytes_recv - net_prev.bytes_recv) / interval
                net_prev = net_now
                time_prev = now

                diagram = Diagram(
                    f"Live System Monitor - CPU: {metrics['cpu']:.1f}% | RAM: {metrics['memory']:.1f}%",
                    vertical_spacing=1,
                    horizontal_spacing=3,
                    # canvas_width=80,
                    # canvas_height=1000,
                    allow_intersections=False,
                )

                system = diagram.add("System Overview")

                cpu_bar = _make_bar(metrics["cpu"])
                mem_bar = _make_bar(metrics["memory"])

                system.add_right(
                    f"CPU\n[green]{cpu_bar}  {metrics['cpu']:.1f}%[/green]"
                ).add_bottom("cpu")
                mem_node = system.add_left(f"RAM\n{mem_bar}  {metrics['memory']:.1f}%")
                mem_node.add_bottom(
                    f"Disk {disk.percent:.1f}%\n{_make_bar(disk.percent)}"
                )

                proc_sample = sum(1 for _ in zip(psutil.process_iter(), range(15)))
                process_node = system.add_bottom(
                    f"Processes (sample) {proc_sample:02d}"
                )
                process_node.add_left(f"Net up {up_rate / 1024:6.1f} KB/s")
                process_node.add_right(f"Net dn {down_rate / 1024:6.1f} KB/s")
                process_node.add_bottom(f"Uptime {uptime_hours:.1f} h")

                if metrics["cpu"] > 80:
                    status_text = "HIGH CPU USAGE"
                elif metrics["cpu"] > 60:
                    status_text = "CPU Moderate"
                else:
                    status_text = "CPU Normal"
                system.add_top(status_text)

                render_start = perf_counter()
                rendered = diagram.render(include_markup=True)
                render_time = (perf_counter() - render_start) * 1000
                loop_time = (perf_counter() - loop_start) * 1000

                live.update(
                    f"{rendered}\n[dim]Render: {render_time:.1f} ms | Loop: {loop_time:.1f} ms[/dim]",
                )
                sleep(1)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped. Goodbye!")


if __name__ == "__main__":
    try:
        main()
    except ImportError:
        print("Error: psutil library required")
        print("Install with: pip install psutil")
