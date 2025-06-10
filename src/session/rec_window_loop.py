from multiprocessing import synchronize
import tkinter as tk
from tkinter import ttk
import time

from webcam_hand_triangulation.capture.finalizable_queue import (
    FinalizableQueue,
)

from .position_loader import load_position, save_position


def rec_window_loop(
    stop_event: synchronize.Event,
    command_channel: FinalizableQueue,
):
    last_command = None
    start_time = None
    last_record_time = 0

    root = tk.Tk()
    root.title("Recording")
    root.geometry("250x120")

    rec_label = tk.Label(root, text="REC", font=("Arial", 12), fg="gray")
    rec_label.pack(anchor="nw", pady=[15, 0], padx=[20, 0])

    timer_label = tk.Label(root, text="00:00:00", font=("Arial", 10))
    timer_label.pack(anchor="nw", padx=[20, 0])

    button_frame = tk.Frame(root)
    button_frame.pack(anchor="sw", pady=[10, 0], padx=[13, 0])

    def redraw_buttons():
        if hasattr(last_command, "value"):
            if last_command.value == -1:
                rec_label.config(fg="red")
            elif last_command.value == -2:
                rec_label.config(fg="gray")
            update_buttons([("Done", on_done), ("Cancel", on_cancel)])
        else:
            rec_label.config(fg="gray")
            update_buttons([("Start", on_start)])

    def redraw_timer():
        if start_time is not None:
            elapsed = time.time() - start_time
        else:
            elapsed = last_record_time
        minutes, seconds = divmod(int(elapsed), 60)
        milliseconds = int((elapsed - int(elapsed)) * 1000)
        timer_label.config(
            text=f"{minutes:02}:{seconds:02}:{milliseconds:03}",
            fg="black" if start_time is not None else "gray",
        )

    def updtodate_channel():
        nonlocal last_command
        if command_channel.qsize() == 0 and command_channel.is_finalized():
            save_position(POSITION_CONFIG, root.winfo_x(), root.winfo_y())
            root.destroy()
            return

        command_updated = False
        while command_channel.qsize() != 0:
            last_command = command_channel.get()
            command_updated = True

        if command_updated:
            redraw_buttons()
            if hasattr(last_command, "value"):
                if last_command.value == -1:
                    start_timer()
                else:
                    stop_timer()
            else:
                stop_timer()
        redraw_timer()

        root.after(16, updtodate_channel)

    def update_buttons(buttons):
        for widget in button_frame.winfo_children():
            widget.destroy()

        state = "disabled" if last_command is None else "normal"
        for text, command in buttons:
            btn = ttk.Button(button_frame, text=text, command=command)
            btn.config(state=state)
            btn.pack(side=tk.LEFT, padx=5)

    def complete_command():
        nonlocal last_command
        last_command = None
        redraw_buttons()
        redraw_timer()

    def start_timer():
        nonlocal start_time
        start_time = time.time()

    def stop_timer():
        nonlocal start_time, last_record_time
        if start_time is not None:
            last_record_time = time.time() - start_time
            start_time = None

    def on_start():
        if hasattr(last_command, "set"):
            last_command.set()
        complete_command()

    def on_done():
        if hasattr(last_command, "value"):
            last_command.value = 1
        stop_timer()
        complete_command()

    def on_cancel():
        if hasattr(last_command, "value"):
            last_command.value = 0
        stop_timer()
        complete_command()

    POSITION_CONFIG = "rec_window_pos"
    x, y = load_position(POSITION_CONFIG)
    root.geometry(f"+{x}+{y}")

    updtodate_channel()
    root.protocol("WM_DELETE_WINDOW", lambda: stop_event.set())
    root.mainloop()
