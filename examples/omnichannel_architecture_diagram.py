from asciinode.ascii_diagram import Diagram as BaseDiagram
from rich import print
from rich.panel import Panel


class Diagram(BaseDiagram):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("connector_style", "[#0a7201 bold]")
        super().__init__(*args, **kwargs)


diagram = Diagram("OmniChannel Architecture (Chained)", allow_intersections=True)

mobile_net = diagram.add("Mobile Provider Network")
device = mobile_net.add_bottom("Device")
browser = device.add_bottom("Browser")

device.add_right("Edge Services") \
    .add_right("Push Notifications") \
    .add_right("Device Analytics") \
    .add_right("Device Security Management") \
    .add_right("Service Discovery & Configuration")

gateway = device.add_right("Gateway")
gateway.add_bottom("Identity Provider").add_bottom("Content Management")

gateway.add_right("Mobile Backend for Frontend 1") \
    .add_right("Proxy 1") \
    .add_right("Reusable Microservices 1") \
    .add_bottom("Reusable Microservices 2")

transform = gateway.add_right("Mobile Backend for Frontend 1") \
    .add_right("Proxy 1") \
    .add_right("Reusable Microservices 1") \
    .add_right("Transformation & Connectivity")

transform.add_top("Enterprise User Directory")
transform.add_right("Device Applications")
transform.add_bottom("Enterprise Data")

gateway.add_right("Mobile Backend for Frontend 2").add_right("Proxy 2")

gateway.add_right("Mobile Backend for Frontend 3") \
    .add_right("Data Store") \
    .add_bottom("Caches")

gateway.add_right("Mobile Backend for Frontend 4").add_right("File Repository")

print(Panel(diagram.render(include_markup=True), border_style="magenta"))
