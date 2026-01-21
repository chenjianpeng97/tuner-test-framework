"""
Tuner CLI - API Recording Tool

Provides CLI for recording HTTP requests via proxy and generating APIModel definitions.
"""

import asyncio
import contextlib
import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

import click


async def start_recorder(
    port: int,
    url_prefixes: Sequence[str],
    output_dir: str,
    *,
    overwrite: bool = False,
) -> None:
    """
    Start mitmproxy service and record API requests.

    Args:
        port: Proxy listen port
        url_prefixes: URL prefix list, only record matching requests
        output_dir: Output directory
        overwrite: Whether to overwrite existing files
    """
    # Lazy import mitmproxy (may not be installed)
    try:
        from mitmproxy.options import Options  # noqa: PLC0415
        from mitmproxy.tools.dump import DumpMaster  # noqa: PLC0415
    except ImportError:
        click.secho(
            "Error: mitmproxy not installed. Run: pip install mitmproxy", fg="red"
        )
        return

    from .addon import APIModelRecorder, DispatcherAddon  # noqa: PLC0415

    # Parse URL prefixes and extract hosts
    hosts: list[str] = []
    normalized_prefixes: list[str] = []

    for prefix in url_prefixes:
        try:
            parsed = urlparse(prefix)
            host = parsed.netloc
            if not host:
                raise ValueError("Invalid URL prefix")
            hosts.append(host)
            normalized_prefixes.append(prefix)
        except Exception:
            click.secho(
                f"Error: Invalid URL prefix '{prefix}'. "
                "Please provide full URL like 'http://example.com/api'",
                fg="red",
            )
            return

    # Deduplicate
    hosts = list(dict.fromkeys(hosts))

    # Configure mitmproxy
    allow_hosts_regex = [re.escape(h) for h in hosts]
    opts = Options(
        listen_host="127.0.0.1",
        listen_port=port,
        allow_hosts=allow_hosts_regex,
    )

    master = DumpMaster(opts, with_termlog=True)

    # Create recorder for each prefix
    output_path = Path(output_dir)
    recorders = [
        APIModelRecorder(
            url_prefix=prefix,
            output_dir=output_path,
            overwrite=overwrite,
        )
        for prefix in normalized_prefixes
    ]

    # Use dispatcher to manage multiple recorders
    dispatcher = DispatcherAddon(recorders)
    master.addons.add(dispatcher)

    # Print startup info
    abs_output = str(output_path.absolute())  # noqa: ASYNC240
    click.echo("")
    click.secho("=" * 60, fg="cyan")
    click.secho("  Tuner API Recorder", fg="cyan", bold=True)
    click.secho("=" * 60, fg="cyan")
    click.echo("")
    click.echo(f"  Proxy address: http://127.0.0.1:{port}")
    click.echo(f"  Output directory: {abs_output}")
    click.echo("")
    click.secho("  Recording URL prefixes:", fg="yellow")
    for prefix in normalized_prefixes:
        click.echo(f"    - {prefix}")
    click.echo("")
    click.secho("  Tips:", fg="green")
    click.echo(f"    1. Configure browser/app to use proxy 127.0.0.1:{port}")
    click.echo("    2. Visit http://mitm.it to install certificate (for HTTPS)")
    click.echo("    3. Operate target app, requests will be recorded as APIModel")
    click.echo("    4. Press Ctrl+C to stop recording")
    click.echo("")
    click.secho("=" * 60, fg="cyan")
    click.echo("")

    try:
        await master.run()
    except KeyboardInterrupt:
        master.shutdown()


@click.group()
@click.version_option(version="1.0.0", prog_name="tuner")
def cli():
    """Tuner test framework CLI tool."""
    pass


@cli.command("record")
@click.option(
    "--port",
    "-p",
    default=8080,
    type=int,
    help="Proxy listen port (default: 8080)",
)
@click.option(
    "--url-prefix",
    "-u",
    required=True,
    multiple=True,
    help="URL prefix to record. Can be specified multiple times. e.g., -u http://api.example.com/v1",
)
@click.option(
    "--output",
    "-o",
    default="recorded_apis",
    type=str,
    help="Output directory (default: recorded_apis)",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing files",
)
def cmd_record(port: int, url_prefix: tuple[str, ...], output: str, overwrite: bool):
    """Start proxy to record API requests and generate APIModel definitions."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(
            start_recorder(
                port=port,
                url_prefixes=url_prefix,
                output_dir=output,
                overwrite=overwrite,
            )
        )

    click.echo("")
    click.secho("Recording stopped.", fg="yellow")
    click.echo(f"Generated APIModel files saved in: {output}/")


def main():
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
