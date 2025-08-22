import tkinter as tk
from tkinter import messagebox
import subprocess
import os

def drop(event):
    filepath = event.data
    if filepath.endswith(('.mp4', '.mkv', '.avi')):
        output_path = os.path.splitext(filepath)[0] + '.gif'
        command = f'ffmpeg -i "{filepath}" -vf "fps=10,scale=320:-1:flags=lanczos" "{output_path}"'
        subprocess.run(command, shell=True)
        messagebox.showinfo("Success", f"File converted and saved as {output_path}")
    else:
        messagebox.showerror("Error", "File type not supported. Please drop a .mp4, .mkv, or .avi file.")

root = tk.Tk()
root.title("Video to GIF converter")

label = tk.Label(root, text="Drag and drop a video file here")
label.pack(padx=10, pady=10)

root.drop_target_register(tk.DND_FILES)
root.dnd_bind('<<Drop>>', drop)

root.mainloop()
