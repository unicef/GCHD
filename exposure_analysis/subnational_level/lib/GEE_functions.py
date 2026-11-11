# GEE_functions.py

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import os
import numpy as np
import pandas as pd

@dataclass
class GEEUtils:
    ee: Any  # injected: the authenticated 'ee' module from the notebook
    unicef_data_source_path: str = "projects/unicef-ccri/assets"
    population_paths_dict: Dict[str, Optional[str]] = None
    hazard_name: Optional[str] = None
    hazard_code: Optional[str] = None
    hazard_threshold: Optional[float] = None

    # Countries to be processed by admin1 due to their large size or singularities
    admin1_process_countries = ["CAN_V1", "USA_V1", "BRA_V1", "IND_V1", "CHN_V1", "AUS_V1", "AUS1_V1", "DZA_V1", "RUS_V1", "FIN_V1", "SRB_V1", "KAZ_V1", "GRL_V1"]
    admin2_process_regions = ["RUS_0002_V1", "RUS_0005_V1", "RUS_0008_V1"]
    admin2_process_large = ["CAN_0008_V1"]
    countries_no_population = [
        'ATA_V1', 'ATF1_V1', 'ATF2_V1', 'ATF3_V1', 'ATF_V1', 
        'BVT_V1', 
        'HMD_V1', 
        'IOT_V1', 
        'SGS_V1', 
        'UMI1_V1', 'UMI2_V1', 'UMI3_V1', 'UMI4_V1', 'UMI5_V1', 'UMI6_V1', 'UMI7_V1', 'UMI8_V1', 'UMI9_V1', 
        'VAT_V1', 
        'xAB_V1', 'xAC_V1', 'xAP_V1', 'xFR1_V1', 'xFR2_V1', 'xJK_V1', 'xJL_V1', 'xPI_V1', 'xRI_V1', 'xSI_V1', 'xSK_V1', 'xSR_V1', 'xUK1_V1', 'xUK2_V1', 'xxx_V1']
    
    #Status: Not applicable
    non_official_codes = ["ALA_V1", "CCK_V1", "CXR_V1", "ESH_V1", "GGY_V1", "JEY_V1", "NFK_V1", "PCN_V1", "SJM_V1"]

    # Status: Not applicable
    sovereignty_unsettled_countries = ['EGY1_V1', 'SDN1_V1', 'SSD1_V1', 'xAB_V1', 'xAC_V1', 'xAP_V1', 'xJK_V1', 'xJL_V1', 'xPI_V1', 'xRI_V1', 'xSI_V1', 'xSK_V1', 'xSR_V1', 'xxx_V1']

    prod_date: Optional[str] = dt.date.today().isoformat()
    time_period: Optional[int] = None
    dataflow: Optional[str] = None

    analysis_scale: Optional[Any] = None  # ee.Number
    valid_population_keys: list[str] = field(default_factory=list)

    ADMIN0_ASSET = "global_boundary/admin0_regions_merged"
    ADMIN1_ASSET = "global_boundary/admin1_regions_merged"
    ADMIN2_ASSET = "global_boundary/admin2_pop_geom" # asset of boundaries with population counts

    def get_admin2_boundaries(self, ucode:str, admin_level:str='adm0_ucode'):
        """
        Retrieves admin2 boundaries for a given administrative unit using its ucode.
        Parameters:
            ucode: unique identifier of country or territory.
            admin_level: adminstrative level to filter the boundaries list, can be adm0_ucode, adm1_ucode, admin2_ucode. Defaults to admin0_ucode.            
        Returns:
            GEE Feature Collection of admin2 boundaries for a country or territory.
        """
        if admin_level not in ['adm0_ucode', 'admin1_ucode', 'admin2_ucode']:
            raise Exception('Invalid admin_level value')
        admin_values = {
            'adm0_ucode': 'adm0_ucode',
            'admin1_ucode': 'adm1_ucode',
            'admin2_ucode': 'adm2_ucode'
        }
        ee = self.ee
        adm2_fc = ee.FeatureCollection(f"{self.unicef_data_source_path}/{self.ADMIN2_ASSET}")
        adm2_fc = adm2_fc.filter(ee.Filter.eq(admin_values[admin_level], ucode))
        # The asset stores some adm2 units more than once as separate features with
        # identical geometry and identical properties (e.g. NGA, SEN, SLE). Return one
        # feature per adm2_ucode so callers cannot double-count rows, area or population.
        adm2_fc = adm2_fc.distinct("adm2_ucode")
        adm2_fc = adm2_fc.map(lambda f: f.set("geo_level", "DISTRICT"))
        return adm2_fc    
    
    def get_country_boundaries(self, ucode):
        ee = self.ee
        adm0_fc = ee.FeatureCollection(f"{self.unicef_data_source_path}/{self.ADMIN0_ASSET}")
        adm0_fc = adm0_fc.filter(ee.Filter.eq("ucode", ucode))
        return adm0_fc


    def get_countries_to_process(self, countries_to_process_iso3: Optional[list[str]] = None):
        """
        Retrieves a list of country ucodes to process based on the provided list of ISO3 codes.
        If no list is provided, retrieves all country ucodes from the admin0 asset.
        Parameters:
            countries_to_process_iso3: Optional list of ISO3 country codes to filter the countries to process. If None, all countries will be processed.
        Returns:
            List of country ucodes to process.
        """
        try:
            ee = self.ee
            admin0_fc = ee.FeatureCollection(f"{self.unicef_data_source_path}/{self.ADMIN0_ASSET}")
            if countries_to_process_iso3:
                admin0_fc = admin0_fc.filter(ee.Filter.inList("ISO3", countries_to_process_iso3))
            #Remove countries with no available population data
            
            countries_to_process = admin0_fc.aggregate_array("ucode").getInfo()

            countries_not_available = set(self.countries_no_population)
            filtered_countries_list = sorted({
                item for item in countries_to_process
                if item not in countries_not_available
            })
            return filtered_countries_list
        except Exception as e:
            print(f"Error retrieving countries to process: {e}")
            return []
    
    def define_hazard(
            self,
            hazard,
            production_date=dt.date.today().isoformat(), 
            time_period=2025, 
            dataflow='UNICEF_DRAFT:DRAFT_HAZARD(1.0)'
        ):
        """
        Define hazard image based on hazard name.
        Set global constants for hazard processing.
        Parameters:
            hazard_textual_name: str, textual name of the hazard (e.g., 'Flood')
            asset_name: str, name of the GEE asset containing the hazard image
            hazard_code: str, code representing the hazard (e.g., 'FLD')
            threshold_value: float, threshold value to create hazard mask
            production_date: str, date of production in ISO format (default: today's date)
            time_period: int, time period of the hazard data (default: 2025)
            dataflow: str, dataflow identifier (default: 'UNICEF_DRAFT:DRAFT_HAZARD(1.0)')
            nodata: value representing no data in the hazard image (default: None)
            mosaic: bool, whether to mosaic the image collection (default: False)
        Returns:
            dict with keys 'hazard_raw_image' and 'hazard_masked_image'
        """
        ee = self.ee
        # Set global constants
        self.hazard_name = hazard.name
        self.hazard_code = hazard.code
        self.hazard_threshold = hazard.threshold

        # Set global output metadata
        self.prod_date = production_date
        self.time_period = time_period
        self.dataflow = dataflow

        # Load hazard image from GEE asset to be returned
        if hazard.mosaic:
            print(f'{hazard.asset} is mosaic')
            hazard_raw_image = ee.ImageCollection(hazard.asset).mosaic()
        else: 
            hazard_raw_image = ee.Image(hazard.asset)
            if hazard.band:
                hazard_raw_image = hazard_raw_image.select(hazard.band)

        # If no data value is specified, filter out based on theoretical minimum if provided, otherwise keep all values
        if hazard.apply_nodata:
            print(f"Applying no data mask with value: {hazard.nodata} and theoretical minimum: {hazard.th_min}")
            hazard_raw_image = hazard_raw_image.updateMask(hazard_raw_image.gte(hazard.th_min))

        # Filter by threshold if applicable
        hazard_masked_image = None

        if hazard.threshold == "mean":
            targetCRS = hazard_raw_image.projection()
            targetScale = hazard_raw_image.projection().nominalScale()
            adm0 = ee.FeatureCollection(f"{self.unicef_data_source_path}/{self.ADMIN0_ASSET}")

            def reproject_adm0(feature):
                return feature.transform(targetCRS)
            
            countryBoundariesReprojected = adm0.map(reproject_adm0)

            landSeaMask = ee.Image(1).clip(countryBoundariesReprojected)  # Clip using reprojected boundaries
            landSeaMask.unmask(0)  # Set sea pixels to 0
            landSeaMask.reproject(
                crs=targetCRS,
                scale=targetScale
            ).rename('landsea_mask');    
            
            hazard_layer_masked = hazard_raw_image.updateMask(landSeaMask)
            global_geometry = ee.Geometry.Polygon([[
                [-179.9, 89.9], [-179.9, -89.9], [179.9, -89.9], [179.9, 89.9]]
            ], None, False)

            threshold_value = hazard_layer_masked.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=global_geometry,
                scale=hazard_layer_masked.projection().nominalScale(),
                maxPixels=1e13
            ).values().get(0).getInfo()
            hazard.threshold = threshold_value
            print(f"Calculated global mean threshold value: {threshold_value}")

        print("apply threshold with: ", hazard.threshold)
        if hazard.threshold_operation == "gt":
            hazard_masked_image = hazard_raw_image.gt(hazard.threshold).rename("hazard_mask")
        elif hazard.threshold_operation == "gte":
            hazard_masked_image = hazard_raw_image.gte(hazard.threshold).rename("hazard_mask")
        elif hazard.threshold_operation == "lt":
            hazard_masked_image = hazard_raw_image.lt(hazard.threshold).rename("hazard_mask")
        elif hazard.threshold_operation == "lte":
            hazard_masked_image = hazard_raw_image.lte(hazard.threshold).rename("hazard_mask")
        else:
            # Use gt if no specified
            hazard_masked_image = hazard_raw_image.gt(hazard.threshold).rename("hazard_mask")

        # both raw and masked images are needed for different calculations
        return {'hazard_raw_image': hazard_raw_image, 'hazard_masked_image': hazard_masked_image}

    def get_population_classes(
        self,
        include_classes: list[str] | None = None
    ):
        """
        Retrieve selected population class images.

        Parameters
        ----------
        include_classes : list[str] | None
            Population classes to include (e.g. ["total", "under_18_total"]).
            If None, all available classes are included.

        Returns
        -------
        dict
            population_stack : ee.Image (multiband)
            valid_population_classes : dict[str, ee.Image]
        """
        ee = self.ee
        paths = self.population_paths_dict

        population_classes = {
            "total": ee.Image(paths["total"]) if paths.get("total") else None,
            "under_18_total": ee.Image(paths["total_under_18"]) if paths.get("total_under_18") else None,
            "total_female": ee.Image(paths["female"]) if paths.get("female") else None,
            "total_male": ee.Image(paths["male"]) if paths.get("male") else None,
            "under_18_female": ee.Image(paths["female_under_18"]) if paths.get("female_under_18") else None,
            "under_18_male": ee.Image(paths["male_under_18"]) if paths.get("male_under_18") else None,
        }

        # Filter classes
        if include_classes is not None:
            population_classes = {
                k: v for k, v in population_classes.items()
                if k in include_classes and v is not None
            }
        else:
            population_classes = {k: v for k, v in population_classes.items() if v is not None}

        if not population_classes:
            raise ValueError("No valid population classes selected.")

        # Canonical analysis scale
        self.analysis_scale = next(iter(population_classes.values())) \
            .projection().nominalScale()

        self.valid_population_keys = list(population_classes.keys())

        population_stack = (
            ee.ImageCollection(list(population_classes.values()))
            .toBands()
            .rename([f"pop_{k}" for k in population_classes.keys()])
        )

        return {
            "population_stack": population_stack,
            "valid_population_classes": population_classes
        }
    def get_population_exposure(
        self,
        hazard_image,
        valid_population_classes
    ):
        '''
        Gets stack of exposed population including all classes.

        Parameters:
            hazard_image: ee.Image of a specific hazard (e.g., flood or drought).
            valid_population_classes: list of valid population classes to extract the exposure.
        Returns:
            exposure_stack: ee.ImageCollection, stack of exposed population images.
        '''
        ee = self.ee
        population_absolute_exposures = {}

        for class_name, pop_image in valid_population_classes.items():
            # Create exposed population raster

            exp_image = pop_image.multiply(hazard_image).rename(f"exp_{class_name}")
            population_absolute_exposures[class_name] = exp_image

        exposure_stack = ee.ImageCollection(list(population_absolute_exposures.values()))\
                            .filter(ee.Filter.notNull(['system:index'])).toBands() \
                            .rename([f"exp_{key}" for key in valid_population_classes.keys()])
        
        return exposure_stack

    def get_population_hazard_statistics(
        self,
        exposure_stack,
        hazard_image, 
        admin2_feature_collection,
        tile_scale=4,
        population_stack=None
    ):    
        """
        Compute population and hazard statistics per admin2 unit.
        Parameters:
            exposure_stack: ee.ImageCollection, stack of population exposure images.
            hazard_image: ee.Image, hazard image. IMPORTANT: should be the raw hazard image, NOT masked based on threshold.
            admin2_feature_collection: ee.FeatureCollection, admin2 boundaries.
            tile_scale: int, tile scale for reduceRegions (default: 4).
        Returns:
            hazard_statistics_feature_collection containing total population sum, 
        exposed population sum, and hazard statistics per admin2 unit.
        """
        ee = self.ee
        composed_fc = admin2_feature_collection
        if population_stack is not None:
            # Add total population per admin2 unit to the exposure stack, to be included in the output statistics
            population_feature_collection = population_stack.reduceRegions(
                collection=admin2_feature_collection,
                reducer=ee.Reducer.sum(),
                scale=self.analysis_scale,
                tileScale=tile_scale
            )
            composed_fc = population_feature_collection


        # Compute population exposure per admin2 unit
        exposure_feature_collection = exposure_stack.reduceRegions(
            collection=composed_fc,
            reducer=ee.Reducer.sum(),
            scale=self.analysis_scale,
            tileScale=tile_scale
        )

        # Combined reducer for hazard statistics
        combined_reducer = (ee.Reducer.mean().setOutputs(["hazs_mean"]))\
                .combine(ee.Reducer.min().setOutputs(["hazs_min"]), sharedInputs=True)\
                .combine(ee.Reducer.max().setOutputs(["hazs_max"]), sharedInputs=True)\
                .combine(ee.Reducer.median().setOutputs(["hazs_median"]), sharedInputs=True)\
                .combine(ee.Reducer.stdDev().setOutputs(["hazs_std"]), sharedInputs=True)

        hazard_statistics_image = hazard_image.rename("haz").toFloat()

        # Add hazard mean/min/max/median/std
        hazard_statistics_feature_collection = hazard_statistics_image.reduceRegions(
            collection=exposure_feature_collection,
            reducer=combined_reducer,
            scale=self.analysis_scale,
            tileScale=tile_scale                       
        )

        return hazard_statistics_feature_collection
    
    def get_admin2_tiled_statistics(
        self,
        admin2_geometry: Any,
        admin2_feature: Any,
        exposure_stack: Any,
        hazard_image: Any,
        population_stack: Optional[Any] = None,
        tile_deg: float = 1.0,
        batch_size: int = 20,
        batch_cooldown: float = 5.0,
        tileScale: int = 4,
        admin2_geojson: Optional[dict] = None,
        feature_properties: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """
        Tiled processing for very large admin2 units (RUS/CAN).

        Key optimization: NO .clip(admin2_geometry) on images.
        Tile-polygon intersections are computed locally with shapely and
        used as reduction geometries.  reduceRegions naturally constrains
        to each feature's geometry — no clip in the computation graph.

        This eliminates the main bottleneck: .clip() on complex polygons
        (50k+ vertices) which GEE re-evaluates per-pixel on every API call.

        Parameters
        ----------
        admin2_geojson : dict, optional
            Pre-downloaded GeoJSON of the admin2 geometry.  If provided,
            skips the geometry .getInfo() call — useful when processing
            the same unit across multiple hazards.
        """
        import time as _time
        import math
        from shapely.geometry import shape as shp_shape, box as shp_box, mapping as shp_mapping
        from shapely.validation import make_valid

        ee = self.ee
        t0 = _time.time()

        # ═══════════════════════════════════════════════════════════
        # Phase 1: Download geometry, compute tile intersections LOCAL
        # ═══════════════════════════════════════════════════════════
        if isinstance(admin2_geometry, ee.featurecollection.FeatureCollection):
            admin2_geometry = admin2_geometry.geometry()

        if admin2_geojson is not None:
            geom_info = admin2_geojson
            print(f"  [Phase 1] Using pre-downloaded admin2 GeoJSON")
        else:
            print(f"  [Phase 1] Downloading admin2 geometry...")
            geom_info = admin2_geometry.getInfo()

        if feature_properties is not None:
            print(f"  [Phase 1] Using pre-loaded feature properties")
        else:
            feature_properties = admin2_feature.toDictionary().getInfo()

        admin2_shape = shp_shape(geom_info)
        if not admin2_shape.is_valid:
            admin2_shape = make_valid(admin2_shape)

        min_lon, min_lat, max_lon, max_lat = admin2_shape.bounds

        # Build grid and compute intersections locally (instant)
        tile_geoms = []
        lon = min_lon
        while lon < max_lon:
            lat = min_lat
            while lat < max_lat:
                tile_rect = shp_box(
                    lon, lat,
                    min(lon + tile_deg, max_lon + 0.001),
                    min(lat + tile_deg, max_lat + 0.001),
                )
                if tile_rect.intersects(admin2_shape):
                    intersection = tile_rect.intersection(admin2_shape)
                    if not intersection.is_empty and intersection.area > 0:
                        # Simplify to cut vertex count (~55 m tolerance,
                        # negligible at 100 m pixel size)
                        simplified = intersection.simplify(
                            0.0005, preserve_topology=True
                        )
                        if not simplified.is_empty:
                            tile_geoms.append(shp_mapping(simplified))
                lat += tile_deg
            lon += tile_deg

        print(f"  [Phase 1] {len(tile_geoms)} tiles intersect polygon "
              f"(grid over [{min_lon:.1f},{min_lat:.1f}]→"
              f"[{max_lon:.1f},{max_lat:.1f}])  "
              f"({_time.time()-t0:.1f}s)")

        if not tile_geoms:
            print("  ⚠ No tiles intersect admin2 — returning null result")
            return self._build_null_result(feature_properties)

        # ═══════════════════════════════════════════════════════════
        # Phase 2: Filter tiles with hazard data  (NO .clip!)
        #   Uses RAW hazard image + intersection geometries.
        # ═══════════════════════════════════════════════════════════
        haz_raw = hazard_image.rename("haz").toFloat()

        FILTER_BATCH = 200
        valid_tile_geoms = []

        for filt_start in range(0, len(tile_geoms), FILTER_BATCH):
            filt_end = min(filt_start + FILTER_BATCH, len(tile_geoms))
            filt_features = [
                ee.Feature(ee.Geometry(tile_geoms[i])).set('tidx', i)
                for i in range(filt_start, filt_end)
            ]
            filt_fc = ee.FeatureCollection(filt_features)
            try:
                counts_info = haz_raw.reduceRegions(
                    collection=filt_fc,
                    reducer=ee.Reducer.count(),
                    scale=10000,
                    tileScale=2,
                ).getInfo()
                for f in counts_info['features']:
                    cnt = f['properties'].get('count', 0) or 0
                    if cnt > 0:
                        valid_tile_geoms.append(
                            tile_geoms[f['properties']['tidx']]
                        )
            except Exception as e:
                print(f"    ⚠ Filter batch {filt_start}–{filt_end} failed "
                      f"({e}), keeping all")
                for i in range(filt_start, filt_end):
                    valid_tile_geoms.append(tile_geoms[i])
            _time.sleep(2)

        print(f"  [Phase 2] {len(valid_tile_geoms)} tiles with data, "
              f"{len(tile_geoms)-len(valid_tile_geoms)} empty skipped  "
              f"({_time.time()-t0:.1f}s)")

        if not valid_tile_geoms:
            print("  ⚠ No tiles with hazard data — returning null result")
            return self._build_null_result(feature_properties)

        # ═══════════════════════════════════════════════════════════
        # Phase 3: Prepare reducers, log plan  (NO .clip!)
        # ═══════════════════════════════════════════════════════════
        exp_bands = exposure_stack.bandNames().getInfo()

        pop_bands = []
        if population_stack is not None:
            pop_bands = population_stack.bandNames().getInfo()

        haz_reducer = (
            ee.Reducer.mean().setOutputs(["hazs_mean"])
            .combine(ee.Reducer.stdDev().setOutputs(["hazs_std"]),
                     sharedInputs=True)
            .combine(ee.Reducer.count().setOutputs(["hazs_count"]),
                     sharedInputs=True)
            .combine(ee.Reducer.min().setOutputs(["hazs_min"]),
                     sharedInputs=True)
            .combine(ee.Reducer.max().setOutputs(["hazs_max"]),
                     sharedInputs=True)
            .combine(ee.Reducer.median().setOutputs(["hazs_median"]),
                     sharedInputs=True)
        )

        n_batches = math.ceil(len(valid_tile_geoms) / batch_size)
        calls_per_batch = (1 if pop_bands else 0) + 1 + 1
        total_calls = n_batches * calls_per_batch

        print(f"  [Phase 3] {len(valid_tile_geoms)} tiles in "
              f"{n_batches} batches of ≤{batch_size}")
        print(f"            {calls_per_batch} calls/batch × {n_batches} "
              f"= {total_calls} total calls")
        print(f"            NO .clip() — intersection geometries used")
        print(f"            Bands: {len(pop_bands)} pop, "
              f"{len(exp_bands)} exp, 6 haz stats")

        # ═══════════════════════════════════════════════════════════
        # Phase 4: Batch reduceRegions on RAW images
        #   Features carry intersection geometries, so reduceRegions
        #   naturally constrains to pixels inside the admin2 unit.
        # ═══════════════════════════════════════════════════════════
        all_tile_results = []
        failed_batches = []
        call_count = 0

        for batch_idx in range(n_batches):
            b_start = batch_idx * batch_size
            b_end = min(b_start + batch_size, len(valid_tile_geoms))
            b_tile_geoms = valid_tile_geoms[b_start:b_end]
            batch_num = batch_idx + 1
            batch_t0 = _time.time()

            # Build FC from intersection geometries (NOT rectangles)
            b_features = [
                ee.Feature(ee.Geometry(tg)).set('tidx', i)
                for i, tg in enumerate(b_tile_geoms)
            ]
            b_fc = ee.FeatureCollection(b_features)

            b_results = [{} for _ in b_tile_geoms]
            batch_ok = True

            # ── Population (all bands, sum, one call) ──
            if pop_bands and population_stack is not None:
                try:
                    pop_info = population_stack.reduceRegions(
                        collection=b_fc,
                        reducer=ee.Reducer.sum(),
                        scale=self.analysis_scale,
                        tileScale=tileScale,
                    ).getInfo()
                    for f in pop_info['features']:
                        tidx = f['properties']['tidx']
                        for band in pop_bands:
                            b_results[tidx][band] = (
                                f['properties'].get(band, 0) or 0
                            )
                    call_count += 1
                except Exception as e:
                    print(f"    ✗ Batch {batch_num}/{n_batches} "
                          f"POP failed: {e}")
                    batch_ok = False
                _time.sleep(batch_cooldown)

            # ── Exposure (all 6 bands, sum, one call) ──
            if batch_ok:
                try:
                    exp_info = exposure_stack.reduceRegions(
                        collection=b_fc,
                        reducer=ee.Reducer.sum(),
                        scale=self.analysis_scale,
                        tileScale=tileScale,
                    ).getInfo()
                    for f in exp_info['features']:
                        tidx = f['properties']['tidx']
                        for band in exp_bands:
                            b_results[tidx][band] = (
                                f['properties'].get(band, 0) or 0
                            )
                    call_count += 1
                except Exception as e:
                    print(f"    ✗ Batch {batch_num}/{n_batches} "
                          f"EXP failed: {e}")
                    batch_ok = False
                _time.sleep(batch_cooldown)

            # ── Hazard (combined reducer, one call) ──
            if batch_ok:
                try:
                    haz_info = haz_raw.reduceRegions(
                        collection=b_fc,
                        reducer=haz_reducer,
                        scale=self.analysis_scale,
                        tileScale=tileScale,
                    ).getInfo()
                    haz_keys = [
                        'hazs_mean', 'hazs_std', 'hazs_count',
                        'hazs_min', 'hazs_max', 'hazs_median',
                    ]
                    for f in haz_info['features']:
                        tidx = f['properties']['tidx']
                        for key in haz_keys:
                            b_results[tidx][key] = (
                                f['properties'].get(key, 0)
                            )
                    call_count += 1
                except Exception as e:
                    print(f"    ✗ Batch {batch_num}/{n_batches} "
                          f"HAZ failed: {e}")
                    batch_ok = False
                _time.sleep(batch_cooldown)

            batch_elapsed = _time.time() - batch_t0
            total_elapsed = _time.time() - t0

            if batch_ok:
                all_tile_results.extend(b_results)
                rate = (call_count / total_elapsed
                        if total_elapsed > 0 else 0.1)
                remaining = total_calls - call_count
                eta_s = remaining / rate if rate > 0 else 0
                print(f"    ✓ Batch {batch_num}/{n_batches} "
                      f"({len(b_tile_geoms)} tiles, "
                      f"{batch_elapsed:.1f}s) | "
                      f"calls {call_count}/{total_calls} | "
                      f"elapsed {total_elapsed/60:.1f}min | "
                      f"ETA ~{eta_s/60:.1f}min")
            else:
                failed_batches.append((batch_idx, b_tile_geoms))
                print(f"    ✗ Batch {batch_num}/{n_batches} FAILED "
                      f"({batch_elapsed:.1f}s) | "
                      f"failures: {len(failed_batches)}")

        # ═══════════════════════════════════════════════════════════
        # Phase 5: Retry failed batches (smaller batch, lower tileScale)
        # ═══════════════════════════════════════════════════════════
        if failed_batches:
            retry_size = max(1, batch_size // 4)
            print(f"\n  [Phase 5] Retrying {len(failed_batches)} failed "
                  f"batches with batch_size={retry_size}...")
            _time.sleep(15)

            still_failed = []
            retry_ts = max(1, tileScale // 2)

            for orig_idx, orig_tile_geoms in failed_batches:
                for sub_start in range(0, len(orig_tile_geoms), retry_size):
                    sub_tg = orig_tile_geoms[sub_start:
                                             sub_start + retry_size]
                    sub_features = [
                        ee.Feature(ee.Geometry(tg)).set('tidx', i)
                        for i, tg in enumerate(sub_tg)
                    ]
                    sub_fc = ee.FeatureCollection(sub_features)
                    sub_results = [{} for _ in sub_tg]
                    sub_ok = True

                    # Pop
                    if pop_bands and population_stack is not None:
                        try:
                            r = population_stack.reduceRegions(
                                collection=sub_fc,
                                reducer=ee.Reducer.sum(),
                                scale=self.analysis_scale,
                                tileScale=retry_ts,
                            ).getInfo()
                            for f in r['features']:
                                tidx = f['properties']['tidx']
                                for band in pop_bands:
                                    sub_results[tidx][band] = (
                                        f['properties'].get(band, 0) or 0
                                    )
                        except Exception:
                            sub_ok = False
                        _time.sleep(batch_cooldown * 2)

                    # Exp
                    if sub_ok:
                        try:
                            r = exposure_stack.reduceRegions(
                                collection=sub_fc,
                                reducer=ee.Reducer.sum(),
                                scale=self.analysis_scale,
                                tileScale=retry_ts,
                            ).getInfo()
                            for f in r['features']:
                                tidx = f['properties']['tidx']
                                for band in exp_bands:
                                    sub_results[tidx][band] = (
                                        f['properties'].get(band, 0) or 0
                                    )
                        except Exception:
                            sub_ok = False
                        _time.sleep(batch_cooldown * 2)

                    # Haz
                    if sub_ok:
                        try:
                            r = haz_raw.reduceRegions(
                                collection=sub_fc,
                                reducer=haz_reducer,
                                scale=self.analysis_scale,
                                tileScale=retry_ts,
                            ).getInfo()
                            haz_keys = [
                                'hazs_mean', 'hazs_std', 'hazs_count',
                                'hazs_min', 'hazs_max', 'hazs_median',
                            ]
                            for f in r['features']:
                                tidx = f['properties']['tidx']
                                for key in haz_keys:
                                    sub_results[tidx][key] = (
                                        f['properties'].get(key, 0)
                                    )
                        except Exception:
                            sub_ok = False
                        _time.sleep(batch_cooldown * 2)

                    if sub_ok:
                        all_tile_results.extend(sub_results)
                        print(f"    ✓ Retry OK ({len(sub_tg)} tiles)")
                    else:
                        still_failed.append((orig_idx, sub_tg))
                        print(f"    ✗ Retry FAILED ({len(sub_tg)} tiles)")

            if still_failed:
                print(f"  ⚠ {len(still_failed)} sub-batches "
                      f"permanently failed")

        # ═══════════════════════════════════════════════════════════
        # Done: Aggregate
        # ═══════════════════════════════════════════════════════════
        total_elapsed = _time.time() - t0
        print(f"\n  [Done] {len(all_tile_results)} tile results | "
              f"{call_count} API calls | {total_elapsed/60:.1f} min")

        return self._aggregate_admin2_tile_results(
            all_tile_results,
            feature_properties,
            self.valid_population_keys,
        )

    def _aggregate_admin2_tile_results(
        self,
        tile_results: list,
        feature_properties: dict,
        population_keys: list
    ) -> dict:
        """Aggregate statistics from multiple tiles of an admin2 unit.
        
        Aggregation strategy:
        - Sums: add across tiles (population, exposure)
        - Mean: weighted average by count
        - Min/Max: global extremes
        - Median: estimated via percentile interpolation
        - StdDev: pooled standard deviation
        
        Args:
            tile_results: List of dicts with per-tile statistics
            feature_properties: Original feature properties to preserve
            population_keys: List of valid population class keys
            
        Returns:
            Dict with aggregated statistics
        """
        import math
        
        if not tile_results:
            return self._build_null_result(feature_properties)
        
        aggregated = {**feature_properties}
        
        # Population sums — only overwrite if tiles actually contain pop data.
        # When population_stack is None the correct values are already in
        # feature_properties (e.g. from local GeoJSON).
        first_has_pop = any(
            f"pop_{k}" in tile_results[0] for k in population_keys
        ) if tile_results else False

        if first_has_pop:
            for key in population_keys:
                pop_col = f"pop_{key}"
                total = sum(t.get(pop_col, 0) or 0 for t in tile_results)
                aggregated[pop_col] = total
        
        # Exposure sums
        for key in population_keys:
            exp_col = f"exp_{key}"
            total = sum(t.get(exp_col, 0) or 0 for t in tile_results)
            aggregated[exp_col] = total
        
        # Hazard statistics aggregation
        total_count = sum(t.get('hazs_count', 0) or 0 for t in tile_results)
        
        if total_count > 0:
            # Weighted mean
            weighted_mean = sum(
                (t.get('hazs_mean') or 0) * (t.get('hazs_count') or 1)
                for t in tile_results
            ) / total_count
            aggregated['hazs_mean'] = weighted_mean
            
            # Global min/max
            aggregated['hazs_min'] = min(
                t.get('hazs_min') for t in tile_results
                if t.get('hazs_min') is not None
            )
            aggregated['hazs_max'] = max(
                t.get('hazs_max') for t in tile_results
                if t.get('hazs_max') is not None
            )
            
            # Estimated median via percentile interpolation
            # Pool all tile medians weighted by count
            medians_weighted = [
                (t.get('hazs_median') or 0, t.get('hazs_count') or 1)
                for t in tile_results
            ]
            medians_weighted.sort(key=lambda x: x[0])
            
            cumulative_count = 0
            for median_val, count in medians_weighted:
                cumulative_count += count
                if cumulative_count >= total_count / 2:
                    aggregated['hazs_median'] = median_val
                    break
                else:
                    # Fallback: average of tile medians
                    aggregated['hazs_median'] = sum(m[0] for m in medians_weighted) / len(medians_weighted)
            
            # Pooled standard deviation
            variance_sum = 0.0
            for t in tile_results:
                tile_std = t.get('hazs_std') or 0
                tile_count = t.get('hazs_count') or 1
                # Contribution: count * (std² + (mean - global_mean)²)
                tile_mean = t.get('hazs_mean') or 0
                variance_sum += tile_count * (
                    (tile_std ** 2) + ((tile_mean - weighted_mean) ** 2)
                )
            
            pooled_std = math.sqrt(variance_sum / total_count) if variance_sum > 0 else 0
            aggregated['hazs_std'] = pooled_std
        else:
            # No hazard pixels at all — set stats to None
            for col in ('hazs_mean', 'hazs_min', 'hazs_max',
                        'hazs_median', 'hazs_std'):
                aggregated[col] = None
        
        # Output metadata
        aggregated['hazard'] = self.hazard_name
        aggregated['prod_date'] = self.prod_date
        aggregated['dataflow'] = self.dataflow
        aggregated['time_period'] = self.time_period

        return aggregated

    def _build_null_result(self, feature_properties: dict) -> dict:
        """Build a complete result dict with all stats columns set to None.

        Preserves admin2 metadata and population counts from
        feature_properties, fills exposure and hazard stats with None
        so downstream DataFrame processing (add_ratios_pandas, etc.)
        produces a valid row instead of crashing.
        """
        result = {**feature_properties}

        # Exposure columns — None (no hazard data → no exposure)
        for key in self.valid_population_keys:
            result[f'exp_{key}'] = None

        # Hazard stat columns — None
        for col in ('hazs_mean', 'hazs_min', 'hazs_max',
                    'hazs_median', 'hazs_std'):
            result[col] = None

        # Output metadata
        result['hazard'] = self.hazard_name
        result['prod_date'] = self.prod_date
        result['dataflow'] = self.dataflow
        result['time_period'] = self.time_period

        return result

    # ================================================================
    # Output column order — single source of truth for all notebooks
    # ================================================================
    OUTPUT_COLUMNS = [
        "Region", "Region_Code", "Regional_Grouping", "ISO3", "adm0_id", "adm0_name",
        "adm0_type", "adm0_ucode", "adm1_id", "adm1_name", "adm1_type",
        "adm1_ucode", "adm2_id", "adm2_name", "adm2_type", "adm2_ucode",
        "exp_total", "exp_total_female", "exp_total_male",
        "exp_under_18_female", "exp_under_18_male", "exp_under_18_total",
        "geo_level", "hazs_max", "hazs_mean", "hazs_median", "hazs_min", "hazs_std",
        "pop_total", "pop_total_female", "pop_total_male",
        "pop_under_18_female", "pop_under_18_male", "pop_under_18_total",
        "hazard", "prod_date", "dataflow", "time_period",
        "total_relative_exposure", "total_log_total", "total_log_exposure",
        "under_18_total_relative_exposure", "under_18_total_log_total", "under_18_total_log_exposure",
        "total_female_relative_exposure", "total_female_log_total", "total_female_log_exposure",
        "total_male_relative_exposure", "total_male_log_total", "total_male_log_exposure",
        "under_18_female_relative_exposure", "under_18_female_log_total", "under_18_female_log_exposure",
        "under_18_male_relative_exposure", "under_18_male_log_total", "under_18_male_log_exposure",
        "source",
    ]

    # ================================================================
    # Missing-data detection helpers
    # ================================================================
    def find_missing_adm2(
        self,
        output_folder: str,
        all_adm2_ucodes: list[str],
    ) -> dict[str, list[tuple[str, list[str]]]]:
        """Detect missing ADM2 units across all hazards in the output folder.

        Scans ``{output_folder}/hazards/*/partials/*.csv`` and compares
        the ``adm2_ucode`` column in each file against the global reference
        list, excluding countries with no population data.

        Parameters
        ----------
        output_folder : str
            Root output folder (e.g. ``"output_CO_updated"``).
        all_adm2_ucodes : list[str]
            Complete reference list of ADM2 ucodes from the GEE asset.

        Returns
        -------
        dict mapping ``hazard_code`` to a list of
        ``(filename, [missing_adm2_ucodes])`` tuples.
        """
        from pathlib import Path

        # Filter out countries with no population
        filtered_adm2 = all_adm2_ucodes.copy()
        for no_pop in self.countries_no_population:
            filtered_adm2 = [u for u in filtered_adm2 if no_pop not in u]

        hazards_root = Path(output_folder) / "hazards"
        if not hazards_root.exists():
            return {}

        errors: dict[str, list[tuple[str, list[str]]]] = {}

        for haz_dir in sorted(hazards_root.iterdir()):
            if not haz_dir.is_dir():
                continue
            haz_code = haz_dir.name
            partials_dir = haz_dir / "partials"
            if not partials_dir.exists():
                continue

            errors[haz_code] = []
            for csv_path in sorted(partials_dir.glob("*.csv")):
                country_prefix = csv_path.name[:4]  # e.g. "RUS_"
                try:
                    df = pd.read_csv(csv_path, usecols=["adm2_ucode"])
                    present = set(df["adm2_ucode"].unique())
                except Exception:
                    present = set()

                expected = [u for u in filtered_adm2 if u[:4] == country_prefix]
                missing = [u for u in expected if u not in present]
                if missing:
                    errors[haz_code].append((csv_path.name, missing))

        return errors

    # ================================================================
    # Local boundary loading for geometry caching
    # ================================================================
    @staticmethod
    def load_local_boundaries(bounds_folder: str) -> tuple[dict, dict]:
        """Load local GeoJSON boundary files into lookup dictionaries.

        Reads every ``*.geojson`` file in *bounds_folder* and builds two
        caches keyed by ``adm2_ucode``:

        * ``geojson_cache``  — ``{adm2_ucode: geometry_dict}``
        * ``properties_cache`` — ``{adm2_ucode: properties_dict}``

        Parameters
        ----------
        bounds_folder : str
            Path to directory containing ``*.geojson`` files.

        Returns
        -------
        (geojson_cache, properties_cache)
        """
        import json
        from pathlib import Path

        geojson_cache: dict = {}
        properties_cache: dict = {}

        folder = Path(bounds_folder)
        if not folder.exists():
            print(f"Bounds folder not found: {bounds_folder}")
            return geojson_cache, properties_cache

        for geojson_file in sorted(folder.glob("*.geojson")):
            with open(geojson_file, "r") as f:
                data = json.load(f)
            for feature in data.get("features", []):
                ucode = feature["properties"].get("adm2_ucode")
                if ucode:
                    geojson_cache[ucode] = feature["geometry"]
                    properties_cache[ucode] = feature["properties"]
            print(f"Loaded {geojson_file.name}: {len(data.get('features', []))} features")

        print(f"Total cached boundaries: {len(geojson_cache)}")
        return geojson_cache, properties_cache

    # ================================================================
    # Process a single missing ADM2 unit using tiled approach
    # ================================================================
    def process_missing_adm2_unit(
        self,
        hazard_images: dict,
        hazard_obj,
        country_ucode: str,
        adm2_ucode: str,
        geojson_cache: dict,
        properties_cache: dict,
        tile_deg: float = 1.0,
        batch_size: int = 20,
        batch_cooldown: float = 5.0,
        tileScale: int = 4,
    ) -> pd.DataFrame:
        """Process a single missing ADM2 unit via local tiling.

        Uses ``get_admin2_tiled_statistics`` with pre-cached local
        geometries to avoid expensive GEE geometry downloads.

        Parameters
        ----------
        hazard_images : dict
            Output of ``define_hazard()`` with ``hazard_raw_image`` and
            ``hazard_masked_image`` keys.
        hazard_obj : Hazard
            The current hazard being processed.
        country_ucode : str
            Country-level ucode (e.g. ``"CAN_V1"``).
        adm2_ucode : str
            The specific ADM2 unit to process (e.g. ``"CAN_0008_0001_V1"``).
        geojson_cache : dict
            Pre-loaded geometry cache (adm2_ucode → GeoJSON geometry dict).
        properties_cache : dict
            Pre-loaded properties cache (adm2_ucode → properties dict).
        tile_deg, batch_size, batch_cooldown, tileScale
            Tiling parameters passed through to ``get_admin2_tiled_statistics``.

        Returns
        -------
        pd.DataFrame
            DataFrame with processed statistics for the ADM2 unit,
            including computed ratios and source column.
            Empty DataFrame on failure.
        """
        ee = self.ee

        try:
            # Get admin2 boundaries from GEE asset
            bound = self.get_admin2_boundaries(adm2_ucode, 'admin2_ucode')

            # Set population dictionaries for the country
            self.set_population_dicts(country_ucode, bound)

            # Get population info
            population_info = self.get_population_classes()
            population_classes_dict = population_info['valid_population_classes']

            # Get exposure stack
            exposure_stack = self.get_population_exposure(
                hazard_images['hazard_masked_image'], population_classes_dict
            )

            # Prepare geometry and feature
            bound_feature = bound.first()
            bound_geometry = bound.geometry()

            # Use cached geometry if available, otherwise download and cache
            if adm2_ucode not in geojson_cache:
                print(f"  Downloading geometry for {adm2_ucode} (will cache)...")
                geojson_cache[adm2_ucode] = bound_geometry.getInfo()

            local_props = properties_cache.get(adm2_ucode, None)

            # Run tiled statistics
            stats_dict = self.get_admin2_tiled_statistics(
                admin2_geometry=bound_geometry,
                admin2_feature=bound_feature,
                exposure_stack=exposure_stack,
                hazard_image=hazard_images['hazard_raw_image'],
                population_stack=None,
                tile_deg=tile_deg,
                batch_size=batch_size,
                batch_cooldown=batch_cooldown,
                tileScale=tileScale,
                admin2_geojson=geojson_cache[adm2_ucode],
                feature_properties=local_props,
            )

            hazard_stats_fc = ee.FeatureCollection([ee.Feature(None, stats_dict)])
            stats_df = self.get_statistics_dataframe(hazard_stats_fc)

            if len(stats_df) == 0:
                print(f"  Empty result for {adm2_ucode}")
                return pd.DataFrame()

            stats_df = self.add_ratios_pandas(stats_df)
            stats_df['source'] = hazard_obj.asset.split('/').pop()
            return stats_df

        except Exception as e:
            print(f"  Error processing missing ADM2 {adm2_ucode}: {e}")
            return pd.DataFrame()

    # ================================================================
    # Merge new results into existing partial CSV
    # ================================================================
    def merge_missing_results(
        self,
        new_df: pd.DataFrame,
        existing_file_path: str,
        output_path: str,
    ) -> None:
        """Merge newly computed rows into an existing partial CSV.

        Reads the existing file, concatenates with *new_df*, deduplicates
        on ``adm2_ucode`` (keeping the new row), sorts, and writes to
        *output_path*.

        Parameters
        ----------
        new_df : pd.DataFrame
            Newly computed rows to merge.
        existing_file_path : str
            Path to the existing partial CSV.
        output_path : str
            Where to write the merged result (can be same as existing).
        """
        cols = [c for c in self.OUTPUT_COLUMNS if c in new_df.columns]
        new_df = new_df.reset_index(drop=True)[cols]

        if os.path.exists(existing_file_path):
            old_df = pd.read_csv(existing_file_path)
            merged = pd.concat([old_df, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=["adm2_ucode"], keep="last")
            merged = merged.sort_values(by="adm2_ucode", ascending=True).reset_index(drop=True)
        else:
            merged = new_df.sort_values(by="adm2_ucode", ascending=True).reset_index(drop=True)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        merged.to_csv(output_path, index=False)

    def add_ratios_pandas(self, df):
        '''
        Adds relative exposed population, logarithmic total, and logarithmic exposure columns to a pandas DataFrame.
        Parameters:
            df: pd.DataFrame, DataFrame with population and exposure columns.
        Returns:
            df: pd.DataFrame, enriched with new columns.
        '''
        def percentage(exp, pop):
            if pd.notna(pop) and pd.notna(exp) and pop != 0:
                return exp / pop * 100
            elif pd.notna(exp) and pop == 0:
                return 0
            else:
                return pd.NA

        def log_with_offset(population):
            if pd.notna(population) and population > 0:
                return np.log(population + 1)
            elif pd.isna(population):
                return pd.NA
            else:
                return 0

        # Add base response fields as columns
        df = df.copy()  # Avoid modifying original
        df["hazard"] = self.hazard_name
        df["prod_date"] = self.prod_date
        df["dataflow"] = self.dataflow
        df["time_period"] = self.time_period

        # Compute for each population class
        for class_name in self.valid_population_keys:
            pop_col = f"pop_{class_name}"
            exp_col = f"exp_{class_name}"
            if pop_col in df.columns and exp_col in df.columns:
                df[f"{class_name}_relative_exposure"] = df.apply(
                    lambda row: percentage(row[exp_col], row[pop_col]), axis=1
                )
                df[f"{class_name}_log_total"] = df[pop_col].apply(log_with_offset)
                df[f"{class_name}_log_exposure"] = df[exp_col].apply(log_with_offset)

                df[exp_col] = pd.to_numeric(df[exp_col], errors="coerce").round(1)
        return df

    def get_statistics_dataframe(
            self,
            hazard_statistics_feature_collection,
        ):
        '''
        Converts hazard statistics FeatureCollection to Pandas DataFrame.
        Parameters:
            hazard_statistics_feature_collection: ee.FeatureCollection, the feature collection containing hazard statistics.
        Returns:
            df: pd.DataFrame, DataFrame containing the hazard statistics.
        '''
        # WARNING: getInfo() can be heavy. For global ADM2, prefer Export.table.toDrive.
        # Workaround for collections with > 5000 features
        # Filter per admin 1 level and concatenate results
        try:
            features = hazard_statistics_feature_collection.getInfo()["features"]
            rows = [f["properties"] for f in features]
            df = pd.DataFrame(rows)
            try:
                df = self._process_null_exposure(df)
            except Exception as null_exp_error:
                print(f"Error setting to null exposed population when hazard data is null: {null_exp_error}")
                pass
            try:
                df = self._ceil_columns(df)
                return df
            except Exception as ceil_error:
                print(f"Error ceiling the population counts: {ceil_error}")
                return df
        except Exception as e:
            print(f"Error converting FeatureCollection to DataFrame: {e}")
            return pd.DataFrame()  # Return empty DataFrame on error
    
    def _process_null_exposure(self, df):
        '''
        Sets the exposed population to null if hazard statistics are null.
        Needed as GEE ee.Reducer.Sum() returns 0 on masked areas instead of null.

        Params:
            df: dataframe with hazard statistics, exposed population count and other info.
        Returns:
            Processed df with null exposed population on masked hazard areas.
        '''
        df_copy = df.copy()
        indices = pd.isna(df_copy['hazs_mean'])
        df_copy.loc[indices, ['exp_total', 'exp_under_18_total', 'exp_total_female', 'exp_total_male', 'exp_under_18_female', 'exp_under_18_male']] = np.nan
        return df_copy
        


    def _ceil_columns(self, df):
        '''
        Ceils population columns (total and exposed).
        Parameters:
            df: Results dataframe
        Returns:
            df: Results dataframe ceiled population numbers
        '''
        for key in self.valid_population_keys:
            # Ceiling population and exposed counts to Int64
            pop_col = f"pop_{key}"
            exp_col = f"exp_{key}"
            if pop_col in df.columns:
                df[pop_col] = np.ceil(pd.to_numeric(df[pop_col], errors="coerce")).astype("Int64")
            if exp_col in df.columns:
                df[exp_col] = np.ceil(pd.to_numeric(df[exp_col], errors="coerce")).astype("Int64")


        return df
    
    def check_process_by_admin1(self, ucode: str):
        '''
        Checks a country by admin0 ucode to determine if it should process the entire country or subdivide per administrative level 1 unit.
        Returns True if it is a large-sized country or a country with a singularity in one or more of its admin1 elements, or False otherwise.
        Parameters:
            ucode: unique code of a country
        Returns:
            boolean: True if it is within the large or singular countries list, False otherwise
        '''
        if ucode in self.admin1_process_countries: return True
        return False
    
    def check_process_by_admin2(self, ucode_admin1: str):
        """
        Checks an admin1 ucode to determine if it should be processed by admin2 level.
        Returns True if it is a large-sized admin1 unit, or False otherwise.
        Parameters:
            ucode_admin1: unique code of an admin1 unit
        Returns:
            boolean: True if it is within the large admin1 list, False otherwise
        """
        if ucode_admin1 in self.admin2_process_regions: return True
        return False

    def check_process_large_adm2(self, ucode_admin1: str):
        """
        Checks an admin1 ucode to determine if it should be processed by admin2 level at large scale.
        Returns True if it is a large-sized admin2 unit, or False otherwise.
        Parameters:
            ucode_admin2: unique code of an admin1 unit
        Returns:
            boolean: True if it is within the large admin1 list, False otherwise
        """
        if ucode_admin1 in self.admin2_process_large: return True
        return False


    def iso3_data_check(self, iso3: str):
        """
        Checks an country ISO3 code to determine if it should process it regularly, skip it, or treat it as a problematic country.
        Returns True if it is a regular country, False for countries with singularities.
        """
        countries_with_pop_issues = ["ATA", "ATF", "BVT", "CPT", "HMD", "IOT", "SGS", "UMI", "VAT", "x"]
        if iso3 in countries_with_pop_issues: return False
        return True

    def get_unique_elements_from_list(self, array):
        """
        Get the unique values of a list

        Parameters:
            array: The list to check
        Returns:
            boolean: True if it is within the large or singular countries list, False otherwise
        
        :param 
        """
        new_list = []
        for element in array:
            if element not in new_list:
                new_list.append(element)
        return new_list
    
    def set_population_dicts(self, adm0_ucode:str, admin2_feature_collection, is_2024=False):
        """
        Centralize the population dictionary assignment to allocate edge cases (which are plenty!).

        Args:
            adm0_ucode: The unique code of an admin0 unit (country)
            admin2_feature_collection: The admin2 feature collection for the country
        """
        country_iso3 = adm0_ucode[0:3]
        iso3_lower = country_iso3[0:3].lower()
        unicef_data_source_path = self.unicef_data_source_path

        if not is_2024:
            # The generic one
            temp_population_paths_dict = {
                "total":           f"{unicef_data_source_path}/population/worldpop_T_2025_CN_100m/{iso3_lower}_T_2025_CN_100m_R2025A_v1",
                "female":          f"{unicef_data_source_path}/population/worldpop_T_F_2025_CN_100m/{iso3_lower}_T_F_2025_CN_100m_R2025A_v1",
                "male":            f"{unicef_data_source_path}/population/worldpop_T_M_2025_CN_100m/{iso3_lower}_T_M_2025_CN_100m_R2025A_v1",
                "total_under_18":  f"{unicef_data_source_path}/population/worldpop_T_U18_2025_CN_100m/{iso3_lower}_T_Under_18_2025_CN_100m_R2025A_v1",
                "female_under_18": f"{unicef_data_source_path}/population/worldpop_T_F_U18_2025_CN_100m/{iso3_lower}_F_Under_18_2025_CN_100m_R2025A_v1",
                "male_under_18":   f"{unicef_data_source_path}/population/worldpop_T_M_U18_2025_CN_100m/{iso3_lower}_M_Under_18_2025_CN_100m_R2025A_v1"
            }

            if "FJI" in adm0_ucode or "GRL" in adm0_ucode or "RUS" in adm0_ucode:
                # Change the U18 population paths to the 2024 dataset
                temp_population_paths_dict["total_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_U18_2025_CN_100m/{iso3_lower}_T_Under_18_2024_CN_100m_R2025A_v1"
                temp_population_paths_dict["female_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_F_U18_2025_CN_100m/{iso3_lower}_F_Under_18_2024_CN_100m_R2025A_v1"
                temp_population_paths_dict["male_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_M_U18_2025_CN_100m/{iso3_lower}_M_Under_18_2024_CN_100m_R2025A_v1"

            # Special pop for Alaska
            elif "USA" in adm0_ucode:
                admin1_ucode = admin2_feature_collection.first().get('adm1_ucode').getInfo()
                if "USA_0002" in admin1_ucode: # Alaska-specific adm1 ucode
                    print("special pop for Alaska")
                    # change the total populations to the Alaska dataset
                    temp_population_paths_dict["total"] = f"{unicef_data_source_path}/population/worldpop_T_2025_CN_100m/ak_T_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["female"] = f"{unicef_data_source_path}/population/worldpop_T_F_2025_CN_100m/ak_T_F_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["male"] = f"{unicef_data_source_path}/population/worldpop_T_M_2025_CN_100m/ak_T_M_2025_CN_100m_R2025A_v1"

            # Special pop for Aaland Island (Finland) - ALA
            elif "FIN" in adm0_ucode:
                admin1_ucode = admin2_feature_collection.first().get('adm1_ucode').getInfo()
                if "FIN_0001" in admin1_ucode:
                    print("special pop for Aaland Island")
                    temp_population_paths_dict["total"] = f"{unicef_data_source_path}/population/worldpop_T_2025_CN_100m/ala_T_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["female"] = f"{unicef_data_source_path}/population/worldpop_T_F_2025_CN_100m/ala_T_F_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["male"] = f"{unicef_data_source_path}/population/worldpop_T_M_2025_CN_100m/ala_T_M_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["total_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_U18_2025_CN_100m/ala_T_Under_18_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["female_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_F_U18_2025_CN_100m/ala_F_Under_18_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["male_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_M_U18_2025_CN_100m/ala_M_Under_18_2025_CN_100m_R2025A_v1"

            # Special pop for Kosovo
            # Kosovo's boundaries data are included within Serbia's dataset.
            elif "SRB" in adm0_ucode:
                if "SRB_0001" in admin2_feature_collection.first().get('adm1_ucode').getInfo():
                    print("special pop for Kosovo")
                    temp_population_paths_dict["total"] = f"{unicef_data_source_path}/population/worldpop_T_2025_CN_100m/xkx_T_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["female"] = f"{unicef_data_source_path}/population/worldpop_T_F_2025_CN_100m/xkx_T_F_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["male"] = f"{unicef_data_source_path}/population/worldpop_T_M_2025_CN_100m/xkx_T_M_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["total_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_U18_2025_CN_100m/xkx_T_Under_18_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["female_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_F_U18_2025_CN_100m/xkx_F_Under_18_2025_CN_100m_R2025A_v1"
                    temp_population_paths_dict["male_under_18"] = f"{unicef_data_source_path}/population/worldpop_T_M_U18_2025_CN_100m/xkx_M_Under_18_2025_CN_100m_R2025A_v1"
        else:
            temp_population_paths_dict = {
                "total":           None,
                "female":          None,
                "male":            None,
                "total_under_18":  f"{unicef_data_source_path}/misc_population/WorldPop_Con_T_U18/{iso3_lower}_T_Under_18_2024_CN_100m_R2024A_v1",
                "female_under_18": f"{unicef_data_source_path}/misc_population/WorldPop_Con_F_U18/{iso3_lower}_F_Under_18_2024_CN_100m_R2024A_v1",
                "male_under_18":   f"{unicef_data_source_path}/misc_population/WorldPop_Con_M_U18/{iso3_lower}_M_Under_18_2024_CN_100m_R2024A_v1",
            }
        self.population_paths_dict = temp_population_paths_dict

    def check_country_no_population(self, country_ucode):
        """
        Checks if a country should be processed as having no population based on its ISO3 code.
        Returns True if the country is in the no population list, False otherwise.
        Parameters:
            country_ucode: unique code of a country
        Returns:
            boolean: True if the country should be processed as having no population, False otherwise
        """
        if country_ucode in self.countries_no_population:
            return True
        return False
    
    def process_hazard_for_country(
            self, 
            hazard, 
            country_ucode,
            hazard_asset,
            tile_scale=4,
            is_2024=False
        ):
        """Process a single hazard for a single country."""
        print(f"Processing country: {country_ucode} {'(2024)' if is_2024 else ''} - Hazard: {hazard_asset}")

        if self.check_country_no_population(country_ucode):
            print(f"Country {country_ucode} is in the no population list. Skipping.")
            pass

        # Get admin2 boundaries
        admin2_boundaries = self.get_admin2_boundaries(country_ucode)

        # Decide processing bounds
        calculate_bounds, bound_ids = self.get_processing_bounds(country_ucode, admin2_boundaries)
        print(bound_ids)

        country_df = None
        for i, (bound, bound_id) in enumerate(zip(calculate_bounds, bound_ids)):
            print(f"Processing region {i+1}/{len(calculate_bounds)}")

            # Set population dictionaries
            self.set_population_dicts(country_ucode, bound, is_2024=is_2024)

            # Get population info
            population_info = self.get_population_classes()
            population_image_collection = population_info['population_stack']
            population_classes_dict = population_info['valid_population_classes']

            # Get exposure
            exposure_image_collection = self.get_population_exposure(
                hazard['hazard_masked_image'], population_classes_dict
            )

            # Set tile scale
            tile_scale = 2 if self.check_process_by_admin2(bound_id) else tile_scale

            # Set tile scale for large adm2
            tile_scale = 16 if self.check_process_large_adm2(bound_id) else tile_scale

            # Get statistics
            hazard_stats_fc = self.get_population_hazard_statistics(
                exposure_image_collection,
                hazard['hazard_raw_image'],
                bound,
                tile_scale=tile_scale,
                population_stack=population_image_collection if is_2024 else None
            )
            stats_df = self.get_statistics_dataframe(hazard_stats_fc)
            stats_df = self.add_ratios_pandas(stats_df)
            stats_df['source'] = hazard_asset.split('/').pop()

            country_df = stats_df if country_df is None else pd.concat([country_df, stats_df])

        return country_df

    def save_country_results(
        self, 
        df, 
        hazard_code, 
        country_ucode,
        output_folder 
    ):
        """Save results to CSV."""
        os.makedirs(f"{output_folder}/hazards/{hazard_code}/partials", exist_ok=True)
        path = f"{output_folder}/hazards/{hazard_code}/partials/{country_ucode}_{hazard_code}_admin2.csv"
        df.to_csv(path, index=False)
        print(f"Saved partial df for country {country_ucode} - {path}")

    def save_global_results(
        self,
        df,
        hazard_code,
        output_folder,
        date=dt.date.today().isoformat()
    ):
        """Save global results to CSV."""
        os.makedirs(f"{output_folder}/global", exist_ok=True)
        path = f"{output_folder}/global/{hazard_code}_{date}.csv"
        df.to_csv(path, index=False)
        print(f"Saved global df - {path}")

    def save_country_results_to_excel(
        self,
        df,
        hazard_code,
        country_ucode,
        output_folder,
        date=dt.date.today().isoformat()
    ):
        
        country_folder_path = f"{output_folder}/results/{country_ucode}/excel"
        # create folder if it does not exist
        os.makedirs(country_folder_path, exist_ok=True)
        # save as excel
        out_xlsx = f"{country_folder_path}/{country_ucode}_{hazard_code}_{date}.xlsx"
        df.to_excel(out_xlsx, index=False)
        print(f"\nExported {hazard_code} results for country {country_ucode}: {out_xlsx}")
    
    def get_processing_bounds(
        self, 
        country_ucode, 
        admin2_boundaries
    ):
        """Return (calculate_bounds, bound_ids) for a country."""
        calculate_bounds = []
        bound_ids = []
        if self.check_process_by_admin1(country_ucode):
            admin1_ucodes = admin2_boundaries.aggregate_array('adm1_ucode').getInfo()
            admin1_ucodes = self.get_unique_elements_from_list(admin1_ucodes)
            for adm1_ucode in admin1_ucodes:
                if self.check_process_by_admin2(adm1_ucode):
                    admin2_for_anomaly = admin2_boundaries.filter(self.ee.Filter.eq("adm1_ucode", adm1_ucode))
                    admin2_ucodes = admin2_for_anomaly.aggregate_array('ucode').getInfo()
                    admin2_ucodes = self.get_unique_elements_from_list(admin2_ucodes)
                    for adm2_ucode in admin2_ucodes:
                        calculate_bounds.append(self.get_admin2_boundaries(adm2_ucode, 'admin2_ucode'))
                        bound_ids.append(adm2_ucode)
                    continue
                calculate_bounds.append(self.get_admin2_boundaries(adm1_ucode, 'admin1_ucode'))
                bound_ids.append(adm1_ucode)
        else:
            calculate_bounds = [admin2_boundaries]
            bound_ids = [country_ucode]
        return calculate_bounds, bound_ids
    
    def build_hazard_exposure_stack(
        self,
        hazard_raw_image,
        exposure_stack
    ):
        """
        Combine raw hazard image and exposure stack into a single multiband image.

        Band order:
        1. hazard_raw
        2. exp_<population_class_1>
        3. exp_<population_class_2>
        ...

        Parameters
        ----------
        hazard_raw_image : ee.Image
            Raw (continuous) hazard image (NOT thresholded).
        exposure_stack : ee.Image
            Multiband exposed population image.

        Returns
        -------
        ee.Image
            Combined multiband image.
        """
        ee = self.ee

        hazard_band = (
            hazard_raw_image
            .rename("hazard_raw")
            .toFloat()
        )

        combined = hazard_band.addBands(exposure_stack)

        return combined
    
    def export_exposure_raster_to_drive(
        self,
        combined_stack,
        country_fc,
        country_ucode,
        hazard_code,
        folder="UNICEF_Exposure_Maps",
        max_pixels=1e13,
        return_task=False
    ):
        """
        Export country-level hazard + exposure multiband raster to Google Drive.

        If return_task=True, returns the started ee.batch.Task so the caller can
        poll it (e.g. sharepoint_sync.wait_for_tasks). Default keeps the original
        behaviour (returns None).
        """
        ee = self.ee

        description = f"{country_ucode}_{hazard_code}_hazard_exposure"

        export_img = (
            combined_stack
            .round()          # applies to exposure bands; hazard is float already
            .toFloat()        # keep hazard continuous
            .set({
                "hazard_code": hazard_code,
                "hazard": self.hazard_name,
                "prod_date": self.prod_date,
                "time_period": self.time_period,
                "population_classes": ",".join(self.valid_population_keys)
            })
        )

        task = ee.batch.Export.image.toDrive(
            image=export_img,
            description=description,
            folder=folder,
            fileNamePrefix=description,
            region=country_fc.geometry(),
            scale=self.analysis_scale,
            maxPixels=max_pixels,
            fileFormat="GeoTIFF",
            formatOptions={"cloudOptimized": True}
        )

        task.start()
        print(f"🚀 Export started: {description}")
        if return_task:
            return task

    def export_singleband_to_drive(
        self,
        image,
        band_name,
        region_fc,
        country_ucode,
        hazard_code,
        folder="UNICEF_Exposure_Maps_View",
        max_pixels=1e13,
        return_task=False
    ):
        ee = self.ee

        description = f"{country_ucode}_{hazard_code}_{band_name}"

        # Recompute scale from image projection as hazards have different native resolutions.
        scale = image.projection().nominalScale().getInfo() if image.projection() else self.analysis_scale

        task = ee.batch.Export.image.toDrive(
            image=image.rename(band_name),
            description=description,
            folder=folder,
            fileNamePrefix=description,
            region=region_fc.geometry(),
            scale=scale,
            maxPixels=max_pixels,
            fileFormat="GeoTIFF",
            fileDimensions=65536,
            formatOptions={"cloudOptimized": True}
        )

        task.start()
        print(f"Export started: {description}")
        if return_task:
            return task

@dataclass
class Hazard:
    name: str
    category: str
    asset: str
    indicator: str
    code: str
    band: str = None
    display_name: Optional[str] = None
    short_code: Optional[str] = None
    # Physical unit of the hazard's own measurement (hazs_mean/std/min/max), e.g.
    # "m", "m/s", "PGA (g)". The normalised g/c/r indices are unitless and are NOT
    # described by this field. Optional so older hazard_info.json files still load.
    unit: Optional[str] = None
    th_min: float = 0.0 
    min: Optional[float] = 0.0
    max: Optional[float] = 1.0
    threshold: str = 0.0
    threshold_operation: str = 'gt'
    apply_nodata: int = 0
    nodata: float = -9999.0
    mosaic: int = 0

    @classmethod
    def from_dict(cls, d: dict, asset_prefix: str = ""):
        d = d.copy()
        if asset_prefix and "asset" in d:
            if 'projects/unicef-ccri' not in d["asset"]:
                d["asset"] = f"{asset_prefix}/hazards/{d['asset']}"

        d["band"] = d.get("band", None)
        if isinstance(d["band"], str):
            d["band"] = d["band"].strip() or None
        # Convert numeric fields from strings, handling empty strings
        def to_float_or_none(val):
            if val == "" or val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        def to_int(val):
            if val == "" or val is None:
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0
        
        d["threshold"] = to_float_or_none(d.get("threshold", 0.0)) or 0.0
        d["th_min"] = to_float_or_none(d.get("th_min", 0.0)) or 0.0
        d["min"] = to_float_or_none(d.get("min"))
        d["max"] = to_float_or_none(d.get("max"))
        d["nodata"] = to_float_or_none(d.get("nodata", -9999.0)) or -9999.0
        d["apply_nodata"] = to_int(d.get("apply_nodata", 0))
        d["mosaic"] = to_int(d.get("mosaic", 0))
        d["display_name"] = d.get("display_name", d.get("name", ""))

        unit = d.get("unit")
        d["unit"] = unit.strip() if isinstance(unit, str) and unit.strip() else None

        return cls(**d)

