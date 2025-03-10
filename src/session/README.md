## Top-level functional diagram

```mermaid
flowchart TD
    subgraph CameraReaders
        cap1[cap_reading]
        cap2[cap_reading]
        capN[cap_reading]
    end

    emg_coupling[coupling + emg]

    cap1 --> emg_coupling
    cap2 --> emg_coupling
    capN --> emg_coupling

    emg_coupling --> ProcessingPool

    subgraph ProcessingPool
        processing1[processing]
        processing2[processing]
        processingM[processing]
    end

    ProcessingPool --> results_sorter[ordering]

    results_sorter --> recorder[recorder + decoupler]

    recorder --> hand_3d_visualizer[hand_3d_visualization]
    recorder --> signal_visualizer[signal_window]

    recorder <--> rec_window[rec_window]

    ProcessingPool --> display_ordering1[ordering]
    ProcessingPool --> display_ordering2[ordering]
    ProcessingPool --> display_orderingN[ordering]

    display_ordering1 --> display1[display]
    display_ordering2 --> display2[display]
    display_orderingN --> displayN[display]

    subgraph Displays
        display1
        display2
        displayN
    end
```

> `coupling + emg` produces packets of frames that capture at the same time and the emg recorded from the last capture

> `recorder + decoupler` is doing two things:
> - splitting the processing result onto emg signal and 3d hand
> - optionally record it to a file before the split - the option to set to do so is controlled with a channel that connects to `rec_window`

> NOTE: considering that processing delay is big and displaying delay is negligible we can say that the record will be written with the data you see on the display (e.g. with some delay from the realtime actions) - e.g. the first frame to be written in the moment you press on the `rec` button is the latest processed frame - e.g. most nearly the frame you see on the display