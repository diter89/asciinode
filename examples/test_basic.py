from asciinode.ascii_diagram import Diagram, Position
from rich import print


mock = "tcp open 22 open"


diagram = Diagram("...",vertical_spacing=6)

cabang = diagram.add_right(f"{mock}",llm_answer=True,llm_system_prompt="kamu adalah ahli dalam menganalisis kerentanan tugas kamu adalah menganisis dan gunakan bahasa profesional")
cabang1 = diagram.add_left("what is btc",llm_answer=True)
#gabung  = diagram.connect(cabang,cabang1,style="[green]",label="gabung")


print(diagram.render(include_markup=True))
