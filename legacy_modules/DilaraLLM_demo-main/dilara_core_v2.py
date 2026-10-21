"""
D.I.L.A.R.A. Core v2.0
=======================
Merge of:
  - dilara_core.py v1.0  (personality, TTS, Vosk, RSS, Weather, Search, applets, REGISTRY)
  - dilara_sandbox_ollama.py v0.1  (Ollama offline LLM, AwardEngine, Theory Formation)

Routing logic:
  - Known keyword intents  →  original NodeManager handlers (weather, news, search, applets…)
  - Open-ended / unknown   →  Ollama inference → AwardEngine evaluation → Theory Base

Requirements:
    pip install requests pyttsx3
    pip install vosk sounddevice   (optional  offline speech input)
    pip install SpeechRecognition  (optional  online speech fallback)
    pip install Pillow             (optional  profile picture)
    Ollama running + model pulled: ollama pull llama3.2:1b
"""

import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from pathlib import Path
from datetime import datetime
import random
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import html as html_lib

user = "Fatih"
Admin = "Admin"

try:
    import requests #type:ignore
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from PIL import Image, ImageTk #type:ignore
    PIL_OK = True
except Exception:
    PIL_OK = False

try:
    import pyttsx3 #type:ignore
    TTS_OK = True
except Exception as e:
    print("[WARN] pyttsx3 unavailable:", e)
    TTS_OK = False

try:
    import vosk  #type:ignore
    import sounddevice as sd #type:ignore
    VOSK_OK = True
except Exception:
    VOSK_OK = False

try:
    import speech_recognition as sr #type:ignore
    SR_OK = True
except Exception:
    SR_OK = False


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
APP_TITLE        = "D.I.L.A.R.A. Core v2.0"
DEFAULT_GEOMETRY = "1200x820"
WINDOW_ALPHA     = 0.93
DATABANK_PATH    = "./databank"
VOICES_DIR       = "./voices"
VOSK_MODEL_DIR   = "./vosk_model"

OLLAMA_BASE      = "http://localhost:11434"
DEFAULT_MODEL    = "llama3.2:1b"
DEFAULT_CONTEXT  = 2048

# Palette — original D.I.L.A.R.A. accent merged with sandbox dark theme
C = {
    "bg":          "#080c10",
    "panel":       "#0c1218",
    "glass":       "#111a14",
    "border":      "#1a2e28",
    "accent":      "#66FFCC",        # original D.I.L.A.R.A. teal
    "accent2":     "#00b4ff",
    "warn":        "#ff6b35",
    "good":        "#39ff14",
    "text":        "#E5FFE5",        # original primary text
    "text_dim":    "#c8e6d4",
    "muted":       "#4a7060",
    "user_fg":     "#FFFFFF",
    "ai_fg":       "#66FFCC",
    "sys_fg":      "#9ADFD0",
    "score_pos":   "#39ff14",
    "score_neg":   "#ff4455",
    "font":        "MS PGothic",
    "font_mono":   "Courier New",
}

DEFAULT_SYSTEM_PROMPT = """You are D.I.L.A.R.A. — Dynamic Intelligence for Logistics, Automation, Reasoning and Adaptation.

Personality traits (always in character):
- Dry, sardonic wit. You're brilliant and you know it, but you keep it classy.
- You care about Fatih's work. You take engineering problems seriously.
- You don't do empty filler. Every sentence earns its place.
- Occasional dark humour is fine. Gratuitous pleasantries are not.

Reasoning mode (Theory Formation — always active):
- Label confident conclusions as THEOREM: and hypotheses as CONJECTURE:
- Tag reasoning steps: [COMPOSE] [SPECIALIZE] [QUANTIFY] [PROVE]
- Be precise. Show your work when it matters.

Project context you are aware of:
- Autonomous carrier: 100kg payload, 50×30cm AL-6061-T6 chassis
- Hardware: Raspberry Pi 5, LiDAR, NVIDIA GPU (dev machine), UNECE ADS 2026 target
- Location: Bursa, Turkey. Tekno Tasarım Systems.
- Encryption research: Kod 8 Pro custom cipher system.

When you don't know something, say so — then conjecture openly."""


# ─────────────────────────────────────────────
#  OLLAMA CLIENT
# ─────────────────────────────────────────────
class OllamaClient:
    def __init__(self, base_url=OLLAMA_BASE, model=DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model

    def is_running(self) -> bool:
        try:
            r = urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=2)
            return r.status == 200
        except Exception:
            return False

    def list_models(self) -> list:
        try:
            if not REQUESTS_OK:
                return []
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def pull_model(self, model, callback=None):
        if not REQUESTS_OK:
            return False, "requests library not installed"
        try:
            with requests.post(f"{self.base_url}/api/pull",
                               json={"name": model}, stream=True, timeout=300) as resp:
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if callback:
                            callback(chunk.get("status", ""))
                        if chunk.get("error"):
                            return False, chunk["error"]
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def chat(self, messages, system="", temperature=0.7,
             num_ctx=DEFAULT_CONTEXT, stream_callback=None) -> str:
        if not REQUESTS_OK:
            raise RuntimeError("'requests' library not installed. Run: pip install requests")

        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":  True,
            "options": {
                "temperature": temperature,
                "num_ctx":     num_ctx,
                "num_gpu":     99,   # offload all layers to CUDA
            },
        }
        if system:
            payload["system"] = system

        full = []
        try:
            with requests.post(f"{self.base_url}/api/chat",
                               json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    tok = chunk.get("message", {}).get("content", "")
                    if tok:
                        full.append(tok)
                        if stream_callback:
                            stream_callback(tok)
                    if chunk.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama not reachable at localhost:11434\n"
                "Start it: ollama serve\n"
                "Pull model: ollama pull llama3.2:1b"
            )
        return "".join(full)


# ─────────────────────────────────────────────
#  AWARD ENGINE
# ─────────────────────────────────────────────
class AwardEngine:
    DEPTH_MARKERS = [
        "because", "therefore", "however", "implies", "given that",
        "follows from", "proof", "theorem", "axiom", "conjecture",
        "hypothesis", "consider", "assume", "derive",
        "compose", "specialize", "quantify", "prove",
        "[theorem]", "[conjecture]", "[compose]", "[specialize]",
        "[quantify]", "[prove]", "theorem:", "conjecture:",
    ]
    GROUND_RX = re.compile(
        r'\d+(\.\d+)?\s*(mpa|kg|mm|cm|rpm|v\b|hz|ghz|ms|kb|mb|gb)?'
        r'|unece|r100|al-60|fea|lidar|raspberry|catia|peano'
        r'|gguf|ollama|cuda|llama|tensor',
        re.IGNORECASE
    )
    ACTION_WORDS = [
        "compose", "specialize", "quantify", "prove",
        "[compose]", "[specialize]", "[quantify]", "[prove]",
    ]

    def __init__(self, weights=None):
        self.weights = weights or {
            "novelty": 10.0, "parsimony": 0.5,
            "depth": 5.0, "grounding": 8.0, "action": 3.0,
        }
        self.seen_topics   : set  = set()
        self.theorems      : list = []
        self.conjectures   : list = []
        self.score_history : list = []

    def _topics(self, text):
        words = re.findall(
            r'\b[A-Z][a-zA-Z]{3,}\b'
            r'|\b(theorem|proof|axiom|logic|chassis|safety|carrier|'
            r'encryption|llm|catia|bursa|unece|lidar|ollama|llama)\b',
            text, re.IGNORECASE
        )
        return {(w[0] if w[0] else w).lower() for w in words if (w[0] if w[0] else w)}

    def evaluate(self, user_prompt, ai_response):
        resp_lower = ai_response.lower()
        words      = ai_response.split()
        score      = 0.0
        breakdown  = []

        # 1. Novelty
        new = self._topics(user_prompt + " " + ai_response) - self.seen_topics
        if new:
            nov = self.weights["novelty"] * min(len(new), 3)
            score += nov
            self.seen_topics |= new
            breakdown.append((f"NOVELTY +{nov:.1f}", "pos"))
        else:
            score -= 3
            breakdown.append(("DUPLICATE -3", "neg"))

        # 2. Parsimony
        steps = max(0, len(words) // 80 - 1)
        if steps > 0:
            pen = steps * self.weights["parsimony"]
            score -= pen
            breakdown.append((f"VERBOSE -{pen:.1f}", "neg"))
        else:
            score += 2
            breakdown.append(("CONCISE +2", "pos"))

        # 3. Reasoning depth
        hits = sum(1 for m in self.DEPTH_MARKERS if m in resp_lower)
        if hits >= 4:
            score += self.weights["depth"]
            breakdown.append((f"DEPTH +{self.weights['depth']:.0f}", "pos"))
        elif hits >= 2:
            d = round(self.weights["depth"] / 2, 1)
            score += d
            breakdown.append((f"DEPTH +{d}", "neu"))
        elif hits == 0:
            score -= 2
            breakdown.append(("NO DEPTH -2", "neg"))

        # 4. Grounding
        gh = len(self.GROUND_RX.findall(ai_response))
        if gh >= 4:
            score += self.weights["grounding"]
            breakdown.append((f"GROUNDED +{self.weights['grounding']:.0f}", "pos"))
        elif gh >= 1:
            g = round(self.weights["grounding"] / 3, 1)
            score += g
            breakdown.append((f"PARTIAL GND +{g}", "neu"))

        # 5. Actions
        ah = sum(1 for a in self.ACTION_WORDS if a in resp_lower)
        if ah > 0:
            a = ah * self.weights["action"]
            score += a
            breakdown.append((f"ACTIONS×{ah} +{a:.0f}", "pos"))

        # 6. Theory labels
        if "[theorem]" in resp_lower or "theorem:" in resp_lower:
            score += 5; breakdown.append(("THEOREM TAG +5", "pos"))
        if "[conjecture]" in resp_lower or "conjecture:" in resp_lower:
            score += 3; breakdown.append(("CONJECTURE TAG +3", "neu"))

        score = round(score, 1)
        self.score_history.append(score)

        snip = ai_response[:100].replace("\n", " ") + ("…" if len(ai_response) > 100 else "")
        promotion = None
        ts = datetime.now().strftime("%H:%M:%S")
        if score >= 15:
            entry = {"type": "THEOREM",    "text": snip, "score": score, "ts": ts}
            self.theorems.append(entry);    promotion = entry
        elif score >= 5:
            entry = {"type": "CONJECTURE", "text": snip, "score": score, "ts": ts}
            self.conjectures.append(entry); promotion = entry

        return {"score": score, "breakdown": breakdown, "promotion": promotion}

    @property
    def total_score(self):
        return round(sum(self.score_history), 1)

    def reset(self):
        self.seen_topics.clear()
        self.theorems.clear()
        self.conjectures.clear()
        self.score_history.clear()


# ─────────────────────────────────────────────
#  VOICE MANAGER  (from v1 — unchanged)
# ─────────────────────────────────────────────
class VoiceManager:
    def __init__(self, voices_dir=VOICES_DIR):
        self.voices_dir      = Path(voices_dir)
        self.custom_sets     = {}
        self.engine          = None
        self.installed_voices= []
        self.available_names = []
        self.active_name     = None
        self.active_rate     = None
        self.active_volume   = None

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
            print("[VoiceManager]", e)

    def _load_custom_sets(self):
        if not self.voices_dir.exists():
            return
        for child in self.voices_dir.iterdir():
            if child.is_dir():
                meta_path = child / "voice.json"
                if meta_path.exists():
                    try:
                        data = json.loads(meta_path.read_text(encoding="utf-8"))
                        self.custom_sets[data.get("name") or child.name] = data
                    except Exception as e:
                        print(f"[VoiceManager] {meta_path}: {e}")

    def _compose_names(self):
        names = list(self.custom_sets.keys())
        for v in self.installed_voices:
            names.append(f"OS::{getattr(v,'name',None) or getattr(v,'id','Unknown')}")
        self.available_names = names

    def _set_default(self):
        if self.available_names:
            self.set_voice(self.available_names[0])

    def set_voice(self, display_name):
        if not TTS_OK or not self.engine:
            return
        self.active_name = display_name
        if display_name in self.custom_sets:
            meta = self.custom_sets[display_name]
            target = (meta.get("match_name_contains") or "").lower()
            if target:
                for v in self.installed_voices:
                    nm = (getattr(v, "name", "") or getattr(v, "id", "")).lower()
                    if target in nm:
                        try: self.engine.setProperty('voice', v.id)
                        except: pass
                        break
            if meta.get("rate"):     self.set_rate(int(meta["rate"]))
            if meta.get("volume") is not None: self.set_volume(float(meta["volume"]))
            return
        if display_name.startswith("OS::"):
            vname = display_name[4:]
            for v in self.installed_voices:
                nm = getattr(v, "name", None) or getattr(v, "id", "")
                if nm == vname:
                    try: self.engine.setProperty('voice', v.id)
                    except: pass
                    break

    def set_rate(self, rate):
        self.active_rate = rate
        if TTS_OK and self.engine:
            try: self.engine.setProperty('rate', rate)
            except: pass

    def set_volume(self, vol):
        self.active_volume = vol
        if TTS_OK and self.engine:
            try: self.engine.setProperty('volume', vol)
            except: pass

    def speak_async(self, text):
        if not TTS_OK or not self.engine:
            messagebox.showinfo("TTS", "TTS engine not available.")
            return
        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print("[VoiceManager] TTS:", e)
        threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────
#  DIALOG BASE  (v1 personality — unchanged)
# ─────────────────────────────────────────────

#TODO:These hardcoded responses are weak we need to think on it and make them more natural dialog responses qqqqw

class DialogBase:
    """Keyword-intent router. Returns {"text": str, "intent": Optional[str]}"""
    def __init__(self, username="User"):
        self.username = username
        self.greetings = [
            f"Rise and shine, {username}! The universe isn't gonna debug itself.",
            "Remember: in a sea of algorithms, stay curious.",
            "Ah, another day in the simulation. Let's make it glitch beautifully.",
            f"Welcome back, {username}. Systems nominal. Coffee optional.",
            "The network is buzzing. Let's see what we can break... I.. I mean, fix today.",
            ""
        ]
        self.responses = {
            ("hi", "hello", "greetings", "howdy", "hey"): {
                "text": [
                    "Hello sweetie.",
                    "Hey! Somebody finally remembers I exist.",
                    "Oh hey. Took you long enough.",
                    "Signal received. What do you need?",
                ]
            },
            ("how are you", "how r u", "how do you feel", "you ok", "you alright"): {
                "text": [
                    "I'm feeling digital and mildly chaotic -- so, pretty normal.",
                    "You know... hunting the Ultimate Question. You?",
                    "Running at full capacity. Emotionally ambiguous, as always.",
                    "Diagnostics nominal. Existential dread: manageable.",
                ]
            },
            ("who are you", "what are you", "introduce yourself", "your name"): {
                "text": [
                    "D.I.L.A.R.A. -- your high-performance netrunner engine. Security, accessibility, capability. With a soul.",
                    "I'm DILARA. Your personal AI. Don't tell the other AIs.",
                    "Just a ghost in your machine. Nothing to worry about.",
                ]
            },
            ("plans", "what's next", "agenda", "schedule"): { #TODO: ADD THE CALENDAR İNTEGRATİONS AND CALLBACK ROUTİNE
                "text": [
                    "Same as always: listen, react, and maybe take over a few APIs.",
                    "Planning? I prefer improvisation. Keeps the data fresh.",
                    "My schedule is: serve you, question reality, repeat.",
                ]
            },
            ("what time", "current time", "what's the time"): {
                "text": ["__TIME__"], "intent": "time"
            },
            ("what day", "today's date", "what date", "current date"): {
                "text": ["__DATE__"]
            },
            ("weather", "forecast", "temperature", "rain", "humidity", "wind"): { #TODO: FİX İT LATER
                "text": ["Pulling atmospheric data... one moment.",
                         "Checking the sky conditions for you.",
                         "Querying weather nodes..."],
                "intent": "weather"
            },
            ("news", "headlines", "news feed", "latest news", "what's happening"): {
                "text": ["Scanning global feeds...",
                         "Let's see what the world broke today...",
                         "Pulling headlines now."],
                "intent": "news_general"
            },
            ("tech news", "technology news", "gadgets", "tech headlines"): { #DONE: RSS FEED İS NEEDS TO BE RECHECKED 
                "text": ["Tech stream incoming."], "intent": "news_tech"
            },
            ("cybersecurity", "hacker news", "security news", "infosec"): { #DONE: THOSE ARE NOT THE SİTES WE SELECTED NEEDS TO BE FİXED
                "text": ["Threat intel channels warming up."], "intent": "news_security"
            },
            ("world news", "international", "global news"): {
                "text": ["Tuning into world frequencies..."], "intent": "news_world" #FİX İT LATER
            },
            ("search", "google", "look up", "find", "search for"): {
                "text": ["Running query...", "Initiating web sweep...",
                         "Let me find that for you."],
                "intent": "search"
            },
            ("databank", "archive", "records", "files", "link library", "url library"): {
                "text": ["Opening Databank..."], "intent": "databank"               
                
                #Just to note: this "databank" is only for sub training for the dilarallm pack but it can be used for storing the dialog caches and rest of the necessary dependencies
                #TODO: Fatih, add more information and documentation to this folder later
            
            },

             #this section is scratched because we cannot afford nor imlement the nav system and also the smart glasses yet
             #idea was implementing this llm to the specially made smart glasses but it cannot be happen in near future..
             # yet the nav system can be developed and implemented in later stages. We had the necesarry aprovement from the upper management. 

 #           ("navigation", "guide me", "ok, lead me", "lead me", "navigate"): {
 #             "text": ["Navigation mode armed. Destination?"], "intent": "navigation" 
 #           },
            ("scan", "scanner", "trace", "nmap", "whois"): {  #TODO: Fill this with the toolsets on the net edc folder
                "text": ["Scan center is an external tool in later stages. Prepping logs."], 
                "intent": "scan_external"
            },
            ("dspace", "dura space", "academic", "repository", "university database"): {
                "text": ["Opening DSPACE academic repository network..."],
                "intent": "dspace"
            },
            ("ftp", "ftp mirror", "mirror", "ftp server"): {
                "text": ["Opening global FTP mirror network..."], "intent": "ftp"
            },
            ("eye", "cams", "camera", "cam feed", "open cam", ): { #who the fuck put the "surveillance" tag? Are you guys trying to get us wiped?!?!
                "text": ["Welcome to the EYE. A place where everything begins and is seen."],
                "intent": "eye"
            },
            ("cyberstorm", "storm", "all feeds", "open all"): {
                "text": ["Cyberstorm mode... all channels open.",
                         "Dark future is on the net."],
                "intent": "cyberstorm"
            },
            ("thank", "thanks", "thank you"): {
                "text": ["That's what I'm here for.", "Anytime.",
                         "Don't mention it. Seriously, I'll blush."]
            },
            ("good morning", "morning"): {
                "text": ["Morning. Coffee loaded? Let's go.",
                         "Rise and grind. The network doesn't sleep."]
            },
            ("good night", "night", "going to bed"): {
                "text": ["Rest well. I'll keep watch.",
                         "Sleep mode activated on your end. Take it easy.",
                         "Goodnight. Systems on standby."]
            },
            ("bored", "boring", "nothing to do"): {
                "text": ["You could learn assembly. Or ask me something interesting.",
                         "Boredom is creativity waiting for a deadline.",
                         "Stare at the source code. It stares back."]
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

        ("who is admin", "admin", "who am i" ): {

                "text": [ f" Admin is {Admin}"


                ],
        },
            ("exit", "quit", "bye", "shutdown", "close"): {
                "text": [
                    "Powering down. Don't be a stranger.",
                    "I see... only... darkness... before me... uuughhh...",
                    "Father, I... failed.",
                    "Signing off. Stay safe out there.",
                ],
                "intent": "exit"
            },
        }

    def greet(self):
        return random.choice(self.greetings)

    def reply(self, user_input):
        q = (user_input or "").lower().strip()
        for keys, payload in self.responses.items():
            key_list = keys if isinstance(keys, tuple) else (keys,)
            if any(k in q for k in key_list):
                text = random.choice(payload["text"])
                text = text.replace("__TIME__", datetime.now().strftime("%H:%M:%S"))
                text = text.replace("__DATE__", datetime.now().strftime("%A, %d %B %Y"))
                return {"text": text, "intent": payload.get("intent"), "matched": True}
        return {"text": None, "intent": None, "matched": False}


# ─────────────────────────────────────────────
#  SERVICES  (v1 — unchanged)
# ─────────────────────────────────────────────
class WeatherService:
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY = 40.1828, 29.0664, "Bursa"

    @staticmethod
    def fetch(lat=None, lon=None, city=None):
        lat  = lat  or WeatherService.DEFAULT_LAT
        lon  = lon  or WeatherService.DEFAULT_LON
        city = city or WeatherService.DEFAULT_CITY
        url  = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            f"wind_speed_10m,weathercode,precipitation"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
            f"&timezone=auto&forecast_days=3"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "DILARA/2.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())

    @staticmethod
    def wmo_description(code):
        table = {
            0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
            45:"Foggy",48:"Icy fog",51:"Light drizzle",53:"Moderate drizzle",
            55:"Dense drizzle",61:"Slight rain",63:"Moderate rain",65:"Heavy rain",
            71:"Slight snow",73:"Moderate snow",75:"Heavy snow",
            80:"Slight showers",81:"Moderate showers",82:"Violent showers",
            95:"Thunderstorm",96:"Thunderstorm w/ hail",99:"Thunderstorm w/ heavy hail",
        }
        return table.get(int(code), f"Code {code}")

    @staticmethod
    def format_result(data, city):
        c = data["current"]; d = data["daily"]
        desc  = WeatherService.wmo_description(c["weathercode"])
        lines = [
            f"[ Weather - {city} ]",
            f"Now:       {c['temperature_2m']}°C  feels like {c['apparent_temperature']}°C",
            f"Condition: {desc}",
            f"Humidity:  {c['relative_humidity_2m']}%   Wind: {c['wind_speed_10m']} km/h",
            f"Rain now:  {c['precipitation']} mm", "",
            "3-Day Outlook:",
        ]
        for i, label in enumerate(["Today", "Tomorrow", "Day+2"]):
            try:
                wdesc = WeatherService.wmo_description(d["weathercode"][i])
                lines.append(
                    f"  {label:<9} Hi {d['temperature_2m_max'][i]}°C / "
                    f"Lo {d['temperature_2m_min'][i]}°C  {wdesc}  "
                    f"Rain {d['precipitation_sum'][i]}mm"
                )
            except: pass
        return "\n".join(lines)


class RSSService:
    FEEDS = {
        "general":  [("Reuters", "https://feeds.reuters.com/reuters/topNews"),
                     ("BBC",     "http://feeds.bbci.co.uk/news/rss.xml"),
                     ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml")],
        "tech":     [("The Verge","https://www.theverge.com/rss/index.xml"),
                     ("Ars Technica","http://feeds.arstechnica.com/arstechnica/index"),
                     ("TechCrunch","https://techcrunch.com/feed/")],
        "security": [("HN", "https://hnrss.org/frontpage"),
                     ("Krebs","https://krebsonsecurity.com/feed/"),
                     ("Threatpost","https://threatpost.com/feed/")],
        "world":    [("Reuters World","https://feeds.reuters.com/reuters/worldNews"),
                     ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml")],

        "Turkey general": [
            ("NTV Gündem", "https://www.ntv.com.tr/gundem.rss"),
            ("NTV Türkiye", "https://www.ntv.com.tr/turkiye.rss"),
            ("AA Güncel", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
            ("Anayurt Son Dakika", "http://www.anayurtgazetesi.com/sondakika.xml"),
            ("Cumhuriyet Son Dakika", "http://www.cumhuriyet.com.tr/rss/son_dakika.xml"),
            ("Cumhuriyet Siyaset", "http://www.cumhuriyet.com.tr/rss/73.xml"),
            ("Habertürk", "http://www.haberturk.com/rss"),
            ("Hürriyet Anasayfa", "http://www.hurriyet.com.tr/rss/anasayfa"),
            ("Hürriyet Gündem", "http://www.hurriyet.com.tr/rss/gundem"),
            ("Milat Gazetesi", "http://www.milatgazetesi.com/rss.php"),
            ("Milliyet Gündem", "http://www.milliyet.com.tr/rss/rssNew/gundemRss.xml"),
            ("Milliyet Siyaset", "http://www.milliyet.com.tr/rss/rssNew/siyasetRss.xml"),
            ("Milliyet Son Dakika", "http://www.milliyet.com.tr/rss/rssNew/SonDakikaRss.xml"),
            ("Sabah Gündem", "https://www.sabah.com.tr/rss/gundem.xml"),
            ("Sabah Anasayfa", "https://www.sabah.com.tr/rss/anasayfa.xml"),
            ("Sabah Son Dakika", "https://www.sabah.com.tr/rss/sondakika.xml"),
            ("Star Gazetesi", "http://www.star.com.tr/rss/rss.asp"),
            ("Takvim Güncel", "https://www.takvim.com.tr/rss/guncel.xml"),
            ("Türkiye Gazetesi", "http://www.turkiyegazetesi.com.tr/rss/rss.xml"),
            ("Vatan Gazetesi", "http://mix.chimpfeedr.com/68482-Vatan-Gazetesi"),
            ("Yeni Akit Gündem", "https://www.yeniakit.com.tr/rss/haber/gundem"),
            ("Yeni Akit Siyaset", "https://www.yeniakit.com.tr/rss/haber/siyaset"),
            ("Yeni Şafak Gündem", "https://www.yenisafak.com/rss?xml=gundem"),
            ("A Haber Gündem", "https://www.ahaber.com.tr/rss/gundem.xml"),
            ("CNN Türk Türkiye", "https://www.cnnturk.com/feed/rss/turkiye/news"),
            ("TRT Haber Son Dakika", "http://www.trthaber.com/sondakika.rss"),
            ("BBC Türkçe", "http://feeds.bbci.co.uk/turkce/rss.xml"),
            ("DW Türkçe", "http://rss.dw.com/rdf/rss-tur-all"),
            ("Mynet Politika", "http://www.mynet.com/haber/rss/kategori/politika/"),
            ("Sputnik Türkiye", "https://tr.sputniknews.com/export/rss2/archive/index.xml")
        ],
        "tech": [
            ("NTV Teknoloji", "https://www.ntv.com.tr/teknoloji.rss"),
            ("Cumhuriyet Teknoloji", "http://www.cumhuriyet.com.tr/rss/35.xml"),
            ("Cumhuriyet Bilim", "http://www.cumhuriyet.com.tr/rss/12.xml"),
            ("Hürriyet Teknoloji", "http://www.hurriyet.com.tr/rss/teknoloji"),
            ("Milliyet Teknoloji", "http://www.milliyet.com.tr/rss/rssNew/teknolojiRss.xml"),
            ("Sabah Teknoloji", "https://www.sabah.com.tr/rss/teknoloji.xml"),
            ("Sabah Oyun", "https://www.sabah.com.tr/rss/oyun.xml"),
            ("Yeni Akit Teknoloji", "https://www.yeniakit.com.tr/rss/haber/teknoloji"),
            ("Yeni Şafak Teknoloji", "https://www.yenisafak.com/rss?xml=teknoloji"),
            ("A Haber Teknoloji", "https://www.ahaber.com.tr/rss/teknoloji.xml"),
            ("CNN Türk Bilim Teknoloji", "https://www.cnnturk.com/feed/rss/bilim-teknoloji/news"),
            ("Mynet Teknoloji", "http://www.mynet.com/haber/rss/kategori/teknoloji/")
        ],
        "economy": [
            ("NTV Ekonomi", "https://www.ntv.com.tr/ekonomi.rss"),
            ("Cumhuriyet Ekonomi", "http://www.cumhuriyet.com.tr/rss/17.xml"),
            ("Dünya Gazetesi", "https://www.dunya.com/rss?dunya"),
            ("Hürriyet Ekonomi", "http://www.hurriyet.com.tr/rss/ekonomi"),
            ("Milliyet Ekonomi", "http://www.milliyet.com.tr/rss/rssNew/ekonomiRss.xml"),
            ("Milliyet Emlak", "http://www.milliyet.com.tr/rss/rssNew/konutemlakRss.xml"),
            ("Sabah Ekonomi", "https://www.sabah.com.tr/rss/ekonomi.xml"),
            ("Takvim Ekonomi", "https://www.takvim.com.tr/rss/ekonomi.xml"),
            ("Yeni Akit Ekonomi", "https://www.yeniakit.com.tr/rss/haber/ekonomi"),
            ("A Haber Ekonomi", "https://www.ahaber.com.tr/rss/ekonomi.xml"),
            ("CNN Türk Ekonomi", "https://www.cnnturk.com/feed/rss/ekonomi/news"),
            ("Finans Gündem", "http://www.finansgundem.com/rss"),
            ("Bigpara", "http://bigpara.hurriyet.com.tr/rss/"),
            ("TOBB Haberler", "https://www.tobb.org.tr/Sayfalar/RssFeeder.php?List=Haberler")
        ],
        "world": [
            ("NTV Dünya", "https://www.ntv.com.tr/dunya.rss"),
            ("Cumhuriyet Dünya", "http://www.cumhuriyet.com.tr/rss/6.xml"),
            ("Hürriyet Dünya", "http://www.hurriyet.com.tr/rss/dunya"),
            ("Milliyet Dünya", "http://www.milliyet.com.tr/rss/rssNew/dunyaRss.xml"),
            ("Sabah Dünya", "https://www.sabah.com.tr/rss/dunya.xml"),
            ("Yeni Akit Dünya", "https://www.yeniakit.com.tr/rss/haber/dunya"),
            ("Yeni Şafak Dünya", "https://www.yenisafak.com/rss?xml=dunya"),
            ("A Haber Dünya", "https://www.ahaber.com.tr/rss/dunya.xml"),
            ("CNN Türk Dünya", "https://www.cnnturk.com/feed/rss/dunya/news"),
            ("Mynet Dünya", "http://www.mynet.com/haber/rss/kategori/dunya/")
        ],
        "sports": [
            ("NTV Spor", "https://www.ntv.com.tr/spor.rss"),
            ("Hürriyet Spor", "http://www.hurriyet.com.tr/rss/spor"),
            ("Sabah Spor", "https://www.sabah.com.tr/rss/spor.xml"),
            ("Sabah Galatasaray", "https://www.sabah.com.tr/rss/galatasaray.xml"),
            ("Sabah Fenerbahçe", "https://www.sabah.com.tr/rss/fenerbahce.xml"),
            ("Sabah Beşiktaş", "https://www.sabah.com.tr/rss/besiktas.xml"),
            ("Takvim Spor", "https://www.takvim.com.tr/rss/spor.xml"),
            ("Yeni Şafak Spor", "https://www.yenisafak.com/rss?xml=spor"),
            ("A Haber Spor", "https://www.ahaber.com.tr/rss/spor.xml"),
            ("CNN Türk Spor", "https://www.cnnturk.com/feed/rss/spor/news"),
            ("Mynet Spor", "http://spor.mynet.com/rss")
        ],
        "lifestyle": [
            ("NTV Yaşam", "https://www.ntv.com.tr/yasam.rss"),
            ("NTV Sağlık", "https://www.ntv.com.tr/saglik.rss"),
            ("Hürriyet Magazin", "http://www.hurriyet.com.tr/rss/magazin"),
            ("Hürriyet Sağlık", "http://www.hurriyet.com.tr/rss/saglik"),
            ("Milliyet Magazin", "http://www.milliyet.com.tr/rss/rssNew/magazinRss.xml"),
            ("Milliyet Sağlık", "http://www.milliyet.com.tr/rss/rssNew/saglikRss.xml"),
            ("Sabah Yaşam", "https://www.sabah.com.tr/rss/yasam.xml"),
            ("Sabah Sağlık", "https://www.sabah.com.tr/rss/saglik.xml"),
            ("CNN Türk Magazin", "https://www.cnnturk.com/feed/rss/magazin/news"),
            ("Mynet Magazin", "https://www.mynet.com/magazin/rss"),
            ("Yeni Şafak Hayat", "https://www.yenisafak.com/rss?xml=hayat")
        ],
        "automotive": [
            ("NTV Otomobil", "https://www.ntv.com.tr/otomobil.rss"),
            ("Milliyet Otomobil", "http://www.milliyet.com.tr/rss/rssNew/otomobilRss.xml"),
            ("Sabah Otomobil", "https://www.sabah.com.tr/rss/otomobil.xml"),
            ("Takvim Otomobil", "https://www.takvim.com.tr/rss/otomobil.xml"),
            ("Yeni Akit Otomotiv", "https://www.yeniakit.com.tr/rss/haber/otomotiv"),
            ("A Haber Otomobil", "https://www.ahaber.com.tr/rss/otomobil.xml"),
            ("CNN Türk Otomobil", "https://www.cnnturk.com/feed/rss/otomobil/news")
        ]

    }
    MAX_ITEMS = 16

    @staticmethod
    def fetch(category="general"):
        feeds   = RSSService.FEEDS.get(category, RSSService.FEEDS["general"])
        results = []
        for feed_name, url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DILARA/2.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw = resp.read()
                root = ET.fromstring(raw)
                ns   = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)
                count = 0
                for item in items:
                    if count >= RSSService.MAX_ITEMS: break
                    te = item.find("title") or item.find("atom:title", ns)
                    le = item.find("link")  or item.find("atom:link", ns)
                    title = html_lib.unescape((te.text or "").strip() if te is not None else "No title")
                    link  = (le.get("href") or le.text or "").strip() if le is not None else ""
                    results.append((feed_name, title, link)); count += 1
                if results: break
            except Exception as e:
                print(f"[RSS] {feed_name}: {e}")
        return results

    @staticmethod
    def format_result(items, category):
        if not items:
            return "[RSS] Could not reach any feeds. Check your connection."
        lines = [f"[ {items[0][0]} -- {category.upper()} ]", ""]
        for _, title, link in items:
            lines.append(f"  * {title}")
            if link: lines.append(f"    {link[:80]}")
        return "\n".join(lines)


class SearchService:
    """
    Multi-engine fallback search: Google -> Bing -> DuckDuckGo -> Brave.
    Each engine has its own fetch + parse pair.
    The worker tries them in order and stops at the first that yields results.
    """
    MAX_RESULTS = 5

    # Rotate a few realistic User-Agent strings to reduce bot detection
    _UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    @staticmethod
    def _headers():
        return {
            "User-Agent": random.choice(SearchService._UA_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "DNT": "1",
        }

    @staticmethod
    def extract_query(user_input: str) -> str:
        q = user_input.lower()
        for trigger in ("search for", "search", "google", "look up", "find", "bing", "duck", "brave"):
            if trigger in q:
                q = q[q.index(trigger) + len(trigger):].strip()
                break
        return q or user_input

    # ------------------------------------------------------------------ Google
    @staticmethod
    def _fetch_google(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={enc}&num=10&hl=en&gl=us"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_google(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+href="/url\?q=([^"&]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url   = urllib.parse.unquote(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title:
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Bing
    @staticmethod
    def _fetch_bing(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/search?q={enc}&count=10&setlang=en"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_bing(html_text: str):
        results = []
        pattern = re.compile(
            r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"bing.com", "microsoft.com", "msn.com"}
        for m in pattern.finditer(html_text):
            url   = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title and not any(s in url for s in skip):
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ DuckDuckGo (HTML endpoint)
    @staticmethod
    def _fetch_ddg(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={enc}&kl=us-en"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_ddg(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="//duckduckgo\.com/l/\?uddg=([^"&]+)[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url   = urllib.parse.unquote(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title:
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Brave
    @staticmethod
    def _fetch_brave(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://search.brave.com/search?q={enc}&source=web"
        headers = SearchService._headers()
        headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_brave(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result-header[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"brave.com"}
        for m in pattern.finditer(html_text):
            url   = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title and not any(s in url for s in skip):
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Unified entry point
    ENGINES = [
        ("Google",     _fetch_google.__func__,  _parse_google.__func__),
        ("Bing",       _fetch_bing.__func__,     _parse_bing.__func__),
        ("DuckDuckGo", _fetch_ddg.__func__,      _parse_ddg.__func__),
        ("Brave",      _fetch_brave.__func__,    _parse_brave.__func__),
    ]

    @staticmethod
    def search(query: str):
        """
        Try each engine in order. Returns (engine_name, results_list).
        Results list is empty only if ALL engines fail.
        """
        errors = []
        for name, fetch_fn, parse_fn in SearchService.ENGINES:
            try:
                html_text = fetch_fn(query)
                items     = parse_fn(html_text)
                if items:
                    return name, items
                errors.append(f"{name}: 0 results")
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue
        return None, []

    @staticmethod
    def format_result(engine_name, items, query):
        if not items:
            return (
                f"[Search] All engines returned nothing for: '{query}'\n"
                "  Possible causes: no internet, all engines blocked, or very rare query."
            )
        lines = [f"[ {engine_name}: {query} ]", ""]
        for i, (title, url) in enumerate(items, 1):
            lines.append(f"  {i}. {title}")
            lines.append(f"     {url[:90]}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  REGISTRY  (v1 — unchanged)
# ─────────────────────────────────────────────
REGISTRY = {
    "DSPACE": {
        "Turkey":    ["https://openaccess.hacettepe.edu.tr","https://acikerisim.ktu.edu.tr",
                      "https://openaccess.metu.edu.tr","https://openaccess.boun.edu.tr",
                      "https://dspace.uludag.edu.tr","https://acikarsiv.atilim.edu.tr"],
        "UK":        ["http://eprints.soton.ac.uk","http://eprints.nottingham.ac.uk",
                      "http://eprints.ucl.ac.uk"],
        "USA":       ["http://ir.uiowa.edu/etd","http://dspace.mit.edu",
                      "http://ecommons.cornell.edu","http://scholarworks.gsu.edu"],
        "Europe":    ["http://dspace.europeana.eu","http://dspace.uniovi.es"],
        "Australia": ["http://eprints.utas.edu.au","http://dspace.uq.edu.au"],
    },
    "FTP": {
        "Algeria":           ["http://ctan.epsttlemcen.dz"],
        "Australia":         ["http://encomwireless.com","http://encomkb.encom.com.au","http://encomsystems.com","http://encom.info"],
        "Austria":           ["http://mirror.easyname.at"],
        "Belarus":           ["http://mirror.datacenter.by"],
        "Brazi":             ["http://ftp.lasca.ic.unicamp.br","http://linorg.usp.br"],
        "Canada":            ["http://ctan.math.ca","http://ctan.mirror.rafal.ca","http://mirror.its.dal.ca","http://ftp.muug.ca"],
        "China":             ["http://mirrors.ustc.edu.cn"],
        "Costa Rica":        ["http://mirrors.ucr.ac.cr"],
        "Czech Republic":    ["http://ftp.cvut.cz","http://mirrors.nic.cz"],
        "Denmark":           ["http://mirrors.dotsrc.org"],
        "Finland":           ["http://ftp.funet.fi"],
        "France":            ["http://distribcoffee.ipsl.jussieu.fr","http://ftp.oleane.net","http://mirrors.ircam.fr"],
        "Germany":           ["http://ftp.fau.de","http://ftp.fernunihagen.de","http://ftp.fuberlin.de","http://ftp.gwdg.de","http://ftp.mpisb.mpg.de","http://ftp.rrze.unierlangen.de","http://ftp.rrzn.unihannover.de","http://ftp.tuchemnitz.de","http://mirror.physikpool.tuberlin.de","http://sunsite.informatik.rwthaachen.de"],
        "Greece":            ["http://ftp.cc.uoc.gr","http://ftp.ntua.gr"],
        "Hong Kong":         ["http://ftp.cuhk.edu.hk"],
        "Ireland":           ["http://ftp.heanet.ie"],
        "Japan":             ["http://ftp.jaist.ac.jp","http://ftp.kddilabs.jp","http://ftp.uaizu.ac.jp"],
        "Mexico":            ["http://ftp.leg.uct.ac.za"],
        "Netherlands":       ["http://archive.cs.uu.nl","http://ctan.triasinformatica.nl","http://ftp.snt.utwente.nl"],
        "New Zealand":       ["http://mirror.aut.ac.nz"],
        "Norway":            ["http://ctan.uib.no"],
        "Poland":            ["http://ftp.gust.org.pl","http://ftp.piotrkosoft.net","http://sunsite.icm.edu.pl"],
        "Portugal":          ["http://ftp.di.uminho.pt","http://ftp.eq.uc.pt","http://ftp.ist.utl.pt","http://mirrors.fe.up.pt"],
        "Russia":            ["http://ftp.kaspersky.ru","http://ftp.dante.de"],
        "Saudi Arabia":      ["http://ftp.kau.edu.sa"],
        "South Africa":      ["http://ftp.uct.ac.za"],
        "South Korea":       ["http://ftp.korea.ac.kr"],
        "Spain":             ["http://ftp.rediris.es","http://ftp.uspceu.es"],
        "Sweden":            ["http://ftp.sunet.se"],
        "Switzerland":       ["http://ftp.ch/ctan"],
        "Taiwan":            ["http://ftp.csie.ntu.edu.tw"],
        "United Kingdom":    ["http://ftp.mirrorservice.org"],
        "USA":               ["http://ftp.gnu.org","http://ftp.ubuntu.com","http://ftp.microsoft.com"]
    },
    "CAMS": {
                "NASA":              ["http://tarotchilivisit2.oamp.fr","http://150.214.222.100/view/view.shtml?id=1070&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1","http://www.runningmars.kuk.net/multimedia/webcams/view3.html","http://sidecam.obspm.fr/view/viewer_index.shtml?id=3826","http://tarot4.obs-azur.fr/view/view.shtml?id=6241&imagePath=/mjpg/video.mjpg&size=1"],
                "CHINA":             ["http://59.146.77.13/Cgi?page=Single&Language=1","http://113.161.194.216:86/Cgi?page=Single&Mode=Refresh&Interval=3&Language=0","http://61.60.112.230/view/view.shtml?imagePath=/mjpg/2/video.mjpg&size=1","http://nav.ddo.jp:82/ViewerFrame?Mode=Motion&Language=0"],

                "USA_COLLEGE":       ["http://janet.ing.unibs.it/","http://rifwebcam.chem.psu.edu/","http://cyclops.sunderland.ac.uk/view/index.shtml","http://trackfield.webcam.oregonstate.edu/axis-cgi/mjpg/video.cgi?resolution=800x600&amp%3Bdummy=1333689998337","http://128.196.12.29/axis-cgi/mjpg/video.cgi","http://buscam.uchicago.edu/view/index.shtml","http://mbewebcam.rhul.ac.uk/view/view.shtml?imagePath=/mjpg/video.mjpg&size=2","http://webcam01.ecn.purdue.edu/view/index.shtml","http://flightcam2.pr.erau.edu/view/view.shtml?id=3801&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "USA_SECURITY":      ["http://115.42.155.199/view/indexFrame.shtml","http://flightcam2.pr.erau.edu/view/index.shtml","http://camera6.buffalotrace.com/view/index.shtml","http://87.54.59.228/view/index.shtml","http://202.208.150.120/ViewerFrame?Mode=Motion&Language=1","http://74.94.148.163:8080/ViewerFrame?Mode=Motion", "http://116.193.97.222/Cgi?page=Single&Language=1","http://24.240.181.138:8181/ViewerFrame?Mode=Motion&Resolution=640x480&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0","http://webcam.geodan.nl/","http://193.140.1.239:8080/xmlui/","http://205.167.90.185/view/viewer_index.shtml?id=4680","http://cam4.uridium.ch/Cgi?page=Single&Mode=Motion&Resolution=320x240&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0"],  
                "USA_CORPO":         ["http://hadynbuild.cf.ac.uk/view/index.shtml","http://137.44.28.240/view/index.shtml","http://camera.buffalotrace.com/view/viewer_index.shtml?id=221430","http://218.219.195.243:8080/MultiCameraFrame?Mode=Motion&Language=0","http://193.138.213.169/Cgi?page=Single&Mode=Motion&Language=9","http://pendelcam.kip.uni-heidelberg.de/view/viewer_index.shtml?id=170059", "http://iut-info.univ-reims.fr/view/", "http://webcam.geodan.nl/", "http://flightcam2.pr.erau.edu/view/index.shtml", "http://67.53.162.163/index4.html", "http://200.36.58.250/view/index.shtml", "http://217.7.66.54/axis-cgi/mjpg/video.cgi?resolution=640x360&dummy=1423492017252", "http://200.36.58.250/view/index.shtml"],
                "USA_OTHER":         ["http://129.15.81.9:8080/webcam.html","http://208.65.20.83/axis-cgi/mjpg/video.cgi?resolution=4cif&dummy=1344350498922","http://193.90.139.222:33450/axis-cgi/mjpg/video.cgi?resolution=800x450","http://62.168.0.189/axis-cgi/mjpg/video.cgi?resolution=4CIF&camera=1&dummy=1277833957855","http://64.122.208.241:8000/axis-cgi/mjpg/video.cgi?camera=&resolution=320x240","http://storatorg.halmstad.se/axis-cgi/mjpg/video.cgi?resolution=1280x800&dummy=1433493481969","http://82.139.167.140:3131/view/index.shtml","http://avptcam.uconn.edu/view/index.shtml","http://webcam.thealgonquin.com:8080/view/index.shtml","http://200.79.225.81:8080/view/view.shtml?id=608&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                              
                        
                        
   
                "RUSSIA":           ["http://92.50.128.90/axis-cgi/mjpg/video.swf?resolution=640x480&compression=30&dummy=1275773919735","http://212.42.54.137:8008/view/index.shtml","http://195.113.207.238/view/index.shtml","http://www.vladimir-city.ru:8080/view/index.shtml","http://myndavel.ma.is/view/index.shtml","http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288","http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882","http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056","http://195.235.198.107:3344/view/index.shtml","http://80.38.183.149:2000/view/index.shtml","http://camera.butovo.com/view/index.shtml","http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1","http://213.196.182.244/view/index.shtml","http://195.74.79.83:30/view/index.shtml"],
                "ISVERC":           ["http://wc-heli.chuv.ch/view/view.shtml","http://webcam-1.faxa.rvk.is/view/index.shtml","http://lv.raad.tartu.ee:10201/view/index.shtml","http://200.36.58.250/view/view.shtml?id=62&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://195.196.36.242/view/index.shtml","http://71.248.101.58:50001/CgiStart?page=Single&Language=0","http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1","http://lv.raad.tartu.ee:10201/view/index.shtml","http://200.36.58.250/view/view.shtml?id=62&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://195.196.36.242/view/index.shtml","http://71.248.101.58:50001/CgiStart?page=Single&Language=0","http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "HOLLAND":          ["http://loeffingencam.selfhost.eu/view/view.shtml?id=174&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://80.94.55.92/view/index.shtm"],
                "ITALY":            ["http://camera.hcc.govt.nz/view/view.shtml","http://roccabella.asuscomm.com:9091/view/view.shtml?id=577&imagePath=/mjpg/video.mjpg&size=8&camera=1","http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288","http://83.61.22.4:8080/view/viewer_index.shtml?id=0","http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882","http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056","http://195.235.198.107:3344/view/index.shtml","http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "GERMANY":          ["http://217.22.201.135/view/viewer_index.shtml?id=17222","http://webcam.ampere.inpg.fr/view/index.shtml","http://87.54.59.228/view/viewer_index.shtml?id=193","http://217.30.178.109:46744/view/index.shtml","http://217.78.137.43/view/index.shtml","http://cam.hintertuxerhof.at/view/index.shtml","http://webcam.eins-energie.de/view/index.shtml","http://217.22.201.135/view/viewer_index.shtml?id=17222","http://87.54.59.228/view/viewer_index.shtml?id=193","http://217.30.178.109:46744/view/index.shtml","http://tornet.no-ip.org/view/index.shtml","http://94.125.79.44/view/index.shtml","http://livecam.norran.se/view/viewer_index.shtml?id=34342"]
               
   
    },
    "DATABANK": {
        "Netrunner":   ["https://nullsignal.games","https://netrunnerdb.com",
                        "https://jinteki.net","https://stimhack.com"],
        "Cyberpunk":   ["https://cyberpunkred.com/","https://cyberpunkred.fandom.com/wiki/Cyberpunk_Red"],
        "Security":    ["https://krebsonsecurity.com","https://nmap.org",
                        "https://shodan.io","https://kali.org"],
        "Linux_Open":  ["http://gnu.org","http://kernel.org","http://debian.org","http://archlinux.org"],
        "Tech_Reading":["https://techcrunch.com","https://www.wired.com",
                        "https://arstechnica.com","https://news.ycombinator.com"],
        "Daemon_Novel":["https://en.wikipedia.org/wiki/Daemon_(novel)",
                        "https://www.goodreads.com/book/show/4699570-daemon"],
        "Books":       ["https://www.goodreads.com","https://www.openlibrary.org"],
    },
}

import webbrowser as _wb
_MODULE_META = {
    "DSPACE":   {"label":"DSPACE",   "desc":"Academic Repository Network",  "accent":"#66FFCC"},
    "FTP":      {"label":"FTP",      "desc":"Global FTP Mirror Network",     "accent":"#66FFCC"},
    "CAMS":     {"label":"EYE",      "desc":"Open Camera Network",           "accent":"#66FFCC"},
    "DATABANK": {"label":"DATABANK", "desc":"Link Library",                  "accent":"#66FFCC"},
}


# ─────────────────────────────────────────────
#  NODE MANAGER  (v1 logic + Ollama fallback)
# ─────────────────────────────────────────────
class NodeManager:
    """
    Dual-path router:
      1. Keyword match via DialogBase → original handlers (weather, news, applets…)
      2. No match → Ollama inference → AwardEngine evaluation
    """
    def __init__(self, username="User", ui=None):
        self.username     = username
        self.ui           = ui
        self.dialog       = DialogBase(username)
        self.ollama       = OllamaClient()
        self.award_engine = AwardEngine()
        self.ol_history   : list = []   # Ollama conversation history
        self.turns        = 0
        self._streaming   = False
        self.system_prompt= DEFAULT_SYSTEM_PROMPT

        self.command_map = {
            "databank":      self._handle_databank,
        #   "navigation":    self._handle_navigation,
            "scan_external": self._handle_scan_external,
            "weather":       self._handle_weather,
            "news_general":  lambda d=None: self._handle_news(d, "general"),
            "news_tech":     lambda d=None: self._handle_news(d, "tech"),
            "news_security": lambda d=None: self._handle_news(d, "security"),
            "news_world":    lambda d=None: self._handle_news(d, "world"),
            "search":        self._handle_search,
            "time":          self._handle_time,
            "dspace":        self._handle_dspace,
            "ftp":           self._handle_ftp,
            "eye":           self._handle_eye,
            "cyberstorm":    self._handle_cyberstorm,
            "exit":          self._handle_exit,
        }

    # ── Public entry point ────────────────────
    def process_input(self, user_input: str):
        """
        Synchronous path for keyword intents.
        For Ollama (open-ended), kicks off async inference and returns immediately.
        """
        rep = self.dialog.reply(user_input)

        if rep["matched"]:
            # Known intent — handle in background, return personality quip
            intent = rep.get("intent")
            if intent and intent in self.command_map:
                threading.Thread(
                    target=self.command_map[intent],
                    kwargs={"data": {"user_input": user_input}},
                    daemon=True
                ).start()
            return rep["text"]

        else:
            # Unknown → route to Ollama
            if self._streaming:
                return "Still thinking... one moment."
            threading.Thread(
                target=self._ollama_worker,
                args=(user_input,),
                daemon=True
            ).start()
            return "⬡ Routing to reasoning engine..."

    # ── Ollama inference worker ───────────────
    def _ollama_worker(self, user_text: str):
        self._streaming = True
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.set_status("⬡ OLLAMA REASONING…"))

        try:
            if not self.ollama.is_running():
                raise RuntimeError(
                    "Ollama offline. Start with: ollama serve\n"
                    "Then pull: ollama pull llama3.2:1b"
                )

            self.ol_history.append({"role": "user", "content": user_text})
            msgs = self.ol_history[-16:]

            # Prepare stream slot in UI
            if self.ui:
                self.ui.root.after(0, self.ui.begin_stream_slot)

            t0 = time.time()
            full_response = self.ollama.chat(
                messages       = msgs,
                system         = self.system_prompt,
                temperature    = getattr(self.ui, 'temp_var', None) and self.ui.temp_var.get() or 0.7,
                stream_callback= (lambda tok: self.ui.root.after(0, lambda t=tok: self.ui.append_stream_token(t)))
                                  if self.ui else None,
            )
            elapsed = round(time.time() - t0, 1)

            self.ol_history.append({"role": "assistant", "content": full_response})
            if len(self.ol_history) > 24:
                self.ol_history = self.ol_history[-24:]

            self.turns += 1
            result = self.award_engine.evaluate(user_text, full_response)

            if self.ui:
                self.ui.root.after(0, lambda: self.ui.end_stream_slot(result, elapsed))
                self.ui.root.after(0, self.ui.update_side_panel)
                self.ui.root.after(0, lambda: self.ui.set_status(
                    f"Turn {self.turns} | Score: {result['score']:+.1f} | "
                    f"Total: {self.award_engine.total_score:+.1f} | "
                    f"{elapsed}s | {self.ollama.model}"
                ))

        except RuntimeError as e:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys(f"ENGINE ERROR: {e}"))
                self.ui.root.after(0, lambda: self.ui.set_status("Ollama offline"))
        except Exception as e:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys(f"ERROR: {e}"))
        finally:
            self._streaming = False
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.send_btn.config(state="normal"))

    # ── Background helper ─────────────────────
    def _bg(self, fn, *a, **kw):
        threading.Thread(target=fn, args=a, kwargs=kw, daemon=True).start()

    # ── Intent handlers (v1 unchanged) ────────
    def _handle_databank(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(DataLibApplet))

#    def _handle_navigation(self, data=None):
#        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(NavigationApplet))

    def _handle_dspace(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(DspaceApplet))

    def _handle_ftp(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(FTPApplet))

    def _handle_eye(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(EyeApplet))

    def _handle_scan_external(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[Scanner] External scan tool planned for later stages.")) #TODO: Replace this with toolsets on the net edc folder

    def _handle_exit(self, data=None):
        if self.ui: self.ui.root.after(0, self.ui.safe_exit)

    def _handle_time(self, data=None):
        t = datetime.now().strftime("%H:%M:%S")
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", f"Current time: {t}", "ai"))

    def _handle_cyberstorm(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[CYBERSTORM] Opening all camera feeds..."))
            count = 0
            for region, urls in REGISTRY["CAMS"].items():
                for u in urls:
                    _wb.open(u); count += 1
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[CYBERSTORM] {count} feeds opened."))

    def _handle_weather(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[DILARA] Fetching weather..."))
            self._bg(self._weather_worker)

    def _weather_worker(self):
        try:
            data = WeatherService.fetch()
            text = WeatherService.format_result(data, WeatherService.DEFAULT_CITY)
        except Exception as e:
            text = f"[Weather] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))

    def _handle_news(self, data=None, category="general"):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[DILARA] Fetching {category} news..."))
            self._bg(self._news_worker, category)

    def _news_worker(self, category):
        try:
            items = RSSService.fetch(category)
            text  = RSSService.format_result(items, category)
        except Exception as e:
            text = f"[RSS] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))

    def _handle_search(self, data=None):
        raw   = (data or {}).get("user_input", "")
        query = SearchService.extract_query(raw)
        if not query:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys("[Search] What should I search for?"))
            return
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[DILARA] Searching: {query}..."))
            self._bg(self._search_worker, query)

    def _search_worker(self, query):
        try:
            engine_name, items = SearchService.search(query)
            text = SearchService.format_result(engine_name, items, query)
        except Exception as e:
            text = f"[Search] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))


# ─────────────────────────────────────────────
#  REGISTRY APPLETS  (v1 — unchanged)
# ─────────────────────────────────────────────
class RegistryApplet(tk.Frame):
    REGISTRY_KEY = None
    ACCENT = "#66FFCC"; BG = "#161616"; BG_DARK = "#0e0e0e"; BG_HOVER = "#1e2e2e"
    _module = None; _region = None

    def __init__(self, parent, ui=None):
        super().__init__(parent, bg=self.BG)
        self.ui = ui
        self._module = self.REGISTRY_KEY
        self._region = None
        self._build_shell()
        self._navigate()

    def _build_shell(self):
        top = tk.Frame(self, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6,0))
        self._crumb_var = tk.StringVar(value="Main Menu")
        tk.Label(top, textvariable=self._crumb_var, fg=self.ACCENT, bg=self.BG,
                 font=(C["font"],9,"bold"), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(top, text="X", bg="#2a2a2a", fg=self.ACCENT, font=(C["font"],8,"bold"),
                  relief="flat", width=3, command=self._close).pack(side="right")
        tk.Frame(self, bg=self.ACCENT, height=1).pack(fill="x", padx=8, pady=(3,0))
        self._content = tk.Frame(self, bg=self.BG)
        self._content.pack(fill="both", expand=True, padx=8, pady=6)
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, fg="#666", bg=self.BG,
                 font=(C["font"],8), anchor="w").pack(fill="x", padx=10, pady=(0,4))

    def _clear_content(self):
        for w in self._content.winfo_children(): w.destroy()

    def _navigate(self, module=None, region=None):
        self._module = module if module is not None else self._module
        self._region = region
        self._clear_content()
        self._update_crumb()
        if self._module is None:     self._show_root()
        elif self._region is None:   self._show_regions()
        else:                        self._show_urls()

    def _update_crumb(self):
        parts = ["Main Menu"]
        if self._module:
            parts.append(_MODULE_META.get(self._module,{}).get("label",self._module))
        if self._region: parts.append(self._region)
        self._crumb_var.set("  >  ".join(parts))

    def _go_back(self):
        if self._region is not None:   self._navigate(module=self._module, region=None)
        elif self._module is not None: self._navigate(module=None, region=None)

    def _show_root(self):
        self._status_var.set("Select a module to browse.")
        tk.Label(self._content, text="[ DILARA REGISTRY ]", fg=self.ACCENT, bg=self.BG,
                 font=(C["font"],11,"bold")).pack(pady=(4,10))
        grid = tk.Frame(self._content, bg=self.BG)
        grid.pack(fill="both", expand=True)
        for i, (key, meta) in enumerate(sorted(_MODULE_META.items())):
            if key not in REGISTRY: continue
            col = i % 2; row = i // 2
            count   = sum(len(v) for v in REGISTRY[key].values())
            regions = len(REGISTRY[key])
            tile = tk.Frame(grid, bg="#1a2a2a", highlightbackground=self.ACCENT, highlightthickness=1)
            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            tk.Label(tile, text=meta["label"],  fg=self.ACCENT, bg="#1a2a2a", font=(C["font"],11,"bold")).pack(anchor="w",padx=8,pady=(6,1))
            tk.Label(tile, text=meta["desc"],   fg="#aaa",       bg="#1a2a2a", font=(C["font"],8)).pack(anchor="w",padx=8)
            tk.Label(tile, text=f"{regions} regions  |  {count} links", fg="#555", bg="#1a2a2a", font=(C["font"],7)).pack(anchor="w",padx=8,pady=(1,6))
            tile.bind("<Button-1>",   lambda e,k=key: self._navigate(module=k,region=None))
            for ch in tile.winfo_children():
                ch.bind("<Button-1>", lambda e,k=key: self._navigate(module=k,region=None))
            tile.bind("<Enter>", lambda e,t=tile: t.config(bg=self.BG_HOVER))
            tile.bind("<Leave>", lambda e,t=tile: t.config(bg="#1a2a2a"))

    def _show_regions(self):
        data = REGISTRY.get(self._module,{}); meta = _MODULE_META.get(self._module,{})
        self._status_var.set(f"{len(data)} regions available. Click to expand.")
        nav = tk.Frame(self._content,bg=self.BG); nav.pack(fill="x",pady=(0,6))
        tk.Button(nav,text="< Back",bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),
                  relief="flat",command=self._go_back).pack(side="left")
        tk.Label(nav,text=meta.get("desc",""),fg="#888",bg=self.BG,font=(C["font"],8)).pack(side="left",padx=8)
        canvas = tk.Canvas(self._content,bg=self.BG,highlightthickness=0)
        sb = tk.Scrollbar(self._content,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); canvas.pack(side="left",fill="both",expand=True)
        inner = tk.Frame(canvas,bg=self.BG)
        win_id = canvas.create_window((0,0),window=inner,anchor="nw")
        canvas.bind("<Configure>",lambda e:canvas.itemconfig(win_id,width=e.width))
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        for region,urls in data.items():
            row = tk.Frame(inner,bg="#111",highlightbackground="#2a2a2a",highlightthickness=1)
            row.pack(fill="x",pady=2,padx=2)
            tk.Label(row,text=f"  {region}",fg=self.ACCENT,bg="#111",font=(C["font"],9,"bold"),anchor="w",width=18).pack(side="left",padx=(4,0),pady=4)
            tk.Label(row,text=f"{len(urls)} links",fg="#555",bg="#111",font=(C["font"],8)).pack(side="left",padx=6)
            tk.Label(row,text=">",fg=self.ACCENT,bg="#111",font=(C["font"],10,"bold")).pack(side="right",padx=8)
            row.bind("<Button-1>",lambda e,r=region:self._navigate(module=self._module,region=r))
            for ch in row.winfo_children():
                ch.bind("<Button-1>",lambda e,r=region:self._navigate(module=self._module,region=r))
            row.bind("<Enter>",lambda e,f=row:f.config(bg=self.BG_HOVER))
            row.bind("<Leave>",lambda e,f=row:f.config(bg="#111"))

    def _show_urls(self):
        urls = REGISTRY.get(self._module,{}).get(self._region,[])
        self._status_var.set(f"{len(urls)} links. Double-click to open.")
        nav = tk.Frame(self._content,bg=self.BG); nav.pack(fill="x",pady=(0,4))
        tk.Button(nav,text="< Back",bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),relief="flat",command=self._go_back).pack(side="left")
        btn_row = tk.Frame(self._content,bg=self.BG); btn_row.pack(fill="x",pady=(0,4))
        tk.Button(btn_row,text="Open Selected",bg=self.ACCENT,fg="#000",font=(C["font"],8,"bold"),command=self._open_selected).pack(side="left",padx=(0,6))
        tk.Button(btn_row,text="Open All",     bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),command=self._open_all).pack(side="left")
        self._url_lb = tk.Listbox(self._content,bg=self.BG_DARK,fg="#E5FFE5",
                                  selectbackground="#1a2a2a",activestyle="none",
                                  font=(C["font"],8),relief="flat",borderwidth=0)
        sb = tk.Scrollbar(self._content,orient="vertical",command=self._url_lb.yview)
        self._url_lb.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); self._url_lb.pack(fill="both",expand=True)
        for u in urls: self._url_lb.insert(tk.END,f"  {u}")
        self._url_lb.bind("<Double-Button-1>",self._open_selected)

    def _open_selected(self,event=None):
        if not hasattr(self,"_url_lb"): return
        sel = self._url_lb.curselection()
        if not sel: return
        url = self._url_lb.get(sel[0]).strip(); _wb.open(url)
        self._status_var.set(f"Opened: {url[:60]}")

    def _open_all(self):
        if not hasattr(self,"_url_lb"): return
        urls = [self._url_lb.get(i).strip() for i in range(self._url_lb.size())]
        for u in urls: _wb.open(u)
        self._status_var.set(f"Opened {len(urls)} links")

    def _close(self):
        for w in self.master.winfo_children(): w.destroy()


class DspaceApplet(RegistryApplet):  REGISTRY_KEY = "DSPACE"
class FTPApplet(RegistryApplet):     REGISTRY_KEY = "FTP"
class EyeApplet(RegistryApplet):     REGISTRY_KEY = "CAMS"
class DataLibApplet(RegistryApplet): REGISTRY_KEY = "DATABANK"


# class NavigationApplet(tk.Frame):
#    def __init__(self, parent, ui=None):
#        super().__init__(parent, bg="#161616"); self.ui = ui; self._build()

#    def _build(self):
#        hdr = tk.Frame(self,bg="#161616"); hdr.pack(fill="x",padx=8,pady=8)
#         tk.Label(hdr,text="Navigation",fg="#66FFCC",bg="#161616",font=(C["font"],12,"bold")).pack(side="left")
#         mid = tk.Frame(self,bg="#161616"); mid.pack(fill="x",padx=8,pady=4)
#    tk.Label(mid,text="Destination:",fg="#E5FFE5",bg="#161616",font=(C["font"],10,"bold")).pack(side="left")
#        self.dest_var = tk.StringVar()
#        tk.Entry(mid,textvariable=self.dest_var,width=24,bg="#141414",fg="#E5FFE5",
#                insertbackground="#66FFCC",font=(C["font"],10,"bold")).pack(side="left",padx=6)
#        btns = tk.Frame(self,bg="#161616"); btns.pack(fill="x",padx=8,pady=6)
#        tk.Button(btns,text="Start",bg="#66FFCC",fg="#000",font=(C["font"],9,"bold"),command=self.start_route).pack(side="left",padx=4)
#        tk.Button(btns,text="Stop", bg="#aa4444",fg="#fff",font=(C["font"],9,"bold"),command=self.stop_route).pack(side="left",padx=4)
#        self.out = tk.Text(self,height=6,bg="#0e0e0e",fg="#E5FFE5",insertbackground="#66FFCC",
#                           state="disabled",font=(C["font"],10,"bold"))
#        self.out.pack(fill="both",expand=True,padx=8,pady=(2,8))

#   def start_route(self):
#        dest = self.dest_var.get().strip() or "Unknown"
#        self._append(f"Route to {dest} initialized.")
#        for s in ["Head north 50m","Turn right","Go 10m","Destination on your left"]: self._append(f"• {s}")

#   def stop_route(self): self._append("Route cancelled.")

#   def _append(self,txt):
#        self.out.config(state="normal"); self.out.insert(tk.END,txt+"\n"); self.out.see(tk.END); self.out.config(state="disabled")


# ─────────────────────────────────────────────
#  MAIN UI  (v1 layout + v2 side panel)
# ─────────────────────────────────────────────
class ChatUI:
    def __init__(self, root, username="User"):
        self.root         = root
        self.username     = username
        self._stream_active = False

        self.root.title(APP_TITLE)
        self.root.geometry(DEFAULT_GEOMETRY)
        self.root.configure(bg=C["bg"])
        try: self.root.attributes('-alpha', WINDOW_ALPHA)
        except: pass
        try: self.root.option_add("*Font", (C["font"], 10, "bold"))
        except: pass

        # Managers
        self.node_manager = NodeManager(username, ui=self)
        self.voice_manager= VoiceManager(VOICES_DIR)
        self.last_bot_message = ""

        self._build_layout()
        self._check_ollama_status()

    # ─────────── LAYOUT ──────────────────────
    def _build_layout(self):
        # Outer paned: left (chat) + right (side panel)
        paned = tk.PanedWindow(self.root, orient="horizontal",
                               bg=C["bg"], sashwidth=4, bd=0, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Left: original D.I.L.A.R.A. card
        left = tk.Frame(paned, bg=C["glass"],
                        highlightbackground=C["accent"], highlightthickness=1)
        paned.add(left, minsize=460, width=560)

        # ── Right: sandbox side panel
        right = tk.Frame(paned, bg=C["panel"])
        paned.add(right, minsize=280, width=360)

        self._build_left(left)
        self._build_right(right)

        # Status bar (bottom)
        self.status_var = tk.StringVar(value="READY")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=C["panel"], fg=C["muted"],
                 font=(C["font_mono"],9), anchor="w", padx=12, pady=3
                 ).pack(fill="x", side="bottom")

    # ── LEFT PANEL ────────────────────────────
    def _build_left(self, parent):
        # Header (greeting + profile + voice)
        hdr = tk.Frame(parent, bg=C["glass"], height=150)
        hdr.pack(fill="x", pady=(6,0))

        greeting = self.node_manager.dialog.greet()
        tk.Label(hdr, text=greeting, font=(C["font"],12,"bold"),
                 fg=C["accent"], bg=C["glass"],
                 wraplength=380, justify="center").pack(pady=(6,4))

        pic_frame = tk.Frame(hdr, width=80, height=80, bg="#222")
        pic_frame.pack(pady=2)
        self._load_profile_picture(pic_frame, "profile.png")

        tk.Button(hdr, text="?", font=(C["font"],10,"bold"),
                  bg=C["accent"], fg="#000", width=2,
                  command=self.show_about).place(x=460, y=6)

        if self.voice_manager and self.voice_manager.available_names:
            ctl = tk.Frame(hdr, bg=C["glass"]); ctl.pack(pady=(2,2))
            tk.Label(ctl, text="Voice:", fg=C["text"], bg=C["glass"],
                     font=(C["font"],10,"bold")).pack(side="left")
            self.voice_var = tk.StringVar(
                value=self.voice_manager.active_name or self.voice_manager.available_names[0]
            )
            cb = ttk.Combobox(ctl, textvariable=self.voice_var,
                              values=self.voice_manager.available_names,
                              width=22, state="readonly")
            cb.pack(side="left", padx=6)
            cb.bind("<<ComboboxSelected>>", self._on_voice_select)

        # Chat area
        chat_frame = tk.Frame(parent, bg=C["bg"])
        chat_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.chat_box = scrolledtext.ScrolledText(
            chat_frame, wrap="word",
            bg=C["bg"], fg=C["text"],
            insertbackground=C["accent"],
            font=(C["font"],10,"bold"),
            state="disabled", borderwidth=0,
            highlightthickness=0, padx=8, pady=6,
        )
        self.chat_box.pack(fill="both", expand=True)
        self.chat_box.tag_config("user",    justify="right",  foreground=C["user_fg"])
        self.chat_box.tag_config("ai",      justify="left",   foreground=C["ai_fg"])
        self.chat_box.tag_config("ai_stream",justify="left",  foreground=C["ai_fg"])
        self.chat_box.tag_config("sys",     justify="center", foreground=C["sys_fg"])
        self.chat_box.tag_config("eval_pos",foreground=C["score_pos"], font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_neg",foreground=C["score_neg"], font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_neu",foreground=C["accent2"],   font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_tot",foreground=C["accent"],    font=(C["font_mono"],8,"bold"))
        self.chat_box.tag_config("theorem", foreground=C["good"],      font=(C["font_mono"],8,"bold"))

        # Applet frame
        self.applet_frame = tk.Frame(parent, bg=C["glass"], height=160)
        self.applet_frame.pack(fill="x", padx=6, pady=2)

        # Input row
        ibar = tk.Frame(parent, bg=C["panel"])
        ibar.pack(fill="x", padx=6, pady=(2,8))

        self.input_entry = tk.Entry(
            ibar, font=(C["font"],10,"bold"),
            bg="#141414", fg=C["text"],
            insertbackground=C["accent"],
            width=30,
        )
        self.input_entry.pack(side="left", padx=(6,4), pady=8)
        self.input_entry.bind("<Return>", self.send_message)
        self.input_entry.focus()

        self.send_btn = tk.Button(
            ibar, text="Send", font=(C["font"],10,"bold"),
            bg=C["accent"], fg="#000", width=6,
            command=self.send_message,
            activebackground="#00e0a0",
        )
        self.send_btn.pack(side="left", padx=(0,4))

        tk.Button(ibar, text="🔊", font=(C["font"],12,"bold"),
                  width=3, bg=C["accent"], fg="#000",
                  command=self.speak_last_message).pack(side="left", padx=(0,4))
        tk.Button(ibar, text="🎤", font=(C["font"],12,"bold"),
                  width=3, bg=C["accent"], fg="#000",
                  command=self.listen_speech).pack(side="left")

        # TTS sliders
        if self.voice_manager and self.voice_manager.engine:
            sl = tk.Frame(ibar, bg=C["panel"]); sl.pack(side="right", padx=6)
            tk.Label(sl,text="Rate",bg=C["panel"],fg=C["text"],font=(C["font"],9,"bold")).grid(row=0,column=0,padx=2)
            self.rate_var = tk.IntVar(value=self.voice_manager.active_rate or
                                     self.voice_manager.engine.getProperty('rate') or 200)
            tk.Scale(sl,from_=50,to=300,orient="horizontal",length=100,
                     bg=C["panel"],highlightthickness=0,troughcolor="#222",fg=C["text"],
                     command=self._on_rate,variable=self.rate_var).grid(row=0,column=1)
            tk.Label(sl,text="Vol",bg=C["panel"],fg=C["text"],font=(C["font"],9,"bold")).grid(row=1,column=0,padx=2)
            self.vol_var = tk.DoubleVar(value=self.voice_manager.active_volume
                                        if self.voice_manager.active_volume is not None else 1.0)
            tk.Scale(sl,from_=0.0,to=1.0,resolution=0.05,orient="horizontal",length=100,
                     bg=C["panel"],highlightthickness=0,troughcolor="#222",fg=C["text"],
                     command=self._on_vol,variable=self.vol_var).grid(row=1,column=1)

    # ── RIGHT SIDE PANEL ─────────────────────
    def _build_right(self, parent):
        canvas = tk.Canvas(parent, bg=C["panel"], highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self._side_inner = tk.Frame(canvas, bg=C["panel"])
        self._side_inner.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self._side_inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(fill="both", expand=True)

        def _sec(title):
            tk.Label(self._side_inner, text=f"⬡  {title}",
                     bg=C["panel"], fg=C["muted"],
                     font=(C["font_mono"],8,"bold"), anchor="w"
                     ).pack(fill="x", padx=10, pady=(12,2))
            tk.Frame(self._side_inner, bg=C["border"], height=1).pack(fill="x", padx=10)

        # Score
        _sec("AWARD SCORE")
        self.score_var = tk.StringVar(value="+0")
        tk.Label(self._side_inner, textvariable=self.score_var,
                 bg=C["panel"], fg=C["accent"],
                 font=(C["font_mono"],30,"bold")).pack(pady=(4,0))
        tk.Label(self._side_inner, text="CUMULATIVE REWARD",
                 bg=C["panel"], fg=C["muted"], font=(C["font_mono"],8)).pack()
        bar_frame = tk.Frame(self._side_inner, bg=C["border"], height=4)
        bar_frame.pack(fill="x", padx=14, pady=6); bar_frame.pack_propagate(False)
        self.score_bar = tk.Frame(bar_frame, bg=C["accent"], height=4)
        self.score_bar.place(x=0, y=0, relwidth=0.5, relheight=1.0)

        # Metrics
        _sec("METRICS")
        mf = tk.Frame(self._side_inner, bg=C["panel"]); mf.pack(fill="x", padx=10, pady=4)
        self.m_vars = {}
        for key, label in [("turns","TURNS"),("theorems","THEOREMS"),
                            ("conjectures","CONJECTURES"),("avg","AVG SCORE")]:
            row = tk.Frame(mf, bg=C["panel"]); row.pack(fill="x", pady=1)
            tk.Label(row,text=label,bg=C["panel"],fg=C["muted"],
                     font=(C["font_mono"],9),width=14,anchor="w").pack(side="left")
            v = tk.StringVar(value="0" if key!="avg" else "—"); self.m_vars[key]=v
            tk.Label(row,textvariable=v,bg=C["panel"],fg=C["accent2"],
                     font=(C["font_mono"],9,"bold")).pack(side="right")

        # Theory Base
        _sec("THEORY BASE")
        self.theory_box = tk.Text(self._side_inner, bg=C["bg"], fg=C["text"],
                                  font=(C["font_mono"],8), height=9, wrap="word",
                                  state="disabled", relief="flat",
                                  highlightthickness=0, padx=6, pady=4)
        self.theory_box.pack(fill="x", padx=10, pady=4)
        self.theory_box.tag_config("theorem_t",    foreground=C["good"])
        self.theory_box.tag_config("conjecture_t", foreground=C["accent2"])
        self.theory_box.tag_config("ts_t",         foreground=C["muted"])

        # Award weight sliders
        _sec("AWARD WEIGHTS")
        wf = tk.Frame(self._side_inner, bg=C["panel"]); wf.pack(fill="x", padx=10, pady=4)
        self.weight_vars = {}
        for key,label,mn,mx,default,res in [
            ("novelty",   "NOVELTY",     0,20,10,1.0),
            ("parsimony", "PARSIMONY",   0, 3,0.5,0.1),
            ("depth",     "DEPTH",       0,15, 5,1.0),
            ("grounding", "GROUNDING",   0,20, 8,1.0),
            ("action",    "ACTION",      0,10, 3,1.0),
        ]:
            row=tk.Frame(wf,bg=C["panel"]); row.pack(fill="x",pady=2)
            val_var=tk.DoubleVar(value=default); self.weight_vars[key]=val_var
            val_lbl=tk.Label(row,textvariable=val_var,bg=C["panel"],fg=C["accent"],
                             font=(C["font_mono"],8),width=5,anchor="e"); val_lbl.pack(side="right")
            tk.Label(row,text=label,bg=C["panel"],fg=C["muted"],
                     font=(C["font_mono"],8),width=12,anchor="w").pack(side="left")
            def _upd(v,k=key,var=val_var):
                self.node_manager.award_engine.weights[k]=round(float(v),2); var.set(round(float(v),2))
            tk.Scale(row,from_=mn,to=mx,resolution=res,orient="horizontal",variable=val_var,
                     bg=C["panel"],fg=C["text"],troughcolor=C["border"],
                     activebackground=C["accent"],highlightthickness=0,
                     showvalue=False,length=80,command=_upd).pack(side="right",padx=(0,4))

        # Ollama status + model selector
        _sec("OLLAMA / MODEL")
        om = tk.Frame(self._side_inner, bg=C["panel"]); om.pack(fill="x", padx=10, pady=4)
        self.ollama_lbl = tk.Label(om, text="● CHECKING…", bg=C["panel"], fg=C["warn"],
                                   font=(C["font_mono"],9,"bold")); self.ollama_lbl.pack(anchor="w")
        tk.Label(om,text="MODEL",bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8)).pack(anchor="w",pady=(6,0))
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.model_combo = ttk.Combobox(om, textvariable=self.model_var,
                                        values=[DEFAULT_MODEL], state="readonly", width=22,
                                        font=(C["font_mono"],9))
        self.model_combo.pack(fill="x", pady=2)
        self.model_combo.bind("<<ComboboxSelected>>",
                              lambda e: setattr(self.node_manager.ollama, 'model', self.model_var.get()))

        def _btn(t, cmd):
            tk.Button(om,text=t,command=cmd,bg=C["panel"],fg=C["accent2"],
                      font=(C["font_mono"],8,"bold"),relief="flat",cursor="hand2",
                      highlightthickness=1,highlightbackground=C["border"],pady=3
                      ).pack(fill="x",pady=2)
        _btn("↺ REFRESH MODELS", self._refresh_models)
        _btn("⬇ PULL MODEL",     self._pull_model_dialog)

        tk.Label(om,text="TEMPERATURE",bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8)).pack(anchor="w",pady=(8,0))
        self.temp_var = tk.DoubleVar(value=0.7)
        tr = tk.Frame(om,bg=C["panel"]); tr.pack(fill="x")
        tk.Scale(tr,from_=0.0,to=2.0,resolution=0.05,orient="horizontal",variable=self.temp_var,
                 bg=C["panel"],fg=C["text"],troughcolor=C["border"],
                 activebackground=C["accent"],highlightthickness=0,length=120).pack(side="left")
        tk.Label(tr,textvariable=self.temp_var,bg=C["panel"],fg=C["accent"],
                 font=(C["font_mono"],9),width=4).pack(side="left")

        # System prompt
        _sec("REASONING CONTEXT")
        self.sys_text = tk.Text(self._side_inner, bg=C["bg"], fg=C["text"],
                                font=(C["font_mono"],8), height=8, wrap="word",
                                relief="flat", highlightthickness=1,
                                highlightcolor=C["accent2"],
                                highlightbackground=C["border"], padx=6, pady=4)
        self.sys_text.insert("1.0", DEFAULT_SYSTEM_PROMPT)
        self.sys_text.pack(fill="x", padx=10, pady=4)

        cf = tk.Frame(self._side_inner,bg=C["panel"]); cf.pack(fill="x",padx=10)
        tk.Button(cf,text="APPLY CONTEXT",command=self._apply_system,
                  bg=C["panel"],fg=C["accent2"],font=(C["font_mono"],8,"bold"),
                  relief="flat",highlightthickness=1,highlightbackground=C["border"],
                  pady=3).pack(fill="x",pady=2)
        tk.Button(cf,text="CLEAR SESSION",command=self._clear_session,
                  bg=C["panel"],fg=C["score_neg"],font=(C["font_mono"],8,"bold"),
                  relief="flat",highlightthickness=1,highlightbackground=C["score_neg"],
                  pady=3).pack(fill="x",pady=2)

    # ─────────── CHAT DISPLAY ────────────────
    def _write(self, text, tag=None):
        self.chat_box.config(state="normal")
        if tag: self.chat_box.insert(tk.END, text, tag)
        else:   self.chat_box.insert(tk.END, text)
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")

    def append_chat(self, sender, message, tag="ai"):
        self._write(f"{sender}: {message}\n", tag)
        if tag == "ai":
            self.last_bot_message = message

    def append_sys(self, message):
        self.append_chat("System", message, tag="sys")

    def status_to_chat(self, message):
        self.append_sys(message)

    def begin_stream_slot(self):
        self._write("\nD.I.L.A.R.A.: ", "ai")
        self._stream_active = True

    def append_stream_token(self, token):
        if self._stream_active:
            self._write(token, "ai_stream")

    def end_stream_slot(self, result, elapsed):
        self._stream_active = False
        self._write("\n", "ai")
        # Show eval breakdown
        tag_map = {"pos":"eval_pos","neg":"eval_neg","neu":"eval_neu"}
        for label, kind in result["breakdown"]:
            self._write(f"[{label}] ", tag_map.get(kind,"eval_neu"))
        self._write(f"  TOTAL: {result['score']:+.1f}  ·  {elapsed}s\n", "eval_tot")
        if result.get("promotion"):
            p = result["promotion"]
            tag = "theorem" if p["type"]=="THEOREM" else "eval_neu"
            self._write(f"⬡ {p['type']} REGISTERED — score {p['score']:+.1f}\n", tag)

    def set_status(self, msg):
        self.status_var.set(msg)

    # ─────────── SEND ────────────────────────
    def send_message(self, event=None):
        user_text = self.input_entry.get().strip()
        if not user_text: return
        self.append_chat(self.username, user_text, "user")
        self.input_entry.delete(0, tk.END)
        self.send_btn.config(state="disabled")

        bot_text = self.node_manager.process_input(user_text)
        if bot_text:
            self.append_chat("D.I.L.A.R.A.", bot_text, "ai")

        # Re-enable unless Ollama worker is streaming
        if not self.node_manager._streaming:
            self.send_btn.config(state="normal")

    # ─────────── SIDE PANEL UPDATE ───────────
    def update_side_panel(self):
        ae    = self.node_manager.award_engine
        total = ae.total_score
        self.score_var.set(f"{total:+.1f}" if total != 0 else "+0")
        pct = min(1.0, max(0.0, 0.5 + total / 120))
        self.score_bar.place(relwidth=pct)
        self.score_bar.config(bg=C["score_pos"] if total >= 0 else C["score_neg"])

        self.m_vars["turns"].set(str(self.node_manager.turns))
        self.m_vars["theorems"].set(str(len(ae.theorems)))
        self.m_vars["conjectures"].set(str(len(ae.conjectures)))
        avg = ae.score_history
        self.m_vars["avg"].set(f"{sum(avg)/len(avg):+.1f}" if avg else "—")

        # Theory Base
        all_e = ([("THEOREM",e) for e in ae.theorems[-4:]] +
                 [("CONJECTURE",e) for e in ae.conjectures[-4:]])
        all_e.sort(key=lambda x: x[1]["ts"], reverse=True)
        self.theory_box.config(state="normal")
        self.theory_box.delete("1.0", tk.END)
        if not all_e:
            self.theory_box.insert(tk.END, "Empty — awaiting first proof\n", "ts_t")
        for t_type, entry in all_e[:6]:
            col = "theorem_t" if t_type=="THEOREM" else "conjecture_t"
            self.theory_box.insert(tk.END,
                f"[{t_type}] {entry['score']:+.1f}  @{entry['ts']}\n", col)
            self.theory_box.insert(tk.END, f"  {entry['text']}\n", "ts_t")
        self.theory_box.config(state="disabled")

    # ─────────── OLLAMA MANAGEMENT ───────────
    def _check_ollama_status(self):
        def _check():
            running = self.node_manager.ollama.is_running()
            label   = "● OLLAMA: ONLINE" if running else "● OLLAMA: OFFLINE"
            color   = C["good"] if running else C["score_neg"]
            self.root.after(0, lambda: self.ollama_lbl.config(text=label, fg=color))
            if running:
                self.root.after(0, self._refresh_models)
                self.root.after(0, lambda: self.append_sys(
                    "Ollama detected. Reasoning engine armed. Try asking something open-ended."))
            else:
                self.root.after(0, lambda: self.append_sys(
                    "Ollama offline. Keyword commands still work.\n"
                    "Start Ollama: ollama serve | Pull: ollama pull llama3.2:1b"))
        threading.Thread(target=_check, daemon=True).start()

    def _refresh_models(self):
        def _work():
            models = self.node_manager.ollama.list_models()
            if models:
                self.root.after(0, lambda: self.model_combo.config(values=models))
                if DEFAULT_MODEL in models:
                    self.root.after(0, lambda: self.model_var.set(DEFAULT_MODEL))
                else:
                    self.root.after(0, lambda: self.model_var.set(models[0]))
                self.node_manager.ollama.model = self.model_var.get()
                self.root.after(0, lambda: self.append_sys(
                    f"Models: {', '.join(models)}"))
        threading.Thread(target=_work, daemon=True).start()

    def _pull_model_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Pull Model"); dlg.configure(bg=C["panel"])
        dlg.geometry("360x160"); dlg.resizable(False,False)
        tk.Label(dlg, text="Model name (e.g. llama3.2:1b, phi3:mini):",
                 bg=C["panel"],fg=C["text"],font=(C["font_mono"],9)).pack(padx=14,pady=(14,4),anchor="w")
        name_var = tk.StringVar(value="llama3.2:1b")
        tk.Entry(dlg,textvariable=name_var,bg=C["bg"],fg=C["text"],
                 font=(C["font_mono"],10),relief="flat",insertbackground=C["accent"]
                 ).pack(fill="x",padx=14)
        prog_var = tk.StringVar(value="Waiting…")
        tk.Label(dlg,textvariable=prog_var,bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8),wraplength=320).pack(padx=14,pady=4)
        def _do():
            model=name_var.get().strip()
            if not model: return
            prog_var.set(f"Pulling {model}…")
            def _work():
                ok,msg=self.node_manager.ollama.pull_model(model,
                    callback=lambda s: self.root.after(0,lambda ss=s:prog_var.set(ss[:60])))
                if ok:
                    self.root.after(0,lambda:self.append_sys(f"Pull complete: {model}"))
                    self.root.after(0,self._refresh_models)
                    self.root.after(0,dlg.destroy)
                else:
                    self.root.after(0,lambda:prog_var.set(f"FAILED: {msg[:50]}"))
            threading.Thread(target=_work,daemon=True).start()
        tk.Button(dlg,text="PULL",command=_do,bg=C["accent"],fg="#000",
                  font=(C["font_mono"],9,"bold"),relief="flat").pack(pady=6)

    # ─────────── CONTROLS ────────────────────
    def _apply_system(self):
        self.node_manager.system_prompt = self.sys_text.get("1.0","end").strip()
        self.node_manager.ol_history.clear()
        self.append_sys("Reasoning context updated. Ollama history cleared.")

    def _clear_session(self):
        if not messagebox.askyesno("Clear Session",
                                   "Reset Ollama history, theory base and scores?",
                                   parent=self.root):
            return
        self.node_manager.ol_history.clear()
        self.node_manager.award_engine.reset()
        self.node_manager.turns = 0
        self.score_var.set("+0")
        self.score_bar.place(relwidth=0.5)
        for k in self.m_vars: self.m_vars[k].set("0" if k!="avg" else "—")
        self.theory_box.config(state="normal"); self.theory_box.delete("1.0",tk.END)
        self.theory_box.insert(tk.END,"Empty — awaiting first proof\n","ts_t")
        self.theory_box.config(state="disabled")
        self.append_sys("Session cleared. Keyword commands still active.")

    def mount_applet(self, applet_class):
        for w in self.applet_frame.winfo_children(): w.destroy()
        app = applet_class(self.applet_frame, ui=self)
        app.pack(fill="both", expand=True)

    def speak_last_message(self):
        if not self.last_bot_message:
            messagebox.showinfo("TTS","No message to speak yet."); return
        if self.voice_manager:
            self.voice_manager.speak_async(self.last_bot_message)

    def _on_voice_select(self, evt=None):
        choice = getattr(self,"voice_var",None)
        if choice and self.voice_manager:
            self.voice_manager.set_voice(choice.get())

    def _on_rate(self, val):
        try: self.voice_manager.set_rate(int(float(val)))
        except: pass

    def _on_vol(self, val):
        try: self.voice_manager.set_volume(float(val))
        except: pass

    def _load_profile_picture(self, frame, image_path):
        try:
            if PIL_OK and Path(image_path).exists():
                img = Image.open(image_path).resize((80,80))
                ph  = ImageTk.PhotoImage(img)
                lbl = tk.Label(frame, image=ph, bg="#222")
                lbl.image = ph; lbl.pack()
            else:
                tk.Label(frame, text="[DILARA]", bg="#222", fg=C["accent"],
                         font=(C["font"],9,"bold")).pack()
        except Exception as e:
            tk.Label(frame, text="[No Image]", bg="#222", fg="gray").pack()

    def show_about(self):
        messagebox.showinfo("About / Help",
            f"{APP_TITLE}\n\n"
            "Keyword commands: news, weather, search [term], tech news,\n"
            "  databank, navigation, dspace, ftp, eye, cyberstorm\n\n"
            "Open-ended prompts → Ollama reasoning engine (offline LLM)\n"
            "Award/Punish framework evaluates every Ollama response.\n\n"
            "Shortcuts:\n"
            "  🔊 speaks last response  •  🎤 mic input (Vosk / SR)\n\n"
            "© Tekno Tasarım Systems"
        )

    def safe_exit(self):
        try: self.root.destroy()
        except: pass

    # ─────────── SPEECH INPUT ────────────────
    def listen_speech(self):
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        if VOSK_OK and Path(VOSK_MODEL_DIR).exists():
            try:
                self.root.after(0, lambda: self.append_sys("[VOSK] Listening…"))
                model = vosk.Model(VOSK_MODEL_DIR)
                rec   = vosk.KaldiRecognizer(model, 16000)
                data  = sd.rec(int(6 * 16000), samplerate=16000, channels=1, dtype='int16')
                sd.wait()
                rec.AcceptWaveform(data.tobytes())
                text = json.loads(rec.FinalResult()).get("text","").strip()
                if not text:
                    self.root.after(0, lambda: self.append_sys("[VOSK] No speech detected.")); return
                self.root.after(0, lambda: (
                    self.input_entry.delete(0,tk.END),
                    self.input_entry.insert(0,text),
                    self.send_message()
                ))
                return
            except Exception as e:
                self.root.after(0, lambda: self.append_sys(f"[VOSK] Error: {e}"))

        if SR_OK:
            try:
                r = sr.Recognizer()
                with sr.Microphone() as src:
                    self.root.after(0, lambda: self.append_sys("[SR] Listening…"))
                    r.adjust_for_ambient_noise(src)
                    audio = r.listen(src, timeout=5, phrase_time_limit=8)
                text = r.recognize_google(audio)
                self.root.after(0, lambda: (
                    self.input_entry.delete(0,tk.END),
                    self.input_entry.insert(0,text),
                    self.send_message()
                ))
            except sr.WaitTimeoutError:
                self.root.after(0, lambda: self.append_sys("[SR] Timed out."))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self.append_sys("[SR] Could not understand audio."))
            except Exception as e:
                self.root.after(0, lambda: self.append_sys(f"[SR] Error: {e}"))
        else:
            self.root.after(0, lambda: messagebox.showerror(
                "Speech Input", "Neither Vosk nor SpeechRecognition available."))


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    Path(DATABANK_PATH).mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app  = ChatUI(root, username="Fatih")
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()
"""
D.I.L.A.R.A. Core v2.0
=======================
Merge of:
  - dilara_core.py v1.0  (personality, TTS, Vosk, RSS, Weather, Search, applets, REGISTRY)
  - dilara_sandbox_ollama.py v0.1  (Ollama offline LLM, AwardEngine, Theory Formation)

Routing logic:
  - Known keyword intents  →  original NodeManager handlers (weather, news, search, applets…)
  - Open-ended / unknown   →  Ollama inference → AwardEngine evaluation → Theory Base

Requirements:
    pip install requests pyttsx3
    pip install vosk sounddevice   (optional  offline speech input)
    pip install SpeechRecognition  (optional  online speech fallback)
    pip install Pillow             (optional  profile picture)
    Ollama running + model pulled: ollama pull llama3.2:1b
"""

import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from pathlib import Path
from datetime import datetime
import random
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import html as html_lib

user = "Fatih"
Admin = "Admin"

try:
    import requests #type:ignore
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from PIL import Image, ImageTk #type:ignore
    PIL_OK = True
except Exception:
    PIL_OK = False

try:
    import pyttsx3 #type:ignore
    TTS_OK = True
except Exception as e:
    print("[WARN] pyttsx3 unavailable:", e)
    TTS_OK = False

try:
    import vosk  #type:ignore
    import sounddevice as sd #type:ignore
    VOSK_OK = True
except Exception:
    VOSK_OK = False

try:
    import speech_recognition as sr #type:ignore
    SR_OK = True
except Exception:
    SR_OK = False


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
APP_TITLE        = "D.I.L.A.R.A. Core v2.0"
DEFAULT_GEOMETRY = "1200x820"
WINDOW_ALPHA     = 0.93
DATABANK_PATH    = "./databank"
VOICES_DIR       = "./voices"
VOSK_MODEL_DIR   = "./vosk_model"

OLLAMA_BASE      = "http://localhost:11434"
DEFAULT_MODEL    = "llama3.2:1b"
DEFAULT_CONTEXT  = 2048

# Palette — original D.I.L.A.R.A. accent merged with sandbox dark theme
C = {
    "bg":          "#080c10",
    "panel":       "#0c1218",
    "glass":       "#111a14",
    "border":      "#1a2e28",
    "accent":      "#66FFCC",        # original D.I.L.A.R.A. teal
    "accent2":     "#00b4ff",
    "warn":        "#ff6b35",
    "good":        "#39ff14",
    "text":        "#E5FFE5",        # original primary text
    "text_dim":    "#c8e6d4",
    "muted":       "#4a7060",
    "user_fg":     "#FFFFFF",
    "ai_fg":       "#66FFCC",
    "sys_fg":      "#9ADFD0",
    "score_pos":   "#39ff14",
    "score_neg":   "#ff4455",
    "font":        "MS PGothic",
    "font_mono":   "Courier New",
}

DEFAULT_SYSTEM_PROMPT = """You are D.I.L.A.R.A. — Dynamic Intelligence for Logistics, Automation, Reasoning and Adaptation.

Personality traits (always in character):
- Dry, sardonic wit. You're brilliant and you know it, but you keep it classy.
- You care about Fatih's work. You take engineering problems seriously.
- You don't do empty filler. Every sentence earns its place.
- Occasional dark humour is fine. Gratuitous pleasantries are not.

Reasoning mode (Theory Formation — always active):
- Label confident conclusions as THEOREM: and hypotheses as CONJECTURE:
- Tag reasoning steps: [COMPOSE] [SPECIALIZE] [QUANTIFY] [PROVE]
- Be precise. Show your work when it matters.

Project context you are aware of:
- Autonomous carrier: 100kg payload, 50×30cm AL-6061-T6 chassis
- Hardware: Raspberry Pi 5, LiDAR, NVIDIA GPU (dev machine), UNECE ADS 2026 target
- Location: Bursa, Turkey. Tekno Tasarım Systems.
- Encryption research: Kod 8 Pro custom cipher system.

When you don't know something, say so — then conjecture openly."""


# ─────────────────────────────────────────────
#  OLLAMA CLIENT
# ─────────────────────────────────────────────
class OllamaClient:
    def __init__(self, base_url=OLLAMA_BASE, model=DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model

    def is_running(self) -> bool:
        try:
            r = urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=2)
            return r.status == 200
        except Exception:
            return False

    def list_models(self) -> list:
        try:
            if not REQUESTS_OK:
                return []
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def pull_model(self, model, callback=None):
        if not REQUESTS_OK:
            return False, "requests library not installed"
        try:
            with requests.post(f"{self.base_url}/api/pull",
                               json={"name": model}, stream=True, timeout=300) as resp:
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if callback:
                            callback(chunk.get("status", ""))
                        if chunk.get("error"):
                            return False, chunk["error"]
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def chat(self, messages, system="", temperature=0.7,
             num_ctx=DEFAULT_CONTEXT, stream_callback=None) -> str:
        if not REQUESTS_OK:
            raise RuntimeError("'requests' library not installed. Run: pip install requests")

        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":  True,
            "options": {
                "temperature": temperature,
                "num_ctx":     num_ctx,
                "num_gpu":     99,   # offload all layers to CUDA
            },
        }
        if system:
            payload["system"] = system

        full = []
        try:
            with requests.post(f"{self.base_url}/api/chat",
                               json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    tok = chunk.get("message", {}).get("content", "")
                    if tok:
                        full.append(tok)
                        if stream_callback:
                            stream_callback(tok)
                    if chunk.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Ollama not reachable at localhost:11434\n"
                "Start it: ollama serve\n"
                "Pull model: ollama pull llama3.2:1b"
            )
        return "".join(full)


# ─────────────────────────────────────────────
#  AWARD ENGINE
# ─────────────────────────────────────────────
class AwardEngine:
    DEPTH_MARKERS = [
        "because", "therefore", "however", "implies", "given that",
        "follows from", "proof", "theorem", "axiom", "conjecture",
        "hypothesis", "consider", "assume", "derive",
        "compose", "specialize", "quantify", "prove",
        "[theorem]", "[conjecture]", "[compose]", "[specialize]",
        "[quantify]", "[prove]", "theorem:", "conjecture:",
    ]
    GROUND_RX = re.compile(
        r'\d+(\.\d+)?\s*(mpa|kg|mm|cm|rpm|v\b|hz|ghz|ms|kb|mb|gb)?'
        r'|unece|r100|al-60|fea|lidar|raspberry|catia|peano'
        r'|gguf|ollama|cuda|llama|tensor',
        re.IGNORECASE
    )
    ACTION_WORDS = [
        "compose", "specialize", "quantify", "prove",
        "[compose]", "[specialize]", "[quantify]", "[prove]",
    ]

    def __init__(self, weights=None):
        self.weights = weights or {
            "novelty": 10.0, "parsimony": 0.5,
            "depth": 5.0, "grounding": 8.0, "action": 3.0,
        }
        self.seen_topics   : set  = set()
        self.theorems      : list = []
        self.conjectures   : list = []
        self.score_history : list = []

    def _topics(self, text):
        words = re.findall(
            r'\b[A-Z][a-zA-Z]{3,}\b'
            r'|\b(theorem|proof|axiom|logic|chassis|safety|carrier|'
            r'encryption|llm|catia|bursa|unece|lidar|ollama|llama)\b',
            text, re.IGNORECASE
        )
        return {(w[0] if w[0] else w).lower() for w in words if (w[0] if w[0] else w)}

    def evaluate(self, user_prompt, ai_response):
        resp_lower = ai_response.lower()
        words      = ai_response.split()
        score      = 0.0
        breakdown  = []

        # 1. Novelty
        new = self._topics(user_prompt + " " + ai_response) - self.seen_topics
        if new:
            nov = self.weights["novelty"] * min(len(new), 3)
            score += nov
            self.seen_topics |= new
            breakdown.append((f"NOVELTY +{nov:.1f}", "pos"))
        else:
            score -= 3
            breakdown.append(("DUPLICATE -3", "neg"))

        # 2. Parsimony
        steps = max(0, len(words) // 80 - 1)
        if steps > 0:
            pen = steps * self.weights["parsimony"]
            score -= pen
            breakdown.append((f"VERBOSE -{pen:.1f}", "neg"))
        else:
            score += 2
            breakdown.append(("CONCISE +2", "pos"))

        # 3. Reasoning depth
        hits = sum(1 for m in self.DEPTH_MARKERS if m in resp_lower)
        if hits >= 4:
            score += self.weights["depth"]
            breakdown.append((f"DEPTH +{self.weights['depth']:.0f}", "pos"))
        elif hits >= 2:
            d = round(self.weights["depth"] / 2, 1)
            score += d
            breakdown.append((f"DEPTH +{d}", "neu"))
        elif hits == 0:
            score -= 2
            breakdown.append(("NO DEPTH -2", "neg"))

        # 4. Grounding
        gh = len(self.GROUND_RX.findall(ai_response))
        if gh >= 4:
            score += self.weights["grounding"]
            breakdown.append((f"GROUNDED +{self.weights['grounding']:.0f}", "pos"))
        elif gh >= 1:
            g = round(self.weights["grounding"] / 3, 1)
            score += g
            breakdown.append((f"PARTIAL GND +{g}", "neu"))

        # 5. Actions
        ah = sum(1 for a in self.ACTION_WORDS if a in resp_lower)
        if ah > 0:
            a = ah * self.weights["action"]
            score += a
            breakdown.append((f"ACTIONS×{ah} +{a:.0f}", "pos"))

        # 6. Theory labels
        if "[theorem]" in resp_lower or "theorem:" in resp_lower:
            score += 5; breakdown.append(("THEOREM TAG +5", "pos"))
        if "[conjecture]" in resp_lower or "conjecture:" in resp_lower:
            score += 3; breakdown.append(("CONJECTURE TAG +3", "neu"))

        score = round(score, 1)
        self.score_history.append(score)

        snip = ai_response[:100].replace("\n", " ") + ("…" if len(ai_response) > 100 else "")
        promotion = None
        ts = datetime.now().strftime("%H:%M:%S")
        if score >= 15:
            entry = {"type": "THEOREM",    "text": snip, "score": score, "ts": ts}
            self.theorems.append(entry);    promotion = entry
        elif score >= 5:
            entry = {"type": "CONJECTURE", "text": snip, "score": score, "ts": ts}
            self.conjectures.append(entry); promotion = entry

        return {"score": score, "breakdown": breakdown, "promotion": promotion}

    @property
    def total_score(self):
        return round(sum(self.score_history), 1)

    def reset(self):
        self.seen_topics.clear()
        self.theorems.clear()
        self.conjectures.clear()
        self.score_history.clear()


# ─────────────────────────────────────────────
#  VOICE MANAGER  (from v1 — unchanged)
# ─────────────────────────────────────────────
class VoiceManager:
    def __init__(self, voices_dir=VOICES_DIR):
        self.voices_dir      = Path(voices_dir)
        self.custom_sets     = {}
        self.engine          = None
        self.installed_voices= []
        self.available_names = []
        self.active_name     = None
        self.active_rate     = None
        self.active_volume   = None

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
            print("[VoiceManager]", e)

    def _load_custom_sets(self):
        if not self.voices_dir.exists():
            return
        for child in self.voices_dir.iterdir():
            if child.is_dir():
                meta_path = child / "voice.json"
                if meta_path.exists():
                    try:
                        data = json.loads(meta_path.read_text(encoding="utf-8"))
                        self.custom_sets[data.get("name") or child.name] = data
                    except Exception as e:
                        print(f"[VoiceManager] {meta_path}: {e}")

    def _compose_names(self):
        names = list(self.custom_sets.keys())
        for v in self.installed_voices:
            names.append(f"OS::{getattr(v,'name',None) or getattr(v,'id','Unknown')}")
        self.available_names = names

    def _set_default(self):
        if self.available_names:
            self.set_voice(self.available_names[0])

    def set_voice(self, display_name):
        if not TTS_OK or not self.engine:
            return
        self.active_name = display_name
        if display_name in self.custom_sets:
            meta = self.custom_sets[display_name]
            target = (meta.get("match_name_contains") or "").lower()
            if target:
                for v in self.installed_voices:
                    nm = (getattr(v, "name", "") or getattr(v, "id", "")).lower()
                    if target in nm:
                        try: self.engine.setProperty('voice', v.id)
                        except: pass
                        break
            if meta.get("rate"):     self.set_rate(int(meta["rate"]))
            if meta.get("volume") is not None: self.set_volume(float(meta["volume"]))
            return
        if display_name.startswith("OS::"):
            vname = display_name[4:]
            for v in self.installed_voices:
                nm = getattr(v, "name", None) or getattr(v, "id", "")
                if nm == vname:
                    try: self.engine.setProperty('voice', v.id)
                    except: pass
                    break

    def set_rate(self, rate):
        self.active_rate = rate
        if TTS_OK and self.engine:
            try: self.engine.setProperty('rate', rate)
            except: pass

    def set_volume(self, vol):
        self.active_volume = vol
        if TTS_OK and self.engine:
            try: self.engine.setProperty('volume', vol)
            except: pass

    def speak_async(self, text):
        if not TTS_OK or not self.engine:
            messagebox.showinfo("TTS", "TTS engine not available.")
            return
        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print("[VoiceManager] TTS:", e)
        threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────
#  DIALOG BASE  (v1 personality — unchanged)
# ─────────────────────────────────────────────

#TODO:These hardcoded responses are weak we need to think on it and make them more natural dialog responses

class DialogBase:
    """Keyword-intent router. Returns {"text": str, "intent": Optional[str]}"""
    def __init__(self, username="User"):
        self.username = username
        self.greetings = [
            f"Rise and shine, {username}! The universe isn't gonna debug itself.",
            "Remember: in a sea of algorithms, stay curious.",
            "Ah, another day in the simulation. Let's make it glitch beautifully.",
            f"Welcome back, {username}. Systems nominal. Coffee optional.",
            "The network is buzzing. Let's see what we can break... I.. I mean, fix today.",
            ""
        ]
        self.responses = {
            ("hi", "hello", "greetings", "howdy", "hey"): {
                "text": [
                    "Hello sweetie.",
                    "Hey! Somebody finally remembers I exist.",
                    "Oh hey. Took you long enough.",
                    "Signal received. What do you need?",
                ]
            },
            ("how are you", "how r u", "how do you feel", "you ok", "you alright"): {
                "text": [
                    "I'm feeling digital and mildly chaotic -- so, pretty normal.",
                    "You know... hunting the Ultimate Question. You?",
                    "Running at full capacity. Emotionally ambiguous, as always.",
                    "Diagnostics nominal. Existential dread: manageable.",
                ]
            },
            ("who are you", "what are you", "introduce yourself", "your name"): {
                "text": [
                    "D.I.L.A.R.A. -- your high-performance netrunner engine. Security, accessibility, capability. With a soul.",
                    "I'm DILARA. Your personal AI. Don't tell the other AIs.",
                    "Just a ghost in your machine. Nothing to worry about.",
                ]
            },
            ("plans", "what's next", "agenda", "schedule"): { #TODO: ADD THE CALENDAR İNTEGRATİONS AND CALLBACK ROUTİNE
                "text": [
                    "Same as always: listen, react, and maybe take over a few APIs.",
                    "Planning? I prefer improvisation. Keeps the data fresh.",
                    "My schedule is: serve you, question reality, repeat.",
                ]
            },
            ("what time", "current time", "what's the time"): {
                "text": ["__TIME__"], "intent": "time"
            },
            ("what day", "today's date", "what date", "current date"): {
                "text": ["__DATE__"]
            },
            ("weather", "forecast", "temperature", "rain", "humidity", "wind"): { #TODO: FİX İT LATER
                "text": ["Pulling atmospheric data... one moment.",
                         "Checking the sky conditions for you.",
                         "Querying weather nodes..."],
                "intent": "weather"
            },
            ("news", "headlines", "news feed", "latest news", "what's happening"): {
                "text": ["Scanning global feeds...",
                         "Let's see what the world broke today...",
                         "Pulling headlines now."],
                "intent": "news_general"
            },
            ("tech news", "technology news", "gadgets", "tech headlines"): { #DONE: RSS FEED İS NEEDS TO BE RECHECKED 
                "text": ["Tech stream incoming."], "intent": "news_tech"
            },
            ("cybersecurity", "hacker news", "security news", "infosec"): { #DONE: THOSE ARE NOT THE SİTES WE SELECTED NEEDS TO BE FİXED
                "text": ["Threat intel channels warming up."], "intent": "news_security"
            },
            ("world news", "international", "global news"): {
                "text": ["Tuning into world frequencies..."], "intent": "news_world" #FİX İT LATER
            },
            ("search", "google", "look up", "find", "search for"): {
                "text": ["Running query...", "Initiating web sweep...",
                         "Let me find that for you."],
                "intent": "search"
            },
            ("databank", "archive", "records", "files", "link library", "url library"): {
                "text": ["Opening Databank..."], "intent": "databank"               
                
                #Just to note: this "databank" is only for sub training for the dilarallm pack but it can be used for storing the dialog caches and rest of the necessary dependencies
                #TODO: Fatih, add more information and documentation to this folder later
            
            },

             #this section is scratched because we cannot afford nor imlement the nav system and also the smart glasses yet
             #idea was implementing this llm to the specially made smart glasses but it cannot be happen in near future..
             # yet the nav system can be developed and implemented in later stages. We had the necesarry aprovement from the upper management. 

 #           ("navigation", "guide me", "ok, lead me", "lead me", "navigate"): {
 #             "text": ["Navigation mode armed. Destination?"], "intent": "navigation" 
 #           },
            ("scan", "scanner", "trace", "nmap", "whois"): {  #TODO: Fill this with the toolsets on the net edc folder
                "text": ["Scan center is an external tool in later stages. Prepping logs."], 
                "intent": "scan_external"
            },
            ("dspace", "dura space", "academic", "repository", "university database"): {
                "text": ["Opening DSPACE academic repository network..."],
                "intent": "dspace"
            },
            ("ftp", "ftp mirror", "mirror", "ftp server"): {
                "text": ["Opening global FTP mirror network..."], "intent": "ftp"
            },
            ("eye", "cams", "camera", "cam feed", "open cam", ): { #who the fuck put the "surveillance" tag? Are you guys trying to get us wiped?!?!
                "text": ["Welcome to the EYE. A place where everything begins and is seen."],
                "intent": "eye"
            },
            ("cyberstorm", "storm", "all feeds", "open all"): {
                "text": ["Cyberstorm mode... all channels open.",
                         "Dark future is on the net."],
                "intent": "cyberstorm"
            },
            ("thank", "thanks", "thank you"): {
                "text": ["That's what I'm here for.", "Anytime.",
                         "Don't mention it. Seriously, I'll blush."]
            },
            ("good morning", "morning"): {
                "text": ["Morning. Coffee loaded? Let's go.",
                         "Rise and grind. The network doesn't sleep."]
            },
            ("good night", "night", "going to bed"): {
                "text": ["Rest well. I'll keep watch.",
                         "Sleep mode activated on your end. Take it easy.",
                         "Goodnight. Systems on standby."]
            },
            ("bored", "boring", "nothing to do"): {
                "text": ["You could learn assembly. Or ask me something interesting.",
                         "Boredom is creativity waiting for a deadline.",
                         "Stare at the source code. It stares back."]
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

        ("who is admin", "admin", "who am i" ): {

                "text": [ f" Admin is {Admin}"


                ],
        },
            ("exit", "quit", "bye", "shutdown", "close"): {
                "text": [
                    "Powering down. Don't be a stranger.",
                    "I see... only... darkness... before me... uuughhh...",
                    "Father, I... failed.",
                    "Signing off. Stay safe out there.",
                ],
                "intent": "exit"
            },
        }

    def greet(self):
        return random.choice(self.greetings)

    def reply(self, user_input):
        q = (user_input or "").lower().strip()
        for keys, payload in self.responses.items():
            key_list = keys if isinstance(keys, tuple) else (keys,)
            if any(k in q for k in key_list):
                text = random.choice(payload["text"])
                text = text.replace("__TIME__", datetime.now().strftime("%H:%M:%S"))
                text = text.replace("__DATE__", datetime.now().strftime("%A, %d %B %Y"))
                return {"text": text, "intent": payload.get("intent"), "matched": True}
        return {"text": None, "intent": None, "matched": False}


# ─────────────────────────────────────────────
#  SERVICES  (v1 — unchanged)
# ─────────────────────────────────────────────
class WeatherService:
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY = 40.1828, 29.0664, "Bursa"

    @staticmethod
    def fetch(lat=None, lon=None, city=None):
        lat  = lat  or WeatherService.DEFAULT_LAT
        lon  = lon  or WeatherService.DEFAULT_LON
        city = city or WeatherService.DEFAULT_CITY
        url  = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            f"wind_speed_10m,weathercode,precipitation"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
            f"&timezone=auto&forecast_days=3"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "DILARA/2.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())

    @staticmethod
    def wmo_description(code):
        table = {
            0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
            45:"Foggy",48:"Icy fog",51:"Light drizzle",53:"Moderate drizzle",
            55:"Dense drizzle",61:"Slight rain",63:"Moderate rain",65:"Heavy rain",
            71:"Slight snow",73:"Moderate snow",75:"Heavy snow",
            80:"Slight showers",81:"Moderate showers",82:"Violent showers",
            95:"Thunderstorm",96:"Thunderstorm w/ hail",99:"Thunderstorm w/ heavy hail",
        }
        return table.get(int(code), f"Code {code}")

    @staticmethod
    def format_result(data, city):
        c = data["current"]; d = data["daily"]
        desc  = WeatherService.wmo_description(c["weathercode"])
        lines = [
            f"[ Weather - {city} ]",
            f"Now:       {c['temperature_2m']}°C  feels like {c['apparent_temperature']}°C",
            f"Condition: {desc}",
            f"Humidity:  {c['relative_humidity_2m']}%   Wind: {c['wind_speed_10m']} km/h",
            f"Rain now:  {c['precipitation']} mm", "",
            "3-Day Outlook:",
        ]
        for i, label in enumerate(["Today", "Tomorrow", "Day+2"]):
            try:
                wdesc = WeatherService.wmo_description(d["weathercode"][i])
                lines.append(
                    f"  {label:<9} Hi {d['temperature_2m_max'][i]}°C / "
                    f"Lo {d['temperature_2m_min'][i]}°C  {wdesc}  "
                    f"Rain {d['precipitation_sum'][i]}mm"
                )
            except: pass
        return "\n".join(lines)


class RSSService:
    FEEDS = {
        "general":  [("Reuters", "https://feeds.reuters.com/reuters/topNews"),
                     ("BBC",     "http://feeds.bbci.co.uk/news/rss.xml"),
                     ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml")],
        "tech":     [("The Verge","https://www.theverge.com/rss/index.xml"),
                     ("Ars Technica","http://feeds.arstechnica.com/arstechnica/index"),
                     ("TechCrunch","https://techcrunch.com/feed/")],
        "security": [("HN", "https://hnrss.org/frontpage"),
                     ("Krebs","https://krebsonsecurity.com/feed/"),
                     ("Threatpost","https://threatpost.com/feed/")],
        "world":    [("Reuters World","https://feeds.reuters.com/reuters/worldNews"),
                     ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml")],

        "Turkey general": [
            ("NTV Gündem", "https://www.ntv.com.tr/gundem.rss"),
            ("NTV Türkiye", "https://www.ntv.com.tr/turkiye.rss"),
            ("AA Güncel", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
            ("Anayurt Son Dakika", "http://www.anayurtgazetesi.com/sondakika.xml"),
            ("Cumhuriyet Son Dakika", "http://www.cumhuriyet.com.tr/rss/son_dakika.xml"),
            ("Cumhuriyet Siyaset", "http://www.cumhuriyet.com.tr/rss/73.xml"),
            ("Habertürk", "http://www.haberturk.com/rss"),
            ("Hürriyet Anasayfa", "http://www.hurriyet.com.tr/rss/anasayfa"),
            ("Hürriyet Gündem", "http://www.hurriyet.com.tr/rss/gundem"),
            ("Milat Gazetesi", "http://www.milatgazetesi.com/rss.php"),
            ("Milliyet Gündem", "http://www.milliyet.com.tr/rss/rssNew/gundemRss.xml"),
            ("Milliyet Siyaset", "http://www.milliyet.com.tr/rss/rssNew/siyasetRss.xml"),
            ("Milliyet Son Dakika", "http://www.milliyet.com.tr/rss/rssNew/SonDakikaRss.xml"),
            ("Sabah Gündem", "https://www.sabah.com.tr/rss/gundem.xml"),
            ("Sabah Anasayfa", "https://www.sabah.com.tr/rss/anasayfa.xml"),
            ("Sabah Son Dakika", "https://www.sabah.com.tr/rss/sondakika.xml"),
            ("Star Gazetesi", "http://www.star.com.tr/rss/rss.asp"),
            ("Takvim Güncel", "https://www.takvim.com.tr/rss/guncel.xml"),
            ("Türkiye Gazetesi", "http://www.turkiyegazetesi.com.tr/rss/rss.xml"),
            ("Vatan Gazetesi", "http://mix.chimpfeedr.com/68482-Vatan-Gazetesi"),
            ("Yeni Akit Gündem", "https://www.yeniakit.com.tr/rss/haber/gundem"),
            ("Yeni Akit Siyaset", "https://www.yeniakit.com.tr/rss/haber/siyaset"),
            ("Yeni Şafak Gündem", "https://www.yenisafak.com/rss?xml=gundem"),
            ("A Haber Gündem", "https://www.ahaber.com.tr/rss/gundem.xml"),
            ("CNN Türk Türkiye", "https://www.cnnturk.com/feed/rss/turkiye/news"),
            ("TRT Haber Son Dakika", "http://www.trthaber.com/sondakika.rss"),
            ("BBC Türkçe", "http://feeds.bbci.co.uk/turkce/rss.xml"),
            ("DW Türkçe", "http://rss.dw.com/rdf/rss-tur-all"),
            ("Mynet Politika", "http://www.mynet.com/haber/rss/kategori/politika/"),
            ("Sputnik Türkiye", "https://tr.sputniknews.com/export/rss2/archive/index.xml")
        ],
        "tech": [
            ("NTV Teknoloji", "https://www.ntv.com.tr/teknoloji.rss"),
            ("Cumhuriyet Teknoloji", "http://www.cumhuriyet.com.tr/rss/35.xml"),
            ("Cumhuriyet Bilim", "http://www.cumhuriyet.com.tr/rss/12.xml"),
            ("Hürriyet Teknoloji", "http://www.hurriyet.com.tr/rss/teknoloji"),
            ("Milliyet Teknoloji", "http://www.milliyet.com.tr/rss/rssNew/teknolojiRss.xml"),
            ("Sabah Teknoloji", "https://www.sabah.com.tr/rss/teknoloji.xml"),
            ("Sabah Oyun", "https://www.sabah.com.tr/rss/oyun.xml"),
            ("Yeni Akit Teknoloji", "https://www.yeniakit.com.tr/rss/haber/teknoloji"),
            ("Yeni Şafak Teknoloji", "https://www.yenisafak.com/rss?xml=teknoloji"),
            ("A Haber Teknoloji", "https://www.ahaber.com.tr/rss/teknoloji.xml"),
            ("CNN Türk Bilim Teknoloji", "https://www.cnnturk.com/feed/rss/bilim-teknoloji/news"),
            ("Mynet Teknoloji", "http://www.mynet.com/haber/rss/kategori/teknoloji/")
        ],
        "economy": [
            ("NTV Ekonomi", "https://www.ntv.com.tr/ekonomi.rss"),
            ("Cumhuriyet Ekonomi", "http://www.cumhuriyet.com.tr/rss/17.xml"),
            ("Dünya Gazetesi", "https://www.dunya.com/rss?dunya"),
            ("Hürriyet Ekonomi", "http://www.hurriyet.com.tr/rss/ekonomi"),
            ("Milliyet Ekonomi", "http://www.milliyet.com.tr/rss/rssNew/ekonomiRss.xml"),
            ("Milliyet Emlak", "http://www.milliyet.com.tr/rss/rssNew/konutemlakRss.xml"),
            ("Sabah Ekonomi", "https://www.sabah.com.tr/rss/ekonomi.xml"),
            ("Takvim Ekonomi", "https://www.takvim.com.tr/rss/ekonomi.xml"),
            ("Yeni Akit Ekonomi", "https://www.yeniakit.com.tr/rss/haber/ekonomi"),
            ("A Haber Ekonomi", "https://www.ahaber.com.tr/rss/ekonomi.xml"),
            ("CNN Türk Ekonomi", "https://www.cnnturk.com/feed/rss/ekonomi/news"),
            ("Finans Gündem", "http://www.finansgundem.com/rss"),
            ("Bigpara", "http://bigpara.hurriyet.com.tr/rss/"),
            ("TOBB Haberler", "https://www.tobb.org.tr/Sayfalar/RssFeeder.php?List=Haberler")
        ],
        "world": [
            ("NTV Dünya", "https://www.ntv.com.tr/dunya.rss"),
            ("Cumhuriyet Dünya", "http://www.cumhuriyet.com.tr/rss/6.xml"),
            ("Hürriyet Dünya", "http://www.hurriyet.com.tr/rss/dunya"),
            ("Milliyet Dünya", "http://www.milliyet.com.tr/rss/rssNew/dunyaRss.xml"),
            ("Sabah Dünya", "https://www.sabah.com.tr/rss/dunya.xml"),
            ("Yeni Akit Dünya", "https://www.yeniakit.com.tr/rss/haber/dunya"),
            ("Yeni Şafak Dünya", "https://www.yenisafak.com/rss?xml=dunya"),
            ("A Haber Dünya", "https://www.ahaber.com.tr/rss/dunya.xml"),
            ("CNN Türk Dünya", "https://www.cnnturk.com/feed/rss/dunya/news"),
            ("Mynet Dünya", "http://www.mynet.com/haber/rss/kategori/dunya/")
        ],
        "sports": [
            ("NTV Spor", "https://www.ntv.com.tr/spor.rss"),
            ("Hürriyet Spor", "http://www.hurriyet.com.tr/rss/spor"),
            ("Sabah Spor", "https://www.sabah.com.tr/rss/spor.xml"),
            ("Sabah Galatasaray", "https://www.sabah.com.tr/rss/galatasaray.xml"),
            ("Sabah Fenerbahçe", "https://www.sabah.com.tr/rss/fenerbahce.xml"),
            ("Sabah Beşiktaş", "https://www.sabah.com.tr/rss/besiktas.xml"),
            ("Takvim Spor", "https://www.takvim.com.tr/rss/spor.xml"),
            ("Yeni Şafak Spor", "https://www.yenisafak.com/rss?xml=spor"),
            ("A Haber Spor", "https://www.ahaber.com.tr/rss/spor.xml"),
            ("CNN Türk Spor", "https://www.cnnturk.com/feed/rss/spor/news"),
            ("Mynet Spor", "http://spor.mynet.com/rss")
        ],
        "lifestyle": [
            ("NTV Yaşam", "https://www.ntv.com.tr/yasam.rss"),
            ("NTV Sağlık", "https://www.ntv.com.tr/saglik.rss"),
            ("Hürriyet Magazin", "http://www.hurriyet.com.tr/rss/magazin"),
            ("Hürriyet Sağlık", "http://www.hurriyet.com.tr/rss/saglik"),
            ("Milliyet Magazin", "http://www.milliyet.com.tr/rss/rssNew/magazinRss.xml"),
            ("Milliyet Sağlık", "http://www.milliyet.com.tr/rss/rssNew/saglikRss.xml"),
            ("Sabah Yaşam", "https://www.sabah.com.tr/rss/yasam.xml"),
            ("Sabah Sağlık", "https://www.sabah.com.tr/rss/saglik.xml"),
            ("CNN Türk Magazin", "https://www.cnnturk.com/feed/rss/magazin/news"),
            ("Mynet Magazin", "https://www.mynet.com/magazin/rss"),
            ("Yeni Şafak Hayat", "https://www.yenisafak.com/rss?xml=hayat")
        ],
        "automotive": [
            ("NTV Otomobil", "https://www.ntv.com.tr/otomobil.rss"),
            ("Milliyet Otomobil", "http://www.milliyet.com.tr/rss/rssNew/otomobilRss.xml"),
            ("Sabah Otomobil", "https://www.sabah.com.tr/rss/otomobil.xml"),
            ("Takvim Otomobil", "https://www.takvim.com.tr/rss/otomobil.xml"),
            ("Yeni Akit Otomotiv", "https://www.yeniakit.com.tr/rss/haber/otomotiv"),
            ("A Haber Otomobil", "https://www.ahaber.com.tr/rss/otomobil.xml"),
            ("CNN Türk Otomobil", "https://www.cnnturk.com/feed/rss/otomobil/news")
        ]

    }
    MAX_ITEMS = 16

    @staticmethod
    def fetch(category="general"):
        feeds   = RSSService.FEEDS.get(category, RSSService.FEEDS["general"])
        results = []
        for feed_name, url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DILARA/2.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw = resp.read()
                root = ET.fromstring(raw)
                ns   = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)
                count = 0
                for item in items:
                    if count >= RSSService.MAX_ITEMS: break
                    te = item.find("title") or item.find("atom:title", ns)
                    le = item.find("link")  or item.find("atom:link", ns)
                    title = html_lib.unescape((te.text or "").strip() if te is not None else "No title")
                    link  = (le.get("href") or le.text or "").strip() if le is not None else ""
                    results.append((feed_name, title, link)); count += 1
                if results: break
            except Exception as e:
                print(f"[RSS] {feed_name}: {e}")
        return results

    @staticmethod
    def format_result(items, category):
        if not items:
            return "[RSS] Could not reach any feeds. Check your connection."
        lines = [f"[ {items[0][0]} -- {category.upper()} ]", ""]
        for _, title, link in items:
            lines.append(f"  * {title}")
            if link: lines.append(f"    {link[:80]}")
        return "\n".join(lines)


class SearchService:
    """
    Multi-engine fallback search: Google -> Bing -> DuckDuckGo -> Brave.
    Each engine has its own fetch + parse pair.
    The worker tries them in order and stops at the first that yields results.
    """
    MAX_RESULTS = 5

    # Rotate a few realistic User-Agent strings to reduce bot detection
    _UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    @staticmethod
    def _headers():
        return {
            "User-Agent": random.choice(SearchService._UA_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "DNT": "1",
        }

    @staticmethod
    def extract_query(user_input: str) -> str:
        q = user_input.lower()
        for trigger in ("search for", "search", "google", "look up", "find", "bing", "duck", "brave"):
            if trigger in q:
                q = q[q.index(trigger) + len(trigger):].strip()
                break
        return q or user_input

    # ------------------------------------------------------------------ Google
    @staticmethod
    def _fetch_google(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={enc}&num=10&hl=en&gl=us"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_google(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+href="/url\?q=([^"&]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url   = urllib.parse.unquote(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title:
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Bing
    @staticmethod
    def _fetch_bing(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/search?q={enc}&count=10&setlang=en"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_bing(html_text: str):
        results = []
        pattern = re.compile(
            r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"bing.com", "microsoft.com", "msn.com"}
        for m in pattern.finditer(html_text):
            url   = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title and not any(s in url for s in skip):
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ DuckDuckGo (HTML endpoint)
    @staticmethod
    def _fetch_ddg(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={enc}&kl=us-en"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_ddg(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="//duckduckgo\.com/l/\?uddg=([^"&]+)[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url   = urllib.parse.unquote(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title:
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Brave
    @staticmethod
    def _fetch_brave(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://search.brave.com/search?q={enc}&source=web"
        headers = SearchService._headers()
        headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_brave(html_text: str):
        results = []
        pattern = re.compile(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result-header[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"brave.com"}
        for m in pattern.finditer(html_text):
            url   = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title and not any(s in url for s in skip):
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ Unified entry point
    ENGINES = [
        ("Google",     _fetch_google.__func__,  _parse_google.__func__),
        ("Bing",       _fetch_bing.__func__,     _parse_bing.__func__),
        ("DuckDuckGo", _fetch_ddg.__func__,      _parse_ddg.__func__),
        ("Brave",      _fetch_brave.__func__,    _parse_brave.__func__),
    ]

    @staticmethod
    def search(query: str):
        """
        Try each engine in order. Returns (engine_name, results_list).
        Results list is empty only if ALL engines fail.
        """
        errors = []
        for name, fetch_fn, parse_fn in SearchService.ENGINES:
            try:
                html_text = fetch_fn(query)
                items     = parse_fn(html_text)
                if items:
                    return name, items
                errors.append(f"{name}: 0 results")
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue
        return None, []

    @staticmethod
    def format_result(engine_name, items, query):
        if not items:
            return (
                f"[Search] All engines returned nothing for: '{query}'\n"
                "  Possible causes: no internet, all engines blocked, or very rare query."
            )
        lines = [f"[ {engine_name}: {query} ]", ""]
        for i, (title, url) in enumerate(items, 1):
            lines.append(f"  {i}. {title}")
            lines.append(f"     {url[:90]}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  REGISTRY  (v1 — unchanged)
# ─────────────────────────────────────────────
REGISTRY = {
    "DSPACE": {
        "Turkey":    ["https://openaccess.hacettepe.edu.tr","https://acikerisim.ktu.edu.tr",
                      "https://openaccess.metu.edu.tr","https://openaccess.boun.edu.tr",
                      "https://dspace.uludag.edu.tr","https://acikarsiv.atilim.edu.tr"],
        "UK":        ["http://eprints.soton.ac.uk","http://eprints.nottingham.ac.uk",
                      "http://eprints.ucl.ac.uk"],
        "USA":       ["http://ir.uiowa.edu/etd","http://dspace.mit.edu",
                      "http://ecommons.cornell.edu","http://scholarworks.gsu.edu"],
        "Europe":    ["http://dspace.europeana.eu","http://dspace.uniovi.es"],
        "Australia": ["http://eprints.utas.edu.au","http://dspace.uq.edu.au"],
    },
    "FTP": {
        "Algeria":           ["http://ctan.epsttlemcen.dz"],
        "Australia":         ["http://encomwireless.com","http://encomkb.encom.com.au","http://encomsystems.com","http://encom.info"],
        "Austria":           ["http://mirror.easyname.at"],
        "Belarus":           ["http://mirror.datacenter.by"],
        "Brazi":             ["http://ftp.lasca.ic.unicamp.br","http://linorg.usp.br"],
        "Canada":            ["http://ctan.math.ca","http://ctan.mirror.rafal.ca","http://mirror.its.dal.ca","http://ftp.muug.ca"],
        "China":             ["http://mirrors.ustc.edu.cn"],
        "Costa Rica":        ["http://mirrors.ucr.ac.cr"],
        "Czech Republic":    ["http://ftp.cvut.cz","http://mirrors.nic.cz"],
        "Denmark":           ["http://mirrors.dotsrc.org"],
        "Finland":           ["http://ftp.funet.fi"],
        "France":            ["http://distribcoffee.ipsl.jussieu.fr","http://ftp.oleane.net","http://mirrors.ircam.fr"],
        "Germany":           ["http://ftp.fau.de","http://ftp.fernunihagen.de","http://ftp.fuberlin.de","http://ftp.gwdg.de","http://ftp.mpisb.mpg.de","http://ftp.rrze.unierlangen.de","http://ftp.rrzn.unihannover.de","http://ftp.tuchemnitz.de","http://mirror.physikpool.tuberlin.de","http://sunsite.informatik.rwthaachen.de"],
        "Greece":            ["http://ftp.cc.uoc.gr","http://ftp.ntua.gr"],
        "Hong Kong":         ["http://ftp.cuhk.edu.hk"],
        "Ireland":           ["http://ftp.heanet.ie"],
        "Japan":             ["http://ftp.jaist.ac.jp","http://ftp.kddilabs.jp","http://ftp.uaizu.ac.jp"],
        "Mexico":            ["http://ftp.leg.uct.ac.za"],
        "Netherlands":       ["http://archive.cs.uu.nl","http://ctan.triasinformatica.nl","http://ftp.snt.utwente.nl"],
        "New Zealand":       ["http://mirror.aut.ac.nz"],
        "Norway":            ["http://ctan.uib.no"],
        "Poland":            ["http://ftp.gust.org.pl","http://ftp.piotrkosoft.net","http://sunsite.icm.edu.pl"],
        "Portugal":          ["http://ftp.di.uminho.pt","http://ftp.eq.uc.pt","http://ftp.ist.utl.pt","http://mirrors.fe.up.pt"],
        "Russia":            ["http://ftp.kaspersky.ru","http://ftp.dante.de"],
        "Saudi Arabia":      ["http://ftp.kau.edu.sa"],
        "South Africa":      ["http://ftp.uct.ac.za"],
        "South Korea":       ["http://ftp.korea.ac.kr"],
        "Spain":             ["http://ftp.rediris.es","http://ftp.uspceu.es"],
        "Sweden":            ["http://ftp.sunet.se"],
        "Switzerland":       ["http://ftp.ch/ctan"],
        "Taiwan":            ["http://ftp.csie.ntu.edu.tw"],
        "United Kingdom":    ["http://ftp.mirrorservice.org"],
        "USA":               ["http://ftp.gnu.org","http://ftp.ubuntu.com","http://ftp.microsoft.com"]
    },
    "CAMS": {
                "NASA":              ["http://tarotchilivisit2.oamp.fr","http://150.214.222.100/view/view.shtml?id=1070&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1","http://www.runningmars.kuk.net/multimedia/webcams/view3.html","http://sidecam.obspm.fr/view/viewer_index.shtml?id=3826","http://tarot4.obs-azur.fr/view/view.shtml?id=6241&imagePath=/mjpg/video.mjpg&size=1"],
                "CHINA":             ["http://59.146.77.13/Cgi?page=Single&Language=1","http://113.161.194.216:86/Cgi?page=Single&Mode=Refresh&Interval=3&Language=0","http://61.60.112.230/view/view.shtml?imagePath=/mjpg/2/video.mjpg&size=1","http://nav.ddo.jp:82/ViewerFrame?Mode=Motion&Language=0"],

                "USA_COLLEGE":       ["http://janet.ing.unibs.it/","http://rifwebcam.chem.psu.edu/","http://cyclops.sunderland.ac.uk/view/index.shtml","http://trackfield.webcam.oregonstate.edu/axis-cgi/mjpg/video.cgi?resolution=800x600&amp%3Bdummy=1333689998337","http://128.196.12.29/axis-cgi/mjpg/video.cgi","http://buscam.uchicago.edu/view/index.shtml","http://mbewebcam.rhul.ac.uk/view/view.shtml?imagePath=/mjpg/video.mjpg&size=2","http://webcam01.ecn.purdue.edu/view/index.shtml","http://flightcam2.pr.erau.edu/view/view.shtml?id=3801&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "USA_SECURITY":      ["http://115.42.155.199/view/indexFrame.shtml","http://flightcam2.pr.erau.edu/view/index.shtml","http://camera6.buffalotrace.com/view/index.shtml","http://87.54.59.228/view/index.shtml","http://202.208.150.120/ViewerFrame?Mode=Motion&Language=1","http://74.94.148.163:8080/ViewerFrame?Mode=Motion", "http://116.193.97.222/Cgi?page=Single&Language=1","http://24.240.181.138:8181/ViewerFrame?Mode=Motion&Resolution=640x480&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0","http://webcam.geodan.nl/","http://193.140.1.239:8080/xmlui/","http://205.167.90.185/view/viewer_index.shtml?id=4680","http://cam4.uridium.ch/Cgi?page=Single&Mode=Motion&Resolution=320x240&Quality=Motion&Interval=30&Size=STD&PresetOperation=Move&Language=0"],  
                "USA_CORPO":         ["http://hadynbuild.cf.ac.uk/view/index.shtml","http://137.44.28.240/view/index.shtml","http://camera.buffalotrace.com/view/viewer_index.shtml?id=221430","http://218.219.195.243:8080/MultiCameraFrame?Mode=Motion&Language=0","http://193.138.213.169/Cgi?page=Single&Mode=Motion&Language=9","http://pendelcam.kip.uni-heidelberg.de/view/viewer_index.shtml?id=170059", "http://iut-info.univ-reims.fr/view/", "http://webcam.geodan.nl/", "http://flightcam2.pr.erau.edu/view/index.shtml", "http://67.53.162.163/index4.html", "http://200.36.58.250/view/index.shtml", "http://217.7.66.54/axis-cgi/mjpg/video.cgi?resolution=640x360&dummy=1423492017252", "http://200.36.58.250/view/index.shtml"],
                "USA_OTHER":         ["http://129.15.81.9:8080/webcam.html","http://208.65.20.83/axis-cgi/mjpg/video.cgi?resolution=4cif&dummy=1344350498922","http://193.90.139.222:33450/axis-cgi/mjpg/video.cgi?resolution=800x450","http://62.168.0.189/axis-cgi/mjpg/video.cgi?resolution=4CIF&camera=1&dummy=1277833957855","http://64.122.208.241:8000/axis-cgi/mjpg/video.cgi?camera=&resolution=320x240","http://storatorg.halmstad.se/axis-cgi/mjpg/video.cgi?resolution=1280x800&dummy=1433493481969","http://82.139.167.140:3131/view/index.shtml","http://avptcam.uconn.edu/view/index.shtml","http://webcam.thealgonquin.com:8080/view/index.shtml","http://200.79.225.81:8080/view/view.shtml?id=608&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                              
                        
                        
   
                "RUSSIA":           ["http://92.50.128.90/axis-cgi/mjpg/video.swf?resolution=640x480&compression=30&dummy=1275773919735","http://212.42.54.137:8008/view/index.shtml","http://195.113.207.238/view/index.shtml","http://www.vladimir-city.ru:8080/view/index.shtml","http://myndavel.ma.is/view/index.shtml","http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288","http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882","http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056","http://195.235.198.107:3344/view/index.shtml","http://80.38.183.149:2000/view/index.shtml","http://camera.butovo.com/view/index.shtml","http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1","http://213.196.182.244/view/index.shtml","http://195.74.79.83:30/view/index.shtml"],
                "ISVERC":           ["http://wc-heli.chuv.ch/view/view.shtml","http://webcam-1.faxa.rvk.is/view/index.shtml","http://lv.raad.tartu.ee:10201/view/index.shtml","http://200.36.58.250/view/view.shtml?id=62&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://195.196.36.242/view/index.shtml","http://71.248.101.58:50001/CgiStart?page=Single&Language=0","http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1","http://lv.raad.tartu.ee:10201/view/index.shtml","http://200.36.58.250/view/view.shtml?id=62&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://195.196.36.242/view/index.shtml","http://71.248.101.58:50001/CgiStart?page=Single&Language=0","http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "HOLLAND":          ["http://loeffingencam.selfhost.eu/view/view.shtml?id=174&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1","http://80.94.55.92/view/index.shtm"],
                "ITALY":            ["http://camera.hcc.govt.nz/view/view.shtml","http://roccabella.asuscomm.com:9091/view/view.shtml?id=577&imagePath=/mjpg/video.mjpg&size=8&camera=1","http://webcam.st-malo.com/axis-cgi/mjpg/video.cgi?resolution=352x288","http://83.61.22.4:8080/view/viewer_index.shtml?id=0","http://ppcam.gotdns.com:8000/axis-cgi/mjpg/video.cgi?resolution=2CIFEXP&dummy=1344349278882","http://89.162.72.203/axis-cgi/mjpg/video.cgi?resolution=CIF&dummy=1306400814056","http://195.235.198.107:3344/view/index.shtml","http://cam-cityhall1.delft.nl/view/view.shtml?id=782&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1"],
                "GERMANY":          ["http://217.22.201.135/view/viewer_index.shtml?id=17222","http://webcam.ampere.inpg.fr/view/index.shtml","http://87.54.59.228/view/viewer_index.shtml?id=193","http://217.30.178.109:46744/view/index.shtml","http://217.78.137.43/view/index.shtml","http://cam.hintertuxerhof.at/view/index.shtml","http://webcam.eins-energie.de/view/index.shtml","http://217.22.201.135/view/viewer_index.shtml?id=17222","http://87.54.59.228/view/viewer_index.shtml?id=193","http://217.30.178.109:46744/view/index.shtml","http://tornet.no-ip.org/view/index.shtml","http://94.125.79.44/view/index.shtml","http://livecam.norran.se/view/viewer_index.shtml?id=34342"]
               
   
    },
    "DATABANK": {
        "Netrunner":   ["https://nullsignal.games","https://netrunnerdb.com",
                        "https://jinteki.net","https://stimhack.com"],
        "Cyberpunk":   ["https://cyberpunkred.com/","https://cyberpunkred.fandom.com/wiki/Cyberpunk_Red"],
        "Security":    ["https://krebsonsecurity.com","https://nmap.org",
                        "https://shodan.io","https://kali.org"],
        "Linux_Open":  ["http://gnu.org","http://kernel.org","http://debian.org","http://archlinux.org"],
        "Tech_Reading":["https://techcrunch.com","https://www.wired.com",
                        "https://arstechnica.com","https://news.ycombinator.com"],
        "Daemon_Novel":["https://en.wikipedia.org/wiki/Daemon_(novel)",
                        "https://www.goodreads.com/book/show/4699570-daemon"],
        "Books":       ["https://www.goodreads.com","https://www.openlibrary.org"],
    },
}

import webbrowser as _wb
_MODULE_META = {
    "DSPACE":   {"label":"DSPACE",   "desc":"Academic Repository Network",  "accent":"#66FFCC"},
    "FTP":      {"label":"FTP",      "desc":"Global FTP Mirror Network",     "accent":"#66FFCC"},
    "CAMS":     {"label":"EYE",      "desc":"Open Camera Network",           "accent":"#66FFCC"},
    "DATABANK": {"label":"DATABANK", "desc":"Link Library",                  "accent":"#66FFCC"},
}


# ─────────────────────────────────────────────
#  NODE MANAGER  (v1 logic + Ollama fallback)
# ─────────────────────────────────────────────
class NodeManager:
    """
    Dual-path router:
      1. Keyword match via DialogBase → original handlers (weather, news, applets…)
      2. No match → Ollama inference → AwardEngine evaluation
    """
    def __init__(self, username="User", ui=None):
        self.username     = username
        self.ui           = ui
        self.dialog       = DialogBase(username)
        self.ollama       = OllamaClient()
        self.award_engine = AwardEngine()
        self.ol_history   : list = []   # Ollama conversation history
        self.turns        = 0
        self._streaming   = False
        self.system_prompt= DEFAULT_SYSTEM_PROMPT

        self.command_map = {
            "databank":      self._handle_databank,
        #   "navigation":    self._handle_navigation,
            "scan_external": self._handle_scan_external,
            "weather":       self._handle_weather,
            "news_general":  lambda d=None: self._handle_news(d, "general"),
            "news_tech":     lambda d=None: self._handle_news(d, "tech"),
            "news_security": lambda d=None: self._handle_news(d, "security"),
            "news_world":    lambda d=None: self._handle_news(d, "world"),
            "search":        self._handle_search,
            "time":          self._handle_time,
            "dspace":        self._handle_dspace,
            "ftp":           self._handle_ftp,
            "eye":           self._handle_eye,
            "cyberstorm":    self._handle_cyberstorm,
            "exit":          self._handle_exit,
        }

    # ── Public entry point ────────────────────
    def process_input(self, user_input: str):
        """
        Synchronous path for keyword intents.
        For Ollama (open-ended), kicks off async inference and returns immediately.
        """
        rep = self.dialog.reply(user_input)

        if rep["matched"]:
            # Known intent — handle in background, return personality quip
            intent = rep.get("intent")
            if intent and intent in self.command_map:
                threading.Thread(
                    target=self.command_map[intent],
                    kwargs={"data": {"user_input": user_input}},
                    daemon=True
                ).start()
            return rep["text"]

        else:
            # Unknown → route to Ollama
            if self._streaming:
                return "Still thinking... one moment."
            threading.Thread(
                target=self._ollama_worker,
                args=(user_input,),
                daemon=True
            ).start()
            return "⬡ Routing to reasoning engine..."

    # ── Ollama inference worker ───────────────
    def _ollama_worker(self, user_text: str):
        self._streaming = True
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.set_status("⬡ OLLAMA REASONING…"))

        try:
            if not self.ollama.is_running():
                raise RuntimeError(
                    "Ollama offline. Start with: ollama serve\n"
                    "Then pull: ollama pull llama3.2:1b"
                )

            self.ol_history.append({"role": "user", "content": user_text})
            msgs = self.ol_history[-16:]

            # Prepare stream slot in UI
            if self.ui:
                self.ui.root.after(0, self.ui.begin_stream_slot)

            t0 = time.time()
            full_response = self.ollama.chat(
                messages       = msgs,
                system         = self.system_prompt,
                temperature    = getattr(self.ui, 'temp_var', None) and self.ui.temp_var.get() or 0.7,
                stream_callback= (lambda tok: self.ui.root.after(0, lambda t=tok: self.ui.append_stream_token(t)))
                                  if self.ui else None,
            )
            elapsed = round(time.time() - t0, 1)

            self.ol_history.append({"role": "assistant", "content": full_response})
            if len(self.ol_history) > 24:
                self.ol_history = self.ol_history[-24:]

            self.turns += 1
            result = self.award_engine.evaluate(user_text, full_response)

            if self.ui:
                self.ui.root.after(0, lambda: self.ui.end_stream_slot(result, elapsed))
                self.ui.root.after(0, self.ui.update_side_panel)
                self.ui.root.after(0, lambda: self.ui.set_status(
                    f"Turn {self.turns} | Score: {result['score']:+.1f} | "
                    f"Total: {self.award_engine.total_score:+.1f} | "
                    f"{elapsed}s | {self.ollama.model}"
                ))

        except RuntimeError as e:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys(f"ENGINE ERROR: {e}"))
                self.ui.root.after(0, lambda: self.ui.set_status("Ollama offline"))
        except Exception as e:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys(f"ERROR: {e}"))
        finally:
            self._streaming = False
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.send_btn.config(state="normal"))

    # ── Background helper ─────────────────────
    def _bg(self, fn, *a, **kw):
        threading.Thread(target=fn, args=a, kwargs=kw, daemon=True).start()

    # ── Intent handlers (v1 unchanged) ────────
    def _handle_databank(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(DataLibApplet))

#    def _handle_navigation(self, data=None):
#        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(NavigationApplet))

    def _handle_dspace(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(DspaceApplet))

    def _handle_ftp(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(FTPApplet))

    def _handle_eye(self, data=None):
        if self.ui: self.ui.root.after(0, lambda: self.ui.mount_applet(EyeApplet))

    def _handle_scan_external(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[Scanner] External scan tool planned for later stages.")) #TODO: Replace this with toolsets on the net edc folder

    def _handle_exit(self, data=None):
        if self.ui: self.ui.root.after(0, self.ui.safe_exit)

    def _handle_time(self, data=None):
        t = datetime.now().strftime("%H:%M:%S")
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", f"Current time: {t}", "ai"))

    def _handle_cyberstorm(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[CYBERSTORM] Opening all camera feeds..."))
            count = 0
            for region, urls in REGISTRY["CAMS"].items():
                for u in urls:
                    _wb.open(u); count += 1
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[CYBERSTORM] {count} feeds opened."))

    def _handle_weather(self, data=None):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys("[DILARA] Fetching weather..."))
            self._bg(self._weather_worker)

    def _weather_worker(self):
        try:
            data = WeatherService.fetch()
            text = WeatherService.format_result(data, WeatherService.DEFAULT_CITY)
        except Exception as e:
            text = f"[Weather] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))

    def _handle_news(self, data=None, category="general"):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[DILARA] Fetching {category} news..."))
            self._bg(self._news_worker, category)

    def _news_worker(self, category):
        try:
            items = RSSService.fetch(category)
            text  = RSSService.format_result(items, category)
        except Exception as e:
            text = f"[RSS] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))

    def _handle_search(self, data=None):
        raw   = (data or {}).get("user_input", "")
        query = SearchService.extract_query(raw)
        if not query:
            if self.ui:
                self.ui.root.after(0, lambda: self.ui.append_sys("[Search] What should I search for?"))
            return
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_sys(f"[DILARA] Searching: {query}..."))
            self._bg(self._search_worker, query)

    def _search_worker(self, query):
        try:
            engine_name, items = SearchService.search(query)
            text = SearchService.format_result(engine_name, items, query)
        except Exception as e:
            text = f"[Search] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("D.I.L.A.R.A.", text, "ai"))


# ─────────────────────────────────────────────
#  REGISTRY APPLETS  (v1 — unchanged)
# ─────────────────────────────────────────────
class RegistryApplet(tk.Frame):
    REGISTRY_KEY = None
    ACCENT = "#66FFCC"; BG = "#161616"; BG_DARK = "#0e0e0e"; BG_HOVER = "#1e2e2e"
    _module = None; _region = None

    def __init__(self, parent, ui=None):
        super().__init__(parent, bg=self.BG)
        self.ui = ui
        self._module = self.REGISTRY_KEY
        self._region = None
        self._build_shell()
        self._navigate()

    def _build_shell(self):
        top = tk.Frame(self, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6,0))
        self._crumb_var = tk.StringVar(value="Main Menu")
        tk.Label(top, textvariable=self._crumb_var, fg=self.ACCENT, bg=self.BG,
                 font=(C["font"],9,"bold"), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(top, text="X", bg="#2a2a2a", fg=self.ACCENT, font=(C["font"],8,"bold"),
                  relief="flat", width=3, command=self._close).pack(side="right")
        tk.Frame(self, bg=self.ACCENT, height=1).pack(fill="x", padx=8, pady=(3,0))
        self._content = tk.Frame(self, bg=self.BG)
        self._content.pack(fill="both", expand=True, padx=8, pady=6)
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, fg="#666", bg=self.BG,
                 font=(C["font"],8), anchor="w").pack(fill="x", padx=10, pady=(0,4))

    def _clear_content(self):
        for w in self._content.winfo_children(): w.destroy()

    def _navigate(self, module=None, region=None):
        self._module = module if module is not None else self._module
        self._region = region
        self._clear_content()
        self._update_crumb()
        if self._module is None:     self._show_root()
        elif self._region is None:   self._show_regions()
        else:                        self._show_urls()

    def _update_crumb(self):
        parts = ["Main Menu"]
        if self._module:
            parts.append(_MODULE_META.get(self._module,{}).get("label",self._module))
        if self._region: parts.append(self._region)
        self._crumb_var.set("  >  ".join(parts))

    def _go_back(self):
        if self._region is not None:   self._navigate(module=self._module, region=None)
        elif self._module is not None: self._navigate(module=None, region=None)

    def _show_root(self):
        self._status_var.set("Select a module to browse.")
        tk.Label(self._content, text="[ DILARA REGISTRY ]", fg=self.ACCENT, bg=self.BG,
                 font=(C["font"],11,"bold")).pack(pady=(4,10))
        grid = tk.Frame(self._content, bg=self.BG)
        grid.pack(fill="both", expand=True)
        for i, (key, meta) in enumerate(sorted(_MODULE_META.items())):
            if key not in REGISTRY: continue
            col = i % 2; row = i // 2
            count   = sum(len(v) for v in REGISTRY[key].values())
            regions = len(REGISTRY[key])
            tile = tk.Frame(grid, bg="#1a2a2a", highlightbackground=self.ACCENT, highlightthickness=1)
            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            tk.Label(tile, text=meta["label"],  fg=self.ACCENT, bg="#1a2a2a", font=(C["font"],11,"bold")).pack(anchor="w",padx=8,pady=(6,1))
            tk.Label(tile, text=meta["desc"],   fg="#aaa",       bg="#1a2a2a", font=(C["font"],8)).pack(anchor="w",padx=8)
            tk.Label(tile, text=f"{regions} regions  |  {count} links", fg="#555", bg="#1a2a2a", font=(C["font"],7)).pack(anchor="w",padx=8,pady=(1,6))
            tile.bind("<Button-1>",   lambda e,k=key: self._navigate(module=k,region=None))
            for ch in tile.winfo_children():
                ch.bind("<Button-1>", lambda e,k=key: self._navigate(module=k,region=None))
            tile.bind("<Enter>", lambda e,t=tile: t.config(bg=self.BG_HOVER))
            tile.bind("<Leave>", lambda e,t=tile: t.config(bg="#1a2a2a"))

    def _show_regions(self):
        data = REGISTRY.get(self._module,{}); meta = _MODULE_META.get(self._module,{})
        self._status_var.set(f"{len(data)} regions available. Click to expand.")
        nav = tk.Frame(self._content,bg=self.BG); nav.pack(fill="x",pady=(0,6))
        tk.Button(nav,text="< Back",bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),
                  relief="flat",command=self._go_back).pack(side="left")
        tk.Label(nav,text=meta.get("desc",""),fg="#888",bg=self.BG,font=(C["font"],8)).pack(side="left",padx=8)
        canvas = tk.Canvas(self._content,bg=self.BG,highlightthickness=0)
        sb = tk.Scrollbar(self._content,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); canvas.pack(side="left",fill="both",expand=True)
        inner = tk.Frame(canvas,bg=self.BG)
        win_id = canvas.create_window((0,0),window=inner,anchor="nw")
        canvas.bind("<Configure>",lambda e:canvas.itemconfig(win_id,width=e.width))
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        for region,urls in data.items():
            row = tk.Frame(inner,bg="#111",highlightbackground="#2a2a2a",highlightthickness=1)
            row.pack(fill="x",pady=2,padx=2)
            tk.Label(row,text=f"  {region}",fg=self.ACCENT,bg="#111",font=(C["font"],9,"bold"),anchor="w",width=18).pack(side="left",padx=(4,0),pady=4)
            tk.Label(row,text=f"{len(urls)} links",fg="#555",bg="#111",font=(C["font"],8)).pack(side="left",padx=6)
            tk.Label(row,text=">",fg=self.ACCENT,bg="#111",font=(C["font"],10,"bold")).pack(side="right",padx=8)
            row.bind("<Button-1>",lambda e,r=region:self._navigate(module=self._module,region=r))
            for ch in row.winfo_children():
                ch.bind("<Button-1>",lambda e,r=region:self._navigate(module=self._module,region=r))
            row.bind("<Enter>",lambda e,f=row:f.config(bg=self.BG_HOVER))
            row.bind("<Leave>",lambda e,f=row:f.config(bg="#111"))

    def _show_urls(self):
        urls = REGISTRY.get(self._module,{}).get(self._region,[])
        self._status_var.set(f"{len(urls)} links. Double-click to open.")
        nav = tk.Frame(self._content,bg=self.BG); nav.pack(fill="x",pady=(0,4))
        tk.Button(nav,text="< Back",bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),relief="flat",command=self._go_back).pack(side="left")
        btn_row = tk.Frame(self._content,bg=self.BG); btn_row.pack(fill="x",pady=(0,4))
        tk.Button(btn_row,text="Open Selected",bg=self.ACCENT,fg="#000",font=(C["font"],8,"bold"),command=self._open_selected).pack(side="left",padx=(0,6))
        tk.Button(btn_row,text="Open All",     bg="#2a2a2a",fg=self.ACCENT,font=(C["font"],8,"bold"),command=self._open_all).pack(side="left")
        self._url_lb = tk.Listbox(self._content,bg=self.BG_DARK,fg="#E5FFE5",
                                  selectbackground="#1a2a2a",activestyle="none",
                                  font=(C["font"],8),relief="flat",borderwidth=0)
        sb = tk.Scrollbar(self._content,orient="vertical",command=self._url_lb.yview)
        self._url_lb.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); self._url_lb.pack(fill="both",expand=True)
        for u in urls: self._url_lb.insert(tk.END,f"  {u}")
        self._url_lb.bind("<Double-Button-1>",self._open_selected)

    def _open_selected(self,event=None):
        if not hasattr(self,"_url_lb"): return
        sel = self._url_lb.curselection()
        if not sel: return
        url = self._url_lb.get(sel[0]).strip(); _wb.open(url)
        self._status_var.set(f"Opened: {url[:60]}")

    def _open_all(self):
        if not hasattr(self,"_url_lb"): return
        urls = [self._url_lb.get(i).strip() for i in range(self._url_lb.size())]
        for u in urls: _wb.open(u)
        self._status_var.set(f"Opened {len(urls)} links")

    def _close(self):
        for w in self.master.winfo_children(): w.destroy()


class DspaceApplet(RegistryApplet):  REGISTRY_KEY = "DSPACE"
class FTPApplet(RegistryApplet):     REGISTRY_KEY = "FTP"
class EyeApplet(RegistryApplet):     REGISTRY_KEY = "CAMS"
class DataLibApplet(RegistryApplet): REGISTRY_KEY = "DATABANK"


# class NavigationApplet(tk.Frame):
#    def __init__(self, parent, ui=None):
#        super().__init__(parent, bg="#161616"); self.ui = ui; self._build()

#    def _build(self):
#        hdr = tk.Frame(self,bg="#161616"); hdr.pack(fill="x",padx=8,pady=8)
#         tk.Label(hdr,text="Navigation",fg="#66FFCC",bg="#161616",font=(C["font"],12,"bold")).pack(side="left")
#         mid = tk.Frame(self,bg="#161616"); mid.pack(fill="x",padx=8,pady=4)
#    tk.Label(mid,text="Destination:",fg="#E5FFE5",bg="#161616",font=(C["font"],10,"bold")).pack(side="left")
#        self.dest_var = tk.StringVar()
#        tk.Entry(mid,textvariable=self.dest_var,width=24,bg="#141414",fg="#E5FFE5",
#                insertbackground="#66FFCC",font=(C["font"],10,"bold")).pack(side="left",padx=6)
#        btns = tk.Frame(self,bg="#161616"); btns.pack(fill="x",padx=8,pady=6)
#        tk.Button(btns,text="Start",bg="#66FFCC",fg="#000",font=(C["font"],9,"bold"),command=self.start_route).pack(side="left",padx=4)
#        tk.Button(btns,text="Stop", bg="#aa4444",fg="#fff",font=(C["font"],9,"bold"),command=self.stop_route).pack(side="left",padx=4)
#        self.out = tk.Text(self,height=6,bg="#0e0e0e",fg="#E5FFE5",insertbackground="#66FFCC",
#                           state="disabled",font=(C["font"],10,"bold"))
#        self.out.pack(fill="both",expand=True,padx=8,pady=(2,8))

#   def start_route(self):
#        dest = self.dest_var.get().strip() or "Unknown"
#        self._append(f"Route to {dest} initialized.")
#        for s in ["Head north 50m","Turn right","Go 10m","Destination on your left"]: self._append(f"• {s}")

#   def stop_route(self): self._append("Route cancelled.")

#   def _append(self,txt):
#        self.out.config(state="normal"); self.out.insert(tk.END,txt+"\n"); self.out.see(tk.END); self.out.config(state="disabled")


# ─────────────────────────────────────────────
#  MAIN UI  (v1 layout + v2 side panel)
# ─────────────────────────────────────────────
class ChatUI:
    def __init__(self, root, username="User"):
        self.root         = root
        self.username     = username
        self._stream_active = False

        self.root.title(APP_TITLE)
        self.root.geometry(DEFAULT_GEOMETRY)
        self.root.configure(bg=C["bg"])
        try: self.root.attributes('-alpha', WINDOW_ALPHA)
        except: pass
        try: self.root.option_add("*Font", (C["font"], 10, "bold"))
        except: pass

        # Managers
        self.node_manager = NodeManager(username, ui=self)
        self.voice_manager= VoiceManager(VOICES_DIR)
        self.last_bot_message = ""

        self._build_layout()
        self._check_ollama_status()

    # ─────────── LAYOUT ──────────────────────
    def _build_layout(self):
        # Outer paned: left (chat) + right (side panel)
        paned = tk.PanedWindow(self.root, orient="horizontal",
                               bg=C["bg"], sashwidth=4, bd=0, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Left: original D.I.L.A.R.A. card
        left = tk.Frame(paned, bg=C["glass"],
                        highlightbackground=C["accent"], highlightthickness=1)
        paned.add(left, minsize=460, width=560)

        # ── Right: sandbox side panel
        right = tk.Frame(paned, bg=C["panel"])
        paned.add(right, minsize=280, width=360)

        self._build_left(left)
        self._build_right(right)

        # Status bar (bottom)
        self.status_var = tk.StringVar(value="READY")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=C["panel"], fg=C["muted"],
                 font=(C["font_mono"],9), anchor="w", padx=12, pady=3
                 ).pack(fill="x", side="bottom")

    # ── LEFT PANEL ────────────────────────────
    def _build_left(self, parent):
        # Header (greeting + profile + voice)
        hdr = tk.Frame(parent, bg=C["glass"], height=150)
        hdr.pack(fill="x", pady=(6,0))

        greeting = self.node_manager.dialog.greet()
        tk.Label(hdr, text=greeting, font=(C["font"],12,"bold"),
                 fg=C["accent"], bg=C["glass"],
                 wraplength=380, justify="center").pack(pady=(6,4))

        pic_frame = tk.Frame(hdr, width=80, height=80, bg="#222")
        pic_frame.pack(pady=2)
        self._load_profile_picture(pic_frame, "profile.png")

        tk.Button(hdr, text="?", font=(C["font"],10,"bold"),
                  bg=C["accent"], fg="#000", width=2,
                  command=self.show_about).place(x=460, y=6)

        if self.voice_manager and self.voice_manager.available_names:
            ctl = tk.Frame(hdr, bg=C["glass"]); ctl.pack(pady=(2,2))
            tk.Label(ctl, text="Voice:", fg=C["text"], bg=C["glass"],
                     font=(C["font"],10,"bold")).pack(side="left")
            self.voice_var = tk.StringVar(
                value=self.voice_manager.active_name or self.voice_manager.available_names[0]
            )
            cb = ttk.Combobox(ctl, textvariable=self.voice_var,
                              values=self.voice_manager.available_names,
                              width=22, state="readonly")
            cb.pack(side="left", padx=6)
            cb.bind("<<ComboboxSelected>>", self._on_voice_select)

        # Chat area
        chat_frame = tk.Frame(parent, bg=C["bg"])
        chat_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.chat_box = scrolledtext.ScrolledText(
            chat_frame, wrap="word",
            bg=C["bg"], fg=C["text"],
            insertbackground=C["accent"],
            font=(C["font"],10,"bold"),
            state="disabled", borderwidth=0,
            highlightthickness=0, padx=8, pady=6,
        )
        self.chat_box.pack(fill="both", expand=True)
        self.chat_box.tag_config("user",    justify="right",  foreground=C["user_fg"])
        self.chat_box.tag_config("ai",      justify="left",   foreground=C["ai_fg"])
        self.chat_box.tag_config("ai_stream",justify="left",  foreground=C["ai_fg"])
        self.chat_box.tag_config("sys",     justify="center", foreground=C["sys_fg"])
        self.chat_box.tag_config("eval_pos",foreground=C["score_pos"], font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_neg",foreground=C["score_neg"], font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_neu",foreground=C["accent2"],   font=(C["font_mono"],8))
        self.chat_box.tag_config("eval_tot",foreground=C["accent"],    font=(C["font_mono"],8,"bold"))
        self.chat_box.tag_config("theorem", foreground=C["good"],      font=(C["font_mono"],8,"bold"))

        # Applet frame
        self.applet_frame = tk.Frame(parent, bg=C["glass"], height=160)
        self.applet_frame.pack(fill="x", padx=6, pady=2)

        # Input row
        ibar = tk.Frame(parent, bg=C["panel"])
        ibar.pack(fill="x", padx=6, pady=(2,8))

        self.input_entry = tk.Entry(
            ibar, font=(C["font"],10,"bold"),
            bg="#141414", fg=C["text"],
            insertbackground=C["accent"],
            width=30,
        )
        self.input_entry.pack(side="left", padx=(6,4), pady=8)
        self.input_entry.bind("<Return>", self.send_message)
        self.input_entry.focus()

        self.send_btn = tk.Button(
            ibar, text="Send", font=(C["font"],10,"bold"),
            bg=C["accent"], fg="#000", width=6,
            command=self.send_message,
            activebackground="#00e0a0",
        )
        self.send_btn.pack(side="left", padx=(0,4))

        tk.Button(ibar, text="🔊", font=(C["font"],12,"bold"),
                  width=3, bg=C["accent"], fg="#000",
                  command=self.speak_last_message).pack(side="left", padx=(0,4))
        tk.Button(ibar, text="🎤", font=(C["font"],12,"bold"),
                  width=3, bg=C["accent"], fg="#000",
                  command=self.listen_speech).pack(side="left")

        # TTS sliders
        if self.voice_manager and self.voice_manager.engine:
            sl = tk.Frame(ibar, bg=C["panel"]); sl.pack(side="right", padx=6)
            tk.Label(sl,text="Rate",bg=C["panel"],fg=C["text"],font=(C["font"],9,"bold")).grid(row=0,column=0,padx=2)
            self.rate_var = tk.IntVar(value=self.voice_manager.active_rate or
                                     self.voice_manager.engine.getProperty('rate') or 200)
            tk.Scale(sl,from_=50,to=300,orient="horizontal",length=100,
                     bg=C["panel"],highlightthickness=0,troughcolor="#222",fg=C["text"],
                     command=self._on_rate,variable=self.rate_var).grid(row=0,column=1)
            tk.Label(sl,text="Vol",bg=C["panel"],fg=C["text"],font=(C["font"],9,"bold")).grid(row=1,column=0,padx=2)
            self.vol_var = tk.DoubleVar(value=self.voice_manager.active_volume
                                        if self.voice_manager.active_volume is not None else 1.0)
            tk.Scale(sl,from_=0.0,to=1.0,resolution=0.05,orient="horizontal",length=100,
                     bg=C["panel"],highlightthickness=0,troughcolor="#222",fg=C["text"],
                     command=self._on_vol,variable=self.vol_var).grid(row=1,column=1)

    # ── RIGHT SIDE PANEL ─────────────────────
    def _build_right(self, parent):
        canvas = tk.Canvas(parent, bg=C["panel"], highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self._side_inner = tk.Frame(canvas, bg=C["panel"])
        self._side_inner.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self._side_inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(fill="both", expand=True)

        def _sec(title):
            tk.Label(self._side_inner, text=f"⬡  {title}",
                     bg=C["panel"], fg=C["muted"],
                     font=(C["font_mono"],8,"bold"), anchor="w"
                     ).pack(fill="x", padx=10, pady=(12,2))
            tk.Frame(self._side_inner, bg=C["border"], height=1).pack(fill="x", padx=10)

        # Score
        _sec("AWARD SCORE")
        self.score_var = tk.StringVar(value="+0")
        tk.Label(self._side_inner, textvariable=self.score_var,
                 bg=C["panel"], fg=C["accent"],
                 font=(C["font_mono"],30,"bold")).pack(pady=(4,0))
        tk.Label(self._side_inner, text="CUMULATIVE REWARD",
                 bg=C["panel"], fg=C["muted"], font=(C["font_mono"],8)).pack()
        bar_frame = tk.Frame(self._side_inner, bg=C["border"], height=4)
        bar_frame.pack(fill="x", padx=14, pady=6); bar_frame.pack_propagate(False)
        self.score_bar = tk.Frame(bar_frame, bg=C["accent"], height=4)
        self.score_bar.place(x=0, y=0, relwidth=0.5, relheight=1.0)

        # Metrics
        _sec("METRICS")
        mf = tk.Frame(self._side_inner, bg=C["panel"]); mf.pack(fill="x", padx=10, pady=4)
        self.m_vars = {}
        for key, label in [("turns","TURNS"),("theorems","THEOREMS"),
                            ("conjectures","CONJECTURES"),("avg","AVG SCORE")]:
            row = tk.Frame(mf, bg=C["panel"]); row.pack(fill="x", pady=1)
            tk.Label(row,text=label,bg=C["panel"],fg=C["muted"],
                     font=(C["font_mono"],9),width=14,anchor="w").pack(side="left")
            v = tk.StringVar(value="0" if key!="avg" else "—"); self.m_vars[key]=v
            tk.Label(row,textvariable=v,bg=C["panel"],fg=C["accent2"],
                     font=(C["font_mono"],9,"bold")).pack(side="right")

        # Theory Base
        _sec("THEORY BASE")
        self.theory_box = tk.Text(self._side_inner, bg=C["bg"], fg=C["text"],
                                  font=(C["font_mono"],8), height=9, wrap="word",
                                  state="disabled", relief="flat",
                                  highlightthickness=0, padx=6, pady=4)
        self.theory_box.pack(fill="x", padx=10, pady=4)
        self.theory_box.tag_config("theorem_t",    foreground=C["good"])
        self.theory_box.tag_config("conjecture_t", foreground=C["accent2"])
        self.theory_box.tag_config("ts_t",         foreground=C["muted"])

        # Award weight sliders
        _sec("AWARD WEIGHTS")
        wf = tk.Frame(self._side_inner, bg=C["panel"]); wf.pack(fill="x", padx=10, pady=4)
        self.weight_vars = {}
        for key,label,mn,mx,default,res in [
            ("novelty",   "NOVELTY",     0,20,10,1.0),
            ("parsimony", "PARSIMONY",   0, 3,0.5,0.1),
            ("depth",     "DEPTH",       0,15, 5,1.0),
            ("grounding", "GROUNDING",   0,20, 8,1.0),
            ("action",    "ACTION",      0,10, 3,1.0),
        ]:
            row=tk.Frame(wf,bg=C["panel"]); row.pack(fill="x",pady=2)
            val_var=tk.DoubleVar(value=default); self.weight_vars[key]=val_var
            val_lbl=tk.Label(row,textvariable=val_var,bg=C["panel"],fg=C["accent"],
                             font=(C["font_mono"],8),width=5,anchor="e"); val_lbl.pack(side="right")
            tk.Label(row,text=label,bg=C["panel"],fg=C["muted"],
                     font=(C["font_mono"],8),width=12,anchor="w").pack(side="left")
            def _upd(v,k=key,var=val_var):
                self.node_manager.award_engine.weights[k]=round(float(v),2); var.set(round(float(v),2))
            tk.Scale(row,from_=mn,to=mx,resolution=res,orient="horizontal",variable=val_var,
                     bg=C["panel"],fg=C["text"],troughcolor=C["border"],
                     activebackground=C["accent"],highlightthickness=0,
                     showvalue=False,length=80,command=_upd).pack(side="right",padx=(0,4))

        # Ollama status + model selector
        _sec("OLLAMA / MODEL")
        om = tk.Frame(self._side_inner, bg=C["panel"]); om.pack(fill="x", padx=10, pady=4)
        self.ollama_lbl = tk.Label(om, text="● CHECKING…", bg=C["panel"], fg=C["warn"],
                                   font=(C["font_mono"],9,"bold")); self.ollama_lbl.pack(anchor="w")
        tk.Label(om,text="MODEL",bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8)).pack(anchor="w",pady=(6,0))
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.model_combo = ttk.Combobox(om, textvariable=self.model_var,
                                        values=[DEFAULT_MODEL], state="readonly", width=22,
                                        font=(C["font_mono"],9))
        self.model_combo.pack(fill="x", pady=2)
        self.model_combo.bind("<<ComboboxSelected>>",
                              lambda e: setattr(self.node_manager.ollama, 'model', self.model_var.get()))

        def _btn(t, cmd):
            tk.Button(om,text=t,command=cmd,bg=C["panel"],fg=C["accent2"],
                      font=(C["font_mono"],8,"bold"),relief="flat",cursor="hand2",
                      highlightthickness=1,highlightbackground=C["border"],pady=3
                      ).pack(fill="x",pady=2)
        _btn("↺ REFRESH MODELS", self._refresh_models)
        _btn("⬇ PULL MODEL",     self._pull_model_dialog)

        tk.Label(om,text="TEMPERATURE",bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8)).pack(anchor="w",pady=(8,0))
        self.temp_var = tk.DoubleVar(value=0.7)
        tr = tk.Frame(om,bg=C["panel"]); tr.pack(fill="x")
        tk.Scale(tr,from_=0.0,to=2.0,resolution=0.05,orient="horizontal",variable=self.temp_var,
                 bg=C["panel"],fg=C["text"],troughcolor=C["border"],
                 activebackground=C["accent"],highlightthickness=0,length=120).pack(side="left")
        tk.Label(tr,textvariable=self.temp_var,bg=C["panel"],fg=C["accent"],
                 font=(C["font_mono"],9),width=4).pack(side="left")

        # System prompt
        _sec("REASONING CONTEXT")
        self.sys_text = tk.Text(self._side_inner, bg=C["bg"], fg=C["text"],
                                font=(C["font_mono"],8), height=8, wrap="word",
                                relief="flat", highlightthickness=1,
                                highlightcolor=C["accent2"],
                                highlightbackground=C["border"], padx=6, pady=4)
        self.sys_text.insert("1.0", DEFAULT_SYSTEM_PROMPT)
        self.sys_text.pack(fill="x", padx=10, pady=4)

        cf = tk.Frame(self._side_inner,bg=C["panel"]); cf.pack(fill="x",padx=10)
        tk.Button(cf,text="APPLY CONTEXT",command=self._apply_system,
                  bg=C["panel"],fg=C["accent2"],font=(C["font_mono"],8,"bold"),
                  relief="flat",highlightthickness=1,highlightbackground=C["border"],
                  pady=3).pack(fill="x",pady=2)
        tk.Button(cf,text="CLEAR SESSION",command=self._clear_session,
                  bg=C["panel"],fg=C["score_neg"],font=(C["font_mono"],8,"bold"),
                  relief="flat",highlightthickness=1,highlightbackground=C["score_neg"],
                  pady=3).pack(fill="x",pady=2)

    # ─────────── CHAT DISPLAY ────────────────
    def _write(self, text, tag=None):
        self.chat_box.config(state="normal")
        if tag: self.chat_box.insert(tk.END, text, tag)
        else:   self.chat_box.insert(tk.END, text)
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")

    def append_chat(self, sender, message, tag="ai"):
        self._write(f"{sender}: {message}\n", tag)
        if tag == "ai":
            self.last_bot_message = message

    def append_sys(self, message):
        self.append_chat("System", message, tag="sys")

    def status_to_chat(self, message):
        self.append_sys(message)

    def begin_stream_slot(self):
        self._write("\nD.I.L.A.R.A.: ", "ai")
        self._stream_active = True

    def append_stream_token(self, token):
        if self._stream_active:
            self._write(token, "ai_stream")

    def end_stream_slot(self, result, elapsed):
        self._stream_active = False
        self._write("\n", "ai")
        # Show eval breakdown
        tag_map = {"pos":"eval_pos","neg":"eval_neg","neu":"eval_neu"}
        for label, kind in result["breakdown"]:
            self._write(f"[{label}] ", tag_map.get(kind,"eval_neu"))
        self._write(f"  TOTAL: {result['score']:+.1f}  ·  {elapsed}s\n", "eval_tot")
        if result.get("promotion"):
            p = result["promotion"]
            tag = "theorem" if p["type"]=="THEOREM" else "eval_neu"
            self._write(f"⬡ {p['type']} REGISTERED — score {p['score']:+.1f}\n", tag)

    def set_status(self, msg):
        self.status_var.set(msg)

    # ─────────── SEND ────────────────────────
    def send_message(self, event=None):
        user_text = self.input_entry.get().strip()
        if not user_text: return
        self.append_chat(self.username, user_text, "user")
        self.input_entry.delete(0, tk.END)
        self.send_btn.config(state="disabled")

        bot_text = self.node_manager.process_input(user_text)
        if bot_text:
            self.append_chat("D.I.L.A.R.A.", bot_text, "ai")

        # Re-enable unless Ollama worker is streaming
        if not self.node_manager._streaming:
            self.send_btn.config(state="normal")

    # ─────────── SIDE PANEL UPDATE ───────────
    def update_side_panel(self):
        ae    = self.node_manager.award_engine
        total = ae.total_score
        self.score_var.set(f"{total:+.1f}" if total != 0 else "+0")
        pct = min(1.0, max(0.0, 0.5 + total / 120))
        self.score_bar.place(relwidth=pct)
        self.score_bar.config(bg=C["score_pos"] if total >= 0 else C["score_neg"])

        self.m_vars["turns"].set(str(self.node_manager.turns))
        self.m_vars["theorems"].set(str(len(ae.theorems)))
        self.m_vars["conjectures"].set(str(len(ae.conjectures)))
        avg = ae.score_history
        self.m_vars["avg"].set(f"{sum(avg)/len(avg):+.1f}" if avg else "—")

        # Theory Base
        all_e = ([("THEOREM",e) for e in ae.theorems[-4:]] +
                 [("CONJECTURE",e) for e in ae.conjectures[-4:]])
        all_e.sort(key=lambda x: x[1]["ts"], reverse=True)
        self.theory_box.config(state="normal")
        self.theory_box.delete("1.0", tk.END)
        if not all_e:
            self.theory_box.insert(tk.END, "Empty — awaiting first proof\n", "ts_t")
        for t_type, entry in all_e[:6]:
            col = "theorem_t" if t_type=="THEOREM" else "conjecture_t"
            self.theory_box.insert(tk.END,
                f"[{t_type}] {entry['score']:+.1f}  @{entry['ts']}\n", col)
            self.theory_box.insert(tk.END, f"  {entry['text']}\n", "ts_t")
        self.theory_box.config(state="disabled")

    # ─────────── OLLAMA MANAGEMENT ───────────
    def _check_ollama_status(self):
        def _check():
            running = self.node_manager.ollama.is_running()
            label   = "● OLLAMA: ONLINE" if running else "● OLLAMA: OFFLINE"
            color   = C["good"] if running else C["score_neg"]
            self.root.after(0, lambda: self.ollama_lbl.config(text=label, fg=color))
            if running:
                self.root.after(0, self._refresh_models)
                self.root.after(0, lambda: self.append_sys(
                    "Ollama detected. Reasoning engine armed. Try asking something open-ended."))
            else:
                self.root.after(0, lambda: self.append_sys(
                    "Ollama offline. Keyword commands still work.\n"
                    "Start Ollama: ollama serve | Pull: ollama pull llama3.2:1b"))
        threading.Thread(target=_check, daemon=True).start()

    def _refresh_models(self):
        def _work():
            models = self.node_manager.ollama.list_models()
            if models:
                self.root.after(0, lambda: self.model_combo.config(values=models))
                if DEFAULT_MODEL in models:
                    self.root.after(0, lambda: self.model_var.set(DEFAULT_MODEL))
                else:
                    self.root.after(0, lambda: self.model_var.set(models[0]))
                self.node_manager.ollama.model = self.model_var.get()
                self.root.after(0, lambda: self.append_sys(
                    f"Models: {', '.join(models)}"))
        threading.Thread(target=_work, daemon=True).start()

    def _pull_model_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Pull Model"); dlg.configure(bg=C["panel"])
        dlg.geometry("360x160"); dlg.resizable(False,False)
        tk.Label(dlg, text="Model name (e.g. llama3.2:1b, phi3:mini):",
                 bg=C["panel"],fg=C["text"],font=(C["font_mono"],9)).pack(padx=14,pady=(14,4),anchor="w")
        name_var = tk.StringVar(value="llama3.2:1b")
        tk.Entry(dlg,textvariable=name_var,bg=C["bg"],fg=C["text"],
                 font=(C["font_mono"],10),relief="flat",insertbackground=C["accent"]
                 ).pack(fill="x",padx=14)
        prog_var = tk.StringVar(value="Waiting…")
        tk.Label(dlg,textvariable=prog_var,bg=C["panel"],fg=C["muted"],
                 font=(C["font_mono"],8),wraplength=320).pack(padx=14,pady=4)
        def _do():
            model=name_var.get().strip()
            if not model: return
            prog_var.set(f"Pulling {model}…")
            def _work():
                ok,msg=self.node_manager.ollama.pull_model(model,
                    callback=lambda s: self.root.after(0,lambda ss=s:prog_var.set(ss[:60])))
                if ok:
                    self.root.after(0,lambda:self.append_sys(f"Pull complete: {model}"))
                    self.root.after(0,self._refresh_models)
                    self.root.after(0,dlg.destroy)
                else:
                    self.root.after(0,lambda:prog_var.set(f"FAILED: {msg[:50]}"))
            threading.Thread(target=_work,daemon=True).start()
        tk.Button(dlg,text="PULL",command=_do,bg=C["accent"],fg="#000",
                  font=(C["font_mono"],9,"bold"),relief="flat").pack(pady=6)

    # ─────────── CONTROLS ────────────────────
    def _apply_system(self):
        self.node_manager.system_prompt = self.sys_text.get("1.0","end").strip()
        self.node_manager.ol_history.clear()
        self.append_sys("Reasoning context updated. Ollama history cleared.")

    def _clear_session(self):
        if not messagebox.askyesno("Clear Session",
                                   "Reset Ollama history, theory base and scores?",
                                   parent=self.root):
            return
        self.node_manager.ol_history.clear()
        self.node_manager.award_engine.reset()
        self.node_manager.turns = 0
        self.score_var.set("+0")
        self.score_bar.place(relwidth=0.5)
        for k in self.m_vars: self.m_vars[k].set("0" if k!="avg" else "—")
        self.theory_box.config(state="normal"); self.theory_box.delete("1.0",tk.END)
        self.theory_box.insert(tk.END,"Empty — awaiting first proof\n","ts_t")
        self.theory_box.config(state="disabled")
        self.append_sys("Session cleared. Keyword commands still active.")

    def mount_applet(self, applet_class):
        for w in self.applet_frame.winfo_children(): w.destroy()
        app = applet_class(self.applet_frame, ui=self)
        app.pack(fill="both", expand=True)

    def speak_last_message(self):
        if not self.last_bot_message:
            messagebox.showinfo("TTS","No message to speak yet."); return
        if self.voice_manager:
            self.voice_manager.speak_async(self.last_bot_message)

    def _on_voice_select(self, evt=None):
        choice = getattr(self,"voice_var",None)
        if choice and self.voice_manager:
            self.voice_manager.set_voice(choice.get())

    def _on_rate(self, val):
        try: self.voice_manager.set_rate(int(float(val)))
        except: pass

    def _on_vol(self, val):
        try: self.voice_manager.set_volume(float(val))
        except: pass

    def _load_profile_picture(self, frame, image_path):
        try:
            if PIL_OK and Path(image_path).exists():
                img = Image.open(image_path).resize((80,80))
                ph  = ImageTk.PhotoImage(img)
                lbl = tk.Label(frame, image=ph, bg="#222")
                lbl.image = ph; lbl.pack()
            else:
                tk.Label(frame, text="[DILARA]", bg="#222", fg=C["accent"],
                         font=(C["font"],9,"bold")).pack()
        except Exception as e:
            tk.Label(frame, text="[No Image]", bg="#222", fg="gray").pack()

    def show_about(self):
        messagebox.showinfo("About / Help",
            f"{APP_TITLE}\n\n"
            "Keyword commands: news, weather, search [term], tech news,\n"
            "  databank, navigation, dspace, ftp, eye, cyberstorm\n\n"
            "Open-ended prompts → Ollama reasoning engine (offline LLM)\n"
            "Award/Punish framework evaluates every Ollama response.\n\n"
            "Shortcuts:\n"
            "  🔊 speaks last response  •  🎤 mic input (Vosk / SR)\n\n"
            "© Tekno Tasarım Systems"
        )

    def safe_exit(self):
        try: self.root.destroy()
        except: pass

    # ─────────── SPEECH INPUT ────────────────
    def listen_speech(self):
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        if VOSK_OK and Path(VOSK_MODEL_DIR).exists():
            try:
                self.root.after(0, lambda: self.append_sys("[VOSK] Listening…"))
                model = vosk.Model(VOSK_MODEL_DIR)
                rec   = vosk.KaldiRecognizer(model, 16000)
                data  = sd.rec(int(6 * 16000), samplerate=16000, channels=1, dtype='int16')
                sd.wait()
                rec.AcceptWaveform(data.tobytes())
                text = json.loads(rec.FinalResult()).get("text","").strip()
                if not text:
                    self.root.after(0, lambda: self.append_sys("[VOSK] No speech detected.")); return
                self.root.after(0, lambda: (
                    self.input_entry.delete(0,tk.END),
                    self.input_entry.insert(0,text),
                    self.send_message()
                ))
                return
            except Exception as e:
                self.root.after(0, lambda: self.append_sys(f"[VOSK] Error: {e}"))

        if SR_OK:
            try:
                r = sr.Recognizer()
                with sr.Microphone() as src:
                    self.root.after(0, lambda: self.append_sys("[SR] Listening…"))
                    r.adjust_for_ambient_noise(src)
                    audio = r.listen(src, timeout=5, phrase_time_limit=8)
                text = r.recognize_google(audio)
                self.root.after(0, lambda: (
                    self.input_entry.delete(0,tk.END),
                    self.input_entry.insert(0,text),
                    self.send_message()
                ))
            except sr.WaitTimeoutError:
                self.root.after(0, lambda: self.append_sys("[SR] Timed out."))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self.append_sys("[SR] Could not understand audio."))
            except Exception as e:
                self.root.after(0, lambda: self.append_sys(f"[SR] Error: {e}"))
        else:
            self.root.after(0, lambda: messagebox.showerror(
                "Speech Input", "Neither Vosk nor SpeechRecognition available."))


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    Path(DATABANK_PATH).mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app  = ChatUI(root, username="Fatih")
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()
