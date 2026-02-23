# *{ip3}{ip4}{int(cw*10):03}{int(ww*10):03}##
# *<ip3><ip4><cw><ww>##

import ipaddress

class CommandBuilder:

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(value, max_value))

    @staticmethod
    def build_cw_ww(cw: float, ww: float) -> str:
        #cw = CommandBuilder._clamp(cw, 0, 100)
        #ww = CommandBuilder._clamp(ww, 0, 100)

        cw_scaled = int(round(cw * 10))
        ww_scaled = int(round(ww * 10))

        return f"{cw_scaled:03}{ww_scaled:03}"

    @staticmethod
    def extract_ip34(ip: str) -> str:
        addr = ipaddress.IPv4Address(ip)
        parts = str(addr).split(".")
        return f"{int(parts[2]):03}{int(parts[3]):03}"

    @staticmethod
    def build_command(ip34: str, cw_ww: str) -> str:
        return f"*{ip34}{cw_ww}##"
