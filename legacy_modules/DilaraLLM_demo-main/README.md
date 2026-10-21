# DilaraLLM_demo
D.I.L.A.R.A. v2.0

Dynamic Intelligence for Logistics, Automation, Reasoning and Adaptation

D.I.L.A.R.A. is a high-performance netrunner engine and engineering companion designed to bridge the gap between hardcoded utility and flexible LLM reasoning. Originally developed as a personality-driven interface for system logistics, v2.0 introduces the Ollama Sandbox integration, enabling offline local reasoning with a proprietary self-evaluation framework known as the AwardEngine.
⬡ Core Architecture: The Dual-Path Router

V2.0 utilizes a hybrid routing logic to manage system resources efficiently:

    NodeManager Handlers (Known Intents): Direct keyword matching (via DialogBase) triggers optimized local services like weather, news, search, and system applets.

    Ollama Reasoning (Open-Ended): If no keyword intent is matched, the query is routed to a local Llama 3.2:1b model for deep inference. This response is then passed through the AwardEngine for metric-based validation.

⬡ Key Features
1. The AwardEngine & Theory Formation

Every local LLM response is evaluated across five weighted metrics:

    Novelty: Rewards the introduction of new technical topics.

    Parsimony: Penalizes excessive verbosity to keep communication "dry and sardonic".

    Reasoning Depth: Scans for logical markers (e.g., "therefore," "implies," "proof").

    Grounding: Rewards references to specific hardware and project telemetry (LiDAR, AL-6061-T6, UNECE R100).

    Action: Detects formal reasoning steps like [COMPOSE], [SPECIALIZE], and [PROVE].

High-scoring responses are promoted to the Theory Base as either THEOREM (score ≥ 15) or CONJECTURE (score ≥ 5).
2. Integrated Services & Registry

    Multi-Engine Search: Fallback logic across Google, Bing, DuckDuckGo, and Brave.

    Registry Applets: Specialized browsers for DSPACE academic repositories, global FTP mirrors, and open camera networks ("THE EYE").

    Atmospheric Data: Real-time weather forecasting for the Bursa region.

    Cyberstorm Mode: A high-intensity command that opens all registered security and NASA camera feeds simultaneously.

3. Audio & Interaction Layer

    Hybrid Speech Input: Support for offline recognition via Vosk and online fallback via SpeechRecognition.

    Custom TTS: Integrated pyttsx3 voice management with adjustable rate and volume sliders in the UI.

⬡ Technical Specifications
Requirements

    OS: Windows/Linux (Optimized for NVIDIA GPU offloading).

    Hardware Context: Raspberry Pi 5, LiDAR, AL-6061-T6 Chassis.

    Backend: Ollama running llama3.2:1b.

    Python Dependencies:
    Bash

    pip install requests pyttsx3 Pillow
    pip install vosk sounddevice speech_recognition

Configuration

    Default Model: llama3.2:1b

    Context Window: 2048 tokens

    Location: Bursa, Turkey (Tekno Tasarım Systems)

⬡ Personality Protocol

D.I.L.A.R.A. is programmed with a Dry, Sardonic Wit.

    Engineering Focus: She prioritizes technical problems over social pleasantries.

    Minimalist: Sentences must earn their place; gratuitous filler is penalized by the AwardEngine.

    In-Character Reasoning: She labels confident conclusions as THEOREM: and hypotheses as CONJECTURE:.

⬡ Project Manager: Fatih Ulusoy
This core is currently tuned for the development of an Autonomous Carrier with the following constraints:

    Payload: 100kg

    Chassis: 50×30cm AL-6061-T6

    Encryption: Kod 8 Pro custom cipher research

    Target: UNECE ADS 2026 Compliance
