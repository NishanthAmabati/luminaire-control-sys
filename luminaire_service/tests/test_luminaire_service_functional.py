"""Functional tests for luminaire_service — command building, ACK parsing, luminaire lifecycle."""

import pytest
from utilities.command_builder import CommandBuilder
from utilities.ack_parser import parse_ACK


# ═══════════════════════════════════════════════════════════════════════════════
# CommandBuilder
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommandBuilder:
    def test_build_cw_ww_typical(self):
        assert CommandBuilder.build_cw_ww(50.0, 30.0) == "500300"

    def test_build_cw_ww_zero(self):
        assert CommandBuilder.build_cw_ww(0.0, 0.0) == "000000"

    def test_build_cw_ww_max(self):
        assert CommandBuilder.build_cw_ww(99.9, 99.9) == "999999"

    def test_build_cw_ww_clamps_above_max(self):
        assert CommandBuilder.build_cw_ww(150.0, 200.0) == "999999"

    def test_build_cw_ww_clamps_negative(self):
        assert CommandBuilder.build_cw_ww(-10.0, -20.0) == "000000"

    def test_build_cw_ww_mixed(self):
        assert CommandBuilder.build_cw_ww(100.0, 50.0) == "999500"

    def test_build_cw_ww_precision(self):
        result = CommandBuilder.build_cw_ww(55.55, 44.44)
        assert len(result) == 6
        assert result.isdigit()

    def test_extract_ip34_valid(self):
        assert CommandBuilder.extract_ip34("192.168.1.100") == "001100"
        assert CommandBuilder.extract_ip34("10.0.0.5") == "000005"

    def test_extract_ip34_invalid(self):
        with pytest.raises(ValueError):
            CommandBuilder.extract_ip34("not-an-ip")

    def test_build_command_format(self):
        cmd = CommandBuilder.build_command("001100", "500300")
        assert cmd == "*001100500300##"
        assert cmd.startswith("*")
        assert cmd.endswith("##")
        assert len(cmd) == 15

    def test_build_command_from_cw_ww(self):
        ip34 = CommandBuilder.extract_ip34("192.168.1.100")
        cw_ww = CommandBuilder.build_cw_ww(50.0, 30.0)
        cmd = CommandBuilder.build_command(ip34, cw_ww)
        assert cmd == "*001100500300##"
        assert cmd.startswith("*")
        assert cmd.endswith("##")
        assert len(cmd) == 15


# ═══════════════════════════════════════════════════════════════════════════════
# ACK Parser
# ═══════════════════════════════════════════════════════════════════════════════

class TestAckParser:
    def test_parse_valid_ack(self):
        result = parse_ACK("*0012100ACK400500#")
        assert result is not None
        assert result["cw"] == 40.0
        assert result["ww"] == 50.0

    def test_parse_ack_with_ip34_prefix(self):
        result = parse_ACK("*29242100ACK167833#")
        assert result["cw"] == 16.7
        assert result["ww"] == 83.3

    def test_parse_ack_three_digit_values(self):
        result = parse_ACK("*129100ACK167833#")
        assert result["cw"] == 16.7
        assert result["ww"] == 83.3

    def test_parse_missing_ack_keyword(self):
        result = parse_ACK("no-ack-here")
        assert result is None

    def test_parse_garbage(self):
        result = parse_ACK("*!!!!!ACKxxxxxx#")
        assert result is None

    def test_parse_empty(self):
        result = parse_ACK("")
        assert result is None
