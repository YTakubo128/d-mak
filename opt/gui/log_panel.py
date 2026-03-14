from datetime import datetime
import tkinter as tk
from tkinter import ttk


class LogPanel:
    def __init__(self, parent, max_lines: int = 300):
        self.max_lines = max_lines

        scrollbar = ttk.Scrollbar(parent, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            parent,
            height=10,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            yscrollcommand=scrollbar.set,
            state="disabled",
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.log_text.yview)

    def append(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\\n"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)

        total_lines = int(self.log_text.index("end-1c").split(".")[0])
        if total_lines > self.max_lines:
            delete_until = f"{total_lines - self.max_lines + 1}.0"
            self.log_text.delete("1.0", delete_until)

        self.log_text.see("end")
        self.log_text.configure(state="disabled")
