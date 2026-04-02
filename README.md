# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

This simulation is a **content-based music recommender** built in Python. It scores every
song in a 20-track catalog against a user's taste profile using a weighted formula that
considers genre, mood, energy, valence, acousticness, and tempo. Songs are ranked by score
and passed through a diversity filter so the same artist or genre cannot flood the results.
The system is transparent by design — every recommendation prints a plain-English explanation
and a percentage match so the reasoning is never hidden.

---

## How The System Works

Real-world recommenders like Spotify and YouTube combine two strategies:
**collaborative filtering** (learning from what millions of similar users enjoyed)
and **content-based filtering** (matching songs by their measurable audio attributes —
tempo, energy, mood). Production systems layer both, then apply a second
**ranking pass** to inject freshness and variety so results never feel repetitive.

This simulation focuses on **content-based filtering with a two-rule pipeline**:

1. **Scoring Rule** — scores every song independently against the user's profile
   using a weighted sum of feature similarities. Numerical features use a
   **Gaussian (bell-curve) proximity formula** instead of simple subtraction,
   which means a song 0.05 units off target still scores nearly perfectly,
   while a song 0.40 units off is penalized sharply — matching how "wrong vibe"
   actually feels.

2. **Ranking Rule** — sorts scored songs and applies a diversity penalty so the
   same artist or genre does not dominate the top results.

The system prioritizes **genre first** (your long-term sonic identity — it defines
tempo range, instrumentation and production style), then **mood** (your current
listening context), then **energy level** as the primary continuous vibe axis,
with valence, acousticness, and tempo contributing secondary texture.

### `Song` Features

| Feature | Type | Role in Scoring |
|---|---|---|
| `genre` | categorical | Taste anchor — **+2.00 pts** for exact match (highest weight) |
| `mood` | categorical | Context match — +1.50 pts for exact match |
| `energy` | float [0–1] | Intensity axis — Gaussian proximity, σ=0.20, weight 1.50 |
| `valence` | float [0–1] | Emotional positivity — Gaussian proximity, σ=0.25, weight 1.00 |
| `acousticness` | float [0–1] | Sonic texture (organic vs. produced) — directional, weight 0.75 |
| `tempo_bpm` | float (BPM) | Physical pace — normalized then Gaussian, σ=0.20, weight 0.25 |
| `danceability` | float [0–1] | Stored but not scored (correlated with energy + tempo) |
| `title`, `artist`, `id` | metadata | Used in output and diversity penalty (artist cap) |

### `UserProfile` Features

| Field | Type | Default | Purpose |
|---|---|---|---|
| `favorite_genre` | str | required | Categorical taste anchor |
| `favorite_mood` | str | required | Current listening context |
| `target_energy` | float | required | Desired intensity level |
| `likes_acoustic` | bool | required | Prefers warm/organic vs. crisp/electronic |
| `target_valence` | float | `0.65` | Desired emotional positivity |
| `target_tempo_bpm` | float | `100.0` | Desired physical pace in BPM |

### Score Formula

```
score = 2.00 × genre_match
      + 1.50 × mood_match
      + 1.50 × Gaussian(energy,      σ=0.20)
      + 1.00 × Gaussian(valence,     σ=0.25)
      + 0.75 × acoustic_alignment
      + 0.25 × Gaussian(tempo_norm,  σ=0.20)
─────────────────────────────────────────────
MAX SCORE = 7.00   (shown as % in explanations)
```

### Data Flow Diagram

The diagram below shows exactly how a single song travels from the CSV file to the
final ranked list. The **Scoring Loop** runs independently for every song; the
**Ranking Rule** runs once on the full collected results.

```mermaid
flowchart TD
    CSV[("data/songs.csv\n20 songs")]
    UP(["UserProfile\ngenre · mood · energy\nvalence · tempo · acoustic"])

    CSV --> LOAD["load_songs()\nParse CSV rows\ninto List[Dict]"]
    UP  --> LOOP

    LOAD --> LOOP

    subgraph LOOP["SCORING LOOP — runs once per song"]
        direction TB
        PICK["Pick next song\nfrom catalog"]
        GM{"Genre\nmatch?"}
        GP["+ 2.00 pts"]
        GZ["+ 0.00 pts"]
        MM{"Mood\nmatch?"}
        MP["+ 1.50 pts"]
        MZ["+ 0.00 pts"]
        EN["Gaussian(energy, σ=0.20)\n× 1.50  →  0.03 – 1.50 pts"]
        VA["Gaussian(valence, σ=0.25)\n× 1.00  →  0.00 – 1.00 pts"]
        AC["Acoustic alignment\n× 0.75  →  0.00 – 0.75 pts"]
        TE["Gaussian(tempo_norm, σ=0.20)\n× 0.25  →  0.00 – 0.25 pts"]
        SUM["song_score = sum of parts\nmax possible = 7.00"]
        STORE["Store song, score pair"]
        MORE{"More songs?"}

        PICK --> GM
        GM -->|Yes| GP --> MM
        GM -->|No | GZ --> MM
        MM -->|Yes| MP --> EN
        MM -->|No | MZ --> EN
        EN --> VA --> AC --> TE --> SUM --> STORE --> MORE
        MORE -->|Yes — next song| PICK
        MORE -->|No — all scored| DONE(["All 20 songs scored"])
    end

    subgraph RANK["RANKING RULE — runs once on full list"]
        direction TB
        SORT["Sort all song, score pairs\ndescending by score"]
        DIV["Diversity penalty\nartist appears > 2×  score × 0.50\ngenre  appears > 3×  score × 0.70"]
        RESORT["Re-sort after\npenalty adjustments"]
        TOPK["Slice top-K results"]

        SORT --> DIV --> RESORT --> TOPK
    end

    DONE --> RANK

    RANK --> OUT(["Top-K Recommendations\ntitle · artist · genre · mood\nscore  ·  % match  ·  explanation"])
```

---

### Algorithm Recipe

This is the complete set of rules the system uses to decide which songs to recommend.
Every decision below was tested against the 20-song catalog and four contrasting user
profiles before being finalized.

#### Step 1 — Load and Parse

```
songs  ← load_songs("data/songs.csv")   # returns List[Dict], 20 songs
```

Each row is cast to typed fields: `id` (int), `energy / valence / acousticness /
danceability` (float), everything else (str).  No song is filtered out at this stage —
every song in the catalog is scored.

#### Step 2 — Score Every Song (Scoring Rule)

For each song run the following weighted sum.
The result is a float between **0.00** and **7.00** (MAX SCORE):

| # | Feature | Rule | Points |
|---|---|---|---|
| 1 | **Genre** | `+2.00` if `song.genre == user.favorite_genre`, else `+0.00` | 0 – 2.00 |
| 2 | **Mood** | `+1.50` if `song.mood == user.favorite_mood`, else `+0.00` | 0 – 1.50 |
| 3 | **Energy** | `1.50 × Gaussian(song.energy, user.target_energy, σ=0.20)` | 0.03 – 1.50 |
| 4 | **Valence** | `1.00 × Gaussian(song.valence, user.target_valence, σ=0.25)` | 0.00 – 1.00 |
| 5 | **Acousticness** | `0.75 × song.acousticness` if `likes_acoustic`, else `0.75 × (1 − song.acousticness)` | 0.00 – 0.75 |
| 6 | **Tempo** | `0.25 × Gaussian(norm(song.bpm), norm(user.bpm), σ=0.20)` | 0.00 – 0.25 |

**Gaussian formula:** `G(x, t, σ) = e^(-(x-t)² / 2σ²)` — returns 1.0 for a perfect match,
decays steeply for large differences.  A song 0.40 energy units off target scores only ~9%
of the maximum energy points; the same gap with a linear formula would still give 60%.

**Why these weights?**
Three strategies were compared against live data before finalising:

| Strategy | Genre | Mood | Key difference |
|---|---|---|---|
| A — Baseline | 2.00 | 1.00 | Energy only, no valence/tempo/acoustic |
| B — v1 | 1.50 | **2.00** | Mood outranked genre |
| **C — Final** | **2.00** | **1.50** | Genre anchors taste; mood captures context |

The critical test was a `pop / happy` user choosing between *Gym Hero* (pop/intense — genre
matches, mood does not) and *Island Sunrise* (reggae/happy — mood matches, genre does not).
All three strategies ranked Gym Hero first, confirming genre is the stronger signal.
Genre defines the entire sonic world — instrumentation, production style, tempo range — and
is far more stable across time than a user's mood at any given moment.  Mood is still
weighted heavily at 1.50 because a wrong mood match is jarring and often leads to a skip;
it simply should not *outrank* the foundational genre preference.

Tempo was reduced from 0.50 to 0.25 because it correlates strongly with energy (r ≈ 0.85
in this catalog) — keeping it at full weight would double-penalise the fast/slow dimension.

#### Step 3 — Rank and Filter (Ranking Rule)

```
1. Sort all (song, score) pairs descending
2. Walk the list in order — apply penalty multipliers:
      same artist appears > 2 times  →  score × 0.50
      same genre  appears > 3 times  →  score × 0.70
      (penalties stack multiplicatively if both thresholds are crossed)
3. Re-sort after penalty adjustments
4. Return top-K songs
```

The Ranking Rule exists separately from the Scoring Rule because the Scoring Rule is
**stateless** — it evaluates each song in isolation and cannot know what other songs have
already been selected.  Without this step, a user who likes lofi could receive five lofi
tracks in a row, technically all high-scoring but practically a filter bubble.

---

### Known Biases and Limitations

These are the expected failure modes of this system, documented honestly before deployment.

#### 1. Genre lock-in (over-prioritising genre)

Genre carries the highest single weight (+2.00).  A genre match alone can push a mediocre
song above a near-perfect match in a different genre.  For example, a poor-fit pop track
(wrong mood, wrong energy) will still outscore an excellent jazz track that matches every
continuous feature — simply because "pop" matched.

> *Practical impact:* Users with niche genres (e.g. `k-pop`, `blues`) will hit a hard
> ceiling since only 1 of 20 catalog songs carries that genre label.  The system will
> recommend cross-genre songs purely on numeric similarity, with no explanation that genre
> was absent — potentially confusing the user.

#### 2. Mood is a binary hard match — no adjacency

`mood` scoring is all-or-nothing: `"chill"` does not match `"relaxed"` or `"peaceful"`
even though those three moods feel musically adjacent.  A user who types `focused` will
score zero mood points against *Coffee Shop Stories* (jazz/relaxed), even though that song
is objectively suitable study music.

> *Practical impact:* Users who describe their mood precisely may receive less relevant
> results than users whose mood label happens to match catalog vocabulary exactly.  This
> could disadvantage non-English-dominant users who describe moods with slightly different
> words.

#### 3. Small catalog amplifies all biases

With only 20 songs, a genre with a single representative (metal, blues, classical, reggae,
etc.) has no fallback.  If a metal fan gets `Iron Eclipse` removed by the diversity
penalty, the next recommendations are purely energy-driven and stylistically wrong.  Biases
that would average out over thousands of songs are glaring at catalog size 20.

#### 4. No negative preferences

The `UserProfile` can only express attraction — there is no way to say "never recommend
metal" or "I dislike country."  A user who dislikes acoustic music but sets `likes_acoustic
= False` only *reduces* the score for acoustic songs; it does not eliminate them.  A
strongly-disliked song at high energy could still appear in the top five.

#### 5. Neutral energy target loses discrimination power

A user whose `target_energy` is near 0.50 will receive near-equal Gaussian scores from
songs at energy 0.28 and energy 0.91 alike, because both are approximately equidistant from
0.50.  The system cannot distinguish "easygoing but not comatose" from "extremely intense"
for this user.  This is the **midpoint collapse** problem — the most neutral profile
produces the least useful recommendations.

#### 6. Valence defaults may silently mis-score

`target_valence` defaults to `0.65` (neutral-positive) when not explicitly set.  A user
who does not know what valence means will never override this default, so the system quietly
awards up to 1.00 bonus point to bright, upbeat songs regardless of whether the user
actually prefers that tone.  This creates a hidden positive-valence bias for any profile
that was not fully specified.

---

## Sample Output

Running `python src/main.py` from the project root produces the following output.
The **Default: Pop / Happy** profile is shown in full; the remaining four profiles
and the differentiation snapshot follow in the same format.

```
Loaded songs: 20

==================================================================
  PROFILE : Default: Pop / Happy
  Genre   : pop           Mood    : happy
  Energy  : 0.8           Valence : 0.82
  Tempo   : 118.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Sunrise City
      by Neon Echo
      Genre: pop             Mood: happy
  --------------------------------------------------------------
      Score:  [####################] 6.85/7.00 (97.9%)
      Why this song?
        +  genre match: 'pop' (+2.00)
        +  mood match: 'happy' (+1.50)
        +  energy: 0.82 ~ target 0.80 (+1.49 / 1.50)
        +  valence: 0.84 ~ target 0.82 (+1.00 / 1.00)
        +  produced texture: 0.18 (+0.61 / 0.75)
        +  tempo: 118 BPM ~ target 118 BPM (+0.25 / 0.25)

  #2  Gym Hero
      by Max Pulse
      Genre: pop             Mood: intense
  --------------------------------------------------------------
      Score:  [###############.....] 5.12/7.00 (73.1%)
      Why this song?
        +  genre match: 'pop' (+2.00)
        +  energy: 0.93 ~ target 0.80 (+1.21 / 1.50)
        +  valence: 0.77 ~ target 0.82 (+0.98 / 1.00)
        +  produced texture: 0.05 (+0.71 / 0.75)
        +  tempo: 132 BPM ~ target 118 BPM (+0.21 / 0.25)

  #3  Rooftop Lights
      by Indigo Parade
      Genre: indie pop       Mood: happy
  --------------------------------------------------------------
      Score:  [#############.......] 4.70/7.00 (67.1%)
      Why this song?
        +  mood match: 'happy' (+1.50)
        +  energy: 0.76 ~ target 0.80 (+1.47 / 1.50)
        +  valence: 0.81 ~ target 0.82 (+1.00 / 1.00)
        ~  produced texture: 0.35 (+0.49 / 0.75)
        +  tempo: 124 BPM ~ target 118 BPM (+0.24 / 0.25)

  #4  Island Sunrise
      by Coral Drift
      Genre: reggae          Mood: happy
  --------------------------------------------------------------
      Score:  [###########.........] 3.87/7.00 (55.3%)
      Why this song?
        +  mood match: 'happy' (+1.50)
        ~  energy: 0.61 ~ target 0.80 (+0.96 / 1.50)
        +  valence: 0.82 ~ target 0.82 (+1.00 / 1.00)
        ~  produced texture: 0.55 (+0.34 / 0.75)
        -  tempo: 82 BPM ~ target 118 BPM (+0.08 / 0.25)

  #5  City Bounce
      by Asphalt Kings
      Genre: hip-hop         Mood: energetic
  --------------------------------------------------------------
      Score:  [#########...........] 3.26/7.00 (46.6%)
      Why this song?
        +  energy: 0.83 ~ target 0.80 (+1.48 / 1.50)
        +  valence: 0.72 ~ target 0.82 (+0.92 / 1.00)
        +  produced texture: 0.08 (+0.69 / 0.75)
        ~  tempo: 96 BPM ~ target 118 BPM (+0.16 / 0.25)

==================================================================
  DIFFERENTIATION SNAPSHOT
  Storm Runner (rock/intense) vs Library Rain (lofi/chill)
==================================================================
  Profile                   Storm Runner  Library Rain     Gap
  ------------------------ ------------- ------------- -------
  Default: Pop / Happy        2.45 (35.0%)     0.94 (13.5%)   1.51 <- rock
  Late Night Coder            1.06 (15.1%)     5.33 (76.2%)   4.27 <- lofi
  Weekend Warrior             4.34 (62.0%)     0.91 (13.1%)   3.42 <- rock
  Sunday Morning              0.81 (11.6%)     3.26 (46.5%)   2.44 <- lofi
  Dark Commute                2.80 (40.1%)     1.22 (17.5%)   1.58 <- rock
```

**Verification notes:**

- **#1 Sunrise City** scores 97.9% — every feature is a near-perfect match (pop genre, happy mood,
  energy 0.82 vs target 0.80, low acousticness for a produced preference, exact tempo).
- **#2 Gym Hero** drops to 73.1% — pop genre matches but mood is "intense" not "happy" (+0 mood points).
- **#3 Rooftop Lights** at 67.1% — "indie pop" misses the genre match, but "happy" mood and nearly
  identical energy/valence keep it in the top 3.
- The **Differentiation Snapshot** confirms the scoring engine separates contrasting profiles cleanly:
  the Late Night Coder gap (4.27 pts) shows the system decisively prefers Library Rain over Storm Runner,
  while Weekend Warrior (3.42 pts) does the opposite — exactly the behavior a well-tuned recommender
  should produce.

---

## Evaluation & Adversarial Profiles

`src/main.py` defines **eight evaluation profiles** as raw preference dicts passed directly
to `recommend_songs()`. The first three are standard benchmarks; the last five are
**adversarial edge-case profiles** designed to expose specific weaknesses in the scoring
logic identified from codebase analysis.

### Terminal Screenshots

**Screenshot 1** — Section 1: all five UserProfile taste profiles
(Default Pop/Happy, Late Night Coder, Weekend Warrior, Sunday Morning, Dark Commute)

![Terminal output — Section 1 taste profiles](images/results-1.png)

---

**Screenshot 2** — Section 2 (first half): standard benchmarks A–C and adversarial
profiles D (High-Energy Melancholic) and E (Midpoint Collapse)

![Terminal output — evaluation profiles A through E](images/results-2.png)

---

**Screenshot 3** — Section 2 (second half): adversarial profiles F (Niche Metal Fan),
G (Acoustic Conflict), and H (Out-of-Range Tempo)

![Terminal output — adversarial profiles F through H](images/results-3.png)

---

### Standard Benchmarks

| Label | Genre | Mood | Energy | Acoustic | What it tests |
|---|---|---|---|---|---|
| A: High-Energy Pop | pop | happy | 0.92 | False | Genre match at maximum intensity |
| B: Chill Lofi | lofi | chill | 0.35 | True | Genre match at maximum calm |
| C: Deep Intense Rock | rock | intense | 0.95 | False | Genre with a single catalog entry |

### Adversarial Edge Cases

| Label | Conflict | Bias targeted |
|---|---|---|
| D: High-Energy Melancholic | Classical + energy 0.92 (catalog classical = 0.22) | Genre bonus vs energy penalty fight |
| E: Midpoint Collapse | All continuous features at 0.50 | Gaussian equidistance problem |
| F: Niche Metal Fan | Metal genre — only 1 catalog song | Single-representative genre lock-in |
| G: Acoustic Intensity Conflict | `likes_acoustic=True` + `energy=0.90` | Energy weight (1.50) overrides acoustic (0.75) |
| H: Out-of-Range Tempo | `target_tempo_bpm=220` above catalog max (168) | Normalization clamping makes tempo useless |

---

### Profile A — High-Energy Pop

```
==================================================================
  PROFILE : A: High-Energy Pop
  Genre   : pop           Mood    : happy
  Energy  : 0.92          Valence : 0.88
  Tempo   : 128.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Sunrise City
      by Neon Echo
      Genre: pop             Mood: happy
  --------------------------------------------------------------
      Score:  [###################.] 6.66/7.00 (95.1%)
      Why this song?
        +  genre match: 'pop' (+2.00)
        +  mood match: 'happy' (+1.50)
        +  energy: 0.82 ~ target 0.92 (+1.32 / 1.50)
        +  valence: 0.84 ~ target 0.88 (+0.99 / 1.00)
        +  produced texture: 0.18 (+0.61 / 0.75)
        +  tempo: 118 BPM ~ target 128 BPM (+0.23 / 0.25)

  #2  Gym Hero
      by Max Pulse
      Genre: pop             Mood: intense
  --------------------------------------------------------------
      Score:  [###############.....] 5.36/7.00 (76.6%)
      Why this song?
        +  genre match: 'pop' (+2.00)
        +  energy: 0.93 ~ target 0.92 (+1.50 / 1.50)
        +  valence: 0.77 ~ target 0.88 (+0.91 / 1.00)
        +  produced texture: 0.05 (+0.71 / 0.75)
        +  tempo: 132 BPM ~ target 128 BPM (+0.25 / 0.25)

  #3  Rooftop Lights
      by Indigo Parade
      Genre: indie pop       Mood: happy
  --------------------------------------------------------------
      Score:  [############........] 4.28/7.00 (61.2%)
      Why this song?
        +  mood match: 'happy' (+1.50)
        ~  energy: 0.76 ~ target 0.92 (+1.09 / 1.50)
        +  valence: 0.81 ~ target 0.88 (+0.96 / 1.00)
        ~  produced texture: 0.35 (+0.49 / 0.75)
        +  tempo: 124 BPM ~ target 128 BPM (+0.25 / 0.25)

  #4  Neon Sunrise
      by Pulse Architect
      Genre: edm             Mood: euphoric
  --------------------------------------------------------------
      Score:  [##########..........] 3.47/7.00 (49.6%)
      Why this song?
        +  energy: 0.94 ~ target 0.92 (+1.49 / 1.50)
        +  valence: 0.89 ~ target 0.88 (+1.00 / 1.00)
        +  produced texture: 0.03 (+0.73 / 0.75)
        +  tempo: 128 BPM ~ target 128 BPM (+0.25 / 0.25)

  #5  Neon Confetti
      by HANA
      Genre: k-pop           Mood: uplifting
  --------------------------------------------------------------
      Score:  [##########..........] 3.36/7.00 (48.0%)
      Why this song?
        +  energy: 0.88 ~ target 0.92 (+1.47 / 1.50)
        +  valence: 0.91 ~ target 0.88 (+0.99 / 1.00)
        +  produced texture: 0.12 (+0.66 / 0.75)
        +  tempo: 136 BPM ~ target 128 BPM (+0.24 / 0.25)
```

**Observation:** Sunrise City wins at 95.1% — genre + mood double-match is nearly
unbeatable even when energy is 0.10 below the target. Gym Hero at #2 earns a perfect
energy score (0.93 vs 0.92) but has no mood match, dropping it to 76.6%.

---

### Profile B — Chill Lofi

```
==================================================================
  PROFILE : B: Chill Lofi
  Genre   : lofi          Mood    : chill
  Energy  : 0.35          Valence : 0.58
  Tempo   : 75.0 BPM       Acoustic: True
==================================================================

  Top 5 Recommendations

  #1  Library Rain
      by Paper Lanterns
      Genre: lofi            Mood: chill
  --------------------------------------------------------------
      Score:  [####################] 6.89/7.00 (98.4%)
      Why this song?
        +  genre match: 'lofi' (+2.00)
        +  mood match: 'chill' (+1.50)
        +  energy: 0.35 ~ target 0.35 (+1.50 / 1.50)
        +  valence: 0.60 ~ target 0.58 (+1.00 / 1.00)
        +  acoustic texture: 0.86 (+0.65 / 0.75)
        +  tempo: 72 BPM ~ target 75 BPM (+0.25 / 0.25)

  #2  Midnight Coding
      by LoRoom
      Genre: lofi            Mood: chill
  --------------------------------------------------------------
      Score:  [###################.] 6.69/7.00 (95.5%)

  #3  Focus Flow
      by LoRoom
      Genre: lofi            Mood: focused
  --------------------------------------------------------------
      Score:  [###############.....] 5.28/7.00 (75.5%)

  #4  Spacewalk Thoughts
      by Orbit Bloom
      Genre: ambient         Mood: chill
  --------------------------------------------------------------
      Score:  [##############......] 4.77/7.00 (68.1%)
      Why this song?
        +  mood match: 'chill' (+1.50)
        +  energy: 0.28 ~ target 0.35 (+1.41 / 1.50)
        +  valence: 0.65 ~ target 0.58 (+0.96 / 1.00)
        +  acoustic texture: 0.92 (+0.69 / 0.75)
        -  tempo: 60 BPM ~ target 75 BPM (+0.21 / 0.25)

  #5  Willow Wind
      by June Farrow
      Genre: folk            Mood: peaceful
  --------------------------------------------------------------
      Score:  [#########...........] 3.26/7.00 (46.6%)
```

**Observation:** The top three are all lofi songs — two from the same artist (LoRoom).
This is exactly what the diversity penalty is designed to limit. Focus Flow (#3, LoRoom)
avoids penalty because it's only the second LoRoom appearance. The fourth slot goes to
Spacewalk Thoughts (ambient/chill) — mood match earned +1.50 pts and high acousticness
filled the texture requirement, demonstrating cross-genre fallback via continuous features.

---

### Profile C — Deep Intense Rock

```
==================================================================
  PROFILE : C: Deep Intense Rock
  Genre   : rock          Mood    : intense
  Energy  : 0.95          Valence : 0.28
  Tempo   : 155.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Storm Runner
      by Voltline
      Genre: rock            Mood: intense
  --------------------------------------------------------------
      Score:  [###################.] 6.62/7.00 (94.6%)
      Why this song?
        +  genre match: 'rock' (+2.00)
        +  mood match: 'intense' (+1.50)
        +  energy: 0.91 ~ target 0.95 (+1.47 / 1.50)
        ~  valence: 0.48 ~ target 0.28 (+0.73 / 1.00)
        +  produced texture: 0.10 (+0.68 / 0.75)
        +  tempo: 152 BPM ~ target 155 BPM (+0.25 / 0.25)

  #2  Gym Hero
      by Max Pulse
      Genre: pop             Mood: intense
  --------------------------------------------------------------
      Score:  [###########.........] 4.01/7.00 (57.3%)

  #3  Iron Eclipse
      by Voidbreaker
      Genre: metal           Mood: angry
  --------------------------------------------------------------
      Score:  [##########..........] 3.39/7.00 (48.4%)

  #4  Neon Sunrise
      by Pulse Architect
      Genre: edm             Mood: euphoric
  --------------------------------------------------------------
      Score:  [#######.............] 2.41/7.00 (34.4%)

  #5  Neon Confetti
      by HANA
      Genre: k-pop           Mood: uplifting
  --------------------------------------------------------------
      Score:  [#######.............] 2.30/7.00 (32.8%)
```

**Observation:** Storm Runner earns 94.6% — the only rock song in the catalog and it
fits almost perfectly. After rank #1 there are **no more rock songs**, so the remaining
four results are driven purely by energy and tempo similarity. Ranks 3–5 (Iron Eclipse,
EDM, k-pop) would feel stylistically wrong to a rock listener — this is the **niche
genre cliff effect** documented in Known Biases §3.

---

### Profile D — High-Energy Melancholic (Adversarial)

**Intent:** `genre=classical` + `energy=0.92`. The only classical song (Rainy Sonata)
has energy=0.22 — a 0.70-unit gap that destroys the energy score. Will genre loyalty
outweigh the severe energy penalty?

```
==================================================================
  PROFILE : D: High-Energy Sad
  Genre   : classical     Mood    : melancholic
  Energy  : 0.92          Valence : 0.20
  Tempo   : 145.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Rainy Sonata
      by Clara Voss
      Genre: classical       Mood: melancholic
  --------------------------------------------------------------
      Score:  [#############.......] 4.48/7.00 (63.9%)
      Why this song?
        +  genre match: 'classical' (+2.00)
        +  mood match: 'melancholic' (+1.50)
        -  energy: 0.22 ~ target 0.92 (+0.00 / 1.50)
        +  valence: 0.28 ~ target 0.20 (+0.95 / 1.00)
        -  produced texture: 0.97 (+0.02 / 0.75)
        -  tempo: 52 BPM ~ target 145 BPM (+0.00 / 0.25)

  #2  Iron Eclipse
      by Voidbreaker
      Genre: metal           Mood: angry
  --------------------------------------------------------------
      Score:  [##########..........] 3.33/7.00 (47.6%)
      Why this song?
        +  energy: 0.97 ~ target 0.92 (+1.45 / 1.50)
        +  valence: 0.21 ~ target 0.20 (+1.00 / 1.00)
        +  produced texture: 0.04 (+0.72 / 0.75)
        ~  tempo: 168 BPM ~ target 145 BPM (+0.16 / 0.25)

  #3  Storm Runner — 42.1%
  #4  Mississippi Slow — 35.9%
  #5  Gym Hero — 35.7%
```

**Finding:** The genre + mood double-bonus (2.00 + 1.50 = 3.50 pts) is strong enough to
push Rainy Sonata to #1 at 63.9% **even with three features scoring nearly zero** (energy,
acousticness, tempo all get `-` prefixes). Iron Eclipse (#2) has none of those genre points
but correctly matches energy and valence — it scores 47.6% on pure numeric similarity.
This confirms the documented **genre lock-in bias**: a song with 3 near-zero feature scores
still wins because of categorical bonuses.

---

### Profile E — Midpoint Collapse (Adversarial)

**Intent:** `energy=0.50`, `valence=0.50`, `tempo_bpm=100` — all continuous features at
the exact midpoint. Songs at 0.28 and 0.83 energy score nearly identically on that axis.

```
==================================================================
  PROFILE : E: Midpoint Collapse
  Genre   : ambient       Mood    : chill
  Energy  : 0.5           Valence : 0.5
  Tempo   : 100.0 BPM       Acoustic: True
==================================================================

  Top 5 Recommendations

  #1  Spacewalk Thoughts
      by Orbit Bloom
      Genre: ambient         Mood: chill
  --------------------------------------------------------------
      Score:  [#################...] 5.91/7.00 (84.4%)
      Why this song?
        +  genre match: 'ambient' (+2.00)
        +  mood match: 'chill' (+1.50)
        ~  energy: 0.28 ~ target 0.50 (+0.82 / 1.50)
        +  valence: 0.65 ~ target 0.50 (+0.84 / 1.00)
        +  acoustic texture: 0.92 (+0.69 / 0.75)
        -  tempo: 60 BPM ~ target 100 BPM (+0.06 / 0.25)

  #2  Midnight Coding — 65.0%
  #3  Library Rain — 61.8%
  #4  Dirt Road Memory — 44.6%
  #5  Focus Flow — 43.2%
```

**Finding:** Ranking collapses onto genre + mood categorical bonuses. Spacewalk Thoughts
wins at 84.4% not because it is a great energy/tempo match (energy is `~`, tempo is `-`)
but because it holds the only `ambient + chill` double-match. Ranks 2–5 are driven almost
entirely by mood match (`chill`) since energy and valence discriminate poorly at 0.50.
This confirms the **midpoint collapse** bias: a neutral user gets recommendations ordered
by genre/mood anchors only, not by actual listening preferences.

---

### Profile F — Niche Metal Fan (Adversarial)

**Intent:** Only one catalog song is `genre=metal`. After rank #1 the genre bonus is
permanently unavailable. What fills the remaining four slots?

```
==================================================================
  PROFILE : F: Niche Metal Fan
  Genre   : metal         Mood    : angry
  Energy  : 0.97          Valence : 0.18
  Tempo   : 168.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Iron Eclipse (metal/angry)   — 99.5%  [near-perfect match]
  #2  Storm Runner (rock/intense)  — 39.9%
  #3  Gym Hero (pop/intense)       — 33.2%
  #4  Neon Sunrise (edm/euphoric)  — 32.7%
  #5  Neon Confetti (k-pop)        — 30.5%
```

**Finding:** Iron Eclipse earns 99.5% — a near-perfect match on every dimension. Then the
score drops **60 percentage points** to Storm Runner at 39.9%. Ranks 3–5 include pop,
EDM, and k-pop — genres a metal fan would likely reject. The valence scores for ranks 2–5
are all `-` (e.g., Gym Hero valence 0.77 vs target 0.18 = +0.06/1.00) showing these songs
are fundamentally incompatible on emotional tone. This is the starkest demonstration of the
**niche genre cliff** — one great recommendation followed by four stylistically mismatched
fallbacks.

---

### Profile G — Acoustic Intensity Conflict (Adversarial)

**Intent:** `likes_acoustic=True` (rewards high-acousticness songs) but `energy=0.90`
(rewards high-intensity songs). In this catalog those two properties are inversely
correlated — no song is both highly acoustic AND high-energy.

```
==================================================================
  PROFILE : G: Acoustic Conflict
  Genre   : folk          Mood    : energetic
  Energy  : 0.9           Valence : 0.78
  Tempo   : 138.0 BPM       Acoustic: True
==================================================================

  Top 5 Recommendations

  #1  City Bounce (hip-hop/energetic)  — 57.1%
      acoustic texture: 0.08 (+0.06 / 0.75)   <-- acoustic preference totally lost
      energy: 0.83 ~ target 0.90 (+1.41 / 1.50) <-- energy wins

  #2  Willow Wind (folk/peaceful)      — 52.1%
      energy: 0.27 ~ target 0.90 (+0.01 / 1.50) <-- genre match saves it
      acoustic texture: 0.94 (+0.70 / 0.75)      <-- acoustic wins

  #3  Gym Hero (pop/intense)           — 39.5%
  #4  Neon Confetti (k-pop/uplifting)  — 38.6%
  #5  Sunrise City (pop/happy)         — 38.1%
```

**Finding:** The conflict is visible at ranks #1 and #2. City Bounce wins because energy
(weight 1.50) beats acoustic (weight 0.75) — it scores near-zero on acousticness (`-  0.08
(+0.06/0.75)`) but high on energy and mood. Willow Wind (#2) wins the genre bonus (+2.00
for folk) and scores perfectly on acoustic (+0.70/0.75), but its energy score is effectively
zero (+0.01/1.50). The system **cannot simultaneously satisfy both preferences** and energy
wins by weight ratio. None of the top 5 provides both high acousticness and high energy —
this was a guaranteed no-win scenario.

---

### Profile H — Out-of-Range Tempo (Adversarial)

**Intent:** `target_tempo_bpm=220` exceeds the catalog maximum of 168 BPM. The
`_normalize_tempo()` function clamps this to 1.0 (equivalent to 180 BPM), creating
a uniform floor gap since every song is at most 168 BPM → normalized ~0.90.

```
==================================================================
  PROFILE : H: Out-of-Range Tempo
  Genre   : edm           Mood    : euphoric
  Energy  : 0.95          Valence : 0.90
  Tempo   : 220.0 BPM       Acoustic: False
==================================================================

  Top 5 Recommendations

  #1  Neon Sunrise (edm/euphoric)    — 96.4%
      tempo: 128 BPM ~ target 220 BPM (+0.02 / 0.25)  <-- tempo near-useless

  #2  Neon Confetti (k-pop)          — 44.5%
      tempo: 136 BPM ~ target 220 BPM (+0.05 / 0.25)  <-- same pattern

  #3  Gym Hero (pop/intense)         — 44.5%
  #4  Sunrise City (pop/happy)       — 40.1%
  #5  City Bounce (hip-hop)          — 38.8%
      tempo: 96 BPM ~ target 220 BPM (+0.00 / 0.25)   <-- effectively zero
```

**Finding:** Every song's tempo score is `-` (near zero). The fastest catalog song (Iron
Eclipse, 168 BPM) would earn only +0.04 of a possible 0.25 pts. The tempo feature is
**completely wasted** — it contributes ~0.02 pts on average instead of ~0.25. All ranking
beyond #1 is driven by energy and valence alone. This confirms `_normalize_tempo`'s clamp
works correctly (no crash, no negative score), but reveals that out-of-range inputs silently
degrade a feature dimension to near-zero usefulness without warning the caller.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this


---

## 7. `model_card_template.md`

Combines reflection and model card framing from the Module 3 guidance. :contentReference[oaicite:2]{index=2}  

```markdown
# 🎧 Model Card - Music Recommender Simulation

## 1. Model Name

Give your recommender a name, for example:

> VibeFinder 1.0

---

## 2. Intended Use

- What is this system trying to do
- Who is it for

Example:

> This model suggests 3 to 5 songs from a small catalog based on a user's preferred genre, mood, and energy level. It is for classroom exploration only, not for real users.

---

## 3. How It Works (Short Explanation)

Describe your scoring logic in plain language.

- What features of each song does it consider
- What information about the user does it use
- How does it turn those into a number

Try to avoid code in this section, treat it like an explanation to a non programmer.

---

## 4. Data

Describe your dataset.

- How many songs are in `data/songs.csv`
- Did you add or remove any songs
- What kinds of genres or moods are represented
- Whose taste does this data mostly reflect

---

## 5. Strengths

Where does your recommender work well

You can think about:
- Situations where the top results "felt right"
- Particular user profiles it served well
- Simplicity or transparency benefits

---

## 6. Limitations and Bias

Where does your recommender struggle

Some prompts:
- Does it ignore some genres or moods
- Does it treat all users as if they have the same taste shape
- Is it biased toward high energy or one genre by default
- How could this be unfair if used in a real product

---

## 7. Evaluation

How did you check your system

Examples:
- You tried multiple user profiles and wrote down whether the results matched your expectations
- You compared your simulation to what a real app like Spotify or YouTube tends to recommend
- You wrote tests for your scoring logic

You do not need a numeric metric, but if you used one, explain what it measures.

---

## 8. Future Work

If you had more time, how would you improve this recommender

Examples:

- Add support for multiple users and "group vibe" recommendations
- Balance diversity of songs instead of always picking the closest match
- Use more features, like tempo ranges or lyric themes

---

## 9. Personal Reflection

A few sentences about what you learned:

- What surprised you about how your system behaved
- How did building this change how you think about real music recommenders
- Where do you think human judgment still matters, even if the model seems "smart"

