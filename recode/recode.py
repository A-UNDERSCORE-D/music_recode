from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, TypedDict, override

from rich import print
from rich.progress import (
    Progress,
    TaskID,
)

if TYPE_CHECKING:

    class FFProbeFormat(TypedDict):
        filename: str
        start_time: str
        duration: str
        size: str
        bit_rate: str
        tags: dict[str, str]

    class FFProbeOutput(TypedDict):
        format: FFProbeFormat


@dataclass
class Plan(ABC):
    source: pathlib.Path
    dest: pathlib.Path
    progress: Progress
    task_id: TaskID = field(init=False)

    type: str = "Unknown"

    def __post_init__(self):
        self.task_id = self.progress.add_task(
            description=self.source.name,
            start=False,
            visible=False,
            operation_type=self.type,
        )

    def start_task(self):
        self.progress.start_task(self.task_id)
        self.progress.update(self.task_id, visible=True)

    def completed(self):
        self.progress.update(self.task_id, visible=False)

    @abstractmethod
    def _execute(self): ...

    def execute(self) -> None:
        self.start_task()
        self._execute()
        self.completed()


@dataclass
class FFMpegPlan(Plan):
    DEFAULT_FLAGS: ClassVar[list[str]] = [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-progress",
        "pipe:1",
        "-stats_period",
        "0.1",
        "-y",
        "-vn",
    ]

    FFPROBE_FLAGS: ClassVar[list[str]] = [
        "-output_format",
        "json",
        "-show_format",
        "-hide_banner",
        "-loglevel",
        "warning",
    ]
    type: str = "File Recode"

    progress_us: int = field(init=False, default=0)

    @cached_property
    def file_info(self) -> FFProbeOutput:
        res = subprocess.run(
            [
                "ffprobe",
                *self.FFPROBE_FLAGS,
                self.source.absolute().as_posix(),
            ],
            capture_output=True,
        )

        res.check_returncode()
        return json.loads(res.stdout)  # pyright: ignore[reportAny]

    @cached_property
    def format(self) -> FFProbeFormat:
        return self.file_info["format"]

    @cached_property
    def size(self) -> int:
        return int(self.format["size"])

    @cached_property
    def duration(self) -> float:
        return float(self.format["duration"]) * 1_000_000

    @property
    def ffmpeg_args(self):
        return [
            "-i",
            self.source.absolute().as_posix(),
            self.dest.absolute().as_posix(),
        ]

    def _handle_state_update(self, line: str):
        key, _, value = line.strip().partition("=")
        match key:
            case "out_time_us":
                if value.isdecimal():
                    self.progress_us = int(value)
                    self.progress.update(self.task_id, completed=self.progress_us)
                else:
                    self.progress.print(f"Invalid value for out time {value = !r}")
            case _:
                pass

    @override
    def start_task(self):
        track_name = self.format["tags"].get("TITLE", self.source.name)
        track_album = self.format["tags"].get("ALBUM", "UAL")
        track_artist = self.format["tags"].get("ARTIST", "UA")
        self.progress.update(
            self.task_id,
            description=f"{track_artist} - {track_album!r}: {track_name!r}",
            total=self.duration,
        )
        super().start_task()

    @override
    def _execute(self):
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            ["ffmpeg", *self.DEFAULT_FLAGS, *self.ffmpeg_args],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None

        line = ""
        for line in iter(proc.stdout.readline, ""):
            self._handle_state_update(line)
        while proc.poll() is None:
            ...
        if proc.returncode != 0:
            print(f"Failed... {proc.returncode}, {line!r}")


@dataclass
class CopyPlan(Plan):
    type: str = "File Copy"

    @override
    def _execute(self):
        self.dest.parent.mkdir(exist_ok=True, parents=True)
        _ = shutil.copy(self.source, self.dest)
