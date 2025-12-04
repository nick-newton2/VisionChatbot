import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import base64, requests, subprocess, time
from PIL import Image, ImageTk

OLLAMA_URL = "http://localhost:11434"
GENERATE_URL = OLLAMA_URL + "/api/generate"

# ---------- OLLAMA STARTUP ----------

def ensure_ollama_running():
    try:
        requests.get(OLLAMA_URL, timeout=1)
        return
    except:
        try:
            subprocess.Popen(["ollama", "serve"], shell=True)
            time.sleep(4)
        except Exception as e:
            messagebox.showerror("Ollama Error", f"Could not start Ollama.\n{e}")

def ensure_model(model_name):
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags").json()
        models = [m["name"] for m in r.get("models", [])]
        if model_name not in models:
            subprocess.run(["ollama", "pull", model_name], shell=True)
    except:
        pass

# ---------- OLLAMA CALL ----------

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

# ---------- IMAGE ----------

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

# ---------- QUIT HANDLER ----------

def quit_app():
    try:
        # Stop all running Ollama models
        subprocess.run(["ollama", "stop", "--all"], shell=True)
    except Exception as e:
        print(f"Error stopping Ollama: {e}")
    root.destroy()

# ---------- GUI ----------

ensure_ollama_running()

root = tk.Tk()
root.title("Local Vision Chatbot")
root.geometry("900x700")

model_var = tk.StringVar()
model_dropdown = ttk.Combobox(root, textvariable=model_var, state="readonly")
model_dropdown["values"] = ("deepseek-r1:8b", "ministral-3:8b")
model_dropdown.current(0)
model_dropdown.pack(pady=5)

ensure_model("deepseek-r1:8b")
ensure_model("ministral-3:8b")
ensure_model("llava")

img_label = tk.Label(root)
img_label.pack()

chatbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=16)
chatbox.pack(fill="both", expand=True)

entry = tk.Entry(root)
entry.pack(fill="x", padx=10)

image_path = None

def upload_image():
    global image_path
    image_path = filedialog.askopenfilename()

    img = Image.open(image_path)
    img.thumbnail((300,300))
    photo = ImageTk.PhotoImage(img)
    img_label.configure(image=photo)
    img_label.image = photo

def send():
    user_text = entry.get()
    model = model_var.get()

    if not image_path:
        messagebox.showwarning("No Image", "Upload an image first.")
        return

    if not user_text:
        return

    chatbox.insert(tk.END, f"\nModel [{model}]\nYou: {user_text}\n")
    entry.delete(0, tk.END)

    try:
        response = chat_with_image(model, image_path, user_text)
        chatbox.insert(tk.END, f"Bot: {response}\n")
    except Exception as e:
        chatbox.insert(tk.END, f"Error: {e}\n")

# ---------- BUTTONS ----------

btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

upload_btn = tk.Button(btn_frame, text="Upload Image", command=upload_image)
upload_btn.pack(side="left", padx=5)

send_btn = tk.Button(btn_frame, text="Ask", command=send)
send_btn.pack(side="left", padx=5)

quit_btn = tk.Button(btn_frame, text="Quit & Stop Ollama", command=quit_app, fg="red")
quit_btn.pack(side="left", padx=5)

# ---------- START GUI LOOP ----------

root.mainloop()
