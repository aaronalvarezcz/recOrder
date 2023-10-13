import shutil
import sys
from pathlib import Path
from time import sleep
from typing import Callable
from pycromanager import Core

import numpy as np
from iohub import open_ome_zarr
from qtpy.QtCore import QFileSystemWatcher, QObject, QThread, Signal, Slot
from qtpy.QtWidgets import (
    QApplication,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

DATASET_PATH = "img.zarr"
MAX_ITERATIONS = 5
INTERVAL_SECONDS = 5

NUM_Z_STEPS = 10
Z_INTERVAL_UM = 2
Z_STEP_INTERVAL_SECONDS = 1


class VBoxBase(QWidget):
    def __init__(
        self, button_text: str, button_callback: Callable, label_text: str
    ):
        super().__init__()
        layout = QVBoxLayout()
        button = QPushButton(button_text)
        button.clicked.connect(button_callback)
        layout.addWidget(button)
        self.le = QLineEdit()
        self.le.setReadOnly(True)
        self.le.setText("")
        row = QFormLayout()
        row.addRow(QLabel(label_text), self.le)
        layout.addLayout(row)
        self.setLayout(layout)


class WriterWorker(QObject):
    finished = Signal()
    written = Signal(str)

    def __init__(self) -> None:
        super().__init__()

    @Slot()
    def run(self):
        mmc = Core(convert_camel_case=False)
        with open_ome_zarr(
            DATASET_PATH, mode="w", layout="hcs", channel_names=["BF"]
        ) as dataset:
            position = dataset.create_position("0", "0", "0")
            for i in range(MAX_ITERATIONS):
                stack = []
                for z_step in range(NUM_Z_STEPS):
                    mmc.setPosition(Z_INTERVAL_UM * z_step)
                    print(f"Z position = {mmc.getPosition()}")
                    sleep(Z_STEP_INTERVAL_SECONDS)
                    # WRITE T = t_step, Z = z_step HERE
                    mmc.snapImage()
                    im = mmc.getImage().reshape(
                        (mmc.getImageHeight(), mmc.getImageWidth())
                    )
                    stack.append(im)
                data = np.array(stack)[None, :]
                value = data.mean()
                if "0" not in position:
                    img = position.create_zeros(
                        "0",
                        (MAX_ITERATIONS, *data.shape),
                        dtype=data.dtype,
                    )
                img[i] = data
                print(f"Wrote: {value}")
                self.written.emit(f"{value:.1f}")
                if i < MAX_ITERATIONS - 1:
                    sleep(INTERVAL_SECONDS)
            self.written.emit(f"Wrote last value: {value:.1f}")
            self.finished.emit()


class ZarrWriter(VBoxBase):
    def __init__(self):
        super().__init__("Start writing", self._write, "Written:")

    @Slot()
    def _write(self):
        self.worker = WriterWorker()
        self.thread = QThread()
        self.worker.written.connect(self.le.setText)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()


class ZarrWatcher(VBoxBase):
    def __init__(self):
        super().__init__("Start watching", self._watch, "Watched:")
        self.num_values = 0

    @Slot()
    def _watch(self):
        img_path = Path(DATASET_PATH) / "0" / "0" / "0" / "0"
        while not img_path.exists():
            sleep(INTERVAL_SECONDS)
        img_path = str(Path(img_path).absolute())
        print(f"Watching {img_path}")
        self.watcher = QFileSystemWatcher([img_path])
        self.watcher.directoryChanged.connect(self._data_changed)

    @Slot()
    def _data_changed(self):
        sleep(0.5)
        with open_ome_zarr(DATASET_PATH) as dataset:
            image = dataset["0/0/0/0"]
            if image.shape[0] <= self.num_values:
                return
            value = image.numpy()[self.num_values].mean()
            self.num_values += 1
            print(f"Read: {value}")
            self.le.setText(f"{value:.1f}")
        if value == MAX_ITERATIONS - 1:
            self.le.setText(f"Read last value: {value:.1f}")


class PairedWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "Watch an OME-Zarr store along the time dimension.\n"
                "1. Press'Start writing';\n"
                "2. Press 'Start watching'."
            )
        )
        layout.addWidget(ZarrWriter())
        layout.addWidget(ZarrWatcher())
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = PairedWidget()
    widget.show()
    code = app.exec()
    shutil.rmtree(DATASET_PATH)
    sys.exit()
