import logging
import qrcode
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import windll
from tkinter import scrolledtext, messagebox
from PIL import ImageTk
from flask import Flask, render_template, request, jsonify


def has_access(rule_name):
    try:
        cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return "No rules match" not in result.stdout
    except:
        return False


def get_access(rule_name):
    if windll.shell32.IsUserAnAdmin() == 0:
        windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        try:
            subprocess.run(f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow program="{sys.executable}" enable=yes profile=any', shell=True, capture_output=True)
            messagebox.showinfo("Success", "Access granted to firewall\nplease restart the program")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    sys.exit()


def remove_access(rule_name):
    if windll.shell32.IsUserAnAdmin() == 0:
        if messagebox.askyesno("Remove access", "You need to run as Administrator.\nrun as Administrator?"):
            windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        try:
            subprocess.run(f'netsh advfirewall firewall delete rule name="{rule_name}"', shell=True, capture_output=True)
            messagebox.showinfo("Success", "Access to firewall removed")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    sys.exit()


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 1))
            ip = s.getsockname()[0]
        except:
            ip = "127.0.0.1"
        return ip


class ListHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        server_logs.append(log_entry)
        if len(server_logs) > 100:
            server_logs.pop(0)


server_logs = []
logger = logging.getLogger('werkzeug')
handler = ListHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)

app = Flask(__name__)
chat_messages = []
active_clients = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/join", methods=["POST"])
def join_chat():
    data = request.json
    ip_addr = request.remote_addr
    nickname = data.get("nickname")
    chat_messages.append(f"System: {nickname} ({ip_addr}) joined the chat")
    return jsonify({"status": "ok"})


@app.route("/get_data")
def get_data():
    ip_addr = request.remote_addr
    active_clients[ip_addr] = time.time()
    return jsonify({"messages": chat_messages})


@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.json
    if data and "message" in data:
        ip_addr = int(request.remote_addr.split(".")[-1])
        chat_messages.append(f"{ip_addr} | {"⚠: " if ":" not in data["message"] else ""}{data["message"]}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400


@app.route("/log")
def log():
    log_content = "\n".join(server_logs)
    return f"""
<html>
    <head><title>Server Logs</title></head>
    <body style="background-color: #1a1a1a; color: #00ff00; font-family: monospace; padding: 20px;">
        <h2>Server Logs</h2>
        <pre>{log_content}</pre>
        <script>
            setTimeout(() => {{ location.reload(); }}, 5000);
        </script>
    </body>
</html>
"""


def get_active_ips():
    current_time = time.time()
    active = [ip for ip, last_seen in active_clients.items() if current_time - last_seen < 2.0]
    return active


def qr_code_image(url):
    qroot = tk.Toplevel()
    qroot.title("QR Code")
    qroot.resizable(False, False)
    qr = qrcode.make(url)
    img = ImageTk.PhotoImage(qr)
    qr_label = tk.Label(qroot, image=img)
    qr_label.image = img
    qr_label.pack()


def run_flask():
    global port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", 50050))
        except:
            sock.bind(("0.0.0.0", 0))
        port = sock.getsockname()[1]
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Server Admin Panel")
        self.root.configure(bg="#2b2b2b")
        self.ip_label = tk.Label(self.root, text=f"http://{get_local_ip()}:{port}", bg="#2b2b2b", fg="white")
        self.ip_label.pack()
        self.sidebar = tk.Frame(self.root, bg="#333333", width=100)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)
        tk.Label(self.sidebar, text="Connected", bg="#333333", fg="#4b6eaf", font=("Arial", 10, "bold")).pack(pady=5)
        self.ips_listbox = tk.Listbox(self.sidebar, bg="#1e1e1e", fg="#00ff00", borderwidth=0, highlightthickness=0, width=13)
        self.ips_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.qr_button = tk.Button(self.sidebar, text="Show QR", command=lambda: qr_code_image(f"http://{get_local_ip()}:{port}"), bg="#4b6eaf", fg="white")
        self.qr_button.pack(fill="x", pady=5)
        self.main_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_frame = tk.Frame(self.main_frame, bg="#2b2b2b")
        self.chat_frame.pack(fill="both", expand=True)
        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, bg="#1e1e1e", fg="white", font=("Arial", 10))
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.config(state="disabled")
        self.input_frame = tk.Frame(self.chat_frame, bg="#2b2b2b")
        self.input_frame.pack(fill="x", pady=(10, 0))
        self.msg_entry = tk.Entry(self.input_frame, bg="#3c3f41", fg="white", insertbackground="white")
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.msg_entry.bind("<Return>", lambda e: self.send_as_admin())
        self.remove_btn = tk.Button(self.input_frame, text="Remove Access", command=lambda: remove_access(rule_name), bg="#a34444", fg="white")
        self.remove_btn.pack(side="right")
        self.send_btn = tk.Button(self.input_frame, text="Send", command=self.send_as_admin, bg="#4b6eaf", fg="white")
        self.send_btn.pack(side="right")
        self.update_ui()

    def send_as_admin(self):
        msg = self.msg_entry.get()
        if msg:
            chat_messages.append(f"Admin: {msg}")
            self.msg_entry.delete(0, "end")

    def update_ui(self):
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", "end")
        for msg in chat_messages:
            self.chat_display.insert("end", msg + "\n")
        self.chat_display.yview("end")
        self.chat_display.config(state="disabled")
        self.ips_listbox.delete(0, "end")
        for ip in get_active_ips():
            self.ips_listbox.insert("end", ip)
        self.root.after(1000, self.update_ui)


if __name__ == "__main__":
    rule_name = "LocalChatServer"

    if getattr(sys, 'frozen', False) and not has_access(rule_name):
        get_access(rule_name)

    try:
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    root = tk.Tk()
    gui = ServerGUI(root)
    root.mainloop()
