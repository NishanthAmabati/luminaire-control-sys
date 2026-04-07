import logging
import traceback

logger = logging.getLogger(__name__)

class LightChanneler:
    def __init__(self, cct_min, cct_max, lux_min, lux_max):
        self.cct_min = cct_min
        self.cct_max = cct_max
        self.lux_min = lux_min
        self.lux_max = lux_max
        logger.info(f"lightchanneler initialized with cct range {cct_min}-{cct_max} and lux range {lux_min}-{lux_max}")

    def resolve_channels(self, cct: float, lux: float):
        try:
            if lux is None or cct is None:
                logger.warning(f"received none values for cct {cct} or lux {lux}")
                return
            
            logger.debug(f"resolving channels for input cct {cct} and lux {lux}")
            
            # 1. Clamp inputs
            safe_lux = max(self.lux_min, min(lux, self.lux_max))
            safe_cct = max(self.cct_min, min(cct, self.cct_max))
            
            if safe_lux != lux or safe_cct != cct:
                logger.debug("clamping applied to input values")
            
            # 2. Calculate the base CW percentage (0 to 100)
            range_width = self.cct_max - self.cct_min
            if range_width == 0:
                logger.error("cct range width is zero cannot divide")
                return {"cw": 0.0, "ww": 0.0}
                
            cw_percentage = (safe_cct - self.cct_min) / (range_width / 100)
            
            # 3. Calculate the intensity factor (0.0 to 1.0)
            intensity_factor = safe_lux / self.lux_max if self.lux_max != 0 else 0
            
            # 4. Scale both channels
            total_available_intensity = intensity_factor * 100
            
            cw = cw_percentage * intensity_factor
            ww = total_available_intensity - cw

            result = {
                "cw": round(max(0.0, min(cw, 100.0)), 2),
                "ww": round(max(0.0, min(ww, 100.0)), 2)
            }
            logger.info(f"channels resolved to cw {result['cw']} and ww {result['ww']}")
            return result

        except Exception as e:
            logger.error(f"failed to resolve channels because {str(e).lower()}")
            logger.debug(traceback.format_exc().lower())
            return {"cw": 0.0, "ww": 0.0}

    def resolve_cct(self, cw: int, ww: int) -> int:
        try:
            if cw is None or ww is None:
                logger.warning(f"cannot resolve cct because cw {cw} or ww {ww} is none")
                return
            
            logger.debug(f"resolving cct from cw {cw} and ww {ww}")
            
            safe_cw = max(0, min(cw, 99))
            safe_ww = max(0, min(ww, 99))
            
            total_sum = safe_cw + safe_ww
            if total_sum == 0:
                logger.warning("sum of channels is zero returning na")
                return {"cct": "NA"}

            ratio = safe_cw / total_sum
            cct_range = self.cct_max - self.cct_min

            cct = self.cct_min + ratio * cct_range
            result = {"cct": int(cct)}
            logger.info(f"resolved cct to {result['cct']}")
            return result
            
        except Exception as e:
            logger.error(f"error during cct resolution {str(e).lower()}")
            logger.debug(traceback.format_exc().lower())
            return {"cct": "NA"}
    
# lh = LightChanneler(
#     cct_min=3500,
#     cct_max=6500,
#     lux_min=0,
#     lux_max=500
# )
# while True:
#     # cw_test = int(input("enter cw: "))
#     # ww_test = int(input("enter ww: "))
#     # cct_test = lh.resolve_cct(cw_test, ww_test)
#     # print(cct_test)
#     cct_test = int(input("enter cct: "))
#     lux_test = int(input("enter lux: "))
#     test = lh.resolve_channels(cct_test, lux_test)
#     print(test)
#     print("\n")