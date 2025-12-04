import customtkinter as ctk
from tkinter import filedialog, messagebox
import base64, requests, subprocess, time, psutil
from PIL import Image

# ---------------- CONFIG ----------------
APP_TITLE = "Local Vision AI"
OLLAMA_URL = "http://localhost:11434"
GENERATE_URL = OLLAMA_URL + "/api/generate"

# ---------------- THEMES ----------------
THEMES = {
    "Glassy": {"mode": "Dark", "color": "blue"},
    "Hacker": {"mode": "Dark", "color": "green"},
    "Professional": {"mode": "Light", "color": "dark-blue"},
    "Mac-style": {"mode": "System", "color": "blue"},
}

# ---------------- OLLAMA MANAGEMENT ----------------
def is_ollama_running():
    try:
        requests.get(OLLAMA_URL, timeout=1)
        return True
    except:
        return False

def start_ollama():
    try:
        subprocess.Popen(["ollama", "serve"], shell=True)
        time.sleep(4)
        return True
    except Exception as e:
        messagebox.showerror("Ollama Error", str(e))
        return False

def ensure_ollama_running():
    if not is_ollama_running():
        return start_ollama()
    return True

def call_ollama(model, prompt, images=None):
    payload = {"model": model, "prompt": prompt, "stream": False}
    if images:
        payload["images"] = images
    r = requests.post(GENERATE_URL, json=payload, timeout=300)
    return r.json()["response"]

# ---------------- IMAGE ----------------
def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def vision_description(image_path):
    return call_ollama(
        "llava",
        "Describe objects, text, people, layout, risks, and anomalies.",
        [encode_image(image_path)],
    )

# ---------------- CHAT ----------------
def ask_ai(model, img, user_text):
    vision = vision_description(img)
    prompt = f"Image context:\n{vision}\n\nUser question:\n{user_text}"
    return call_ollama(model, prompt)

# ---------------- PROCESS CONTROL ----------------
def kill_ollama():
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and "ollama" in proc.info["name"].lower():
            proc.kill()

# ---------------- THEMING ----------------
def apply_theme(theme_name):
    theme = THEMES[theme_name]
    ctk.set_appearance_mode(theme["mode"])
    ctk.set_default_color_theme(theme["color"])
    status_label.configure(text=f"Theme: {theme_name}")

# ---------------- GUI ----------------
ctk.set_default_color_theme("blue")
ctk.set_appearance_mode("Dark")

app = ctk.CTk()
app.title(APP_TITLE)
app.geometry("980x750")

# Top bar
top = ctk.CTkFrame(app, height=50)
top.pack(fill="x", padx=10, pady=10)

model_var = ctk.StringVar(value="deepseek-r1:8b")
model_menu = ctk.CTkOptionMenu(top, values=["deepseek-r1:8b", "ministral-3:8b"], variable=model_var)
model_menu.pack(side="left", padx=10)

theme_var = ctk.StringVar(value="Glassy")
theme_menu = ctk.CTkOptionMenu(top, values=list(THEMES.keys()), variable=theme_var, command=apply_theme)
theme_menu.pack(side="left", padx=10)

status_label = ctk.CTkLabel(top, text="Starting Ollama...", text_color="cyan")
status_label.pack(side="right", padx=10)

# Main area
main = ctk.CTkFrame(app, corner_radius=15)
main.pack(fill="both", expand=True, padx=10, pady=10)

chatbox = ctk.CTkTextbox(main, height=400)
chatbox.pack(fill="both", expand=True, padx=10, pady=10)

entry = ctk.CTkEntry(app, placeholder_text="Ask about the image...")
entry.pack(fill="x", padx=10, pady=10)

btns = ctk.CTkFrame(app)
btns.pack(pady=10)

img_path = None

def upload_image():
    global img_path
    img_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
    if not img_path:
        return
    chatbox.insert("end", f"\n[Image loaded: {img_path}]\n")

def send():
    if not img_path:
        messagebox.showwarning("No Image", "Upload an image first")
        return
    user_text = entry.get().strip()
    if not user_text:
        messagebox.showwarning("No Input", "Enter a question")
        return

    model = model_var.get()
    status_label.configure(text="Thinking...")
    chatbox.insert("end", f"\n[{model}] You: {user_text}\n")
    entry.delete(0, "end")

    try:
        response = ask_ai(model, img_path, user_text)
        chatbox.insert("end", f"AI: {response}\n")
        status_label.configure(text="Ready")
    except Exception as e:
        chatbox.insert("end", f"Error: {e}\n")
        status_label.configure(text="Error")

def quit_app():
    kill_ollama()
    app.destroy()

ctk.CTkButton(btns, text="Upload Image", command=upload_image).pack(side="left", padx=5)
ctk.CTkButton(btns, text="Ask AI", command=send).pack(side="left", padx=5)
ctk.CTkButton(btns, text="Quit & Kill Ollama", fg_color="red", command=quit_app).pack(side="left", padx=5)

# Start Ollama at boot
if ensure_ollama_running():
    status_label.configure(text="Ollama Ready")

apply_theme("Glassy")
app.mainloop()
