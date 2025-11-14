from asciinode.ascii_diagram import Diagram
from rich import print

def build_network() -> Diagram:
    diagram = Diagram(
        "✦ [bold cyan]Services Overview[/bold cyan]",
        horizontal_spacing=8,
        vertical_spacing=5,
        max_box_width=40,
        canvas_width=500,
        canvas_height=150,
        box_style="square",
    )

    api_tier = diagram.add_right("▲ [bold red]API Tier[/bold red]")
    data_flow = diagram.add_bottom("◆ [bold magenta]Data Flow[/bold magenta]")
    operations = diagram.add_left("☑ [bold green]Operations[/bold green]")

    api_gateway = api_tier.add_bottom("▶ [bold]API Gateway[/bold]")
    cache_cluster = api_gateway.add_bottom("◼ Cache Cluster")
    auth_service = cache_cluster.add_bottom("✚ Auth Service")
    billing_service = auth_service.add_bottom("⊕ Billing Service")
    reports_portal = billing_service.add_bottom("▣ Reporting Portal")

    queue = data_flow.add_bottom("☰ Message Queue")
    workers = queue.add_bottom("⚙ Worker Pool")
    analytics = workers.add_bottom("▦ Analytics Engine")
    scheduler = analytics.add_bottom("⟳ Scheduler")

    monitoring = operations.add_bottom("◉ Monitoring")
    audit_logs = monitoring.add_bottom("☷ Audit Logs")

    diagram.connect(api_gateway, queue, label="➤ [cyan]enqueue jobs[/cyan]")
    diagram.connect(cache_cluster, workers, label="☄ [yellow]prefetch cache[/yellow]")
    diagram.connect(auth_service, queue, label="↻ [green]token refresh[/green]")
    diagram.connect(analytics, reports_portal, label="✹ [magenta]raw metrics[/magenta]", bidirectional=True)
    diagram.connect(scheduler, cache_cluster, label="✖ [red]purge cache[/red]")
    diagram.connect(monitoring, reports_portal, label="✎ [blue]report status[/blue]")
    diagram.connect(audit_logs, billing_service, label="✺ [bold]monthly audit[/bold]")

    return diagram


def main() -> None:
    diagram = build_network()
    print(diagram.render(include_markup=True))


if __name__ == "__main__":
    main()
