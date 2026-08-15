# Kaggriculture Comprehensive Strategy & Meta Report

## Executive Summary & Live Ladder Meta
Analysis of live Kaggle ladder datasets (`georgymamarin/kaggriculture-episodes`, `busyaprime/kaggriculture-ladder-meta`, `dariushafshar/kaggriculture-agent-benchmark-18k`) reveals that top-performing ladder bots achieve final scores of **3,130 to 3,201+** by employing livestock-heavy CARE compounding strategies.

### Top Leaderboard Clusters (`openings_clusters.csv`):
1. **Counter-Meta (`Seb`, Rank 1: 3201.1)**
   - Opening: 14 hires Day 0, 3 Cows + 2 Sheep on Day 0.
   - Final: 4 Land Quadrants, 9 Cows + 11 Sheep, aggressive labor hiring frontier.
2. **Sheep-First Hybrid (`HealthStone`, Rank 2: 3132.9)**
   - Opening: 3 hires Day 0, 1 Cow + 4 Sheep on Day 0.
   - Final: 8 Cows + 4 Sheep, sheep-first CARE compounding.
3. **v23 Fork (`tao_wu11`, `Mohamed`, `mrgrishninsb`, Rank 3: 3131.4)**
   - Opening: 5 hires Day 0, 2 Cows + 2 Sheep on Day 0.
   - Final: 8 Cows + 6 Sheep, 7 Wheat / 12 Melon / 0 Strawberry seeds.

---

## Unit Economics & Animal CARE Mechanics

### Animal Net Revenue Breakdown (`care_economics.csv`)
| Animal | Product | Structure | Cost | Interval | Care Mult | Units/Day (Care ON) | Gross Revenue/Day | Feed Cost/Day | Net Revenue/Day |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GOOSE** | EGG | COOP | $300 | 1 Day | 2.07x | 2.0 | $100.00 | $25.00 | **$75.00** |
| **COW** | MILK | PASTURE | $400 | 2 Days | 3.25x | 1.5 | $240.00 | $25.00 | **$215.00** |
| **SHEEP** | WOOL | PASTURE | $500 | 3 Days | 4.22x | 1.33 | $266.67 | $25.00 | **$241.67** |

### Key Mechanics Insights
- **Sheep Net Yield**: Sheep yields the highest net revenue per animal per day (**$241.67/day**), followed by Cow (**$215.00/day**).
- **Max Held Yield Capping**: `yield_units` sitting on a tile is capped at `max_held` (6 for Cow/Sheep). If unharvested produce sits on the tile when a CARE-boosted production fires, excess yield past 6 is **permanently lost**.
- **Pre-Production Harvest Optimization**:
  - COW: Production fires every 2 days. Harvest on `age % 2 == 1` (day right before production).
  - SHEEP: Production fires every 3 days. Harvest on `age % 3 == 2` (day right before production).

---

## Market Dynamics & Pricing Mechanics

### Market Pricing Rules
- **Simultaneous Pre-Commit Pricing**: Both players' quotes for the same market order slot index are calculated from the *same pre-commit inventory*. There is no first-mover player index price advantage.
- **Order Slot Priority**: Order prices update between slot indices (slots 0..9). Early slots take precedence, which is why `_SORT_KEY='impact'` ranks orders by gross revenue lost if delayed.
- **Wheat Feed Reservation**: Wheat is both a tradeable product and animal feed. Agents must enforce a minimum wheat reserve in the shed (`owned_animals * 2 + 5`) to prevent animal starvation and escape.

---

## Codebase Agent Implementations

1. **`main.py` (Primary Competitive Agent)**
   - Trajectory-replay agent based on Lev Neganov's episode 91587143 with an overlaid game-theoretic market controller.
   - Includes `_pre_production_animal_harvest` to clear Cow and Sheep tiles before production days, preventing `max_held` yield loss.
2. **`main (3).py` (Dynamic Heuristic State-Machine Agent)**
   - Dynamic heuristic task assignment engine for farmer and farm hands.
   - Fully repaired: resolves day-0 immature crop harvesting, virtual seed tracking, fertilizer/wheat buy-sell loops, center shed tile building protection, and land-gated animal scaling.
