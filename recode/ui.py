import os
from collections.abc import Iterable
from typing import NamedTuple, override

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Column, Table


class RunningFirstProgress(Progress):
    @override
    def make_tasks_table(self, tasks: Iterable[Task]) -> Table:
        return super().make_tasks_table(sorted(tasks, key=lambda t: t.start_time or 0))


class Render(NamedTuple):
    table: Table
    task_progress: Progress
    total_progress: Progress


def make_render():
    task_progress = RunningFirstProgress(
        TextColumn("{task.fields[operation_type]:<20} | "),
        TextColumn("{task.description}", table_column=Column(ratio=10)),
        SpinnerColumn(),
        BarColumn(table_column=Column(justify="right")),
        TaskProgressColumn(),
        TimeRemainingColumn(compact=True, elapsed_when_finished=True),
        refresh_per_second=10,
        expand=True,
    )

    total_progress = Progress(
        TextColumn("{task.description}", table_column=Column(ratio=1)),
        MofNCompleteColumn(),
        SpinnerColumn(),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(compact=True, elapsed_when_finished=True),
        refresh_per_second=10,
        expand=True,
    )

    table = Table.grid(expand=True)

    table.add_row(
        Panel(
            task_progress,
            height=os.cpu_count(),
            title="In Progress...",
            title_align="left",
            padding=(1, 1),
        )
    )
    table.add_row(
        Panel(
            total_progress,
            title="Total Progress...",
            title_align="left",
            padding=(1, 1),
        )
    )

    return Render(table, task_progress, total_progress)
