from asciinode.ascii_diagram import Diagram

diagram = Diagram("A")
node_A = diagram.root
node_B = diagram.add_right("B")
node_C = node_B.add_right("C")
node_D = node_A.add_bottom("D")
node_E = node_B.add_bottom("E")
node_F = node_C.add_bottom("F")
node_G = node_D.add_bottom("G")
node_H = node_E.add_bottom("H")
node_I = node_F.add_bottom("I")

diagram.connect(node_A, node_B)
diagram.connect(node_B, node_C)
diagram.connect(node_D, node_E)
diagram.connect(node_E, node_F)
diagram.connect(node_G, node_H)
diagram.connect(node_H, node_I)

diagram.connect(node_A, node_D)
diagram.connect(node_B, node_E)
diagram.connect(node_C, node_F)
diagram.connect(node_D, node_G)
diagram.connect(node_E, node_H)
diagram.connect(node_F, node_I)

rows = [
  [node_A, node_B, node_C],
  [node_D, node_E, node_F],
  [node_G, node_H, node_I],
]

diagram.use_grid_layout(rows)
print(diagram.render())
