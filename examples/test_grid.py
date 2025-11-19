from asciinode.ascii_diagram import Diagram

diagram = Diagram("Grid 10x10")


grid = [[None for _ in range(10)] for _ in range(10)]


for r in range(10):
    for c in range(10):
        label = f"{chr(65 + r)}{c + 1}"  # A1 A2 ... A10, B1 B2 ...
        if r == 0 and c == 0:
            grid[r][c] = diagram.root
            grid[r][c].text = label
        else:
            if c > 0:
                grid[r][c] = grid[r][c - 1].add_right(label)
            else:
                grid[r][c] = grid[r - 1][c].add_bottom(label)


for r in range(10):
    for c in range(9):
        diagram.connect(grid[r][c], grid[r][c + 1])


for r in range(9):
    for c in range(10):
        diagram.connect(grid[r][c], grid[r + 1][c])


diagram.use_grid_layout(grid)


print(diagram.render(include_markup=True))
