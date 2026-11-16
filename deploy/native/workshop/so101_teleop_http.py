"""Loopback-only MJPEG viewer and validated SO-101 teleoperation mailbox.

The simulator owns the scene and consumes this mailbox on its main thread. HTTP
threads never touch Isaac Sim or LeRobot objects. Use an SSH tunnel to reach it.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import threading
import time


JOINTS = (
    "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
    "wrist_flex.pos", "wrist_roll.pos", "gripper.pos",
)


class TeleopState:
    def __init__(self, dataset_root, allow_mock_recording=False):
        self.cond = threading.Condition()
        self.jpeg = None
        self.frame_seq = 0
        self.frame_at = None
        self.closed = False
        self.action = None
        self.action_seq = -1
        self.action_source = None
        self.action_at = None
        self.armed = False
        self.pending = []
        self.next_control_id = 0
        self.last_control_id = 0
        self.last_control_result = None
        self.recording = False
        self.saving = False
        self.episodes = 0
        self.frames = 0
        self.error = None
        self.dataset_root = str(dataset_root)
        self.allow_mock_recording = allow_mock_recording

    def publish(self, jpeg):
        with self.cond:
            self.jpeg = jpeg
            self.frame_seq += 1
            self.frame_at = time.monotonic()
            self.cond.notify_all()

    def next_frame(self, seq, timeout=5):
        with self.cond:
            self.cond.wait_for(lambda: self.frame_seq > seq or self.closed, timeout)
            return self.frame_seq, self.jpeg, self.closed

    def status(self):
        with self.cond:
            now = time.monotonic()
            age = now - self.action_at if self.action_at is not None else None
            return {
                "ready": self.jpeg is not None and not self.closed,
                "frame_seq": self.frame_seq,
                "frame_age_seconds": round(now - self.frame_at, 2) if self.frame_at else None,
                "action_age_seconds": round(age, 2) if age is not None else None,
                "leader_online": age is not None and age < 0.8 and self.action_source == "leader",
                "armed": (self.armed and age is not None and age < 0.8
                          and (self.action_source == "leader" or self.allow_mock_recording)),
                "source": self.action_source,
                "recording": self.recording,
                "saving": self.saving,
                "frames_recorded": self.frames,
                "episodes_saved": self.episodes,
                "dataset_root": self.dataset_root,
                "error": self.error,
                "last_control_id": self.last_control_id,
                "last_control_result": self.last_control_result,
            }

    def set_action(self, message):
        if not isinstance(message, dict) or message.get("source") not in ("leader", "mock"):
            raise ValueError("source must be leader or mock")
        seq = message.get("seq")
        if type(seq) is not int or seq < 0:
            raise ValueError("seq must be a nonnegative integer")
        action = message.get("action")
        if not isinstance(action, dict) or set(action) != set(JOINTS):
            raise ValueError("action must contain exactly the six SO-101 joints")
        values = {}
        for name in JOINTS:
            raw = action[name]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{name} must be numeric")
            value = float(raw)
            lower = 0 if name == "gripper.pos" else -100
            if not math.isfinite(value) or not lower <= value <= 100:
                raise ValueError(f"{name} is outside its calibrated range")
            values[name] = value
        with self.cond:
            if self.recording and message["source"] == "mock" and not self.allow_mock_recording:
                raise ValueError("Mock input is blocked during a real episode")
            if (self.action_source == message["source"] and self.action_at is not None
                    and time.monotonic() - self.action_at < 1.0 and seq <= self.action_seq):
                raise ValueError("out-of-order action sequence")
            self.action = values
            self.action_seq = seq
            self.action_source = message["source"]
            self.action_at = time.monotonic()

    def latest_action(self):
        with self.cond:
            age = time.monotonic() - self.action_at if self.action_at else None
            if age is None or age >= 0.8:
                return None, self.action_source
            return self.action.copy(), self.action_source

    def enqueue(self, command):
        if command not in ("start", "stop", "discard", "reset"):
            raise ValueError("unknown control command")
        with self.cond:
            if self.closed:
                raise RuntimeError("Simulation has stopped")
            if command == "reset":
                raise RuntimeError("场景重置暂不可用：本次 env.reset() 导致仿真退出；当前不会重置或自动保存，若正在录制请单独点击保存本回合")
            age = time.monotonic() - self.action_at if self.action_at else None
            if command == "start":
                if self.recording or any(item[1] == "start" for item in self.pending):
                    raise RuntimeError("An episode is already recording")
                if self.saving:
                    raise RuntimeError("Wait for the current episode to finish saving")
                if age is None or age >= 0.8:
                    raise RuntimeError("Connect and move the leader before recording")
                if not self.armed:
                    raise RuntimeError("Wait for the initial pose transition to finish")
                if self.action_source != "leader" and not self.allow_mock_recording:
                    raise RuntimeError("Mock input cannot enter the real training dataset")
            elif not self.recording and not any(item[1] == "start" for item in self.pending):
                raise RuntimeError("没有正在录制的回合；请先点击开始录制")
            self.next_control_id += 1
            self.pending.append((self.next_control_id, command))
            return self.next_control_id

    def finish_control(self, control_id, result, error=False):
        with self.cond:
            self.last_control_id = control_id
            self.last_control_result = result
            self.error = result if error else None

    def drain_controls(self):
        with self.cond:
            commands, self.pending = self.pending, []
            return commands

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not self.path.startswith("/action") and not self.path.startswith("/status"):
                print("TELEOP_HTTP", fmt % args, flush=True)

        def respond_json(self, code, value):
            data = json.dumps(value, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if host not in (f"127.0.0.1:{self.server.server_port}",
                            f"localhost:{self.server.server_port}"):
                self.send_error(403, "Use the loopback SSH tunnel")
                return
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}",
                                         f"http://localhost:{self.server.server_port}"):
                self.send_error(403, "Foreign browser origin")
                return
            if self.headers.get_content_type() != "application/json":
                self.send_error(415, "JSON required")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400, "Invalid body length")
                return
            if not 0 < length <= 4096:
                self.send_error(413, "Invalid body size")
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if self.path == "/action":
                    state.set_action(payload)
                elif self.path == "/control":
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a JSON object")
                    control_id = state.enqueue(payload.get("command"))
                else:
                    self.send_error(404)
                    return
            except (ValueError, TypeError) as exc:
                self.respond_json(422, {"error": str(exc)})
                return
            except RuntimeError as exc:
                self.respond_json(409, {"error": str(exc)})
                return
            reply = {"accepted": True}
            if self.path == "/control":
                reply["control_id"] = control_id
            self.respond_json(202, reply)

        def do_GET(self):
            if self.path in ("/health", "/status"):
                self.respond_json(200, state.status())
                return
            if self.path == "/":
                html = """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>SO-101 遥操作</title>
<style>body{background:#171b22;color:#eee;font:16px system-ui;margin:20px}
img{max-width:100%;border:1px solid #555}button{padding:9px;margin-right:8px}
pre{white-space:pre-wrap}small{color:#aaa}</style>
<h2>SO-101 · Isaac Sim 实时遥操作</h2>
<p>左：外部相机 D455；右：腕部相机。通过本地 SSH 隧道查看与控制。</p>
<img src="/stream.mjpg" alt="双视角实时画面"><p id="state">等待仿真启动…</p>
<button onclick="send('start')">开始录制</button>
<button onclick="send('stop')">保存本回合</button>
<button onclick="send('discard')">丢弃本回合</button>
<button onclick="send('reset')">重置场景</button>
<pre id="message"></pre><small>录制保存在服务器数据盘，不会上传到 Hugging Face。</small>
<script>
let controlPending=false;
async function send(command) {
  if(controlPending) return;
  controlPending=true;
  const message=document.getElementById('message');
  try {
    const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({command})});
    const x=await r.json();
    if(!r.ok) {message.textContent='无法执行：'+x.error;return;}
    message.textContent='正在执行：'+command;
    for(let attempt=0;attempt<240;attempt++) {
      await new Promise(resolve=>setTimeout(resolve,500));
      const status=await (await fetch('/status',{cache:'no-store'})).json();
      if(status.last_control_id>=x.control_id) {
        message.textContent=status.last_control_result;
        return;
      }
    }
    message.textContent='操作未在两分钟内确认，请查看仿真日志与状态';
  } catch(e) {message.textContent='连接已中断，请查看仿真日志：'+String(e);}
  finally {controlPending=false;}
}
async function refresh() {
  try {const x=await (await fetch('/status',{cache:'no-store'})).json();
    document.getElementById('state').textContent='主臂: '+(x.leader_online?'已连接':
      (x.source==='mock'?'仅模拟测试':'未连接/动作已超时'))+
      ' | 可录制 '+(x.armed?'是':'否')+' | 画面帧 '+x.frame_seq+
      ' | 当前录制 '+(x.recording?x.frames_recorded+' 帧':'否')+
      ' | 保存中 '+(x.saving?'是':'否')+' | 已保存 '+x.episodes_saved+' 回合'+
      (x.error?' | 错误: '+x.error:'');
  } catch(e) {document.getElementById('state').textContent='连接中断：'+String(e);}
}
setInterval(refresh,1000);refresh();
</script></html>""".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(html)
                return
            if self.path == "/frame.jpg":
                _, jpeg, _ = state.next_frame(0)
                if jpeg is None:
                    self.send_error(503, "Cameras are starting")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpeg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(jpeg)
                return
            if self.path != "/stream.mjpg":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = 0
            try:
                while True:
                    seq, jpeg, closed = state.next_frame(last)
                    if closed:
                        break
                    if jpeg is None or seq == last:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                                     + jpeg + b"\r\n")
                    self.wfile.flush()
                    last = seq
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass

    return Handler


def start_server(state, port):
    class HTTPServer(ThreadingHTTPServer):
        daemon_threads = True

    server = HTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
