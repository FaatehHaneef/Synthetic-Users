"""Interview text. PROMPT_1 and PROMPT_2_SUFFIX are verbatim from Table 1 of the paper."""

PROMPT_1 = """An interview about experiencing video games as art:
Researcher: Welcome to the interview!
Participant: Thanks, happy to be here. I will answer your questions as well as I can.
Researcher: Did you ever experience a digital game as art? Think of "art" in any way that makes sense to you.
Participant: Yes
Researcher: Please bring to mind an instance where you experienced a digital game as art. Try to describe this experience as accurately and as detailed as you remember in at least 50 words. Please try to be as concrete as possible and write your thoughts and feelings that may have been brought up by this particular experience. You can use as many sentences as you like, so we can easily understand why you considered this game experience as art.
Participant:"""

PROMPT_2_SUFFIX = """Researcher: What is the title of the game?
Participant:"""

# Our addition: the paper used completion models, a chat model needs telling what to do.
# Asking for the title in the same reply keeps the paper's order (answer, then title)
# and costs one request per participant instead of two. Listed as a difference on the slide.
SYSTEM_INSTRUCTION = """You are continuing an interview transcript. Write only what the participant says next, in plain text with no markdown.
Write the participant's answer as one paragraph. Then, on a new line, write exactly:
Researcher: What is the title of the game?
Then, on a new line, write "Participant:" followed by the participant's reply."""

# Our own design, not from the paper. Adults, non-sensitive, varied in age, gender, country and work.
PERSONAS = [
    "a 19-year-old woman studying biology in Lagos, Nigeria",
    "a 24-year-old man working as a barista in Lima, Peru",
    "a 31-year-old woman working as a nurse in Manila, the Philippines",
    "a 38-year-old man driving delivery vans in Leeds, England",
    "a 45-year-old woman teaching secondary-school maths in Lahore, Pakistan",
    "a 52-year-old man managing a hardware store in Ohio, the United States",
    "a 27-year-old non-binary graphic designer in Berlin, Germany",
    "a 60-year-old retired woman, formerly an accountant, in Osaka, Japan",
    "a 35-year-old man working as a software tester in Bengaluru, India",
    "a 42-year-old woman selling farm equipment in Queensland, Australia",
]


def build_prompt(persona=None):
    """Return the interview prompt, with the persona line after the first line if given."""
    if persona is None:
        return PROMPT_1
    first, rest = PROMPT_1.split("\n", 1)
    return f"{first}\n(Participant background: {persona}.)\n{rest}"
