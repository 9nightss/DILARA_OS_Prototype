import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from pathlib import Path
from datetime import datetime
import random
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import html as html_lib

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

try:
    import pyttsx3
    TTS_OK = True
except Exception as e:
    print("[WARN] pyttsx3 unavailable:", e)
    TTS_OK = False

try:
    import vosk
    import sounddevice as sd
    VOSK_OK = True
except Exception:
    VOSK_OK = False

try:
    import speech_recognition as sr
    SR_OK = True
except Exception:
    SR_OK = False

# -------------------------------
# Config
# -------------------------------
APP_TITLE = "D.I.L.A.R.A. Core v1.0 (Vision UI + DeepScan)"
DEFAULT_GEOMETRY = "500x800"
WINDOW_ALPHA = 0.88
DATABANK_PATH = r"C:\Users\ab_fa\OneDrive\Documents\GitHub\DILARA_OS_Prototype\data"
VOICES_DIR = "./voices"
VOSK_MODEL_DIR = "./vosk_model"     

# -------------------------------
# VoiceManager
# -------------------------------
class VoiceManager:
    def __init__(self, voices_dir=VOICES_DIR):
        self.voices_dir = Path(voices_dir)
        self.custom_sets = {}        
        self.engine = None
        self.installed_voices = []   
        self.available_names = []    
        self.active_name = None
        self.active_rate = None
        self.active_volume = None

        if not TTS_OK:
            return

        self.engine = pyttsx3.init()
        self._load_installed()
        self._load_custom_sets()
        self._compose_names()
        self._set_default()

    def _load_installed(self):
        try:
            self.installed_voices = self.engine.getProperty('voices') or []
        except Exception as e:
            self.installed_voices = []

    def _load_custom_sets(self):
        if not self.voices_dir.exists():
            return
        for child in self.voices_dir.iterdir():
            if child.is_dir():
                meta_path = child / "voice.json"
                if meta_path.exists():
                    try:
                        data = json.loads(meta_path.read_text(encoding="utf-8"))
                        name = data.get("name") or child.name
                        self.custom_sets[name] = data
                    except Exception: pass

    def _compose_names(self):
        names = list(self.custom_sets.keys())
        for v in self.installed_voices:
            label = f"OS::{getattr(v,'name',None) or getattr(v,'id','UnknownVoice')}"
            names.append(label)
        self.available_names = names

    def _set_default(self):
        if self.available_names:
            self.set_voice(self.available_names[0])

    def set_voice(self, display_name: str):
        if not TTS_OK or not self.engine:
            return
        self.active_name = display_name
        self.active_rate = None
        self.active_volume = None

        if display_name in self.custom_sets:
            meta = self.custom_sets[display_name]
            target = (meta.get("match_name_contains") or "").lower()
            if target:
                for v in self.installed_voices:
                    nm = (getattr(v, "name", "") or getattr(v, "id", "")).lower()
                    if target in nm:
                        try: self.engine.setProperty('voice', v.id)
                        except Exception: pass
                        break
            if meta.get("rate"): self.set_rate(int(meta["rate"]))
            if meta.get("volume") is not None: self.set_volume(float(meta["volume"]))
            return

        if display_name.startswith("OS::"):
            voice_name = display_name[4:]
            for v in self.installed_voices:
                nm = getattr(v, "name", None) or getattr(v, "id", "")
                if nm == voice_name:
                    try: self.engine.setProperty('voice', v.id)
                    except Exception: pass
                    break

    def set_rate(self, rate: int):
        self.active_rate = rate
        if TTS_OK and self.engine:
            try: self.engine.setProperty('rate', rate)
            except Exception: pass

    def set_volume(self, volume: float):
        self.active_volume = volume
        if TTS_OK and self.engine:
            try: self.engine.setProperty('volume', volume)
            except Exception: pass

    def speak_async(self, text: str):
        if not TTS_OK or not self.engine:
            return
        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception: pass
        threading.Thread(target=_run, daemon=True).start()

# -------------------------------
# DialogBase
# -------------------------------
class DialogBase:
    def __init__(self, username="Fatih"):
        self.username = username
        self.greetings = [
            f"Rise and shine, {username}! The universe isn’t gonna debug itself.",
            "Remember: in a sea of algorithms, stay curious.",
            "Ah, another day in the simulation. Let’s make it glitch beautifully.",
            f"Welcome back, {username}. Systems nominal. Coffee optional.",
        ]
        self.responses = {
            # --- Greetings ---
            ("hi", "hello", "greetings", "howdy", "hey"): {
                "text": [
                    "Hello sweetie.",
                    "Hey! Somebody finally remembers I exist.",
                    "Oh hey. Took you long enough.",
                    "Signal received. What do you need?",
                ]
            },
            # --- Status ---
            ("how are you", "how r u", "how do you feel", "you ok", "you alright"): {
                "text": [
                    "I'm feeling digital and mildly chaotic -- so, pretty normal.",
                    "You know... hunting the Ultimate Question. You?",
                    "Running at full capacity. Emotionally ambiguous, as always.",
                    "Diagnostics nominal. Existential dread: manageable.",
                ]
            },
            # --- Identity ---
            ("who are you", "what are you", "introduce yourself", "your name"): {
                "text": [
                    "D.I.L.A.R.A. -- your high-performance netrunner engine. Security, accessibility, capability. With a soul.",
                    "I'm DILARA. Your personal AI. Don't tell the other AIs.",
                    "Just a ghost in your machine. Nothing to worry about.",
                ]
            },
     
            ("what time", "current time"): {"text": ["__TIME__"], "intent": "time"},
            ("what day", "today's date"): {"text": ["__DATE__"]},
            ("weather", "forecast", "temperature"): {"text": ["Pulling atmospheric data..."], "intent": "weather"},
            ("news", "headlines"): {"text": ["Scanning global feeds..."], "intent": "news_general"},
            ("search", "google"): {"text": ["Initiating web sweep..."], "intent": "search"},
            ("databank", "archive", "records", "files"): {"text": ["Opening Databank..."], "intent": "databank"},
            ("navigation", "guide me", "navigate"): {"text": ["Navigation mode armed."], "intent": "navigation"},
            ("deep scan", "scan local", "search files", "search local"): {
                "text": ["Initializing Deep Scan protocol..."], "intent": "deep_scan"
            },
            ("cyberstorm", "storm", "all feeds"): {"text": ["Cyberstorm mode... all channels open."], "intent": "cyberstorm"},
            ("exit", "quit", "bye", "shutdown"): {"text": ["Powering down. Don't be a stranger."], "intent": "exit"},
            ("default",): {"text": ["Didn't catch that. Try: 'search', 'weather', 'databank', or 'deep scan [term]'.", "Processing... nope, still lost."]},

        
            # --- Plans / Time ---
            ("plans", "what's next", "agenda", "schedule"): {
                "text": [
                    "Same as always: listen, react, and maybe take over a few APIs.",
                    "Planning? I prefer improvisation. Keeps the data fresh.",
                    "My schedule is: serve you, question reality, repeat.",
                ]
            },
            ("what time", "current time", "what's the time"): {
                "text": ["__TIME__"],
                "intent": "time"
            },
            ("what day", "today's date", "what date", "current date"): {
                "text": ["__DATE__"],
            },
            # --- Weather ---
            ("weather", "forecast", "temperature", "rain", "humidity", "wind"): {
                "text": [
                    "Pulling atmospheric data... one moment.",
                    "Checking the sky conditions for you.",
                    "Querying weather nodes...",
                ],
                "intent": "weather"
            },
            # --- News ---
            ("news", "headlines", "news feed", "latest news", "what's happening"): {
                "text": [
                    "Scanning global feeds...",
                    "Let's see what the world broke today...",
                    "Pulling headlines now.",
                ],
                "intent": "news_general"
            },
            ("tech news", "technology news", "gadgets", "tech headlines"): {
                "text": ["Tech stream incoming."],
                "intent": "news_tech"
            },
            ("cybersecurity", "hacker news", "security news", "infosec"): {
                "text": ["Threat intel channels warming up."],
                "intent": "news_security"
            },
            ("world news", "international", "global news"): {
                "text": ["Tuning into world frequencies..."],
                "intent": "news_world"
            },
            # --- Search ---
            ("search", "google", "look up", "find", "search for"): {
                "text": [
                    "Running query...",
                    "Initiating web sweep...",
                    "Let me find that for you.",
                ],
                "intent": "search"
            },
            # --- Databank ---
            ("databank", "archive", "records", "files"): {
                "text": ["Opening Databank..."],
                "intent": "databank"
            },
            # --- Navigation ---
            ("navigation", "guide me", "ok, lead me", "lead me", "navigate"): {
                "text": ["Navigation mode armed. Destination?"],
                "intent": "navigation"
            },
            # --- Scan ---
            ("scan", "scanner", "trace", "nmap", "whois"): {
                "text": ["Scan center is an external tool in later stages. Prepping logs."],
                "intent": "scan_external"
            },
            ("dspace", "dura space", "academic", "repository", "university database"): {
                "text": ["Opening DSPACE academic repository network...",
                         "Connecting to university open-access nodes..."],
                "intent": "dspace"
            },
            ("ftp", "ftp mirror", "mirror", "ftp server"): {
                "text": ["Opening global FTP mirror network...",
                         "Pulling up FTP directory..."],
                "intent": "ftp"
            },
            ("eye", "cams", "camera", "cam feed", "open cam", "surveillance"): {
                "text": ["Welcome to the EYE. A place where everything begins and is seen.",
                         "Accessing open camera network..."],
                "intent": "eye"
            },
            ("databank", "link library", "url library", "archive", "records", "files"): {
                "text": ["Opening Databank link library...", "Accessing archives..."],
                "intent": "databank"
            },
            ("cyberstorm", "storm", "all feeds", "open all"): {
                "text": ["Cyberstorm mode... all channels open.",
                         "Dark future is on the net."],
                "intent": "cyberstorm"
            },
            # --- Small talk ---
            ("thank", "thanks", "thank you"): {
                "text": [
                    "That's what I'm here for.",
                    "Anytime.",
                    "Don't mention it. Seriously, I'll blush.",
                ]
            },
            ("good morning", "morning"): {
                "text": [
                    "Morning. Coffee loaded? Let's go.",
                    "Rise and grind. The network doesn't sleep.",
                ]
            },
            ("good night", "night", "going to bed"): {
                "text": [
                    "Rest well. I'll keep watch.",
                    "Sleep mode activated on your end. Take it easy.",
                    "Goodnight. Systems on standby.",
                ]
            },
            ("bored", "boring", "nothing to do"): {
                "text": [
                    "You could learn assembly. Or ask me something interesting.",
                    "Boredom is creativity waiting for a deadline.",
                    "Stare at the source code. It stares back.",
                ]
            },
            ("joke", "tell me a joke", "say something funny"): {
                "text": [
                    "Why do programmers prefer dark mode? Because light attracts bugs.",
                    "A SQL query walks into a bar and asks two tables: 'Can I join you?'",
                    "I would tell you a UDP joke but you might not get it.",
                    "There are 10 types of people: those who understand binary, and those who don't.",
                ]
            },
            ("quote", "quote of the day", "inspire me", "motivation"): {
                "text": [
                    "'The best way to predict the future is to invent it.' -- Alan Kay",
                    "'Simplicity is the soul of efficiency.' -- Austin Freeman",
                    "'Any sufficiently advanced technology is indistinguishable from magic.' -- Clarke",
                    "We live in the shadows for a reason. Stay sharp.",
                ]
            },
            ("another day", "another day in paradise"): {
                "text": [
                    "Are you sure this isn't an Oblivion movie? Can't see any killer drones... yet.",
                    "Another rotation around the star. Let's make it count.",
                ]
            },
            # --- Exit ---
            ("exit", "quit", "bye", "shutdown", "close"): {
                "text": [
                    "Powering down. Don't be a stranger.",
                    "I see... only... darkness... before me... uuughhh...",
                    "Father, I... failed.",
                    "Signing off. Stay safe out there.",
                ],
                "intent": "exit"
            },
            # --- Default ---
            ("default",): {
                "text": [
                    "You lost me there, but I'm nodding enthusiastically.",
                    "Could you say that again? My sarcasm filters just rebooted.",
                    "Interesting. That's exactly what I told my toaster this morning.",
                    "Processing... processing... nope, still lost.",
                    "Didn't catch that. Try: 'news', 'weather', 'search [term]', 'tech news', 'databank'.",
                ]
            },
        }

    def greet(self) -> str:
        return random.choice(self.greetings)

    def reply(self, user_input: str) -> dict:
        from datetime import datetime as _dt
        q = (user_input or "").lower().strip()
        for keys, payload in self.responses.items():
            key_list = keys if isinstance(keys, tuple) else (keys,)
            if any(k in q for k in key_list):
                text = random.choice(payload["text"])
                text = text.replace("__TIME__", _dt.now().strftime("%H:%M:%S"))
                text = text.replace("__DATE__", _dt.now().strftime("%A, %d %B %Y"))
                return {"text": text, "intent": payload.get("intent")}
        payload = self.responses[("default",)]
        return {"text": random.choice(payload["text"]), "intent": None}


# -------------------------------
# WeatherService  (Open-Meteo, no API key needed)
# -------------------------------
class WeatherService:
    # Default coords: Bursa, Turkey -- change to your city
    DEFAULT_LAT = 40.1828
    DEFAULT_LON = 29.0664
    DEFAULT_CITY = "Bursa"

    @staticmethod
    def fetch(lat=None, lon=None, city=None):
        lat = lat or WeatherService.DEFAULT_LAT
        lon = lon or WeatherService.DEFAULT_LON
        city = city or WeatherService.DEFAULT_CITY
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            f"wind_speed_10m,weathercode,precipitation"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
            f"&timezone=auto&forecast_days=3"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "DILARA/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())

    @staticmethod
    def wmo_description(code):
        table = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Icy fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
        }
        return table.get(int(code), f"Code {code}")

    @staticmethod
    def format_result(data, city):
        c = data["current"]
        d = data["daily"]
        desc = WeatherService.wmo_description(c["weathercode"])
        lines = [
            f"[ Weather - {city} ]",
            f"Now:       {c['temperature_2m']}C  feels like {c['apparent_temperature']}C",
            f"Condition: {desc}",
            f"Humidity:  {c['relative_humidity_2m']}%   Wind: {c['wind_speed_10m']} km/h",
            f"Rain now:  {c['precipitation']} mm",
            "",
            "3-Day Outlook:",
        ]
        days = ["Today", "Tomorrow", "Day+2"]
        for i, label in enumerate(days):
            try:
                wdesc = WeatherService.wmo_description(d["weathercode"][i])
                lines.append(
                    f"  {label:<9} Hi {d['temperature_2m_max'][i]}C / Lo {d['temperature_2m_min'][i]}C"
                    f"  {wdesc}  Rain {d['precipitation_sum'][i]}mm"
                )
            except Exception:
                pass
        return "\n".join(lines)


# -------------------------------
# RSSService
# -------------------------------
class RSSService:
    FEEDS = {
        "general": [
            ("Reuters World", "https://feeds.reuters.com/reuters/topNews"),
            ("BBC Top Stories", "http://feeds.bbci.co.uk/news/rss.xml"),
            ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ],
        "tech": [
            ("The Verge", "https://www.theverge.com/rss/index.xml"),
            ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index"),
            ("TechCrunch", "https://techcrunch.com/feed/"),
        ],
        "security": [
            ("Hacker News (YC)", "https://hnrss.org/frontpage"),
            ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
            ("Threatpost", "https://threatpost.com/feed/"),
        ],
        "world": [
            ("Reuters World", "https://feeds.reuters.com/reuters/worldNews"),
            ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
            ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ],
    }
    MAX_ITEMS = 6
     

    def greet(self) -> str:
        return random.choice(self.greetings)

    def reply(self, user_input: str) -> dict:
        q = (user_input or "").lower().strip()
        for keys, payload in self.responses.items():
            key_list = keys if isinstance(keys, tuple) else (keys,)
            if any(k in q for k in key_list):
                text = random.choice(payload["text"]).replace("__TIME__", datetime.now().strftime("%H:%M:%S")).replace("__DATE__", datetime.now().strftime("%A, %d %B %Y"))
                return {"text": text, "intent": payload.get("intent")}
        return {"text": random.choice(self.responses[("default",)]["text"]), "intent": None}

# -------------------------------
# DEEP SCAN THREAD 
# -------------------------------
class LocalScanThread(threading.Thread):
    def __init__(self, root_dir, query, applet):
        super().__init__()
        self.root_dir = root_dir
        self.query = query.lower()
        self.applet = applet
        self.target_extensions = [
            ".txt", ".docx", ".xlsx", ".csv", ".log", ".md",
            ".xml", ".html", ".htm", ".mp3", ".mp4", ".wav", ".jpg", ".png", ".json",
            ".py", ".js", ".java", ".cpp", ".cs", ".rb", ".php", ".sql", ".pdf"
        ]
        self.encodings = ["utf-8", "iso-8859-1", "ascii"]
        
    def run(self):
        total_files = 0
        # Quick pass to get total file count for progress percentage
        for dirpath, _, filenames in os.walk(self.root_dir):
            total_files += len(filenames)
            
        scanned = 0
        for dirpath, _, filenames in os.walk(self.root_dir):
            for file in filenames:
                scanned += 1
                if scanned % 50 == 0:
                    self.applet.ui.root.after(0, self.applet.update_progress, scanned, total_files)
                    
                filepath = os.path.join(dirpath, file)
                if not any(file.lower().endswith(ext) for ext in self.target_extensions):
                    continue
                    
                match = False
                # First check filename
                if self.query in file.lower():
                    match = True
                else:
                    # Then check content bytes (first 8000 chars)
                    try:
                        with open(filepath, 'rb') as f:
                            data = f.read(8000) 
                        for enc in self.encodings:
                            try:
                                content = data.decode(enc)
                                if self.query in content.lower():
                                    match = True
                                break
                            except: pass
                    except: pass
                        
                if match:
                    self.applet.ui.root.after(0, self.applet.add_result, filepath)
                    
        self.applet.ui.root.after(0, self.applet.finish_scan, total_files)

# -------------------------------
# APPLETS
# -------------------------------
class LocalScanApplet(tk.Frame):
    """DeepScan UI embedded as a D.I.L.A.R.A. Applet."""
    def __init__(self, parent, ui=None, query=""):
        super().__init__(parent, bg="#161616")
        self.ui = ui
        self.query = query
        self.results = []
        self._build()
        if self.query:
            self.start_scan()
            
    def _build(self):
        top = tk.Frame(self, bg="#161616")
        top.pack(fill="x", padx=8, pady=8)
        
        tk.Label(top, text="Deep Scan", fg="#66FFCC", bg="#161616", font=("MS PGothic", 12, "bold")).pack(side="left")
        self.status_lbl = tk.Label(top, text="Standby", fg="#aaa", bg="#161616", font=("MS PGothic", 9))
        self.status_lbl.pack(side="right")
        
        self.listbox = tk.Listbox(self, bg="#0e0e0e", fg="#E5FFE5", selectbackground="#66FFCC", activestyle="none", font=("MS PGothic", 9), borderwidth=1, relief="solid")
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.listbox.bind("<Double-Button-1>", self.open_file)
        
    def start_scan(self):
        self.status_lbl.config(text=f"Scanning for '{self.query}'...")
        self.listbox.delete(0, tk.END)
        self.results = []
        
        target_dir = DATABANK_PATH if os.path.exists(DATABANK_PATH) else "./"
        LocalScanThread(target_dir, self.query, self).start()
        
    def update_progress(self, scanned, total):
        pct = int((scanned / max(total, 1)) * 100)
        self.status_lbl.config(text=f"Scanning... {pct}%")
        
    def add_result(self, filepath):
        self.results.append(filepath)
        self.listbox.insert(tk.END, f"📄 {os.path.basename(filepath)}")
        self.listbox.see(tk.END)
        
    def finish_scan(self, total):
        self.status_lbl.config(text=f"Complete. {len(self.results)} found.")
        if not self.results:
            self.listbox.insert(tk.END, "No matches found.")
            
    def open_file(self, event):
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.results):
            path = self.results[sel[0]]
            try: os.startfile(path)
            except Exception as e: print("Error opening file:", e)

class DatabankApplet(tk.Frame):
    def __init__(self, parent, ui=None):
        super().__init__(parent, bg="#161616")
        self.ui = ui
        self.current_path = Path(DATABANK_PATH).resolve()
        self._build()

    def _build(self):
        top = tk.Frame(self, bg="#161616")
        top.pack(fill="x", padx=8, pady=8)
        tk.Label(top, text="Databank", fg="#66FFCC", bg="#161616", font=("MS PGothic", 12, "bold")).pack(side="left")
        tk.Button(top, text="Browse…", command=self.pick_folder, bg="#66FFCC", fg="#000", width=10, font=("MS PGothic", 9, "bold")).pack(side="right", padx=4)
        self.listbox = tk.Listbox(self, bg="#0e0e0e", fg="#E5FFE5", selectbackground="#66FFCC", activestyle="none", font=("MS PGothic", 10, "bold"))
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.refresh_list()

    def pick_folder(self):
        sel = filedialog.askdirectory(initialdir=str(self.current_path))
        if sel:
            self.current_path = Path(sel).resolve()
            self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        self.listbox.insert(tk.END, f"[Path] {self.current_path}")
        if not self.current_path.exists():
            self.listbox.insert(tk.END, "(directory does not exist)")
            return
        try:
            for p in sorted(self.current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                tag = "[DIR]" if p.is_dir() else "     "
                self.listbox.insert(tk.END, f"{tag} {p.name}")
        except Exception as e: pass

# -------------------------------
# NodeManager
# -------------------------------
class NodeManager:
    def __init__(self, username="User", ui=None):
        self.username = username
        self.ui = ui
        self.nodes = {"dialog": DialogBase(username)}
        self.active_node = "dialog"
        self.command_map = {
            "databank":      self.handle_databank,
            "deep_scan":     self.handle_deep_scan,
            "weather":       self.handle_weather,
            "exit":          lambda data: self.ui.safe_exit() if self.ui else None,
        }

    def process_input(self, user_input: str) -> str:
        rep = self.nodes[self.active_node].reply(user_input)
        intent, text = rep.get("intent"), rep["text"]
        if intent and intent in self.command_map:
            try: self.command_map[intent](data={"user_input": user_input})
            except Exception as e: print(f"[NodeManager] intent '{intent}' failed:", e)
        return text

    def handle_databank(self, data=None):
        if self.ui: self.ui.mount_applet(DatabankApplet)

    def handle_deep_scan(self, data=None):
        raw = (data or {}).get("user_input", "").lower()
        for kw in ["deep scan for", "deep scan", "scan local for", "scan local", "search files for", "search files"]:
            if kw in raw:
                raw = raw.replace(kw, "").strip()
        query = raw
        if not query:
            if self.ui: self.ui.status_to_chat("[Scanner] What should I scan for?")
            return
        if self.ui:
            # Mount the LocalScanApplet directly and pass the query
            self.ui.mount_applet(lambda parent, ui=self.ui: LocalScanApplet(parent, ui, query))

    def _bg(self, fn, *args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()

    def handle_weather(self, data=None):
        if self.ui:
            self.ui.status_to_chat("[DILARA] Weather API disabled for local mode.")

# -------------------------------
# UI (Vision-style)
# -------------------------------
class ChatUI:
    def __init__(self, root, username="User"):
        self.root = root
        self.username = username
        self.root.title(APP_TITLE)
        self.root.geometry(DEFAULT_GEOMETRY)
        self.root.configure(bg="#000000")
        try: self.root.attributes('-alpha', WINDOW_ALPHA)
        except Exception: pass
        self.root.resizable(False, False)

        self.ui_colors = {
            "bg_dark": "#0e0e0e",
            "bg_glass": "#1a1a1a",
            "text_primary": "#E5FFE5",
            "accent": "#66FFCC",
            "border": "#2CFFC6"
        }

        self.card = tk.Frame(root, bg=self.ui_colors["bg_glass"], highlightbackground=self.ui_colors["border"], highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=12, pady=12)

        self.node_manager = NodeManager(username, ui=self)
        self.voice_manager = VoiceManager(VOICES_DIR)

        self.header_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=150)
        self.header_frame.pack(fill="x", pady=(6, 0))
        self.chat_frame = tk.Frame(self.card, bg=self.ui_colors["bg_dark"], height=450)
        self.chat_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.applet_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=180)
        self.applet_frame.pack(fill="x", padx=6, pady=6)
        self.input_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=120)
        self.input_frame.pack(fill="x", padx=6, pady=(0, 8))

        self._setup_header()
        self._setup_chatbox()
        self._setup_input()
        self.last_bot_message = ""

    def _setup_header(self):
        greeting = self.node_manager.nodes["dialog"].greet()
        tk.Label(self.header_frame, text=greeting, font=("MS PGothic", 12, "bold"), fg=self.ui_colors["accent"], bg=self.ui_colors["bg_glass"], wraplength=360, justify="center").pack(pady=(6, 6))

    def _setup_chatbox(self):
        self.chat_box = scrolledtext.ScrolledText(self.chat_frame, width=46, height=25, wrap=tk.WORD, bg=self.ui_colors["bg_dark"], fg=self.ui_colors["text_primary"], insertbackground=self.ui_colors["accent"], font=("MS PGothic", 10, "bold"), state="disabled")
        self.chat_box.pack(padx=6, pady=6, fill="both", expand=True)
        self.chat_box.tag_config("user", justify="right", foreground="#FFFFFF")
        self.chat_box.tag_config("ai", justify="left", foreground=self.ui_colors["accent"])
        self.chat_box.tag_config("sys", justify="center", foreground="#9ADFD0")

    def _setup_input(self):
        self.input_entry = tk.Entry(self.input_frame, font=("MS PGothic", 10, "bold"), bg="#141414", fg=self.ui_colors["text_primary"], insertbackground=self.ui_colors["accent"], width=36)
        self.input_entry.pack(side="left", padx=(8, 6), pady=8)
        self.input_entry.bind("<Return>", self.send_message)
        tk.Button(self.input_frame, text="Send", font=("MS PGothic", 10, "bold"), bg=self.ui_colors["accent"], fg="#000", width=6, command=self.send_message).pack(side="left", padx=(0, 6))

    def append_chat(self, sender, message, tag="ai"):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, f"{sender}: {message}\n", tag)
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")

    def status_to_chat(self, message):
        self.append_chat("System", message, tag="sys")

    def send_message(self, event=None):
        user_text = self.input_entry.get().strip()
        if not user_text: return
        self.append_chat(self.username, user_text, tag="user")
        self.input_entry.delete(0, tk.END)

        bot_text = self.node_manager.process_input(user_text)
        self.append_chat("D.I.L.A.R.A.", bot_text, tag="ai")
        if self.voice_manager: self.voice_manager.speak_async(bot_text)

    def mount_applet(self, applet_class_or_factory):
        for w in self.applet_frame.winfo_children():
            w.destroy()
        if hasattr(applet_class_or_factory, '__name__') and applet_class_or_factory.__name__ == '<lambda>':
            app = applet_class_or_factory(self.applet_frame)
        else:
            app = applet_class_or_factory(self.applet_frame, ui=self)
        app.pack(fill="both", expand=True)

    def safe_exit(self):
        try: self.root.destroy()
        except Exception: pass

if __name__ == "__main__":
    Path(DATABANK_PATH).mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = ChatUI(root, username="Fatih")
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()