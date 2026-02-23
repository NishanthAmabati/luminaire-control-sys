class LightChanneler:
    def __init__(self, cct_min, cct_max, lux_min, lux_max):
        """
        :param cct_min: The Kelvin temperature when Cold White is 0%
        :param cct_max: The Kelvin temperature when Cold White is 100%
        """
        self.cct_min = cct_min
        self.cct_max = cct_max
        self.lux_min = lux_min
        self.lux_max = lux_max

    def resolve_channels(self, cct: float, lux: float):
        """
        Calculates CW and WW values.
        Logic: 
        1. Determine the color ratio based on CCT.
        2. Scale that ratio by the Lux (total intensity).
        3. Ensure WW is the inverse of CW relative to Lux.
        """
        if lux is None or cct is None:
            return
        # 1. Clamp inputs to safe boundaries
        safe_lux = max(0.0, min(lux, 100.0))
        #safe_lux = max(self.lux_min, min(lux, self.lux_max))
        safe_cct = max(self.cct_min, min(cct, self.cct_max))
        
        # 2. Calculate Cold White Ratio (0.0 to 1.0)
        # If cct is cct_min, ratio is 0. If cct is cct_max, ratio is 1.
        range_width = self.cct_max - self.cct_min
        cw_ratio = (safe_cct - self.cct_min) / range_width if range_width > 0 else 0.5
        ww_ratio = 1.0 - cw_ratio

        # 3. Calculate CW and WW based on Lux
        # If lux is 100 and cw_ratio is 0.7, cw is 70.
        cw = cw_ratio * safe_lux
        
        # Logic: ww should be the remainder of the total intensity
        ww = ww_ratio * safe_lux

        # 4. Final clamp and return
        return {
            "cw": max(0.0, min(cw, 100.0)),
            "ww": max(0.0, min(ww, 100.0))
        }
