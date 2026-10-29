# SunShift Flex — three-minute demo script

**Goal:** show a real Nemotron preference call, the deterministic simulation and the before/after comparison in under three minutes.

**Before recording**

1. Start the app: `python3 server.py` and open `http://127.0.0.1:8788`.
2. Set `NEBIUS_API_KEY` and optionally `NEBIUS_MODEL`. Confirm the AI panel says **Nemotron ready**.
3. Use a 1440 × 1000 browser window. Do not show the terminal, environment variables or the key.
4. Have the three-minute narration ready. Keep the app on the three-home sample.

## Shot list

| Time | Picture | Voice |
|---|---|---|
| 0:00–0:18 | Hero and three-home image, then the home cards | “A neighbourhood can have solar on one roof and an evening need under another. The usual bill hides that. SunShift Flex puts the three homes on one table.” |
| 0:18–0:35 | Show Home A surplus, B and C need; point at the daily cards | “Home A has the larger roof and battery. Home B and Home C need more than they generate, especially in the evening. The question is what could be shared, and what it changes.” |
| 0:35–0:55 | Left panel: Home A, the sample preference, **Plan energy sharing** | “I can describe what matters in plain language. Keep the battery above forty percent, prefer local use and share the spare battery in the evening.” |
| 0:55–1:15 | AI panel: **validated**, model name, constraint chips | “Nemotron on Nebius Token Factory turns that into strict constraints. The server validates every field before the simulator sees them. The model does not calculate energy; any number it mentions must match the supplied result.” |
| 1:15–1:40 | Stage at 18:00; press **Play day** or drag the hour | “At six in the evening, Home A is sharing from its battery. B and C receive local energy, then import the rest. The grid stays connected; this is a virtual allocation.” |
| 1:40–2:05 | Scroll to **Independent vs coordinated** | “Against independent homes, the coordinated case uses more local solar, imports less, exports less and costs less in this sample. Those are modelled daily estimates, not a bill.” |
| 2:05–2:25 | Open **How the simulation works**; show chart, table, validation | “Every number comes from the deterministic simulator: energy balance, battery reserve, transfer limits, tariff-based cost, zero violations.” |
| 2:25–2:40 | Show 30-day assumption and limitations | “The monthly figure is the sample day repeated thirty times. It assumes no seasonal, tariff or demand change. It is not a forecast.” |
| 2:40–2:55 | Return to the stage or the explanation card | “SunShift Flex makes the neighbourhood trade-off visible before anything is committed. Simulated allocation, honest limits, and a clear role for the model.” |

## Honesty notes for the recording

- If the key is missing or the API fails, do **not** pretend there was a model result. Show the **unavailable** panel and the labelled manual fallback, and say so. The submission demo should use a real key.
- Do not say the homes traded electricity, received a retailer credit or saved money in a real market. Say “simulated allocation” and “modelled energy cost”.
- Do not show the mock/test fixture as a live Nemotron response.
- Keep the “Simulation only” and “not settlement data” labels visible.
