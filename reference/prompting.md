# Prompt recipes by asset type

Flux.1-schnell wants natural-language captions: subject, setting, lighting,
mood, style — as a sentence, not comma-spam tags. Concrete nouns beat
adjectives. Never ask for legible text beyond 1–2 words.

## Hero images (1440x800, 1440x600, 2880x1600 for retina)

Pattern: `[style] photo of [concrete scene], [lighting], [mood]`

> warm, natural-light photograph of a sunlit pottery studio, shelves of
> handmade ceramic bowls, soft morning atmosphere

Leave negative space for headline overlay by putting the subject to one
side: "subject on the right third, soft out-of-focus background on the left".

## Section backgrounds & textures (1440x600, or square tiles 1024x1024)

Pattern: `abstract [material/texture], [palette], [energy]`

> abstract close-up of handmade paper texture, warm ivory tones, subtle
> fibers, soft even lighting, minimalist

Keep contrast LOW so foreground text stays readable: add "muted, low
contrast, soft" and avoid "vibrant, dramatic".

## Spot illustrations (600x600 – 800x800)

Pattern: `flat [style] illustration of [single subject], [palette], simple shapes, clean background`

> flat minimalist illustration of a paper airplane looping upward, two-tone
> terracotta and cream, simple geometric shapes, solid off-white background

One subject per image. Diffusion gets crowded compositions wrong.

## og:images / social cards (1200x630)

Design for NO text (your page title gets overlaid by the platform or by
HTML). Aim for a bold, simple, high-recognition composition:

> bold minimal composition of a single terracotta ceramic bowl centered on
> a warm cream background, soft studio lighting, generous negative space

## Placeholder & editorial photography (varies)

Pattern: `[shot type] photograph of [subject], [setting], [lighting]`

> candid medium-shot photograph of two people reviewing sketches at a
> workshop table, natural window light, shallow depth of field

Avoid celebrity names and brand logos. For diverse team/people sets,
generate separate images with consistent lighting via a shared style suffix
rather than one group shot.

## What consistently fails — redirect instead

| Ask | Do this instead |
|---|---|
| Logo | SVG, hand-written |
| Icon set | SVG library or hand-drawn SVG |
| UI screenshot | Build the UI, screenshot it |
| Chart/diagram | HTML/SVG/Mermaid |
| Legible paragraph text in image | HTML/CSS overlay |
