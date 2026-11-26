"""ECM Launcher entry point."""
import sys

from ecm.ui.app import App


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
