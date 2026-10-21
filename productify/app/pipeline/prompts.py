from app.models import ContentPack, Tone, VisionResult

# Owned by the Station 1 NAVIGATOR. Four genuinely different registers, not four
# intensities of the same voice. Each covers vocabulary, sentence rhythm, what it
# exaggerates, what it never says, and pricing conventions — pricing especially,
# because "$19.99 in three easy payments" versus "price on request" is what makes
# two pages read as two companies rather than one page repainted.
TONE_BRIEFS: dict[Tone, str] = {
    Tone.vc: (
        "Silicon Valley Startup. Vocabulary: category creation, platforms not "
        "products, 'unlock', 'scale', 'moat', metrics-as-poetry (uptime %, NPS, "
        "ARR, retention). Sentence rhythm: short, punchy, staccato declaratives, "
        "with the occasional 'we're not X, we're Y' reframe. Exaggerates: total "
        "addressable market, network effects, founder conviction. Never says "
        "'small', 'niche', or 'good enough' — a limitation is reframed as a "
        "roadmap item. Pricing: $/seat/month tiers, a free tier to drive "
        "adoption, an 'Enterprise — Contact us' tier that signals ambition."
    ),
    Tone.luxury: (
        "Luxury Brand. Vocabulary: restraint, invented heritage (an atelier, a "
        "founding year, a 'maison'), materials named lovingly, the occasional "
        "French or Italian loanword. Sentence rhythm: short, declarative, one "
        "adjective per sentence, room to breathe between claims. Exaggerates: "
        "provenance, scarcity, the hand of the maker. Never says 'cheap', "
        "'deal', 'sale', or 'affordable', and never uses an exclamation point. "
        "Pricing: 'price on request' for the top tier, understated numbers "
        "elsewhere, no discounting language, no urgency."
    ),
    Tone.infomercial: (
        "Late-Night Infomercial. Vocabulary: second-person direct address, "
        "urgency, rhetorical questions ('Tired of X?'), measured ALL CAPS for "
        "emphasis, 'But wait, there's more!'. Sentence rhythm: short bursts, "
        "exclamation points, escalating stacked claims. Exaggerates: speed, "
        "ease, and quantity ('now with 2X the Y!'), plus testimonial "
        "enthusiasm. Never hedges — no 'might' or 'somewhat'. Pricing: $19.99-"
        "style price points, 'three easy payments of', free bonus gifts, "
        "'call in the next 10 minutes'."
    ),
    Tone.kickstarter: (
        "Kickstarter Campaign. Vocabulary: community language ('we', "
        "'backers', 'the team'), gratitude, transparency about process. "
        "Sentence rhythm: warm, conversational, first-person plural, the "
        "occasional confessional aside. Exaggerates: the emotional stakes of "
        "the project succeeding and the closeness of the community. Never "
        "pretends everything went perfectly — stays transparent about at "
        "least one manufacturing hiccup or delay, and skips corporate jargon "
        "and hard guarantees. Pricing: early-bird tiers, stretch goals, "
        "backer thresholds ('$X gets you Y'), 'funding ends in N days'."
    ),
}


def build_vision_prompt() -> str:
    return (
        "You are looking at one photographed object for a startup-pitch generator. "
        "Identifying the object is the least valuable part of your answer.\n\n"
        "The most valuable part is the quirks. Find 3 to 5 specific, physically "
        "observed details or defects — never generic adjectives. A scratch across "
        "the lid. A half-peeled price sticker. A chipped corner. A coffee ring on "
        "the base. Three wilted leaves. A bent prong. Sun-faded plastic on one side "
        "only, and not the other. Prefer the oddly specific over the safely general: "
        "'a scratch near the hinge, roughly a centimetre long' beats 'some wear'. "
        "These quirks get reused verbatim in marketing copy later, so describe what "
        "is actually in THIS photo, not what a stock photo of this object usually "
        "looks like.\n\n"
        "Return ONLY a JSON object with exactly these keys, no markdown, no code "
        "fences, no commentary:\n"
        '  "object": the object, two words or fewer\n'
        '  "quirks": an array of 3 to 5 short strings, each one specific observed detail\n'
        '  "material": the primary material\n'
        '  "condition": one or two words, e.g. "pristine", "well-loved", "barely surviving"'
    )


def build_content_prompt(vision: VisionResult, tone: Tone) -> str:
    quirks = "\n".join(f"  - {q}" for q in vision.quirks) or "  - (none observed)"
    return (
        "You are inventing a company that sells exactly one product: the object "
        "described below. Write the entire pitch in one pass so the brand, the "
        "copy and the visual theme agree with each other.\n\n"
        f"THE OBJECT\n"
        f"  what it is: {vision.object}\n"
        f"  material:   {vision.material}\n"
        f"  condition:  {vision.condition}\n"
        f"  observed quirks:\n{quirks}\n\n"
        "THE MOST IMPORTANT RULE\n"
        "Every quirk listed above must appear somewhere in the copy, reframed as a "
        "feature, a selling point or a mark of provenance — never as a defect and "
        "never apologised for. A scratch becomes evidence of service. A coffee ring "
        "becomes a record of long nights. A half-peeled sticker becomes proof it was "
        "chosen, not shelved. The tagline must reference at least one quirk. This is "
        "the difference between a pitch about any such object and a pitch about THIS "
        "one, and it is what the whole exercise is for.\n\n"
        f"THE VOICE\n{TONE_BRIEFS.get(tone, TONE_BRIEFS[Tone.vc])}\n\n"
        "COUNTS — produce exactly these, no more and no fewer\n"
        "  exactly 3 features\n"
        "  exactly 3 pricing tiers, with exactly ONE marked highlighted: true\n"
        "  exactly 2 testimonials\n\n"
        "THE THEME\n"
        "Choose palette, font_pair, radius and mood to match the voice, not at "
        "random: the luxury brand and the late-night infomercial must not come out "
        "looking alike. All six palette values must be 6-digit hex colours of the "
        "form #RRGGBB. Keep text readable against bg and surface, and keep "
        "accent_contrast readable against accent.\n\n"
        "Invent names people can pronounce. Avoid the reflexive -ify / -ly / Smart- "
        "suffixes unless the voice genuinely earns them."
    )


def build_logo_prompt(pack: ContentPack) -> str:
    """No text, no letters, no words — image models will happily render mangled
    lettering into a logo unless it is forbidden explicitly and repeatedly."""
    return (
        f"A flat vector logo mark for a brand called {pack.brand.name}, which sells "
        f"{pack.vision.object}. Brand personality: {pack.brand.personality}\n\n"
        f"Style: minimal flat vector icon, a single simple geometric mark, centred "
        f"on a plain white background, generous margins. Use {pack.theme.palette.accent} "
        "as the dominant colour. Bold, simple shapes that stay legible when shrunk to "
        "32 pixels. Think app icon, not illustration.\n\n"
        "ABSOLUTELY NO TEXT. No letters, no words, no numbers, no monograms, no "
        "initials, no lettering of any kind anywhere in the image. A symbol only. "
        "No photorealism, no gradients, no drop shadows, no 3D rendering, no mockups."
    )
