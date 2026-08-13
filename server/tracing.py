"""Optional TraceRoot integration.

Import `observe` / `update_current_span` from here instead of `traceroot` directly.
When the real traceroot SDK is unavailable (e.g. Python 3.10 on the VM), these
degrade to no-ops so the server runs identically — just without tracing.
Replaces the hand-made dummy `traceroot` module that used to live on the VM.
"""
import os

try:
    import traceroot as _traceroot
    from traceroot import observe
    from traceroot import update_current_span as _update_current_span_real
    HAS_TRACEROOT = True

    def update_current_span(*args, **kwargs):
        """Safe wrapper around the real SDK's KEYWORD-ONLY update_current_span.

        Telemetry must NEVER break a feature. Two real bugs came from this:
        callers passed a POSITIONAL dict (update_current_span({...})) but the SDK
        signature is `(*, name=None, input=None, metadata=None, ...)`, raising
        'takes 0 positional arguments but 1 was given' and aborting SystemAgent /
        Vision / task-planner / action-executor mid-run (seen 26x in VM traces
        2026-07-24). So: map a stray positional dict → metadata, drop other
        positionals, and swallow ANY SDK error — a span update can never be
        allowed to crash the caller."""
        try:
            if args:
                if len(args) == 1 and isinstance(args[0], dict):
                    kwargs.setdefault("metadata", args[0])
                args = ()
            return _update_current_span_real(**kwargs)
        except Exception:
            return None
except Exception:
    _traceroot = None
    HAS_TRACEROOT = False

    def observe(*d_args, **d_kwargs):
        """No-op decorator; works bare (@observe) and configured (@observe(name=...))."""
        if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
            return d_args[0]

        def _decorator(fn):
            return fn
        return _decorator

    def update_current_span(*args, **kwargs):
        return None


def initialize_tracing() -> bool:
    """Initialize TraceRoot from TRACEROOT_API_KEY if the SDK is present."""
    api_key = os.getenv("TRACEROOT_API_KEY")
    if not HAS_TRACEROOT or not api_key:
        return False
    try:
        from traceroot.instrumentation import Integration
        _traceroot.initialize(
            api_key=api_key,
            integrations=[Integration.GOOGLE_GENAI, Integration.OPENAI],
        )
        return True
    except Exception as e:
        print(f"[TRACING] TraceRoot init failed (non-fatal): {e}")
        return False
