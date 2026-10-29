# SunShift Flex — Nebius Global AI Hackathon submission

## Track

**Best Apps and Agents**

## Name and tagline

**SunShift Flex**

A simulated three-home solar-sharing planner. One roof has spare solar, another has an evening need, and the neighbourhood can see the trade-off before anything is committed.

## Short description

SunShift Flex shows how spare rooftop solar could be allocated to a neighbour's evening demand. Choose a home, describe what matters in plain language, and watch a 24-hour simulation compare independent homes with a coordinated local allocation. NVIDIA Nemotron through Nebius Token Factory turns the preference into constraints; a deterministic simulator calculates every kWh, cost and balance. Synthetic sample, virtual allocation, no direct wires.

## What it does

- Shows three homes with different solar, demand and battery state.
- Accepts a natural-language preference, or a labelled manual sample.
- Uses Nemotron to extract a strict set of constraints: battery reserve, local-first choice, evening-sharing choice and no-discharge window.
- Validates the model output before the simulator sees it.
- Simulates 24 one-hour intervals for independent homes and a coordinated neighbourhood.
- Animates solar, demand, battery state, local allocation, grid import and export.
- Compares local solar used, grid imports, exports, cost and self-sufficiency.
- Explains what changed, with an optional qualitative Nemotron explanation that cannot add numbers.
- Exports/exposes the sample CSV and records a local hash-chain receipt for the exact plan.

## Why it matters

Household bills hide complementarity between neighbours. One home exports at the export rate while another imports at the retail rate at the same time. A local allocation or community-energy arrangement could keep more value and more solar in the neighbourhood. SunShift Flex makes that question inspectable without pretending the grid, retailer or market has approved it.

## How it works

1. The browser sends the preference, chosen home and scenario to the local Python server.
2. The server calls Nebius Token Factory only if `NEBIUS_API_KEY` is configured.
3. Nemotron returns schema-constrained JSON. The server validates every field, including the reserve range, boolean types and a consistent no-discharge window.
4. The deterministic simulator applies the constraints to the three homes. It never asks the model for an energy value.
5. The UI shows the model name, the validated constraints, the simulation and the comparison.
6. A second optional model call explains the already-calculated result. Numbers in its response must match the supplied result summary. Invented numbers and unsupported claims are rejected.

## Nemotron and Nebius disclosure

- **Service:** Nebius Token Factory, OpenAI-compatible chat completions API.
- **Default model:** `nvidia/Nemotron-3_5-Lightning` (NVIDIA Nemotron 3.5 Lightning).
- **Why this model:** it is a responsive Nemotron model suited to a short extraction task; the catalogue changes, so the model ID is configurable with `NEBIUS_MODEL`.
- **Where it runs:** server-side only. The browser never receives the key.
- **What it contributes:** natural-language interpretation and an optional qualitative explanation.
- **What it does not do:** calculate, estimate, schedule or invent energy, costs, savings or feasibility.
- **Failure behavior:** missing key or API failure is displayed as unavailable; the labelled manual sample is used and no model result is fabricated.
- **Logging:** model, outcome, HTTP status and latency only. No key, prompt or personal data.

Live verification on 2026-10-28 used `nvidia/Nemotron-3_5-Lightning` for both the preference interpretation and the qualitative explanation. Latency was about 1.8 to 2.7 seconds for interpretation and 1.7 to 2.4 seconds for the explanation. The repository does not contain a Nebius key, so a fresh clone must supply one.

## Data disclosure

The three-home scenario is **synthetic and illustrative**, created for this prototype. It is not measured billing, meter, network or settlement data. The committed files are:

- `data/flex_scenario.json`
- `data/flex_homes_sample.csv`

The app labels the scenario as simulated and provides the CSV download. If you replace it with consented data, update the label and README. No external dataset is fetched at runtime.

## Built with

Python, JavaScript, HTML, CSS, NVIDIA Nemotron, Nebius Token Factory, JSON Schema, standard-library HTTP server, Vercel serverless functions.

## Links to add before submitting

- **Public code repository:** currently `github.com/radhika-verma06/sunshift-nem` (private at the time of writing). It must be made public with the MIT licence visible before submission.
- **Working demo URL:** local `http://127.0.0.1:8788`; deploy to Vercel if a hosted URL is required. Set `NEBIUS_API_KEY` and `NEBIUS_MODEL` in Vercel.
- **Demo video:** record a public YouTube video of 3 minutes or less using `docs/DEMO_SCRIPT.md`.

## What was materially added to the existing project

The repository already contained a two-home SunShift NEM planner, a deterministic optimizer, a local ledger and a premium static UI. For this hackathon:

- Added `flex_model.py`, a deterministic three-home, 24-interval simulator with batteries, reserve windows, local allocation, baseline comparison, costs and validation.
- Added `flex_ai.py`, the server-only Nebius client with strict schema validation, a qualitative explanation guard, failure states and secret-safe logging.
- Added the synthetic three-home scenario and CSV.
- Replaced the main UI with the SunShift Flex workflow inside the existing visual identity: three-home stage, hour animation, AI panel, comparison, chart, validation table and local receipt.
- Added `/api/flex/*` local and hosted routes and Vercel rewrites.
- Added model, AI, route and receipt tests, plus README, MIT licence and `.env.example`.
- Preserved the existing optimizer, ledger, contracts and legacy routes for compatibility.

## Assumptions and limitations

- The scenario and profiles are synthetic. No measured savings, emissions or grid impact is claimed.
- Local allocation is virtual accounting. The public grid remains connected; no electricity is physically routed between houses.
- The model is not a network study, retailer, market, settlement or financial forecast.
- Tariffs exclude daily supply, network, taxes, retailer margin, losses and settlement.
- Battery degradation, temperature, inverter limits and standby losses are not modelled.
- Monthly figures are exactly 30 repeated sample days, not seasonal forecasts.
- A real deployment needs consent, metering, a retailer or community-energy agreement, network approval, consumer protection and measured follow-up.
- The model catalogue and model IDs can change; verify the selected Nemotron model before a live demo.
- The live verification was performed on this machine with a local `NEBIUS_API_KEY`; the key is not in the repository, so a fresh clone must supply one.

## Demo checklist

- [ ] `NEBIUS_API_KEY` set in the shell or Vercel; the UI shows **Nemotron ready**.
- [ ] Plan with a sample preference; the AI panel shows **validated** and the model ID.
- [ ] Stage animation shows sharing, battery state, grid import/export.
- [ ] Comparison shows local solar, import, export, cost and self-sufficiency.
- [ ] Technical details show the chart, table, zero violations, tariffs and 30-day assumption.
- [ ] Local receipt records the plan hash (local demo only).
- [ ] README and MIT licence visible on the public repository.
- [ ] Video is 3 minutes or less and shows the real model call and the deterministic calculation.
