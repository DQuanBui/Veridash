"""Brand assets: the Veridash "V" mark, wordmark and small line icons.

Everything is inline SVG so no binary assets are required at runtime.
The mark is a V whose right stroke rises like a check mark ("verified").
"""

from __future__ import annotations

from core.settings import APP_NAME

MARK_SVG = (
    '<svg width="{s}" height="{s}" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" '
    'aria-hidden="true">'
    '<defs><linearGradient id="vdg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#14B8A6"/><stop offset="1" stop-color="#0F766E"/>'
    "</linearGradient></defs>"
    '<rect width="32" height="32" rx="8" fill="url(#vdg)"/>'
    '<path d="M8.5 11 L14.6 22.5 L24 8.8" fill="none" stroke="#fff" stroke-width="3.2" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def mark(size: int = 28) -> str:
    """Return the V mark as an inline SVG string."""
    return MARK_SVG.format(s=size)


def wordmark(size: int = 28) -> str:
    """Return the mark plus the "Veridash" wordmark as HTML."""
    return f'<span class="vd-wordmark">{mark(size)}<span>{APP_NAME}</span></span>'


def logo_svg_file_content() -> str:
    """Return a standalone wordmark SVG for ``st.logo`` (teal text reads on light and dark)."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="150" height="32" viewBox="0 0 150 32">'
        + MARK_SVG.format(s=32).replace("<svg", "<svg x='0' y='0'", 1)
        + '<text x="42" y="23" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="20" '
        'font-weight="800" fill="#0D9488" letter-spacing="-0.4">Veridash</text></svg>'
    )


_ICON_PATHS = {
    "upload": '<path d="M12 16V4m0 0-4 4m4-4 4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    "check": '<path d="M9 12.5l2 2 4-4.5"/><path d="M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6l7-3z"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "export": '<path d="M14 3h6v6"/><path d="M20 3l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/>',
    "sql": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>',
}


def icon(name: str, size: int = 20) -> str:
    """Return a stroked line icon (24px grid) as inline SVG."""
    path = _ICON_PATHS[name]
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )
