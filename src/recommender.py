"""
Music Recommender — Finalized Algorithm Recipe
===============================================

ALGORITHM RECIPE OVERVIEW
--------------------------
The recommender is a content-based filtering system using a two-rule pipeline:

  1. SCORING RULE  — scores every song independently against one user profile
  2. RANKING RULE  — sorts scores and applies diversity penalties across the list

Three candidate weight strategies were evaluated against 20 songs and 4 profiles:

  Strategy A  (Baseline)   genre=2.0, mood=1.0, energy=1.0 (linear), no other features
  Strategy B  (v1)         mood=2.0,  genre=1.5, energy=1.5, valence=1.0, acoustic=0.75, tempo=0.5
  Strategy C  (Finalized)  genre=2.0, mood=1.5, energy=1.5, valence=1.0, acoustic=0.75, tempo=0.25

WEIGHT DECISION ANALYSIS:

  GENRE vs MOOD (the core debate):
    Common starting point suggests genre=+2.0, mood=+1.0.
    Strategy B inverted this (mood=2.0, genre=1.5) based on "listening context" logic.
    Live data test (pop/happy user, Gym Hero vs Island Sunrise):
      - All three strategies correctly prefer Gym Hero (genre+energy match)
        over Island Sunrise (mood match only)
    Conclusion: Genre=2.0 is the right anchor because genre defines the sonic
    world — tempo range, instrumentation, production style. Mood is still
    important (1.5) because wrong mood = likely skip, but it is more volatile
    than genre preference and should not outrank it.

  ENERGY (continuous Gaussian, not linear):
    Weight 1.5 with sigma=0.20 gives strong discrimination:
      Perfect match (diff=0.00): +1.500 pts
      Close match   (diff=0.10): +1.219 pts   (81% of max)
      Moderate miss (diff=0.30): +0.373 pts   (25% of max)
      Large miss    (diff=0.50): +0.027 pts   (nearly 0)
    This means a song must be within ~0.20 energy units to score competitively.

  TEMPO reduced to 0.25 (from 0.5):
    Tempo correlates strongly with energy (r~0.85 in the catalog).
    At weight 0.25 it still breaks ties between same-energy songs with
    different tempos without double-penalizing the fast/slow dimension.

FINALIZED SCORING FORMULA:
    score(song, user) =
        2.00  × genre_match(song, user)                        # long-term taste anchor
      + 1.50  × mood_match(song, user)                         # current listening context
      + 1.50  × gaussian(song.energy,      user.target_energy,    sigma=0.20)
      + 1.00  × gaussian(song.valence,     user.target_valence,   sigma=0.25)
      + 0.75  × acoustic_alignment(song.acousticness, user.likes_acoustic)
      + 0.25  × gaussian(norm(song.tempo), norm(user.tempo_bpm), sigma=0.20)
      ──────────────────────────────────────────────────────────────────────
      MAX = 7.00   (clean total — makes percentage display intuitive)

    genre_match / mood_match: binary 1.0 (exact string match) or 0.0
    gaussian(x, t, s)       : bell-curve e^(-(x-t)^2 / (2s^2)), range [0, 1]
    acoustic_alignment      : song.acousticness if likes_acoustic else 1-acousticness
    norm(bpm)               : (bpm - 60) / (180 - 60) mapped to [0, 1]

RANKING RULE (post-scoring, list-aware):
    1. Sort all (song, score) pairs descending
    2. Apply diversity penalty:
         - Artist appears > 2 times  ->  score x 0.50
         - Genre  appears > 3 times  ->  score x 0.70
    3. Re-sort after penalty and return top-k
    WHY: The Scoring Rule is stateless (sees one song at a time). The Ranking
    Rule is stateful (sees the full list) and prevents filter bubbles where the
    same artist/genre floods the top results.

GAUSSIAN vs LINEAR PROXIMITY:
    Linear:   score = 1 - |diff|              (penalizes all differences equally)
    Gaussian: score = e^(-diff^2 / (2*sigma^2)) (forgiving for small diffs, harsh for large)

    diff = 0.00  Gaussian(s=0.20) = 1.000   Linear = 1.000
    diff = 0.05  Gaussian(s=0.20) = 0.994   Linear = 0.950  <- Gaussian kinder
    diff = 0.15  Gaussian(s=0.20) = 0.754   Linear = 0.850
    diff = 0.25  Gaussian(s=0.20) = 0.458   Linear = 0.750  <- Gaussian harsher
    diff = 0.40  Gaussian(s=0.20) = 0.135   Linear = 0.600  <- punishes hard
    diff = 0.60  Gaussian(s=0.20) = 0.011   Linear = 0.400  <- nearly 0 vs still 40%
"""

import csv
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Song:
    """
    Represents a song and its content attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.

    Core fields (required — used by tests/test_recommender.py):
        favorite_genre  : categorical taste anchor
        favorite_mood   : current listening context
        target_energy   : desired intensity level  [0.0 – 1.0]
        likes_acoustic  : prefers warm/organic vs. electronic/produced

    Extended fields (optional with defaults — for richer scoring):
        target_valence      : desired emotional positivity [0.0 – 1.0]
        target_tempo_bpm    : desired physical pace in BPM
    """
    # Required by existing tests — DO NOT change order or add required fields
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

    # Extended preferences — have defaults so existing tests keep passing
    target_valence: float = 0.65       # neutral-positive default
    target_tempo_bpm: float = 100.0    # moderate pace default


# ─────────────────────────────────────────────────────────────────────────────
# Low-Level Math Primitives
# ─────────────────────────────────────────────────────────────────────────────

def _gaussian(song_val: float, target: float, sigma: float = 0.20) -> float:
    """
    Gaussian (bell-curve) proximity score.

    Returns 1.0 when song_val exactly matches target, and decays smoothly
    as the difference grows. Never returns negative values.

    Formula:  f(x) = e^( -(x - target)² / (2σ²) )

    The sigma (σ) parameter controls how "forgiving" the function is:
        σ = 0.10  →  tight match required (musical perfectionists)
        σ = 0.20  →  moderate tolerance   (default for energy / tempo)
        σ = 0.25  →  relaxed tolerance    (default for valence)
        σ = 0.30  →  wide tolerance       (genre-adjacent matching)

    WHY Gaussian over Linear (1 - |diff|)?
        Human perception of musical "fit" is not linear.
        A song 0.05 energy units off target feels nearly perfect;
        a song 0.40 units off feels completely wrong — not just "40% worse."
        The bell curve's steep tail models this perceptual cliff accurately.

    Args:
        song_val : the song's feature value
        target   : the user's preferred value for that feature
        sigma    : tolerance width (standard deviation of the bell curve)

    Returns:
        float in [0.0, 1.0]
    """
    return math.exp(-((song_val - target) ** 2) / (2.0 * sigma ** 2))


def _normalize_tempo(bpm: float, min_bpm: float = 60.0, max_bpm: float = 180.0) -> float:
    """
    Maps BPM → [0.0, 1.0] so tempo can be scored on the same scale as
    energy, valence, and acousticness (all naturally in [0, 1]).

    Formula:  normalized = (bpm − min) / (max − min)

    Using min=60, max=180 covers the full range in our dataset (60–152)
    with headroom for faster songs.
    """
    return max(0.0, min(1.0, (bpm - min_bpm) / (max_bpm - min_bpm)))


# ─────────────────────────────────────────────────────────────────────────────
# Weight Table  (see module docstring for rationale)
# ─────────────────────────────────────────────────────────────────────────────

WEIGHTS: Dict[str, float] = {
    # ── Categorical features (binary 0 or weight) ─────────────────────────
    "genre":        2.00,   # HIGHEST: long-term taste anchor — defines sonic world
    "mood":         1.50,   # current listening context — wrong mood = likely skip

    # ── Continuous features (Gaussian proximity, sigma values in scorer) ──
    "energy":       1.50,   # primary vibe axis — intensity/calmness (sigma=0.20)
    "valence":      1.00,   # emotional positivity / happiness   (sigma=0.25)

    # ── Texture & pace features ───────────────────────────────────────────
    "acousticness": 0.75,   # sonic texture: warm/organic vs. crisp/electronic
    "tempo":        0.25,   # physical pace — reduced (correlates with energy)

    # danceability intentionally omitted: strongly correlated with energy+tempo
}

MAX_SCORE: float = sum(WEIGHTS.values())   # 7.00 — clean total for % display


# ─────────────────────────────────────────────────────────────────────────────
# SCORING RULE  — applied to a SINGLE (song, user) pair
# ─────────────────────────────────────────────────────────────────────────────

def _score_song_for_user(song: Song, user: UserProfile) -> float:
    """
    SCORING RULE: How well does ONE song match ONE user profile?

    Each feature contributes a weighted partial score:

        Categorical (genre, mood):
            partial = weight × 1.0   if exact match
            partial = weight × 0.0   otherwise
            → Binary; a wrong genre/mood is a hard miss.

        Continuous via Gaussian (energy, valence, tempo):
            partial = weight × gaussian(song_val, user_target, sigma)
            → Smooth curve; nearby values score nearly as well as perfect matches.
            → Large mismatches are harshly penalized (score approaches 0).

        Directional (acousticness):
            partial = weight × song.acousticness        if user likes acoustic
            partial = weight × (1 − song.acousticness)  if user prefers produced
            → Rewards the user's textural preference without requiring a binary.

    Returns:
        float in [0.0, MAX_SCORE] where MAX_SCORE = 7.00
    """
    score = 0.0

    # ── Categorical Features ──────────────────────────────────────────────────

    # Genre: highest weight — long-term taste anchor, defines the sonic world
    if song.genre.lower() == user.favorite_genre.lower():
        score += WEIGHTS["genre"]     # +2.00 for exact match, +0.00 otherwise

    # Mood: second highest — captures the "right now" listening context
    if song.mood.lower() == user.favorite_mood.lower():
        score += WEIGHTS["mood"]      # +1.50 for exact match, +0.00 otherwise

    # ── Continuous Features (Gaussian Proximity) ──────────────────────────────

    # Energy: weight=1.50, sigma=0.20 — a 0.20-unit diff costs ~60% of the score
    #   Perfect (diff=0.00): +1.500 pts  (100%)
    #   Close   (diff=0.10): +1.219 pts  ( 81%)
    #   Moderate(diff=0.30): +0.373 pts  ( 25%)
    #   Far     (diff=0.50): +0.027 pts  (  2%) — nearly eliminated
    score += WEIGHTS["energy"] * _gaussian(song.energy, user.target_energy, sigma=0.20)

    # Valence: weight=1.00, sigma=0.25 — slightly more tolerant than energy
    # (emotional positivity has softer perceptual edges than intensity)
    score += WEIGHTS["valence"] * _gaussian(song.valence, user.target_valence, sigma=0.25)

    # Tempo: weight=0.25 (reduced from earlier 0.50 — strongly correlated with energy)
    # Normalize BPM to [0,1] first so it's on the same scale as other features
    norm_song_tempo = _normalize_tempo(song.tempo_bpm)
    norm_user_tempo = _normalize_tempo(user.target_tempo_bpm)
    score += WEIGHTS["tempo"] * _gaussian(norm_song_tempo, norm_user_tempo, sigma=0.20)

    # ── Directional Preference ────────────────────────────────────────────────

    # Acousticness: rewards warm/organic (acoustic) or crisp/electronic (produced)
    # depending on the user's binary preference flag
    acoustic_score = song.acousticness if user.likes_acoustic else (1.0 - song.acousticness)
    score += WEIGHTS["acousticness"] * acoustic_score

    return round(score, 4)


# ─────────────────────────────────────────────────────────────────────────────
# RANKING RULE  — applied to the FULL scored list
# ─────────────────────────────────────────────────────────────────────────────

def _apply_diversity_penalty(
    scored: List[Tuple[Song, float]],
    max_per_artist: int = 2,
    max_per_genre: int = 3,
) -> List[Tuple[Song, float]]:
    """
    Post-scoring diversity adjustment.

    WHY this is a separate step from scoring:
        The Scoring Rule evaluates each song in ISOLATION — it cannot know
        whether the artist or genre has already appeared in the top results.
        The Ranking Rule has access to the FULL sorted list and can enforce
        variety across the final recommendations.

        This mirrors how Spotify's "post-scoring re-ranker" works:
          1. Score every candidate independently (Scoring Rule)
          2. Re-order with diversity constraints (Ranking Rule)

    Penalty logic:
        - Each artist may appear at most `max_per_artist` times in top results.
        - Each genre may appear at most `max_per_genre` times.
        - Once a threshold is exceeded the song's score is multiplied by a
          penalty factor (not zeroed — it can still appear if truly excellent).

    Args:
        scored        : list of (song, score) sorted descending by score
        max_per_artist: how many times one artist can appear before penalty
        max_per_genre : how many times one genre can appear before penalty

    Returns:
        new list of (song, adjusted_score) — caller should re-sort after this
    """
    artist_count: Dict[str, int] = {}
    genre_count:  Dict[str, int] = {}
    adjusted: List[Tuple[Song, float]] = []

    for song, score in scored:
        artist_key = song.artist.lower()
        genre_key  = song.genre.lower()

        artist_appearances = artist_count.get(artist_key, 0)
        genre_appearances  = genre_count.get(genre_key, 0)

        # Compute penalty multiplier (stacks multiplicatively)
        penalty = 1.0
        if artist_appearances >= max_per_artist:
            penalty *= 0.50   # halve score after exceeding artist cap
        if genre_appearances >= max_per_genre:
            penalty *= 0.70   # reduce by 30% after exceeding genre cap

        adjusted.append((song, round(score * penalty, 4)))

        # Update appearance counters
        artist_count[artist_key] = artist_appearances + 1
        genre_count[genre_key]   = genre_appearances  + 1

    return adjusted


# ─────────────────────────────────────────────────────────────────────────────
# OOP Interface  (required by tests/test_recommender.py)
# ─────────────────────────────────────────────────────────────────────────────

class Recommender:
    """
    Combines the Scoring Rule and Ranking Rule into a single recommendation engine.

    Usage:
        rec = Recommender(songs)
        top5 = rec.recommend(user, k=5)
        for song in top5:
            print(rec.explain_recommendation(user, song))
    """

    def __init__(self, songs: List[Song]):
        """Stores the full song catalog that all recommendation calls will score against."""
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """
        Full pipeline: Score → Sort → Diversity-adjust → Re-sort → Top-k.

        Step 1 (Scoring Rule):  Score every song independently with _score_song_for_user
        Step 2 (Ranking Rule):  Sort descending by score
        Step 3 (Diversity):     Apply _apply_diversity_penalty to adjust repeated artist/genre
        Step 4 (Final rank):    Re-sort after penalty adjustments
        Step 5 (Slice):         Return top-k songs
        """
        # Step 1 — Scoring Rule (per-song, stateless)
        scored: List[Tuple[Song, float]] = [
            (song, _score_song_for_user(song, user)) for song in self.songs
        ]

        # Step 2 — Sort descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Step 3 & 4 — Ranking Rule (list-aware, re-sort after diversity penalty)
        scored = _apply_diversity_penalty(scored)
        scored.sort(key=lambda x: x[1], reverse=True)

        # Step 5 — Slice top-k
        return [song for song, _ in scored[:k]]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """
        Returns a human-readable explanation of why a song was recommended,
        mirroring each weighted component of the Scoring Rule.
        """
        reasons: List[str] = []

        # Categorical match reasons
        if song.mood.lower() == user.favorite_mood.lower():
            reasons.append(f"matches your current mood ({song.mood})")

        if song.genre.lower() == user.favorite_genre.lower():
            reasons.append(f"fits your favorite genre ({song.genre})")

        # Energy proximity reason
        energy_sim = _gaussian(song.energy, user.target_energy, sigma=0.20)
        if energy_sim >= 0.75:
            reasons.append(
                f"energy level ({song.energy:.2f}) is close to your target ({user.target_energy:.2f})"
            )
        elif energy_sim < 0.30:
            reasons.append(
                f"energy ({song.energy:.2f}) differs from your target ({user.target_energy:.2f})"
            )

        # Valence reason
        valence_sim = _gaussian(song.valence, user.target_valence, sigma=0.25)
        if valence_sim >= 0.80:
            if song.valence >= 0.70:
                reasons.append(f"has the uplifting, positive vibe you enjoy (valence: {song.valence:.2f})")
            else:
                reasons.append(f"matches your preferred emotional tone (valence: {song.valence:.2f})")

        # Acoustic texture reason
        if user.likes_acoustic and song.acousticness >= 0.60:
            reasons.append(f"has the warm, acoustic texture you prefer (acousticness: {song.acousticness:.2f})")
        elif not user.likes_acoustic and song.acousticness <= 0.30:
            reasons.append(f"has the crisp, electronic sound you like (acousticness: {song.acousticness:.2f})")

        if not reasons:
            reasons.append("it broadens your taste based on listener patterns similar to yours")

        score = _score_song_for_user(song, user)
        pct   = round((score / MAX_SCORE) * 100, 1)
        return (
            f'"{song.title}" by {song.artist} — '
            f'{"; ".join(reasons)}. '
            f'(Score: {score:.2f} / {MAX_SCORE:.2f} = {pct}%)'
        )


# ─────────────────────────────────────────────────────────────────────────────
# Functional Interface  (required by src/main.py)
# ─────────────────────────────────────────────────────────────────────────────

def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file into a list of dictionaries.
    Required by src/main.py
    """
    print(f"Loading songs from {csv_path}...")
    songs: List[Dict] = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                songs.append({
                    "id":           int(row["id"]),
                    "title":        row["title"],
                    "artist":       row["artist"],
                    "genre":        row["genre"],
                    "mood":         row["mood"],
                    "energy":       float(row["energy"]),
                    "tempo_bpm":    float(row["tempo_bpm"]),
                    "valence":      float(row["valence"]),
                    "danceability": float(row["danceability"]),
                    "acousticness": float(row["acousticness"]),
                })
    except FileNotFoundError:
        print(f"Error: '{csv_path}' not found. Returning empty song list.")
    return songs


def _score_dict_song(song: Dict, user_prefs: Dict) -> float:
    """
    Functional version of the Scoring Rule for dict-based songs.

    user_prefs keys:
        genre           (str,   required)
        mood            (str,   required)
        energy          (float, required)
        likes_acoustic  (bool,  optional, default False)
        target_valence  (float, optional, default 0.65)
        target_tempo_bpm(float, optional, default 100.0)
    """
    target_genre     = user_prefs.get("genre", "").lower()
    target_mood      = user_prefs.get("mood", "").lower()
    target_energy    = float(user_prefs.get("energy", 0.5))
    likes_acoustic   = bool(user_prefs.get("likes_acoustic", False))
    target_valence   = float(user_prefs.get("target_valence", 0.65))
    target_tempo_bpm = float(user_prefs.get("target_tempo_bpm", 100.0))

    score = 0.0

    # Categorical
    if song.get("mood", "").lower() == target_mood:
        score += WEIGHTS["mood"]
    if song.get("genre", "").lower() == target_genre:
        score += WEIGHTS["genre"]

    # Gaussian proximity
    score += WEIGHTS["energy"]  * _gaussian(float(song.get("energy", 0.5)), target_energy, 0.20)
    score += WEIGHTS["valence"] * _gaussian(float(song.get("valence", 0.5)), target_valence, 0.25)

    norm_song  = _normalize_tempo(float(song.get("tempo_bpm", 100.0)))
    norm_user  = _normalize_tempo(target_tempo_bpm)
    score += WEIGHTS["tempo"] * _gaussian(norm_song, norm_user, 0.20)

    # Directional
    acousticness = float(song.get("acousticness", 0.5))
    acoustic_score = acousticness if likes_acoustic else (1.0 - acousticness)
    score += WEIGHTS["acousticness"] * acoustic_score

    return round(score, 4)


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """
    PUBLIC SCORING FUNCTION — the heart of the recommendation engine.

    Implements the finalized Algorithm Recipe from Phase 2.
    Scores ONE song against ONE user preference profile and returns
    both the numeric total AND a human-readable reasons list so every
    recommendation can explain itself.

    Algorithm Recipe (weights sum to MAX_SCORE = 7.00):
    ┌─────────────────────┬────────┬──────────────────────────────────────────┐
    │ Feature             │ Weight │ Rule                                     │
    ├─────────────────────┼────────┼──────────────────────────────────────────┤
    │ genre               │  2.00  │ +2.00 if exact string match, else +0.00  │
    │ mood                │  1.50  │ +1.50 if exact string match, else +0.00  │
    │ energy  (σ=0.20)    │  1.50  │ 1.50 × Gaussian(song.energy, target)     │
    │ valence (σ=0.25)    │  1.00  │ 1.00 × Gaussian(song.valence, target)    │
    │ acousticness        │  0.75  │ 0.75 × song.acousticness  if likes_acou  │
    │                     │        │ 0.75 × (1−acousticness)   if not         │
    │ tempo   (σ=0.20)    │  0.25  │ 0.25 × Gaussian(norm_bpm,  target_norm)  │
    └─────────────────────┴────────┴──────────────────────────────────────────┘

    Gaussian formula: G(x, t, σ) = e^(-(x-t)² / 2σ²)
      Returns 1.0 for a perfect match and decays steeply for large differences.
      A 0.40-unit energy miss scores only ~9% of the maximum energy points.

    Args:
        user_prefs : dict with keys — genre, mood, energy (required);
                     likes_acoustic, target_valence, target_tempo_bpm (optional)
        song       : dict loaded from songs.csv via load_songs()

    Returns:
        (score, reasons)
        score   — float in [0.0, MAX_SCORE], rounded to 4 decimal places
        reasons — list of strings, one entry per feature that contributed points,
                  each formatted as  "feature: detail (+X.XX pts)"
                  e.g. ["genre match (+2.00)", "energy: 0.82~0.80 (+1.48)"]
    """
    # ── Unpack user preferences (with safe defaults) ──────────────────────────
    target_genre     = user_prefs.get("genre", "").lower()
    target_mood      = user_prefs.get("mood", "").lower()
    target_energy    = float(user_prefs.get("energy", 0.5))
    likes_acoustic   = bool(user_prefs.get("likes_acoustic", False))
    target_valence   = float(user_prefs.get("target_valence", 0.65))
    target_tempo_bpm = float(user_prefs.get("target_tempo_bpm", 100.0))

    total_score: float    = 0.0
    reasons:     List[str] = []

    # ── 1. Genre match  (+2.00 or +0.00) ─────────────────────────────────────
    if song.get("genre", "").lower() == target_genre:
        pts = WEIGHTS["genre"]          # 2.00
        total_score += pts
        reasons.append(f"genre match: '{song['genre']}' (+{pts:.2f})")

    # ── 2. Mood match  (+1.50 or +0.00) ──────────────────────────────────────
    if song.get("mood", "").lower() == target_mood:
        pts = WEIGHTS["mood"]           # 1.50
        total_score += pts
        reasons.append(f"mood match: '{song['mood']}' (+{pts:.2f})")

    # ── 3. Energy proximity  Gaussian(σ=0.20) × 1.50 ─────────────────────────
    song_energy = float(song.get("energy", 0.5))
    energy_sim  = _gaussian(song_energy, target_energy, sigma=0.20)
    energy_pts  = round(WEIGHTS["energy"] * energy_sim, 4)
    total_score += energy_pts
    reasons.append(
        f"energy: {song_energy:.2f} ~ target {target_energy:.2f} "
        f"(+{energy_pts:.2f} / {WEIGHTS['energy']:.2f})"
    )

    # ── 4. Valence proximity  Gaussian(σ=0.25) × 1.00 ────────────────────────
    song_valence = float(song.get("valence", 0.5))
    valence_sim  = _gaussian(song_valence, target_valence, sigma=0.25)
    valence_pts  = round(WEIGHTS["valence"] * valence_sim, 4)
    total_score += valence_pts
    reasons.append(
        f"valence: {song_valence:.2f} ~ target {target_valence:.2f} "
        f"(+{valence_pts:.2f} / {WEIGHTS['valence']:.2f})"
    )

    # ── 5. Acousticness preference  (directional) × 0.75 ─────────────────────
    song_acoustic  = float(song.get("acousticness", 0.5))
    acoustic_align = song_acoustic if likes_acoustic else (1.0 - song_acoustic)
    acoustic_pts   = round(WEIGHTS["acousticness"] * acoustic_align, 4)
    total_score   += acoustic_pts
    texture_label  = "acoustic" if likes_acoustic else "produced"
    reasons.append(
        f"{texture_label} texture: {song_acoustic:.2f} "
        f"(+{acoustic_pts:.2f} / {WEIGHTS['acousticness']:.2f})"
    )

    # ── 6. Tempo proximity  Gaussian(σ=0.20) × 0.25 ──────────────────────────
    song_bpm   = float(song.get("tempo_bpm", 100.0))
    norm_song  = _normalize_tempo(song_bpm)
    norm_user  = _normalize_tempo(target_tempo_bpm)
    tempo_sim  = _gaussian(norm_song, norm_user, sigma=0.20)
    tempo_pts  = round(WEIGHTS["tempo"] * tempo_sim, 4)
    total_score += tempo_pts
    reasons.append(
        f"tempo: {song_bpm:.0f} BPM ~ target {target_tempo_bpm:.0f} BPM "
        f"(+{tempo_pts:.2f} / {WEIGHTS['tempo']:.2f})"
    )

    return round(total_score, 4), reasons


def _explain_dict_song(song: Dict, user_prefs: Dict, score: float) -> str:
    """
    Builds a compact one-line explanation string from score_song's reasons list.
    Used internally by recommend_songs for the explanation field in its output tuples.
    """
    _, reasons = score_song(user_prefs, song)

    # Only surface reasons that are meaningful matches (exclude near-zero contributions)
    highlights: List[str] = []
    for r in reasons:
        if "genre match" in r or "mood match" in r:
            highlights.append(r)
        elif "(+" in r:
            # Extract points earned vs max for continuous features
            try:
                pts_str  = r.split("(+")[1].split(" /")[0]
                max_str  = r.split("/ ")[1].rstrip(")")
                pts_val  = float(pts_str)
                max_val  = float(max_str)
                if max_val > 0 and (pts_val / max_val) >= 0.50:   # at least 50% of max
                    highlights.append(r)
            except (IndexError, ValueError):
                highlights.append(r)

    if not highlights:
        highlights = [reasons[0]] if reasons else ["no strong feature match"]

    pct = round((score / MAX_SCORE) * 100, 1)
    return f"{' | '.join(highlights)}  [{score:.2f}/{MAX_SCORE:.2f} = {pct}%]"


def recommend_songs(
    user_prefs: Dict, songs: List[Dict], k: int = 5
) -> List[Tuple[Dict, float, List[str]]]:
    """
    Rank every song in the catalog using score_song as the judge, then
    return the top-k results sorted from highest score to lowest.

    ── HOW THE RANKING LOOP WORKS ──────────────────────────────────────────
    The core idea is simple: treat score_song as a "judge" and call it once
    for every song in the catalog.  Each call returns (score, reasons).
    We collect all (song, score, reasons) triples, sort by score descending,
    and slice the top k.

    Written Pythonically this is a single list comprehension + sorted():

        scored = sorted(
            [(*score_song(user_prefs, s), s) for s in songs],
            key=lambda item: item[0],
            reverse=True,
        )

    The comprehension unpacks score_song's two return values with the *
    splat operator so each element becomes (score, reasons, song_dict).

    ── .sort() vs sorted() — what is the difference? ───────────────────────

    list.sort()                        sorted(iterable)
    ─────────────────────────────────  ──────────────────────────────────────
    Mutates the list IN PLACE          Returns a BRAND NEW sorted list
    Returns None                       Leaves the original list unchanged
    Only works on list objects         Works on any iterable (tuple, dict…)
    Slightly faster (no copy)          Safer when original order must survive
    songs.sort(key=…)  ← changes       sorted(songs, key=…)  ← non-destructive
    songs itself                       produces a new object

    WHY we use sorted() here:
      - `songs` is the caller's list; mutating it would be a surprising
        side-effect that breaks repeated calls with different k values.
      - sorted() creates a fresh ranked list every time, which is the
        expected behaviour for a pure function.
      - The performance difference is negligible for a 20-song catalog.

    ── STEP-BY-STEP ────────────────────────────────────────────────────────

    Step 1  List comprehension — score every song
            Calls score_song(user_prefs, song) for each of the 20 songs.
            Each call returns (score: float, reasons: List[str]).
            The * splat unpacks those two values so we get a flat 3-tuple:
              (score, reasons, song_dict)

    Step 2  sorted() — rank the full catalog
            key=lambda item: item[0]  →  sort by the score (first element)
            reverse=True              →  highest score first (descending)
            Result: a new list of (score, reasons, song_dict) triples,
            ordered from best match to worst.

    Step 3  Slice [:k] — keep only the top-k results
            Python list slicing is safe even if k > len(scored): it just
            returns everything available, so no IndexError can occur.

    Step 4  Re-pack into the public return shape
            Callers expect (song_dict, score, reasons) so we swap the order
            from the internal (score, reasons, song) back to
            (song, score, reasons) for a cleaner public API.

    Args:
        user_prefs : user preference dict (see score_song for key names)
        songs      : full catalog from load_songs()
        k          : number of recommendations to return (default 5)

    Returns:
        List of (song_dict, score, reasons) tuples, best match first.
        song_dict — the raw dict from load_songs()
        score     — float total from score_song(), range [0.0, MAX_SCORE]
        reasons   — List[str] from score_song(), one line per scored feature
    """
    # ── Step 1 & 2: score every song then sort by score descending ────────
    # sorted() is used (not .sort()) so the original `songs` list is never
    # mutated — same input list can be safely reused across multiple calls.
    scored: List[Tuple[float, List[str], Dict]] = sorted(
        [(*score_song(user_prefs, song), song) for song in songs],
        key=lambda item: item[0],   # sort key  = score (index 0)
        reverse=True,               # direction = highest first
    )

    # ── Step 3 & 4: slice top-k and repack into public (song, score, reasons) ──
    return [
        (song, score, reasons)          # public shape: song first
        for score, reasons, song        # internal shape from comprehension above
        in scored[:k]                   # [:k] is safe even when k > len(scored)
    ]
