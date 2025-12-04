import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import base64, requests, subprocess, time, psutil, threading, json, os, datetime

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

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.img_path = None
        self.chat_log = []
        self.current_gpu_log = {}
        self.gpu_sidebar_visible = True

        self.build_ui()
        self.build_gpu_sidebar()
        if GPU_AVAILABLE:
            self.update_gpu()
        self.ensure_ollama()

    # ---------------- UI ----------------
    def build_ui(self):
        self.top = ctk.CTkFrame(self, height=50)
        self.top.pack(fill="x", padx=10, pady=5)

        self.model_var = ctk.StringVar(value="deepseek-r1:8b")
        ctk.CTkOptionMenu(self.top,
                           values=["deepseek-r1:8b", "ministral-3:8b"],
                           variable=self.model_var).pack(side="left", padx=10)

        self.mode = ctk.StringVar(value="Dark")
        ctk.CTkOptionMenu(self.top,
                           values=["Dark", "Light"],
                           variable=self.mode,
                           command=self.toggle_mode).pack(side="left", padx=10)

        self.gpu_status_label = ctk.CTkLabel(self.top, text="GPU: --", text_color="green")
        self.gpu_status_label.pack(side="right", padx=10)

        self.status_label = ctk.CTkLabel(self.top, text="Starting Ollama...", text_color="yellow")
        self.status_label.pack(side="right", padx=10)

        self.chat_frame = ctk.CTkFrame(self)
        self.chat_frame.pack(fill="both", expand=True, padx=15, pady=(5,0))

        self.chat_area = ctk.CTkScrollableFrame(self.chat_frame, corner_radius=15, height=400)
        self.chat_area.pack(fill="both", expand=True, side="left", padx=(0,10))

        self.entry = ctk.CTkEntry(self, placeholder_text="Ask about the image...")
        self.entry.pack(fill="x", padx=15, pady=5)
        self.entry.bind("<Return>", lambda e: self.send())

        bar = ctk.CTkFrame(self)
        bar.pack(pady=5)
        ctk.CTkButton(bar, text="Upload Image", command=self.upload_image).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Ask", command=self.send).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Clear Chat", command=self.clear_chat).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Export Logs", command=self.export_logs).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Quit", fg_color="red", command=self.quit_app).pack(side="left", padx=6)

    # ---------------- GPU SIDEBAR ----------------
    def build_gpu_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        self.gpu_toggle_btn = ctk.CTkButton(
            self.sidebar, text="Collapse GPU", command=self.toggle_gpu_sidebar
        )
        self.gpu_toggle_btn.pack(pady=10, padx=10)

        self.log_frame = ctk.CTkScrollableFrame(self.sidebar)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def toggle_gpu_sidebar(self):
        if self.gpu_sidebar_visible:
            self.sidebar.pack_forget()
            self.gpu_sidebar_visible = False
            self.gpu_toggle_btn = ctk.CTkButton(
                self, text="Show GPU Logs", command=self.toggle_gpu_sidebar
            )
            self.gpu_toggle_btn.place(x=0, y=50)
        else:
            self.sidebar.pack(side="left", fill="y")
            self.gpu_sidebar_visible = True
            if hasattr(self, 'gpu_toggle_btn'):
                self.gpu_toggle_btn.destroy()

    # ---------------- CHAT ----------------
    def bubble(self, text, sender="ai"):
        bg = "#1f6aa5" if sender == "user" else "#2b2b2b"
        anchor = "e" if sender == "user" else "w"
        box = ctk.CTkLabel(self.chat_area, text=text, fg_color=bg,
                            corner_radius=15, wraplength=620, justify="left")
        box.pack(anchor=anchor, padx=10, pady=6)

    # ---------------- IMAGE ----------------
    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.tiff")])
        if path:
            self.img_path = path
            self.bubble(f"Image Loaded:\n{path}", "user")
            self.show_image_preview(path)

    def show_image_preview(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((200, 200))
            photo = ctk.CTkImage(img, size=img.size)
            label = ctk.CTkLabel(self.chat_area, image=photo, text="")
            label.image = photo
            label.pack(anchor="e", padx=10, pady=6)
        except Exception as e:
            self.bubble(f"Preview Error: {e}", "ai")

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
        self.status_label.configure(text="Thinking...", text_color="orange")

        threading.Thread(target=self.ask_ai, args=(msg,), daemon=True).start()

    # ---------------- AI ----------------
    def ask_ai(self, text):
        self.log_key_event("Question sent to Ollama.")

        try:
            vision = self.call_ollama("llava",
                                      "Describe objects, text, risks, layout and anomalies.",
                                      [self.encode_image(self.img_path)])
            self.log_key_event("Vision analysis complete.")

            model = self.model_var.get()
            prompt = f"Image:\n{vision}\n\nUser:\n{text}"

            reply = self.call_ollama(model, prompt)
            self.log_key_event("Ollama response complete.")

            self.chat_log.append({"user": text, "ai": reply, "gpu_log": self.current_gpu_log.copy()})
            self.bubble(reply,"ai")
            self.status_label.configure(text="Ready", text_color="yellow")

        except Exception as e:
            self.status_label.configure(text="Error", text_color="red")
            self.bubble(f"Error: {e}","ai")

    # ---------------- OLLAMA ----------------
    def call_ollama(self, model, prompt, images=None):
        payload = {"model": model, "prompt": prompt, "stream": False}
        if images:
            payload["images"] = images
        r = requests.post(GENERATE_URL, json=payload, timeout=300)
        return r.json().get("response","")

    def log_key_event(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.append_log(f"[{timestamp}] {text}", key_event=True)

    def append_log(self, text, key_event=False):
        color = "green" if key_event else "white"
        lbl = ctk.CTkLabel(self.log_frame, text=text, anchor="w",
                            justify="left", wraplength=280, text_color=color)
        lbl.pack(fill="x", pady=1, padx=5)
        self.log_frame.update_idletasks()

    # ---------------- GPU ----------------
    def update_gpu(self):
        if not GPU_AVAILABLE:
            self.gpu_status_label.configure(text="GPU: N/A")
            return
        try:
            h = nvmlDeviceGetHandleByIndex(0)
            util = nvmlDeviceGetUtilizationRates(h)
            mem = nvmlDeviceGetMemoryInfo(h)
            temp = nvmlDeviceGetTemperature(h, NVML_TEMPERATURE_GPU)
            gpu_text = f"GPU: {util.gpu}%  Mem: {mem.used/1024**2:.1f}/{mem.total/1024**2:.1f} MB  Temp: {temp}°C"
            self.gpu_status_label.configure(text=gpu_text, text_color="green")
            self.current_gpu_log = {"gpu":util.gpu, "memory_used":mem.used,
                                    "memory_total":mem.total, "temp":temp}
        except:
            self.gpu_status_label.configure(text="GPU: N/A")
            self.current_gpu_log = {}
        self.after(1000, self.update_gpu)

    # ---------------- OLLAMA MANAGEMENT ----------------
    def ensure_ollama(self):
        try:
            requests.get(OLLAMA_URL, timeout=1)
            self.status_label.configure(text="Ollama Ready", text_color="yellow")
        except:
            subprocess.Popen(["ollama","serve"], shell=True)
            time.sleep(5)
            self.status_label.configure(text="Ollama Started", text_color="yellow")

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

    # ---------------- CLEAR & EXPORT ----------------
    def clear_chat(self):
        for w in self.chat_area.winfo_children():
            w.destroy()
        self.chat_log.clear()

    def export_logs(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            export_data = {"chat": self.chat_log}
            with open(path,"w") as f:
                json.dump(export_data, f, indent=2)
            messagebox.showinfo("Saved","Logs exported")

    # ---------------- EXIT ----------------
    def quit_app(self):
        self.kill_ollama()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
