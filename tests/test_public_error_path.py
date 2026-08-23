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

    error = ValueError("database unavailable")
    reference = common.log_public_exception(error)

    assert re.fullmatch(r"WEB-[A-F0-9]{8}", reference)
    assert f"[web][{reference}] ValueError: database unavailable" in capsys.readouterr().out
    assert printed_tracebacks
    assert printed_tracebacks[0][1] is error


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
