import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)

log = logging.getLogger(__name__)

def parse_ACK(message: str):
    """
    Expected:
    *<IP3><IP4>100ACK<CW%><WW>%#

    Example:
    *0012100ACK400500#
    *001012100ACK400500#
    *129100ACK167833#

    *112100ACK167833#

    *29242100ACK400500#
    """
    if "ACK" not in message:
        log.error("ACK not found in recv: %s", message)
        return None
    try:
        ack_stripped = message.split("ACK")[1].rstrip("#")
        cw = round(float(ack_stripped[0:3]), 1) / 10
        ww  = round(float(ack_stripped[3:6]), 1) / 10
        return {
            "cw": cw,
            "ww": ww
        }
    except Exception as e:
        log.warning(f"Failed to parse ACK: {message} | error: {e}")
        return None