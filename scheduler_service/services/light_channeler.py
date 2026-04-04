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
            if lux is None or cct is None:
                return
            
            # 1. Clamp inputs
            safe_lux = max(self.lux_min, min(lux, self.lux_max))
            safe_cct = max(self.cct_min, min(cct, self.cct_max))
            
            # 2. Calculate the base CW percentage (0 to 100)
            # This represents the "color mix" regardless of brightness
            range_width = self.cct_max - self.cct_min
            cw_percentage = (safe_cct - self.cct_min) / (range_width / 100)
            
            # 3. Calculate the intensity factor (0.0 to 1.0)
            # If lux is 250 and max is 500, intensity_factor is 0.5
            intensity_factor = safe_lux / self.lux_max
            
            # 4. Scale both channels
            # Total light (CW + WW) should equal (intensity_factor * 100)
            total_available_intensity = intensity_factor * 100
            
            cw = cw_percentage * intensity_factor
            ww = total_available_intensity - cw

            return {
                "cw": round(max(0.0, min(cw, 100.0)), 2),
                "ww": round(max(0.0, min(ww, 100.0)), 2)
            }

    def resolve_cct(self, cw: int, ww: int) -> int:
        """
        caclulates cct from passed in cw, ww

        range: since cw, ww are passed in as int the possible range of values
        for cw, ww would be between 0, 99(cause we are capping at 99) the possible range of cct
        would be between 3530 (cw: 1, ww: 99) and 6470 (cw: 99, ww: 1).
        """
        if cw is None or ww is None:
            return
        safe_cw = max(0, min(cw, 99))
        safe_ww = max(0, min(ww, 99))
        
        try:
            sum = safe_cw + safe_ww
            ratio = safe_cw / sum
            cct_range = self.cct_max - self.cct_min

            cct = self.cct_min + ratio * cct_range
            return {
                "cct": int(cct)
            }
        except ZeroDivisionError:
            return {"cct": "NA"}
    
# lh = LightChanneler(
#     cct_min=3500,
#     cct_max=6500,
#     lux_min=0,
#     lux_max=500
# )
# while True:
#     cw_test = int(input("enter cw: "))
#     ww_test = int(input("enter ww: "))
#     cct_test = lh.resolve_cct(cw_test, ww_test)
#     print(cct_test)
#     # cct_test = int(input("enter cct: "))
#     # lux_test = int(input("enter lux: "))
#     # test = lh.resolve_channels(cct_test, lux_test)
#     # print(test)
#     print("\n")