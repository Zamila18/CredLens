# CredLens final designs and Claude Code handoff

This folder contains the selected visual references, the original content brief, and implementation instructions. It is a design handoff, not an implemented website.

## Start here

Give Claude Code the extracted folder in your project and use this prompt:

> Read `CredLens_Final_Designs/CLAUDE_CODE_INSTRUCTIONS.md`, `CHATGPT_DESIGN_BRIEF.md`, and `CONSENT_PHONE_COPY.md` completely. Inspect every image listed in `IMAGE_MANIFEST.json` and the existing repository. Implement the working interface to closely match the approved screenshots, preserving the existing stack. Follow the later layout/localisation decisions in the instructions, correct generated-image text/data errors using the brief, and implement all interactions, role/consent guards, mobile layouts and full English/Bangla translation. Do not just display screenshots as webpages. Validate at1440px desktop and390px mobile, compare screenshots, fix discrepancies, and report completed work and actual checks. Do not publish or deploy.

## Files

- `CLAUDE_CODE_INSTRUCTIONS.md`: primary implementation directions, image-to-route map, final decisions, behaviour and acceptance checks.
- `CHATGPT_DESIGN_BRIEF.md`: original detailed page content, supplied data and rules. Later decisions in the implementation instructions override older layout requirements.
- `CONSENT_PHONE_COPY.md`: complete bilingual consent-state copy, transitions and questionnaire distinction.
- `IMAGE_MANIFEST.json`: image filenames, actual raster dimensions and hashes.
- Numbered PNG files: approved visual references. `01-home-bangla.png` is the existing Bangla Home sample; additional Bangla images are not required. Claude Code should localise all routes in code.

## Coverage

The images include the design-system sheet, pages01–11, five separate consent states, one additional phone-only consent Ask image, and the Bangla Home sample. Separate Home/Queue/Merchant390px mockups, Bangla Merchant detail, and the three additional merchant-condition images were not generated; their responsive/localised/state implementations are specified for Claude Code instead. This archive must not be mistaken for an already-built app or validated production analytics.

The PNGs have varied generated raster sizes.1440px desktop and390px phone are implementation viewport targets, not a claim about PNG pixel dimensions. Use the manifest to inspect actual sizes.

## Important

Preserve the mint visual style. Queue uses cards; merchant detail uses full-width scrolling sections; Decision log uses a table; Portfolio uses five explanatory questions. Generated image mistakes are not product requirements. Supplied canonical data and consent/permission constraints take precedence. All five phone consent states are local simulations and must not create or revoke real API consent.
