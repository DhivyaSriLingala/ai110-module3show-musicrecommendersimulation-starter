# Model Card: VibeFinder 1.0

---

## 1. Model Name

**VibeFinder 1.0**

A content-based music recommender simulation built in Python for classroom use.

---

## 2. Goal / Task

VibeFinder tries to answer one question: *"Given what a user likes, which songs in the catalog fit them best?"*

It does not learn from listening history. It does not know what other users liked. It just looks at the features of each song — genre, mood, energy, acoustic texture, tempo, and emotional tone — and picks the five that match the user's stated preferences most closely.

Think of it like a very attentive DJ who reads your mood card and flips through 20 records to find the closest matches.

---

## 3. Data Used

**Catalog size:** 20 songs, stored in `data/songs.csv`.

**Each song has 10 fields:**
- Metadata: id, title, artist
- Categorical: genre, mood
- Numeric (0–1 scale): energy, valence, acousticness, danceability
- Numeric (BPM): tempo

**Genre coverage:** 17 genres — pop, lofi, rock, ambient, jazz, synthwave, indie pop, r&b, hip-hop, classical, country, metal, edm, blues, folk, reggae, k-pop.

**Mood coverage:** 14 moods — happy, chill, intense, melancholic, relaxed, moody, focused, romantic, energetic, nostalgic, angry, euphoric, peaceful, uplifting.

**Big limits to know about:**
- The catalog is tiny. Most genres have exactly one song. If your genre has no match, the system guesses from energy and mood alone.
- All numeric features were assigned by hand — they reflect the developer's opinion, not measured audio data.
- No non-Western genres. No non-English music. No music from before the 1990s.
- The catalog has no songs that are both high-energy AND highly acoustic. That means some user preferences are impossible to satisfy at the same time.

---

## 4. Algorithm Summary

Every song gets a score out of 7.00. The score is built from six parts.

**The six parts:**

| Feature | Max points | How it works |
|---|---|---|
| Genre | 2.00 | Full points if the genre label matches exactly. Zero if it doesn't. |
| Mood | 1.50 | Same — full or zero, no in-between. |
| Energy | 1.50 | A bell curve. Close to your target = almost full points. Far away = almost zero. |
| Valence (happiness) | 1.00 | Same bell-curve approach. |
| Acoustic texture | 0.75 | If you like acoustic, songs with high acousticness score higher. If you prefer produced sound, it flips. |
| Tempo | 0.25 | Bell curve again, but the lowest weight because tempo already correlates with energy. |

**Why a bell curve instead of simple subtraction?**
Because a song that is 0.02 energy units off your target should feel almost perfect. A song that is 0.40 units off should feel clearly wrong. Simple subtraction treats both gaps the same way. The bell curve does not — it is forgiving for small differences and harsh for large ones.

**After scoring:**
Songs are sorted by score. A diversity rule prevents the same artist from appearing more than twice or the same genre more than three times in the final list.

---

## 5. Observed Behavior / Biases

**The biggest problem: Gym Hero keeps showing up for everyone.**

Gym Hero is a pop/intense song with very high energy (0.93) and very low acousticness (0.05). It appeared in the top 5 for 8 out of 13 completely different user profiles — including lofi fans, folk listeners, and classical music users.

Here is why in plain language: the catalog has 7 songs that are all high-energy and electronically produced (Gym Hero, Iron Eclipse, Neon Sunrise, Storm Runner, Neon Confetti, City Bounce, Sunrise City). They are all crammed into the same corner of the "map." When a user asks for high energy, all 7 score almost identically on that dimension, and Gym Hero floats to the top because its pop genre happens to overlap with nearby profiles. It is not a broken formula — it is a catalog that is too small and unevenly distributed.

Doubling the energy weight did not fix this. Gym Hero still appeared 8 times. The problem is structural, not a tuning issue.

**Other biases found:**

- **Lofi gets three songs; most genres get one.** Lofi users receive better, more varied recommendations than metal, jazz, or classical users — purely because of how the catalog was built.
- **Moods are all-or-nothing.** "Chill" and "relaxed" are treated as completely different. A focused user gets zero mood points from a jazz/relaxed song, even though that song is clearly suitable background study music.
- **No way to say "never this."** Users can only say what they want, not what they hate. A user who dislikes metal cannot exclude it — if nothing else scores higher, a metal song will still appear.
- **Genre can win even when every other feature is wrong.** A song that matches your genre but sounds nothing like what you asked for still earns 29.5% of the max score. That is sometimes enough to beat a song that fits perfectly on energy, mood, and texture but has a different genre label.

---

## 6. Evaluation Process

**How it was tested:**

13 user profiles were run against the catalog. Five were realistic everyday listeners. Eight were designed specifically to expose weaknesses.

**The five core profiles:**

| Profile | What it tested |
|---|---|
| Default Pop/Happy | Baseline — should prefer bright, upbeat pop |
| Late Night Coder | Quiet, focused, acoustic background music |
| Weekend Warrior | Maximum energy workout playlist |
| Sunday Morning | Slow, organic, peaceful folk |
| Dark Commute | Medium-high energy with a dark tone |

**The adversarial profiles were designed to "trick" the system:**

- *High-Energy Melancholic* — asked for classical music at energy 0.92. The only classical song has energy 0.22. Did the genre bonus override the energy mismatch? Yes — Rainy Sonata still ranked first at 63.9% despite scoring near-zero on three features. The genre + mood double-bonus (50% of max score) was too big to overcome.
- *Midpoint Collapse* — set all continuous preferences to exactly 0.50. The system had almost no signal to rank on and fell back to whoever had the right genre and mood label.
- *Acoustic Intensity Conflict* — wanted acoustic AND high-energy. No song in the catalog has both. City Bounce (hip-hop, acousticness=0.08) ranked first for a user who explicitly said they prefer acoustic sound. Numerically correct; practically wrong.
- *Niche Metal Fan* — only one metal song exists. Iron Eclipse scored 99.5% at #1. Then the score dropped 60 percentage points to #2. Ranks 2–5 included pop, EDM, and k-pop songs a real metal fan would likely skip.

**One experiment was run:**
Energy weight was doubled (1.50 → 3.00) and genre weight was halved (2.00 → 1.00). The #1 result was identical across all profiles — proving that genre + mood bonuses are too strong to dislodge even at half weight. The only visible effect was EDM and k-pop songs flooding into genre-mismatched lists, making recommendations worse, not better.

**What surprised me most:**
That the #1 result never changed during the weight experiment. I expected something to move. Nothing did. The genre anchor is much stickier than I thought.

---

## 7. Intended Use and Non-Intended Use

**This system IS designed for:**
- Learning how content-based recommenders work
- Exploring how small changes to weights change which songs rank first
- Understanding where bias comes from in AI recommendation systems
- Classroom or portfolio projects that need a transparent, explainable scoring system

**This system is NOT designed for:**
- Real music listeners who expect accurate recommendations
- Production use in any app or service
- Users with niche musical tastes — if your genre has one song in the catalog, results will be poor
- Personalization based on listening history — this system has no memory and learns nothing over time
- Non-Western music, non-English genres, or any musical tradition not represented in the 20-song catalog

If someone used this to actually recommend music, they would frequently receive genre-mismatched songs that score well only because their energy level happened to be close to the user's target. That is not a useful recommendation in practice.

---

## 8. Ideas for Improvement

**1. Expand the catalog — at least 5 songs per genre.**
Right now most genres have one song. After the #1 result, the system has nothing genre-appropriate to suggest. A larger catalog would let the diversity rule and genre anchor both work as intended. This is the single change that would most improve result quality.

**2. Add mood adjacency — nearby moods should earn partial credit.**
"Chill," "relaxed," and "peaceful" should not score zero against each other. A simple lookup table that gives "chill vs. relaxed" a 0.6 similarity score instead of 0.0 would immediately improve recommendations for users whose mood vocabulary differs slightly from the catalog labels.

**3. Let users say what they dislike.**
A `disliked_genres` field on the user profile would let the system hard-exclude certain songs instead of surfacing them whenever nothing better scores higher. A metal fan who also hates EDM should be able to say so.

---

## 9. Personal Reflection

### Biggest Learning Moment

The biggest thing I learned is that bias can live in the data, not just the code.

I spent time tuning weights and running experiments expecting the Gym Hero problem to shrink. It never did. Gym Hero appeared in the top 5 for 8 out of 13 completely different user profiles — not because the formula was broken, but because 7 of the 20 catalog songs happened to share the same high-energy, low-acoustic profile. They all live in the same corner of the feature map. No weight adjustment can move them apart. Only a more diverse catalog could.

That was a real shift in how I thought about the project. I kept asking "what weight is wrong?" when the actual question was "what is missing from the data?" Those are very different problems, and only one of them is solvable with a keyboard.

---

### How AI Tools Helped — and When I Had to Double-Check

AI tools were genuinely useful for the parts of this project that require pattern recognition across a lot of information at once: designing a scoring formula that balanced six features, generating a diverse 20-song catalog without accidentally making it too uniform, and identifying edge cases like the midpoint collapse or out-of-range tempo profile that I might not have thought to test on my own.

The adversarial profiles were a good example. When I asked for profiles designed to "trick" the scoring logic, the suggestions were grounded in the actual code — acoustic weight versus energy weight, what normalization does to a 220 BPM target, what happens when a genre has only one catalog entry. That kind of systematic thinking across the whole codebase at once was faster with an AI partner than doing it alone.

But I had to double-check two things specifically.

First, the suggested weights in an earlier draft of the README had mood ranked higher than genre. The intuition was "your current mood matters more than your long-term genre preference." That sounds reasonable, but when I ran the actual test — a pop/happy user choosing between Gym Hero (pop/intense) and Island Sunrise (reggae/happy) — genre-first produced the better result every time. The AI suggestion made logical sense as an argument; the data said something different. I had to run the experiment myself to know which was right.

Second, the weight-sensitivity experiment. The prediction was that doubling the energy weight would meaningfully change the rankings. It did not — the #1 result was identical across every profile. The AI analysis was correct about *what changed* (ranks 2–5 shifted toward EDM and k-pop) but initially framed this as "making results more energy-accurate." Looking at the actual output, those results were worse for users, not better. The framing needed to be corrected by reading the output with human judgment, not just accepting the summary.

The general pattern: AI tools were most reliable when generating options and identifying structure. They needed checking when making qualitative claims about whether a result was good.

---

### What Surprised Me About Simple Algorithms Feeling Like Recommendations

I was surprised by how quickly a weighted formula starts to *feel* like it understands you — even when it clearly does not.

When Focus Flow appeared first for the Late Night Coder profile at 97.6%, it genuinely felt correct. A lofi track with low energy, acoustic texture, and a focused mood — that is exactly what a late-night study session sounds like. The formula had no idea what studying feels like. It just added up six numbers and sorted them. But the output landed close enough to something a human would choose that it felt intentional.

The flip side was just as striking. The Acoustic Intensity Conflict profile asked for high-energy folk music with acoustic texture. City Bounce — a hip-hop track — ranked first. That is obviously wrong to anyone who has listened to music for five minutes. But the formula was doing exactly the right thing: energy was worth more than acoustic texture (1.50 vs 0.75), and City Bounce had the right energy. The algorithm was not confused. It was consistent. The problem was that "consistent with its rules" and "useful to the person" are not the same thing.

That gap is what real AI ethics conversations are about. A credit scoring model, a resume filter, a medical triage tool — they all have this same property. They are internally consistent. They optimize a number faithfully. And they can still produce results that feel completely wrong to the person receiving them, for reasons that are invisible without a transparency layer.

---

### What I Would Try Next

**More catalog songs — at least 5 per genre.**
This is the single change with the biggest impact. Right now a metal or classical fan gets one correct recommendation followed by four wrong ones. Five songs per genre would give the diversity filter and genre anchor room to work properly.

**Mood adjacency scoring.**
"Peaceful," "relaxed," and "chill" all mean roughly the same thing to a listener but score zero against each other in this system. A small similarity table — peaceful→relaxed: 0.7, chill→relaxed: 0.8 — would immediately produce better results for any user whose mood vocabulary differs slightly from the catalog labels. This is also closer to how Spotify actually handles mood: as a spectrum, not a binary label.

**A feedback loop.**
Right now the system has no memory. Every session starts from scratch. Even a simple thumbs-up / thumbs-down on the top result — stored in a file between runs — could let the system adjust weights over time. Did the user skip a high-energy song three times in a row? Probably reduce the energy target slightly next run. That would turn VibeFinder from a static formula into something that actually learns, which is the first step toward the kind of collaborative filtering that Spotify and YouTube use at scale.
