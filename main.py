#!/usr/bin/env python3
"""Alice Assistant - Entry point."""
import sys
import os

# Ensure we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import AliceApp


def main():
    app = AliceApp()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
