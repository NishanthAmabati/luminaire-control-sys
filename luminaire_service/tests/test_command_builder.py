from utilities.command_builder import CommandBuilder


class TestCommandBuilder:
    def test_build_cw_ww_normal(self):
        result = CommandBuilder.build_cw_ww(50.0, 30.0)
        assert result == "500300"

    def test_build_cw_ww_zero(self):
        result = CommandBuilder.build_cw_ww(0.0, 0.0)
        assert result == "000000"

    def test_build_cw_ww_max(self):
        result = CommandBuilder.build_cw_ww(99.9, 99.9)
        assert result == "999999"

    def test_build_cw_ww_clamps_above_99_9(self):
        result = CommandBuilder.build_cw_ww(100.0, 100.0)
        assert result == "999999"

    def test_build_cw_ww_clamps_negative(self):
        result = CommandBuilder.build_cw_ww(-1.0, -5.0)
        assert result == "000000"

    def test_build_cw_ww_mixed_clamping(self):
        result = CommandBuilder.build_cw_ww(150.0, 50.0)
        assert result == "999500"

    def test_build_cw_ww_precision(self):
        result = CommandBuilder.build_cw_ww(55.55, 44.44)
        scaled = int(round(55.55 * 10))
        expected_cw = f"{scaled:03}"
        assert result.startswith(expected_cw)
        assert len(result) == 6

    def test_extract_ip34_valid(self):
        result = CommandBuilder.extract_ip34("192.168.1.100")
        assert result == "001100"

    def test_extract_ip34_zero_padded(self):
        result = CommandBuilder.extract_ip34("10.0.0.5")
        assert result == "000005"

    def test_extract_ip34_invalid(self):
        import pytest
        with pytest.raises(ValueError, match="Invalid IP format"):
            CommandBuilder.extract_ip34("not-an-ip")

    def test_build_command(self):
        result = CommandBuilder.build_command("001100", "500300")
        assert result == "*001100500300##"
