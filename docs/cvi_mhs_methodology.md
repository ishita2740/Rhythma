# CVI and MHS Methodology

This document outlines the scoring systems, mathematical formulations, and machine learning methodologies behind the Cycle Variability Index (CVI™) and the Menstrual Health Score (MHS™) in Rhythma.

---

## 🌸 Cycle Variability Index (CVI™)

The **Cycle Variability Index (CVI)** is a metric designed to quantify the stability and variability of a woman's menstrual cycles over a rolling window (up to the last 6 cycles). Higher scores indicate greater cycle irregularity, which can be an early indicator of conditions like PCOD/PCOS or elevated lifestyle stress.

### Feature Representation
To calculate or predict the CVI, the following features are extracted from the user's cycle logs:
1. **Mean Cycle Length**: Average duration in days between successive period start dates.
2. **Standard Deviation of Cycle Length**: Quantifies cycle length volatility.
3. **Mean Flow Duration**: Average number of bleeding days.
4. **Standard Deviation of Flow Duration**: Quantifies volatility in bleeding duration.
5. **Cycle Length Range**: Difference between the longest and shortest cycles logged.
6. **Mean Stress Level**: Average stress level rated on a scale from 1 (low) to 5 (high).
7. **Mean Sleep Hours**: Average nightly sleep duration.
8. **Recent Cycle Count**: Number of recent cycles used for features (3 to 6).

### Machine Learning Model
- **Algorithm**: XGBoost Regressor (`XGBRegressor`)
- **Inputs**: The 8 features listed above.
- **Target**: Continuous score from 0.0 to 100.0.
- **Output**: Predicts a continuous, multi-factor variability index.

### Heuristic Fallback
If the machine learning model is unavailable, a fallback calculation based on the standard deviation of cycle lengths is used:
$$\text{CVI} = \min(100.0, \sigma_{\text{lengths}} \times 8.0 + 30.0)$$

### Risk Tiers
The final CVI score is mapped to risk categories:
- **Low**: $\text{CVI} < 30$ (healthy stability)
- **Medium**: $30 \le \text{CVI} < 65$ (moderate variability / stress response)
- **High**: $\text{CVI} \ge 65$ (significant variability, potential PCOD/PCOS indicator)

---

## ❤️ Menstrual Health Score (MHS™)

The **Menstrual Health Score (MHS)** is a holistic index representing overall menstrual and reproductive wellness. MHS integrates cycle regularity (CVI) with daily lifestyle factors.

### Component Scores
MHS combines five independent health dimensions, each scored from 0 to 100 (where higher is better):
1. **CVI Component**: Inverted CVI score, representing regularity:
   $$\text{Score}_{\text{CVI}} = 100.0 - \text{CVI}$$
2. **Sleep Score**: Optimal sleep is centered around 8 hours, with penalties for deviation:
   $$\text{Score}_{\text{Sleep}} = \max(0.0, 100.0 - |\mu_{\text{sleep}} - 8.0| \times 15.0)$$
3. **Stress Score**: Inverted stress level, mapped to 0–100:
   $$\text{Score}_{\text{Stress}} = \max(0.0, 100.0 - (\mu_{\text{stress}} - 1.0) \times 25.0)$$
4. **Symptom Score**: Penalizes the average number of symptoms logged per cycle:
   $$\text{Score}_{\text{Symptom}} = \max(0.0, 100.0 - \mu_{\text{symptoms}} \times 10.0)$$
5. **Lifestyle Score**: Default baseline score (70.0) reflecting physical exercise and diet, to be integrated with profile tracking in future phases.

### Machine Learning Model
- **Algorithm**: Logistic Regression Classifier (`LogisticRegression`)
- **Inputs**: The 5 component scores listed above.
- **Methodology**: The model is trained on synthetic user profiles to classify "Optimal Menstrual Health" (defined as a weighted composite score $\ge 65$).
- **Inference**: During runtime, the model computes the probability of the positive class ($P(\text{Optimal})$) and scales it to a 0–100 score:
  $$\text{MHS} = P(\text{Optimal}) \times 100.0$$
  This logistic sigmoid mapping provides a smooth, non-linear score that is more sensitive to multiple concurrent risks.

### Heuristic Fallback
When the model is unavailable, MHS is calculated as a weighted linear combination of components:
$$\text{MHS} = 0.30 \times \text{Score}_{\text{CVI}} + 0.20 \times \text{Score}_{\text{Sleep}} + 0.20 \times \text{Score}_{\text{Stress}} + 0.15 \times \text{Score}_{\text{Symptom}} + 0.15 \times \text{Score}_{\text{Lifestyle}}$$

---

## 🔒 Privacy and Synthetic Training
To preserve user data privacy and comply with health data standards:
- **Zero Real Data**: All training is performed entirely on programmatically generated synthetic datasets modeling common healthy and irregular patient archetypes.
- **On-Device Fallback**: The model weights and heuristics run locally inside the API backend environment, ensuring sensitive patient logs never leave the secure application scope.
