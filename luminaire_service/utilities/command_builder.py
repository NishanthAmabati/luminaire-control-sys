# *{ip3}{ip4}{int(cw*10):03}{int(ww*10):03}##
# *<ip3><ip4><cw><ww>##

import ipaddress
import structlog

log = structlog.get_logger()

class CommandBuilder:

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(value, max_value))

    @staticmethod
    def build_cw_ww(cw: float, ww: float) -> str:
        cw = CommandBuilder._clamp(cw, 0.0, 99.9)
        ww = CommandBuilder._clamp(ww, 0.0, 99.9)

        cw_scaled = int(round(cw * 10))
        ww_scaled = int(round(ww * 10))

        return f"{cw_scaled:03}{ww_scaled:03}"

    @staticmethod
    def extract_ip34(ip: str) -> str:
        try:
            addr = ipaddress.IPv4Address(ip)
            parts = str(addr).split(".")
            return f"{int(parts[2]):03}{int(parts[3]):03}"
        except ipaddress.AddressValueError as e:
            log.error("command_build_failed_invalid_ip", ip=ip, error=str(e), exc_info=True)
            raise ValueError(f"Invalid IP format provided: {ip}") from e
        except Exception as e:
            log.error("command_build_unexpected_error", ip=ip, error=str(e), exc_info=True)
            raise

    @staticmethod
    def build_command(ip34: str, cw_ww: str) -> str:
        return f"*{ip34}{cw_ww}##"
