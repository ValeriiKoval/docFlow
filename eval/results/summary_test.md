# Run comparison

n = 50 documents per set.

## Document exact match (all 11 fields correct)

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 92% | 90% | 90% | 54% |
| claude-sonnet-5-5 / extract_v2 | 100% | 100% | 98% | 60% |
| claude-haiku-5-5 / extract_v2 | 100% | 98% | 100% | 28% |

## Field accuracy (mean over 11 fields)

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 99% | 99% | 99% | 92% |
| claude-sonnet-5-5 / extract_v2 | 100% | 100% | 100% | 93% |
| claude-haiku-5-5 / extract_v2 | 100% | 100% | 100% | 87% |

## Human-in-the-loop at confidence >= 0.8

Auto-accepted share / exact-match accuracy of the auto-accepted documents.

| Run | clean | light | medium | heavy |
|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 100% / 92% | 100% / 90% | 100% / 90% | 18% / 89% |
| claude-sonnet-5-5 / extract_v2 | 100% / 100% | 100% / 100% | 100% / 98% | 4% / 100% |
| claude-haiku-5-5 / extract_v2 | 98% / 100% | 100% / 98% | 98% / 100% | 2% / 100% |

## Threshold sweep

Per run: auto-accepted share / exact-match accuracy of accepted / wrong documents that slipped through (out of all documents in the set).

**claude-sonnet-5-5 / extract_v1**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 92% / 4 | 100% / 90% / 5 | 100% / 90% / 5 | 84% / 64% / 15 |
| 0.6 | 100% / 92% / 4 | 100% / 90% / 5 | 100% / 90% / 5 | 70% / 74% / 9 |
| 0.7 | 100% / 92% / 4 | 100% / 90% / 5 | 100% / 90% / 5 | 46% / 74% / 6 |
| 0.8 | 100% / 92% / 4 | 100% / 90% / 5 | 100% / 90% / 5 | 18% / 89% / 1 |
| 0.9 | 92% / 98% / 1 | 90% / 98% / 1 | 76% / 100% / 0 | 0% / - / 0 |

**claude-sonnet-5-5 / extract_v2**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 56% / 86% / 4 |
| 0.6 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 26% / 100% / 0 |
| 0.7 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 12% / 100% / 0 |
| 0.8 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 98% / 1 | 4% / 100% / 0 |
| 0.9 | 100% / 100% / 0 | 100% / 100% / 0 | 54% / 100% / 0 | 0% / - / 0 |

**claude-haiku-5-5 / extract_v2**

| Threshold | clean | light | medium | heavy |
|---|---|---|---|---|
| 0.5 | 100% / 100% / 0 | 100% / 98% / 1 | 100% / 100% / 0 | 28% / 64% / 5 |
| 0.6 | 100% / 100% / 0 | 100% / 98% / 1 | 100% / 100% / 0 | 8% / 75% / 1 |
| 0.7 | 98% / 100% / 0 | 100% / 98% / 1 | 100% / 100% / 0 | 6% / 67% / 1 |
| 0.8 | 98% / 100% / 0 | 100% / 98% / 1 | 98% / 100% / 0 | 2% / 100% / 0 |
| 0.9 | 94% / 100% / 0 | 90% / 98% / 1 | 10% / 100% / 0 | 0% / - / 0 |


## Cost and latency (all sets)

| Run | Avg in tok | Avg out tok | Cost / doc, USD | Cost / 1000 docs, USD | Avg latency, s | Failed calls |
|---|---|---|---|---|---|---|
| claude-sonnet-5-5 / extract_v1 | 3358 | 359 | 0.0103 | 10.31 | 3.3 | 0 |
| claude-sonnet-5-5 / extract_v2 | 4022 | 378 | 0.0118 | 11.82 | 3.3 | 0 |
| claude-haiku-5-5 / extract_v2 | 4022 | 570 | 0.0007 | 0.69 | 4.2 | 0 |
