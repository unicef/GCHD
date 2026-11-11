"""The 195 "state" country ucodes eligible for indices/classes normalization.

Ported verbatim from notebook 02. Only these units enter the global/country/
region index and class computations; every other unit is carried through the
output with blank numerics and a status flag.

Kept as a code constant (like the NB02 status rules in ``na_rules``) because the
notebook's list is the authoritative source for this step. If/when a canonical
CSV of state countries exists, this can switch to reading it.
"""

STATE_COUNTRIES = [
    "AFG_V1", "AGO_V1", "ALB_V1", "AND_V1", "ARE_V1", "ARG_V1", "ARM_V1", "ATG_V2",
    "AUS_V1", "AUT_V1", "AZE_V1", "BDI_V1", "BEL_V1", "BEN_V1", "BFA_V1", "BGD_V1",
    "BGR_V1", "BHR_V2", "BHS_V2", "BIH_V1", "BLR_V1", "BLZ_V1", "BOL_V1", "BRA_V1",
    "BRB_V2", "BRN_V1", "BTN_V1", "BWA_V1", "CAF_V1", "CAN_V1", "CHE_V1", "CHL_V1",
    "CHN_V1", "CIV_V1", "CMR_V1", "COD_V1", "COG_V1", "COL_V1", "COM_V2", "CPV_V2",
    "CRI_V1", "CUB_V2", "CYP_V1", "CZE_V1", "DEU_V1", "DJI_V1", "DMA_V2", "DNK_V1",
    "DOM_V2", "DZA_V1", "ECU_V1", "EGY_V1", "ERI_V1", "ESP_V1", "EST_V1", "ETH_V1",
    "FIN_V1", "FJI_V2", "FRA_V1", "FSM_V2", "GAB_V1", "GBR_V1", "GEO_V1", "GHA_V1",
    "GIN_V1", "GMB_V1", "GNB_V1", "GNQ_V1", "GRC_V1", "GRD_V2", "GTM_V1", "GUY_V1",
    "HND_V1", "HRV_V1", "HTI_V2", "HUN_V1", "IDN_V1", "IND_V1", "IRL_V1", "IRN_V1",
    "IRQ_V1", "ISL_V1", "ISR_V1", "ITA_V1", "JAM_V2", "JOR_V1", "JPN_V1", "KAZ_V1",
    "KEN_V1", "KGZ_V1", "KHM_V1", "KIR_V2", "KNA_V2", "KOR_V1", "KWT_V1", "LAO_V1",
    "LBN_V1", "LBR_V1", "LBY_V1", "LCA_V2", "LIE_V1", "LKA_V1", "LSO_V1", "LTU_V1",
    "LUX_V1", "LVA_V1", "MAR_V1", "MCO_V1", "MDA_V1", "MDG_V1", "MDV_V2", "MEX_V1",
    "MHL_V2", "MKD_V1", "MLI_V1", "MLT_V1", "MMR_V1", "MNE_V1", "MNG_V1", "MOZ_V1",
    "MRT_V1", "MUS_V2", "MWI_V1", "MYS_V1", "NAM_V1", "NER_V1", "NGA_V1", "NIC_V1",
    "NLD_V1", "NOR_V1", "NPL_V1", "NRU_V2", "NZL_V1", "OMN_V1", "PAK_V1", "PAN_V1",
    "PER_V1", "PHL_V1", "PLW_V2", "PNG_V1", "POL_V1", "PRK_V1", "PRT_V1", "PRY_V1",
    "PSE_V1", "QAT_V1", "ROU_V1", "RUS_V1", "RWA_V1", "SAU_V1", "SDN_V1", "SEN_V1",
    "SGP_V2", "SLB_V2", "SLE_V1", "SLV_V1", "SMR_V1", "SOM_V1", "SRB_V1", "SSD_V1",
    "STP_V2", "SUR_V1", "SVK_V1", "SVN_V1", "SWE_V1", "SWZ_V1", "SYC_V2", "SYR_V1",
    "TCD_V1", "TGO_V1", "THA_V1", "TJK_V1", "TKM_V1", "TLS_V1", "TON_V2", "TTO_V2",
    "TUN_V1", "TUR_V1", "TUV_V2", "TZA_V1", "UGA_V1", "UKR_V1", "URY_V1", "USA_V1",
    "UZB_V1", "VAT_V1", "VCT_V2", "VEN_V1", "VNM_V1", "VUT_V2", "WSM_V2", "YEM_V1",
    "ZAF_V1", "ZMB_V1", "ZWE_V1",
]
