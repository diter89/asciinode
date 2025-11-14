from asciinode.ascii_diagram import Diagram

diagram = Diagram("Service Topology")
api = diagram.add_right("API Gateway")
worker = api.add_bottom("Worker Pool")
store = worker.add_bottom("Data Store")

diagram.connect(api, worker, label="dispatch")
diagram.connect(worker, store, label="persist")

print(diagram.render(include_markup=True))
