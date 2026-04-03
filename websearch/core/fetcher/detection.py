"""SPA detection heuristics."""

from __future__ import annotations

# JavaScript frameworks that indicate a SPA
SPAMARKERS = [
    # Core frameworks
    b"react",
    b"vue",
    b"angular",
    b"svelte",
    b"solid",
    b"lit",
    b"preact",
    # Next.js variants
    b"next",
    b"__next",
    b"_next/",
    # Nuxt.js variants
    b"nuxt",
    b"nuxtjs",
    # Remix
    b"remix",
    b"@remix-run",
    # Shopify Hydrogen
    b"@shopify/hydrogen",
    b"shopify hydrogen",
    # Gatsby
    b"gatsby",
    b"gatsbyjs",
    # Astro (can be SPA or MPA, but often SPA-like behavior)
    b"astro",
    b"astro-island",
    # Inertia.js
    b"inertia",
    b"@inertiajs",
    # Livewire
    b"livewire",
    b"@livewire",
    # Hotwire (Turbo)
    b"hotwire",
    b"@hotwired",
    b"turbo-",
    b"data-turbo",
    # Alpine.js
    b"alpinejs",
    b"@alpinejs",
    # Stimulus
    b"stimulus",
    b"@stimulus",
    # Solid.js
    b"solid-js",
    b"solidjs",
]

# HTML attributes that indicate dynamic content
DYNAMIC_ATTRIBUTES = [
    b"data-vue",
    b"ng-app",
    b"data-reactroot",
    b"data-ng-app",
    # Vue 3 specific
    b"data-v-app",
    b"v-app",
    # React 18+ hydration markers
    b"data-reactroot",
    b"data-hydrate",
    # Inertia.js
    b"data-page",
    b"data-inertia",
    # Livewire
    b"wire:id",
    b"wire:init",
    b"wire:model",
    b"wire:effect",
    b"wire:navigate",
    # Hotwire Turbo
    b"data-turbo-frame",
    b"data-turbo-action",
    b"data-turbo-permanent",
    # Alpine.js
    b"x-data",
    b"x-init",
    b"x-show",
    b"x-for",
    # Stimulus
    b"data-controller",
    b"data-action",
    b"data-target",
    # Solid.js
    b"data-solid",
    b"data-solid-start",
]

# CDN-hosted framework patterns
CDN_PATTERNS = [
    b"cdn.jsdelivr.net/npm/react",
    b"cdn.jsdelivr.net/npm/vue",
    b"cdn.jsdelivr.net/npm/svelte",
    b"cdn.jsdelivr.net/npm/solid",
    b"cdn.jsdelivr.net/npm/lit",
    b"cdn.jsdelivr.net/npm/preact",
    b"unpkg.com/react",
    b"unpkg.com/vue",
    b"unpkg.com/svelte",
    b"unpkg.com/solid",
    b"unpkg.com/lit",
    b"unpkg.com/preact",
    b"unpkg.com/alpinejs",
    b"cdnjs.cloudflare.com/ajax/libs/react",
    b"cdnjs.cloudflare.com/ajax/libs/vue",
    b"cdnjs.cloudflare.com/ajax/libs/angular",
    b"cdnjs.cloudflare.com/ajax/libs/svelte",
    b"cdnjs.cloudflare.com/ajax/libs/lit",
    b"cdnjs.cloudflare.com/ajax/libs/preact",
    b"cdn.jsdelivr.net/npm/@hotwired/turbo",
    b"cdn.jsdelivr.net/npm/alpinejs",
]

# Common JS bundle patterns that indicate SPA
BUNDLE_PATTERNS = [
    b"/_next/static/",
    b"/build/static/",
    b"/assets/",
    b"/chunks/",
    b"chunk-vendors",
    b"chunk-",
    b".bundle.",
    b"/dist/",
    b"/out/_build/",
]


def is_spa(html: bytes) -> bool:
    """Detect if page is likely a SPA based on content.

    A page is considered a SPA when:
    1. Content is minimal (<500 bytes)
    2. Contains JavaScript framework markers
    3. Contains dynamic content attributes
    4. Contains CDN-hosted framework patterns
    5. Contains bundle patterns

    Args:
        html: Raw HTML content

    Returns:
        True if page is likely a SPA
    """
    if len(html) < 500:
        return True

    content_lower = html.lower()

    # Check for framework markers
    for marker in SPAMARKERS:
        if marker in content_lower:
            return True

    # Check for dynamic attributes
    for attr in DYNAMIC_ATTRIBUTES:
        if attr in content_lower:
            return True

    # Check for CDN patterns
    for pattern in CDN_PATTERNS:
        if pattern in content_lower:
            return True

    # Check for bundle patterns
    for pattern in BUNDLE_PATTERNS:
        if pattern in content_lower:
            return True

    return False
