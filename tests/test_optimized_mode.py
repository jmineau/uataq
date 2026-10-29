"""
Argument checks still raise under ``python -O``.

``python -O`` strips ``assert`` statements, so a check written as one is skipped
and a bad argument is dropped without a word. Each case runs in a fresh
interpreter started with ``-O``.
"""

import subprocess
import sys

import pytest

CASES = {
    "TimeRange with both a range and a start": (
        "from uataq.timerange import TimeRange\n"
        "TimeRange('2024', start='2023-01-01')\n",
        "Cannot specify both",
    ),
    "Instrument.read_data with an unknown level": (
        "import uataq\n"
        "inst = uataq.get_site('WBB').instruments['teledyne_t400']\n"
        "inst.read_data('lin', 'gold', '2025-06')\n",
        "Invalid data level",
    ),
    "LGR_UGGA_File.get_files with a level other than raw": (
        "from uataq.filesystem.groupspaces import lin\n"
        "lin.LGR_UGGA_File.get_files('WBB', 'lgr_ugga', 'qaqc')\n",
        "Only raw data",
    ),
}


@pytest.mark.parametrize("code, message", CASES.values(), ids=CASES.keys())
def test_check_raises_value_error_under_optimized_mode(code, message):
    program = (
        "import sys\n"
        "if __debug__:\n"
        "    sys.exit('not running under -O')\n"
        "try:\n"
        + "".join(f"    {line}\n" for line in code.splitlines())
        + "except ValueError as error:\n"
        "    print('ValueError:', error)\n"
        "else:\n"
        "    sys.exit('nothing was raised')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", program],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert "ValueError:" in result.stdout
    assert message in result.stdout
