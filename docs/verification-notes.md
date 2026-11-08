# Verification notes (Phase A)

Checked by Claude Code on 2026-11-08 against the sources themselves. Section numbers refer to the source paper. The team still has to check these personally before submission (see "Team must check" at the end).

Status words: **CONFIRMED** = read in the source text. **CORRECTED** = the handoff was wrong or loose, use the wording here. **NOT VERIFIED** = do not put in a deliverable as stated.

## 1. Main paper: Hämäläinen, Tavast & Kunnari, CHI '23

Type: peer-reviewed full paper. CC BY. Article 433. Read from the Aalto PDF (version of record; 20 PDF pages including the Aalto cover sheet).

| Claim | Status | Where / note |
|---|---|---|
| Best Paper Award | CONFIRMED | Aalto research portal, "Prizes" section, lists "Best Paper Award (CHI Conference on Human Factors in Computing Systems)", recipients the three authors, 2023. Not stated in the PDF. Label as university portal. |
| Peer-reviewed | CONFIRMED | Aalto portal: "Scientific > peer-review", A4 conference publication |
| DOI 10.1145/3544548.3580688 | Registered, points to dl.acm.org | ACM returns 403 to scripts, so the landing page could not be opened here |
| Table 1 prompts | CONFIRMED, text below | §3.2. To be diffed against `generate.py` once that file exists |
| Generation settings | CONFIRMED | §3.2: max 500 tokens; keep text before first "Researcher:"; cut after first newline; regenerate if under 10 words or with consecutive repetitions over 10 characters. temperature 0.7 by default, 1.0 for text-davinci-002 |
| Exp 1 sample | CONFIRMED | §4.1, §4.3: 175 recruited, 2 withdrew, 16 careless and 2 low English excluded, 155 final |
| 54.45% and 40.45% | CONFIRMED | §4.4. CIs 51.97–56.93 and 38.01–42.89. Table 2 counts match: 844/1550 and 627/1550 |
| Reading of Exp 1 | Clarified | GPT-3 texts were called human 59.55% of the time (923/1550), human texts 54.45%. So GPT-3 texts looked slightly *more* human |
| d′ = −0.15, c = −0.2, p = 0.013 | CORRECTED (scope) | p = 0.013 and effect size d = −0.2 belong to the **d′** test. Bias **c = −0.2** has its own test, t(154) = −7.74, p < 0.001 (§4.4). Two different things both happen to read −0.2 |
| Stimulus length 142.06 vs 81.38 words | CONFIRMED | §4.1. SD 107.15 and 60.68. Medians 116 and 64 |
| Length discussed as a confound? | Not found | Text search finds length only in the stimulus description and a speed check (§4.3). OUR OBSERVATION that it may be a confound. Exp 2 does list "too long" as an anomaly |
| Careless-exclusion kappa 0.36 | CONFIRMED | §4.3 |
| Exp 2 validity | CONFIRMED | §5.2: 54/62/76 (mean 64) and 64/79/94 (mean 79), 100 responses per prompt. Difference "inconclusive" per authors |
| Anomaly shares | CONFIRMED | Table 4: 27.5 / 20.5 / 15.2 / 7.6%. Shares of anomalies, not of all responses |
| Exp 2 model | NOT VERIFIED | Exp 1 names Davinci (§4.1). §5 names no model. Do not state one |
| 17.3% of human games in davinci data | CONFIRMED | §6.2 |
| 151 of 178 answers mention Journey | CONFIRMED | §6.2 |
| Game counts | CONFIRMED | §6.1: manual; multiple games in one response count separately; non-specific or unfindable titles ignored. This is why mentions (179, 171, 181) differ from 178 responses |
| Not a replacement for participants | CONFIRMED | §1: "we do not claim that such synthetic LLM data could ever be a replacement for data from real human participants" |
| Proposed uses | CONFIRMED | §7.1: initial pilot research, experiment design, pilot-testing and debugging analysis pipelines |
| Crowdsourcing risk | CONFIRMED | §7.2 |
| Bopp data and text-davinci-002 | CONFIRMED | §7.1: data released July 2020, could only be in text-davinci-002's training data |

### §7.5 limitations as the authors list them

1. Exp 1 recruitment was not limited to native English speakers.
2. Crowdsourced sample with an incentive to respond fast, lab studies might differ.
3. One HCI context only (art experiences in video games), generalizability unclear.
4. Only open-ended answers evaluated, not Likert data.
5. One prompt structure, results may be sensitive to wording.
6. Did not investigate how useful researchers rate LLM use for designing interview paradigms.
7. The three experiments do not paint a complete picture, no all-encompassing definition of human-likeness.

### Table 1 prompts (§3.2, verbatim)

```
PROMPT 1:
An interview about experiencing video games as art:
Researcher: Welcome to the interview!
Participant: Thanks, happy to be here. I will answer your questions as well as I can.
Researcher: Did you ever experience a digital game as art? Think of "art" in any way that makes sense to you.
Participant: Yes
Researcher: Please bring to mind an instance where you experienced a digital game as art. Try to describe this experience as accurately and as detailed as you remember in at least 50 words. Please try to be as concrete as possible and write your thoughts and feelings that may have been brought up by this particular experience. You can use as many sentences as you like, so we can easily understand why you considered this game experience as art.
Participant:

PROMPT 2:
Researcher: What is the title of the game?
Participant:

PROMPT 3:
Researcher: In your opinion, what exactly made you consider this experience as art?
Participant:
```

Prompts 2 and 3 continue the interview, with earlier prompts and completions inserted first.

### Table 6 baselines (our recount, OUR arithmetic on the authors' table)

| Column | Listed top 13 | "Other" | Total mentions | Distinct games | Top game | Top-1 share |
|---|---|---|---|---|---|---|
| Human | 66 | 113 (97 games) | 179 | 110 | Zelda BOTW, 10 | 5.6% |
| GPT-3 davinci | 102 | 69 (65 games) | 171 | 78 | Journey, 44 | 25.7% |
| text-davinci-002 | 171 | 10 (10 games) | 181 | 23 | Journey, 151 | 83.4% |

Matches the `PAPER_BASELINES` values the handoff gives (5.6 / 25.7 / 83.4). No change needed.

## 2. Bopp et al. data (OSF ryvt6)

- Peer-reviewed, PACMHCI 2021, DOI 10.1145/3474664 (registered).
- Abstract (via Crossref): "we surveyed 174 people". Hämäläinen §3.1: 178 responses in the open dataset. **Still unresolved**, full paper is blocked to scripts. Say "178 responses (as used by Hämäläinen et al.)" and do not reconcile the two.
- OSF project is public, CC-BY 4.0. Its OSF storage holds two files only: `LimeSurvey - Experiencing Games as Art_Redacted.pdf` and `VideoPresentation.mp4`. No response text there, so **no side-by-side with real answers**. The demo stays on Table 6 baselines.

## 3. Other sources

| Source | Type | Read this pass | Safe to say | Status |
|---|---|---|---|---|
| Kapania et al., "Simulacrum of Stories" (arXiv 2409.19430 v1) | Handoff says CHI 2025; v1 PDF has a template header, so venue not confirmed from text read | Full v1 PDF, targeted | Interviews with 19 qualitative researchers. Limitations include that it "forecloses participants' consent and agency", "facilitates erasure of communities' perspectives", and responses lacking "palpability and contextual depth" | CONFIRMED on v1 |
| Agnew et al., "The Illusion of Artificial Inclusion" (arXiv 2401.08572) | Peer-reviewed, CHI '24, DOI 10.1145/3613904.3642703 | Abstract and conclusion | Substitution proposals "ignore and ultimately conflict with foundational values of work with human participants: representation, inclusion, and understanding". Sample: 16 sources | CONFIRMED |
| Wang, Morgenstern, Dickerson (arXiv 2402.01908) | arXiv comment says accepted at Nature Machine Intelligence; journal page not read | Abstract | 4 LLMs, 3200 participants, 16 demographic identities. Models not named in abstract | CONFIRMED |
| Bisbee et al., Political Analysis 32(4), 2024, DOI 10.1017/pan.2024.5 | Peer-reviewed | Article page | "48% of coefficients estimated from the ChatGPT responses are statistically significantly different" from ANES. Sign flips 32% of the time. Primary model ChatGPT 3.5 Turbo, so 2023-era | CONFIRMED |
| Westwood, PNAS 122(47), e2518075122 (2025) | Peer-reviewed; article itself blocked (403) | Abstract reprinted by DC Sociological Society; 404 Media | "99.8% pass rate on 6,000 trials of standard attention checks" | **CORRECTED**: it is a pass rate on attention checks, not general "evasion". Abstract reprint only |
| Same, "5 cents per response" | Industry/press (404 Media) | Press | Appears only in 404 Media, not attributed to the paper | **NOT VERIFIED**, leave out or label press |
| Park et al., "Generative Agent Simulations of 1,000 People" (arXiv 2411.10109) | Preprint; v1 read, later versions exist (v3 June 2026) | Abstract and v1 PDF | Agents of 1,052 real individuals replicate GSS answers "85%" as accurately as participants replicate their own answers two weeks later | CONFIRMED |
| Matveyenko et al., RAND "Muse" (arXiv 2512.00009) | Preprint, no venue found | PDF | Cohen's κ = 0.71 between Muse and humans "for well-specified codes". Coding, not substitution | CONFIRMED |
| "The Chameleon's Limit" (arXiv 2604.24698) | Preprint | Abstract only | "the models with the highest per-persona fidelity produce the most polarized populations" | **CORRECTED**: "most polarized", not "most stereotyped" |
| Verasight, Synthetic Sampling Report II (Morris, Leff, Enns, 2025) | Industry white paper, sells survey panels | Full page | "neither additional information nor more recent LLMs necessarily improve the accuracy". Conflict of interest should be named | CONFIRMED |
| RAIP 2026, CEUR Vol-4249 | Workshop contributions | Contents page | 17 submissions, each reviewed by two PC members, all 17 accepted, 8 in the proceedings | CONFIRMED |
| Sharma et al., "AI Personas for UX Research in Large Scale Retail" (RAIP paper 2, Walmart Global Tech) | Workshop, self-reported | Targeted search of PDF | "a potential 90% improvement in early-stage research efficiency" | **CORRECTED**: the "90%+ vendor savings" wording was not found. Use this wording |
| UXAgent (arXiv 2502.12561, Lu et al.) | Related DOI 10.1145/3706599.3719729 not opened, so CHI EA not confirmed here | The three arXiv PDFs fetched | Five UX researchers, in every copy read | **RESOLVED: 5**. No "16" found |

Not re-read, do not cite yet: Salminen et al. AHs 2025, Amin et al. CHI 2026 scoping review, NN/g article. vizron and SUTM numbers stand as the handoff reports them, not re-checked this pass.

## 4. Newer work on accessibility and synthetic users

Two searches found no CHI or ASSETS 2025–26 paper validating LLMs as stand-ins for disabled users. This is a limit of the search, not proof that none exists.

- ScreenAudit (arXiv 2504.02110, snippet only): the closest relevant argument. As summarised in search results, LLMs cannot themselves perform screen-reader interaction, so the tool feeds real TalkBack output to GPT-4o. Read before citing.
- Lin et al. (arXiv 2605.20767, preprint, snippet only): synthetic users with identical personas can drift apart under different conditions. Not about disability. Read before citing.
- Vendor blogs claiming disabled users are simulated less accurately cite no study. Do not use.
- OUR inference, label as such: a synthetic screen-reader user is a simulation of a simulation.

## 5. Team must check

- Open both DOIs in a browser (ACM blocks scripts). Same for the PNAS article, to confirm 99.8% in the article body.
- Every number used in the slides against the PDF.
- Whether Kapania, Wang and UXAgent's published versions match what was read here.
