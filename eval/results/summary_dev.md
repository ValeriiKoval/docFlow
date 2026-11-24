# Run comparison

n = 50 documents per set.

## Document exact match (all 11 fields correct)

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 74% | 78% | 80% | 46% |
| claude-sonnet-5-5 / extract_v2 | 100% | 100% | 100% | 54% |
| claude-haiku-5-5 / extract_v2 | 100% | 100% | 98% | 26% |

## Field accuracy (mean over 11 fields)

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 98% | 98% | 98% | 92% |
| claude-sonnet-5-5 / extract_v2 | 100% | 100% | 100% | 94% |
| claude-haiku-5-5 / extract_v2 | 100% | 100% | 100% | 84% |

## Human-in-the-loop at confidence >= 0.8

Auto-accepted share / exact-match accuracy of the auto-accepted documents.

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 88% / 84% | 92% / 80% | 86% / 86% | 10% / 100% |
| claude-sonnet-5-5 / extract_v2 | 100% / 100% | 100% / 100% | 98% / 100% | 0% / - |
| claude-haiku-5-5 / extract_v2 | 100% / 100% | 100% / 100% | 96% / 100% | 0% / - |

## Threshold sweep

Per run: auto-accepted share / exact-match accuracy of accepted / wrong documents that slipped through (out of all documents in the set).

**claude-sonnet-5-5 / extract_v1**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 74% / 13 | 100% / 78% / 11 | 100% / 80% / 10 | 94% / 49% / 24 |
| 0.6 | 100% / 74% / 13 | 100% / 78% / 11 | 100% / 80% / 10 | 68% / 59% / 14 |
| 0.7 | 100% / 74% / 13 | 100% / 78% / 11 | 100% / 80% / 10 | 32% / 81% / 3 |
| 0.8 | 88% / 84% / 7 | 92% / 80% / 9 | 86% / 86% / 6 | 10% / 100% / 0 |
| 0.9 | 82% / 90% / 4 | 80% / 92% / 3 | 68% / 94% / 2 | 0% / - / 0 |

**claude-sonnet-5-5 / extract_v2**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 100% / 0 | 38% / 89% / 2 |
| 0.6 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 100% / 0 | 22% / 100% / 0 |
| 0.7 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 100% / 0 | 8% / 100% / 0 |
| 0.8 | 100% / 100% / 0 | 100% / 100% / 0 | 98% / 100% / 0 | 0% / - / 0 |
| 0.9 | 100% / 100% / 0 | 100% / 100% / 0 | 46% / 100% / 0 | 0% / - / 0 |

**claude-haiku-5-5 / extract_v2**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 16% / 75% / 2 |
| 0.6 | 100% / 100% / 0 | 100% / 100% / 0 | 98% / 100% / 0 | 4% / 50% / 1 |
| 0.7 | 100% / 100% / 0 | 100% / 100% / 0 | 98% / 100% / 0 | 0% / - / 0 |
| 0.8 | 100% / 100% / 0 | 100% / 100% / 0 | 96% / 100% / 0 | 0% / - / 0 |
| 0.9 | 96% / 100% / 0 | 90% / 100% / 0 | 18% / 100% / 0 | 0% / - / 0 |


## Cost and latency (all sets)

| Run | Avg in tok | Avg out tok | Cost / doc, USD | Cost / 1000 docs, USD | Avg latency, s | Failed calls |
|---|---|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 3334 | 399 | 0.0107 | 10.66 | 3.6 | 0 |
| claude-sonnet-5-5 / extract_v2 | 4023 | 376 | 0.0118 | 11.81 | 3.4 | 0 |
| claude-haiku-5-5 / extract_v2 | 4023 | 575 | 0.0007 | 0.69 | 3.9 | 0 |
