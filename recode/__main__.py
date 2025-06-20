import os
import pathlib
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor

from rich import print
from rich.live import Live

from . import recode, ui

ignored_globs = [".localized"]


def create_plan(source: pathlib.Path, dest: pathlib.Path, render: ui.Render):
    if any(source.match(f) for f in ignored_globs):
        return None

    match source.suffix.lower():
        case ".ape" | ".flac" | ".m4a" | ".mp4":
            return recode.FFMpegPlan(
                source, dest.with_suffix(".ogg"), render.task_progress
            )
        case ".ogg" | ".cue" | ".mp3" | ".ogg":
            return recode.CopyPlan(source, dest, render.task_progress)

        # Varied sometimes-inclided files that we dont need to copy
        case (
            ".jpg" | ".png" | ".log" | ".pdf" | ".txt" | ".ffp" | ".md5" | 
            ".m3u" | ".nfo" | ".!qb" | ".jpeg" | ".accurip" | ".db" | 
            ".html" | ".bmp" | ".sfv" | ".htm" | ".sh" | ".gif" | ".zsh" 
            | ".swf" | ".exe" | ".inf" | ".DS_Store" | ".m3u8" | ".to"
        ):  # fmt: skip
            return None

        case _:
            # return recode.CopyPlan(source, dest, render.task_progress)
            print(f"Dont know how to handle {source}")
            return None


def create_plans(
    source: pathlib.Path, dest: pathlib.Path, render: ui.Render
) -> list[recode.Plan]:
    if not source.exists():
        return []

    out: list[recode.Plan] = []
    task = render.total_progress.add_task(
        description="Processing... (Files Scanned / Files Selected)",
        total=None,
        start=True,
    )
    for local_source in source.glob("**"):
        if not local_source.is_file():
            continue

        render.total_progress.advance(task, 1)
        if local_source.name == ".localized":
            continue

        local_dest = dest / local_source.relative_to(source)
        if (plan := create_plan(local_source, local_dest, render)) is not None:
            out.append(plan)

    render.total_progress.update(task, total=len(out))
    return sorted(out, key=lambda v: v.source)


def main(source: pathlib.Path, dest: pathlib.Path):
    executor = ThreadPoolExecutor(max_workers=os.cpu_count())

    render = ui.make_render()

    with Live(render.table, refresh_per_second=10):
        tasks: list[recode.Plan] = create_plans(source, dest, render)
        total_task = render.total_progress.add_task("Files Processed", total=len(tasks))

        def exec_worker(plan: recode.Plan):
            plan.execute()
            render.total_progress.advance(total_task, 1)

        _ = list(executor.map(exec_worker, tasks))


if __name__ == "__main__":
    parser = ArgumentParser()
    _ = parser.add_argument(
        "--source-path",
        "-s",
        type=pathlib.Path,
        required=True,
        help="Source of media files",
    )
    _ = parser.add_argument(
        "--dest-path",
        "-d",
        type=pathlib.Path,
        required=True,
        help="Dest of media files",
    )
    _ = parser.add_argument("--copy-unknown", action="store_true")
    parsed = parser.parse_args()

    main(parsed.source_path, parsed.dest_path)
