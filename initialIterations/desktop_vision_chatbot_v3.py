import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import base64, requests, subprocess, time
from PIL import Image, ImageTk
import psutil  # new

OLLAMA_URL = "http://localhost:11434"
GENERATE_URL = OLLAMA_URL + "/api/generate"

# ---------- OLLAMA MANAGEMENT ----------

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
        messagebox.showerror("Ollama Error", f"Could not start Ollama.\n{e}")
        return False

def ensure_ollama_running():
    if not is_ollama_running():
        return start_ollama()
    return True

def ensure_model(model_name):
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags").json()
        models = [m["name"] for m in r.get("models", [])]
        if model_name not in models:
            subprocess.run(["ollama", "pull", model_name], shell=True)
    except:
        pass

# ---------- OLLAMA API ----------

def call_ollama(model, prompt, images=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if images:
        payload["images"] = images
    r = requests.post(GENERATE_URL, json=payload, timeout=300)
    return r.json()["response"]

# ---------- IMAGE HANDLING ----------

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def vision_description(image_path):
    return call_ollama(
        model="llava",
        prompt="Describe objects, text, people, risks, and notable details.",
        images=[encode_image(image_path)]
    )

# ---------- CHAT ----------

def chat_with_image(user_model, image_path, question):
    description = vision_description(image_path)
    prompt = f"""
You are an intelligent assistant.

Image context:
{description}

User question:
{question}

Respond clearly and helpfully.
"""
    return call_ollama(user_model, prompt)

# ---------- QUIT BUTTON ----------

def quit_app():
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if 'ollama' in proc.info['name'].lower():
                proc.kill()
        print("All Ollama processes killed.")
    except Exception as e:
        print(f"Error killing Ollama: {e}")
    finally:
        root.destroy()

# ---------- STATUS ----------

def update_status(running=True, busy=False):
    if not running:
        status_label.config(text="Ollama: Not Running", bg="red")
    elif busy:
        status_label.config(text="Ollama: Busy", bg="orange")
    else:
        status_label.config(text="Ollama: Running", bg="green")

# ---------- GUI ----------

root = tk.Tk()
root.title("Local Vision Chatbot")
root.geometry("950x750")

# Model selector
model_var = tk.StringVar()
model_dropdown = ttk.Combobox(root, textvariable=model_var, state="readonly")
model_dropdown["values"] = ("deepseek-r1:8b", "ministral-3:8b")
model_dropdown.current(0)
model_dropdown.pack(pady=5)

# Status label
status_label = tk.Label(root, text="Ollama: Unknown", font=("Arial", 12), width=20)
status_label.pack(pady=5)

# Ensure Ollama + models
if ensure_ollama_running():
    update_status(running=True)
else:
    update_status(running=False)

for m in ["deepseek-r1:8b", "ministral-3:8b", "llava"]:
    ensure_model(m)

# Image preview
img_label = tk.Label(root)
img_label.pack()

# Chat box
chatbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=16)
chatbox.pack(fill="both", expand=True)

# User entry
entry = tk.Entry(root)
entry.pack(fill="x", padx=10)

image_path = None

# ---------- BUTTON FUNCTIONS ----------

def upload_image():
    global image_path
    image_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
    if not image_path:
        return

    img = Image.open(image_path)
    img.thumbnail((300,300))
    photo = ImageTk.PhotoImage(img)
    img_label.configure(image=photo)
    img_label.image = photo

def send():
    user_text = entry.get().strip()
    model = model_var.get()

    if not is_ollama_running():
        update_status(running=False)
        messagebox.showerror("Ollama Not Running", "Ollama is not running.")
        return

    if not image_path:
        messagebox.showwarning("No Image", "Please upload an image first.")
        return
    if not user_text:
        messagebox.showwarning("No Question", "Please type a question to ask.")
        return

    update_status(running=True, busy=True)
    chatbox.insert(tk.END, f"\nModel [{model}]\nYou: {user_text}\n")
    entry.delete(0, tk.END)
    root.update()

    try:
        response = chat_with_image(model, image_path, user_text)
        chatbox.insert(tk.END, f"Bot: {response}\n")
    except Exception as e:
        chatbox.insert(tk.END, f"Error: {e}\n")
    finally:
        update_status(running=True, busy=False)

# Buttons
btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

upload_btn = tk.Button(btn_frame, text="Upload Image", command=upload_image)
upload_btn.pack(side="left", padx=5)

send_btn = tk.Button(btn_frame, text="Ask", command=send)
send_btn.pack(side="left", padx=5)

quit_btn = tk.Button(btn_frame, text="Quit & Kill Ollama", command=quit_app, fg="red")
quit_btn.pack(side="left", padx=5)

# Start GUI
root.mainloop()
