"""``flyconn-bench`` command line: export, verify and plan uploads of HF-ready snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from flyconn.data.store import Store

from flyconn_bench.export import export_store
from flyconn_bench.slices import parse_slice
from flyconn_bench.upload import plan_upload
from flyconn_bench.verify import verify_export

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)


@app.command()
def export(
    ref: Annotated[str, typer.Argument(help="Dataset reference, e.g. malecns@1.0")],
    out: Annotated[Path, typer.Option("--out", help="Output folder (created)")],
    slice_: Annotated[
        list[str] | None,
        typer.Option("--slice", help="Extra tables: 'min_weight=N' or 'types' (repeatable)"),
    ] = None,
    store: Annotated[
        Path | None, typer.Option(help="Store folder; default is flyconn's cache for REF")
    ] = None,
    repo_id: Annotated[str | None, typer.Option(help="Planned Hub repo id for the card")] = None,
    force: Annotated[bool, typer.Option(help="Replace a previous export in OUT")] = False,
    memory_limit: Annotated[str, typer.Option(help="DuckDB memory cap for slices")] = "2GB",
    threads: Annotated[int, typer.Option(help="DuckDB threads for slices")] = 2,
) -> None:
    """Export a flyconn store to an HF dataset folder. Nothing is uploaded."""
    try:
        slices = [parse_slice(s) for s in slice_ or []]
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--slice") from e
    s = Store(store) if store else Store.open(ref)
    if s.ref != ref:
        msg = f"store at {s.root} holds {s.ref}, not {ref}"
        raise typer.BadParameter(msg, param_hint="--store")
    try:
        result = export_store(
            s,
            out,
            slices,
            repo_id=repo_id,
            force=force,
            memory_limit=memory_limit,
            threads=threads,
        )
    finally:
        s.close()
    for t in result.tables:
        typer.echo(f"{t.path:<34} {t.rows:>13,} rows {t.bytes / 1e6:>9.1f} MB {t.seconds:>7.2f} s")
    typer.echo(
        f"wrote {out} in {result.info['seconds_total']} s "
        f"(peak RSS {result.info['peak_rss_mb']} MB)"
    )


@app.command()
def verify(
    out: Annotated[Path, typer.Argument(help="Export folder")],
    load: Annotated[bool, typer.Option(help="Round-trip through datasets.load_dataset")] = True,
    deep: Annotated[bool, typer.Option(help="Compare full contents (small exports)")] = False,
    cache_dir: Annotated[
        Path | None, typer.Option(help="datasets cache folder for the round trip")
    ] = None,
) -> None:
    """Check checksums and row counts of an export."""
    report = verify_export(out, load=load, deep=deep, cache_dir=cache_dir)
    for line in report.checked:
        typer.echo(line)
    for line in report.problems:
        typer.echo(f"PROBLEM: {line}", err=True)
    if not report.ok:
        raise typer.Exit(1)
    typer.echo("ok")


@app.command()
def upload(
    out: Annotated[Path, typer.Argument(help="Export folder")],
    repo_id: Annotated[
        str | None, typer.Option(help="Hub repo id (default: from the export)")
    ] = None,
) -> None:
    """Dry run: check the licence gate and the export, and list what would be uploaded.

    Uploading itself is not enabled yet; it needs the owner's approval per dataset.
    """
    plan = plan_upload(out, repo_id=repo_id)
    typer.echo(f"dataset {plan.ref} -> https://huggingface.co/datasets/{plan.repo_id} (dry run)")
    for rel, size in plan.files:
        typer.echo(f"  {rel:<34} {size / 1e6:>9.1f} MB")
    typer.echo(f"  total {plan.total_bytes / 1e6:.1f} MB; commit message: {plan.commit_message}")
    for p in plan.problems:
        typer.echo(f"BLOCKED: {p}", err=True)
    if not plan.ok:
        raise typer.Exit(1)
    typer.echo("ready (nothing was uploaded)")
