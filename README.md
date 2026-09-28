# COMEDK Compass: Navigate Your Future

You are a world-class product designer and senior frontend engineer.

Build the frontend for a premium product called **COMEDK Compass** — a modern, data-driven counselling and college discovery platform for COMEDK engineering aspirants in Karnataka.

IMPORTANT:

* This is a FRONTEND-FIRST build.
* Do not build a generic dashboard template.
* Do not make it look like an AI chatbot website.
* Do not overuse gradients, glassmorphism, glowing borders, or meaningless animations.
* The product should feel like a serious combination of **Linear + Vercel + modern fintech analytics + high-end education product**.
* Every screen must feel intentionally designed.
* Use realistic COMEDK-specific data throughout the UI.
* All data can initially be mocked locally with TypeScript objects.
* Structure the code so the mock data can later be replaced with a real database/API without redesigning the components.

## PRODUCT PURPOSE

COMEDK Compass helps students:

1. Estimate probable rank from marks.
2. Enter their rank and discover realistic colleges/branches.
3. Explore historical cutoff trends.
4. Compare colleges.
5. Filter colleges according to budget.
6. Understand round-wise admission chances.
7. Build a counselling preference list.
8. See college fees, placements, ROI and student-verified information.
9. Eventually receive upgrade/branch-switch guidance.

The most important differentiator is **ROUND-WISE COUNSELLING INTELLIGENCE**.

A student shouldn't only see:

"RNSIT CSE — cutoff 18,432"

Instead they should eventually see something like:

Round 1 → unlikely
Round 2 → possible
Round 3 → strong possibility
Round 4 → historically favorable

Make the UI architecture capable of presenting this kind of information beautifully.

---

# TECH STACK

Use:

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui where appropriate
* Lucide icons
* Recharts for charts
* Framer Motion for animations
* Responsive design
* Dark + light mode
* Component-driven architecture

Keep dependencies reasonable.

Do NOT introduce unnecessary libraries.

---

# DESIGN DIRECTION

Visual personality:

**"Mission control for college counselling."**

The user should feel like they are operating a sophisticated decision-support system rather than browsing an education blog.

Design principles:

* Extremely clean typography
* Strong visual hierarchy
* Lots of intentional whitespace
* Dense information where useful
* Beautiful data visualization
* Subtle borders
* Soft shadows
* Carefully controlled color palette
* Excellent hover states
* Smooth page transitions
* Micro-interactions
* No visual clutter

Primary colors should feel academic + technical.

Use a restrained neutral foundation with one strong accent color.

Use semantic colors only when communicating meaning:

Green → strong/positive
Amber → uncertain
Red → unlikely/risk
Blue → information
Purple → AI/insight

Do not turn every card into a colorful gradient.

---

# BRAND

Name:

**COMEDK Compass**

Possible tagline:

**"Navigate counselling with data, not guesswork."**

Logo should be simple and modern.

Create a small compass-inspired mark using CSS/SVG.

---

# GLOBAL NAVIGATION

Desktop navbar:

Left:

* Compass logo
* COMEDK Compass

Navigation:

* Explore
* Predictor
* Colleges
* Cutoffs
* Compare
* Counselling

Right:

* Search
* "My Profile"
* Theme toggle

Mobile:

* compact navbar
* hamburger menu
* bottom navigation where appropriate

Navbar should become slightly elevated/sticky while scrolling.

---

# LANDING PAGE

Build an exceptional landing page.

Hero section:

Small eyebrow:

COMEDK 2026 COUNSELLING INTELLIGENCE

Headline:

**Stop guessing your college.
Start navigating it.**

Supporting text:

"Explore historical cutoffs, admission probabilities, fees, placements and counselling trends — all in one place."

Primary CTA:

**Find My Colleges →**

Secondary CTA:

**Explore Cutoffs**

Below the hero, create an interactive mini predictor panel.

Example:

YOUR RANK

`18,432`

Stream:
Engineering

Button:
`Show my options`

When clicked, animate into a results preview.

---

# HERO VISUAL

Do NOT use a stock illustration.

Create a sophisticated interactive visualization showing:

Student Rank
↓
Possible Colleges
↓
Branches
↓
Counselling Rounds

Use animated nodes/lines.

Example:

18,432 Rank
↓
┌─────────────────────┐
│  12 Possible Colleges│
└─────────────────────┘
↓
CSE · AIML · ISE · ECE

Use Framer Motion for subtle movement.

---

# LANDING PAGE SECTIONS

After hero:

### 1. "Your rank is only the beginning."

Show 4 feature cards:

Rank Predictor
Cutoff Intelligence
Round Probability
College Comparison

Each card should have a mini visualization.

---

### 2. LIVE COUNSELLING SNAPSHOT

Create a dashboard-style section.

Show:

Current counselling phase
Latest round
Last updated
Total colleges tracked
Branches tracked

Example:

ROUND 3

Counselling status

`ACTIVE`

Last updated:
Today, 10:42 AM

---

### 3. CUT-OFF TREND VISUALIZATION

Beautiful interactive line chart.

Example college:

RNS Institute of Technology

Branch:

Computer Science & Engineering

Chart:

2022
2023
2024
2025
2026

Show historical closing rank.

Allow switching:

* CSE
* AIML
* ISE
* ECE

---

### 4. ROUND-WISE PROBABILITY

This section should visually demonstrate the killer feature.

Example:

RNSIT
Computer Science & Engineering

Your rank:
18,432

Round 1
12%

Round 2
27%

Round 3
61%

Round 4
78%

Display as a beautiful probability timeline.

Important:

Never present predictions as guaranteed outcomes.

Use wording like:

"Historical probability"

"Estimated"

"Based on previous counselling rounds"

---

### 5. COLLEGE DISCOVERY

Create a horizontal/vertical collection of premium college cards.

Each card:

College logo placeholder
College name
Location
Latest cutoff
Median package
Fees
Admission probability
Verified data badge

Example:

R.V. College of Engineering

Bengaluru

CSE

Closing Rank:
1,842

Median Package:
₹16.2 LPA

Estimated chance:
Low

---

### 6. COMPARE COLLEGES

Create a polished comparison preview.

Example:

RVCE
vs
BMSCE
vs
RNSIT

Metrics:

Cutoff
Fees
Median Package
ROI
Location
Campus
Student verified data

Use visual bars instead of a boring spreadsheet.

---

### 7. TRUST / DATA SOURCES

Very important.

The product's advantage is trustworthy structured data.

Create section:

**Every number has a source.**

Show source badges:

Official COMEDK
Verified Student
Historical Data
Institution Source

Every important number should have a small source indicator.

---

### 8. STUDENT CONTRIBUTIONS

Create a section:

**Know something we don't?**

"Help future COMEDK students make better decisions."

CTA:

**Contribute verified data →**

Show:

✓ College fees
✓ Hostel fees
✓ Placement data
✓ Student experience

---

### 9. FINAL CTA

Large closing section:

**Your counselling journey shouldn't be a guessing game.**

Buttons:

Find My Colleges
Explore Cutoffs

---

# MAIN APP DASHBOARD

Create `/dashboard`.

This should feel like the student's personal counselling command center.

Top:

Good morning, Student 👋

Your counselling profile

Rank:
18,432

Preferred branches:
CSE, AIML, ISE

Budget:
₹4L–₹8L

---

## DASHBOARD SECTIONS

### Admission Overview

Cards:

Possible Colleges
12

Strong Matches
4

Reach Colleges
3

Safe Options
5

---

### Your Shortlist

College cards with probability indicators.

---

### Counselling Timeline

Visual timeline:

Round 1
↓
Round 2
↓
Round 3
↓
Round 4

Show current status.

---

### Recommended Actions

Example:

"Round 3 results are approaching."

"3 colleges in your shortlist historically see significant movement in Round 3."

CTA:

View round trends

---

# PREDICTOR PAGE

Route:

`/predictor`

Create a beautiful two-step interface.

Step 1:

Enter marks

Physics
Chemistry
Mathematics

OR

Enter rank directly.

Step 2:

Show estimated rank range.

Example:

Estimated rank

**16,800 – 19,400**

Confidence:

Moderate

Then:

**Explore colleges for this rank →**

Important UI:

Do NOT show fake precision.

Use ranges.

---

# COLLEGES PAGE

Route:

`/colleges`

Create a powerful discovery interface.

Left filter panel:

Rank
Budget
Branch
Location
College type
Hostel
Placement range

Main area:

Results.

Each college card should show:

Name
Location
Branches
Cutoff
Fees
Median package
ROI
Probability
Verification status

Include sorting:

Recommended
Cutoff
Fees
Placement
ROI

---

# COLLEGE DETAIL PAGE

Route:

`/colleges/[slug]`

This page should be one of the most polished pages.

Header:

College logo

RNS Institute of Technology

Bengaluru, Karnataka

Verified data badge

Buttons:

Add to shortlist
Compare

---

## College Overview

Stats:

Median Package
₹8.5 LPA

Annual Fee
₹2.2L

Hostel
₹1.2L

Established
1963

---

## Branch Cutoffs

Interactive table.

Columns:

Branch
R1
R2
R3
R4
Trend

Rows:

CSE
AIML
ISE
ECE
EEE

---

## CUTOFF TREND

Large interactive chart.

Toggle:

Opening Rank
Closing Rank

Year:

2022 → 2026

---

## ROUND PROBABILITY

Student rank input.

Example:

Your rank:

18,432

Then show historical estimated probability for each round.

---

## FEES

Break down:

College fee
Hostel
Other fees
Estimated total

Show source.

---

## PLACEMENTS

Charts:

Median package
Average package
Highest package

Clearly show:

Source
Year

Never mix years without displaying the year.

---

## VERIFIED STUDENT DATA

Dedicated section.

Example:

Verified student submission

Batch:
2025

Branch:
AIML

✓ Verified student

"Confirmed by 7 students"

Show fee and placement submissions.

If data conflicts:

⚠ Data discrepancy

Official source:
₹2.1L

Student submissions:
₹2.3L–₹2.4L

Do NOT silently choose one.

---

# COMPARE PAGE

Route:

`/compare`

Allow 2–3 colleges.

Build a visually excellent comparison table.

Sticky college headers.

Rows:

Admission
Cutoff
Fees
Hostel
Placement
ROI
Location
Campus
Verified data

Add a radar/chart visualization if useful.

---

# CUTOFFS PAGE

Route:

`/cutoffs`

This should feel like a data exploration tool.

Controls:

Year
Round
Branch
College
Category

Large table.

Columns:

College
Branch
Round 1
Round 2
Round 3
Round 4
Trend

Clicking a row opens detailed historical data.

---

# COUNSELLING PAGE

Route:

`/counselling`

Make this feel like the "mission control" screen.

Top:

COMEDK Counselling 2026

Current phase:

ROUND 3

Countdown-style component:

Next important event

Then:

### Your Counselling Strategy

Based on the user's rank and shortlist.

Sections:

Safe
Target
Reach

Each college has:

Current cutoff
Your rank
Historical movement
Round probability

---

# PREFERENCE LIST BUILDER

Route:

`/preference-list`

Drag-and-drop interface.

Example:

01 — RVCE CSE
02 — BMSCE CSE
03 — RNSIT CSE
04 — BMSCE AIML
05 — BMSIT AIML

Allow:

Drag
Reorder
Remove
Add college

Show:

"Your list contains 18 preferences."

Add a side panel showing:

Coverage
Safe options
Target options
Reach options

Do not claim that the generated list guarantees admission.

---

# SEARCH

Implement a global command palette.

Shortcut:

⌘ K / Ctrl K

Search:

Colleges
Branches
Cutoffs
Pages

Example:

Search "RNSIT CSE"

Results:

RNS Institute of Technology
CSE cutoff
AIML cutoff
College profile

Make this feel like Linear's command palette.

---

# MICRO-INTERACTIONS

Use animations carefully.

Examples:

* Cards subtly lift on hover
* Numbers animate when entering viewport
* Charts animate on load
* Probability bars animate
* Page transitions are subtle
* Filter changes animate results
* Buttons have tactile hover/press states
* Skeleton loaders
* Toast notifications

Avoid excessive animation.

Performance matters.

---

# RESPONSIVE DESIGN

The entire application must work beautifully on:

Desktop
Laptop
Tablet
Mobile

Do not simply shrink desktop components.

For mobile:

* bottom navigation
* horizontally scrollable comparison cards
* collapsible filters
* compact charts
* sticky CTA where appropriate

---

# ACCESSIBILITY

Implement:

* semantic HTML
* keyboard navigation
* visible focus states
* aria labels
* sufficient contrast
* reduced motion support

---

# DATA ARCHITECTURE

Create `/lib/mock-data`.

Create realistic mock datasets:

`colleges.ts`
`cutoffs.ts`
`branches.ts`
`fees.ts`
`placements.ts`
`counselling.ts`
`students.ts`

Create TypeScript interfaces.

Example:

College
CutoffRecord
Branch
FeeRecord
PlacementRecord
ProbabilityRecord
StudentSubmission

Do NOT scatter mock data inside components.

---

# COMPONENT ARCHITECTURE

Create reusable components:

Navbar
CommandPalette
CollegeCard
CollegeLogo
ProbabilityBadge
ProbabilityTimeline
CutoffChart
CutoffTable
StatCard
SourceBadge
VerificationBadge
CollegeComparison
FilterPanel
RankInput
PredictorResult
CounsellingTimeline
PreferenceList
StudentSubmissionCard
EmptyState
LoadingSkeleton

Keep components modular.

---

# IMPORTANT DATA TRUST UX

This is NOT an entertainment website.

Whenever a statistic appears, design space for:

Source
Year
Verification status
Confidence

Example:

₹8.5 LPA
Median package
2025
Source: Student verified × 8

This should be part of the design system.

---

# EMPTY / LOADING / ERROR STATES

Do not ignore these.

Create polished states for:

No colleges found
No cutoff data
Data unavailable
Loading college
Prediction unavailable
No student submissions

Example:

"No verified student data yet."

"Be the first student to contribute."

---

# DARK MODE

Dark mode should not simply invert colors.

Create a genuinely designed dark theme.

Think:

Linear
Vercel
Raycast

Use subtle surfaces and borders.

---

# CODE QUALITY

The code must:

* compile
* be TypeScript-safe
* have no unnecessary `any`
* use reusable components
* use proper routing
* have clean folder structure
* avoid duplicated UI
* keep mock data separate
* be easy to connect to a real backend later

Do not hardcode the same data in multiple places.

---

# MOST IMPORTANT

Before coding, mentally establish the design system.

Then build the application in this order:

1. Global layout
2. Design system
3. Navbar
4. Landing page
5. Dashboard
6. Predictor
7. Colleges
8. College detail
9. Cutoffs
10. Compare
11. Counselling
12. Preference builder
13. Command palette
14. Responsive/mobile polish
15. Dark mode
16. Animations
17. Loading/error/empty states

Do not stop after creating a basic landing page.

The result should feel like a **real startup product ready for a demo**, not a generated template.

Prioritize visual quality, information hierarchy, interaction design and polish.

When finished, ensure all routes are connected and navigable.

Use realistic COMEDK terminology and data examples, but clearly treat mock data as demo data until the real verified dataset is connected.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://comedk-navigator-pro.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/2c795dd4-fea9-4dba-867d-aa9dd5b5fd9a).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
