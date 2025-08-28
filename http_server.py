#!/usr/bin/env python3
"""
MuSync HTTP Server Runner
"""

from app.interfaces.http import HTTPServer


def main():
    """Run the HTTP server."""
    server = HTTPServer(
        host='localhost',
        port=3000,
        debug=True
    )
    server.run()


if __name__ == '__main__':
    main()
