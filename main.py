import json
import logging
import qrcode
import socket
import subprocess
import sys
import threading
import time
from ctypes import windll
from tkinter import messagebox
from PIL import Image
from flask import Flask, render_template, request, jsonify, Response
import customtkinter as ctk


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
logger = logging.getLogger("werkzeug")
handler = ListHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
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


def message_generator(ip_addr):
    last_count = 0
    while True:
        active_clients[ip_addr] = time.time()
        if len(chat_messages) > last_count:
            last_count = len(chat_messages)
            json_data = json.dumps({"messages": chat_messages})
            yield f"data: {json_data}\n\n"
        time.sleep(0.2)


@app.route("/stream")
def stream():
    ip_addr = request.remote_addr
    return Response(message_generator(ip_addr), mimetype="text/event-stream")


@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.json
    if data and "message" in data:
        ip_addr = int(request.remote_addr.split(".")[-1])
        chat_messages.append(f"{ip_addr} | {'⚠: ' if ':' not in data['message'] else ''}{data['message']}")
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
    active = [ip for ip, last_seen in active_clients.items() if current_time - last_seen < 4.0]
    return active


def qr_code_image(url):
    qroot = ctk.CTkToplevel()
    qroot.title("QR Code")
    qroot.resizable(False, False)
    qr_pil_img = qrcode.make(url).get_image()
    qr_ctk_img = ctk.CTkImage(light_image=qr_pil_img, dark_image=qr_pil_img, size=(qr_pil_img.width, qr_pil_img.height))
    qr_label = ctk.CTkLabel(qroot, image=qr_ctk_img, text="")
    qr_label.pack()


def run_flask():
    global port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", 50050))
        except:
            sock.bind(("0.0.0.0", 0))
        port = sock.getsockname()[1]
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


class ServerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Chat Server Admin Panel")
        self.geometry("800x500")
        self.ip_label = ctk.CTkLabel(self, text=f"http://{get_local_ip()}:{port}")
        self.ip_label.pack(pady=5)
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self.main_frame, width=100)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)
        ctk.CTkLabel(self.sidebar, text="Connected").pack(pady=5)
        self.connected_ips_label = ctk.CTkLabel(self.sidebar, text="", fg_color="grey10", text_color="#00ff00", justify="left")
        self.connected_ips_label.pack(fill="both", expand=True, padx=5, pady=5)
        self.qr_button = ctk.CTkButton(self.sidebar, text="Show QR", command=lambda: qr_code_image(f"http://{get_local_ip()}:{port}"))
        self.qr_button.pack(fill="x", pady=5, padx=5)
        self.chat_frame = ctk.CTkFrame(self.main_frame)
        self.chat_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_display = ctk.CTkTextbox(self.chat_frame)
        self.chat_display.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.chat_display.configure(state="disabled")
        self.msg_entry = ctk.CTkEntry(self.chat_frame, placeholder_text="Send message as Admin...")
        self.msg_entry.grid(row=1, column=0, sticky="ew", padx=(5,0), pady=5)
        self.msg_entry.bind("<Return>", lambda e: self.send_as_admin())
        self.send_btn = ctk.CTkButton(self.chat_frame, text="Send", command=self.send_as_admin, width=70)
        self.send_btn.grid(row=1, column=1, padx=5, pady=5)
        self.remove_btn = ctk.CTkButton(self.chat_frame, text="Remove Access", fg_color="red", hover_color="darkred", command=lambda: remove_access(rule_name))
        self.remove_btn.grid(row=1, column=2, padx=(0, 5), pady=5)
        self.update_ui()

    def send_as_admin(self):
        msg = self.msg_entry.get()
        if msg:
            chat_messages.append(f"Admin: {msg}")
            self.msg_entry.delete(0, "end")
            self.update_chat_display()

    def update_chat_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        for msg in chat_messages:
            self.chat_display.insert("end", msg + "\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def update_ui(self):
        self.update_chat_display()
        active_ips = get_active_ips()
        self.connected_ips_label.configure(text="\n".join(active_ips))
        self.after(1000, self.update_ui)


if __name__ == "__main__":
    rule_name = "LocalChatServer"

    if getattr(sys, "frozen", False) and not has_access(rule_name):
        get_access(rule_name)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    gui = ServerGUI()
    gui.mainloop()