"""
Music Recommender Simulation — Terminal Runner
===============================================

Runs five UserProfile taste profiles AND eight evaluation/adversarial
dict profiles against the 20-song catalog.

Standard UserProfiles (Section 1):
  0. Default (pop / happy)  — starter profile from the project brief
  1. Late Night Coder       — lofi / focused / acoustic
  2. Weekend Warrior        — pop  / intense / produced
  3. Sunday Morning         — folk / peaceful / acoustic
  4. Dark Commute           — synthwave / moody / produced

Evaluation dict profiles (Section 2) — three standard benchmarks:
  A. High-Energy Pop        — genre match at full intensity
  B. Chill Lofi             — genre match at full calm
  C. Deep Intense Rock      — genre match with a single-song catalog

Adversarial / edge-case dict profiles (Section 2, continued):
  D. High-Energy Melancholic  — energy 0.92 vs genre classical (low-energy catalog)
  E. Midpoint Collapse        — all continuous features at 0.50
  F. Niche Metal Fan          — only ONE catalog song matches the genre
  G. Acoustic Intensity Conflict — likes_acoustic=True but energy=0.90
  H. Out-of-Range Tempo       — target 220 BPM exceeds catalog max (168)
"""

from recommender import (
    load_songs, recommend_songs, score_song,
    UserProfile, _score_song_for_user, Song, MAX_SCORE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Layout constants
# ─────────────────────────────────────────────────────────────────────────────
WIDTH      = 66          # total line width
BAR_WIDTH  = 20          # character width of the ASCII score bar
INDENT     = "    "      # 4-space indent for reason lines

# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Taste Profiles  (UserProfile objects)
# ─────────────────────────────────────────────────────────────────────────────

# Profile 0 — Default "pop / happy"
# The starter profile from the project brief.  Used as the primary
# verification case: top results should be bright, energetic pop songs.
default_pop_happy = UserProfile(
    favorite_genre   = "pop",
    favorite_mood    = "happy",
    target_energy    = 0.80,
    likes_acoustic   = False,
    target_valence   = 0.82,
    target_tempo_bpm = 118.0,
)

# Profile 1 — Late Night Coder
late_night_coder = UserProfile(
    favorite_genre   = "lofi",
    favorite_mood    = "focused",
    target_energy    = 0.40,
    likes_acoustic   = True,
    target_valence   = 0.58,
    target_tempo_bpm = 80.0,
)

# Profile 2 — Weekend Warrior
weekend_warrior = UserProfile(
    favorite_genre   = "pop",
    favorite_mood    = "intense",
    target_energy    = 0.92,
    likes_acoustic   = False,
    target_valence   = 0.78,
    target_tempo_bpm = 132.0,
)

# Profile 3 — Sunday Morning
sunday_morning = UserProfile(
    favorite_genre   = "folk",
    favorite_mood    = "peaceful",
    target_energy    = 0.28,
    likes_acoustic   = True,
    target_valence   = 0.68,
    target_tempo_bpm = 74.0,
)

# Profile 4 — Dark Commute
dark_commute = UserProfile(
    favorite_genre   = "synthwave",
    favorite_mood    = "moody",
    target_energy    = 0.75,
    likes_acoustic   = False,
    target_valence   = 0.45,
    target_tempo_bpm = 108.0,
)

ALL_PROFILES = {
    "Default: Pop / Happy ": default_pop_happy,
    "Late Night Coder     ": late_night_coder,
    "Weekend Warrior      ": weekend_warrior,
    "Sunday Morning       ": sunday_morning,
    "Dark Commute         ": dark_commute,
}

# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Evaluation Profiles  (plain dicts, used by recommend_songs)
# ─────────────────────────────────────────────────────────────────────────────
# These are defined as raw preference dicts rather than UserProfile objects
# so they can be passed directly to recommend_songs() without conversion.
# ─────────────────────────────────────────────────────────────────────────────

# ── Standard Benchmark Profiles ──────────────────────────────────────────────

# A — High-Energy Pop
# A bright, high-BPM pop listener who wants maximum energy and positivity.
# Expected: Gym Hero and Sunrise City dominate; genre+energy alignment is strong.
high_energy_pop: dict = {
    "genre":            "pop",
    "mood":             "happy",
    "energy":           0.92,
    "likes_acoustic":   False,
    "target_valence":   0.88,
    "target_tempo_bpm": 128.0,
}

# B — Chill Lofi
# A warm, slow lofi listener who wants organic texture and a low-intensity vibe.
# Expected: Focus Flow and Library Rain at the top; acoustic weight matters here.
chill_lofi: dict = {
    "genre":            "lofi",
    "mood":             "chill",
    "energy":           0.35,
    "likes_acoustic":   True,
    "target_valence":   0.58,
    "target_tempo_bpm": 75.0,
}

# C — Deep Intense Rock
# A raw, heavy rock listener pushing intensity and valence to dark extremes.
# Expected: Storm Runner at #1 (only rock song); everything else fills in on
# numeric similarity (energy/valence) with no further genre matches available.
deep_intense_rock: dict = {
    "genre":            "rock",
    "mood":             "intense",
    "energy":           0.95,
    "likes_acoustic":   False,
    "target_valence":   0.28,
    "target_tempo_bpm": 155.0,
}

# ── Adversarial / Edge-Case Profiles ─────────────────────────────────────────
# Designed via codebase analysis to expose known weaknesses in the scoring logic.
# Each profile targets a specific bias documented in README.md § Known Biases.

# D — High-Energy Melancholic  [conflicts energy with genre physics]
# Classical songs in the catalog (Rainy Sonata) all have energy ~0.22.
# This profile asks for classical + melancholic but at energy=0.92, which is
# the opposite of what classical songs can deliver.
# Exposes: genre bonus can pull a low-energy song into the top result even when
# the energy penalty is severe — or alternatively, non-classical songs dominate
# despite genre mismatch, revealing the limits of the genre anchor.
high_energy_sad: dict = {
    "genre":            "classical",
    "mood":             "melancholic",
    "energy":           0.92,
    "likes_acoustic":   False,
    "target_valence":   0.20,
    "target_tempo_bpm": 145.0,
}

# E — Midpoint Collapse  [all continuous features at 0.50]
# Every Gaussian feature (energy, valence, tempo) is set to exactly 0.50.
# Songs at 0.28 energy and songs at 0.83 energy are equidistant from 0.50
# and score nearly identically on that dimension.
# Exposes: the "midpoint collapse" bias — a neutral profile produces the least
# discriminating recommendations, and ranking is dominated by the genre match
# bonus (+2.00) rather than any continuous preference signal.
midpoint_collapse: dict = {
    "genre":            "ambient",
    "mood":             "chill",
    "energy":           0.50,
    "likes_acoustic":   True,
    "target_valence":   0.50,
    "target_tempo_bpm": 100.0,
}

# F — Niche Metal Fan  [genre with a single catalog representative]
# Only ONE song in the 20-song catalog matches "metal" (Iron Eclipse).
# After rank #1, no further genre points are available.
# Exposes: niche-genre users get one perfect match then fall off a cliff —
# the remaining 4 results are driven purely by energy/valence similarity
# and may feel stylistically wrong (e.g., EDM or k-pop filling a metal fan's list).
niche_metal_fan: dict = {
    "genre":            "metal",
    "mood":             "angry",
    "energy":           0.97,
    "likes_acoustic":   False,
    "target_valence":   0.18,
    "target_tempo_bpm": 168.0,
}

# G — Acoustic Intensity Conflict  [texture preference vs. energy preference]
# likes_acoustic=True rewards warm, organic songs (high acousticness).
# energy=0.90 rewards loud, intense songs.
# In this catalog, highly acoustic songs (acousticness > 0.70) are all
# low-energy (energy < 0.45). The scorer cannot satisfy both simultaneously.
# Exposes: energy weight (1.50) > acoustic weight (0.75), so high-energy
# low-acoustic songs win — the acoustic preference is effectively overridden.
acoustic_intensity_conflict: dict = {
    "genre":            "folk",
    "mood":             "energetic",
    "energy":           0.90,
    "likes_acoustic":   True,
    "target_valence":   0.78,
    "target_tempo_bpm": 138.0,
}

# H — Out-of-Range Tempo  [target BPM beyond catalog maximum]
# target_tempo_bpm=220 is well above the catalog maximum of 168 BPM.
# _normalize_tempo clamps the user target to 1.0 (same as 180 BPM).
# Every catalog song is at most 168 BPM → normalized ~0.90, creating a
# uniform floor gap that makes tempo a near-useless discriminator.
# Exposes: the tempo dimension provides almost zero signal when the target
# is clamped — all songs score similarly on tempo and the feature is wasted.
out_of_range_tempo: dict = {
    "genre":            "edm",
    "mood":             "euphoric",
    "energy":           0.95,
    "likes_acoustic":   False,
    "target_valence":   0.90,
    "target_tempo_bpm": 220.0,
}

EVAL_PROFILES: dict = {
    # ── Standard benchmarks ──────────────────────────────────────────────────
    "A: High-Energy Pop      ": high_energy_pop,
    "B: Chill Lofi           ": chill_lofi,
    "C: Deep Intense Rock    ": deep_intense_rock,
    # ── Adversarial edge cases ───────────────────────────────────────────────
    "D: High-Energy Sad      ": high_energy_sad,
    "E: Midpoint Collapse    ": midpoint_collapse,
    "F: Niche Metal Fan      ": niche_metal_fan,
    "G: Acoustic Conflict    ": acoustic_intensity_conflict,
    "H: Out-of-Range Tempo   ": out_of_range_tempo,
}

# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_bar(score: float, max_score: float = MAX_SCORE, width: int = BAR_WIDTH) -> str:
    """Renders an ASCII progress bar for a score value."""
    filled = round((score / max_score) * width)
    filled = max(0, min(width, filled))        # clamp to [0, width]
    bar    = "#" * filled + "." * (width - filled)
    pct    = score / max_score * 100
    return f"[{bar}] {score:.2f}/{max_score:.2f} ({pct:.1f}%)"


def _reason_prefix(reason: str) -> str:
    """Returns '+', '~', or '-' based on earned/max ratio (>=80%, >=40%, <40%)."""
    try:
        earned = float(reason.split("(+")[1].split(" /")[0])
        maxi   = float(reason.split("/ ")[1].rstrip(")"))
        ratio  = earned / maxi if maxi > 0 else 0
        if ratio >= 0.80:
            return "+"
        if ratio >= 0.40:
            return "~"
        return "-"
    except (IndexError, ValueError, ZeroDivisionError):
        return "+"


def print_profile_header(label: str, profile: UserProfile) -> None:
    """Prints the decorated header block for a UserProfile object."""
    print("=" * WIDTH)
    print(f"  PROFILE : {label.strip()}")
    print(f"  Genre   : {profile.favorite_genre:<12}  Mood    : {profile.favorite_mood}")
    print(f"  Energy  : {profile.target_energy:<12}  Valence : {profile.target_valence}")
    print(f"  Tempo   : {profile.target_tempo_bpm} BPM       Acoustic: {profile.likes_acoustic}")
    print("=" * WIDTH)


def print_dict_profile_header(label: str, prefs: dict) -> None:
    """Prints the decorated header block for a raw preference dict."""
    genre   = prefs.get("genre", "?")
    mood    = prefs.get("mood", "?")
    energy  = prefs.get("energy", "?")
    valence = prefs.get("target_valence", 0.65)
    tempo   = prefs.get("target_tempo_bpm", 100.0)
    acoustic = prefs.get("likes_acoustic", False)
    print("=" * WIDTH)
    print(f"  PROFILE : {label.strip()}")
    print(f"  Genre   : {genre:<12}  Mood    : {mood}")
    print(f"  Energy  : {energy:<12}  Valence : {valence}")
    print(f"  Tempo   : {tempo} BPM       Acoustic: {acoustic}")
    print("=" * WIDTH)


def print_recommendation(rank: int, song: dict, score: float, reasons: list) -> None:
    """Prints one recommendation as a formatted card with score bar and annotated reasons."""
    divider = "  " + "-" * (WIDTH - 4)
    print(f"  #{rank}  {song['title']}")
    print(f"      by {song['artist']}")
    print(f"      Genre: {song['genre']:<14}  Mood: {song['mood']}")
    print(divider)
    print(f"      Score:  {_score_bar(score)}")
    print(f"      Why this song?")
    for reason in reasons:
        prefix = _reason_prefix(reason)
        print(f"        {prefix}  {reason}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Differentiation snapshot
# ─────────────────────────────────────────────────────────────────────────────

def run_differentiation_test(songs_dict: list) -> None:
    """Shows how each UserProfile separates the two most contrasting catalog songs."""
    storm = next((s for s in songs_dict if s["title"] == "Storm Runner"), None)
    rain  = next((s for s in songs_dict if s["title"] == "Library Rain"), None)
    if not storm or not rain:
        return

    def to_song(d: dict) -> Song:
        """Converts a song dict to a Song dataclass instance."""
        return Song(
            id=d["id"], title=d["title"], artist=d["artist"],
            genre=d["genre"], mood=d["mood"], energy=d["energy"],
            tempo_bpm=d["tempo_bpm"], valence=d["valence"],
            danceability=d["danceability"], acousticness=d["acousticness"],
        )

    storm_song = to_song(storm)
    rain_song  = to_song(rain)

    print("=" * WIDTH)
    print("  DIFFERENTIATION SNAPSHOT")
    print("  Storm Runner (rock/intense) vs Library Rain (lofi/chill)")
    print("=" * WIDTH)
    print(f"  {'Profile':<24} {'Storm Runner':>13} {'Library Rain':>13} {'Gap':>7}")
    print(f"  {'-'*24} {'-'*13} {'-'*13} {'-'*7}")
    for label, profile in ALL_PROFILES.items():
        s = _score_song_for_user(storm_song, profile)
        r = _score_song_for_user(rain_song,  profile)
        g = abs(s - r)
        w = "<- rock" if s > r else "<- lofi"
        print(f"  {label.strip():<24} {s:>7.2f} ({s/MAX_SCORE*100:>4.1f}%)"
              f"  {r:>7.2f} ({r/MAX_SCORE*100:>4.1f}%)  {g:>5.2f} {w}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Runs all UserProfile and evaluation dict profiles, then prints a diff snapshot."""
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")
    print()

    # ── Section 1: original UserProfile taste profiles ────────────────────────
    print("#" * WIDTH)
    print("  SECTION 1 — TASTE PROFILES  (UserProfile objects)")
    print("#" * WIDTH)
    print()

    for label, profile in ALL_PROFILES.items():
        print_profile_header(label, profile)

        recs = recommend_songs(
            user_prefs={
                "genre":            profile.favorite_genre,
                "mood":             profile.favorite_mood,
                "energy":           profile.target_energy,
                "likes_acoustic":   profile.likes_acoustic,
                "target_valence":   profile.target_valence,
                "target_tempo_bpm": profile.target_tempo_bpm,
            },
            songs=songs,
            k=5,
        )

        print()
        print(f"  Top 5 Recommendations")
        print()
        for rank, (song, score, reasons) in enumerate(recs, 1):
            print_recommendation(rank, song, score, reasons)

    run_differentiation_test(songs)

    # ── Section 2: evaluation dict profiles (standard + adversarial) ──────────
    print("#" * WIDTH)
    print("  SECTION 2 — EVALUATION PROFILES  (standard + adversarial dicts)")
    print("#" * WIDTH)
    print()

    for label, prefs in EVAL_PROFILES.items():
        print_dict_profile_header(label, prefs)

        recs = recommend_songs(user_prefs=prefs, songs=songs, k=5)

        print()
        print(f"  Top 5 Recommendations")
        print()
        for rank, (song, score, reasons) in enumerate(recs, 1):
            print_recommendation(rank, song, score, reasons)


if __name__ == "__main__":
    main()
