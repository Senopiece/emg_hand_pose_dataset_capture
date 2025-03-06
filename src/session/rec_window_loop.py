from multiprocessing import synchronize
import tkinter as tk
from tkinter import ttk

from webcam_hand_triangulation.capture.finalizable_queue import (
    FinalizableQueue,
)

from .position_loader import load_position, save_position

def rec_window_loop(
    stop_event: synchronize.Event,
    command_channel: FinalizableQueue,
):
    last_command = None

    root = tk.Tk()
    root.title("Recording")
    root.geometry("250x90")
    
    rec_label = tk.Label(root, text="REC", font=("Arial", 12), fg="gray")
    rec_label.pack(anchor="nw", pady=[15, 0], padx=[20, 0])
    
    button_frame = tk.Frame(root)
    button_frame.pack(anchor="sw", pady=[10, 0], padx=[13, 0])

    def update_ui():
        if hasattr(last_command, "value"):
            rec_label.config(fg="red")
            update_buttons([("Done", on_done), ("Cancel", on_cancel)])
        else:
            rec_label.config(fg="gray")
            update_buttons([("Start", on_start)])
    
    def updtodate_channel():
        nonlocal last_command
        if command_channel.qsize() == 0 and command_channel.is_finalized():
            save_position(POSITION_CONFIG, root.winfo_x(), root.winfo_y())
            root.destroy()
            return
        
        updated = False
        while command_channel.qsize() != 0:
            last_command = command_channel.get()
            updated = True
        
        if updated:
            update_ui()

        root.after(200, updtodate_channel)
    
    def update_buttons(buttons):
        for widget in button_frame.winfo_children():
            widget.destroy()
        
        state = "disabled" if last_command is None else "normal"
        for text, command in buttons:
            btn = ttk.Button(button_frame, text=text, command=lambda cmd=command: complete_command(cmd))
            btn.config(state=state)
            btn.pack(side=tk.LEFT, padx=5)
    
    def complete_command(action):
        nonlocal last_command
        action()
        last_command = None
        update_ui()
    
    def on_start():
        if hasattr(last_command, "set"):
            last_command.set()
    
    def on_done():
        if hasattr(last_command, "value"):
            last_command.value = 1
    
    def on_cancel():
        if hasattr(last_command, "value"):
            last_command.value = 0
    
    POSITION_CONFIG = "rec_window_pos"
    x, y = load_position(POSITION_CONFIG)
    root.geometry(f"+{x}+{y}")
    
    updtodate_channel()
    root.protocol("WM_DELETE_WINDOW", lambda: stop_event.set())
    root.mainloop()
