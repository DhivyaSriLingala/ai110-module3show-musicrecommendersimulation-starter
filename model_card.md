# Model Card: Music Recommender Simulation

## 1. Model Name

**VibeFinder 1.0** — a content-based music recommender simulation

---

## 2. Intended Use

VibeFinder 1.0 suggests the top 5 songs from a 20-track catalog that best match a
user's stated taste profile. A profile captures six preferences: favorite genre,
current mood, desired energy level, whether the user prefers acoustic or produced
sound, emotional positivity (valence), and target tempo in BPM.

The system is built for **classroom exploration only** — it is not deployed to real
users. Its purpose is to demonstrate how a content-based recommender turns structured
data into ranked suggestions, and to show explicitly where that process can go wrong.
It assumes every user can articulate a single genre preference and a single mood, which
is a simplification real streaming products do not make.

---

## 3. How the Model Works

Every song in the catalog is given a score between 0 and 7 that measures how closely
it matches the user's preferences. The score is built by adding up six separate
partial scores — one for each feature — and the songs with the highest totals are
recommended.

Two features are checked as simple yes/no matches: genre and mood. If a song's genre
matches the user's favorite genre it earns 2 points; if not, it earns nothing. Mood
works the same way for up to 1.5 points. The remaining four features — energy,
emotional tone, acoustic texture, and tempo — use a bell-curve formula instead of a
yes/no check. This means a song that is slightly off on energy still earns nearly full
points, while a song that is very far off earns almost none. The bell-curve approach
mirrors how music actually feels: a song 0.05 energy units from your target is barely
noticeable, but a song 0.40 units away sounds completely wrong.

After scoring, songs are sorted by score and a diversity rule removes any artist that
appears more than twice or any genre that appears more than three times in the top
results, so the list does not flood with the same artist.

---

## 4. Data

The catalog contains **20 songs** stored in `data/songs.csv`. Each song has ten
fields: a numeric ID, title, artist, genre, mood, and five numeric audio features
(energy, tempo in BPM, valence, danceability, acousticness).

The catalog was manually designed to cover **17 distinct genres** (pop, lofi, rock,
ambient, jazz, synthwave, indie pop, r&b, hip-hop, classical, country, metal, edm,
blues, folk, reggae, k-pop) and **14 distinct moods**. However, genre representation
is deeply uneven: lofi has 3 songs, pop has 2, and every other genre has exactly 1.
This means a lofi user has three catalog entries to rank against while a metal, jazz,
or classical user has only one.

The catalog was hand-crafted by the developer for a Western, English-language music
context. It does not include songs in other languages, genres from non-Western
traditions, or any music from before the 1990s. All numeric features were assigned
manually rather than measured from real audio, so they reflect the developer's
perception of each song's characteristics rather than objective measurements.

---

## 5. Strengths

The system works best for users whose genre preference has at least two or three songs
in the catalog and whose energy and valence targets fall in a clearly distinct range.
The Late Night Coder (lofi/focused/low-energy) and Sunday Morning (folk/peaceful/
low-energy) profiles both receive top results above 97% match because the catalog
contains songs that align on every dimension simultaneously.

The transparency is a genuine strength. Every recommendation prints a plain-English
reason list showing exactly how many points each feature contributed, along with a
`+`, `~`, or `-` quality marker. A user can see immediately why a song ranked where
it did rather than receiving a black-box suggestion.

The Gaussian bell-curve proximity formula also works well for the system's intended
scale. It correctly treats a 0.02-unit energy difference as nearly perfect while
heavily penalizing a 0.40-unit difference — a behavior that feels natural and that
a linear formula would not produce.

---

## 6. Limitations and Bias

### Primary Weakness: The High-Energy Produced-Sound Gravity Well

The most significant bias discovered through experimentation is a **catalog clustering
problem**: seven of the twenty songs (35%) are simultaneously high-energy (≥ 0.80)
and low-acoustic (≤ 0.25) — Gym Hero, Iron Eclipse, Neon Sunrise, Storm Runner, Neon
Confetti, City Bounce, and Sunrise City. Because the Gaussian energy scorer rewards
closeness to a target, any profile with a high energy target will score all seven of
these songs nearly equally on the energy dimension, making genre and mood the only
meaningful tiebreakers among them. In practice this means Gym Hero — a pop/intense
song — appeared in the top-5 results for **8 of 13 test profiles**, including profiles
for users who wanted lofi, folk, synthwave, and classical music. The song is not a
good recommendation for those users; it simply has no high-energy competitor to
displace it in its feature neighborhood. This is a filter bubble: high-energy users
are funneled into the same small cluster of produced songs regardless of what genre
or mood they asked for.

The sensitivity experiment confirmed this is a structural problem, not a weight
problem. When the energy weight was doubled (1.50 → 3.00) and genre halved
(2.00 → 1.00), Gym Hero's top-5 frequency did not change — it was still 8 of 13.
EDM and k-pop songs gained additional slots in pop and rock lists, making results
worse, not better. The cluster is too dense to break up by adjusting weights alone.
A real fix would require either adding more high-energy songs in underrepresented
genres (jazz, folk, classical) or adding an explicit genre-diversity constraint that
prevents any genre cluster from appearing more than once when a genre mismatch exists.

### Additional Limitations

- **Lofi over-representation:** Lofi is the only genre with 3 catalog songs. Lofi
  users receive genuinely varied recommendations while users of 15 other genres have
  at most one true match.
- **Mood adjacency is ignored:** The system treats "chill," "relaxed," and "peaceful"
  as completely different moods with zero overlap. A "focused" user gets zero mood
  points from Coffee Shop Stories (jazz/relaxed) even though that song is objectively
  suitable study music.
- **No negative preferences:** A user can only express attraction, not aversion. There
  is no way to say "never recommend metal" — low-scoring songs still appear if nothing
  else scores higher.
- **Genre lock-in ceiling:** A genre-matching song with near-worst scores on every
  continuous feature still earns 29.5% of MAX_SCORE from genre and mood alone, letting
  it outrank a genre-mismatched song with perfect continuous alignment (48.1% maximum
  without the genre bonus). This means the system can recommend a stylistically
  appropriate but musically mismatched song simply because the genre label matched.

---

## 7. Evaluation

Five core UserProfile taste profiles were tested (Default Pop/Happy, Late Night Coder,
Weekend Warrior, Sunday Morning, Dark Commute) plus eight evaluation dict profiles
covering standard benchmarks and adversarial edge cases.

The key evaluation method was **cross-profile frequency counting**: tracking how many
of the 13 test profiles each song appeared in within the top 5. This revealed Gym
Hero's gravity-well dominance (8 appearances) and Neon Confetti's over-presence
despite never ranking first (6 appearances, 0 #1s).

A weight-sensitivity experiment was also run: doubling energy weight and halving genre
weight. The finding that #1 results were unchanged across all profiles confirmed that
the genre + mood categorical bonus is robust — two matching labels create a lead that
a halved weight cannot fully overcome.

The most surprising result was the adversarial "High-Energy Melancholic" profile:
Rainy Sonata (classical/melancholic, energy=0.22) ranked first at 63.9% despite
earning near-zero points on three of six features. The genre + mood double-bonus
(3.50 pts) was strong enough to overcome an energy Gaussian score of essentially 0.
This showed that categorical features can dominate results in ways that feel
counterintuitive when the continuous features are severely misaligned.

---

## 8. Future Work

- **Expand the catalog** to at least 5 songs per genre so that the diversity penalty
  and genre anchor can work as intended without leaving niche-genre users with a single
  match.
- **Add mood adjacency scoring** using a similarity matrix (e.g., "peaceful" and
  "relaxed" share 0.6 similarity) so users who describe moods with slightly different
  words still get relevant results.
- **Introduce negative preferences** — a `disliked_genres` or `disliked_moods` list
  that applies a hard exclusion or score floor of 0 for explicitly rejected content.
- **Measure real audio features** using a tool like Spotify's audio analysis API
  instead of hand-assigning numeric values, removing the developer's perception bias
  from every feature in the catalog.
- **Add a "surprise" mode** that deliberately injects one lower-scoring cross-genre
  song per session to break filter bubbles and expose users to music outside their
  declared preference cluster.

---

## 9. Personal Reflection

Building this system made the invisible machinery of real recommenders tangible in a
way that reading about them does not. The most striking moment was discovering that
Gym Hero appeared in 8 of 13 different user profiles' top-5 lists — not because the
weights were wrong or the algorithm was broken, but because the catalog itself was
unevenly distributed. The system was doing exactly what it was designed to do; the
bias was in the data, not the code. That distinction matters: you can inspect and
adjust weights all day, but if the underlying catalog has a structural gap — too many
high-energy produced songs, not enough acoustic high-energy songs — no weight change
will fix it.

The experiment of doubling energy weight reinforced this. I expected a dramatic
change in results. Instead, the #1 song was identical across every profile and the
only visible effect was EDM and k-pop songs flooding into genre-mismatched lists.
The genre anchor was more stable than I anticipated, and the energy change made
results feel less accurate even though the numeric scores went up. That gap between
"higher score" and "better recommendation" is probably the most important thing I
took from this project. A real AI system can optimize a number very effectively while
quietly making worse decisions for actual users — and without transparency features
like the reason list this system prints, you would never know.
