---
name: Ethereal Estate
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f4'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#4d4636'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#7f7664'
  outline-variant: '#d1c5b0'
  surface-tint: '#765b00'
  primary: '#765b00'
  on-primary: '#ffffff'
  primary-container: '#c19b2e'
  on-primary-container: '#453400'
  inverse-primary: '#ebc252'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e5e2e1'
  on-secondary-container: '#656464'
  tertiary: '#5d5f5f'
  on-tertiary: '#ffffff'
  tertiary-container: '#9fa0a0'
  on-tertiary-container: '#353737'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdf93'
  primary-fixed-dim: '#ebc252'
  on-primary-fixed: '#241a00'
  on-primary-fixed-variant: '#594400'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  headline-lg:
    fontFamily: Noto Serif
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Noto Serif
    fontSize: 32px
    fontWeight: '500'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Noto Serif
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.1em
spacing:
  container-max: 1280px
  gutter: 24px
  margin-page: 64px
  unit-xs: 4px
  unit-sm: 8px
  unit-md: 16px
  unit-lg: 32px
  unit-xl: 64px
---

## Brand & Style

The design system is anchored in the visual language of high-end, luxury real estate and private equity. It evokes feelings of exclusivity, heritage, and architectural precision. The brand personality is authoritative yet understated, favoring substance over flash. 

The aesthetic follows a **Minimalist** philosophy combined with **Editorial** layouts. It utilizes expansive whitespace to signify "breathing room"—a digital metaphor for sprawling luxury estates. Visual elements are characterized by sharp lines, a restrained color palette, and high-contrast typography that mirrors the experience of browsing a premium lifestyle magazine or an architectural portfolio.

## Colors

The color palette of the design system is a classic triad of luxury: Gold, Black, and White. 

- **Primary (Gold):** Used sparingly as an accent to denote prestige, primary actions, or interactive states. It should never overwhelm the layout but rather act as a "seal of quality."
- **Secondary (Deep Black):** Provides the structural foundation. Used for primary typography, borders, and high-impact background sections to create a sense of weight and permanence.
- **Tertiary & Neutral (Off-White/White):** The canvas. The subtle shift between pure white and the slightly grey off-white allows for soft grouping of content without the need for heavy lines or shadows.

Default color mode is set to light to maintain a clean, airy feel, though high-impact landing pages may utilize "Dark Mode" sections where #111111 becomes the primary canvas with Gold and White accents.

## Typography

This design system uses a sophisticated typographic pairing to balance tradition and modernity. 

**Noto Serif** is the primary headline font. It brings a timeless, literary quality to the interface. Headlines should use generous line heights and occasionally tight letter-spacing for a modern editorial look.

**Manrope** serves as the functional workhorse. It is a highly refined sans-serif that maintains legibility across body text and metadata. To maintain the luxury aesthetic, labels and navigation elements should utilize Manrope in all-caps with increased letter-spacing, suggesting the precision of an engraved plaque.

## Layout & Spacing

The layout philosophy is based on a **Fixed Grid** system. This ensures that content feels intentional and "framed" within the viewport. A 12-column grid is standard for desktop, with generous outer margins to ensure the content never feels crowded.

Spacing follows an 8px rhythmic scale. However, the design system encourages "intentional emptiness." Instead of filling every gap, use large vertical spacing (`unit-xl`) between major sections to emphasize the distinction between different properties or investment tiers. Alignment should be rigorous; elements should snap to the grid to reflect architectural stability.

## Elevation & Depth

To maintain a sophisticated and flat aesthetic, the design system avoids heavy shadows or realistic skeuomorphism. Instead, it uses **Tonal Layers** and **Low-contrast Outlines**.

- **Depth through Color:** Information hierarchy is established by layering #FFFFFF cards or sections over a #F7F7F7 background.
- **Ghost Borders:** Elements like input fields or secondary cards use 1px solid borders in a very light grey or the primary Gold.
- **Textural Overlays:** For high-impact imagery (e.g., property photos), a subtle gradient overlay (from transparent to 40% Black) may be used to ensure white typography remains legible without the need for drop shadows.

## Shapes

The shape language of the design system is **Sharp (0px)**. 

Sharp corners convey precision, strength, and a modern architectural edge. This applies to buttons, image containers, input fields, and cards. By removing all roundedness, the UI takes on a custom, "bespoke" feel that differentiates it from common, more approachable consumer apps. The only exception to the rectangular rule is the occasional use of circular iconography or decorative elements to provide a soft counterpoint to the rigid grid.

## Components

### Buttons
Primary buttons are solid #111111 with White text or solid Gold with White text. They feature sharp corners and high-contrast hover states (e.g., background color shift). Secondary buttons are "Ghost" style—1px borders with centered, letter-spaced Manrope text.

### Inputs
Fields are represented by a bottom-only border (Underline style) or a full 1px border. Focus states must use the primary Gold color for the border. Labels are always placed above the field in uppercase Manrope.

### Cards
Cards do not use shadows. They are defined by #FFFFFF backgrounds against a #F7F7F7 page, or by a simple 1px border. This keeps the focus on the photography and typography.

### Chips & Tags
Used for property status (e.g., "Available", "Sold"). These are small, rectangular boxes with solid Gold backgrounds and small, uppercase Manrope text.

### Navigation
The navigation bar is minimal and fixed. It uses a high-contrast logo and uppercase links. Hover effects on links should be a simple color transition to Gold or a thin underline.