# Advanced Overfitting Detection

Overfitting is the most insidious threat to quantitative strategy development. A strategy may show exceptional historical performance yet fail catastrophically in live trading because it was unconsciously tailored to past data rather than capturing genuine market inefficiencies. Simulor provides three complementary anti-overfitting tools that work together to validate strategy robustness.

## Table of Contents

- [Quick Start: Which Tool Should I Use?](#-quick-start-which-tool-should-i-use)
- [Part 1: Walk-Forward Analysis (WFA)](#part-1-walk-forward-analysis-wfa)
  - [Why Traditional Backtesting Overfits](#why-traditional-backtesting-overfits)
  - [WFA Methodologies](#wfa-methodologies)
  - [WFA Configuration & Workflow](#wfa-configuration--workflow)
  - [WFA Performance Metrics](#wfa-performance-metrics)
  - [WFA Best Practices](#wfa-best-practices)
- [Part 2: Combinatorial Purged Cross-Validation & PBO](#part-2-combinatorial-purged-cross-validation--probability-of-backtest-overfitting)
  - [Why Standard K-Fold CV Fails for Trading](#why-standard-k-fold-cv-fails-for-trading)
  - [Combinatorial Purged Cross-Validation (CSCV)](#combinatorial-purged-cross-validation-cscv)
  - [Probability of Backtest Overfitting (PBO)](#probability-of-backtest-overfitting-pbo)
  - [Deflated Sharpe Ratio (DSR)](#deflated-sharpe-ratio-dsr)
  - [Combined CSCV + PBO Workflow](#combined-cscv--pbo-workflow)
- [Part 3: Probabilistic Backtesting](#part-3-probabilistic-backtesting)
  - [Motivation: Beyond Single-Path Backtesting](#motivation-beyond-single-path-backtesting)
  - [Monte Carlo Path Generation Methods](#monte-carlo-path-generation-methods)
  - [Probabilistic Backtest Execution](#probabilistic-backtest-execution)
  - [Probabilistic Performance Metrics](#probabilistic-performance-metrics)
  - [Visualizing Probabilistic Results](#visualizing-probabilistic-results)
  - [Permutation Testing for Statistical Significance](#permutation-testing-for-statistical-significance)
  - [Configuration & Best Practices](#configuration--best-practices)
- [Integration: Combined Overfitting Detection Workflow](#integration-combined-overfitting-detection-workflow)

---

## ⚡ Quick Start: Which Tool Should I Use?

**Use this decision guide to choose the right overfitting detection approach:**

### Complementary Anti-Overfitting Tools: When to Use Each

The three primary anti-overfitting techniques serve different but complementary purposes in the strategy validation workflow:

| Aspect           | Probability of Backtest Overfitting (PBO)   | Walk-Forward Analysis (WFA)                        |
| ---------------- | ------------------------------------------- | -------------------------------------------------- |
| **Primary Role** | **Detects** overfitting after optimization  | **Prevents** overfitting through validation design |
| **When Applied** | Post-optimization diagnosis                 | During strategy development & validation           |
| **Output**       | Probability (0-1) of overfitting            | Time-series of out-of-sample performance           |
| **Focus**        | Selection bias among multiple strategies    | Parameter stability across time                    |
| **Method**       | Combinatorial analysis of train/test splits | Sequential rolling window validation               |

**Practical Workflow**:

1. **Development Phase**: Use **WFA** to design robust validation (prevents overfitting from the start)
2. **Post-Optimization**: Use **PBO + CSCV** to detect if optimization caused overfitting (diagnosis)
3. **Final Validation**: Use **Probabilistic Backtesting** to quantify uncertainty in all performance metrics (risk assessment)

**Key Insight**: WFA and PBO are complementary, not alternatives. WFA provides the validation structure, PBO diagnoses the result, and probabilistic backtesting quantifies uncertainty.

---

## Part 1: Walk-Forward Analysis (WFA)

Walk-Forward Analysis is the gold standard for out-of-sample validation of trading strategies. Instead of optimizing on all historical data (which guarantees overfitting), WFA systematically partitions time into training and testing windows, optimizes on past data, and validates on unseen future data.

### Why Traditional Backtesting Overfits

**The Problem**: Traditional backtesting optimizes strategy parameters on the entire historical dataset, then reports performance on that same data. This is analogous to training a machine learning model and reporting training set accuracy—the results are meaningless.

**The Consequence**: Parameters are unconsciously tuned to historical noise rather than signal. The strategy memorizes past market behavior instead of learning generalizable patterns. Live trading performance inevitably degrades.

**The Solution**: Out-of-sample validation. Parameters must be optimized on past data and validated on future data that was never seen during optimization.

### WFA Methodologies

**Anchored Walk-Forward (Expanding Window)**:

```text
Timeline: |------------Historical Data------------|

Window 1:  [Train-1]--->[Test-1]
Window 2:  [---Train-2---]--->[Test-2]
Window 3:  [------Train-3------]--->[Test-3]
Window 4:  [---------Train-4---------]--->[Test-4]
```

- **Training window expands** from fixed start date (incorporates all historical data)
- **Test window advances** sequentially into the future
- **Use Case**: Strategies that benefit from more historical data (e.g., mean reversion, regime detection)
- **Advantage**: Maximum data utilization, captures long-term patterns
- **Disadvantage**: Assumes stationarity (old data remains relevant)

**Rolling Walk-Forward (Sliding Window)**:

```text
Timeline: |------------Historical Data------------|

Window 1:  [Train-1]--->[Test-1]
Window 2:      [Train-2]--->[Test-2]
Window 3:          [Train-3]--->[Test-3]
Window 4:              [Train-4]--->[Test-4]
```

- **Training window slides** forward (fixed size, discards old data)
- **Test window advances** sequentially
- **Use Case**: Non-stationary markets, adaptive strategies, recent data more relevant
- **Advantage**: Adapts to regime changes, discards obsolete patterns
- **Disadvantage**: Less training data, may miss long-term cycles

### WFA Configuration & Workflow

#### Step 1: Define Time Windows

```python
from simulor.analytics import WalkForwardAnalysis

wfa = WalkForwardAnalysis(
    strategy=my_strategy,
    mode='anchored',  # or 'rolling'

    # Time periods (in trading days)
    training_period=252,      # 1 year training
    test_period=63,           # 3 months testing
    step_size=21,             # Monthly steps (advance by 1 month)

    # Optimization settings
    param_grid={
        'sma_fast': [10, 20, 30, 50],
        'sma_slow': [50, 100, 150, 200],
        'rsi_period': [10, 14, 20, 30]
    },
    optimization_metric='sharpe_ratio',
    min_trades=30  # Require minimum trades for valid test period
)
```

#### Step 2: Run WFA Simulation

```python
results = wfa.run()

# Access aggregated results
print(f"In-Sample Sharpe:  {results.in_sample_sharpe:.2f}")
print(f"Out-of-Sample Sharpe: {results.out_of_sample_sharpe:.2f}")
print(f"Degradation: {results.degradation:.1%}")
print(f"Efficiency Ratio: {results.efficiency_ratio:.2f}")
```

#### Step 3: Analyze Parameter Stability

```python
# Plot parameter evolution across windows
wfa.plot_parameter_evolution()

# Example output:
# Window 1: sma_fast=20, sma_slow=100, rsi_period=14
# Window 2: sma_fast=30, sma_slow=100, rsi_period=14  (stable)
# Window 3: sma_fast=10, sma_slow=200, rsi_period=30  (unstable - red flag!)
# Window 4: sma_fast=20, sma_slow=150, rsi_period=14

# Parameter consistency score
print(f"Parameter Consistency: {results.parameter_consistency:.1%}")
# High consistency (>70%) = robust strategy
# Low consistency (<40%) = overfitting to noise
```

#### Step 4: Visualize Results

```python
# Time series of in-sample vs out-of-sample performance
wfa.plot_performance_comparison()

# Equity curves for all test periods
wfa.plot_test_equity_curves()

# Scatter plot: in-sample vs out-of-sample Sharpe
wfa.plot_is_vs_oos_scatter()
```

### WFA Performance Metrics

**Efficiency Ratio**:

```text
Efficiency Ratio = Out-of-Sample Sharpe / In-Sample Sharpe
```

- **Ratio > 0.8**: Excellent—strategy generalizes well
- **Ratio 0.5-0.8**: Acceptable—moderate degradation
- **Ratio < 0.5**: Poor—significant overfitting likely

**Degradation Percentage**:

```text
Degradation = (In-Sample Sharpe - Out-of-Sample Sharpe) / In-Sample Sharpe
```

- **Degradation < 20%**: Robust strategy
- **Degradation 20-40%**: Moderate overfitting
- **Degradation > 40%**: Severe overfitting—strategy likely unusable

**Parameter Consistency Score**:

```text
Consistency = 1 - (Std Dev of Parameters Across Windows / Mean Parameter Value)
```

- Measures how stable optimal parameters remain across windows
- High consistency = strategy captures real signal
- Low consistency = curve-fitting to noise

### WFA Best Practices

**1. Minimum Test Period Requirements**:

- Daily strategies: 30+ trades per test period
- Intraday strategies: 100+ trades per test period
- Position trading: 10+ trades per test period

**2. Avoid Look-Ahead Bias**:

- Never use test period data in training
- Recalculate indicators fresh at start of each window
- No peeking at future data for parameter selection

**3. Representative Time Periods**:

- Include at least one full market cycle (bull + bear)
- Minimum 3-5 years of data for meaningful WFA
- More windows = more reliable OOS estimate (aim for 10+ test periods)

**4. Statistical Significance**:

- Calculate confidence intervals for OOS Sharpe
- Use t-test to compare IS vs OOS performance
- Require OOS Sharpe statistically > 0 (p < 0.05)

**Example - Identifying Overfitting**:

```python
# Strategy A: Robust
In-Sample Sharpe:  1.8
Out-of-Sample Sharpe: 1.5
Efficiency Ratio: 0.83  ✅
Parameter Consistency: 78%  ✅
Verdict: Deploy to production

# Strategy B: Overfit
In-Sample Sharpe:  3.2
Out-of-Sample Sharpe: 0.4
Efficiency Ratio: 0.13  ❌
Parameter Consistency: 22%  ❌
Verdict: Reject - severely overfit to training data
```

---

## Part 2: Combinatorial Purged Cross-Validation & Probability of Backtest Overfitting

Traditional K-fold cross-validation fails for time series data due to look-ahead bias and autocorrelation. Combinatorial Purged Cross-Validation (CSCV) and Probability of Backtest Overfitting (PBO) provide rigorous methods to detect overfitting in trading strategies, particularly when multiple parameter sets or strategies are tested.

### Why Standard K-Fold CV Fails for Trading

#### Problem 1: Look-Ahead Bias

- Random train/test splits leak future information into training
- Labels (future returns) overlap between train/test due to autocorrelation
- Example: Today's feature computed using tomorrow's close price

#### Problem 2: Non-IID Data

- Returns exhibit autocorrelation, volatility clustering, trends
- Violates independence assumption of standard CV
- Adjacent samples are not independent observations

#### Problem 3: Temporal Structure Ignored

- Shuffling destroys time dependencies
- Can't test strategy on realistic sequential data
- Unrealistic performance estimates

### Combinatorial Purged Cross-Validation (CSCV)

Based on **Marcos López de Prado: "Advances in Financial Machine Learning" (Chapter 7)**

**Key Innovations**:

1. **Sequential Splits**: Preserve time ordering (no shuffling)
2. **Purging**: Remove training samples that overlap with test data
3. **Embargo**: Add buffer period between train/test to prevent leakage
4. **Combinatorial Paths**: Test all combinations of train/test folds

**Purged K-Fold Algorithm**:

```python
from simulor.analytics import CombinatorialPurgedCV

cscv = CombinatorialPurgedCV(
    n_splits=10,
    purge_pct=0.10,   # Remove 10% of training data near test boundary
    embargo_pct=0.01, # 1% embargo buffer after test period

    # Optional: Weight samples by uniqueness (de Prado's method)
    sample_weights='time_decay'  # or 'sequential_bootstrap', None
)

# Run CV on strategy parameters
cv_results = cscv.cross_validate(
    strategy=my_strategy,
    param_grid={'rsi_period': [10, 14, 20, 30]},
    data=historical_data
)
```

**How Purging Works**:

```text
Timeline: |--------Train--------|==Purge==|---Test---|==Embargo==|

Purge Zone: Remove training samples whose labels overlap with test period
- If feature at t=100 uses data through t=105 (5-day indicator)
- And test starts at t=100
- Purge training samples from t=95 to t=100

Embargo Zone: Buffer after test to prevent reverse leakage
- Prevents information from test influencing subsequent training folds
- Typical embargo: 1-2% of total timeline
```

**Configuration Parameters**:

```python
# Example: 252 trading days total, 10 folds

purge_pct = 0.10
# Purge zone = 252 * 0.10 = 25 days
# Remove 25 days of training data before each test fold

embargo_pct = 0.01
# Embargo = 252 * 0.01 = 2-3 days
# Skip 2-3 days after test before next train fold starts
```

### Probability of Backtest Overfitting (PBO)

Based on **Bailey, Borwein, López de Prado, Zhu (2014): "The Probability of Backtest Overfitting"**

**Core Concept**: If a strategy is not overfit, its performance on different out-of-sample test sets should be **symmetrically distributed around the median**. If most OOS results are below median while IS results are above median, the strategy is likely overfit.

**PBO Calculation Workflow**:

#### Step 1: Generate CSCV Splits

```python
# Run purged K-fold CV to get N train/test splits
n_splits = 16  # Must be even number for PBO

splits = cscv.generate_splits(data, n_splits=n_splits)
# Each split: (train_indices, test_indices)
```

#### Step 2: Optimize on Each Training Fold

```python
optimal_params = []
is_performance = []  # In-sample
oos_performance = []  # Out-of-sample

for train_idx, test_idx in splits:
    # Optimize on training data
    best_params = optimize_parameters(
        data[train_idx],
        param_grid=param_grid,
        metric='sharpe_ratio'
    )
    optimal_params.append(best_params)

    # Record in-sample performance
    is_sharpe = backtest(data[train_idx], best_params)
    is_performance.append(is_sharpe)

    # Record out-of-sample performance
    oos_sharpe = backtest(data[test_idx], best_params)
    oos_performance.append(oos_sharpe)
```

#### Step 3: Generate Combinatorial Paths

```python
# With N=16 splits, generate C = 2^(N-1) = 32,768 combinations
# Each combination represents one possible way to partition data

import itertools

n = len(oos_performance)
num_combinations = 2 ** (n - 1)  # 32,768 for N=16

# Generate all binary partitions
# Example partition [0,0,1,1,0,1,1,0] means:
# - Folds 0,1,4,7 in Group A
# - Folds 2,3,5,6 in Group B
```

#### Step 4: Calculate Performance Ranks

```python
def calculate_pbo(is_performance, oos_performance):
    """
    Calculate Probability of Backtest Overfitting

    Returns:
        pbo: float in [0, 1]
        interpretation: > 0.5 indicates likely overfitting
    """
    n = len(oos_performance)
    num_combinations = 2 ** (n - 1)

    overfitting_count = 0

    for combination in range(num_combinations):
        # Convert to binary partition
        partition = [(combination >> i) & 1 for i in range(n)]

        # Split into two groups
        group_a = [oos_performance[i] for i, p in enumerate(partition) if p == 0]
        group_b = [oos_performance[i] for i, p in enumerate(partition) if p == 1]

        # Calculate median ranks
        median_a = np.median(group_a)
        median_b = np.median(group_b)

        # Count if OOS median < IS median (sign of overfitting)
        is_median = np.median(is_performance)
        oos_median = np.median([median_a, median_b])

        if oos_median < is_median:
            overfitting_count += 1

    pbo = overfitting_count / num_combinations
    return pbo
```

#### Step 5: Interpret PBO Score

```python
pbo_score = calculate_pbo(is_performance, oos_performance)

print(f"Probability of Backtest Overfitting: {pbo_score:.1%}")

# Interpretation:
# PBO < 30%: Low overfitting risk - strategy likely robust
# PBO 30-50%: Moderate risk - proceed with caution
# PBO > 50%: High overfitting risk - reject strategy
# PBO > 70%: Severe overfitting - strategy is curve-fit to noise
```

**Example Results**:

```python
# Strategy A: Robust momentum strategy
is_sharpe = [1.8, 1.9, 1.7, 1.8, 1.9, 1.8, 1.7, 1.8, ...]
oos_sharpe = [1.5, 1.6, 1.4, 1.5, 1.6, 1.5, 1.4, 1.5, ...]

pbo = calculate_pbo(is_sharpe, oos_sharpe)
# PBO = 0.23 (23%) ✅ Low overfitting - deploy

# Strategy B: Overfit ML model
is_sharpe = [3.2, 3.5, 3.1, 3.4, 3.3, 3.2, 3.4, 3.1, ...]
oos_sharpe = [0.4, 0.6, -0.2, 0.3, 0.5, 0.1, -0.1, 0.4, ...]

pbo = calculate_pbo(is_sharpe, oos_sharpe)
# PBO = 0.82 (82%) ❌ Severe overfitting - reject
```

### Deflated Sharpe Ratio (DSR)

When testing multiple parameter combinations, the probability of finding a "lucky" parameter set increases. The Deflated Sharpe Ratio adjusts for this multiple testing problem.

**Formula**:

$$
\text{DSR} = \text{SR} \times \sqrt{1 - \frac{V[\text{SR}]}{n}}
$$

Where:

- $\text{SR}$ = Observed Sharpe ratio
- $V[\text{SR}]$ = Variance of Sharpe across trials
- $n$ = Number of trials (parameter combinations tested)

**Implementation**:

```python
def deflated_sharpe_ratio(sharpe_observed, sharpe_trials, n_trials):
    """
    Calculate Deflated Sharpe Ratio adjusting for multiple testing

    Args:
        sharpe_observed: Best Sharpe ratio found
        sharpe_trials: List of all Sharpe ratios from parameter search
        n_trials: Number of parameter combinations tested

    Returns:
        dsr: Deflated Sharpe Ratio
    """
    sharpe_variance = np.var(sharpe_trials)

    dsr = sharpe_observed * np.sqrt(1 - sharpe_variance / n_trials)

    return dsr

# Example: Testing 100 parameter combinations
sharpe_trials = [1.2, 0.8, 1.5, 0.9, ..., 2.1]  # 100 values
sharpe_best = max(sharpe_trials)  # 2.1

dsr = deflated_sharpe_ratio(sharpe_best, sharpe_trials, n_trials=100)
print(f"Raw Sharpe: {sharpe_best:.2f}")
print(f"Deflated Sharpe: {dsr:.2f}")

# Raw Sharpe: 2.10
# Deflated Sharpe: 1.45
# Interpretation: After adjusting for 100 trials, true skill is 1.45, not 2.1
```

**Interpretation**:

- DSR >> 1.0: Strategy has genuine edge even after multiple testing correction
- DSR ≈ 1.0: Marginal edge, may not survive transaction costs
- DSR < 1.0: No significant edge—likely found by chance

### Combined CSCV + PBO Workflow

```python
from simulor.analytics import OverfittingDetection

detector = OverfittingDetection(
    strategy=my_strategy,
    param_grid={
        'rsi_period': [10, 14, 20, 30],
        'sma_fast': [20, 30, 50],
        'sma_slow': [100, 150, 200]
    },
    n_splits=16,
    purge_pct=0.10,
    embargo_pct=0.01
)

# Run comprehensive overfitting analysis
results = detector.analyze()

# Results
print("=== Overfitting Detection Report ===")
print(f"\nPBO Score: {results.pbo:.1%}")
print(f"Interpretation: {results.pbo_interpretation}")
print(f"\nDeflated Sharpe: {results.deflated_sharpe:.2f}")
print(f"Raw Sharpe: {results.raw_sharpe:.2f}")
print(f"Deflation Factor: {results.deflation_factor:.2f}")
print(f"\nParameter Consistency: {results.param_consistency:.1%}")
print(f"Number of Trials: {results.n_trials}")

# Decision recommendation
if results.pbo < 0.3 and results.deflated_sharpe > 1.0:
    print("\n✅ DECISION: Low overfitting risk - proceed to production")
elif results.pbo < 0.5 and results.deflated_sharpe > 0.8:
    print("\n⚠️  DECISION: Moderate risk - additional validation recommended")
else:
    print("\n❌ DECISION: High overfitting risk - reject strategy")

# Detailed diagnostics
results.plot_pbo_distribution()
results.plot_is_vs_oos_performance()
results.plot_parameter_stability()
```

**Output Example**:

```text
=== Overfitting Detection Report ===

PBO Score: 28.4%
Interpretation: Low overfitting probability - strategy appears robust

Deflated Sharpe: 1.32
Raw Sharpe: 1.68
Deflation Factor: 0.79

Parameter Consistency: 74.2%
Number of Trials: 36

✅ DECISION: Low overfitting risk - proceed to production
```

---

## Part 3: Probabilistic Backtesting

Traditional backtesting reports single-point estimates: "Sharpe Ratio = 1.5", "Max Drawdown = 18%". But these are based on **one historical realization**—the market could have evolved differently. Probabilistic backtesting quantifies uncertainty by testing strategies on **distributions of plausible market scenarios**, not just one path.

### Motivation: Beyond Single-Path Backtesting

**The Problem with Deterministic Backtesting**:

```python
# Traditional backtest - Single result
backtest_result = run_backtest(strategy, historical_data)
print(f"Sharpe Ratio: {backtest_result.sharpe}")
# Output: Sharpe Ratio: 1.52

# Question: Is 1.52 robust, or did we get lucky with this particular market path?
```

**The Reality**:

- Historical prices are **one random draw** from infinite possible market evolutions
- Markets exhibit stochastic volatility, rare events, regime changes
- Strategy performance may vary dramatically across alternative plausible histories
- Single-path backtest = extremely small sample size (N=1)

**The Solution**: Generate **hundreds or thousands** of plausible alternative price paths using statistical models, run backtest on each path, and analyze the **distribution** of outcomes.

### Monte Carlo Path Generation Methods

#### Method 1: Bootstrap Resampling

Resample historical returns with replacement to create alternative market scenarios.

```python
from simulor.analytics import BootstrapSimulation

# Simple bootstrap
bootstrap = BootstrapSimulation(
    returns=historical_returns,
    n_paths=1000,
    block_size=20,  # Block bootstrap to preserve autocorrelation
    random_seed=42
)

simulated_paths = bootstrap.generate_paths()
# Output: 1000 alternative return sequences
```

**Advantages**:

- Non-parametric (no distribution assumptions)
- Captures empirical return distribution
- Simple and fast

**Disadvantages**:

- Limited to observed range (won't generate tail events beyond historical)
- Ignores volatility clustering dynamics
- Assumes past return distribution = future

#### Method 2: Parametric Simulation

Fit statistical distribution to returns and simulate from fitted model.

```python
from simulor.analytics import ParametricSimulation

# Fit t-distribution (heavy tails)
parametric = ParametricSimulation(
    returns=historical_returns,
    distribution='t',  # or 'normal', 'skewed-t', 'levy-stable'
    n_paths=1000,
    fit_method='mle',  # Maximum Likelihood Estimation
    random_seed=42
)

# Estimated parameters
print(f"Degrees of freedom: {parametric.params['df']:.1f}")
print(f"Location: {parametric.params['loc']:.4f}")
print(f"Scale: {parametric.params['scale']:.4f}")

simulated_paths = parametric.generate_paths()
```

**Advantages**:

- Can generate tail events beyond historical data
- Flexible distribution families (capture fat tails, skewness)
- Mathematically tractable

**Disadvantages**:

- Assumes returns are IID (ignores autocorrelation, volatility clustering)
- Distribution choice impacts results (model risk)
- May not capture regime changes

#### Method 3: GARCH Simulation

Model volatility clustering using GARCH processes—periods of high/low volatility persist.

```python
from simulor.analytics import GARCHSimulation
from arch import arch_model

# Fit GARCH(1,1) to historical returns
garch = GARCHSimulation(
    returns=historical_returns,
    model='GARCH',  # or 'EGARCH', 'GJR-GARCH'
    p=1, q=1,  # GARCH(p,q)
    distribution='t',  # Innovation distribution
    n_paths=1000,
    random_seed=42
)

# Estimated GARCH parameters
print(f"Omega (constant): {garch.params['omega']:.6f}")
print(f"Alpha (ARCH): {garch.params['alpha']:.4f}")
print(f"Beta (GARCH): {garch.params['beta']:.4f}")

simulated_paths = garch.generate_paths(horizon=252)  # 1 year ahead
```

**GARCH(1,1) Model**:

$$
r_t = \mu + \epsilon_t, \quad \epsilon_t = \sigma_t z_t, \quad z_t \sim t(\nu)
$$

$$
\sigma_t^2 = \omega + \alpha \epsilon_{t-1}^2 + \beta \sigma_{t-1}^2
$$

**Advantages**:

- Captures volatility clustering (realistic market dynamics)
- Models autocorrelation in volatility (not returns)
- Can incorporate leverage effects (EGARCH, GJR-GARCH)

**Disadvantages**:

- More complex estimation and simulation
- Requires sufficient historical data (252+ observations)
- Still assumes constant mean and distribution shape

#### Method 4: Regime-Switching Models

Allow market dynamics to switch between different states (bull/bear/crisis).

```python
from simulor.analytics import RegimeSwitchingSimulation

# Fit 3-regime model (bull, normal, bear)
regime_sim = RegimeSwitchingSimulation(
    returns=historical_returns,
    n_regimes=3,
    model='markov_switching',
    n_paths=1000,
    random_seed=42
)

# Detected regimes
print("Regime Parameters:")
for i, regime in enumerate(regime_sim.regimes):
    print(f"Regime {i+1}: μ={regime.mean:.2%}, σ={regime.std:.2%}")

# Transition matrix
print("\nTransition Probabilities:")
print(regime_sim.transition_matrix)

simulated_paths = regime_sim.generate_paths()
```

**Advantages**:

- Captures structural market changes
- Realistic crisis scenarios
- Different volatility regimes

**Disadvantages**:

- Complex estimation (EM algorithm)
- Overfitting risk with too many regimes
- Regime detection is uncertain

### Probabilistic Backtest Execution

#### Step 1: Generate Alternative Scenarios

```python
from simulor.analytics import ProbabilisticBacktest

prob_backtest = ProbabilisticBacktest(
    strategy=my_strategy,
    historical_data=historical_prices,

    # Simulation method
    simulation_method='garch',  # 'bootstrap', 'parametric', 'garch', 'regime'
    n_paths=1000,

    # GARCH configuration
    garch_model='GARCH',
    garch_p=1,
    garch_q=1,
    innovation_dist='t',

    # Backtest settings
    initial_capital=100000,
    start_date='2020-01-01',
    end_date='2023-12-31',

    random_seed=42  # Reproducibility
)
```

#### Step 2: Run Backtest on Each Path

```python
# Execute backtests in parallel
results = prob_backtest.run(n_jobs=-1)  # Use all CPU cores

print(f"Completed {results.n_paths} simulations")
print(f"Total runtime: {results.runtime:.1f} seconds")
```

#### Step 3: Analyze Performance Distributions

```python
# Access distributions (not single values)
sharpe_dist = results.sharpe_ratio
returns_dist = results.annual_return
drawdown_dist = results.max_drawdown

# Summary statistics
print("=== Probabilistic Backtest Results ===\n")

print(f"Sharpe Ratio:")
print(f"  Mean: {sharpe_dist.mean():.2f}")
print(f"  Std: {sharpe_dist.std():.2f}")
print(f"  Median: {sharpe_dist.median():.2f}")
print(f"  95% CI: [{sharpe_dist.quantile(0.025):.2f}, {sharpe_dist.quantile(0.975):.2f}]")

print(f"\nAnnual Return:")
print(f"  Mean: {returns_dist.mean():.1%}")
print(f"  Std: {returns_dist.std():.1%}")
print(f"  95% CI: [{returns_dist.quantile(0.025):.1%}, {returns_dist.quantile(0.975):.1%}]")

print(f"\nMax Drawdown:")
print(f"  Median: {drawdown_dist.median():.1%}")
print(f"  95th Percentile (worst case): {drawdown_dist.quantile(0.95):.1%}")
print(f"  99th Percentile: {drawdown_dist.quantile(0.99):.1%}")
```

**Example Output**:

```text
=== Probabilistic Backtest Results ===

Sharpe Ratio:
  Mean: 1.52
  Std: 0.28
  Median: 1.48
  95% CI: [1.02, 2.08]

Annual Return:
  Mean: 24.3%
  Std: 7.2%
  95% CI: [11.2%, 38.1%]

Max Drawdown:
  Median: 12.4%
  95th Percentile (worst case): 21.8%
  99th Percentile: 28.3%
```

**Interpretation**:

- **Sharpe 95% CI [1.02, 2.08]**: Strategy is robust—even in 5th percentile scenario, Sharpe > 1
- **Annual Return 95% CI [11.2%, 38.1%]**: Wide range—substantial uncertainty
- **Max DD 95th percentile 21.8%**: In worst 5% of scenarios, expect >20% drawdown

### Probabilistic Performance Metrics

**Risk-Adjusted Metrics with Confidence Intervals**:

```python
# Sharpe Ratio distribution
print(f"Sharpe Ratio: {results.sharpe.mean():.2f} ± {results.sharpe.std():.2f}")
print(f"  10th percentile: {results.sharpe.quantile(0.10):.2f}")
print(f"  50th percentile: {results.sharpe.quantile(0.50):.2f}")
print(f"  90th percentile: {results.sharpe.quantile(0.90):.2f}")

# Sortino Ratio distribution
print(f"\nSortino Ratio: {results.sortino.mean():.2f} ± {results.sortino.std():.2f}")

# Calmar Ratio distribution
print(f"\nCalmar Ratio: {results.calmar.mean():.2f} ± {results.calmar.std():.2f}")
```

**Probabilistic Tail Risk**:

```python
# Value-at-Risk (VaR) distribution
var_95 = results.value_at_risk(confidence=0.95)
print(f"95% VaR: {var_95.mean():.2%} (±{var_95.std():.2%})")

# Conditional VaR (Expected Shortfall)
cvar_95 = results.conditional_var(confidence=0.95)
print(f"95% CVaR: {cvar_95.mean():.2%}")

# Maximum Drawdown distribution
print(f"\nMax Drawdown Distribution:")
print(f"  Best case (5th %ile): {results.max_drawdown.quantile(0.05):.1%}")
print(f"  Median: {results.max_drawdown.median():.1%}")
print(f"  Worst case (95th %ile): {results.max_drawdown.quantile(0.95):.1%}")
```

**Probability of Achieving Targets**:

```python
# Probability of positive returns
prob_positive = (results.annual_return > 0).mean()
print(f"P(Annual Return > 0%): {prob_positive:.1%}")

# Probability of beating benchmark
benchmark_return = 0.10  # 10% S&P 500 return
prob_outperform = (results.annual_return > benchmark_return).mean()
print(f"P(Return > 10%): {prob_outperform:.1%}")

# Probability of Sharpe > 1.0
prob_sharpe = (results.sharpe_ratio > 1.0).mean()
print(f"P(Sharpe > 1.0): {prob_sharpe:.1%}")

# Probability of drawdown exceeding limit
prob_large_dd = (results.max_drawdown > 0.20).mean()
print(f"P(Max DD > 20%): {prob_large_dd:.1%}")
```

**Example Output**:

```text
Probabilistic Target Achievement:

P(Annual Return > 0%): 87.3%
P(Return > 10%): 78.2%
P(Sharpe > 1.0): 82.6%
P(Max DD > 20%): 15.4%

Interpretation:
- 87% chance of positive returns
- 78% chance of beating 10% benchmark
- 15% chance of >20% drawdown (acceptable risk)
```

### Visualizing Probabilistic Results

```python
# 1. Distribution histograms
results.plot_distributions()
# Shows: Sharpe, Return, Drawdown, Win Rate histograms with percentiles

# 2. Equity curve fan chart
results.plot_equity_fan(
    percentiles=[5, 25, 50, 75, 95],
    show_historical=True
)
# Shows: Range of possible equity curves (fan chart)

# 3. Risk/return scatter
results.plot_risk_return_scatter()
# X-axis: Max Drawdown, Y-axis: Annual Return, color by Sharpe

# 4. Probabilistic metrics
results.plot_metric_confidence_intervals(
    metrics=['sharpe_ratio', 'sortino_ratio', 'calmar_ratio']
)
# Bar chart with error bars showing 95% CI

# 5. Tail risk analysis
results.plot_tail_risk()
# VaR/CVaR distributions, drawdown percentiles
```

### Permutation Testing for Statistical Significance

**Concept**: Randomize trade entry/exit signals to test if strategy has genuine predictive power or if performance is due to chance.

**Null Hypothesis**: Strategy has no edge—performance is indistinguishable from random trading.

**Workflow**:

```python
from simulor.analytics import PermutationTest

perm_test = PermutationTest(
    strategy=my_strategy,
    historical_data=data,

    # Permutation settings
    n_permutations=1000,
    permutation_method='shuffle_signals',  # or 'shuffle_returns', 'block_shuffle'

    # Test metric
    metric='sharpe_ratio',  # or 'annual_return', 'sortino', 'calmar'

    random_seed=42
)

# Run permutation test
perm_results = perm_test.run()

# Actual strategy performance
actual_sharpe = perm_results.actual_metric
print(f"Actual Sharpe Ratio: {actual_sharpe:.2f}")

# Null distribution (permuted performance)
null_distribution = perm_results.null_distribution
print(f"Null Mean: {null_distribution.mean():.2f}")
print(f"Null Std: {null_distribution.std():.2f}")

# P-value: How often did permutations beat actual?
p_value = perm_results.p_value
print(f"\nP-value: {p_value:.4f}")

if p_value < 0.05:
    print("✅ Statistically significant - strategy has genuine edge")
else:
    print("❌ Not significant - performance may be due to chance")
```

**Permutation Methods**:

1. **Shuffle Signals**: Randomize buy/sell signals while preserving signal frequency
2. **Shuffle Returns**: Randomize return sequence (breaks autocorrelation)
3. **Block Shuffle**: Shuffle blocks of returns (preserves local autocorrelation)

**Example Output**:

```text
Permutation Test Results:

Actual Sharpe Ratio: 1.68

Null Distribution (1000 permutations):
  Mean: 0.12
  Std: 0.34
  95% CI: [-0.52, 0.78]

P-value: 0.003

✅ Statistically significant - strategy has genuine edge
(Only 0.3% of random permutations achieved Sharpe ≥ 1.68)
```

**Visualization**:

```python
perm_results.plot_null_distribution()
# Histogram of permuted Sharpe ratios
# Vertical line showing actual Sharpe
# Shaded region showing p-value
```

### Configuration & Best Practices

**Choosing Number of Paths**:

```python
# Quick validation: 100-500 paths
prob_backtest = ProbabilisticBacktest(..., n_paths=100)

# Standard analysis: 1000-2000 paths
prob_backtest = ProbabilisticBacktest(..., n_paths=1000)

# Publication-quality: 5000-10,000 paths
prob_backtest = ProbabilisticBacktest(..., n_paths=10000)
```

**Simulation Method Selection**:

- **Bootstrap**: Fast, non-parametric, good for moderate datasets
- **Parametric**: When you have strong distributional assumptions
- **GARCH**: Best for strategies sensitive to volatility regimes
- **Regime-Switching**: For strategies designed to adapt to market regimes

**Computational Considerations**:

```python
# Parallel execution for speed
results = prob_backtest.run(
    n_jobs=-1,  # Use all CPU cores
    verbose=True,  # Progress bar
    cache_dir='/tmp/prob_backtest'  # Cache intermediate results
)

# Distributed computing for large-scale simulations
from simulor.distributed import DistributedBacktest

dist_backtest = DistributedBacktest(
    prob_backtest_config=prob_backtest,
    cluster='ray',  # or 'dask', 'spark'
    n_workers=100
)

results = dist_backtest.run()
# Completes 10,000 simulations in minutes instead of hours
```

**Interpreting Results - Decision Framework**:

```python
def interpret_probabilistic_results(results):
    """Decision framework for probabilistic backtest results"""

    # Criteria 1: Median Sharpe
    median_sharpe = results.sharpe.median()

    # Criteria 2: 5th percentile Sharpe (bad luck scenario)
    worst_case_sharpe = results.sharpe.quantile(0.05)

    # Criteria 3: Probability of positive returns
    prob_positive = (results.annual_return > 0).mean()

    # Criteria 4: 95th percentile max drawdown
    worst_drawdown = results.max_drawdown.quantile(0.95)

    # Decision logic
    if median_sharpe > 1.5 and worst_case_sharpe > 0.8 and prob_positive > 0.85:
        return "DEPLOY - Highly robust strategy"
    elif median_sharpe > 1.0 and worst_case_sharpe > 0.5 and prob_positive > 0.75:
        return "PROCEED WITH CAUTION - Additional validation recommended"
    else:
        return "REJECT - Insufficient robustness across scenarios"

decision = interpret_probabilistic_results(results)
print(decision)
```

---

## Integration: Combined Overfitting Detection Workflow

The three anti-overfitting tools work together in a comprehensive validation pipeline:

```python
from simulor.analytics import ComprehensiveValidation

validator = ComprehensiveValidation(
    strategy=my_strategy,
    historical_data=data,

    # Walk-Forward Analysis
    wfa_config={
        'mode': 'anchored',
        'training_period': 252,
        'test_period': 63,
        'step_size': 21
    },

    # CSCV + PBO
    cscv_config={
        'n_splits': 16,
        'purge_pct': 0.10,
        'embargo_pct': 0.01
    },

    # Probabilistic Backtest
    prob_config={
        'simulation_method': 'garch',
        'n_paths': 1000
    },

    param_grid={
        'rsi_period': [10, 14, 20, 30],
        'sma_fast': [20, 30, 50],
        'sma_slow': [100, 150, 200]
    }
)

# Run complete validation suite
validation_results = validator.run_all()

# Unified report
print("=== COMPREHENSIVE OVERFITTING VALIDATION REPORT ===\n")

print("1. Walk-Forward Analysis:")
print(f"   OOS Sharpe: {validation_results.wfa.oos_sharpe:.2f}")
print(f"   Efficiency Ratio: {validation_results.wfa.efficiency_ratio:.2f}")
print(f"   Verdict: {validation_results.wfa.verdict}")

print("\n2. Combinatorial Analysis:")
print(f"   PBO Score: {validation_results.pbo.score:.1%}")
print(f"   Deflated Sharpe: {validation_results.pbo.deflated_sharpe:.2f}")
print(f"   Verdict: {validation_results.pbo.verdict}")

print("\n3. Probabilistic Backtest:")
print(f"   Median Sharpe: {validation_results.prob.median_sharpe:.2f}")
print(f"   5th Percentile Sharpe: {validation_results.prob.worst_case_sharpe:.2f}")
print(f"   P(Positive Return): {validation_results.prob.prob_positive:.1%}")
print(f"   Verdict: {validation_results.prob.verdict}")

print("\n" + "="*50)
print(f"FINAL RECOMMENDATION: {validation_results.final_verdict}")
print("="*50)

# Generate comprehensive PDF report
validation_results.export_report('validation_report.pdf')
```

**Example Output**:

```text
=== COMPREHENSIVE OVERFITTING VALIDATION REPORT ===

1. Walk-Forward Analysis:
   OOS Sharpe: 1.42
   Efficiency Ratio: 0.81
   Verdict: ✅ PASS - Good out-of-sample performance

2. Combinatorial Analysis:
   PBO Score: 32.4%
   Deflated Sharpe: 1.28
   Verdict: ✅ PASS - Low overfitting probability

3. Probabilistic Backtest:
   Median Sharpe: 1.38
   5th Percentile Sharpe: 0.92
   P(Positive Return): 86.3%
   Verdict: ✅ PASS - Robust across scenarios

==================================================
FINAL RECOMMENDATION: ✅ DEPLOY TO PRODUCTION
Strategy passes all overfitting validation tests
==================================================
```
