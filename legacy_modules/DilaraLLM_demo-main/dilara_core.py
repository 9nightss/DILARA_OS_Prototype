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

#this is an early iteration of the dilara project but this ui is specifically made for AR envoirnment 
#which is the next in line on the developement cycle 
#thats why this is here...


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
APP_TITLE = "D.I.L.A.R.A. Core v1.0 (Vision UI)"
DEFAULT_GEOMETRY = "500x800"
WINDOW_ALPHA = 0.88
DATABANK_PATH = "./databank"
VOICES_DIR = "./voices"
VOSK_MODEL_DIR = "./vosk_model"     # place model folder here (rename it to 'vosk_model')

# -------------------------------
# VoiceManager
# -------------------------------
class VoiceManager:
    """
    Unified voice layer:
      - Discover app-bundled voice sets (./voices/*/voice.json)
      - Fallback to OS voices via pyttsx3
      - Expose selectable list and apply rate/volume
    """
    def __init__(self, voices_dir=VOICES_DIR):
        self.voices_dir = Path(voices_dir)
        self.custom_sets = {}        # name -> metadata (voice.json)
        self.engine = None
        self.installed_voices = []   # pyttsx3 voice objects
        self.available_names = []    # UI-friendly names (custom first, then OS::voiceName)
        self.active_name = None
        self.active_rate = None
        self.active_volume = None

        if not TTS_OK:
            print("[VoiceManager] TTS engine unavailable.")
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
            print("[VoiceManager] Failed retrieving OS voices:", e)
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
                    except Exception as e:
                        print(f"[VoiceManager] Invalid {meta_path}: {e}")

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

        # Custom set?
        if display_name in self.custom_sets:
            meta = self.custom_sets[display_name]
            target = (meta.get("match_name_contains") or "").lower()
            if target:
                for v in self.installed_voices:
                    nm = (getattr(v, "name", "") or getattr(v, "id", "")).lower()
                    if target in nm:
                        try:
                            self.engine.setProperty('voice', v.id)
                        except Exception as e:
                            print("[VoiceManager] set voice failed:", e)
                        break
            # rate/volume overrides
            if meta.get("rate"):
                self.set_rate(int(meta["rate"]))
            if meta.get("volume") is not None:
                self.set_volume(float(meta["volume"]))
            return

        # OS voice selection (label starts with OS::)
        if display_name.startswith("OS::"):
            voice_name = display_name[4:]
            for v in self.installed_voices:
                nm = getattr(v, "name", None) or getattr(v, "id", "")
                if nm == voice_name:
                    try:
                        self.engine.setProperty('voice', v.id)
                    except Exception as e:
                        print("[VoiceManager] set OS voice failed:", e)
                    break

    def set_rate(self, rate: int):
        self.active_rate = rate
        if TTS_OK and self.engine:
            try:
                self.engine.setProperty('rate', rate)
            except Exception:
                pass

    def set_volume(self, volume: float):
        self.active_volume = volume
        if TTS_OK and self.engine:
            try:
                self.engine.setProperty('volume', volume)
            except Exception:
                pass

    def speak_async(self, text: str):
        if not TTS_OK or not self.engine:
            messagebox.showinfo("TTS", "TTS engine not available.")
            return

        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print("[VoiceManager] TTS error:", e)

        threading.Thread(target=_run, daemon=True).start()

# -------------------------------
# DialogBase (intent + text)
# -------------------------------
class DialogBase:
    """
    Dialogue & intent layer. Returns {"text": str, "intent": Optional[str]}
    """
    def __init__(self, username="User"):
        self.username = username
        self.time = datetime.now()
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

    @staticmethod
    def fetch(category="general"):
        feeds = RSSService.FEEDS.get(category, RSSService.FEEDS["general"])
        results = []
        for feed_name, url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DILARA/1.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw = resp.read()
                root = ET.fromstring(raw)
                # Handle both RSS and Atom
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)
                count = 0
                for item in items:
                    if count >= RSSService.MAX_ITEMS:
                        break
                    title_el = item.find("title") or item.find("atom:title", ns)
                    link_el  = item.find("link")  or item.find("atom:link", ns)
                    title = (title_el.text or "").strip() if title_el is not None else "No title"
                    title = html_lib.unescape(title)
                    link  = (link_el.get("href") or link_el.text or "").strip() if link_el is not None else ""
                    results.append((feed_name, title, link))
                    count += 1
                if results:
                    break  # got enough from first working feed
            except Exception as e:
                print(f"[RSS] {feed_name} failed: {e}")
                continue
        return results

    @staticmethod
    def format_result(items, category):
        if not items:
            return "[RSS] Could not reach any feeds. Check your connection."
        feed_name = items[0][0]
        lines = [f"[ {feed_name} -- {category.upper()} ]", ""]
        for _, title, link in items:
            lines.append(f"  * {title}")
            if link:
                lines.append(f"    {link[:80]}")
        return "\n".join(lines)


# -------------------------------
# SearchService  (Google via scrape -- zero API key)
# -------------------------------
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
        import random as _r
        return {
            "User-Agent": _r.choice(SearchService._UA_POOL),
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
        import re
        results = []
        pattern = re.compile(
            r'<a[^>]+href="/url\?q=([^"&]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url = urllib.parse.unquote(m.group(1))
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
        import re
        results = []
        # Bing: <h2><a href="https://...">title</a></h2>
        pattern = re.compile(
            r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"bing.com", "microsoft.com", "msn.com"}
        for m in pattern.finditer(html_text):
            url = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            title = html_lib.unescape(title)
            if url.startswith("http") and title and not any(s in url for s in skip):
                results.append((title, url))
            if len(results) >= SearchService.MAX_RESULTS:
                break
        return results

    # ------------------------------------------------------------------ DuckDuckGo  (HTML endpoint)
    @staticmethod
    def _fetch_ddg(query: str) -> str:
        enc = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={enc}&kl=us-en"
        req = urllib.request.Request(url, headers=SearchService._headers())
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_ddg(html_text: str):
        import re
        results = []
        # DDG HTML: result links look like //duckduckgo.com/l/?uddg=<encoded-url>&...
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="//duckduckgo\.com/l/\?uddg=([^"&]+)[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        for m in pattern.finditer(html_text):
            url = urllib.parse.unquote(m.group(1))
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
        import re
        results = []
        # Brave: <a href="https://..." class="result-header">...</a> with inner title span
        pattern = re.compile(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result-header[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        skip = {"brave.com"}
        for m in pattern.finditer(html_text):
            url = m.group(1).strip()
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
        ("Bing",       _fetch_bing.__func__,    _parse_bing.__func__),
        ("DuckDuckGo", _fetch_ddg.__func__,     _parse_ddg.__func__),
        ("Brave",      _fetch_brave.__func__,   _parse_brave.__func__),
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
                items = parse_fn(html_text)
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

# -------------------------------
# NodeManager
# -------------------------------
class NodeManager:
    """
    Routes dialog intents to UI applets; keeps the 'active node' simple.
    """
    def __init__(self, username="User", ui=None):
        self.username = username
        self.ui = ui
        self.nodes = {"dialog": DialogBase(username)}
        self.active_node = "dialog"
        self.command_map = {
            "databank":      self.handle_databank,
            "navigation":    self.handle_navigation,
            "scan_external": self.handle_scan_external,
            "weather":       self.handle_weather,
            "news_general":  lambda data=None: self.handle_news(data, "general"),
            "news_tech":     lambda data=None: self.handle_news(data, "tech"),
            "news_security": lambda data=None: self.handle_news(data, "security"),
            "news_world":    lambda data=None: self.handle_news(data, "world"),
            "search":        self.handle_search,
            "time":          self.handle_time,
            "dspace":        self.handle_dspace,
            "ftp":           self.handle_ftp,
            "eye":           self.handle_eye,
            "cyberstorm":    self.handle_cyberstorm,
        }

    def process_input(self, user_input: str) -> str:
        rep = self.nodes[self.active_node].reply(user_input)
        intent, text = rep.get("intent"), rep["text"]

        if intent and intent in self.command_map:
            try:
                self.command_map[intent](data={"user_input": user_input})
            except Exception as e:
                print(f"[NodeManager] intent '{intent}' failed:", e)

        if intent == "exit" and self.ui:
            self.ui.safe_exit()

        return text

    def handle_databank(self, data=None):
        if self.ui:
            self.ui.mount_applet(DataLibApplet)

    def handle_navigation(self, data=None):
        if self.ui:
            self.ui.mount_applet(NavigationApplet)

    def handle_dspace(self, data=None):
        if self.ui:
            self.ui.mount_applet(DspaceApplet)

    def handle_ftp(self, data=None):
        if self.ui:
            self.ui.mount_applet(FTPApplet)

    def handle_eye(self, data=None):
        if self.ui:
            self.ui.mount_applet(EyeApplet)

    def handle_cyberstorm(self, data=None):
        """Open all CAMS feeds across all regions -- the old chaos mode, safely."""
        if self.ui:
            self.ui.status_to_chat("[CYBERSTORM] Opening all camera feeds...")
            import webbrowser as _wb
            count = 0
            for region, urls in REGISTRY["CAMS"].items():
                for u in urls:
                    _wb.open(u)
                    count += 1
            self.ui.status_to_chat(f"[CYBERSTORM] {count} feeds opened.")

    def handle_scan_external(self, data=None):
        if self.ui:
            self.ui.status_to_chat("[Scanner] External scan tool is planned for later stages.")

    def _bg(self, fn, *args, **kwargs):
        """Run fn in background thread; results go to UI via root.after."""
        threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()

    # ---- Weather ----
    def handle_weather(self, data=None):
        if self.ui:
            self.ui.status_to_chat("[DILARA] Fetching weather...")
            self._bg(self._weather_worker)

    def _weather_worker(self):
        try:
            result = WeatherService.fetch()
            text = WeatherService.format_result(result, WeatherService.DEFAULT_CITY)
        except Exception as e:
            text = f"[Weather] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("DILARA", text, tag="ai"))

    # ---- News / RSS ----
    def handle_news(self, data=None, category="general"):
        if self.ui:
            self.ui.status_to_chat(f"[DILARA] Fetching {category} news...")
            self._bg(self._news_worker, category)

    def _news_worker(self, category):
        try:
            items = RSSService.fetch(category)
            text = RSSService.format_result(items, category)
        except Exception as e:
            text = f"[RSS] Error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("DILARA", text, tag="ai"))

    # ---- Search ----
    def handle_search(self, data=None):
        raw = (data or {}).get("user_input", "")
        query = SearchService.extract_query(raw)
        if not query:
            if self.ui:
                self.ui.status_to_chat("[Search] What should I search for?")
            return
        if self.ui:
            self.ui.status_to_chat(f"[DILARA] Searching: {query}...")
            self._bg(self._search_worker, query)

    def _search_worker(self, query):
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.status_to_chat("[Search] Trying Google..."))
        try:
            engine_name, items = SearchService.search(query)
            if engine_name and engine_name != "Google":
                self.ui.root.after(0, lambda n=engine_name: self.ui.status_to_chat(
                    f"[Search] Google blocked -- got results from {n}."))
            text = SearchService.format_result(engine_name, items, query)
        except Exception as e:
            text = f"[Search] Unexpected error: {e}"
        if self.ui:
            self.ui.root.after(0, lambda: self.ui.append_chat("DILARA", text, tag="ai"))

    # ---- Time ----
    def handle_time(self, data=None):
        pass  # reply text already shows the time; nothing extra needed

# -------------------------------
# Applets
# -------------------------------

# ================================================================
# Registry  (DSPACE / FTP / CAMS / DATABANK URL library)
# ================================================================
REGISTRY = {
    "DSPACE": {
        "Turkey":   [
            "http://dspace.marmara.edu.tr",
            "http://acikerisim.tbmm.gov.tr:8080/xmlui/",
            "http://acikerisim.ikc.edu.tr:8080/xmlui",
            "http://acikerisim.fsm.edu.tr:8080/xmlui",
            "http://acikerisim.kirklareli.edu.tr:8080/xmlui",
            "http://openaccess.izu.edu.tr",
            "http://openaccess.firat.edu.tr/xmlui/?locale-attribute=tr",
            "http://acikerisim.khas.edu.tr:8080/xmlui",
            "http://earsiv.kmu.edu.tr",
            "http://openaccess.artvin.edu.tr/xmlui",
            "http://earsiv.atauni.edu.tr/xmlui",
            "http://acikerisim.kocaeli.edu.tr:8080/xmlui",
            "http://acikerisim.nigde.edu.tr:8080/jspui",
        ],
        "India":    ["http://dspace.cusat.ac.in/jspui", "http://dspace.library.iitb.ac.in/jspui",
                     "http://dspace.gipe.ac.in/xmlui"],
        "USA":      ["http://dspace.mit.edu", "http://dspace.lib.rochester.edu",
                     "http://dspace.lib.miamioh.edu/xmlui", "http://dspace.iup.edu",
                     "http://dspace.library.colostate.edu", "http://dspace.library.uvic.ca",
                     "http://dspace.lib.hawaii.edu"],
        "England":  ["http://dspace.lib.ntua.gr", "http://dspace.lboro.ac.uk/dspace-jspui",
                     "http://lib.cam.ac.uk/repository", "http://dspace.lib.cranfield.ac.uk"],
        "Germany":  ["http://dspace.vsb.cz", "http://dspace.ut.ee"],
        "Asia":     ["http://dspace.lib.niigata-u.ac.jp/dspace", "http://dspace.library.uu.nl",
                     "http://dspace.lib.kanazawa-u.ac.jp", "http://dspace.lib.sp.edu.sg/xmlui",
                     "http://dspace.lib.cuhk.edu.hk"],
        "Russia":   ["http://dspace.lib.ntua.gr", "http://dspace.lib.uom.gr"],
    },
    "FTP": {
        "Algeria":        ["http://ctan.epsttlemcen.dz"],
        "Australia":      ["http://encomwireless.com","http://encomkb.encom.com.au",
                           "http://encomsystems.com","http://encom.info"],
        "Austria":        ["http://mirror.easyname.at"],
        "Belarus":        ["http://mirror.datacenter.by"],
        "Brazil":         ["http://ftp.lasca.ic.unicamp.br","http://linorg.usp.br"],
        "Canada":         ["http://ctan.math.ca","http://ctan.mirror.rafal.ca",
                           "http://mirror.its.dal.ca","http://ftp.muug.ca"],
        "China":          ["http://mirrors.ustc.edu.cn"],
        "Costa Rica":     ["http://mirrors.ucr.ac.cr"],
        "Czech Republic": ["http://ftp.cvut.cz","http://mirrors.nic.cz"],
        "Denmark":        ["http://mirrors.dotsrc.org"],
        "Finland":        ["http://ftp.funet.fi"],
        "France":         ["http://distribcoffee.ipsl.jussieu.fr","http://ftp.oleane.net",
                           "http://mirrors.ircam.fr"],
        "Germany":        ["http://ftp.fau.de","http://ftp.fernunihagen.de","http://ftp.fuberlin.de",
                           "http://ftp.gwdg.de","http://ftp.mpisb.mpg.de",
                           "http://ftp.rrze.unierlangen.de","http://ftp.rrzn.unihannover.de",
                           "http://ftp.tuchemnitz.de","http://mirror.physikpool.tuberlin.de",
                           "http://sunsite.informatik.rwthaachen.de"],
        "Greece":         ["http://ftp.cc.uoc.gr","http://ftp.ntua.gr"],
        "Hong Kong":      ["http://ftp.cuhk.edu.hk"],
        "Ireland":        ["http://ftp.heanet.ie"],
        "International":  ["http://tug.ctan.org","http://ctan.sharelatex.com"],
        "Japan":          ["http://ftp.jaist.ac.jp","http://ftp.kddilabs.jp","http://ftp.uaizu.ac.jp"],
        "Mexico":         ["http://ftp.leg.uct.ac.za"],
        "Netherlands":    ["http://archive.cs.uu.nl","http://ctan.triasinformatica.nl",
                           "http://ftp.snt.utwente.nl"],
        "New Zealand":    ["http://mirror.aut.ac.nz"],
        "Norway":         ["http://ctan.uib.no"],
        "Poland":         ["http://ftp.gust.org.pl","http://ftp.piotrkosoft.net",
                           "http://sunsite.icm.edu.pl"],
        "Portugal":       ["http://ftp.di.uminho.pt","http://ftp.eq.uc.pt",
                           "http://ftp.ist.utl.pt","http://mirrors.fe.up.pt"],
        "Russia":         ["http://ftp.kaspersky.ru","http://ftp.dante.de"],
        "Saudi Arabia":   ["http://ftp.kau.edu.sa"],
        "South Africa":   ["http://ftp.uct.ac.za"],
        "South Korea":    ["http://ftp.korea.ac.kr"],
        "Spain":          ["http://ftp.rediris.es","http://ftp.uspceu.es"],
        "Sweden":         ["http://ftp.sunet.se"],
        "Switzerland":    ["http://ftp.ch/ctan"],
        "Taiwan":         ["http://ftp.csie.ntu.edu.tw"],
        "United Kingdom": ["http://ftp.mirrorservice.org"],
        "USA":            ["http://ftp.gnu.org","http://ftp.ubuntu.com","http://ftp.microsoft.com"],
    },
    "CAMS": {
        "NASA":         [
            "http://tarotchilivisit2.oamp.fr",
            "http://150.214.222.100/view/view.shtml?id=1070&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1",
            "http://sidecam.obspm.fr/view/viewer_index.shtml?id=3826",
            "http://tarot4.obs-azur.fr/view/view.shtml?id=6241&imagePath=/mjpg/video.mjpg&size=1",
        ],
        "China":        [
            "http://59.146.77.13/Cgi?page=Single&Language=1",
            "http://113.161.194.216:86/Cgi?page=Single&Mode=Refresh&Interval=3&Language=0",
            "http://61.60.112.230/view/view.shtml?imagePath=/mjpg/2/video.mjpg&size=1",
            "http://nav.ddo.jp:82/ViewerFrame?Mode=Motion&Language=0",
        ],
        "USA_College":  [
            "http://rifwebcam.chem.psu.edu/",
            "http://128.196.12.29/axis-cgi/mjpg/video.cgi",
            "http://buscam.uchicago.edu/view/index.shtml",
            "http://webcam01.ecn.purdue.edu/view/index.shtml",
            "http://flightcam2.pr.erau.edu/view/view.shtml?id=3801&imagepath=%2Fmjpg%2Fvideo.mjpg&size=1",
        ],
        "USA_Security": [
            "http://115.42.155.199/view/indexFrame.shtml",
            "http://camera6.buffalotrace.com/view/index.shtml",
            "http://202.208.150.120/ViewerFrame?Mode=Motion&Language=1",
            "http://74.94.148.163:8080/ViewerFrame?Mode=Motion",
            "http://205.167.90.185/view/viewer_index.shtml?id=4680",
        ],
        "USA_Other":    [
            "http://129.15.81.9:8080/webcam.html",
            "http://82.139.167.140:3131/view/index.shtml",
            "http://avptcam.uconn.edu/view/index.shtml",
            "http://webcam.thealgonquin.com:8080/view/index.shtml",
        ],
        "Russia":       [
            "http://212.42.54.137:8008/view/index.shtml",
            "http://195.113.207.238/view/index.shtml",
            "http://camera.butovo.com/view/index.shtml",
            "http://195.74.79.83:30/view/index.shtml",
        ],
        "Switzerland":  [
            "http://wc-heli.chuv.ch/view/view.shtml",
            "http://195.196.36.242/view/index.shtml",
            "http://195.196.35.91/view/view.shtml?id=565&imagePath=%2Fmjpg%2Fvideo.mjpg&size=1",
        ],
        "Holland":      [
            "http://loeffingencam.selfhost.eu/view/view.shtml?id=174&imagepath=%2Fmjpg%2F1%2Fvideo.mjpg&size=1",
            "http://80.94.55.92/view/index.shtml",
        ],
        "Germany":      [
            "http://217.22.201.135/view/viewer_index.shtml?id=17222",
            "http://217.30.178.109:46744/view/index.shtml",
            "http://217.78.137.43/view/index.shtml",
            "http://cam.hintertuxerhof.at/view/index.shtml",
            "http://webcam.eins-energie.de/view/index.shtml",
            "http://94.125.79.44/view/index.shtml",
        ],
        "Italy":        [
            "http://83.61.22.4:8080/view/viewer_index.shtml?id=0",
            "http://195.235.198.107:3344/view/index.shtml",
        ],
    },
    "DATABANK": {
        "Netrunner":    [
            "https://nullsignal.games", "https://netrunnerdb.com",
            "https://www.reddit.com/r/Netrunner", "https://jinteki.net",
            "https://stimhack.com", "https://netrunner.fandom.com",
        ],
        "Cyberpunk":    [
            "https://cyberpunkred.com/", "https://cyberpunkred.fandom.com/wiki/Cyberpunk_Red",
            "https://www.reddit.com/r/cyberpunkred/", "https://roll20.net/",
            "https://homebrewery.naturalcrit.com/share/BvkGVODbp6gZ",
        ],
        "Security":     [
            "https://krebsonsecurity.com", "https://news.ycombinator.com",
            "https://nmap.org", "https://shodan.io", "https://kali.org",
            "https://www.schneier.com", "https://www.grc.com/securitynow.htm",
        ],
        "Linux_Open":   [
            "http://gnu.org", "http://kernel.org", "http://debian.org",
            "http://ubuntu.com", "http://archlinux.org", "http://kali.org",
            "http://nmap.org", "http://docker.com",
        ],
        "Tech_Reading": [
            "https://techcrunch.com", "https://www.wired.com", "https://arstechnica.com",
            "https://theverge.com", "https://bleepingcomputer.com",
            "https://theregister.com", "https://news.ycombinator.com",
        ],
        "Daemon_Novel": [
            "https://en.wikipedia.org/wiki/Daemon_(novel)",
            "https://www.goodreads.com/book/show/4699570-daemon",
            "https://www.penguinrandomhouse.com/books/304687/daemon-by-daniel-suarez/",
            "https://www.tor.com/2017/06/07/burning-through-daniel-suarezs-daemon-and-freedom-tm/",
        ],
        "Books":        [
            "https://www.goodreads.com", "https://www.projectgutenberg.org",
            "https://www.openlibrary.org", "https://www.nypl.org",
            "https://www.librarything.com",
        ],
    },
}

# ================================================================
# RegistryApplet  -- tree-navigation browser
#   Level 0  : Main Menu  (shows all registry keys as tiles)
#   Level 1  : Region list for chosen module
#   Level 2  : URL list for chosen region
#   Breadcrumb bar always shows:  Main Menu > MODULE > Region
# ================================================================
import webbrowser as _wb

# Human-readable labels for each registry key
_MODULE_META = {
    "DSPACE":   {"label": "DSPACE",   "desc": "Academic Repository Network",  "accent": "#66FFCC"},
    "FTP":      {"label": "FTP",      "desc": "Global FTP Mirror Network",     "accent": "#66FFCC"},
    "CAMS":     {"label": "EYE",      "desc": "Open Camera Network",           "accent": "#66FFCC"},
    "DATABANK": {"label": "DATABANK", "desc": "Link Library",                  "accent": "#66FFCC"},
}

class RegistryApplet(tk.Frame):
    """
    Three-level tree navigator.
    Instantiated either from the main menu (REGISTRY_KEY=None  -> show root)
    or by a chat command (REGISTRY_KEY set -> jump straight to region level).
    """
    REGISTRY_KEY = None   # None = start at root; set in subclasses to jump in
    ACCENT       = "#66FFCC"
    BG           = "#161616"
    BG_DARK      = "#0e0e0e"
    BG_HOVER     = "#1e2e2e"

    # Navigation state
    _module  = None   # e.g. "DSPACE"
    _region  = None   # e.g. "Turkey"

    def __init__(self, parent, ui=None):
        super().__init__(parent, bg=self.BG)
        self.ui = ui
        self._module = self.REGISTRY_KEY  # None for root, set for subclasses
        self._region = None
        self._build_shell()
        self._navigate()

    # ------------------------------------------------------------------
    # Shell: fixed chrome that never changes (breadcrumb + content area)
    # ------------------------------------------------------------------
    def _build_shell(self):
        # ── top bar: breadcrumb + close
        top = tk.Frame(self, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6, 0))

        self._crumb_var = tk.StringVar(value="Main Menu")
        self._crumb_lbl = tk.Label(
            top, textvariable=self._crumb_var,
            fg=self.ACCENT, bg=self.BG,
            font=("MS PGothic", 9, "bold"), anchor="w"
        )
        self._crumb_lbl.pack(side="left", fill="x", expand=True)

        tk.Button(
            top, text="X", bg="#2a2a2a", fg=self.ACCENT,
            font=("MS PGothic", 8, "bold"), relief="flat", width=3,
            command=self._close
        ).pack(side="right")

        # ── separator line
        tk.Frame(self, bg=self.ACCENT, height=1).pack(fill="x", padx=8, pady=(3, 0))

        # ── content area (swapped out per level)
        self._content = tk.Frame(self, bg=self.BG)
        self._content.pack(fill="both", expand=True, padx=8, pady=6)

        # ── status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self._status_var,
            fg="#666", bg=self.BG,
            font=("MS PGothic", 8), anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 4))

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------
    # Navigation router
    # ------------------------------------------------------------------
    def _navigate(self, module=None, region=None):
        self._module = module if module is not None else self._module
        self._region = region
        self._clear_content()
        self._update_crumb()

        if self._module is None:
            self._show_root()
        elif self._region is None:
            self._show_regions()
        else:
            self._show_urls()

    def _update_crumb(self):
        parts = ["Main Menu"]
        if self._module:
            label = _MODULE_META.get(self._module, {}).get("label", self._module)
            parts.append(label)
        if self._region:
            parts.append(self._region)
        self._crumb_var.set("  >  ".join(parts))

    def _go_back(self):
        if self._region is not None:
            self._navigate(module=self._module, region=None)
        elif self._module is not None:
            self._navigate(module=None, region=None)

    # ------------------------------------------------------------------
    # Level 0 -- Root: module tiles
    # ------------------------------------------------------------------
    def _show_root(self):
        self._status_var.set("Select a module to browse.")
        tk.Label(
            self._content, text="[ DILARA REGISTRY ]",
            fg=self.ACCENT, bg=self.BG,
            font=("MS PGothic", 11, "bold")
        ).pack(pady=(4, 10))

        grid = tk.Frame(self._content, bg=self.BG)
        grid.pack(fill="both", expand=True)

        for i, (key, meta) in enumerate(sorted(_MODULE_META.items())):
            if key not in REGISTRY:
                continue
            col = i % 2
            row = i // 2
            count = sum(len(v) for v in REGISTRY[key].values())
            regions = len(REGISTRY[key])

            tile = tk.Frame(grid, bg="#1a2a2a",
                            highlightbackground=self.ACCENT,
                            highlightthickness=1)
            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            grid.columnconfigure(col, weight=1)

            tk.Label(tile, text=meta["label"],
                     fg=self.ACCENT, bg="#1a2a2a",
                     font=("MS PGothic", 11, "bold")).pack(anchor="w", padx=8, pady=(6,1))
            tk.Label(tile, text=meta["desc"],
                     fg="#aaa", bg="#1a2a2a",
                     font=("MS PGothic", 8)).pack(anchor="w", padx=8)
            tk.Label(tile, text=f"{regions} regions  |  {count} links",
                     fg="#555", bg="#1a2a2a",
                     font=("MS PGothic", 7)).pack(anchor="w", padx=8, pady=(1,6))

            tile.bind("<Button-1>", lambda e, k=key: self._navigate(module=k, region=None))
            for child in tile.winfo_children():
                child.bind("<Button-1>", lambda e, k=key: self._navigate(module=k, region=None))
            tile.bind("<Enter>", lambda e, t=tile: t.config(bg=self.BG_HOVER))
            tile.bind("<Leave>", lambda e, t=tile: t.config(bg="#1a2a2a"))

    # ------------------------------------------------------------------
    # Level 1 -- Regions for a module
    # ------------------------------------------------------------------
    def _show_regions(self):
        data = REGISTRY.get(self._module, {})
        meta = _MODULE_META.get(self._module, {})
        self._status_var.set(f"{len(data)} regions available. Click to expand.")

        # Header row
        nav = tk.Frame(self._content, bg=self.BG)
        nav.pack(fill="x", pady=(0, 6))
        tk.Button(nav, text="< Back", bg="#2a2a2a", fg=self.ACCENT,
                  font=("MS PGothic", 8, "bold"), relief="flat",
                  command=self._go_back).pack(side="left")
        tk.Label(nav, text=meta.get("desc", ""),
                 fg="#888", bg=self.BG,
                 font=("MS PGothic", 8)).pack(side="left", padx=8)

        # Scrollable region list
        canvas = tk.Canvas(self._content, bg=self.BG, highlightthickness=0)
        sb = tk.Scrollbar(self._content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=self.BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for region, urls in data.items():
            row = tk.Frame(inner, bg="#111",
                           highlightbackground="#2a2a2a", highlightthickness=1)
            row.pack(fill="x", pady=2, padx=2)

            tk.Label(row, text=f"  {region}",
                     fg=self.ACCENT, bg="#111",
                     font=("MS PGothic", 9, "bold"),
                     anchor="w", width=18).pack(side="left", padx=(4,0), pady=4)
            tk.Label(row, text=f"{len(urls)} links",
                     fg="#555", bg="#111",
                     font=("MS PGothic", 8)).pack(side="left", padx=6)

            # Arrow
            tk.Label(row, text=">",
                     fg=self.ACCENT, bg="#111",
                     font=("MS PGothic", 10, "bold")).pack(side="right", padx=8)

            row.bind("<Button-1>",
                     lambda e, r=region: self._navigate(module=self._module, region=r))
            for child in row.winfo_children():
                child.bind("<Button-1>",
                           lambda e, r=region: self._navigate(module=self._module, region=r))
            row.bind("<Enter>", lambda e, f=row: f.config(bg=self.BG_HOVER))
            row.bind("<Leave>", lambda e, f=row: f.config(bg="#111"))

    # ------------------------------------------------------------------
    # Level 2 -- URLs for a region
    # ------------------------------------------------------------------
    def _show_urls(self):
        data   = REGISTRY.get(self._module, {})
        urls   = data.get(self._region, [])
        self._status_var.set(f"{len(urls)} links in {self._region}. Double-click to open.")

        # Nav bar
        nav = tk.Frame(self._content, bg=self.BG)
        nav.pack(fill="x", pady=(0, 4))
        tk.Button(nav, text="< Back", bg="#2a2a2a", fg=self.ACCENT,
                  font=("MS PGothic", 8, "bold"), relief="flat",
                  command=self._go_back).pack(side="left")

        # Action buttons
        btn_row = tk.Frame(self._content, bg=self.BG)
        btn_row.pack(fill="x", pady=(0, 4))
        tk.Button(btn_row, text="Open Selected", bg=self.ACCENT, fg="#000",
                  font=("MS PGothic", 8, "bold"),
                  command=self._open_selected).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="Open All", bg="#2a2a2a", fg=self.ACCENT,
                  font=("MS PGothic", 8, "bold"),
                  command=self._open_all).pack(side="left")

        # URL listbox
        self._url_lb = tk.Listbox(
            self._content, bg=self.BG_DARK, fg="#E5FFE5",
            selectbackground="#1a2a2a", activestyle="none",
            font=("MS PGothic", 8),
            relief="flat", borderwidth=0
        )
        sb = tk.Scrollbar(self._content, orient="vertical",
                          command=self._url_lb.yview)
        self._url_lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._url_lb.pack(fill="both", expand=True)

        for u in urls:
            self._url_lb.insert(tk.END, f"  {u}")

        self._url_lb.bind("<Double-Button-1>", self._open_selected)

    def _open_selected(self, event=None):
        if not hasattr(self, "_url_lb"):
            return
        sel = self._url_lb.curselection()
        if not sel:
            return
        url = self._url_lb.get(sel[0]).strip()
        _wb.open(url)
        self._status_var.set(f"Opened: {url[:60]}")

    def _open_all(self):
        if not hasattr(self, "_url_lb"):
            return
        urls = [self._url_lb.get(i).strip() for i in range(self._url_lb.size())]
        for u in urls:
            _wb.open(u)
        self._status_var.set(f"Opened {len(urls)} links")

    def _close(self):
        for w in self.master.winfo_children():
            w.destroy()


# Subclasses jump straight to the region list for their module
class DspaceApplet(RegistryApplet):
    REGISTRY_KEY = "DSPACE"

class FTPApplet(RegistryApplet):
    REGISTRY_KEY = "FTP"

class EyeApplet(RegistryApplet):
    REGISTRY_KEY = "CAMS"

class DataLibApplet(RegistryApplet):
    REGISTRY_KEY = "DATABANK"

class DatabankApplet(tk.Frame):
    """Simple directory viewer for ./databank (changeable via Browse…)."""
    def __init__(self, parent, ui=None):
        super().__init__(parent, bg="#161616")
        self.ui = ui
        self.current_path = Path(DATABANK_PATH).resolve()
        self._build()

    def _build(self):
        top = tk.Frame(self, bg="#161616")
        top.pack(fill="x", padx=8, pady=8)

        tk.Label(top, text="Databank",
                 fg="#66FFCC", bg="#161616",
                 font=("MS PGothic", 12, "bold")).pack(side="left")

        tk.Button(top, text="Browse…", command=self.pick_folder,
                  bg="#66FFCC", fg="#000", width=10,
                  font=("MS PGothic", 9, "bold")).pack(side="right", padx=4)

        self.listbox = tk.Listbox(self, bg="#0e0e0e", fg="#E5FFE5",
                                  selectbackground="#66FFCC", activestyle="none",
                                  font=("MS PGothic", 10, "bold"))
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
        except Exception as e:
            self.listbox.insert(tk.END, f"(error listing path: {e})")

class NavigationApplet(tk.Frame):
    """Navigation stub; later replace with real pathfinding/overlay."""
    def __init__(self, parent, ui=None):
        super().__init__(parent, bg="#161616")
        self.ui = ui
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg="#161616")
        hdr.pack(fill="x", padx=8, pady=8)
        tk.Label(hdr, text="Navigation",
                 fg="#66FFCC", bg="#161616",
                 font=("MS PGothic", 12, "bold")).pack(side="left")

        mid = tk.Frame(self, bg="#161616")
        mid.pack(fill="x", padx=8, pady=4)

        tk.Label(mid, text="Destination:",
                 fg="#E5FFE5", bg="#161616",
                 font=("MS PGothic", 10, "bold")).pack(side="left")

        self.dest_var = tk.StringVar()
        tk.Entry(mid, textvariable=self.dest_var, width=24,
                 bg="#141414", fg="#E5FFE5",
                 insertbackground="#66FFCC",
                 font=("MS PGothic", 10, "bold")).pack(side="left", padx=6)

        btns = tk.Frame(self, bg="#161616")
        btns.pack(fill="x", padx=8, pady=6)
        tk.Button(btns, text="Start", bg="#66FFCC", fg="#000",
                  font=("MS PGothic", 9, "bold"),
                  command=self.start_route).pack(side="left", padx=4)
        tk.Button(btns, text="Stop", bg="#aa4444", fg="#fff",
                  font=("MS PGothic", 9, "bold"),
                  command=self.stop_route).pack(side="left", padx=4)

        self.out = tk.Text(self, height=6, bg="#0e0e0e", fg="#E5FFE5",
                           insertbackground="#66FFCC", state="disabled",
                           font=("MS PGothic", 10, "bold"))
        self.out.pack(fill="both", expand=True, padx=8, pady=(2, 8))

    def start_route(self):
        dest = self.dest_var.get().strip() or "Unknown destination"
        self._append(f"Route to {dest} initialized.")
        for s in ["Head north 50m", "Turn right", "Go 10m", "Destination on your left"]:
            self._append(f"• {s}")

    def stop_route(self):
        self._append("Route cancelled.")

    def _append(self, txt):
        self.out.config(state="normal")
        self.out.insert(tk.END, txt + "\n")
        self.out.see(tk.END)
        self.out.config(state="disabled")

# -------------------------------
# UI (Vision-style)
# -------------------------------
class ChatUI:
    def __init__(self, root, username="User"):
        self.root = root
        self.username = username

        # Window
        self.root.title(APP_TITLE)
        self.root.geometry(DEFAULT_GEOMETRY)
        self.root.configure(bg="#000000")
        try:
            self.root.attributes('-alpha', WINDOW_ALPHA)
        except Exception:
            pass
        self.root.resizable(False, False)

        # Global font preference (fallback-safe)
        try:
            self.root.option_add("*Font", ("MS PGothic", 10, "bold"))
        except Exception:
            pass

        # Theme tokens
        self.ui_colors = {
            "bg_dark": "#0e0e0e",
            "bg_glass": "#1a1a1a",
            "text_primary": "#E5FFE5",
            "accent": "#66FFCC",
            "border": "#2CFFC6"
        }

        # Glass card
        self.card = tk.Frame(
            root,
            bg=self.ui_colors["bg_glass"],
            highlightbackground=self.ui_colors["border"],
            highlightthickness=1
        )
        self.card.pack(fill="both", expand=True, padx=12, pady=12)

        # NodeManager (after card exists)
        self.node_manager = NodeManager(username, ui=self)

        # Voice (TTS)
        self.voice_manager = VoiceManager(VOICES_DIR)

        # Regions
        self.header_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=150)
        self.header_frame.pack(fill="x", pady=(6, 0))
        self.chat_frame = tk.Frame(self.card, bg=self.ui_colors["bg_dark"], height=450)
        self.chat_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.applet_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=180)
        self.applet_frame.pack(fill="x", padx=6, pady=6)
        self.input_frame = tk.Frame(self.card, bg=self.ui_colors["bg_glass"], height=120)
        self.input_frame.pack(fill="x", padx=6, pady=(0, 8))

        # Build sections
        self._setup_header()
        self._setup_chatbox()
        self._setup_input()

        self.last_bot_message = ""

    # Header
    def _setup_header(self):
        greeting = self.node_manager.nodes["dialog"].greet()
        tk.Label(
            self.header_frame,
            text=greeting,
            font=("MS PGothic", 12, "bold"),
            fg=self.ui_colors["accent"],
            bg=self.ui_colors["bg_glass"],
            wraplength=360,
            justify="center"
        ).pack(pady=(6, 6))

        # Profile
        pic_frame = tk.Frame(self.header_frame, width=96, height=96, bg="#222")
        pic_frame.pack(pady=4)
        self._load_profile_picture(pic_frame, "profile.png")

        # Help
        tk.Button(
            self.header_frame, text="?",
            font=("MS PGothic", 10, "bold"),
            bg=self.ui_colors["accent"], fg="#000",
            width=2, command=self.show_about
        ).place(x=360, y=6)

        # Voice selector
        if self.voice_manager and self.voice_manager.available_names:
            ctl = tk.Frame(self.header_frame, bg=self.ui_colors["bg_glass"])
            ctl.pack(pady=(2, 2))
            tk.Label(ctl, text="Voice:", fg=self.ui_colors["text_primary"],
                     bg=self.ui_colors["bg_glass"],
                     font=("MS PGothic", 10, "bold")).pack(side="left")
            self.voice_var = tk.StringVar(
                value=self.voice_manager.active_name or self.voice_manager.available_names[0]
            )
            self.voice_dropdown = ttk.Combobox(
                ctl, textvariable=self.voice_var,
                values=self.voice_manager.available_names,
                width=24, state="readonly"
            )
            self.voice_dropdown.pack(side="left", padx=6)
            self.voice_dropdown.bind("<<ComboboxSelected>>", self.on_voice_select)

    # Chat
    def _setup_chatbox(self):
        self.chat_box = scrolledtext.ScrolledText(
            self.chat_frame,
            width=46, height=25, wrap=tk.WORD,
            bg=self.ui_colors["bg_dark"],
            fg=self.ui_colors["text_primary"],
            insertbackground=self.ui_colors["accent"],
            font=("MS PGothic", 10, "bold"),
            state="disabled"
        )
        self.chat_box.pack(padx=6, pady=6, fill="both", expand=True)

        # tags for alignment
        self.chat_box.tag_config("user", justify="right", foreground="#FFFFFF")
        self.chat_box.tag_config("ai", justify="left", foreground=self.ui_colors["accent"])
        self.chat_box.tag_config("sys", justify="center", foreground="#9ADFD0")

    # Input row
    def _setup_input(self):
        # text entry
        self.input_entry = tk.Entry(
            self.input_frame,
            font=("MS PGothic", 10, "bold"),
            bg="#141414", fg=self.ui_colors["text_primary"],
            insertbackground=self.ui_colors["accent"],
            width=26
        )
        self.input_entry.pack(side="left", padx=(8, 6), pady=8)
        self.input_entry.bind("<Return>", self.send_message)

        # send
        tk.Button(
            self.input_frame, text="Send",
            font=("MS PGothic", 10, "bold"),
            bg=self.ui_colors["accent"], fg="#000",
            width=6, command=self.send_message
        ).pack(side="left", padx=(0, 6))

        # tts
        tk.Button(
            self.input_frame, text="🔊",
            font=("MS PGothic", 12, "bold"),
            width=3, bg=self.ui_colors["accent"], fg="#000",
            command=self.speak_last_message
        ).pack(side="left", padx=(0, 6))

        # mic (Vosk primary, SR fallback)
        tk.Button(
            self.input_frame, text="🎤",
            font=("MS PGothic", 12, "bold"),
            width=3, bg=self.ui_colors["accent"], fg="#000",
            command=self.listen_speech
        ).pack(side="left")

        # tts sliders (rate/volume)
        if self.voice_manager and self.voice_manager.engine:
            sliders = tk.Frame(self.input_frame, bg=self.ui_colors["bg_glass"])
            sliders.pack(side="right", padx=6)
            tk.Label(sliders, text="Rate", bg=self.ui_colors["bg_glass"],
                     fg=self.ui_colors["text_primary"],
                     font=("MS PGothic", 9, "bold")).grid(row=0, column=0, padx=2)
            self.rate_var = tk.IntVar(
                value=self.voice_manager.active_rate or
                self.voice_manager.engine.getProperty('rate') or 200
            )
            tk.Scale(sliders, from_=50, to=300, orient="horizontal", length=120,
                     bg=self.ui_colors["bg_glass"], highlightthickness=0,
                     troughcolor="#222", fg=self.ui_colors["text_primary"],
                     command=self._on_rate_slider, variable=self.rate_var).grid(row=0, column=1)

            tk.Label(sliders, text="Vol", bg=self.ui_colors["bg_glass"],
                     fg=self.ui_colors["text_primary"],
                     font=("MS PGothic", 9, "bold")).grid(row=1, column=0, padx=2)
            self.vol_var = tk.DoubleVar(
                value=self.voice_manager.active_volume if self.voice_manager.active_volume is not None else 1.0
            )
            tk.Scale(sliders, from_=0.0, to=1.0, resolution=0.05,
                     orient="horizontal", length=120,
                     bg=self.ui_colors["bg_glass"], highlightthickness=0,
                     troughcolor="#222", fg=self.ui_colors["text_primary"],
                     command=self._on_volume_slider, variable=self.vol_var).grid(row=1, column=1)

    # Utilities
    def _load_profile_picture(self, frame, image_path):
        try:
            if PIL_OK and Path(image_path).exists():
                img = Image.open(image_path).resize((96, 96))
                ph = ImageTk.PhotoImage(img)
                label = tk.Label(frame, image=ph, bg="#222")
                label.image = ph
                label.pack()
            else:
                tk.Label(frame, text="[No Image]", bg="#222", fg="gray",
                         font=("MS PGothic", 9, "bold")).pack()
        except Exception as e:
            tk.Label(frame, text="[No Image]", bg="#222", fg="gray").pack()
            print("[UI] Profile image load error:", e)

    def append_chat(self, sender, message, tag="ai"):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, f"{sender}: {message}\n", tag)
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")

    def status_to_chat(self, message):
        self.append_chat("System", message, tag="sys")

    def send_message(self, event=None):
        user_text = self.input_entry.get().strip()
        if not user_text:
            return
        self.append_chat(self.username, user_text, tag="user")
        self.input_entry.delete(0, tk.END)

        bot_text = self.node_manager.process_input(user_text)
        self.append_chat("D.I.L.A.R.A.", bot_text, tag="ai")
        self.last_bot_message = bot_text

    def speak_last_message(self):
        if not self.last_bot_message:
            messagebox.showinfo("TTS", "No message to speak yet.")
            return
        if self.voice_manager:
            self.voice_manager.speak_async(self.last_bot_message)

    def on_voice_select(self, evt=None):
        choice = getattr(self, "voice_var", None).get() if hasattr(self, "voice_var") else None
        if choice and self.voice_manager:
            self.voice_manager.set_voice(choice)

    def _on_rate_slider(self, val):
        try:
            self.voice_manager.set_rate(int(float(val)))
        except Exception:
            pass

    def _on_volume_slider(self, val):
        try:
            self.voice_manager.set_volume(float(val))
        except Exception:
            pass

    def mount_applet(self, applet_class):
        for w in self.applet_frame.winfo_children():
            w.destroy()
        app = applet_class(self.applet_frame, ui=self)
        app.pack(fill="both", expand=True)

    def show_about(self):
        text = (
            f"{APP_TITLE}\n"
            "Vision-style UI • Dialog→Intent routing • TTS voice sets • Vosk speech\n\n"
            "Shortcuts:\n"
            " - Type and press Enter, or click Send\n"
            " - reads last response  •  speaks via Vosk (SR fallback)\n"
            " - 'databank' / 'navigation' mount applets\n\n"
            "© Tekno Tasarım Systems"
        )
        messagebox.showinfo("About / Help", text)

    def safe_exit(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    # --- Speech input (Vosk → SR fallback) ---
    def listen_speech(self):
        """Kick off speech recognition on a background thread so UI stays live."""
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        # VOSK primary (offline)
        if VOSK_OK and Path(VOSK_MODEL_DIR).exists():
            try:
                self.root.after(0, lambda: self.status_to_chat("[VOSK] Listening…"))
                model = vosk.Model(VOSK_MODEL_DIR)
                rec = vosk.KaldiRecognizer(model, 16000)
                duration = 6
                data = sd.rec(int(duration * 16000), samplerate=16000,
                              channels=1, dtype='int16')
                sd.wait()
                rec.AcceptWaveform(data.tobytes())
                result = json.loads(rec.FinalResult())
                text = (result.get("text") or "").strip()
                if not text:
                    self.root.after(0, lambda: self.status_to_chat("[VOSK] No speech detected."))
                    return
                self.root.after(0, lambda: self.status_to_chat(f"[VOSK → Text] {text}"))
                self.root.after(0, lambda: (
                    self.input_entry.delete(0, tk.END),
                    self.input_entry.insert(0, text),
                    self.send_message()
                ))
                return
            except Exception as e:
                self.root.after(0, lambda: self.status_to_chat(f"[VOSK] Error: {e}"))

        # SpeechRecognition fallback (online)
        if SR_OK:
            try:
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    self.root.after(0, lambda: self.status_to_chat("[SR] Listening (fallback)…"))
                    r.adjust_for_ambient_noise(source)
                    audio = r.listen(source, timeout=5, phrase_time_limit=8)
                text = r.recognize_google(audio)
                self.root.after(0, lambda: self.status_to_chat(f"[SR → Text] {text}"))
                self.root.after(0, lambda: (
                    self.input_entry.delete(0, tk.END),
                    self.input_entry.insert(0, text),
                    self.send_message()
                ))
            except sr.WaitTimeoutError:
                self.root.after(0, lambda: self.status_to_chat("[SR] Listening timed out."))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self.status_to_chat("[SR] Could not understand audio."))
            except sr.RequestError as e:
                self.root.after(0, lambda: self.status_to_chat(f"[SR] API error: {e}"))
            except Exception as e:
                self.root.after(0, lambda: self.status_to_chat(f"[SR] Error: {e}"))
        else:
            self.root.after(0, lambda: messagebox.showerror(
                "Speech Input", "Neither Vosk (model missing) nor SpeechRecognition are available."))
# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    # Ensure optional folders exist
    Path(DATABANK_PATH).mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    app = ChatUI(root, username="Fatih")
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()
