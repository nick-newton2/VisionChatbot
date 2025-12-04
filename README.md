# VisionChatbot
Using locally hosted AI models to run a desktop app of a image chatbot


## Installation
Need to install Ollama and Python 3

### Ollama
Install Ollama from website for Windows
Link: [Windows Download](https://ollama.com/download/windows)

Download models that are compatible with your graphics card VRAM

In terminal prompt:
```bash
ollama pull ministral-3:8b
ollama pull deepseek-r1:8b
ollama pull llava
```

### After installing python3 use pip to install python packages
```bash
python3 -m pip install psutil requests pillow customtkinter pynvml

# Standard tkinter should be installed with windows python3 install can test with
python3 -m tkinter
```

## Running Ollama Notes
To run a model (for this code it is handled by the script):
```bash
ollama run [model] # This is started/stopped in code
```

To kill ollama models:
```bash
# Check running models
ollama ps

# Determind ollama processes
tasklist | findstr ollama

# Kill processes
taskkill /PID 1234 /F  # -> where 1234 is pid number
```

## Running the Application
Launch the interactive GUI
```bash
python3 desktop_vision_chatbot_vf.py
```

From here you can select the chat model and choose between themes

You are able to upload an image from your computer then fill in the box and click ask to prompt the models.

To exit and quit the models press the quit button.

## Summary
| Component       | Tool                |
| --------------- | ------------------- |
| GPU inference   | RTX 4060            |
| Model host      | Ollama              |
| Vision model    | LLaVA               |
| Reasoning model | Ministral/Deepseek  |
| Desktop UI      | Customtkinter       |
| Privacy         | 100% local          |


