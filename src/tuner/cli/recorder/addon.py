"""
mitmproxy Addon: API Model Recorder

Intercept HTTP requests and generate corresponding APIModel definition files.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

from .codegen import (
    RecordedRequest,
    RecordedResponse,
    generate_apimodel_code,
    generate_filename,
)


class APIModelRecorder:
    """
    mitmproxy addon for recording HTTP requests and generating APIModel definitions.

    Usage:
        recorder = APIModelRecorder(
            url_prefix="http://api.example.com/v1",
            output_dir="recorded_apis"
        )
        # Add to mitmproxy addons
    """

    # Static resource extensions (skip recording)
    STATIC_EXT_PATTERN = (
        r"\.(css|js|jpg|jpeg|png|gif|svg|woff2?|ttf|map|ico|json|xml|eot|otf|"
        r"mp3|mp4|webp|webm|pdf|zip|tar|gz)(?:[?#]|$)"
    )

    def __init__(
        self,
        url_prefix: str,
        output_dir: str | Path = "recorded_apis",
        *,
        skip_static: bool = True,
        overwrite: bool = False,
    ):
        """
        Initialize recorder.

        Args:
            url_prefix: URL prefix, only record matching requests
            output_dir: Output directory
            skip_static: Whether to skip static resources
            overwrite: Whether to overwrite existing files
        """
        self.url_prefix = url_prefix
        self.output_dir = Path(output_dir)
        self.skip_static = skip_static
        self.overwrite = overwrite

        self._static_re = re.compile(self.STATIC_EXT_PATTERN, re.IGNORECASE)
        self._processed_urls: set[str] = set()

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Create __init__.py to make it a Python package
        init_file = self.output_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text(
                '"""Recorded API Model definitions"""\n', encoding="utf-8"
            )

    def _should_skip(self, url: str) -> bool:
        """Determine whether to skip this request."""
        # Check prefix
        if not url.startswith(self.url_prefix):
            return True

        # Check if already processed
        # Use URL without query string as unique identifier
        parsed = urlparse(url)
        url_key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if url_key in self._processed_urls:
            return True

        # Check static resources
        return self.skip_static and self._static_re.search(url) is not None

    def _mark_processed(self, url: str) -> None:
        """Mark URL as processed."""
        parsed = urlparse(url)
        url_key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        self._processed_urls.add(url_key)

    def response(self, flow) -> None:  # mitmproxy.http.HTTPFlow
        """
        mitmproxy response hook.

        Record request after receiving response and generate APIModel.
        """
        from mitmproxy import ctx  # noqa: PLC0415

        req = flow.request
        res = flow.response

        url = req.url

        # Check if should skip
        if self._should_skip(url):
            return

        # Mark as processed
        self._mark_processed(url)

        # Build recorded data
        recorded_request = RecordedRequest(
            method=req.method,
            url=url,
            headers=dict(req.headers),
            body_content=req.content,
            body_content_type=req.headers.get("content-type"),
        )

        recorded_response = RecordedResponse(
            status_code=res.status_code,
            headers=dict(res.headers),
            body_content=res.content,
        )

        # Generate code
        try:
            code = generate_apimodel_code(
                recorded_request, recorded_response, url_prefix=self.url_prefix
            )
        except Exception as e:
            ctx.log.error(f"Failed to generate APIModel code: {url} - {e}")
            return

        # Generate filename
        parsed = urlparse(url)
        filename = generate_filename(req.method, parsed.path, self.url_prefix)
        filepath = self.output_dir / filename

        # Check overwrite
        if filepath.exists() and not self.overwrite:
            # Add sequence number to avoid overwriting
            base = filepath.stem
            suffix = filepath.suffix
            counter = 1
            while filepath.exists():
                filepath = self.output_dir / f"{base}_{counter}{suffix}"
                counter += 1

        # Write file
        try:
            filepath.write_text(code, encoding="utf-8")
            ctx.log.info(f"Generated APIModel: {filepath}")
        except Exception as e:
            ctx.log.error(f"Failed to write file: {filepath} - {e}")


class DispatcherAddon:
    """
    Dispatcher addon supporting multiple URL prefixes.

    Dispatch requests matching different prefixes to corresponding APIModelRecorder.
    """

    def __init__(self, recorders: list[APIModelRecorder]):
        """
        Initialize dispatcher.

        Args:
            recorders: List of APIModelRecorder instances
        """
        self.recorders = recorders

    def response(self, flow) -> None:  # mitmproxy.http.HTTPFlow
        """Dispatch response to matching recorder."""
        url = flow.request.url
        for recorder in self.recorders:
            if url.startswith(recorder.url_prefix):
                recorder.response(flow)
                # One request only handled by one recorder
                break
