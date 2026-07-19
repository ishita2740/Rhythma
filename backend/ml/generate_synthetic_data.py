import os
import random
import numpy as np
import pandas as pd

def generate_dataset(num_users=2000, seed=42):
    np.random.seed(seed)
    random.seed(seed)
    
    cvi_features_list = []
    cvi_targets = []
    
    mhs_features_list = []
    mhs_targets = []
    
    # Types of user profiles
    # 0: Regular/Healthy
    # 1: Irregular/High-stress/PCOS-risk
    # 2: Stressed/Sleep-deprived
    # 3: Random/Mixed
    
    for user_idx in range(num_users):
        profile_type = np.random.choice([0, 1, 2, 3], p=[0.4, 0.3, 0.2, 0.1])
        num_cycles = np.random.randint(3, 13)
        
        # Define simulation parameters based on profile
        if profile_type == 0:  # Regular
            mean_len = np.random.normal(28.0, 1.0)
            std_len = np.random.uniform(0.5, 1.8)
            mean_flow = np.random.normal(5.0, 0.5)
            std_flow = np.random.uniform(0.3, 0.8)
            mean_stress = np.random.normal(1.8, 0.4)
            mean_sleep = np.random.normal(7.8, 0.5)
            mean_symptoms = np.random.uniform(0.1, 1.0)
            lifestyle_score = np.random.normal(85.0, 5.0)
        elif profile_type == 1:  # Irregular / PCOS-risk
            mean_len = np.random.normal(34.0, 3.0)
            std_len = np.random.uniform(5.0, 10.0)
            mean_flow = np.random.normal(6.0, 1.2)
            std_flow = np.random.uniform(1.0, 2.0)
            mean_stress = np.random.normal(3.8, 0.6)
            mean_sleep = np.random.normal(5.8, 0.8)
            mean_symptoms = np.random.uniform(2.5, 5.0)
            lifestyle_score = np.random.normal(50.0, 8.0)
        elif profile_type == 2:  # Stressed / Sleep-deprived
            mean_len = np.random.normal(29.0, 1.5)
            std_len = np.random.uniform(1.5, 3.5)
            mean_flow = np.random.normal(5.0, 0.8)
            std_flow = np.random.uniform(0.5, 1.2)
            mean_stress = np.random.normal(4.2, 0.4)
            mean_sleep = np.random.normal(5.2, 0.6)
            mean_symptoms = np.random.uniform(1.0, 2.5)
            lifestyle_score = np.random.normal(60.0, 7.0)
        else:  # Mixed/Random
            mean_len = np.random.uniform(21.0, 40.0)
            std_len = np.random.uniform(1.0, 8.0)
            mean_flow = np.random.uniform(3.0, 8.0)
            std_flow = np.random.uniform(0.5, 2.0)
            mean_stress = np.random.uniform(1.0, 5.0)
            mean_sleep = np.random.uniform(4.5, 9.0)
            mean_symptoms = np.random.uniform(0.0, 6.0)
            lifestyle_score = np.random.uniform(30.0, 100.0)

        # Ensure parameters are within valid bounds
        mean_stress = max(1.0, min(5.0, mean_stress))
        mean_sleep = max(4.0, min(10.0, mean_sleep))
        lifestyle_score = max(0.0, min(100.0, lifestyle_score))
        
        # Simulate individual cycles
        lengths = np.random.normal(mean_len, std_len, num_cycles).round().astype(int)
        lengths = np.clip(lengths, 15, 60)
        
        flows = np.random.normal(mean_flow, std_flow, num_cycles).round().astype(int)
        flows = np.clip(flows, 2, 10)
        
        stresses = np.random.normal(mean_stress, 0.5, num_cycles)
        stresses = np.clip(stresses, 1.0, 5.0)
        
        sleeps = np.random.normal(mean_sleep, 0.6, num_cycles)
        sleeps = np.clip(sleeps, 4.0, 10.0)
        
        symptoms = np.random.poisson(mean_symptoms, num_cycles)
        
        # Limit to the most recent 6 cycles for CVI feature calculation (same as api/dashboard.py)
        recent_count = min(6, num_cycles)
        recent_lengths = lengths[:recent_count]
        recent_flows = flows[:recent_count]
        recent_stresses = stresses[:recent_count]
        recent_sleeps = sleeps[:recent_count]
        
        # Feature calculations
        mean_len_f = np.mean(recent_lengths)
        std_len_f = np.std(recent_lengths)
        mean_flow_f = np.mean(recent_flows)
        std_flow_f = np.std(recent_flows)
        range_len_f = max(recent_lengths) - min(recent_lengths)
        mean_stress_f = np.mean(recent_stresses)
        mean_sleep_f = np.mean(recent_sleeps)
        len_recent_f = len(recent_lengths)
        
        # Create CVI target score
        base_cvi = (
            std_len_f * 7.5 +
            range_len_f * 1.5 +
            (mean_stress_f - 1.0) * 4.5 +
            (8.0 - mean_sleep_f) * 3.0 +
            15.0
        )
        cvi_noise = np.random.normal(0.0, 2.5)
        cvi_target = max(0.0, min(100.0, base_cvi + cvi_noise))
        cvi_target = round(cvi_target, 1)
        
        cvi_features_list.append([
            mean_len_f, std_len_f, mean_flow_f, std_flow_f,
            range_len_f, mean_stress_f, mean_sleep_f, len_recent_f
        ])
        cvi_targets.append(cvi_target)
        
        # Calculate component scores for MHS
        cvi_comp = 100.0 - cvi_target
        sleep_comp = max(0.0, 100.0 - abs(mean_sleep_f - 8.0) * 15.0)
        stress_comp = max(0.0, 100.0 - (mean_stress_f - 1.0) * 25.0)
        avg_symptoms_f = np.mean(symptoms[:3]) if len(symptoms) >= 3 else np.mean(symptoms)
        symptom_comp = max(0.0, 100.0 - avg_symptoms_f * 10.0)
        lifestyle_comp = lifestyle_score
        
        composite_mhs = (
            cvi_comp * 0.30 +
            sleep_comp * 0.20 +
            stress_comp * 0.20 +
            symptom_comp * 0.15 +
            lifestyle_comp * 0.15
        )
        
        # Binary target: 1 = Good Menstrual Health, 0 = Needs Attention
        mhs_binary_target = 1 if composite_mhs >= 65.0 else 0
        
        mhs_features_list.append([
            cvi_comp, sleep_comp, stress_comp, symptom_comp, lifestyle_comp
        ])
        mhs_targets.append(mhs_binary_target)

    # Save to CSV
    cvi_df = pd.DataFrame(cvi_features_list, columns=[
        'mean_cycle_length', 'std_cycle_length', 'mean_flow_duration', 'std_flow_duration',
        'cycle_length_range', 'mean_stress', 'mean_sleep', 'recent_cycle_count'
    ])
    cvi_df['cvi_target'] = cvi_targets
    
    mhs_df = pd.DataFrame(mhs_features_list, columns=[
        'cvi_score', 'sleep_score', 'stress_score', 'symptom_score', 'lifestyle_score'
    ])
    mhs_df['mhs_target'] = mhs_targets
    
    return cvi_df, mhs_df

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    cvi, mhs = generate_dataset()
    cvi.to_csv(os.path.join(data_dir, 'cvi_synthetic_data.csv'), index=False)
    mhs.to_csv(os.path.join(data_dir, 'mhs_synthetic_data.csv'), index=False)
    print(f"Generated {len(cvi)} synthetic records for CVI and MHS.")
