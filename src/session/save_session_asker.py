from webcam_hand_triangulation.capture.finalizable_queue import (
    EmptyFinalized,
    FinalizableQueue,
)
import tkinter as tk
from tkinter import messagebox


def ask_user_to_save():
    """Displays a pop-up window asking the user whether to save the record."""
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    result = messagebox.askyesno("Save Recording", "Do you want to save the recording?")
    root.destroy()
    return result


def confirmation_loop(
    save_record_question_channel: FinalizableQueue,
):
    while True:
        try:
            promise = save_record_question_channel.get()
        except EmptyFinalized:
            break

        # Display a popup asking the user whether to save the record
        save_record = ask_user_to_save()
        promise.set(save_record)
