import argparse
import sys
import time
from rich import print
import nmap

from asciinode.ascii_diagram import Diagram


DEFAULT_TARGET = "127.0.0.1"
DEFAULT_PROFILE = "balanced"


SCAN_PROFILES = {
    "quick": {
        "label": "Quick Surface",
        "description": "Top 50 TCP ports with service detection",
        "tcp_args": "-sS --top-ports 50",
        "udp_args": None,
        "service_detection": True,
        "os_detection": False,
        "vuln_scripts": False,
        "requires_sudo": True,
    },
    "balanced": {
        "label": "Balanced Coverage",
        "description": "SYN scan on top 100 TCP ports plus light UDP sampling",
        "tcp_args": "-sS --top-ports 100",
        "udp_args": "-sU --top-ports 30",
        "service_detection": True,
        "os_detection": True,
        "vuln_scripts": False,
        "requires_sudo": True,
    },
    "full": {
        "label": "Full Insight",
        "description": "Comprehensive TCP/UDP scan with service, OS, and vuln scripts",
        "tcp_args": "-sS -p-",
        "udp_args": "-sU --top-ports 50",
        "service_detection": True,
        "os_detection": True,
        "vuln_scripts": True,
        "requires_sudo": True,
    },
}


class ProfiledNmapDiagram(Diagram):
    def __init__(self, title, *args, **kwargs):
        kwargs.setdefault("connector_style", "[dim]")
        super().__init__(title, *args, **kwargs)


def colorize_status(status: str) -> str:
    lowered = status.lower()
    if any(keyword in lowered for keyword in ("error", "fail", "critical", "down", "aborted")):
        return f"[bold red]{status}[/bold red]"
    if any(keyword in lowered for keyword in ("pending", "waiting", "running", "init")):
        return f"[yellow]{status}[/yellow]"
    if any(keyword in lowered for keyword in ("skip", "disabled", "no")):
        return f"[cyan]{status}[/cyan]"
    if any(keyword in lowered for keyword in ("completed", "selected", "up", "ok", "finished", "found")):
        return f"[bold green]{status}[/bold green]"
    return f"[white]{status}[/white]"


def set_node_state(node, title: str, status: str, action: str | None = None) -> None:
    node._title = title
    node._action = action
    node._status = status
    lines = [f"[bold]{title}[/bold]"]
    if action:
        lines.append(f"[dim]Action:[/dim] {action}")
    lines.append(f"Status: {colorize_status(status)}")
    node.text = "\n".join(lines)


def get_node_title(node) -> str:
    if hasattr(node, "_title"):
        return node._title
    text = getattr(node, "text", "") or ""
    return text.split("\n", 1)[0]


def build_summary_nodes(
    report_node,
    target_ip: str,
    host_state: str,
    tcp_ports: list[int],
    udp_ports: list[int],
    os_matches: list[dict],
    hostscripts: list[dict],
    scanner: nmap.PortScanner,
):
    summary = report_node.add_bottom("Scan Summary")
    summary.text = "\n".join(
        [
            "[bold underline]Scan Summary[/bold underline]",
            f"Status: {colorize_status('Completed')}",
        ]
    )

    host_node = summary.add_bottom("Host State")
    host_node.text = "\n".join(
        [
            "[bold]Host State[/bold]",
            f"Target: {target_ip}",
            f"Status: {colorize_status(host_state.upper())}",
        ]
    )

    tcp_node = summary.add_right("Open TCP Ports")
    tcp_lines = ["[bold]Open TCP Ports[/bold]"]
    tcp_data = scanner[target_ip].get("tcp", {}) if target_ip in scanner.all_hosts() else {}
    if tcp_ports:
        for port in tcp_ports[:6]:
            details = tcp_data.get(port, {})
            service = details.get("name", "?")
            product = details.get("product")
            version = details.get("version")
            banner = " ".join(filter(None, [product, version]))
            if banner:
                service = f"{service} ({banner})"
            state = colorize_status(details.get("state", "open"))
            tcp_lines.append(f"{port}/tcp • {service} • {state}")
        if len(tcp_ports) > 6:
            tcp_lines.append(f"… +{len(tcp_ports) - 6} more")
    else:
        tcp_lines.append(f"Status: {colorize_status('No open ports')}")
    tcp_node.text = "\n".join(tcp_lines)

    udp_node = summary.add_left("Open UDP Ports")
    udp_lines = ["[bold]Open UDP Ports[/bold]"]
    udp_data = scanner[target_ip].get("udp", {}) if target_ip in scanner.all_hosts() else {}
    if udp_ports:
        for port in udp_ports[:6]:
            details = udp_data.get(port, {})
            service = details.get("name", "?")
            state = colorize_status(details.get("state", "open"))
            udp_lines.append(f"{port}/udp • {service} • {state}")
        if len(udp_ports) > 6:
            udp_lines.append(f"… +{len(udp_ports) - 6} more")
    else:
        udp_lines.append(f"Status: {colorize_status('No open ports')}")
    udp_node.text = "\n".join(udp_lines)

    os_node = summary.add_bottom("OS Matches")
    os_lines = ["[bold]OS Guesses[/bold]"]
    if os_matches:
        for match in os_matches[:3]:
            name = match.get("name", "Unknown")
            accuracy = match.get("accuracy", "?")
            os_lines.append(f"{name} ({accuracy}%)")
        if len(os_matches) > 3:
            os_lines.append(f"… +{len(os_matches) - 3} more")
    else:
        os_lines.append(f"Status: {colorize_status('No OS fingerprint data')}")
    os_node.text = "\n".join(os_lines)

    vuln_node = os_node.add_bottom("Vulnerability Scripts")
    vuln_lines = ["[bold]Vulnerability Scripts[/bold]"]
    if hostscripts:
        for script in hostscripts[:3]:
            output = (script.get("output") or "").splitlines()
            first_line = output[0] if output else "Result available"
            vuln_lines.append(f"[yellow]{script.get('id', 'nse')}[/yellow]: {first_line[:80]}")
        if len(hostscripts) > 3:
            vuln_lines.append(f"… +{len(hostscripts) - 3} more")
    else:
        vuln_lines.append(f"Status: {colorize_status('No vulnerability script findings')}")
    vuln_node.text = "\n".join(vuln_lines)


def create_profile_diagram(target_ip: str, profile: dict):
    diagram = ProfiledNmapDiagram(
        f"Nmap Profile Flow ({target_ip}) - {profile['label']}",
        max_layout_width=110,
    )

    start = diagram.add("Initialize Scanner")
    profile_node = start.add_bottom("Select Profile")
    discovery = profile_node.add_bottom("Host Discovery (-sn)")
    tcp_scan = discovery.add_right("TCP Scan")
    udp_scan = discovery.add_left("UDP Scan")
    service = discovery.add_bottom("Service Detection (-sV)")
    os_detect = service.add_bottom("OS Detection (-O)")
    vuln = os_detect.add_bottom("Vuln Scripts (--script vuln)")
    report = vuln.add_bottom("Final Report")

    set_node_state(start, "Initialize Scanner", "Pending...", "Setup PortScanner")
    set_node_state(
        profile_node,
        f"Profile: {profile['label']}",
        "Pending...",
        profile["description"],
    )
    set_node_state(discovery, "Host Discovery (-sn)", "Pending...", "Ping sweep")
    set_node_state(
        tcp_scan,
        "TCP Scan",
        "Pending...",
        profile["tcp_args"] or "Disabled",
    )
    set_node_state(
        udp_scan,
        "UDP Scan",
        "Pending...",
        profile["udp_args"] or "Disabled",
    )
    set_node_state(
        service,
        "Service Detection (-sV)",
        "Pending...",
        "Fingerprint services" if profile["service_detection"] else "Disabled",
    )
    set_node_state(
        os_detect,
        "OS Detection (-O)",
        "Pending...",
        "Match host OS" if profile["os_detection"] else "Disabled",
    )
    set_node_state(
        vuln,
        "Vuln Scripts (--script vuln)",
        "Pending...",
        "Run vulnerability NSE" if profile["vuln_scripts"] else "Disabled",
    )
    set_node_state(report, "Final Report", "Pending...", "Aggregate findings")

    nodes = {
        "start": start,
        "profile": profile_node,
        "discovery": discovery,
        "tcp": tcp_scan,
        "udp": udp_scan,
        "service": service,
        "os": os_detect,
        "vuln": vuln,
        "report": report,
    }

    return diagram, nodes


def extract_open_ports(port_data: dict) -> list[int]:
    if not port_data:
        return []
    return sorted(
        port for port, details in port_data.items() if details.get("state") == "open"
    )


def run_profile_scan(target_ip: str, profile_name: str):
    profile = SCAN_PROFILES.get(profile_name)
    if not profile:
        raise ValueError(f"Unknown profile '{profile_name}'. Available: {', '.join(SCAN_PROFILES)}")

    diagram, nodes = create_profile_diagram(target_ip, profile)
    scanner = nmap.PortScanner()

    tcp_ports: list[int] = []
    udp_ports: list[int] = []
    host_up = False
    host_state = "unknown"
    scan_successful = False
    hostscripts: list[dict] = []
    os_matches: list[dict] = []

    print("\n" + "=" * 60)
    print(f"--- [INFO] Starting '{profile['label']}' scan for {target_ip} ---")
    print("=" * 60)

    try:
        set_node_state(nodes["start"], "Initialize Scanner", "OK", "Setup PortScanner")
        set_node_state(
            nodes["profile"],
            f"Profile: {profile['label']}",
            "Selected",
            profile["description"],
        )

        # Host discovery
        set_node_state(nodes["discovery"], "Host Discovery (-sn)", "Running", "Ping sweep")
        scanner.scan(target_ip, arguments="-sn", sudo=profile["requires_sudo"])

        if target_ip not in scanner.all_hosts() or scanner[target_ip].state() != "up":
            set_node_state(nodes["discovery"], "Host Discovery (-sn)", "Host down", "Ping sweep")
            for key in ("tcp", "udp", "service", "os", "vuln"):
                set_node_state(nodes[key], get_node_title(nodes[key]), "Skipped", "Host unreachable")
            set_node_state(nodes["report"], "Final Report", "Aborted", "Aggregate findings")
            print(f"[ERROR] Target {target_ip} is unreachable. Aborting scan.")
            return

        host_up = True
        host_state = scanner[target_ip].state()
        set_node_state(nodes["discovery"], "Host Discovery (-sn)", "Completed", "Ping sweep")
        print("[1/5] Host is up.")

        # TCP scan
        if profile["tcp_args"]:
            set_node_state(nodes["tcp"], "TCP Scan", "Running", profile["tcp_args"])
            scanner.scan(target_ip, arguments=profile["tcp_args"], sudo=profile["requires_sudo"])
            tcp_ports = extract_open_ports(scanner[target_ip].get("tcp")) if target_ip in scanner.all_hosts() else []
            status = "Completed" if tcp_ports else "Completed (no open TCP ports)"
            set_node_state(nodes["tcp"], "TCP Scan", status, profile["tcp_args"])
            print("[2/5] TCP scan finished.")
        else:
            set_node_state(nodes["tcp"], "TCP Scan", "Disabled", "Profile setting")

        # UDP scan
        if profile["udp_args"]:
            set_node_state(nodes["udp"], "UDP Scan", "Running", profile["udp_args"])
            scanner.scan(target_ip, arguments=profile["udp_args"], sudo=profile["requires_sudo"])
            udp_ports = extract_open_ports(scanner[target_ip].get("udp")) if target_ip in scanner.all_hosts() else []
            status = "Completed" if udp_ports else "Completed (no open UDP ports)"
            set_node_state(nodes["udp"], "UDP Scan", status, profile["udp_args"])
            print("[3/5] UDP scan finished.")
        else:
            set_node_state(nodes["udp"], "UDP Scan", "Disabled", "Profile setting")

        # Service detection
        if profile["service_detection"]:
            combined_ports = sorted(set(tcp_ports + udp_ports))
            if combined_ports:
                port_arg = ",".join(map(str, combined_ports))
                set_node_state(nodes["service"], "Service Detection (-sV)", "Running", "Fingerprint services")
                scanner.scan(
                    target_ip,
                    arguments=f"-sV -p {port_arg}",
                    sudo=profile["requires_sudo"],
                )
                set_node_state(nodes["service"], "Service Detection (-sV)", "Completed", "Fingerprint services")
                print("[4/5] Service detection finished.")
            else:
                set_node_state(
                    nodes["service"],
                    "Service Detection (-sV)",
                    "Skipped (no open ports)",
                    "Fingerprint services",
                )
        else:
            set_node_state(nodes["service"], "Service Detection (-sV)", "Disabled", "Profile setting")

        # OS detection
        if profile["os_detection"]:
            set_node_state(nodes["os"], "OS Detection (-O)", "Running", "Match host OS")
            scanner.scan(target_ip, arguments="-O", sudo=profile["requires_sudo"])
            os_matches = scanner[target_ip].get("osmatch", []) if target_ip in scanner.all_hosts() else []
            status = "Completed" if os_matches else "Completed (no OS match)"
            set_node_state(nodes["os"], "OS Detection (-O)", status, "Match host OS")
        else:
            set_node_state(nodes["os"], "OS Detection (-O)", "Disabled", "Profile setting")

        # Vulnerability scripts
        if profile["vuln_scripts"]:
            combined_ports = sorted(set(tcp_ports + udp_ports))
            if combined_ports:
                port_arg = ",".join(map(str, combined_ports))
                set_node_state(nodes["vuln"], "Vuln Scripts (--script vuln)", "Running", "Run vulnerability NSE")
                scanner.scan(
                    target_ip,
                    arguments=f"--script vuln -sV -p {port_arg}",
                    sudo=profile["requires_sudo"],
                )
                hostscripts = scanner[target_ip].get("hostscript", []) if target_ip in scanner.all_hosts() else []
                status = "Completed" if hostscripts else "Completed (no findings)"
                set_node_state(nodes["vuln"], "Vuln Scripts (--script vuln)", status, "Run vulnerability NSE")
            else:
                set_node_state(
                    nodes["vuln"],
                    "Vuln Scripts (--script vuln)",
                    "Skipped (no open ports)",
                    "Run vulnerability NSE",
                )
        else:
            set_node_state(nodes["vuln"], "Vuln Scripts (--script vuln)", "Disabled", "Profile setting")

        scan_successful = True

    except nmap.PortScannerError as exc:
        set_node_state(nodes["start"], "Initialize Scanner", f"Nmap error: {exc}", "Setup PortScanner")
        set_node_state(nodes["report"], "Final Report", "Aborted", "Aggregate findings")
        print(f"\n[CRITICAL] Nmap failed: {exc}")
    except Exception as exc:
        set_node_state(nodes["start"], "Initialize Scanner", f"Unexpected error: {exc}", "Setup PortScanner")
        set_node_state(nodes["report"], "Final Report", "Aborted", "Aggregate findings")
        print(f"\n[CRITICAL] Unexpected exception: {exc}")
    else:
        if scan_successful and host_up:
            set_node_state(nodes["report"], "Final Report", "Completed", "Aggregate findings")
            if target_ip in scanner.all_hosts():
                host_state = scanner[target_ip].state()
            build_summary_nodes(
                nodes["report"],
                target_ip,
                host_state,
                tcp_ports,
                udp_ports,
                os_matches,
                hostscripts,
                scanner,
            )

    print("--- [SUMMARY] Diagram ---")
    print(diagram.render(include_markup=True))
    if not scan_successful or not host_up:
        return

    host_state = scanner[target_ip].state() if target_ip in scanner.all_hosts() else "unknown"
    print(f"Host State: {host_state}")

    if tcp_ports:
        print("\nOpen TCP Ports:")
        for port in tcp_ports:
            details = scanner[target_ip]["tcp"][port]
            service = details.get("name", "?")
            product = details.get("product")
            version = details.get("version")
            extra = " ".join(filter(None, [product, version]))
            extra = f" ({extra})" if extra else ""
            print(f"  {port}/tcp: {details.get('state', '?')} - {service}{extra}")
    else:
        print("\nNo open TCP ports detected.")

    if udp_ports:
        print("\nOpen UDP Ports:")
        for port in udp_ports:
            details = scanner[target_ip]["udp"][port]
            service = details.get("name", "?")
            print(f"  {port}/udp: {details.get('state', '?')} - {service}")
    else:
        print("\nNo open UDP ports detected.")

    if os_matches:
        print("\nOS Matches:")
        for match in os_matches[:5]:
            name = match.get("name", "Unknown")
            accuracy = match.get("accuracy")
            device = match.get("osclass", [])
            cpes = []
            for cls in device:
                cpes.extend(cls.get("cpe", []))
            cpe_str = f" CPE: {', '.join(cpes)}" if cpes else ""
            print(f"  - {name} (accuracy {accuracy}%) {cpe_str}")
    else:
        print("\nNo OS fingerprint data.")

    if hostscripts:
        print("\nVulnerability Script Findings:")
        for script in hostscripts:
            print(f"  [{script.get('id')}] {script.get('output')}")
    else:
        if profile["vuln_scripts"]:
            print("\nNo vulnerability script findings.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nmap profile scanner with ASCIINODE visualization")
    parser.add_argument("target", nargs="?", default=DEFAULT_TARGET, help="Target IP or hostname")
    parser.add_argument(
        "--profile",
        choices=list(SCAN_PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help="Scan profile to use",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Optional delay before starting the scan (seconds)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    if args.sleep > 0:
        time.sleep(args.sleep)
    run_profile_scan(args.target, args.profile)


if __name__ == "__main__":
    main()
