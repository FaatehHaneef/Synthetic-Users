# Synthetic Users

A small local app that tests whether an AI crowd is as varied as real people. It asks a current Gemini model the interview question from Hämäläinen, Tavast & Kunnari (CHI '23), then compares how varied the simulated answers are against the paper's data.

Built for the CS3014 Applied HCI Tool Talk by team E01-Insyder.

> **Simulated participants, not user evidence.** This illustrates the paper's finding. It does not reproduce the study.

## Contents

- [Results](#results)
- [Quick start](#quick-start)
- [Add your Gemini key](#add-your-gemini-key)
- [Using the app](#using-the-app)
- [Command line](#command-line)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Changing the frontend](#changing-the-frontend)
- [How this differs from the paper](#how-this-differs-from-the-paper)
- [Sources](#sources)

## Results

356 simulated interviews on `gemini-3.6-flash`, 178 per group, each one a separate request.

| Group | Game mentions | Different games | Top game | Top game share |
|---|---|---|---|---|
| Real people (paper, Table 6) | 179 | 110 | The Legend of Zelda: BOTW | 5.6% |
| GPT-3 davinci (paper) | 171 | 78 | Journey | 25.7% |
| GPT-3 text-davinci-002 (paper) | 181 | 23 | Journey | 83.4% |
| Gemini, plain prompt (our run) | 178 | 5 | Journey | 92.7% |
| Gemini, with persona (our run) | 178 | 9 | Gris | 28.7% |

Paper rows are our arithmetic on the authors' Table 6. Our rows are one model on one question.

With personas, the overall share falls, but individual personas collapse onto one game. For example, the Lahore maths teacher named Monument Valley 18 of 18 times, and the Ohio hardware store manager named Red Dead Redemption 2 18 of 18 times.

The full data is in [data/runs/gemini-main.jsonl](data/runs/gemini-main.jsonl), and the analysis output is in [results/gemini-main/](results/gemini-main/).

## Quick start

You need Python 3.11 or newer. Node is only needed if you want to change the frontend, because a built copy is included.

```bash
git clone https://github.com/FaatehHaneef/Synthetic-Users.git
cd Synthetic-Users
pip install -r requirements.txt
python server.py
```

The app opens at <http://127.0.0.1:8502>. Press Ctrl+C in the terminal to stop it.

**Saved Run works straight away with no key.** You only need a key for Live (Gemini).

## Add your Gemini key

1. Create a free API key at <https://aistudio.google.com/apikey>.
2. Copy the example file:

   ```bash
   # macOS or Linux
   cp .env.example .env

   # Windows PowerShell
   Copy-Item .env.example .env
   ```

3. Open `.env` and paste your key after the `=`, with no quotes or spaces:

   ```
   GEMINI_KEY_1=your_key_here
   ```

4. Save the file and restart `python server.py`.

`.env` is listed in `.gitignore`, so it stays on your machine. Keys are never written to logs or run files, which only record the key's number.

**Things to know**

- Free-tier limits are low and set by Google. We saw about 20 requests per day per project for this model, and 5 per minute. Daily quotas reset at midnight Pacific.
- Some Google projects are refused the free tier. If the app says "These API keys were refused by Google", check the project in AI Studio, or try a project on another account or with billing.
- You can add `GEMINI_KEY_2`, `GEMINI_KEY_3` and so on. The app uses the first key with quota left.

## Using the app

| Screen | What it does |
|---|---|
| **Landing** | Press Get started |
| **Setup** | Choose Live (Gemini) for 1, 5 or 10 fresh interviews, or Saved Run for the full 356 |
| **Working** | Shows progress. Failed calls retry automatically for up to 25 seconds |
| **Output** | Live shows interview cards. Saved Run shows the top game, with a Plain and Persona switch |
| **Inspect** | Comparison with the paper, charts, persona table, themes, exact prompt, review sheet, title cleanup and export |

Live interviews are not saved. They are for trying it out. The saved results only change if you generate a run from the command line.

## Command line

```bash
# See how many keys are loaded and their status today
python generate.py keys

# Make one real test request
python generate.py probe

# Generate a run, safe to stop and restart
python generate.py run --provider gemini --name my-run --n 178 --rpm 5

# Generate offline test data, never use this as results
python generate.py run --provider fake --name fake-test --n 20

# Analyse a run and write its CSVs, charts and summary
python analyze.py data/runs/my-run.jsonl
```

To view a different run in the app, change `RUN_NAME` in `server.py`.

## Project layout

```
server.py              Local server for the app
generate.py            Command line for generating interviews
analyze.py             Command line for analysis
synthusers/
  prompts.py           The paper's prompt, our additions and personas
  keys.py              Loading keys and moving between them
  generate.py          Gemini calls, quality rules, resumable runs
  analyze.py           Title cleaning, metrics, charts, exports
  themes.py            Simple keyword theme tagger
web/                   React frontend (built copy in web/dist)
data/runs/             Saved runs, one JSONL file per run
data/aliases.json      Title merges
results/gemini-main/   CSVs, charts, summary and human review sheet
docs/                  Verification notes against each source
tests/                 Offline tests, no network or keys needed
```

## Tests

```bash
python -m pytest tests -q
```

## Changing the frontend

```bash
cd web
npm install
npm run dev     # development server, run python server.py alongside it
npm run build   # rebuild web/dist, which server.py serves
```

## How this differs from the paper

- A current chat model instead of GPT-3 completion models.
- A short instruction so a chat model continues the transcript.
- The title is asked in the same reply as the answer, in the paper's order.
- Our own persona group and persona list. The paper's main experiments did not use personas.
- Temperature cannot be set on this model. The paper used 0.7 and 1.0.
- Baselines come from our arithmetic on Table 6, not raw data. The original dataset's OSF page has no response text.
- Titles are cleaned automatically with manual merges, and we count one title per response. The paper counted manually.
- The paper's third prompt is not used.

Each participant is a separate request. Listing many participants in one prompt would let the model see its earlier answers and vary them on purpose.

Human review: 20 sampled answers are in [the review sheet](results/gemini-main/review_sample.csv). This is an AI first pass against public sources: 16 answers marked accurate and 4 uncertain.

## Sources

- Hämäläinen, Tavast & Kunnari (2023). Evaluating Large Language Models in Generating Synthetic HCI Research Data: a Case Study. CHI '23. <https://doi.org/10.1145/3544548.3580688>
- Bopp et al. (2021). "My Soul Got a Little Bit Cleaner": Art Experience in Videogames. PACMHCI. <https://doi.org/10.1145/3474664>

Orb animation from [thinking-orbs](https://www.npmjs.com/package/thinking-orbs) (MIT). Code drafted with AI assistance.
