# Appendices (pp. 1147–1174, appendices 1–3)

## Appendix 1 — Probability tables
Normal distribution areas, t-distribution critical values, and a table of uniform random numbers (used in Ch 22 for the roulette/Martingale simulation). Today: scipy.stats (norm.cdf/ppf, t.ppf, chi2.ppf) and numpy.random replace them.

## Appendix 2 — Matrix solution of linear equations & Markov chains
- **Gaussian (Gauss–Jordan) elimination**: write the augmented coefficient matrix; use row operations (scale a row, swap rows, add/subtract multiples of rows) to reach the identity on the left → right column is the solution. Worked example gives x₁ = 1, x₂ = 2, x₃ = 3. (numpy.linalg.solve.)
- **Markov chain steady state (direct)**: π = πT with Σπ = 1 → linear system (replace one redundant equation by the sum constraint). Weather example: A = 0.400, B = 0.425, C = 0.175.
- **Convergence method** (Arrington): build frequency matrix F of next-day state (up / down / neutral, neutral = tiny changes) given today's state (e.g. 5-day trend up/down/neutral); divide each row by its total → transition matrix T; compute Tⁿ by repeated multiplication (cᵢⱼ = Σₖ aᵢₖbₖⱼ) until it stops changing; every row then equals the long-run probabilities.
- Use: long-run frequency of states; compare a conditional row of T with the steady state to see if the current state carries predictive information (and test the difference statistically — χ²).

## Appendix 3 — Trigonometric regression programs (FORTRAN)
TRIG1 (single frequency) and two-frequency versions for Ch 11: detrend by linear regression (copper b = +0.267¢/quarter), compute α, ω, period T, solve normal equations for a, b, add trend back. Copper cycle ≈ 8.4 quarters; monthly corn 1964–83 gave a 21.4-month cycle — **not seasonal**, explained by supply/stock dynamics or distortion from the 1973 and 1980 non-seasonal rallies — a reminder that fitted cycles can be artefacts of a few big moves.

## Takeaway for NSE project
Markov transition matrices of discretised states (return sign / trend regime / volatility regime) are an easy, interpretable baseline: estimate T on training data, check stationarity of T across 2015–19 vs 2020–24, and test conditional vs steady-state probabilities with χ² before using them as features.
