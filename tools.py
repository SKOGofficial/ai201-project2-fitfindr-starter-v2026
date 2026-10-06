"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings

_STOPWORDS = {
    "a", "an", "and", "the", "for", "in", "of", "on", "or", "to", "with", "under",
    "below", "over", "around", "size", "i", "me", "my", "want", "need", "looking",
    "find", "some", "something", "that", "is", "it", "any",
}


def _words(text: str) -> set[str]:
    """Lowercase word tokens, with a trailing plural 's' stripped ("tees" -> "tee")."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in tokens}


def _size_tokens(size: str) -> set[str]:
    """Split a size on spaces, '/', and parentheses: "S/M" -> {"s", "m"}."""
    return {t for t in re.split(r"[\s/()]+", size.lower()) if t}


def _size_matches(requested: str, listing_size: str) -> bool:
    """Whole-token match: every token of the request must be a token of the listing."""
    wanted = _size_tokens(requested)
    return bool(wanted) and wanted <= _size_tokens(listing_size)



def _fix_text(text: str) -> str:
    """The sample data has UTF-8 dashes that were decoded as cp1252; undo that."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _describe_item(item: dict) -> str:
    return (
        f"{_fix_text(item['title'])} - {item['category']}, size {item['size']}, "
        f"{item['condition']} condition, ${item['price']:g} on {item['platform']}. "
        f"Colors: {', '.join(item['colors'])}. Style: {', '.join(item['style_tags'])}."
    )


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    keywords = _words(description) - _STOPWORDS
    scored = []
    for listing in load_listings():
        if max_price is not None and listing["price"] > max_price:
            continue
        if size and not _size_matches(size, listing["size"]):
            continue
        haystack = _words(" ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            listing["brand"] or "",
            " ".join(listing["style_tags"]),
            " ".join(listing["colors"]),
        ]))
        score = len(keywords & haystack)
        if score > 0:
            scored.append((score, listing))
    scored.sort(key=lambda pair: pair[0], reverse=True)  # stable: ties keep file order
    return [listing for _, listing in scored[:config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    items = (wardrobe or {}).get("items") or []
    item_text = _describe_item(new_item)
    if not items:
        prompt = (
            f"A shopper is considering this secondhand find:\n{item_text}\n\n"
            "They have not told us what is in their wardrobe. Give general styling "
            "advice: one or two outfit ideas built around this item, naming the kinds "
            "of pieces that would go with it. Keep it under 120 words."
        )
    else:
        closet = "\n".join(
            f"- {w['name']} ({w['category']}; {', '.join(w['colors'])}; "
            f"{', '.join(w['style_tags'])})" + (f" - {w['notes']}" if w.get("notes") else "")
            for w in items
        )
        prompt = (
            f"A shopper is considering this secondhand find:\n{item_text}\n\n"
            f"Their wardrobe:\n{closet}\n\n"
            "Suggest one or two outfits that combine the new item with pieces they "
            "already own. Name those pieces exactly as listed. Keep it under 150 words."
        )
    result = generate(prompt, system="You are a thrift-store stylist. Be specific and concise.")
    return result.strip() or "Pair it with simple basics in a neutral colour."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip() or not new_item:
        return "Can't write a fit card without an outfit and an item."
    price = f"${new_item['price']:g}"
    prompt = (
        f"Item: {_fix_text(new_item['title'])}\n"
        f"Price: {price}\nPlatform: {new_item['platform']}\n\n"
        f"Outfit idea:\n{outfit}\n\n"
        "Write a two-to-four sentence caption someone would actually post about this "
        "find. Sound like a real post, not a product description. Mention the item, "
        f"its price written exactly as {price}, and the platform once each, and be "
        "specific about the vibe."
    )
    result = generate(prompt, system="You write short, casual social captions for thrift finds.")
    return result.strip() or "Can't write a fit card: the model returned nothing."
