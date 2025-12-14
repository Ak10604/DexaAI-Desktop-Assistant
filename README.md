# DexaAI – Desktop Voice Assistant 🤖🎙️

DexaAI is a **powerful offline-first desktop AI assistant** built in Python with a modern GUI, voice control, system automation, and productivity tools.  
Inspired by JARVIS-style assistants, DexaAI runs locally, respects privacy, and gives you deep control over your system — all through voice.

> 💡 Designed for real-world use, not demos.

---

## 🚀 Key Features

### 🎙️ Voice Intelligence
- Wake-word activation (`Hey Dexa`)
- Offline speech recognition (PocketSphinx)
- Text-to-speech using `pyttsx3`
- Adjustable voice, speed, volume & sensitivity
- Background listening support

### 🖥️ Desktop Automation
- Open apps, files, and folders
- Lock, shutdown, mute, screenshot via voice
- Screen recording (start / stop)
- System tray integration
- Start on boot support

### 📊 System Awareness
- Live CPU, RAM & Disk monitoring
- Visual alerts when thresholds are exceeded
- Battery and system info commands

### 📝 Notes & Productivity
- Create, read, list, and delete notes via voice
- Smart fuzzy-matching for note retrieval
- Scheduled reminders with pop-up alerts

### 🧠 Smart Commands
- Fully customizable voice commands
- Dynamic commands (search, play, remind, open)
- Import / export command sets
- Command history logging

### 🎨 Modern UI
- Built with `CustomTkinter`
- Dark / Light themes
- Animated waveform visualizer
- Floating assistant popup
- Clean, futuristic design

---

## 🔐 Privacy First
- Works **fully offline**
- No cloud APIs required
- No data collection
- All logs stored locally

---

## 🛠️ Tech Stack

- **Python 3.10+**
- `CustomTkinter` – Modern GUI
- `SpeechRecognition` + PocketSphinx
- `pyttsx3` – Offline TTS
- `OpenCV` – Camera utilities
- `psutil` – System monitoring
- `pystray` – System tray
- `PyAutoGUI` – Automation
- `FuzzyWuzzy` – Command matching

---

## 📦 Installation

```bash
git clone https://github.com/your-username/DexaAI-Desktop-Assistant.git
cd DexaAI-Desktop-Assistant
pip install -r requirements.txt
python Dexa.py
