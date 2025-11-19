from asciinode.ascii_diagram import Diagram


def main() -> None:
    diagram = Diagram("Root")

    # Build a simple tree
    child = diagram.add_right("Child")
    child.add_bottom("Grandchild")

    # Validate the healthy diagram (no issues expected)
    print("Initial validation:")
    print(diagram.validate())

    # Introduce an intentional structural issue
    child.parent = None

    print("After corrupting parent reference:")
    print(diagram.validate())


if __name__ == "__main__":
    main()
