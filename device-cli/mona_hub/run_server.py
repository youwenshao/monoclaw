"""Launcher that creates a SO_REUSEADDR socket and hands it to uvicorn.

This solves the TIME_WAIT bind failure that occurs when launchd restarts
the server after a crash or macOS sleep/Jetsam kill.  By pre-creating
the socket with SO_REUSEADDR, the new process can bind immediately even
if the old socket is still in TIME_WAIT.
"""

import os
import socket
import subprocess
import sys

HOST = os.environ.get("MONA_HOST", "127.0.0.1")
PORT = int(os.environ.get("MONA_PORT", "8000"))


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    sock.bind((HOST, PORT))
    sock.listen(128)

    fd = sock.fileno()
    os.set_inheritable(fd, True)

    os.execvp(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--fd", str(fd)],
    )


if __name__ == "__main__":
    main()
