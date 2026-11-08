"""A deliberately simple theme tagger: whole-word keyword matches, nothing hidden."""
import collections
import re

THEMES = {
    "Story": ["story", "stories", "narrative", "plot", "ending", "storytelling", "characters", "character"],
    "Music and sound": ["music", "soundtrack", "score", "sound", "melody", "audio", "song"],
    "Visual style": ["visual", "visuals", "graphics", "painted", "painting", "canvas", "colors", "colours", "art style", "landscape", "landscapes", "beautiful"],
    "Emotion": ["cry", "cried", "tears", "emotional", "emotion", "emotions", "moved", "grief", "joy", "sadness", "awe", "felt"],
    "Player agency": ["choice", "choices", "decide", "decision", "decisions", "control", "agency", "responsible"],
    "Atmosphere and world": ["atmosphere", "world", "ruins", "desert", "environment", "quiet", "silence", "solitude"],
    "Meaning and reflection": ["meaning", "reflect", "reflection", "philosophical", "mortality", "existence", "life", "death"],
}

_PATTERNS = {theme: re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", re.I) for theme, words in THEMES.items()}


def tag_answer(answer):
    return [theme for theme, pattern in _PATTERNS.items() if pattern.search(answer)]


def theme_counts(answers):
    """Return [(theme, responses tagged)], most common first."""
    counts = collections.Counter()
    for answer in answers:
        counts.update(tag_answer(answer))
    return [(theme, counts.get(theme, 0)) for theme in sorted(THEMES, key=lambda t: -counts.get(t, 0))]
