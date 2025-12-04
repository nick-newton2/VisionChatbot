import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import base64, requests, subprocess, time, psutil, threading, json
import os

# Try to import NVML, if available
try:
    from pynvml import *
    nvmlInit()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

APP_TITLE = "Local Vision AI"
OLLAMA_URL = "http://localhost:11434"
GENERATE_URL = OLLAMA_URL + "/api/generate"

# ---------------- GUI ----------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x800")

        self.img_path = None
        self.chat_log = []

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.build_ui()
        if GPU_AVAILABLE:
            self.update_gpu()
        self.ensure_ollama()

    # ---------------- UI ----------------
    def build_ui(self):
        self.top = ctk.CTkFrame(self, height=50)
        self.top.pack(fill="x", padx=10, pady=10)

        self.model_var = ctk.StringVar(value="deepseek-r1:8b")
        ctk.CTkOptionMenu(self.top,
            values=["deepseek-r1:8b","ministral-3:8b"],
            variable=self.model_var).pack(side="left", padx=10)

        self.mode = ctk.StringVar(value="Dark")
        ctk.CTkOptionMenu(self.top,
            values=["Dark","Light"],
            variable=self.mode,
            command=self.toggle_mode).pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(self.top, text="Starting Ollama...", text_color="cyan")
        self.status_label.pack(side="right", padx=10)

        if GPU_AVAILABLE:
            self.gpu_label = ctk.CTkLabel(self.top, text="GPU: --", text_color="orange")
            self.gpu_label.pack(side="right", padx=10)

        # Chat area
        self.chat_area = ctk.CTkScrollableFrame(self, corner_radius=15)
        self.chat_area.pack(fill="both", expand=True, padx=15, pady=10)

        self.entry = ctk.CTkEntry(self, placeholder_text="Ask about the image...")
        self.entry.pack(fill="x", padx=15, pady=10)
        self.entry.bind("<Return>", lambda e:self.send())

        bar = ctk.CTkFrame(self)
        bar.pack(pady=10)

        ctk.CTkButton(bar, text="Upload Image", command=self.upload_image).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Ask", command=self.send).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Settings", command=self.settings_panel).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Export Logs", command=self.export_logs).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Quit", fg_color="red", command=self.quit_app).pack(side="left", padx=6)

    # ---------------- CHAT BUBBLES ----------------
    def bubble(self, text, sender="ai"):
        bg = "#1f6aa5" if sender == "user" else "#2b2b2b"
        anchor = "e" if sender == "user" else "w"
        box = ctk.CTkLabel(self.chat_area, text=text, fg_color=bg,
            corner_radius=15, wraplength=620, justify="left")
        box.pack(anchor=anchor, padx=10, pady=6)

    # ---------------- IMAGE ----------------
    def upload_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.tiff")]
        )
        if path:
            self.img_path = path
            self.bubble(f"Image Loaded:\n{path}", "user")

    # ---------------- SEND ----------------
    def send(self):
        if not self.img_path:
            messagebox.showwarning("No Image","Upload an image first.")
            return

        msg = self.entry.get().strip()
        if not msg:
            return

        self.entry.delete(0,"end")
        self.bubble(msg, "user")
        self.status_label.configure(text="Thinking...")

        threading.Thread(target=self.ask_ai, args=(msg,), daemon=True).start()

    # ---------------- AI ----------------
    def ask_ai(self, text):
        try:
            vision = self.call_ollama("llava",
                "Describe objects, text, risks, layout and anomalies.",
                [self.encode_image(self.img_path)]
            )

            model = self.model_var.get()
            prompt = f"Image:\n{vision}\n\nUser:\n{text}"

            reply = self.call_ollama(model, prompt)

            self.chat_log.append({"user":text,"ai":reply})
            self.after(0, lambda:self.bubble(reply,"ai"))
            self.status_label.configure(text="Ready")

        except Exception as e:
            self.status_label.configure(text="Error")
            self.after(0, lambda:self.bubble(f"Error: {e}","ai"))

    # ---------------- OLLAMA ----------------
    def call_ollama(self, model, prompt, images=None):
        payload = {"model":model,"prompt":prompt,"stream":False}
        if images:
            payload["images"] = images
        r = requests.post(GENERATE_URL, json=payload, timeout=300)
        return r.json()["response"]

    def ensure_ollama(self):
        try:
            requests.get(OLLAMA_URL, timeout=1)
            self.status_label.configure(text="Ollama Ready")
        except:
            subprocess.Popen(["ollama","serve"], shell=True)
            time.sleep(5)
            self.status_label.configure(text="Ollama Started")

    def kill_ollama(self):
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "ollama" in proc.info["name"].lower():
                proc.kill()

    # ---------------- UTILS ----------------
    def encode_image(self, path):
        with open(path,"rb") as f:
            return base64.b64encode(f.read()).decode()

    def toggle_mode(self, m):
        ctk.set_appearance_mode(m)

    # ---------------- GPU ----------------
    def update_gpu(self):
        if not GPU_AVAILABLE:
            return
        try:
            h = nvmlDeviceGetHandleByIndex(0)
            util = nvmlDeviceGetUtilizationRates(h)
            self.gpu_label.configure(text=f"GPU: {util.gpu}%")
        except:
            self.gpu_label.configure(text="GPU: N/A")
        self.after(1000, self.update_gpu)

    # ---------------- SETTINGS ----------------
    def settings_panel(self):
        s = ctk.CTkToplevel(self)
        s.title("Settings")
        s.geometry("320x250")

        ctk.CTkLabel(s, text="Settings", font=("Arial",16)).pack(pady=10)

        ctk.CTkLabel(s, text="Model").pack()
        ctk.CTkOptionMenu(s, values=["deepseek-r1:8b","ministral-3:8b"],
                          variable=self.model_var).pack(pady=5)

        ctk.CTkLabel(s, text="Theme").pack()
        ctk.CTkOptionMenu(s, values=["Dark","Light"],
                          variable=self.mode,
                          command=self.toggle_mode).pack(pady=5)

        ctk.CTkButton(s, text="Clear Chat", command=self.clear_chat).pack(pady=8)
        ctk.CTkButton(s, text="Kill Ollama", fg_color="red", command=self.kill_ollama).pack()

    def clear_chat(self):
        for w in self.chat_area.winfo_children():
            w.destroy()
        self.chat_log.clear()

    # ---------------- EXPORT ----------------
    def export_logs(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            with open(path,"w") as f:
                json.dump(self.chat_log, f, indent=2)
            messagebox.showinfo("Saved","Logs exported")

    # ---------------- EXIT ----------------
    def quit_app(self):
        self.kill_ollama()
        self.destroy()


# ---------------- START ----------------
if __name__ == "__main__":
    app = App()
    app.mainloop()
