# KOD8_ENC

KOD 8 is a multi-layered obfuscation and encryption engine designed for high-diffusion data protection. Unlike standard single-algorithm ciphers, KOD 8 utilizes a Strategic Chain Architecture, applying exactly eight distinct, reversible transformations based on the detected or specified input type.

More Features

    Strategic Auto-Detection: The engine analyzes input headers and entropy to automatically select the most effective cipher list (Text, Image, Video, Document, Numeric, or Experimental).
    
Uses a base function, works simply as:  

     F(x) = 1(3(9(7(4(2(6(8*x)))))))  
    
    8-Round Chain Logic: Every piece of data passes through exactly 8 operations. Decryption is achieved by running the identical chain in perfect reverse.

    Turkish Alphabet Support: Specialized Vigenere and Atbash operations that respect the unique character set of the Turkish language (ABCÇDEFGĞHİIJKLMNOÖPRSŞTUÜVYZ).

    Zero-Dependency UI: A professional, high-contrast Tkinter interface built entirely on the Python Standard Library.

    Deterministic Security: Features a Fisher-Yates shuffled S-Box and a Linear Congruential Generator (LCG) keystream, both seeded by a customizable master key.

Architecture

The system is divided into two primary modules:

    kod8_engine.py: The cryptographic core containing the primitive operations (S-Box, XOR cascades, Columnar transpositions, etc.) and the 6 defined CipherLists.

    kod8_ui.py: The frontend controller providing real-time verification of each encryption layer.

The 6 Cipher Strategies

ID	Name	Targeted Data	Primary Focus
CL1	Plain Text	Human-readable prose	Turkish-aware substitution & linguistic diffusion.
CL2	Image Files	PNG, JPG, WebP	Binary-safe S-Box layers & block shuffling.
CL3	Video Files	MP4, MKV, AVI	Stream-XOR heavy to break long repeating patterns.
CL4	Documents	PDF, DOCX, TXT	Structure-breaking columnar transpositions.
CL5	Numeric/Data	JSON, CSV, Coords	Base-36 transformation to eliminate decimal patterns.
CL6	Experimental	Mixed/Unknown	Maximum obfuscation using all primitive families.

Getting Started
Prerequisites

    Python 3.8 or higher.

    No external libraries (like pip install) are required.

Installation

    Save kod8_engine.py and kod8_ui.py in the same directory.

    (Optional) Open kod8_engine.py and modify the KOD8_KEY variable to your own custom 8-digit numeric string.

Usage

Run the UI via your terminal: 
python kod8_ui.py


Tutorial

    Upload: Click "UPLOAD / BROWSE" to load a file, or type directly into the text area.

    Encrypt: Press "ENCRYPT". The UI will visually "check off" each of the 8 layers as they are applied.

    Save: After encryption, you can save the result as a .kod8 file. This file contains a header identifying which cipher_id was used.

    Decrypt: Load a .kod8 file. If the header is missing, the UI will prompt you to select the original strategy used.

Primitive Operations

KOD 8 uses a variety of mathematical and positional primitives:

    Substitution: S-Box (bijective byte mapping), Vigenere (polyalphabetic), Atbash (mirror), and Base-36 digit shifting.

    Transposition: Rail-Fence (zigzag), Columnar (grid-based), Block Shuffle (key-derived chunk reordering), and circular Block Rotation.

    Diffusion: Rolling XOR (CBC-style byte chaining) and Block XOR Cascade (CBC-style block chaining).

    Encoding: Hex and Base64 normalization.

Chain Safety Rules (R1–R6)

To ensure 100% reversibility without data corruption, the engine enforces strict safety rules:

    R4 (Unicode Constraint): unicode_shift never precedes Turkish-alphabet operations to prevent "breaking" the character mapping.

    R6 (Normalization): All text input is normalized to uppercase before the first step to ensure substitution consistency.

    Binary Integrity: Image and Video lists (CL2, CL3) utilize Base64 as the primary entry point to ensure binary payloads remain printable throughout the chain.

License

This project is provided for educational and obfuscation purposes.
