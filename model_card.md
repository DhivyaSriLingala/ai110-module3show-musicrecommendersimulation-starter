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

### Profiles Tested

Thirteen distinct user profiles were run against the 20-song catalog, split into
two groups.

**Group 1 — Core taste profiles** (realistic everyday listeners):

| Profile | Genre | Mood | Energy | What it represents |
|---|---|---|---|---|
| Default Pop/Happy | pop | happy | 0.80 | Baseline verification — should prefer bright, upbeat pop |
| Late Night Coder | lofi | focused | 0.40 | Low-intensity background music for concentration |
| Weekend Warrior | pop | intense | 0.92 | High-energy workout or party playlist |
| Sunday Morning | folk | peaceful | 0.28 | Very quiet, organic, unhurried listening |
| Dark Commute | synthwave | moody | 0.75 | Medium-high energy with a brooding emotional tone |

**Group 2 — Evaluation and adversarial profiles** (designed to stress-test the logic):

| Profile | Purpose |
|---|---|
| A: High-Energy Pop | Genre match at near-max intensity — should behave like Default Pop/Happy but skewed faster |
| B: Chill Lofi | Genre + mood double-match at the calm extreme — expected near-perfect top result |
| C: Deep Intense Rock | Only one rock song in catalog — tests what happens after the genre pool runs out |
| D: High-Energy Melancholic | Classical genre + energy 0.92 — the catalog's only classical song has energy 0.22 |
| E: Midpoint Collapse | All continuous features set to 0.50 — tests what the system does with a neutral user |
| F: Niche Metal Fan | Metal genre with one catalog entry — tests the genre cliff |
| G: Acoustic Intensity Conflict | Likes acoustic sounds AND wants energy 0.90 — those two preferences are mutually exclusive in this catalog |
| H: Out-of-Range Tempo | Target BPM of 220, above the catalog maximum of 168 — tests normalization edge case |

### What the Results Showed

The results fell into three categories: profiles that worked as expected, profiles
that revealed a real limitation, and one result that was genuinely surprising.

**Profiles that worked as expected:**
Late Night Coder, Sunday Morning, Weekend Warrior, and Dark Commute all returned
a clear, sensible #1 result above 97% match. These profiles worked well because
the catalog happened to contain at least one song that aligned on genre, mood, energy,
and acousticness simultaneously. When every feature points in the same direction, the
scoring system functions correctly and the result feels right intuitively.

**Profiles that revealed limitations:**
The Deep Intense Rock profile (C) showed what happens when the catalog runs out of
genre-matching songs. Storm Runner ranked #1 at 94.6% — genuinely correct — but
ranks 2 through 5 were Gym Hero (pop), Iron Eclipse (metal), Neon Sunrise (EDM), and
Neon Confetti (k-pop). A rock fan would not consider three of those five suggestions
relevant. The system had no more rock songs to offer and filled the remaining slots
with the highest-scoring non-rock songs by energy and tempo similarity alone.

The Acoustic Intensity Conflict profile (G) also exposed a real ceiling: no song in
the catalog is both highly acoustic and high-energy. The two properties point in
opposite directions in every single song in the dataset. The system correctly ranked
by the stronger weight (energy > acoustic), but the result was that City Bounce
(hip-hop/energetic, acousticness=0.08) appeared first for a user who explicitly said
they prefer acoustic-sounding music. Numerically consistent; intuitively wrong.

**The most surprising result:**
Profile D — High-Energy Melancholic — produced the most counterintuitive output.
The user asked for classical music at high energy. The catalog's only classical song,
Rainy Sonata, has energy=0.22 — a 0.70-unit gap from the target of 0.92. On the
energy dimension alone, that gap is so large the Gaussian formula returns essentially
zero. Yet Rainy Sonata still ranked first at 63.9%.

Why? Because "classical" and "melancholic" matched exactly, earning 3.50 points out
of 7.00 from genre and mood alone before a single continuous feature was checked.
That 50% head-start from two label matches was enough to beat every other song despite
three features scoring near-zero. The system was not broken — it did exactly what the
weights told it to do. But a person listening to the result would hear a quiet,
slow, acoustic classical piece when they asked for loud, energetic classical music.

### The Gym Hero Question

The most consistent pattern across all thirteen profiles was Gym Hero (pop/intense)
appearing in the top 5 even for users who asked for lofi, folk, classical, or
synthwave music. See `reflection.md` for a plain-language explanation of why this
happens and what it reveals about the system.

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
