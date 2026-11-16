"""Forward the SO-101 live camera page to a local browser over SSH.

Reads the user's existing, ignored autodl-4090.md connection note in memory.
No credential is printed, copied to another file, or passed in command arguments.
Both endpoints bind only to 127.0.0.1.
"""

import argparse
import json
from pathlib import Path
import re
import socket
import socketserver
import threading
import time
import webbrowser

import paramiko


def connection_from_note(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    ssh_line = next(line for line in lines if "ssh -p " in line)
    match = re.search(r"ssh\s+-p\s+(\d+)\s+([^@\s]+)@([\w.-]+)", ssh_line)
    if not match:
        raise ValueError("Connection note has no SSH host and port")
    password_line = next(line for line in lines if line.startswith("密码"))
    password = password_line.partition("：")[2].strip()
    if not password:
        raise ValueError("Connection note has no password")
    return match.group(3), int(match.group(1)), match.group(2), password


def start_or_reuse_teleop(client, remote_port):
    """Start the installed simulator in the background if its HTTP API is absent."""
    url = f"http://127.0.0.1:{remote_port}"

    def probe(path):
        _, stdout, _ = client.exec_command(
            f"curl --silent --max-time 2 {url}{path}", timeout=5)
        raw = stdout.read()
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return None

    current = probe("/status")
    if isinstance(current, dict) and "leader_online" in current:
        print("Remote teleoperation already running.", flush=True)
        return
    if isinstance(probe("/health"), dict):
        raise RuntimeError("Remote port is occupied by the older camera-only viewer. Stop that process first.")

    _, stdout, _ = client.exec_command(
        "ps -eo args | grep '[s]o101_remote_teleop.py' | head -1", timeout=5)
    already_starting = bool(stdout.read().strip())
    if not already_starting:
        # SIGINT gives Python's finally block time to finalize an active episode.
        command = ("nohup timeout --signal=INT --kill-after=120s 1800 bash "
                   "/root/autodl-tmp/isaac-transfer-tools/workshop/run_so101_remote_teleop.sh "
                   "> /root/autodl-tmp/workshop/logs/so101-remote-teleop-current.log "
                   "2>&1 </dev/null & echo $!")
        _, stdout, stderr = client.exec_command(command, timeout=10)
        pid = stdout.read().decode().strip()
        if not pid.isdecimal():
            raise RuntimeError("Could not start the remote teleoperation process")
        print(f"Starting remote SO-101 simulation (PID {pid}); first launch can take a minute.", flush=True)
        stderr.read()
    else:
        print("Waiting for the remote SO-101 simulation to finish starting.", flush=True)

    for _ in range(100):
        status = probe("/status")
        if isinstance(status, dict) and status.get("ready"):
            print("Remote teleoperation ready; cameras are live.", flush=True)
            return
        time.sleep(1)
    raise RuntimeError("Remote simulation did not start within 100 seconds. Check "
                       "/root/autodl-tmp/workshop/logs/so101-remote-teleop-current.log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-note", type=Path,
                        default=Path(__file__).resolve().parents[3] / "autodl-4090.md")
    parser.add_argument("--local-port", type=int, default=8765)
    parser.add_argument("--remote-port", type=int, default=8765)
    parser.add_argument("--start-teleop", action="store_true",
                        help="Start/reuse the remote teleop scene and open its local page")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window")
    args = parser.parse_args()
    host, port, user, password = connection_from_note(args.connection_note)

    client = paramiko.SSHClient()
    client.load_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(host, port=port, username=user, password=password,
                   look_for_keys=False, allow_agent=False, timeout=15)
    transport = client.get_transport()
    transport.set_keepalive(30)
    if args.start_teleop:
        start_or_reuse_teleop(client, args.remote_port)

    class Forward(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                remote = transport.open_channel(
                    "direct-tcpip", ("127.0.0.1", args.remote_port), self.client_address)
            except (OSError, paramiko.SSHException) as exc:
                print(f"Remote viewer unavailable: {type(exc).__name__}", flush=True)
                return
            if remote is None:
                return

            def copy(source, destination):
                try:
                    while True:
                        data = source.recv(65536)
                        if not data:
                            break
                        destination.sendall(data)
                except (OSError, EOFError, paramiko.SSHException):
                    pass
                finally:
                    try:
                        destination.shutdown(socket.SHUT_WR)
                    except (OSError, AttributeError):
                        pass

            upstream = threading.Thread(target=copy, args=(self.request, remote), daemon=True)
            upstream.start()
            copy(remote, self.request)
            remote.close()
            upstream.join(timeout=2)

    class LocalServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        with LocalServer(("127.0.0.1", args.local_port), Forward) as server:
            print(f"Open http://127.0.0.1:{args.local_port} in your browser; Ctrl+C to stop.",
                  flush=True)
            if args.start_teleop and not args.no_browser:
                webbrowser.open_new_tab(f"http://127.0.0.1:{args.local_port}/")
            server.serve_forever(poll_interval=0.25)
    finally:
        client.close()


if __name__ == "__main__":
    main()
