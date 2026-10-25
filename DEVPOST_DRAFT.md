# Devpost submission draft — SunShift NEM

## Project name
SunShift NEM

## Tagline
Coordinate local solar sharing and flexible demand before energy is exported or imported elsewhere.

## Track
Renewable Energy & Energy Trading — microgrid coordination and peer-to-peer energy trading.

## Inspiration
Australian energy communities can have renewable generation at one site and flexible demand or storage at another. SunShift explores how an interval-level plan and a shared evidence record could help a community coordinate the two. AEMO reports NEM solar curtailment and economic offloading; this prototype addresses local peer matching and does not claim to solve utility-scale curtailment.

## What it does
SunShift models a rooftop-solar producer, community buyer and flexible storage task. It matches forecast or user-provided solar intervals to buyer demand, respects a transfer capacity, schedules a fixed flexible-energy target, and compares buyer grid imports and scenario costs with a no-peer-trade baseline. It can record a local SHA-256 hash-chain receipt for the proposed interval matches and includes a reference Solidity registry that rejects duplicate trade identifiers.

## How it is built
- Python standard-library HTTP server and deterministic dispatch optimizer.
- Vanilla HTML/CSS/JavaScript interactive dashboard.
- Optional Open-Meteo hourly solar/weather forecast.
- CSV import for 24 hourly solar-supply and buyer-load values.
- Local hash-chain receipt ledger plus a separate Solidity contract reference.

## Climate relevance
The prototype tests whether scheduling flexible loads and coordinating local renewable supply can improve local solar matching and reduce a buyer’s modeled grid imports. Metrics are scenario comparisons, not independently verified emissions reductions or settled trades.

## What is novel in the prototype
The coordination plan exposes the energy match and transfer constraint interval by interval, and the evidence design binds a plan hash to a unique proposed trade event. It separates live forecast data from illustrative or user-supplied participant profiles so the demo does not label modeled results as measured impact.

## Demo flow
1. Start the local app and select South Australia.
2. Show the solar producer, community buyer and storage participants.
3. Adjust peer transfer capacity and the fixed storage-energy requirement.
4. Build the microgrid plan and compare the no-trade and coordinated import curves.
5. Upload the included 24-row example profile to demonstrate data ingestion.
6. Record the local receipt and show that a repeated plan hash is rejected.

## Limitations
The included participant profiles are synthetic. Weather forecasts do not equal NEM dispatch or settlement data. The optimizer is deterministic and is not a trained ML model. The app’s receipt is local, not on a public blockchain. The Solidity contract is reference code, not compiled, audited or deployed. No market bids, payments, device controls or real-world impact claims are made.

## Links to add before submission
- Public source repository: not published yet; user requested local/private work.
- Demo video (3–5 minutes): record after the final run-through.
- Live public demo: intentionally not deployed.
