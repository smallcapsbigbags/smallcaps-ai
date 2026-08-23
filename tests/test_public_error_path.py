from __future__ import annotations

import re

from ui import common


def test_public_exception_logging_returns_traceable_reference(
    monkeypatch,
    capsys,
) -> None:
    printed_tracebacks: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        common.traceback,
        "print_exception",
        lambda *args, **_kwargs: printed_tracebacks.append(args),
    )

    error = ValueError("database unavailable\nsecond line")
    reference = common.log_public_exception(error)

    assert re.fullmatch(r"WEB-[A-F0-9]{8}", reference)
    output = capsys.readouterr().out
    assert f"[web][{reference}] ValueError: database unavailable second line" in output
    assert printed_tracebacks
    assert printed_tracebacks[0][1] is error


def test_public_exception_reference_survives_traceback_logging_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        common.traceback,
        "print_exception",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("log failed")),
    )

    reference = common.log_public_exception(RuntimeError("customer-safe path"))

    assert re.fullmatch(r"WEB-[A-F0-9]{8}", reference)


def test_public_service_error_escapes_and_displays_reference(monkeypatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(common, "render_brand", lambda: None)
    monkeypatch.setattr(common, "render_footer", lambda: None)
    monkeypatch.setattr(
        common.st,
        "markdown",
        lambda body, **_kwargs: rendered.append(body),
    )

    common.render_service_error(reference='WEB-<script>alert("x")</script>')

    assert len(rendered) == 1
    assert 'Reference: WEB-&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in rendered[0]
    assert "<script>" not in rendered[0]
    assert "Smallcaps.ai is temporarily unavailable." in rendered[0]
