# OZON SELLER DESIGN SYSTEM --- MASTER UI SPECIFICATION

> **Purpose:** this file is the visual source of truth for the Ozon
> Manager project.
>
> **Source basis:** the two HTML files supplied for this project: -
> `Ozon_ html.html` - `Ozon_ Торговая площадка.html`
>
> The specification below extracts the design language actually present
> in those files: typography, semantic colors, layout dimensions,
> elevation, borders, radii, interaction states, controls, tables,
> overlays and component patterns.
>
> **Scope:** visual design only. It does not change Ozon API contracts,
> business rules, Price Engine, mutation safety, authentication, data
> models or application architecture.

------------------------------------------------------------------------

## 1. MASTER RULE

For every new screen, component or feature:

``` text
New feature
    ↓
This Design System
    ↓
Existing project UI component
    ↓
New shared component only when necessary
    ↓
Screen implementation
```

Do **not** invent a separate visual language for a new feature.

Existing functionality must remain unchanged when applying the design
system.

------------------------------------------------------------------------

# 2. DESIGN DNA

The supplied Ozon Seller HTML establishes the following visual language:

-   light application shell;
-   white content surfaces;
-   very light neutral/blue-gray workspace background;
-   Ozon blue as the main action color;
-   Onest as the principal font;
-   compact information-dense UI;
-   restrained borders;
-   soft elevation;
-   rounded controls and cards;
-   semantic green/yellow/red states;
-   clear primary/secondary/tertiary text hierarchy;
-   tables designed as operational work surfaces;
-   explicit hover, selected, active, focus and disabled states;
-   overlays/popovers/dialogs with stronger elevation;
-   desktop-first layout.

The project must preserve this character even for screens that do not
yet exist.

------------------------------------------------------------------------

# 3. SOURCE-LEVEL LAYOUT TOKENS

The supplied Seller HTML exposes these base layout values:

``` css
--base-layout-wrapper-min-width: 1264px;
--base-layout-width: 1216px;
--base-layout-padding: 24px;
```

Project interpretation:

``` css
--oz-layout-min-width: 1264px;
--oz-content-width: 1216px;
--oz-page-padding: 24px;
```

Use the same visual grid across pages.

Do not create unrelated left/right page paddings on individual screens.

------------------------------------------------------------------------

# 4. FONT

The supplied HTML uses **Onest** as the main Seller UI font.

Preferred:

``` css
font-family: Onest, Arial, Helvetica, sans-serif;
```

If the project bundles a local Onest asset, prefer the local asset.

Fallback:

``` css
font-family: Onest, Arial, Helvetica, sans-serif;
```

The reference HTML also contains isolated legacy/embedded `Inter`
declarations. These are not the primary Seller design language and
should not become the project's default font.

------------------------------------------------------------------------

# 5. TYPOGRAPHY SCALE

The reference exposes this primary scale:

  Token             Size   Line-height Typical use
  --------------- ------ ------------- -----------------------
  `heading-800`     40px          48px large page heading
  `heading-700`     36px          44px large heading
  `heading-600`     32px          40px major heading
  `heading-500`     28px          36px page title
  `heading-400`     26px          30px large section heading
  `heading-300`     19px          24px section/card heading
  `heading-200`     17px          22px compact heading
  `body-700`        19px          28px large body
  `body-600`        17px          28px emphasized body
  `body-500`        15px          24px primary UI text
  `body-400`        13px          20px secondary/table text
  `body-300`        11px          16px compact metadata

The HTML also contains 12px and 14px usages for specific controls.

### Project mapping

``` text
Page title       → 28/36 or 32/40
Section title    → 19/24
Card title       → 17/22
Main body        → 15/24
Table body       → 13/20
Meta/caption     → 11/16
Compact control  → 12–14px where required
```

Do not enlarge the interface beyond the reference without a functional
reason.

------------------------------------------------------------------------

# 6. CORE COLOR TOKENS

These tokens are directly present in the supplied Seller HTML.

## Main

``` css
--text-500: #070707;
--text-300: rgba(0, 26, 51, 0.6);
--text-200: rgba(42, 73, 100, 0.5490196078431373);

--text-500-inverted: #f8fafd;
--text-300-inverted: rgba(255, 255, 255, 0.6);
--text-200-inverted: rgba(255, 255, 255, 0.47843137254901963);

--icon-600: rgba(2, 24, 43, 0.6862745098039216);
--icon-500: rgba(0, 26, 51, 0.6);
--icon-300: rgba(75, 102, 126, 0.5294117647058824);

--icon-600-inverted: #fff;
--icon-500-inverted: rgba(255, 255, 255, 0.8588235294117647);
--icon-300-inverted: rgba(255, 255, 255, 0.4980392156862745);
--icon-200-inverted: rgba(255, 255, 255, 0.2980392156862745);

--main-900: #070707;
--main-800: #2f3135;
--main-100: #f8fafd;
--main-50: #f8fafd;
--main-0: #fff;

--overlay-paranja: rgba(155, 183, 226, 0.06666666666666667);
--overlay-dimming: rgba(3, 8, 13, 0.23921568627450981);
--main-0-transparent: rgba(255,255,255,0);
--main-50-inverted: rgba(255,255,255,0.11764705882352941);
--main-100-inverted: rgba(255,255,255,0.058823529411764705);
```

## Neutral

``` css
--neutral-600: #253646;
--neutral-500: #667685;
--neutral-400: #768695;
--neutral-300: rgba(94,118,139,0.4588235294117647);
--neutral-200: rgba(95,126,155,0.34901960784313724);
--neutral-150: rgba(124,155,181,0.22745098039215686);
--neutral-150-opaque: #e1e8ee;
--neutral-100: rgba(149,166,182,0.17647058823529413);
--neutral-100-opaque: #eceff2;
--neutral-50: rgba(171,188,213,0.11764705882352941);
--neutral-50-opaque: #f5f7fa;
--neutral-25: rgba(255,255,255,0.058823529411764705);
```

## Action / Ozon Blue

``` css
--action-600: #0050e0;
--action-500: #005bff;
--action-400: #0096ff;
--action-300: #74c7fd;
--action-200: rgba(91,186,255,0.4666666666666667);
--action-200-opaque: #b2dfff;
--action-100: rgba(0,148,255,0.1568627450980392);
--action-100-opaque: #d6eeff;
--action-50: rgba(55,175,255,0.09803921568627451);
--action-50-opaque: #ebf7ff;
--action-25: rgba(112,197,255,0.06666666666666667);
--action-25-opaque: #f5fbff;
```

## Success

``` css
--success-600: #007f33;
--success-500: #00b14a;
--success-400: #00c451;
--success-300: #00db5b;
--success-200: rgba(0,225,16,0.4666666666666667);
--success-200-opaque: #87f18f;
--success-100: rgba(5,217,5,0.1568627450980392);
--success-100-opaque: #d7f9d7;
--success-50: rgba(0,235,65,0.09803921568627451);
--success-50-opaque: #e4fdec;
--success-25: rgba(26,255,97,0.06666666666666667);
--success-25-opaque: #effff4;
```

## Warning

``` css
--warning-600: #e17f07;
--warning-500: #f0a000;
--warning-400: #ffa800;
--warning-300: #ffb800;
--warning-200: rgba(254,164,0,0.4627450980392157);
--warning-200-opaque: #ffd540;
--warning-100: rgba(255,161,0,0.1568627450980392);
--warning-100-opaque: #fff0d1;
```

## Alert / Pink

The HTML exposes a separate alert scale:

``` css
--alert-600: #cd066a;
--alert-500: #f1117e;
--alert-400: #fb3d8b;
--alert-300: #fda5be;
--alert-200: rgba(255,146,174,0.4666666666666667);
--alert-200-opaque: #ffccd9;
--alert-100: rgba(255,105,142,0.1568627450980392);
--alert-100-opaque: #ffe7ed;
--alert-50: rgba(255,145,175,0.09803921568627451);
--alert-50-opaque: #fff4f7;
--alert-25: rgba(255,155,183,0.06666666666666667);
--alert-25-opaque: #fff8fa;
```

Use only for UI states that semantically require this alert family.

------------------------------------------------------------------------

# 7. ADDITIONAL PALETTE FROM THE SECOND REFERENCE

The second supplied HTML exposes an additional legacy/UI palette:

``` css
--ui-color-blue-bg: #e9f0fd;
--ui-color-blue-light: #92b4f6;
--ui-color-blue: #216bff;
--ui-color-blue-dark: #1849a9;

--ui-color-green-bg: #dffae8;
--ui-color-green-light: #93ddac;
--ui-color-green: #3ac267;
--ui-color-green-dark: #268045;

--ui-color-yellow-bg: #fff7d1;
--ui-color-yellow-light: #ffed8a;
--ui-color-yellow: #ffd900;
--ui-color-yellow-dark: #e59900;

--ui-color-red-bg: #fde5ec;
--ui-color-red-light: #f47b9f;
--ui-color-red: #df2059;
--ui-color-red-dark: #861313;

--ui-color-gray-white: #f5f7fa;
--ui-color-gray-light: #e6e9f0;
--ui-color-gray: #d4d9e2;
--ui-color-gray-dark: #8d95a5;
--ui-color-white: #fff;
--ui-color-black-light: #48556e;
--ui-color-black: #172133;

--ui-color-purple: #a57bf1;
--ui-color-azure: #44a9e3;
--ui-color-blues: #337cff;
--ui-color-verdant: #3ac267;
--ui-color-amber: #ffd900;
--ui-color-premium: #012250;
--ui-color-rosy: #d69ab7;
--ui-color-aquamarine: #06ca99;
```

### Priority rule

For new Ozon Manager components:

1.  prefer the current semantic `action/success/warning/alert/neutral`
    tokens above;
2.  use the additional `ui-color-*` family only when reproducing a
    specific visual pattern from the second reference.

Do not randomly mix both palettes.

------------------------------------------------------------------------

# 8. OPACITY TOKENS

The second reference exposes:

``` css
--opacity-50: 5%;
--opacity-100: 10%;
--opacity-200: 25%;
--opacity-300: 50%;
--opacity-400: 75%;
--opacity-500: 100%;
```

These are utility opacity levels, not independent colors.

------------------------------------------------------------------------

# 9. ELEVATION / SHADOW

The references contain the following elevation hierarchy.

``` css
--shadowToken-100:
    0 0 2px rgba(0,0,0,.12);

--elevation-200:
    0 0 4px 0 var(--neutral-50),
    0 4px 10px 0 var(--neutral-150);

--elevation-200-top:
    0 0 4px 0 var(--neutral-50),
    0 -4px 10px 0 var(--neutral-150);

--elevation-300:
    0 0 4px 0 var(--neutral-50),
    0 0 24px 0 var(--neutral-150);

--elevation-500:
    0 0 4px 0 var(--neutral-50),
    0 8px 16px -2px var(--neutral-150);

--elevation-500-left:
    0 0 4px 0 var(--neutral-50),
    -8px 0 16px -2px var(--neutral-150);

--elevation-500-right:
    0 0 4px 0 var(--neutral-50),
    8px 0 16px -2px var(--neutral-150);

--elevation-500-top:
    0 0 4px 0 var(--neutral-50),
    0 -8px 16px -2px var(--neutral-150);

--elevation-900:
    0 0 4px 0 var(--neutral-50),
    0 16px 24px -2px var(--neutral-150);
```

### Mapping

``` text
elevation-200 → small floating/control surface
elevation-300 → popover/dropdown
elevation-500 → larger floating surface
elevation-900 → dialog / major overlay
```

Avoid strong shadows on ordinary cards.

------------------------------------------------------------------------

# 10. RADIUS SCALE

The source contains these radii:

``` text
1px
2px
3px
4px
5px
6px
8px
12px
16px
18px
20px
24px
28px
32px
50px
128px
50%
100%
```

Project semantic mapping:

``` css
--oz-radius-xs: 4px;
--oz-radius-sm: 6px;
--oz-radius-control: 8px;
--oz-radius-md: 12px;
--oz-radius-card: 16px;
--oz-radius-lg: 20px;
--oz-radius-xl: 24px;
--oz-radius-pill: 128px;
```

Use the smaller radii for controls and compact surfaces, larger radii
for cards/dialogs.

------------------------------------------------------------------------

# 11. FOCUS / ACTIVE BORDER STATES

The source repeatedly uses inset borders and action-colored focus rings.

Reference patterns:

``` css
box-shadow:
    inset 0 0 0 2px var(--action-500);
```

and:

``` css
box-shadow:
    inset 0 0 0 2px var(--action-500),
    0 0 0 4px var(--action-50);
```

Project rule:

-   active controls → action border;
-   keyboard focus → visible action ring;
-   selected containers → action border + subtle action surface where
    appropriate;
-   do not remove focus indication.

------------------------------------------------------------------------

# 12. CONTAINERS / CARDS

Default application surface:

``` css
background: var(--main-0);
border-radius: var(--oz-radius-card);
```

Optional border:

``` css
border: 1px solid var(--neutral-150);
```

Card padding should generally use:

``` text
16px
20px
24px
```

depending on density.

Do not turn every data item into a large card. Seller's visual language
is information-dense.

------------------------------------------------------------------------

# 13. APPLICATION SHELL

Target structure:

``` text
┌──────────────────────────────────────────────────────┐
│ application/header                                   │
├───────────────┬──────────────────────────────────────┤
│ navigation    │ main workspace                       │
│               │                                      │
│               │ page header                          │
│               │ toolbar                              │
│               │ content                              │
│               │                                      │
└───────────────┴──────────────────────────────────────┘
```

Rules:

-   navigation is visually stable;
-   main workspace uses the neutral light background;
-   content surfaces are primarily white;
-   page content aligns to the common layout grid;
-   navigation active state uses the action family;
-   avoid visual clutter.

------------------------------------------------------------------------

# 14. SIDEBAR / NAVIGATION

Navigation item pattern:

``` text
[icon]  Label
```

Optional:

``` text
[icon] Label                 [counter]
```

States:

``` text
default
hover
active
disabled
```

Active:

-   stronger text/icon;
-   subtle action background;
-   action accent;
-   rounded item.

Do not use a full saturated blue rectangle for every active navigation
item.

------------------------------------------------------------------------

# 15. PAGE HEADER

Recommended:

``` text
Page title
Context / subtitle

                         secondary actions
                         primary action
```

Page title:

``` text
28/36 or 32/40
weight 600–700
```

Secondary information:

``` text
13/20 or 15/24
text-300
```

------------------------------------------------------------------------

# 16. TOOLBAR

Toolbar should be compact and aligned:

``` text
[Search] [Filter] [Sort] [Other controls]          [Primary action]
```

All controls in one toolbar should have compatible heights.

Use white/neutral controls with subtle borders.

Do not turn the toolbar into a second page header.

------------------------------------------------------------------------

# 17. BUTTON SYSTEM

## Primary

``` css
background: var(--action-500);
color: var(--text-500-inverted);
```

Hover:

``` css
background: var(--action-600);
```

## Secondary

Use action-soft surface:

``` css
background: var(--action-50);
color: var(--action-500);
```

Hover:

``` css
background: var(--action-100);
```

## Tertiary / text

Use text/icon colors and action color only for the interactive emphasis.

Every button should support:

``` text
default
hover
pressed
focus
disabled
loading
```

------------------------------------------------------------------------

# 18. INPUT SYSTEM

Input:

``` text
white/neutral surface
thin neutral border
8px radius
```

Placeholder:

``` css
color: var(--text-200);
```

Focus:

``` css
border: action
box-shadow: action focus ring
```

Search:

``` text
[search icon] Search
```

Do not use giant inputs.

------------------------------------------------------------------------

# 19. SELECT / DROPDOWN

Dropdown surface:

``` css
background: #fff;
border-radius: 8–12px;
box-shadow: var(--elevation-300);
```

Menu item:

``` text
normal
hover
selected
disabled
```

Selected item should use subtle action emphasis, not excessive
saturation.

------------------------------------------------------------------------

# 20. POPOVER / FILTER MENU

For the project's existing right-click table filter:

``` text
right-click column header
        ↓
popover
        ↓
filter input
        ↓
Enter = apply
Esc = close
```

Visual requirements:

-   white;
-   8--12px radius;
-   elevation-300;
-   compact padding;
-   clear input focus;
-   action state for applied filter.

The interaction must remain unchanged.

------------------------------------------------------------------------

# 21. TABLE SYSTEM

All tables in Ozon Manager must use the same visual foundation:

-   Candidates;
-   Participants;
-   Auto-Add;
-   Products;
-   Price management;
-   History;
-   Rollback;
-   future operational tables.

### Table shell

``` css
background: #fff;
border-radius: 16px;
```

### Header

-   muted but readable;
-   13/20 or 15/20 typography;
-   sorting indicator;
-   filter affordance;
-   compact vertical density.

### Row

-   white by default;
-   subtle separator;
-   hover overlay;
-   selected state;
-   disabled state if applicable.

### Selected

Use action-soft background or action inset border.

### Numeric

Right-align where semantically appropriate.

Use stable numeric formatting.

------------------------------------------------------------------------

# 22. TABLE INTERACTION CONTRACT

The current project already has important table behavior. Design changes
must not break it.

Preserve:

-   checkbox-only selection;
-   clicking ordinary cells does not accidentally select;
-   Shift-click visible range;
-   text selection with mouse;
-   Ctrl+C copy;
-   header sorting;
-   numeric sorting;
-   right-click filtering;
-   Enter to apply filter;
-   Esc to close filter.

Visual states must make these interactions understandable.

------------------------------------------------------------------------

# 23. PRODUCT TABLE

Preferred product hierarchy:

``` text
[checkbox]
[product image]
Product name
secondary ID/meta
```

Then:

``` text
Price
Action
Status
```

Product name is more visually important than technical IDs.

IDs:

``` text
Product ID
SKU
Offer ID
```

should be secondary metadata.

------------------------------------------------------------------------

# 24. PRICE PRESENTATION

Prices are operationally important and should be visually prominent.

Recommended:

``` text
1 080 ₽
981 ₽
```

Delta:

``` text
-99 ₽
+5%
```

Do not visually hide the old price when comparison is necessary.

Use locale-consistent formatting.

------------------------------------------------------------------------

# 25. BADGES / TAGS

Badges are compact semantic surfaces.

Examples:

``` text
ACTIVE
PREVIEW
DRY RUN
SUCCESS
PARTIAL
FAILED
UNKNOWN
```

General form:

``` text
small text
medium/semibold weight
rounded
semantic soft background
semantic text
```

Do not use highly saturated backgrounds for every badge.

------------------------------------------------------------------------

# 26. STATUS COLORS

### Information

``` css
background: var(--action-50-opaque);
```

### Success

``` css
background: var(--success-25-opaque);
```

### Warning

``` css
background: var(--warning-25-opaque);
```

### Error

Use the alert/negative semantic family available in the reference.

Status should never be communicated by color alone.

------------------------------------------------------------------------

# 27. DIALOG

Reference behavior uses high elevation.

``` css
background: #fff;
border-radius: 20–24px;
box-shadow: var(--elevation-900);
```

Structure:

``` text
Title                                      Close
------------------------------------------------
content

------------------------------------------------
Cancel                         Primary action
```

Internal padding:

``` text
24px
```

Dialog must support focus and keyboard close where applicable.

------------------------------------------------------------------------

# 28. OVERLAY

Reference dimming:

``` css
--overlay-dimming: rgba(3,8,13,0.23921568627450981);
```

Use this as the basis for dialogs/major overlays.

Do not over-darken the application.

------------------------------------------------------------------------

# 29. DRAWER / SIDE PAGE

Use:

-   white surface;
-   elevation-500/900 as appropriate;
-   clear close;
-   16--24px internal padding;
-   same typography and controls as main workspace.

------------------------------------------------------------------------

# 30. SKELETON / LOADING

The source includes loading/skeleton patterns.

Skeleton should:

-   use neutral-50/100 surfaces;
-   preserve approximate final geometry;
-   avoid layout jumping;
-   be used for large product/table loads.

Do not show an empty white page during a known loading operation.

------------------------------------------------------------------------

# 31. EMPTY STATE

Structure:

``` text
icon/illustration
title
short explanation
optional action
```

Keep it compact.

------------------------------------------------------------------------

# 32. ERROR STATE

Structure:

``` text
semantic error icon
short title
human-readable explanation
recovery action
optional technical detail
```

Never expose:

-   API keys;
-   Client IDs where not necessary;
-   credentials;
-   environment variables;
-   raw secret-bearing traceback.

------------------------------------------------------------------------

# 33. NOTIFICATIONS / TOASTS

The second reference exposes high z-index notification/popup layers:

``` css
--z-index-notification: 11000;
--z-index-popup: 9000;
--z-index-window: 9000;
--z-index-side-page: 8000;
```

Project semantic layers:

``` css
--oz-z-side-page: 8000;
--oz-z-popup: 9000;
--oz-z-window: 9000;
--oz-z-notification: 11000;
```

Do not arbitrarily create new z-index values.

------------------------------------------------------------------------

# 34. PRODUCT IMAGE

Product imagery should be:

-   clean;
-   contained;
-   consistent aspect ratio;
-   rounded according to the reference style;
-   never allowed to dominate table rows.

Use a fallback placeholder for missing images.

------------------------------------------------------------------------

# 35. PRODUCT DETAIL / FUTURE DRAWER

Not yet required for the current application, but future implementation
must use:

``` text
image
name
offer/product identifiers
current price
action price
status
metadata
actions
```

The detail surface should be visually consistent with Seller
cards/dialogs.

------------------------------------------------------------------------

# 36. PROMOTIONS SCREEN

Current promotion UI should evolve toward:

``` text
Page title
Promotion context
Toolbar
Candidates / Participants / Auto-Add controls
Table
```

Do not expose raw technical API structure as the primary UI.

------------------------------------------------------------------------

# 37. AUTO-ADD SCREEN

Current functional areas:

``` text
Candidates
Participants
Auto-Add
```

All three tables must share the same table component.

Auto-Add values received from Ozon must be displayed as supplied by the
API unless a separate business rule explicitly defines a transformation.

------------------------------------------------------------------------

# 38. PRICE MANAGER --- FUTURE UI

For future price operations:

``` text
Page header
↓
selection/filter toolbar
↓
selected count
↓
operation controls
↓
preview table
↓
fresh check
↓
snapshot status
↓
confirmation
↓
result
```

Visual hierarchy:

``` text
old price → operation → new price
```

Safety Floor should have an explicit visual state.

------------------------------------------------------------------------

# 39. PREVIEW

Preview is a safety checkpoint.

Recommended structure:

``` text
Preview

Selected: 120 products

Old price → New price

Operation: +5%
Rounding: ...
Safety Floor: ...

[Cancel] [Continue]
```

It should look deliberate and clearly separate from ordinary browsing.

------------------------------------------------------------------------

# 40. FRESH CHECK

Normal:

``` text
✓ Prices unchanged
```

Changed:

``` text
⚠ Prices changed
Refresh and recalculate required
```

A mismatch must be visually prominent.

------------------------------------------------------------------------

# 41. SNAPSHOT

Snapshot status:

``` text
Snapshot created
Operation ID
Products: N
Timestamp
```

Blocking condition:

``` text
Snapshot unavailable
Mutation disabled
```

------------------------------------------------------------------------

# 42. HISTORY

History table:

``` text
Timestamp
Operation
Type/value
Products
Success
Failed
Status
Snapshot
```

Use semantic status badges.

------------------------------------------------------------------------

# 43. ROLLBACK

Rollback is a mutation and must use the same visual safety language:

``` text
Select snapshot
↓
Preview
↓
Fresh Check
↓
Confirmation
↓
Mutation
↓
Result
```

Each stage should be visually explicit.

------------------------------------------------------------------------

# 44. DENSITY

Seller's interface is dense enough to operate on many records.

Project rules:

-   avoid oversized cards;
-   avoid excessive vertical whitespace;
-   keep table rows compact;
-   keep controls readable;
-   allow many products to remain visible simultaneously.

------------------------------------------------------------------------

# 45. SPACING SCALE

Use the reference-oriented spacing vocabulary:

``` text
2
4
6
8
10
12
14
16
20
24
28
32
40
48
```

Preferred:

``` text
icon ↔ label       6–8px
control padding    8–16px
card padding       16–24px
section gap        24–32px
major section      32–48px
```

Avoid arbitrary values unless a source-derived component requires them.

------------------------------------------------------------------------

# 46. RESPONSIVE BEHAVIOR

The supplied references are desktop-first.

Desktop is the primary target.

For narrower widths:

-   preserve the design tokens;
-   allow table horizontal scrolling;
-   wrap toolbar controls;
-   stack cards when necessary;
-   keep sidebar behavior consistent.

Do not invent a separate mobile visual language unless a mobile
reference is supplied.

------------------------------------------------------------------------

# 47. ICONS

Use a coherent icon family.

Icon states:

``` text
default
hover
active
disabled
semantic
```

Do not use emoji as UI icons.

Do not mix visually incompatible icon libraries without a reason.

------------------------------------------------------------------------

# 48. ACCESSIBILITY

Preserve:

-   keyboard navigation;
-   visible focus;
-   semantic buttons/inputs;
-   sufficient contrast;
-   readable text;
-   non-color-only status;
-   usable target sizes.

Focus should use the reference action ring.

------------------------------------------------------------------------

# 49. SECURITY UI

Credentials are never visual content.

Never render API keys in:

-   tables;
-   logs;
-   dialogs;
-   toasts;
-   errors;
-   history;
-   screenshots.

Masked input is required for secret fields.

------------------------------------------------------------------------

# 50. STREAMLIT RULE

Streamlit defaults are **not** the project's visual source of truth.

Architecture:

``` text
Ozon Seller Design System
        ↓
Project UI component layer
        ↓
Streamlit rendering
```

Where Streamlit defaults conflict with this specification, use the
project's custom CSS/HTML component layer.

Do not let default Streamlit widgets reintroduce generic Streamlit
appearance.

------------------------------------------------------------------------

# 51. SHARED COMPONENT ARCHITECTURE

Preferred component vocabulary:

``` text
OzonAppShell
OzonSidebar
OzonPageHeader
OzonToolbar
OzonButton
OzonInput
OzonSelect
OzonCheckbox
OzonBadge
OzonStatus
OzonCard
OzonTable
OzonFilterPopover
OzonDialog
OzonDrawer
OzonToast
OzonSkeleton
OzonEmptyState
OzonErrorState
```

If an equivalent project component already exists, extend it rather than
creating a visually competing duplicate.

------------------------------------------------------------------------

# 52. TABLE COMPONENT IS A SINGLE DESIGN SYSTEM

The same visual component must power:

``` text
Candidates
Participants
Auto-Add
Products
Price Manager
History
Rollback
Future bulk operations
```

Only data/configuration/actions should change.

The visual language must not fork.

------------------------------------------------------------------------

# 53. STATES FOR EVERY COMPONENT

Every interactive component should consider:

``` text
default
hover
active
pressed
focus
selected
disabled
loading
error
```

Only implement states relevant to the component, but do not omit
focus/disabled states.

------------------------------------------------------------------------

# 54. DESIGN OF FUTURE, CURRENTLY UNIMPLEMENTED FEATURES

The following are explicitly included in the design specification even
if they are not currently implemented:

-   Products screen;
-   stock/inventory screen;
-   bulk price management;
-   percentage operation;
-   absolute ₽ operation;
-   exact price;
-   rounding selector;
-   Safety Floor;
-   Preview;
-   Fresh Check;
-   Snapshot viewer;
-   rollback wizard;
-   operation history details;
-   partial failure viewer;
-   reconciliation UI;
-   Dry Run;
-   API diagnostics;
-   account settings;
-   product detail drawer;
-   advanced filters;
-   pagination;
-   loading skeletons;
-   empty/error states;
-   confirmation dialogs;
-   notification system.

They must all use this design system when implemented.

------------------------------------------------------------------------

# 55. DO NOT

Do not introduce:

-   random colors;
-   random radii;
-   arbitrary shadows;
-   gradients without source support;
-   glassmorphism;
-   neon styling;
-   generic Bootstrap styling;
-   generic Material styling;
-   generic dashboard styling;
-   oversized buttons;
-   oversized table rows;
-   unrelated typography;
-   emoji as UI icons;
-   a different table design for each screen;
-   technical IDs visually larger than product names;
-   red primary actions without semantic justification.

------------------------------------------------------------------------

# 56. DESIGN TOKENS FOR PROJECT CSS

Recommended normalized project aliases:

``` css
:root {
    --oz-font: Onest, Arial, Helvetica, sans-serif;

    --oz-bg: #f8fafd;
    --oz-surface: #ffffff;

    --oz-text-primary: #070707;
    --oz-text-secondary: rgba(0,26,51,.6);
    --oz-text-tertiary: rgba(42,73,100,.5490196078);

    --oz-action: #005bff;
    --oz-action-hover: #0050e0;
    --oz-action-light: #0096ff;
    --oz-action-soft: rgba(55,175,255,.0980392157);

    --oz-border: rgba(124,155,181,.2274509804);

    --oz-success: #00b14a;
    --oz-warning: #f0a000;
    --oz-alert: #f1117e;

    --oz-radius-control: 8px;
    --oz-radius-card: 16px;
    --oz-radius-dialog: 20px;
    --oz-radius-large: 24px;
    --oz-radius-pill: 128px;

    --oz-shadow-small:
        0 0 2px rgba(0,0,0,.12);

    --oz-shadow-popover:
        0 0 4px 0 var(--neutral-50),
        0 0 24px 0 var(--neutral-150);

    --oz-shadow-dialog:
        0 0 4px 0 var(--neutral-50),
        0 16px 24px -2px var(--neutral-150);
}
```

These aliases are for project implementation; the source tokens above
remain the reference vocabulary.

------------------------------------------------------------------------

# 57. DESIGN REVIEW CHECKLIST

Before declaring a UI stage complete:

## Typography

-   [ ] Onest
-   [ ] correct scale
-   [ ] correct line-height
-   [ ] correct hierarchy

## Color

-   [ ] source-derived tokens
-   [ ] semantic states
-   [ ] no arbitrary palette

## Layout

-   [ ] 24px page padding where applicable
-   [ ] common content alignment
-   [ ] consistent density
-   [ ] no accidental oversized gaps

## Components

-   [ ] correct radius
-   [ ] correct borders
-   [ ] correct elevation
-   [ ] hover
-   [ ] active
-   [ ] focus
-   [ ] disabled
-   [ ] loading where applicable

## Tables

-   [ ] shared visual table
-   [ ] sorting
-   [ ] filtering
-   [ ] selection
-   [ ] Shift selection
-   [ ] text copy
-   [ ] hover
-   [ ] selected
-   [ ] loading
-   [ ] empty
-   [ ] error

## Accessibility

-   [ ] keyboard
-   [ ] focus
-   [ ] contrast
-   [ ] status not communicated by color alone

------------------------------------------------------------------------

# 58. SOURCE FIDELITY

This specification is derived from the supplied HTML.

When a future component is not represented by the references:

1.  do not claim that its exact appearance is source-proven;
2.  reuse the nearest source-derived token and component pattern;
3.  keep the component visually consistent;
4.  mark genuinely new visual behavior as project adaptation.

Do not silently invent a new visual system.

------------------------------------------------------------------------

# 59. WHAT MUST NOT BE COPIED FROM THE HTML

The HTML is a visual reference, not a license to copy application
internals.

Do not copy into Ozon Manager:

-   hashed CSS class names;
-   React/Vue internals;
-   bundled JavaScript;
-   tracking;
-   analytics;
-   private application implementation;
-   Ozon API behavior from page internals;
-   credentials;
-   unrelated third-party code.

Use only the design information required to reproduce the visual
language.

------------------------------------------------------------------------

# 60. FINAL RULE

**Every future UI addition to Ozon Manager must look as though it
belongs to the same Ozon Seller product family represented by the two
supplied references.**

The project should evolve like this:

``` text
Existing Ozon Manager functionality
            +
Ozon Seller visual system
            ↓
One coherent product
```

Never:

``` text
Existing product
+
new feature
+
new independent visual style
```

------------------------------------------------------------------------

# 61. ACCEPTANCE CRITERIA

The UI design stage is visually compliant when:

1.  Onest is the primary typography;
2.  layout follows the reference desktop grid;
3.  white surfaces and light neutral workspace are consistent;
4.  action blue follows the source palette;
5.  cards/dialogs use the source radius/elevation language;
6.  all operational tables share one design;
7.  controls have explicit interactive states;
8.  future screens can be implemented from the same tokens;
9.  no arbitrary visual palette has appeared;
10. visual changes have not altered business/API behavior.

------------------------------------------------------------------------

## END OF MASTER DESIGN SPECIFICATION

---

# Project implementation addendum — 2026-10-03

The current Ozon Manager implementation follows the design-system direction for dialogs and overlays with a centered loading modal used for long-running operations.

## Loading modal contract

- full-screen dimming layer;
- centered white modal surface;
- Onest typography;
- Ozon-blue progress spinner;
- operation title plus current step text;
- interaction is visually blocked while the operation is executing;
- the overlay is presentation-only and never replaces Preview, Fresh Check, Snapshot, Confirmation or read-after-write safety gates.

The shared implementation is `_loading_overlay()` in `app/ui/streamlit_app.py`. It is used for connection checks, Ozon data reads, Product Card enrichment, reconciliation, rollback, REMOVE, ADD and Participant UPDATE workflows.

## Participant UPDATE controls

The Participant UPDATE dialog adds a compact global percentage control using the existing Seller-style control language. It provides predefined convenience choices plus a manual value (`Другое`). These choices are UI conveniences, not Ozon API limits. Validation remains product-specific and is performed before the package is changed.


# Project implementation addendum — 2026-10-04

- This design system remains the mandatory UI source of truth for the current Ozon Manager release.
- The 2026-10-04 update is documentation-only; no UI implementation was changed.
- Current UI regression suite: **256 passed, 1 skipped**; `compileall`: **PASS**.
- Existing table scrolling, sticky headers, filtering, selection and viewport constraints remain part of the current implementation contract.
