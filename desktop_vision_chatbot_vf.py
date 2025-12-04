import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import base64, requests, subprocess, time, psutil, threading, json, os

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
        self.geometry("1200x800")

        self.img_path = None
        self.chat_log = []

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Sidebar visibility
        self.log_collapsed = False
        self.current_gpu_log = {}

        self.build_ui()
        self.build_gpu_sidebar()
        if GPU_AVAILABLE:
            self.update_gpu()
        self.ollama_running = False

    # ---------------- UI ----------------
    def build_ui(self):
        # Top bar
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

        self.status_label = ctk.CTkLabel(self.top, text="Ready", text_color="yellow")
        self.status_label.pack(side="right", padx=10)

        # Main chat area (adjustable height)
        self.chat_area_frame = ctk.CTkFrame(self)
        self.chat_area_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.chat_area = ctk.CTkScrollableFrame(self.chat_area_frame, corner_radius=15)
        self.chat_area.pack(fill="both", expand=True)

        # Entry box
        self.entry = ctk.CTkEntry(self, placeholder_text="Ask about the image...")
        self.entry.pack(fill="x", padx=15, pady=10)
        self.entry.bind("<Return>", lambda e:self.send())

        # Bottom buttons
        bar = ctk.CTkFrame(self)
        bar.pack(pady=10)

        ctk.CTkButton(bar, text="Upload Image", command=self.upload_image).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Ask", command=self.send).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Clear Chat", command=self.clear_chat).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Export Logs", command=self.export_logs).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Quit", fg_color="red", command=self.quit_app).pack(side="left", padx=6)

    # ---------------- GPU SIDEBAR ----------------
    def build_gpu_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        # GPU stats at top left
        self.gpu_label = ctk.CTkLabel(self.sidebar, text="GPU Stats Loading...", text_color="orange", anchor="w", justify="left")
        self.gpu_label.pack(fill="x", padx=10, pady=10)

        # Collapsible log section
        self.log_frame = ctk.CTkFrame(self.sidebar)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.log_text = ctk.CTkTextbox(self.log_frame, width=280, height=300)
        self.log_text.pack(fill="both", expand=True)

        self.gpu_toggle_btn = ctk.CTkButton(self.sidebar, text="Collapse Logs", command=self.toggle_log)
        self.gpu_toggle_btn.pack(pady=5, padx=10)

    def toggle_log(self):
        if self.log_collapsed:
            self.log_text.pack(fill="both", expand=True)
            self.gpu_toggle_btn.configure(text="Collapse Logs")
            self.log_collapsed = False
        else:
            self.log_text.pack_forget()
            self.gpu_toggle_btn.configure(text="Expand Logs")
            self.log_collapsed = True

    def append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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

        if not self.ollama_running:
            threading.Thread(target=self.ensure_ollama, daemon=True).start()

        threading.Thread(target=self.ask_ai, args=(msg,), daemon=True).start()

    # ---------------- AI ----------------
    def ask_ai(self, text):
        try:
            # Stream logs from Ollama while generating
            self.ollama_running = True
            self.append_log("Starting Ollama generation...")

            vision = self.call_ollama("llava",
                "Describe objects, text, risks, layout and anomalies.",
                [self.encode_image(self.img_path)]
            )
            self.append_log("Vision processing complete.")

            model = self.model_var.get()
            prompt = f"Image:\n{vision}\n\nUser:\n{text}"
            reply = self.call_ollama(model, prompt)
            self.append_log("AI response received.")

            self.chat_log.append({"user":text,"ai":reply, "gpu_log": self.current_gpu_log.copy()})
            self.after(0, lambda:self.bubble(reply,"ai"))
            self.status_label.configure(text="Ready", text_color="yellow")

        except Exception as e:
            self.status_label.configure(text="Error", text_color="red")
            self.after(0, lambda:self.bubble(f"Error: {e}","ai"))
            self.append_log(f"Error: {e}")

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
            self.append_log("Ollama already running.")
        except:
            self.append_log("Starting Ollama server...")
            subprocess.Popen(["ollama","serve"], shell=True)
            time.sleep(5)
            self.append_log("Ollama started.")

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
            mem = nvmlDeviceGetMemoryInfo(h)
            temp = nvmlDeviceGetTemperature(h, NVML_TEMPERATURE_GPU)
            gpu_text = f"GPU: {util.gpu}%\nMemory: {mem.used/1024**2:.1f}/{mem.total/1024**2:.1f} MB\nTemp: {temp}°C"
            self.gpu_label.configure(text=gpu_text)
            self.current_gpu_log = {"gpu":util.gpu, "memory_used":mem.used, "memory_total":mem.total, "temp":temp}
        except:
            self.gpu_label.configure(text="GPU: N/A")
            self.current_gpu_log = {}
        self.after(1000, self.update_gpu)

    # ---------------- CLEAR CHAT ----------------
    def clear_chat(self):
        for w in self.chat_area.winfo_children():
            w.destroy()
        self.chat_log.clear()

    # ---------------- EXPORT ----------------
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


# ---------------- START ----------------
if __name__ == "__main__":
    app = App()
    app.mainloop()
