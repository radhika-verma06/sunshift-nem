# SunShift NEM

**Forecast-aware peer-to-peer solar matching for Australian energy communities.**

SunShift coordinates an illustrative solar producer, a community-site buyer and a flexible storage task. It matches forecast or user-supplied solar intervals to buyer demand, respects a transfer-capacity limit, and compares the result with a no-trade evening-charge baseline. A local receipt log demonstrates tamper-evident provenance; the Solidity contract is a reference for a future testnet deployment.

## Run locally

Requires Python 3.9+; the prototype uses only the standard library.

```bash
python3 server.py
```

Open **http://127.0.0.1:8788**. The server binds only to loopback. No robot, battery, market bid, or payment integration is configured.

For the ClimateChain project story, open **http://127.0.0.1:8788/hackathon-explainer.html**. Its interactive scenario uses the same local optimizer; it does not represent a live trade.

Stop with `Ctrl-C`.

## Use the prototype

1. The initial South Australia scenario works offline and is clearly labelled illustrative.
2. Adjust solar capacity, buyer load, storage energy/power, peer transfer capacity and scenario prices.
3. Choose **Coordinate the microgrid**. The planner matches seller solar to buyer demand, then schedules the flexible storage load within the selected 07:00–22:00 window.
4. Review matched kWh, buyer imports, peak import, buyer cost difference and seller revenue under the scenario price.
5. Optionally select **Load live weather**. This fetches a next-day Open-Meteo solar-radiation/temperature forecast. It does not fetch live AEMO dispatch or meter data.
6. Optionally upload a 24-row CSV with columns `hour,seller_solar_kwh,buyer_load_kwh`. A sample file is downloadable in the UI. Uploaded values are user-supplied and not independently verified.
7. **Record local receipt** appends the plan hash and proposed interval matches to a local SHA-256 hash chain. Duplicate event IDs and duplicate plan hashes are rejected. The record is stored in `data/receipts.local.jsonl` (ignored by Git). It is not a blockchain transaction and does not prove physical delivery.

## Technical outline

- `optimizer.py`: validates inputs, preserves flexible energy and power limits, greedily allocates first to modeled solar surplus and then to lower-import intervals; matches peer energy under a transfer limit.
- `server.py`: loopback-only standard-library web/API server and optional Open-Meteo forecast proxy.
- `web/`: responsive standalone UI; no third-party runtime dependencies.
- `ledger.py`: local tamper-evident append-only hash chain with unique event IDs and verification.
- `contracts/PeerEnergyRegistry.sol`: reference smart contract for unique, evidence-linked trade interval records. It is not compiled, deployed, audited, or called by this app.
- `tests/`: offline optimizer and ledger tests.

## Data and interpretation

The default site curves and solar profile are a teaching scenario, not measurements. Open-Meteo supplies weather forecasts, not NEM market dispatch. The emissions factor and prices are user-entered scenario assumptions. “Buyer imports avoided,” “buyer savings,” and CO₂e are modeled comparisons and must not be presented as verified impact. The current baseline intentionally represents no peer trade; a real evaluation should compare against a measured, time-aligned counterfactual and account for network losses, tariffs, settlement rules and what the seller would otherwise export.

Open-Meteo data attribution is shown in the interface when loaded. Its API/data terms and attribution requirements should be rechecked before public or commercial deployment.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py optimizer.py ledger.py vercel_api.py sunshift_forecast.py api/demo.py api/optimize.py api/forecast.py api/receipt.py api/ledger/verify.py
node --check web/app.js
```

## Vercel preview

The repository includes `vercel.json` and Python function routes under `api/`. Deploy the project root with Vercel's Python runtime. The hosted demo supports the scenario, optimizer and forecast routes, but **receipt recording is intentionally disabled**: serverless function storage is not a durable append-only ledger. Run locally if you need the persistent local receipt chain. No credentials, meter data or local receipt file belong in the deployment.

```bash
vercel --prod
```

The initial deployment requires a Vercel account login and project linking. Keep the GitHub repository private unless you explicitly choose to publish the source.

## Privacy

The local prototype needs no credentials; no data leaves the Mac except when **Load live weather** is explicitly clicked. Uploaded participant profiles are processed in the browser and sent to the planner request. Do not enter real meter/customer data into the hosted preview or publish it in a repository. The local receipt file may contain scenario details and is excluded from version control.
