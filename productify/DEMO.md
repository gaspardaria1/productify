# DEMO.md — Productify, 5 minutes + questions

Owned by Station 2. Read by all four of us before the freeze.

Everything below assumes: **Station 1's laptop runs the server**, Station 2's code is
already merged onto it, and the backup gallery is pre-generated.

---

## Who speaks when

| Who | Minute | What happens |
|---|---|---|
| **S2 · navigator** | 0:00–0:45 | Takes an object from the audience, photographs it live from the phone, picks a tone |
| **S1 · driver** | 0:45–1:45 | Narrates the pipeline while it runs |
| **S2 · driver** | 1:45–2:45 | Opens the page, downloads it, kills the server, opens it from disk. Then: same object, different tone |
| **S1 · navigator** | 2:45–4:00 | Second object. Shows the quirk from the photo reappearing in the tagline |
| **all four** | 4:00–5:00 | The gallery. "These are the companies founded today." Audience votes |

Names: S1 driver ______________ · S1 navigator ______________ ·
S2 driver ______________ · S2 navigator ______________

---

## First sentences, written out

The opening is where everybody freezes, so these are scripted verbatim. After the first
sentence, talk normally.

**S2 · navigator, 0:00**
> "Can someone hand me an object? Anything at all — whatever is in your pocket."

Then, while photographing: *"I'm taking the photo, choosing a tone — let's do Silicon
Valley startup — and starting it. While it runs you can see exactly what it's doing: it
looks at the object, invents the company, designs the brand, publishes the page."*

**S1 · driver, 0:45**
> "What you're watching is three model calls chained together."

Then: *"The first is vision, and it isn't just identifying the object — it's hunting for its
flaws, the scratches, the faded colour, the wilting leaves, because those are exactly what
make the copy good. The second is a single structured-outputs call that produces the whole
package in one round: brand, tagline, features, pricing, testimonials, and the visual
theme. The third draws the logo and runs in the background — which is why the page is
already in front of you."*

**S2 · driver, 1:45**
> "This page is one single file."

Then: *"No external CSS, no fonts from a CDN, not one network request — the images are
base64 inside it. [download, stop the server, open the file from disk] And now: the same
stapler, a different tone. [luxury version] The model doesn't only pick colours — it picks
the font pairing, the corner radius and the spacing rhythm from a set we defined. That's
why it reads as a different company, not the same page repainted."*

**S1 · navigator, 2:45**
> "Let me show you why the copy isn't generic."

Then: *"Vision found the scratch on the lid and the half-peeled label — and there they
are, in the tagline. That's the difference between a pitch about any stapler in the world
and a pitch about **this** stapler. And when we change the tone, it isn't just the
adjectives: the pricing structure changes, and so does what it chooses to exaggerate. A
moment ago it was $19.99 in three easy payments. Now it's 'price on request'."*

**All four, 4:00**
> "These are all the companies founded today. Which one gets funded?"

---

## The objects

A good object has **visible flaws** and is boring. A bad object is new, pretty and generic.

| Object | Preferred tone | Why it works |
|---|---|---|
| scratched stapler | `vc` | the scratch and the coffee ring both land in the copy |
| mug with a coffee stain | `luxury` | "invented heritage" writes itself off a stain |
| half-dead desk plant | `kickstarter` | "help us bring it back" is genuinely funny here |
| tangled cable / odd adapter | `infomercial` | "But wait" plus a tangle is the whole joke |
| crumpled coffee cup | `infomercial` | reliable laugh, good fallback |

Fill in after testing: ______________________________________________

- [ ] All five tested before the demo
- [ ] Any object that produced a flat result is out of the pocket
- [ ] We also accept 2–3 objects from the audience

---

## Plan B — the network drops

Open the pre-generated backup gallery and narrate from it. Do not debug on stage.

> "The network in here has opinions, so let me show you the ones we founded earlier."

Then walk the gallery: same object across tones, and point at a quirk in a tagline. The
pages are self-contained, so **they open from disk with no server and no network at all.**
That is a feature, not a workaround — say so out loud.

- [ ] 6–8 good pitches generated and left in the gallery before 6:00
- [ ] One downloaded `.html` sitting on the desktop, ready to double-click

## Plan C — a call fails live

Stay calm and say it plainly:

> "That's a model — it has a bad day occasionally. Watch."

Then retry. A failure handled gracefully looks **better** than no failure at all, because it
shows the fallbacks are real. If content generation fails twice, switch objects rather than
retrying a third time.

If the logo never arrives: the page is already correct — it shows an inline SVG monogram.
Point at it: *"the logo is still rendering; the page never waited for it."*

---

## Tabs open before we start

- `index.html?presenter=1` — the capture screen, scaled for projection
- `gallery.html` — with the backup pitches already in it
- `/api/stats` — the spend cap and the timings
- one downloaded `.html` on the desktop

---

## The four scope decisions, one each

Said out loud during the demo — the mentors are explicitly looking for these.

**S1 · driver:** ______________________________________________
> e.g. "One structured-outputs call instead of five small ones — coherence across the whole
> package beats fine-grained control."

**S1 · navigator:** ______________________________________________
> e.g. "The logo runs in the background. `gpt-image-1` takes tens of seconds and the
> must-have was 'under a minute', so the page publishes without it and swaps it in."

**S2 · driver:** ______________________________________________
> e.g. "Vanilla HTML and JS, no framework. A build step would have cost 45 minutes and
> bought nothing for an upload screen and a gallery."

**S2 · navigator:** ______________________________________________
> e.g. "`mood` changes structure — padding, type scale, shadows, hero alignment — not just
> colour. Four repainted pages would not have read as four companies."

---

## Likely questions and who answers

| Question | Who |
|---|---|
| Why one structured-outputs call and not five? | S1 driver |
| What happens between the POST returning and the logo appearing? | S1 driver |
| The model returns 4 features instead of 3 — what happens? | S1 navigator |
| Why replace the whole palette when one colour is invalid? | S1 navigator |
| What is "quirk coverage"? | S1 navigator |
| What does "self-contained" mean, and how do you verify it? | S2 driver |
| Why no Google Fonts? | S2 driver |
| How do you stop a bad palette shipping an unreadable page? | S2 driver |
| Why does `mood` change structure and not just colour? | S2 navigator |
| Is the progress bar real or simulated? | S2 navigator |
| Why `<input capture>` and not `getUserMedia`? | S2 driver |
| Why resize in the browser if the server resizes anyway? | either S2 |

### The two answers to get right

**"Is the progress bar real?"** — Tell the truth. It is driven by elapsed time with
plausible thresholds, and it snaps to complete the moment the real response arrives,
because the server sends no per-stage events. With more time, server-sent events would have
been the correct answer. The honest answer scores better than a evasive one.

**"How is the page verified self-contained?"** — `assert_self_contained()` scans every
`src=`, `href=` and `url()` in the finished HTML and raises if any value is not a `data:`
URI, a fragment, or inline. It runs at the end of every render, so a page that would break
offline never gets written to disk.

---

## Definition of done for this document

- [ ] Read by all four of us
- [ ] Names filled in
- [ ] Five objects tested, preferred tone recorded for each
- [ ] Four scope decisions written as sentences, not bullets
- [ ] Two full dry runs, timed, standing up
