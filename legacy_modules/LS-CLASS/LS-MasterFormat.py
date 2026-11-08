import customtkinter as ctk
import subprocess
import psutil
import platform
import os
import datetime
from tkinter import messagebox

# -------- Helper Functions --------

def get_removable_drives():
    drives = []
    partitions = psutil.disk_partitions(all=False)
    for p in partitions:
        if "removable" in p.opts.lower() and not p.device.startswith(('C:', 'X:')):
            drives.append(p.device)
    return drives

def format_drive_windows(drive_letter, fs_type):
    try:
        subprocess.run(
            f'format {drive_letter}: /FS:{fs_type} /Q /Y',
            shell=True, check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def encrypt_drive_windows(drive_letter):
    try:
        result = subprocess.run(
            ['manage-bde', '-on', f'{drive_letter}:', '-RecoveryPassword', '-ForceEncryptionType', 'Full'],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        return False

def encrypt_drive_luks(drive_letter):
    try:
        subprocess.run([
            'sudo', 'cryptsetup', 'luksFormat', drive_letter,
            '--batch-mode', '--type', 'luks2'
        ], check=True)
        subprocess.run(['sudo', 'cryptsetup', 'open', drive_letter, 'encrypted_drive'], check=True)
        subprocess.run(['sudo', 'mkfs.ext4', '/dev/mapper/encrypted_drive'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(e)
        return False

def encrypt_drive_filevault(drive_letter):
    try:
        subprocess.run(['sudo', 'fdesetup', 'enable'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(e)
        return False

def encrypt_drive(drive_letter, method):
    system = platform.system()
    if method == "None":
        return True
    elif method == "BitLocker" and system == "Windows":
        return encrypt_drive_windows(drive_letter)
    elif method == "LUKS" and system == "Linux":
        return encrypt_drive_luks(drive_letter)
    elif method == "FileVault" and system == "Darwin":
        return encrypt_drive_filevault(drive_letter)
    else:
        print(f"Unsupported encryption method or OS: {method} on {system}")
        return False

# -------- GUI Logic --------

global status_label

def update_drive_dropdown():
    drives = get_removable_drives()
    drive_names = ["All Drives"] + drives
    cmb_drive.configure(values=drive_names)
    if drive_names:
        cmb_drive.set(drive_names[0])

def process_selected_drives():
    status_label.configure(text="Status: Running...", text_color="yellow")
    confirm = messagebox.askyesno("Confirm Operation", "This will format and encrypt the selected drive(s). Are you sure?")
    if not confirm:
        return

    selected_drive = cmb_drive.get()
    os_type = os_var.get()
    fs_type = fs_var.get()
    encryption = enc_var.get()

    if not selected_drive or not os_type or not fs_type or encryption is None:
        messagebox.showerror("Missing Selection", "Please make all selections before proceeding.")
        return

    drives = get_removable_drives() if selected_drive == "All Drives" else [selected_drive]

    txt_output.delete("1.0", "end")

    for dev in drives:
        txt_output.insert("end", f"Processing {dev}...\n")
        txt_output.insert("end", f"Formatting {dev} as {fs_type}...\n")
        success = False

        if os_type == "Windows":
            success = format_drive_windows(dev.replace("\\", "").replace(":", ""), fs_type)
        else:
            txt_output.insert("end", f"Unsupported OS: {os_type}\n")
            continue

        if not success:
            txt_output.insert("end", f"Failed to format {dev}.\n")
            continue

        txt_output.insert("end", f"Encrypting {dev} with {encryption}...\n")
        encrypt_success = encrypt_drive(dev, encryption)
        if encrypt_success:
            with open("encryption_log.txt", "a") as log:
                log.write(f"{datetime.datetime.now()} - {dev} encrypted with {encryption}\n")

        if encrypt_success:
            txt_output.insert("end", f"{dev} processed successfully.\n\n")
        else:
            txt_output.insert("end", f"Encryption failed for {dev}.\n\n")

    txt_output.insert("end", "All selected drives processed.")
    status_label.configure(text="Status: Done", text_color="green")

def open_feedback():
    messagebox.showinfo("Feedback", "Send your feedback to: afatihu@icloud.com")

# -------- GUI Setup --------

def setup_gui():
    global cmb_drive, os_var, fs_var, enc_var, txt_output, status_label

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.title("LS-MasterFormat Tool - Format & Encrypt USB Drives")
    root.geometry("800x650")

    side_frame = ctk.CTkFrame(root, width=200)
    side_frame.pack(side="left", fill="y", padx=10, pady=10)

    ctk.CTkLabel(side_frame, text="Drive Selection").pack(pady=(10, 5))
    cmb_drive = ctk.CTkComboBox(side_frame, width=180)
    cmb_drive.pack()
    update_drive_dropdown()

    ctk.CTkButton(side_frame, text="Rescan Drives", command=update_drive_dropdown).pack(pady=(10, 20))

    os_var = ctk.StringVar()
    fs_var = ctk.StringVar()
    enc_var = ctk.StringVar()

    ctk.CTkLabel(side_frame, text="Operating System").pack(pady=5)
    for os_name in ["Windows", "Linux", "macOS"]:
        ctk.CTkRadioButton(side_frame, text=os_name, variable=os_var, value=os_name).pack(anchor="w")

    ctk.CTkLabel(side_frame, text="File System").pack(pady=5)
    for fs in ["NTFS", "exFAT", "FAT32", "ext4"]:
        ctk.CTkRadioButton(side_frame, text=fs, variable=fs_var, value=fs).pack(anchor="w")

    ctk.CTkLabel(side_frame, text="Encryption").pack(pady=5)
    for enc in ["None", "BitLocker", "LUKS", "FileVault"]:
        ctk.CTkRadioButton(side_frame, text=enc, variable=enc_var, value=enc).pack(anchor="w")

    main_frame = ctk.CTkFrame(root)
    main_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    txt_output = ctk.CTkTextbox(main_frame, wrap="word")
    txt_output.pack(fill="both", expand=True, pady=10)

    status_label = ctk.CTkLabel(main_frame, text="Status: Idle", text_color="gray")
    status_label.pack(pady=(0, 5))

    ctk.CTkButton(main_frame, text="Format + Encrypt", command=process_selected_drives).pack(pady=10)
    ctk.CTkButton(main_frame, text="📧", width=40, height=28, command=open_feedback).place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

    root.mainloop()

# -------- Run GUI --------

if __name__ == "__main__":
    setup_gui()
