"""The seam registry — Mizune's harness.

A **seam** is a swappable capability with three roles: a *definition* declaring the
interface, a *provider* implementing it, and a *consumer* using it. One role alone is not
a seam. That rule is borrowed from deepseek-harness (`docs/capability-seams.md`); the
implementation here is not, because Mizune has 163 MB of RAM and no room for a DI
container.

WHY THIS EXISTS — a real defect, not a design preference:

    # server/subconscious.py, before 2026-08-09
    due = getattr(global_cron_manager, "peek_due_soon", lambda: [])()

`CronManager` has no `peek_due_soon`. The fallback fired on every tick since the line was
written, so the branch returned `[]` forever and the subconscious's scheduled-task
awareness never once contributed anything. Nobody noticed, because a silent fallback
looks exactly like a working feature with nothing to report. That is a consumer with no
definition and no provider — and it is invisible by construction.

The registry makes that shape impossible to write by accident:

    HARNESS.declare("orchestra.llm", "...", methods=("complete",))   # definition
    HARNESS.provide("orchestra.llm", MistralPool(...), source="orchestra")  # provider
    llm = HARNESS.require("orchestra.llm")                            # consumer

`require` raises. It does not degrade. A missing provider is a wiring bug and wiring bugs
should be loud at the first call, not silent for three months.

DESIGN LIMITS, stated so nobody expects more:

- Not a DI container. No lifecycle, no scopes, no injection, no async. A dict with rules.
- Duck-typed. `methods=` is checked with `hasattr` at registration time, which catches the
  typo and the wrong object; it does not check signatures.
- Process-global, single instance. Mizune is one process with one config.
- Zero runtime cost after registration: `require` is a dict lookup.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:                                    # keep the module importable from scripts/tests
    from .config import log_info
except ImportError:                     # pragma: no cover
    def log_info(msg: str) -> None:     # type: ignore[misc]
        print(msg)

__all__ = ["Seam", "SeamError", "SeamMissing", "SeamContract", "Harness", "HARNESS"]


class SeamError(RuntimeError):
    """Base for every wiring failure. Always a bug in the program, never in the input."""


class SeamMissing(SeamError):
    """A consumer required a seam nobody provides."""


class SeamContract(SeamError):
    """A provider was registered that does not satisfy the declared interface."""


class Seam:
    """A declared capability: its name, why it exists, and what a provider must offer."""

    __slots__ = ("name", "doc", "methods", "declared_by")

    def __init__(self, name: str, doc: str, methods: Tuple[str, ...], declared_by: str):
        self.name = name
        self.doc = doc
        self.methods = methods
        self.declared_by = declared_by

    def __repr__(self) -> str:            # pragma: no cover - diagnostics only
        return f"<Seam {self.name} by {self.declared_by}>"


class Harness:
    """Declarations, providers, and the rule that a consumer cannot outrun either."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seams: Dict[str, Seam] = {}
        self._providers: Dict[str, Any] = {}
        self._sources: Dict[str, str] = {}
        self._consumers: Dict[str, set] = {}

    # ── definition ─────────────────────────────────────────────────────────────
    def declare(self, name: str, doc: str, *, methods: Iterable[str] = (),
                declared_by: str = "?") -> Seam:
        """Declare a seam. Idempotent — modules are imported more than once."""
        m = tuple(methods)
        with self._lock:
            existing = self._seams.get(name)
            if existing is not None:
                # Re-declaring with a DIFFERENT interface means two modules disagree about
                # what the capability is. That is the drift this registry exists to stop,
                # so it is an error rather than a last-writer-wins overwrite.
                if existing.methods != m:
                    raise SeamContract(
                        f"seam {name!r} re-declared with a different interface: "
                        f"{existing.declared_by} says {existing.methods}, "
                        f"{declared_by} says {m}")
                return existing
            seam = Seam(name, doc, m, declared_by)
            self._seams[name] = seam
            return seam

    # ── provider ───────────────────────────────────────────────────────────────
    def provide(self, name: str, impl: Any, *, source: str = "?") -> Any:
        """Register the implementation. Validated NOW, so a typo fails at import."""
        with self._lock:
            seam = self._seams.get(name)
            if seam is None:
                raise SeamMissing(
                    f"provider registered for undeclared seam {name!r} (from {source}). "
                    f"Declare it first — a provider with no definition is half a seam.")
            missing = [x for x in seam.methods if not hasattr(impl, x)]
            if missing:
                raise SeamContract(
                    f"{source} provides {name!r} with {type(impl).__name__}, which is "
                    f"missing {missing}. Declared interface: {list(seam.methods)}")
            self._providers[name] = impl
            self._sources[name] = source
            return impl

    # ── consumer ───────────────────────────────────────────────────────────────
    def require(self, name: str, *, consumer: str = "?") -> Any:
        """Resolve a seam, or raise. This is the line `getattr(..., lambda: [])` should
        have been."""
        with self._lock:
            self._consumers.setdefault(name, set()).add(consumer)
            impl = self._providers.get(name)
            if impl is not None:
                return impl
            seam = self._seams.get(name)
        if seam is None:
            raise SeamMissing(
                f"{consumer} required seam {name!r}, which was never declared. "
                f"Known seams: {sorted(self._seams)}")
        raise SeamMissing(
            f"{consumer} required seam {name!r} ({seam.doc}), declared by "
            f"{seam.declared_by}, but nothing provides it.")

    def optional(self, name: str, default: Any = None, *, consumer: str = "?") -> Any:
        """Resolve if present, else `default`.

        For capabilities that are genuinely allowed to be absent — a paid search backend
        with no key, say. Use it ONLY where the caller degrades on purpose and says so;
        reaching for it to silence a wiring error rebuilds `peek_due_soon`.
        """
        with self._lock:
            self._consumers.setdefault(name, set()).add(consumer)
            return self._providers.get(name, default)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._providers

    # ── introspection ──────────────────────────────────────────────────────────
    def graph(self) -> List[Dict[str, Any]]:
        """Every seam with its provider and consumers — the capability graph."""
        with self._lock:
            return [{
                "seam": s.name,
                "doc": s.doc,
                "declared_by": s.declared_by,
                "methods": list(s.methods),
                "provider": self._sources.get(s.name),
                "wired": s.name in self._providers,
                "consumers": sorted(self._consumers.get(s.name, ())),
            } for s in sorted(self._seams.values(), key=lambda x: x.name)]

    def unwired(self) -> List[str]:
        """Declared seams nobody provides. A startup check, not a runtime one."""
        with self._lock:
            return sorted(n for n in self._seams if n not in self._providers)

    def report(self) -> str:
        """One-line-per-seam summary for the startup log."""
        rows = self.graph()
        if not rows:
            return "[HARNESS] no seams declared"
        out = [f"[HARNESS] {len(rows)} seam(s):"]
        for r in rows:
            mark = "OK " if r["wired"] else "!! "
            who = r["provider"] or "NOBODY"
            out.append(f"  {mark}{r['seam']:<28} <- {who}"
                       f"   consumers={len(r['consumers'])}")
        return "\n".join(out)

    def check(self, *, strict: bool = False) -> List[str]:
        """Log the graph; return the unwired seams.

        `strict=True` raises instead. Startup calls it non-strict so a half-wired optional
        capability cannot stop the server booting — the log line is the alarm, and the
        `require` at the actual call site is the enforcement.
        """
        log_info(self.report())
        missing = self.unwired()
        if missing:
            msg = f"[HARNESS] UNWIRED SEAMS: {missing}"
            log_info(msg)
            if strict:
                raise SeamMissing(msg)
        return missing


#: The process-wide registry.
HARNESS = Harness()
