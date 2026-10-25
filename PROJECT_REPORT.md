# SunShift NEM — Project Report

**Working title:** SunShift NEM: auditable peer-to-peer solar coordination for community microgrids
**Track:** Renewable Energy & Energy Trading
**Prototype status:** Functional scenario-planning prototype; hosted deployment is a preview only
**Evidence level:** Synthetic example plus optional weather forecast or user-supplied 24-hour participant data

## Executive summary

SunShift NEM models a small local energy community with two participants: a rooftop-solar producer and a community-site buyer with a flexible storage load. It schedules the buyer’s flexible task, then matches forecast solar to buyer demand subject to an interconnection limit. It compares this coordinated case with a no-peer-trade baseline and records a hash-linked receipt for the proposed interval matches.

The project targets a practical Australian renewable-energy problem: how to coordinate local flexible demand and renewable supply so more energy can be used close to where it is produced. AEMO’s NEM reporting documents economic offloading and network curtailment affecting grid-scale solar output; the prototype’s focus is local coordination, not a claim that it can prevent utility-scale curtailment. [AEMO Quarterly Energy Dynamics, Q4 2025](https://aemo.com.au/-/media/files/major-publications/qed/2025/qed-q4-2025.pdf?rev=b29ae0bd014c48f59a259009d246280f&sc_lang=en)

## Problem and user

Small energy communities can have solar generation at one site and flexible demand or storage at another. Without interval-level coordination, one participant may export or leave renewable energy unmatched while another imports energy and charges later. Potential users include community-energy groups, councils, schools, commercial sites and microgrid operators. The demo is advisory; it is not a market participant, retailer, aggregator or control system.

## Proposed workflow

1. Select an NEM region and define a virtual solar producer, buyer and flexible storage task.
2. Use the built-in illustrative 24-hour profile, explicitly load a weather forecast, or upload 24 hourly rows of participant solar/load data.
3. Set the power transfer limit, flexible energy requirement, charge limit and scenario prices.
4. SunShift schedules flexible energy into solar-surplus intervals first, then lower-import eligible intervals; it matches seller generation to buyer demand subject to the transfer limit.
5. Review the hourly P2P match, buyer import comparison, peak import and scenario price outcomes.
6. Record a unique local receipt containing the plan hash and proposed intervals. A future permissioned/on-chain deployment could register meter-evidence hashes and reject duplicate trade IDs.

## How the prototype works

The dispatch heuristic is intentionally transparent. For each interval it computes modeled PV energy, buyer demand and flexible charge. It allocates the fixed flexible-energy target without exceeding the configured charge limit. It then matches the minimum of seller solar, buyer demand and the transfer limit. Remaining buyer demand is modeled as grid import. The baseline has no peer match and places flexible charging in the evening window. Both schedules use the same 24-hour energy target.

This is a deterministic optimization heuristic, not a trained machine-learning model. The application exposes a live-weather forecast option and supports imported participant profiles, but no custom ML model is trained or evaluated in this prototype. This distinction should be explicit in any CV or hackathon claim.

The local audit receipt hashes the canonical plan/evidence payload and chains each receipt to the previous hash. Unique event IDs prevent duplicate local records, and the verifier detects edits to prior records. This is a single-machine tamper-evident log, **not a decentralized blockchain**. `contracts/PeerEnergyRegistry.sol` is a reference Solidity contract for the next implementation stage; it has not been compiled, audited or deployed, and no receipt is currently written on-chain.

## Prototype scenario results

The built-in illustrative South Australia summer profile currently produces the following example with default inputs: 42 kW modeled PV, 17 kW average buyer load, 18 kWh flexible storage task, 6 kW charge limit, 24 kW transfer limit, 18 c/kWh P2P scenario price and 32 c/kWh grid reference price.

| Metric | Example output | Interpretation |
|---|---:|---|
| P2P solar matched | 212.155 kWh | Modeled interval matches in this synthetic profile |
| Buyer import difference | 212.155 kWh | Versus the no-peer-trade baseline; not a measured saving |
| Peak import reduction | 4.805 kW | Synthetic hourly comparison |
| Buyer energy-cost difference | AUD 29.70 | At entered scenario prices only; no network fees or settlement rules |
| CO₂e indicator | 137.901 kg | Import difference × illustrative 0.65 kg/kWh; not verified abatement |

These numbers are generated from the checked-in illustrative fixture and are provided to show the software path works. They are **not field results**, actual Australian site outcomes, energy settlements, or scientifically validated emissions reductions. The baseline is deliberately simple and should be replaced by a time-aligned measured counterfactual before impact claims.

## ClimateChain fit

The project aligns most directly with the official **Renewable Energy & Energy Trading** track: microgrid coordination and P2P energy trading. The AI/data-driven contribution is interval-level forecast-aware dispatch; the blockchain contribution is an auditable, duplicate-resistant trade-evidence design. The judging criteria also require clear climate impact, practical usefulness, technical execution and communication. [Hackathon overview and tracks](https://ieee-climatechain-hack.devpost.com/) · [Rules and judging criteria](https://ieee-climatechain-hack.devpost.com/rules)

For a credible presentation, show the participant roles, transfer limit, hourly schedule and one duplicate-event rejection. Explicitly say that uploaded data is not independently verified and that the local receipt is not yet on a public chain.

## Australian relevance and sources

- AEMO publishes public NEM five-minute dispatch data by region; production-grade live analysis should ingest and cite the relevant AEMO feeds and schemas rather than infer market conditions from weather. [AEMO dispatch data](https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/dispatch)
- Open Electricity provides Australian NEM/WEM generation, demand and market metrics through an authenticated API; its documented API currently requires a key and carries a non-commercial data licence unless otherwise stated. [API overview](https://docs.openelectricity.org.au/api-reference/overview/)
- Optional weather data comes from Open-Meteo’s hourly forecast API; it is not an NEM feed. [Open-Meteo](https://open-meteo.com/)
- The hackathon deadline was listed as 25 October 2026, 5:00 p.m. UTC+03. The project gallery was unpublished in the page view inspected, so the competitive field could not be assessed. Eligibility wording also differed between overview and rules pages and should be checked with the organiser. [Schedule](https://ieee-climatechain-hack.devpost.com/details/dates) · [Overview](https://ieee-climatechain-hack.devpost.com/) · [Rules](https://ieee-climatechain-hack.devpost.com/rules)

## Limitations and next steps

1. Replace the illustrative load curve with consented, interval-meter participant data and model data quality/missing intervals.
2. Ingest historical/forecast NEM or local distribution data with source timestamps and clear licensing.
3. Add explicit seller/buyer offer curves and test price-clearing/fairness, not only fixed-price scenario economics.
4. Account for network losses, congestion, retailer arrangements, metering, market rules and storage state-of-charge/efficiency.
5. Benchmark the scheduler against a measured baseline and report uncertainty.
6. Compile and test the Solidity registry, define identity/authorisation and evidence-signing, then deploy only to a testnet after review.
7. Only then describe actual P2P settlement or verified environmental impact.

## Reproduction

```bash
python3 server.py
```

Open `http://127.0.0.1:8788`. The server binds to loopback. Run automated checks with `python3 -m unittest discover -s tests -v`.
