import os
import queue
import signal
import subprocess
import sys
import threading
from typing import List


class MonitorRunner:
    def __init__(self, base_dir: str, monitor_exe_path: str, monitor_script_path: str):
        self.base_dir = base_dir
        self.monitor_exe_path = monitor_exe_path
        self.monitor_script_path = monitor_script_path

        self.process: subprocess.Popen | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _resolve_command(self) -> List[str]:
        if os.path.exists(self.monitor_exe_path):
            return [self.monitor_exe_path]
        if os.path.exists(self.monitor_script_path):
            return [sys.executable, self.monitor_script_path]
        raise FileNotFoundError(
            f"Monitor target not found: {self.monitor_exe_path} or {self.monitor_script_path}"
        )

    def _read_output(self, proc: subprocess.Popen) -> None:
        if proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                self.output_queue.put(line)
        except Exception as exc:
            self.output_queue.put(f"[reader-error] {exc}")

    def start(self) -> subprocess.Popen:
        command = self._resolve_command()

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        self.process = subprocess.Popen(
            command,
            cwd=self.base_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()
        return self.process

    def stop(self) -> bool:
        if self.process is None or self.process.poll() is not None:
            self.process = None
            return False

        proc = self.process
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.wait(timeout=3)
            else:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait(timeout=3)

        self.process = None
        return True

    def poll_exit_code(self) -> int | None:
        if self.process is None:
            return None
        return self.process.poll()

    def drain_output(self) -> List[str]:
        lines: List[str] = []
        while True:
            try:
                lines.append(self.output_queue.get_nowait())
            except queue.Empty:
                break
        return lines
