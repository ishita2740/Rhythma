# Machine Learning Training Pipeline

This directory contains the pipeline for generating synthetic menstrual cycle datasets and training the machine learning models used in the Rhythma backend.

## Structure
- `generate_synthetic_data.py`: Script to simulate realistic cycle tracking logs for different user profiles (regular, irregular, high-stress, low-sleep).
- `train.py`: Script to train the XGBoost Regressor (for CVI) and Logistic Regression (for MHS) on the synthetic dataset, evaluate performance, and save model artifacts.
- `data/`: Generated dataset files (stored in CSV format).

## Dataset Source
Because real-world menstrual cycle datasets are highly private and regulated, we generate a synthetic dataset with realistic constraints. The generator models 4 distinct user profiles:
1. **Regular (Healthy)**: Stable 28-day cycle length, optimal sleep, low stress, and low symptom count.
2. **Irregular / PCOS-risk**: High variability in cycle length (e.g., standard deviation between 5 and 10 days, range up to 40 days), poor sleep, high stress, and frequent symptom occurrences.
3. **Stressed / Sleep-deprived**: Moderate cycle variability, low sleep, and high stress.
4. **Mixed / Random**: Normal distribution of attributes across all ranges.

## Training Process
1. **Cycle Variability Index (CVI)**:
   - **Model**: `XGBRegressor` from XGBoost.
   - **Features**: Mean cycle length, standard deviation of cycle lengths, mean flow duration, standard deviation of flow duration, cycle length range, mean stress level, mean sleep hours, and the recent cycle count.
   - **Target**: Continuous CVI score (0–100) calculated by combining standard deviation, cycle length range, stress levels, and sleep hours with random noise.

2. **Menstrual Health Score (MHS)**:
   - **Model**: `LogisticRegression` from scikit-learn.
   - **Features**: Component scores calculated for CVI, sleep, stress, symptoms, and lifestyle.
   - **Target**: Binary classification (1 = Optimal Menstrual Health, 0 = Sub-optimal / Needs Attention) defined by thresholding the weighted composite score of components at $\ge 65$.
   - **Inference**: During prediction, the model outputs the probability of class 1 (`predict_proba(features)[:, 1]`), which is scaled by 100 to produce the final score (0–100). This provides a smooth, non-linear representation of holistic health.

## Model Versioning
Model artifacts are exported to:
- `backend/models/cvi_model.joblib`
- `backend/models/mhs_model.joblib`

Whenever retraining models, run:
```bash
python generate_synthetic_data.py
python train.py
```
This will automatically overwrite the model artifacts in the models folder. These artifacts are tracked in Git.

## Privacy Considerations
Rhythma is a privacy-first application. No real-world user data or cloud database inputs are used in the training of these models. The entire training pipeline is self-contained and operates purely on programmatically generated synthetic data.
