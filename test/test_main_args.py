import sys

import pytest

from lurkiti import __version__
from lurkiti.main import parse_arguments


@pytest.mark.parametrize('flag', ['-V', '--version'])
def test_version_option_prints_version(monkeypatch, capsys, flag):
  monkeypatch.setattr(sys, 'argv', ['lurkiti', flag])
  with pytest.raises(SystemExit) as exc:
    parse_arguments()
  assert exc.value.code == 0
  assert capsys.readouterr().out.strip() == f'lurkiti {__version__}'
