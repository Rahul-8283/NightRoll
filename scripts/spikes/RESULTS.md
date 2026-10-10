# Phase 0 risk spikes: results

Status as of the last update. Fill in one row per spike when it runs. Keep the raw numbers, not just pass or fail.

| # | Spike | Question | Status | What it needs | Numbers / evidence | Decision or workaround |
|---|---|---|---|---|---|---|
| 11.1 | Keystore signing | Can a test phone make a non-exportable P-256 key and sign bytes that Python verifies? | Not run | A development build on a test phone | | |
| 11.2 | Play Integrity | Does a directly installed build return a decodable token, and which verdict fields come back? | Not run | A development build, the Play Integrity setup, and the service account JSON | | |
| 11.3 | Face latency | Per-frame time for `buffalo_l` on the demo laptop CPU | Not run | The face worker from Phase 5 | ms per frame: | |
| 11.4 | Wi-Fi scan | Does a test phone return BSSIDs and RSSI for nearby networks? | Not run | A development build on a test phone | | |
| 11.5 | Source address | Does the laptop see a different source address for each demo router? | Not run | Two demo routers and the phones on them | | |

Notes:
- Spikes 11.1, 11.2 and 11.4 use a development build, because Expo Go cannot run the native code they test.
- The Phase 13 walk test and tuning use their own files under `docs/measurements/`.
