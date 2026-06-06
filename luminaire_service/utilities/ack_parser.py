import structlog

log = structlog.get_logger()

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
        log.warning("ack_parse_failed_missing_keyword", raw_message=message)
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
        log.warning("ack_parse_exception", raw_message=message, error=str(e), exc_info=True)
        return None