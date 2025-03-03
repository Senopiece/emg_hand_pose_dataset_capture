from collections import deque
import multiprocessing
import multiprocessing.synchronize
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

from .requestable_toggle import RequestableToggle
from webcam_hand_triangulation.capture.finalizable_queue import (
    EmptyFinalized,
    FinalizableQueue,
)


def signal_window_loop(
    title: str,
    channels_num: int,
    ymin: float,
    ymax: float,
    stop_event: multiprocessing.synchronize.Event,
    signal_queue: FinalizableQueue,
    record_toggle: RequestableToggle,
):
    # Create a deque for each channel to store the last N records
    dmaxlen = 10000  # Define the maximum length of the deque
    data = [deque([0] * dmaxlen, maxlen=dmaxlen) for _ in range(channels_num)]

    # Set up the plot
    fig, ax = plt.subplots()
    colors = plt.cm.tab10.colors  # Use a colormap for consistent colors # type: ignore
    lines = [
        ax.plot(data[i], label=f"Channel {i}", color=colors[i % len(colors)])[0]
        for i in range(channels_num)
    ]
    ax.set_ylim(ymin, ymax)
    ax.set_title(f"Real-Time {title} Signal")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Value")

    def on_close(_):
        stop_event.set()

    # Connect the close event handler
    fig.canvas.mpl_connect("close_event", on_close)

    # Add the REC button
    ax_rec = plt.axes((0.85, 0.05, 0.1, 0.05))
    rec_button = Button(ax_rec, "REC")

    def update_rec_button():
        if record_toggle.toggle_requested():
            ax_rec.set_facecolor("red" if record_toggle.is_toggled() else "green")
        else:
            ax_rec.set_facecolor("gray")

    def on_rec_clicked(_):
        record_toggle.toggle()
        update_rec_button()

    rec_button.on_clicked(on_rec_clicked)

    # Create buttons for each channel and place them in the top-right corner
    buttons = []
    button_width = 0.1  # Width of each button
    button_height = 0.04  # Height of each button
    button_spacing = 0.05  # Vertical spacing between buttons
    initial_x = 0.85  # X position (right side)
    initial_y = 0.9  # Y position (top)

    # Function to toggle visibility of a channel and update button color
    def toggle_channel(index):
        lines[index].set_visible(not lines[index].get_visible())
        if lines[index].get_visible():
            buttons[index].color = colors[index]
        else:
            buttons[index].color = "gray"
        buttons[index].ax.set_facecolor(buttons[index].color)
        plt.draw()

    for i in range(channels_num):
        ax_button = plt.axes(
            (initial_x, initial_y - i * button_spacing, button_width, button_height)
        )
        button = Button(ax_button, f"Ch {i}", color=colors[i % len(colors)])
        button.on_clicked(lambda event, i=i: toggle_channel(i))
        buttons.append(button)

    while True:
        try:
            signal_chunk = signal_queue.get()
        except EmptyFinalized:
            break

        # Populate queue with the chunk data
        for sample in signal_chunk:
            for i in range(channels_num):
                data[i].append(sample[i])

        # Update each channel's plot line
        for i, line in enumerate(lines):
            line.set_ydata(data[i])

        update_rec_button()

        # Redraw the plot
        fig.canvas.draw_idle()
        plt.pause(0.03)  # Allow matplotlib to process GUI events

        signal_queue.task_done()

    print("Plot window closed.")
