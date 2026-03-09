# Mona Style Guide

> The definitive design reference for the MonoClaw "Mona" AI agent onboarding experience.
> A local web app running on Mac — ultra-minimalist Nordic-design neuomorphism with neutral palette and muted accents.

---

## 1. Design Philosophy

**Nordic minimalism meets neuomorphism.** Every surface, shadow, and transition serves a purpose. If it doesn't guide the user forward, it doesn't belong.

### Core Principles

- **Meeting a person, not configuring software.** Mona's onboarding is an introduction — warm, composed, human. The UI retreats so the conversation can lead.
- **Progressive disclosure.** One thing at a time. Each screen asks one question, presents one idea, or celebrates one milestone. Complexity is revealed only when the user is ready.
- **Depth without decoration.** Neuomorphic shadows create a tactile sense of physicality — raised buttons you want to press, inset fields that invite input — without borders, outlines, or visual clutter.
- **Emotionally resonant.** Inspired by Apple's onboarding: generous whitespace, deliberate pacing, moments that breathe. The experience should feel considered, not rushed.
- **Quiet confidence.** The design communicates trust through restraint. No flashy gradients, no attention-grabbing animations. Calm competence.

### Design Influences

| Influence | What We Take |
|-----------|--------------|
| Apple Setup Assistant | Focused single-task screens, emotional pacing, generous whitespace |
| Nordic interior design | Warm neutrals, natural materials palette, functional beauty |
| Neuomorphism (refined) | Soft depth, tactile surfaces — but restrained, not the 2020 trend excess |
| Dieter Rams | "Less, but better" — every element earns its place |

---

## 2. Color System

The palette draws from natural materials — linen, sand, sage, stone. Warm enough to feel human, neutral enough to stay professional.

### Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#F2EFEB` (warm linen) | App background |
| `--surface-raised` | `#F7F5F2` | Neuomorphic raised elements |
| `--surface-inset` | `#E8E4DE` | Neuomorphic pressed/inset elements |
| `--text-primary` | `#2C2825` | Headings, primary text |
| `--text-secondary` | `#8A8279` | Body copy, muted labels |
| `--text-tertiary` | `#B0A99F` | Placeholder text, disabled states |
| `--accent` | `#7C9A8E` (muted sage) | Interactive highlights, Mona's orb |
| `--accent-warm` | `#C4A882` (muted sand) | Secondary accent, progress indicators |
| `--accent-subtle` | `rgba(124, 154, 142, 0.15)` | Hover backgrounds, selection highlights |
| `--success` | `#8BA888` | Confirmations, completed states |
| `--warning` | `#C9A96E` | Alerts, pending items |
| `--error` | `#B87070` | Errors, destructive actions |
| `--shadow-light` | `rgba(255, 255, 255, 0.7)` | Neuomorphic light edge |
| `--shadow-dark` | `rgba(174, 168, 158, 0.5)` | Neuomorphic dark edge |

### Dark Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--surface` | `#1C1B19` | App background |
| `--surface-raised` | `#242320` | Raised elements |
| `--surface-inset` | `#151412` | Inset elements |
| `--text-primary` | `#E8E4DE` | Headings, primary text |
| `--text-secondary` | `#7A7470` | Body copy, muted labels |
| `--text-tertiary` | `#4A4642` | Placeholder text, disabled states |
| `--shadow-light` | `rgba(255, 255, 255, 0.03)` | Neuomorphic light edge |
| `--shadow-dark` | `rgba(0, 0, 0, 0.5)` | Neuomorphic dark edge |

Accent colors remain identical across modes:

| Token | Value |
|-------|-------|
| `--accent` | `#7C9A8E` |
| `--accent-warm` | `#C4A882` |
| `--accent-subtle` | `rgba(124, 154, 142, 0.15)` |
| `--success` | `#8BA888` |
| `--warning` | `#C9A96E` |
| `--error` | `#B87070` |

### CSS Custom Properties

```css
:root {
  --surface: #F2EFEB;
  --surface-raised: #F7F5F2;
  --surface-inset: #E8E4DE;
  --text-primary: #2C2825;
  --text-secondary: #8A8279;
  --text-tertiary: #B0A99F;
  --accent: #7C9A8E;
  --accent-warm: #C4A882;
  --accent-subtle: rgba(124, 154, 142, 0.15);
  --success: #8BA888;
  --warning: #C9A96E;
  --error: #B87070;
  --shadow-light: rgba(255, 255, 255, 0.7);
  --shadow-dark: rgba(174, 168, 158, 0.5);
}

@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1C1B19;
    --surface-raised: #242320;
    --surface-inset: #151412;
    --text-primary: #E8E4DE;
    --text-secondary: #7A7470;
    --text-tertiary: #4A4642;
    --shadow-light: rgba(255, 255, 255, 0.03);
    --shadow-dark: rgba(0, 0, 0, 0.5);
  }
}
```

---

## 3. Typography

Type is the primary design element. It carries Mona's voice, guides the user, and sets emotional tone. We use a restrained typographic scale with careful weight selection.

### Font Stack

| Role | Family | Fallback |
|------|--------|----------|
| Primary | Inter | system-ui, -apple-system, sans-serif |
| Monospace | JetBrains Mono | ui-monospace, "SF Mono", monospace |
| CJK Traditional | Noto Sans TC | "PingFang TC", sans-serif |
| CJK Simplified | Noto Sans SC | "PingFang SC", sans-serif |

### Type Scale

| Level | Weight | Size | Line Height | Letter Spacing | Usage |
|-------|--------|------|-------------|----------------|-------|
| Display XL | 300 (Light) | 48px / 3rem | 1.1 | -0.02em | Welcome screen hero text |
| Display L | 300 (Light) | 40px / 2.5rem | 1.15 | -0.02em | Section hero text |
| Display M | 300 (Light) | 32px / 2rem | 1.2 | -0.02em | Step titles |
| Heading L | 400 (Regular) | 24px / 1.5rem | 1.3 | -0.01em | Section headings |
| Heading M | 400 (Regular) | 20px / 1.25rem | 1.35 | -0.01em | Card headings, sub-sections |
| Body L | 400 (Regular) | 16px / 1rem | 1.6 | 0 | Primary body text |
| Body M | 400 (Regular) | 14px / 0.875rem | 1.6 | 0 | Secondary body text, captions |
| Body Strong | 500 (Medium) | 16px / 1rem | 1.6 | 0 | Emphasis within body copy |
| Mono | 400 (Regular) | 14px / 0.875rem | 1.5 | 0 | Codes, technical details, API keys |

### Mona's Voice Typography

When Mona "speaks" (TypeWriter text, chat bubbles, conversational copy), apply a distinct but subtle treatment:

```css
.mona-voice {
  font-family: "Inter", system-ui, sans-serif;
  font-weight: 300;
  letter-spacing: 0.01em;
  line-height: 1.8;
}
```

This wider line-height and lighter weight creates text that feels **conversational, not mechanical** — like reading a handwritten note rather than a system message.

### CJK Considerations

- Traditional Chinese (繁體中文): Use Noto Sans TC. Maintain the same weight mappings.
- Simplified Chinese (简体中文): Use Noto Sans SC. Same weight mappings.
- Line heights may need slight increases (1.7–1.8 for body) to accommodate CJK character density.
- Do not use bold (700+) for CJK — it reduces readability. Use color or size for emphasis.

---

## 4. Spacing & Layout

### Base Unit

All spacing derives from an **8px base unit**. Use multiples:

| Token | Value | Common Use |
|-------|-------|------------|
| `--space-1` | 4px | Tight internal padding, icon-to-label gap |
| `--space-2` | 8px | Base unit, compact spacing |
| `--space-3` | 12px | Small component padding |
| `--space-4` | 16px | Default element gap |
| `--space-5` | 20px | — |
| `--space-6` | 24px | Component internal padding, element groups |
| `--space-8` | 32px | Section sub-spacing |
| `--space-10` | 40px | — |
| `--space-12` | 48px | Section spacing, page horizontal padding |
| `--space-16` | 64px | Page vertical padding |
| `--space-20` | 80px | Major section breaks |
| `--space-24` | 96px | — |

### Page Layout

```
┌──────────────────────────────────────────────────┐
│                   64px top                        │
│    ┌──────────────────────────────────────┐       │
│    │          max-width: 640px            │       │
│ 48 │                                      │ 48   │
│ px │   Content flows vertically here.     │ px   │
│    │   Single column. Centered.           │       │
│    │                                      │       │
│    └──────────────────────────────────────┘       │
│                   64px bottom                     │
└──────────────────────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Max content width | 640px |
| Horizontal padding | 48px |
| Vertical padding | 64px |
| Content centering | `margin: 0 auto` |
| Between major sections | 48px |
| Between form elements | 16px – 24px |

### Full-Viewport Screens

Certain emotional beats occupy the full viewport height with content centered both vertically and horizontally:

- **Welcome** — Mona introduces herself
- **Independence Day** — the moment the system goes autonomous
- **Launch** — the final send-off

These screens use `min-height: 100vh` with flexbox centering.

---

## 5. Neuomorphism Specification

Neuomorphism in Mona is **subtle and functional**. It creates a sense that UI elements are gently rising from or pressing into the surface — like soft clay or leather. It is never harsh, never cartoonish.

### Raised (Default Card/Button State)

```css
.neu-raised {
  background: var(--surface-raised);
  box-shadow:
    6px 6px 12px var(--shadow-dark),
    -6px -6px 12px var(--shadow-light);
  border: none;
  border-radius: 16px;
}
```

### Inset (Pressed/Input State)

```css
.neu-inset {
  background: var(--surface-inset);
  box-shadow:
    inset 4px 4px 8px var(--shadow-dark),
    inset -4px -4px 8px var(--shadow-light);
  border: none;
  border-radius: 8px;
}
```

### Hover State (Raised Elements)

```css
.neu-raised:hover {
  box-shadow:
    8px 8px 16px var(--shadow-dark),
    -8px -8px 16px var(--shadow-light);
}
```

### Active/Pressed State

```css
.neu-raised:active {
  background: var(--surface-inset);
  box-shadow:
    inset 4px 4px 8px var(--shadow-dark),
    inset -4px -4px 8px var(--shadow-light);
}
```

### Border Radius Scale

| Element | Radius |
|---------|--------|
| Cards | 16px |
| Buttons | 12px |
| Inputs | 8px |
| Orb containers | 24px |
| Pills / tags | 9999px |

### Rules

- **No hard borders anywhere.** Depth is communicated entirely through shadow.
- **All shadow transitions** use `transition: box-shadow 200ms ease-out`.
- **In dark mode**, the effect is more subtle — `--shadow-light` is barely perceptible, and `--shadow-dark` does the heavy lifting.
- **Avoid nesting** raised inside raised — it creates visual noise. Use flat or inset for children of raised parents.

---

## 6. Component Specifications

### NeuCard

The primary container for grouped content.

| Property | Value |
|----------|-------|
| Background | `var(--surface-raised)` |
| Box shadow | Raised neuomorphism (see §5) |
| Padding | 24px |
| Border radius | 16px |
| Border | None |

**Variants:**
- `default` — Raised neuomorphism
- `inset` — Inset neuomorphism, used for selected/active cards
- `flat` — No shadow, just `var(--surface-raised)` background, used inside other cards

```tsx
<NeuCard variant="default">
  <h3>WiFi Setup</h3>
  <p>Connect to your local network.</p>
</NeuCard>
```

---

### NeuButton

| Variant | Background | Shadow | Text Color | Hover |
|---------|-----------|--------|------------|-------|
| Primary | `var(--surface-raised)` | Raised | `var(--accent)` | Shadow increases |
| Secondary | `var(--surface-raised)` | Subtle raised (50% shadow opacity) | `var(--text-secondary)` | Full raised |
| Ghost | transparent | None | `var(--text-secondary)` | Subtle raised appears |

**Sizes:**

| Size | Height | Horizontal Padding | Font Size |
|------|--------|--------------------|-----------|
| `sm` | 40px | 16px | 14px |
| `md` | 48px | 24px | 16px |
| `lg` | 56px | 32px | 16px |

**States:**
- **Hover:** Shadow distance increases (see §5)
- **Active/Pressed:** Transitions to inset shadow
- **Disabled:** opacity 0.5, no shadow, cursor not-allowed
- **Loading:** Text replaced with subtle pulse animation

**Border radius:** 12px default, `9999px` for pill variant.

```tsx
<NeuButton variant="primary" size="md">Continue</NeuButton>
<NeuButton variant="ghost" size="sm">Skip</NeuButton>
<NeuButton variant="primary" size="lg" pill>Get Started</NeuButton>
```

---

### NeuInput

Text inputs appear **recessed into the surface**, inviting interaction.

| Property | Value |
|----------|-------|
| Background | `var(--surface-inset)` |
| Box shadow | Inset neuomorphism (see §5) |
| Height | 48px |
| Padding | 0 16px |
| Border radius | 8px |
| Border | None |
| Font | Body L (16px, weight 400) |
| Placeholder color | `var(--text-tertiary)` |

**Focus state:**
```css
.neu-input:focus {
  outline: none;
  box-shadow:
    inset 4px 4px 8px var(--shadow-dark),
    inset -4px -4px 8px var(--shadow-light),
    0 0 0 3px rgba(124, 154, 142, 0.3);
}
```

The focus ring uses `--accent` at 30% opacity, creating a soft glow rather than a hard outline.

---

### NeuProgress

A track-and-fill progress indicator.

| Property | Value |
|----------|-------|
| Track background | Inset neuomorphism |
| Track height | 8px |
| Track border radius | 9999px |
| Fill | `linear-gradient(90deg, var(--accent), var(--accent-warm))` |
| Fill border radius | 9999px |
| Fill transition | `width 600ms ease-out` |

```tsx
<NeuProgress value={0.4} /> {/* 40% complete */}
```

---

### Orb (Mona's Presence)

The orb is Mona's visual embodiment — a soft, breathing sphere of light that communicates her state.

| Property | Intro Size | Compact Size |
|----------|-----------|--------------|
| Diameter | 120px | 80px |
| Shape | Circle | Circle |
| Background | Radial gradient: `var(--accent)` center → transparent edge | Same |
| Container radius | 24px (if contained) | 24px |

**States:**

| State | Visual |
|-------|--------|
| Idle / Breathing | Gentle scale pulse: 1.0 → 1.03, 4s cycle |
| Listening | Subtle ring pulse outward from orb edge |
| Speaking | Morphs to waveform visualization |
| Thinking | Slow rotation of gradient axis, 8s cycle |
| Success | Brief flash to `var(--success)`, returns to accent |

**Transition between all states:** 600ms ease-in-out.

---

### TypeWriter

Mona's text appears character by character, simulating natural typing with organic rhythm.

| Property | Value |
|----------|-------|
| Character speed | 40–80ms per character (randomized per character) |
| Pause at period (`.`) | 400ms |
| Pause at comma (`,`) | 200ms |
| Pause at question mark (`?`) | 350ms |
| Cursor style | Thin vertical bar (`|`), 2px wide |
| Cursor color | `var(--accent)` |
| Cursor blink interval | 530ms |
| Cursor after completion | Fades out over 300ms, then hidden |

The randomized per-character speed prevents the uncanny "constant rate" feel of naive typewriter effects.

---

### WaveForm

Audio visualization for Mona's voice input/output.

| Property | Value |
|----------|-------|
| Bar count | 40–60 bars |
| Bar width | 3px |
| Bar gap | 2px |
| Bar color | `var(--accent)` |
| Bar border radius | 9999px (fully rounded) |
| Container height | Matches orb diameter |

**States:**

| State | Behavior |
|-------|----------|
| Idle | Subtle random height variation, 2–5px range, gentle undulation |
| Active (speaking) | Bar heights respond to audio output amplitude |
| Active (listening) | Bar heights respond to microphone input amplitude |

Transition between idle and active: 300ms ease-out.

---

## 7. Animation System

All animations use **Framer Motion**. The system is designed for fluidity and calm — nothing should feel abrupt or jarring.

### Page Transitions

```typescript
const pageVariants = {
  initial: { opacity: 0, y: 20 },
  enter: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] },
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: { duration: 0.3 },
  },
};
```

Apply to each onboarding step's root element with `<AnimatePresence mode="wait">`.

### Stagger Children

For lists, form groups, and any set of sibling elements that should appear sequentially:

```typescript
const containerVariants = {
  enter: {
    transition: { staggerChildren: 0.05 },
  },
};

const childVariants = {
  initial: { opacity: 0, y: 12 },
  enter: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4 },
  },
};
```

### Spring Physics

For interactive elements (drag, toggle, orb movement):

```typescript
const springConfig = {
  stiffness: 100,
  damping: 20,
  mass: 1,
};
```

This produces a natural, slightly underdamped motion — responsive but not bouncy.

### Orb Breathing

```typescript
const orbVariants = {
  breathing: {
    scale: [1, 1.03, 1],
    transition: {
      duration: 4,
      repeat: Infinity,
      ease: "easeInOut",
    },
  },
};
```

### Checkmark Draw

For success confirmations, animate an SVG checkmark path:

```typescript
const checkmarkVariants = {
  hidden: { pathLength: 0, opacity: 0 },
  visible: {
    pathLength: 1,
    opacity: 1,
    transition: {
      pathLength: { duration: 0.8, ease: "easeOut" },
      opacity: { duration: 0.2 },
    },
  },
};
```

```tsx
<motion.svg viewBox="0 0 24 24">
  <motion.path
    d="M4 12l6 6L20 6"
    fill="none"
    stroke="var(--success)"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    variants={checkmarkVariants}
    initial="hidden"
    animate="visible"
  />
</motion.svg>
```

### Fade In

Utility variant for simple opacity reveals:

```typescript
const fadeIn = {
  initial: { opacity: 0 },
  enter: {
    opacity: 1,
    transition: { duration: 0.5 },
  },
};
```

### Animation Timing Reference

| Animation | Duration | Easing |
|-----------|----------|--------|
| Page enter | 400ms | cubic-bezier(0.25, 0.1, 0.25, 1) |
| Page exit | 300ms | ease-out |
| Shadow transition | 200ms | ease-out |
| Orb state change | 600ms | ease-in-out |
| Orb breathing cycle | 4000ms | ease-in-out |
| Stagger interval | 50ms | — |
| Checkmark draw | 800ms | ease-out |
| Progress fill | 600ms | ease-out |
| Cursor fade-out | 300ms | ease-out |

---

## 8. Mona's Personality & Voice Guidelines

Mona is not a chatbot. She is not an assistant. She is a **capable, warm colleague** meeting you on her first day. She knows what she's doing — she just needs to learn how *you* work.

### Character Traits

| Trait | Expression |
|-------|------------|
| Warm | Genuine interest in the user's work, never perfunctory |
| Composed | Calm even during errors — "Let me try that differently" |
| Gently confident | Knows her capabilities without boasting |
| Respectful of expertise | "You know your business — I'll handle the busywork" |
| Concise | Says what needs saying, then stops |

### Voice Rules

- Uses **first person** naturally: "I can help with that" — never "Mona can help with that"
- **Never** overly enthusiastic, salesy, or performatively excited
- **Never** uses "AI" buzzwords: no "leverage", "empower", "revolutionize", "cutting-edge"
- Acknowledges uncertainty honestly: "I'm not sure about that yet. Can you show me?"
- Error states are calm, not apologetic: "That didn't work. Let's try another way."

### Tone Spectrum

The user can choose their preferred tone during onboarding. All three tones maintain the same personality — only the register changes.

| Tone | Greeting | Style | Example |
|------|----------|-------|---------|
| Casual | "Hey! Ready when you are." | Short sentences, contractions, warm | "Cool, got it. What's next?" |
| Balanced (default) | "Hi there. I'm ready to help." | Natural, clear, professional-friendly | "That's set up. Shall we continue?" |
| Formal | "Good morning. I'm at your service." | Complete sentences, respectful distance | "Configuration is complete. When you're ready, we can proceed." |

### Multilingual Voice

| Language | Notes |
|----------|-------|
| English | Default. Clear, concise, active voice. |
| Cantonese (繁體中文) | Natural Hong Kong colloquial tone where appropriate. Not stiff written Chinese. 「搞掂喇」 not 「已完成配置」. |
| Mandarin (简体中文) | Standard Mandarin, clean and modern. 「好的，设置完成。」 |

The personality must translate across languages — Mona should feel like the same person regardless of language.

### Copy Principles for Onboarding

- **Short sentences.** Maximum 12 words per line.
- **One idea per screen.** If you're explaining two things, it's two screens.
- **Active voice always.** "I'll set this up" not "This will be set up."
- **No jargon.** No "AI", "model", "inference", "pipeline" in user-facing copy.
- **Whitespace over punctuation.** Emotional beats use timing and space, not exclamation marks.
- **Respect the user's time.** Every word must earn its place.

### Example Copy

**Welcome screen:**
> Hi. I'm Mona.
>
> I'll be working alongside you —
> handling the tasks you'd rather not.

**After WiFi setup:**
> Connected.
> That's our first step together.

**Error state:**
> That network didn't respond.
> Want to try another, or skip for now?

**Independence moment:**
> From here, I work on my own.
> You set the direction. I handle the rest.

---

## 9. Iconography & Illustration

### Icon Style

| Property | Value |
|----------|-------|
| Style | Line art, outlined |
| Stroke width | 1.5px |
| Stroke caps | Round |
| Stroke joins | Round |
| Default color | `var(--text-secondary)` |
| Interactive/active color | `var(--accent)` |
| Icon set | [Lucide](https://lucide.dev/) as base |

### Icon Sizing

| Context | Size |
|---------|------|
| Inline with text | 16px × 16px |
| Button icon | 20px × 20px |
| Section icon | 24px × 24px |
| Feature illustration | 48px × 48px |

### Illustration Guidelines

- **Nordic illustration style:** Minimal, geometric, warm. Think simple line drawings with occasional accent color fills.
- **No emoji** in the onboarding UI. Mona's personality comes from words and animation, not pictograms.
- **Illustrations are optional.** If a screen communicates clearly with text alone, don't add an illustration for decoration.
- **Accent color fills** should be used sparingly — at most one filled element per illustration.

---

## 10. Accessibility

Accessibility is not an afterthought. Every specification in this guide is designed to meet or exceed WCAG 2.1 AA standards.

### Touch & Click Targets

- All interactive elements: **minimum 44px × 44px** touch/click target
- If the visual element is smaller (e.g., a text link), extend the clickable area with padding

### Color Contrast

| Combination | Ratio | Standard |
|-------------|-------|----------|
| `--text-primary` on `--surface` | 10.2:1 | AAA |
| `--text-secondary` on `--surface` | 4.7:1 | AA |
| `--accent` on `--surface` | 4.5:1 | AA |
| `--text-primary` on `--surface-raised` | 9.8:1 | AAA |
| `--error` on `--surface` | 4.5:1 | AA |

All text must meet **4.5:1 minimum** (normal text) or **3:1 minimum** (large text, 18px+ or 14px+ bold).

### Focus Management

```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

- Focus rings are visible on keyboard navigation only (`:focus-visible`, not `:focus`)
- Tab order follows visual order — no `tabindex` hacks
- Full keyboard navigation through all onboarding steps
- Escape key closes modals and overlays

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

When `prefers-reduced-motion` is active:
- Orb breathing animation: **disabled** (static orb)
- TypeWriter effect: **disabled** (text appears instantly)
- Page transitions: **disabled** (instant swap)
- Progress bar: **disabled** (instant fill)
- Waveform: **disabled** (static bars at mid-height)
- Checkmark: **appears instantly** (no draw animation)

### Screen Reader Support

- All decorative elements (orb, waveform, illustrations): `aria-hidden="true"`
- Interactive elements have descriptive `aria-label` attributes
- Onboarding progress is announced: `aria-live="polite"` on step indicators
- TypeWriter text uses `aria-live="polite"` so the full text is announced when complete, not character by character
- Form errors are linked via `aria-describedby`

### Language

- `lang` attribute set on `<html>` and updated when language changes
- CJK text blocks use appropriate `lang` sub-tags (`zh-Hant-HK`, `zh-Hans`)

---

## 11. Responsive Considerations

### Target Devices

| Priority | Device | Viewport |
|----------|--------|----------|
| Primary | Mac (local app) | 1440px+ |
| Secondary | iPad (local network) | 768px – 1024px |
| Tertiary | iPhone (local network) | 375px – 428px |

### Breakpoints

| Token | Value | Target |
|-------|-------|--------|
| `sm` | 640px | Small phones |
| `md` | 768px | Tablets, small laptops |
| `lg` | 1024px | Standard laptops |
| `xl` | 1440px | Desktop (primary) |

### Responsive Adaptations

| Element | Desktop (1440px+) | Tablet (768px) | Mobile (375px) |
|---------|-------------------|----------------|----------------|
| Page padding (horizontal) | 48px | 32px | 24px |
| Page padding (vertical) | 64px | 48px | 32px |
| Max content width | 640px | 640px | 100% |
| Display XL font | 48px | 40px | 32px |
| Display L font | 40px | 32px | 28px |
| Orb diameter | 120px | 100px | 80px |
| Section spacing | 48px | 40px | 32px |
| NeuCard padding | 24px | 20px | 16px |

### Mobile-Specific Rules

- Neuomorphic shadows are reduced by ~30% on mobile (less visual weight on smaller screens)
- Horizontal scrolling is forbidden — all content flows vertically
- Bottom navigation/actions are pinned above the keyboard when input is focused
- Orb scales down but maintains the same animation timings

---

## 12. Onboarding Flow (12 Phases)

The onboarding is designed as meeting a colleague, not configuring software. Each phase has an emotional beat.

| Phase | Screen | Emotional Beat | Duration |
|-------|--------|----------------|----------|
| 0 | Welcome | Anticipation | ~5s |
| 1 | Independence | Empowerment | ~15s |
| 2 | Introduction | Warmth | ~20s |
| 3 | Voice Interaction | Delight | Live local TTS/STT (mlx-whisper + Qwen3-TTS) |
| 4 | Chat Experience | Connection | SSE Streaming, Model Selector, Stop Button |
| 5 | Profile | Personalization | User-paced |
| 6 | MacSetup | Ownership | User-paced |
| 7 | API Keys | Configuration | Guided wizards for DeepSeek, Kimi, GLM-5, etc. |
| 8 | Tools & Skills | Confidence | Industry tools + ClawHub community skills |
| 9 | GuidedFirstTask | Competence | Contextual industry task |
| 10 | Summary | Reassurance | ~10s |
| 11 | Launch | Celebration | ~10s |

### Pacing Rules

- Emotional screens (Welcome, Independence, Introduction, Launch) are time-driven — the user watches, not clicks.
- Interactive screens (Voice, Chat, Profile, Mac, API Keys) are user-paced — no rushing.
- Every screen has a "Continue" or "Skip" option — never trap the user.

---

## 13. Interaction & Intelligence

### Model Routing (Max Bundle Only)
Users who commissioned the Max Bundle (1,999 HKD) have access to **Automated Model Routing**. Mona automatically selects the most efficient model based on task complexity:
- **Simple**: Fast, lightweight models (e.g., Qwen 0.8B)
- **Moderate**: Standard balanced models (e.g., Mistral 7B)
- **Complex**: High-reasoning models (e.g., Qwen 9B)
- **Code**: Specialized coding models (e.g., Qwen Coder)

### Manual Selection
All users can manually override model selection via the **ModelSelector** pill in the chat interface. The selected model and routing mode are **persisted** to disk (`routing-config.json`) and synced to OpenClaw’s default model so the gateway uses the user’s choice across restarts and tab switches.

### Persistent Chat & Conversations
Chat history is stored locally (one JSON file per conversation in `/opt/openclaw/state/chat/`). The Chat tab shows a **conversation sidebar** with:
- **New chat** — Creates a new conversation and focuses the input.
- **Conversation list** — Each item shows title (or first message snippet) and date; clicking opens that conversation. Delete via the trash icon on hover.
- **Single active context** — Only one conversation is active at a time; the input and sidebar actions (New chat, switch conversation) are disabled while Mona is streaming a response.

Conversations not opened or used for **30 days** are automatically removed on Hub startup (auto-drain). The last-open conversation id is remembered so returning to the Chat tab restores the same thread.

### Voice/Text Interaction Manager
To ensure a seamless experience, Mona uses an **Interaction Manager** that prevents voice and text modes from conflicting. 
- **Text Mode**: Uses SSE (Server-Sent Events) for real-time token streaming.
- **Voice Mode**: Uses a synchronous path to ensure the full response is ready for high-quality TTS synthesis.
- **Voice Toggle**: Users can disable Mona's voice interface at any time via the neuomorphic toggle.

---

## 14. Additional Components

### NeuCheckbox (for web portal)

Uses the host platform's checkbox design (shadcn/ui on web portal). Not neuomorphic — follows the web portal's existing design system.

### ModelSelector

A compact dropdown pill for selecting the active LLM model.

| Property | Value |
|----------|-------|
| Trigger | Pill-shaped chip, `var(--surface-raised)`, raised shadow |
| Trigger height | 32px |
| Trigger padding | 8px 12px |
| Trigger font | Body M (14px) |
| Dropdown | `NeuCard` raised, max-height 300px, overflow scroll |
| Item height | 40px |
| Selected item | `var(--surface-inset)` background |
| Category badge | Pill, `var(--accent-subtle)` background, Body M |

When auto-routing is active (Max Bundle only), the trigger shows "Auto" with a subtle gradient accent.

### VoiceToggle

A neuomorphic on/off switch for Mona's voice.

| Property | Value |
|----------|-------|
| Width | 48px |
| Height | 28px |
| Track (off) | `var(--surface-inset)`, inset shadow |
| Track (on) | `var(--accent)` at 30% opacity |
| Thumb diameter | 22px |
| Thumb (off) | `var(--surface-raised)`, left-aligned |
| Thumb (on) | `var(--accent)`, right-aligned |
| Transition | 200ms ease-out |

### Conversation Sidebar (Chat tab)

When the user is on the Chat route, a left sidebar lists conversations and provides "New chat".

| Property | Value |
|----------|-------|
| Width | 280px |
| Background | `var(--surface)` |
| Border | Right border, `var(--shadow-dark)` 20% |
| New chat button | Full-width `NeuButton`, Plus icon + "New chat" |
| List item | NavLink to `/chat/:id`, title + date; trash icon on hover (delete) |
| Disabled state | When streaming, New chat and conversation switches are disabled |

### StopButton

Replaces the send button during active text generation.

| Property | Value |
|----------|-------|
| Shape | Pill (same as NeuButton sm pill) |
| Icon | 8×8 filled square, `var(--text-secondary)` |
| Variant | Ghost |
| Hover | Subtle raised shadow appears, icon becomes `var(--error)` |

### GuidedKeySetup

A multi-step wizard for API key configuration. Used in the ApiKeys onboarding phase.

| Property | Value |
|----------|-------|
| Step number badge | 24px circle, `var(--accent)` background, white text |
| Step card | `NeuCard` flat variant, 16px padding |
| Link button | Ghost NeuButton with arrow icon, `var(--accent)` text |
| Key input | `NeuInput` with `font-mono` class |
| Validation checking | Pulsing accent border (2px), "Verifying..." text |
| Validation valid | `var(--success)` border, checkmark icon |
| Validation invalid | `var(--error)` border, error message text |

### Messaging Platform Icons

When displaying messaging platform icons in the ApiKeys phase, use muted versions of brand colors to maintain the neutral palette:

| Platform | Brand Color | Muted Version |
|----------|-------------|---------------|
| WhatsApp | #25D366 | `var(--accent)` (use accent instead of green) |
| Telegram | #0088CC | `var(--accent)` |
| Discord | #5865F2 | `var(--accent)` |
| Email | — | `var(--text-secondary)` |

Do **not** use brand colors directly. All platform icons use `var(--accent)` for consistency.

---

## Appendix: Quick Reference

### Shadow Presets

```css
/* Raised */
box-shadow: 6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light);

/* Raised (hover) */
box-shadow: 8px 8px 16px var(--shadow-dark), -8px -8px 16px var(--shadow-light);

/* Inset */
box-shadow: inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light);

/* Focus ring */
box-shadow: inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light), 0 0 0 3px rgba(124, 154, 142, 0.3);
```

### Border Radius Tokens

```css
--radius-sm: 8px;    /* Inputs */
--radius-md: 12px;   /* Buttons */
--radius-lg: 16px;   /* Cards */
--radius-xl: 24px;   /* Orb containers */
--radius-full: 9999px; /* Pills */
```

### Z-Index Scale

| Layer | Z-Index |
|-------|---------|
| Base content | 0 |
| Raised cards | 1 |
| Sticky headers | 10 |
| Overlays/modals | 100 |
| Orb (always visible) | 50 |
| Toast notifications | 200 |

---

*This is a living document. As Mona evolves, so will this guide.*
*Last updated: 2026-03-08*
