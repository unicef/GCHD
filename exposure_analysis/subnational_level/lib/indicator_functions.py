# ============================================================
# Modular Functions for Exposure Index & Class Computation
# ============================================================
# indicator_functions.py

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import mapclassify 

@dataclass
class IndicatorUtils:
    indicator_metadata = ['geo_level', 'hazard', 'source', 'prod_date', 'dataflow', 'time_period']

    indicator_nominal = ['iso3', 
        'adm0_id', 'adm0_name', 'adm0_ucode', 
        'adm1_name', 'adm1_ucode', 'adm2_name', 'adm2_ucode',
        'unicef_region', 'unicef_region_full'
    ]

    indicator_hazard = ['hazs_mean', 'hazs_std', 'hazs_max', 'hazs_min', 'hazs_median']

    indicator_hazard_severity_index = ['gindex', 'cindex', 'rindex']

    indicator_population = ['pop_total', 'pop_total_m', 'pop_total_f', 'u18_pop_total', 'u18_pop_m', 'u18_pop_f']

    indicator_abs_exposure = ['aexp', 'amexp', 'afexp', 'u18_aexp', 'u18_amexp', 'u18_afexp']

    indicator_relative_exposure = ['rexp', 'rmexp', 'rfexp', 'u18_rexp', 'u18_rmexp', 'u18_rfexp']

    indicator_exposure_indices = [
        'gexpi', 'cexpi', 'rexpi', 
        'gmexpi', 'cmexpi', 'rmexpi', 
        'gfexpi', 'cfexpi', 'rfexpi', 
        'u18_gexpi', 'u18_cexpi', 'u18_rexpi', 
        'u18_gmexpi', 'u18_cmexpi', 'u18_rmexpi', 
        'u18_gfexpi', 'u18_cfexpi', 'u18_rfexpi'
    ]

    indicator_exposure_classes = [
        'gexpc', 'cexpc', 'rexpc', 
        'gmexpc', 'cmexpc', 'rmexpc', 
        'gfexpc', 'cfexpc', 'rfexpc', 
        'u18_gexpc', 'u18_cexpc', 'u18_rexpc', 
        'u18_gmexpc', 'u18_cmexpc', 'u18_rmexpc', 
        'u18_gfexpc', 'u18_cfexpc', 'u18_rfexpc'
    ]

    indicator_note = ['status']

    indicator_cols = \
        indicator_metadata + indicator_nominal + indicator_hazard + \
        indicator_hazard_severity_index + indicator_population + \
        indicator_abs_exposure + indicator_relative_exposure + \
        indicator_exposure_indices + indicator_exposure_classes + indicator_note

    def compute_exposure_index(
            self,
            df:pd.DataFrame, 
            log_aexp_col:str, 
            rexp_col:str, 
            output_col:str="expi"
        ):
        """
        Compute normalized exposure index (gexpi, cexpi, rexpi).
        
        Args:
            df: DataFrame with exposure data
            log_aexp_col: Column name for log-transformed absolute exposure
            rexp_col: Column name for relative exposure (%)
            log_aexp_min: Global min for normalization (if None, uses df min)
            log_aexp_max: Global max for normalization (if None, uses df max)
            output_col: Name for output index column
        
        Returns:
            DataFrame with added index column (0-10 scale)
        """
        df = df.copy()
        df[log_aexp_col] = pd.to_numeric(df[log_aexp_col])
        df[rexp_col] = pd.to_numeric(df[rexp_col])
        
        # Compute min and max
        log_aexp_min = df[log_aexp_col].min(skipna=True)
        log_aexp_max = df[log_aexp_col].max(skipna=True)
        
        # Normalize log absolute exposure
        if log_aexp_max > log_aexp_min:
            exp_norm = ((df[log_aexp_col] - log_aexp_min) / 
                        (log_aexp_max - log_aexp_min)) * 10
        else:
            exp_norm = 0.0
        
        # Geometric mean: sqrt((ExpNorm * 0.5) * (rexp/10 * 0.5))
        exps = np.sqrt((exp_norm * 0.5) * 
                    ((pd.to_numeric(df[rexp_col], errors="coerce") / 10) * 0.5))
        exps = exps.fillna(0.0)
        
        # Normalize geometric mean to 0-10 scale
        exps_max = exps.max(skipna=True)
        if exps_max > 0:
            df[output_col] = (exps / exps_max) * 10
        else:
            df[output_col] = 0.0
        
        df[output_col] = df[output_col].fillna(0.0).round(1)
        
        return df


    def compute_exposure_class(
            self,
            df, 
            expi_col, 
            aexp_col, 
            k=5, 
            output_col="expc"
        ):
        """
        Compute Fisher-Jenks classification for exposure index.
        
        Args:
            df: DataFrame with exposure index
            expi_col: Column name for exposure index (0-10)
            aexp_col: Column name for absolute exposure (for exposure detection)
            k: Number of classes
            output_col: Name for output class column
        
        Returns:
            DataFrame with added class column (1-k for exposed, 0 for no exposure)
        """
        df = df.copy()
        df[output_col] = 0
        
        # Identify exposed areas (absolute exposure > 0)
        aexp_num = pd.to_numeric(df.get(aexp_col, 0), errors="coerce").fillna(0)
        exposed_mask = aexp_num > 0
        exposed_indices = df[exposed_mask].index
        
        # Classify on the index rounded to the reported precision (1 decimal).
        # The exposure index is delivered rounded to 1dp; classifying on the
        # UNROUNDED value makes units that sit on a Fisher-Jenks break flip class
        # based on sub-decimal differences invisible in the output
        # ("what you see is what's classed"). Rounding first makes the class a
        # deterministic function of the reported index, so identical reported
        # indices always get the same class on re-runs.
        idx_vals = np.round(pd.to_numeric(df.loc[exposed_indices, expi_col], errors="coerce"), 1)
        # Exposed units with a valid (non-NaN) index are classified via Jenks;
        # exposed units whose index is NaN cannot be binned -> class 1 (lowest).
        valid_idx = idx_vals.dropna().index
        nan_idx = idx_vals.index.difference(valid_idx)
        df.loc[nan_idx, output_col] = 1

        if len(valid_idx) > 1:
            values = idx_vals.loc[valid_idx].values
            unique_values = np.unique(values)
            if len(unique_values) <= 1:
                df.loc[valid_idx, output_col] = 1
            else:
                effective_k = min(k, len(unique_values))
                try:
                    fj = mapclassify.FisherJenks(values, k=effective_k)
                    df.loc[valid_idx, output_col] = fj.yb + 1  # Classes 1-k
                except Exception as e:
                    print(f"  Warning: Fisher-Jenks classification failed: {e}")
                    df.loc[valid_idx, output_col] = 1
        elif len(valid_idx) == 1:
            df.loc[valid_idx, output_col] = 1

        df[output_col] = pd.to_numeric(df[output_col], errors="coerce")
        
        return df


    def compute_hazard_index(
            self,
            df, 
            hazs_max_col, 
            output_col="index"
        ):
        """
        Compute normalized hazard index (gindex, cindex, rindex).
        
        Args:
            df: DataFrame with hazard statistics
            hazs_max_col: Column name for max hazard value
            output_col: Name for output index column
        
        Returns:
            DataFrame with added hazard index column (0-10 scale)
        """
        df = df.copy()
        
        hazs_max = pd.to_numeric(df.get(hazs_max_col), errors="coerce")
        hazs_min = hazs_max.min(skipna=True)
        hazs_max_val = hazs_max.max(skipna=True)
        
        if hazs_max_val > hazs_min:
            df[output_col] = ((hazs_max - hazs_min) / (hazs_max_val - hazs_min)) * 10
        else:
            df[output_col] = 0.0
        
        df[output_col] = pd.to_numeric(df[output_col], errors="coerce").round(1)
        
        return df

    def get_all_indicator_columns(self):
        return self.indicator_cols.copy()
    
    def get_numeric_columns_for_NA(self):
        return ['exp_total', 'exp_total_female', 'exp_total_male', 'exp_under_18_female', 'exp_under_18_male', 'exp_under_18_total',
                'hazs_max', 'hazs_mean', 'hazs_median', 'hazs_min', 'hazs_std', 
                'pop_total', 'pop_total_female', 'pop_total_male', 'pop_under_18_female', 'pop_under_18_male', 'pop_under_18_total',
                'total_relative_exposure', 'total_log_total', 'total_log_exposure', 
                'under_18_total_relative_exposure', 'under_18_total_log_total', 'under_18_total_log_exposure', 
                'total_female_relative_exposure', 'total_female_log_total', 'total_female_log_exposure', 
                'total_male_relative_exposure', 'total_male_log_total', 'total_male_log_exposure', 
                'under_18_female_relative_exposure', 'under_18_female_log_total', 
                'under_18_female_log_exposure', 'under_18_male_relative_exposure', 'under_18_male_log_total', 
                'under_18_male_log_exposure',  
            ]
    
    def remove_non_children_indicators(self, indicators: list[str]):
        '''
        Function to filter out regular population indicators from a list of indicators, keeping only those relevant for children.
        
        Args:
            indicators (list[str]): List of indicator names.
        '''

        # Create a copy to not modify the entire list
        indicators_copy = indicators.copy()
        total_pop_indicators = [
            'pop_total', 'pop_total_m', 'pop_total_f', 'aexp', 'amexp', 'afexp', 'rexp', 'rmexp', 'rfexp', 'cexpi', 'cmexpi', 'cfexpi', 'cexpc', 'cmexpc', 'cfexpc'
        ]
        # Remove all global indicators
        indicators_copy = list(filter(lambda i: i not in total_pop_indicators, indicators_copy))
        return indicators_copy
    
    def remove_non_country_level(self, indicators: list[str]):
        '''
        Function to filter out global and regional indicators from a list of indicators.
        This is useful when processing data at a country level.
        
        Args:
            indicators (list[str]): List of indicator names.
        Returns:
            list[str]: Filtered list of indicator names without global/regional indicators.
        '''
        # Create a copy to not modify the entire list
        indicators_copy = indicators.copy()
        global_regional_indicators = [
            'gindex', 'gexpi', 'gmexpi', 'gfexpi', 'u18_gexpi', 'u18_gmexpi', 'u18_gfexpi', 'gexpc', 'gmexpc', 'gfexpc', 'u18_gexpc', 'u18_gmexpc', 'u18_gfexpc',
            'rindex', 'rexpi', 'rmexpi', 'rfexpi', 'u18_rexpi', 'u18_rmexpi', 'u18_rfexpi', 'rexpc', 'rmexpc', 'rfexpc', 'u18_rexpc', 'u18_rmexpc', 'u18_rfexpc'
        ]
        # Remove all global indicators
        indicators_copy = list(filter(lambda i: i not in global_regional_indicators, indicators_copy))
        return indicators_copy
    
    def round_cols(self, dataframe: pd.DataFrame):   
        try:
            df = dataframe.copy()     
            # Round hazard indicator columns to 2 decimals
            round_cols = self.indicator_hazard
            for col in round_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").round(5)
            # Round numeric columns to 1 decimal
            round_cols = self.indicator_hazard_severity_index + self.indicator_exposure_indices + self.indicator_relative_exposure
            for col in round_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").round(1)
            return df
        except Exception as e:
            print(f"Error rounding columns: {e}")
            return dataframe
    
    def get_rename_map(self):
        return {
        #'geo_level', 'hazard', 'source', 'prod_date', 'dataflow', 'time_period',
        'ISO3': 'iso3',
        #'adm0_id', 'adm0_name', 'adm0_ucode',
        #'adm1_name', 'adm1_ucode',
        'name': 'adm2_name', 'ucode': 'adm2_ucode',
        'Region_Code': 'unicef_region', 'Region': 'unicef_region_full',
        #'hazs_mean', 'hazs_std', 'hazs_max', 'hazs_min', 'hazs_median', 'gindex', 'cindex', 'rindex', 
        #'pop_total',
        'pop_total_male': 'pop_total_m', 'pop_total_female': 'pop_total_f',
        'pop_under_18_total': 'u18_pop_total', 'pop_under_18_male': 'u18_pop_m', 'pop_under_18_female': 'u18_pop_f',
        'exp_total': 'aexp', 'exp_total_male': 'amexp', 'exp_total_female': 'afexp',
        'exp_under_18_total': 'u18_aexp', 'exp_under_18_male': 'u18_amexp', 'exp_under_18_female': 'u18_afexp',
        'total_relative_exposure': 'rexp', 'total_male_relative_exposure': 'rmexp', 'total_female_relative_exposure': 'rfexp',
        'under_18_total_relative_exposure': 'u18_rexp', 'under_18_male_relative_exposure': 'u18_rmexp', 'under_18_female_relative_exposure': 'u18_rfexp',
        'gexpi_total': 'gexpi', 'cexpi_total': 'cexpi', 'rexpi_total': 'rexpi',
        'gexpi_total_male': 'gmexpi', 'cexpi_total_male': 'cmexpi', 'rexpi_total_male': 'rmexpi',
        'gexpi_total_female': 'gfexpi', 'cexpi_total_female': 'cfexpi', 'rexpi_total_female': 'rfexpi',
        'gexpi_under_18_total': 'u18_gexpi', 'cexpi_under_18_total': 'u18_cexpi', 'rexpi_under_18_total': 'u18_rexpi',
        'gexpi_under_18_male': 'u18_gmexpi', 'cexpi_under_18_male': 'u18_cmexpi', 'rexpi_under_18_male': 'u18_rmexpi',
        'gexpi_under_18_female': 'u18_gfexpi', 'cexpi_under_18_female': 'u18_cfexpi', 'rexpi_under_18_female': 'u18_rfexpi',
        'gexpc_total': 'gexpc', 'cexpc_total': 'cexpc', 'rexpc_total': 'rexpc',
        'gexpc_total_male': 'gmexpc', 'cexpc_total_male': 'cmexpc', 'rexpc_total_male': 'rmexpc',
        'gexpc_total_female': 'gfexpc', 'cexpc_total_female': 'cfexpc', 'rexpc_total_female': 'rfexpc',
        'gexpc_under_18_total': 'u18_gexpc', 'cexpc_under_18_total': 'u18_cexpc', 'rexpc_under_18_total': 'u18_rexpc',
        'gexpc_under_18_male': 'u18_gmexpc', 'cexpc_under_18_male': 'u18_cmexpc', 'rexpc_under_18_male': 'u18_rmexpc',
        'gexpc_under_18_female': 'u18_gfexpc', 'cexpc_under_18_female': 'u18_cfexpc', 'rexpc_under_18_female': 'u18_rfexpc'
    }