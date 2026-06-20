import json

nb = json.load(open('fixed_openwakeword.ipynb'))

# Replace the first cell's source with the ultimate patch
nb['cells'][0]['source'] = [
    "# ULTIMATE PATCH FOR COLAB PYTHON 3.12 & PYTORCH 2.1+ CRASHES\n",
    "import pkgutil\n",
    "class DummyImporter:\n",
    "    def find_module(self, fullname, path=None):\n",
    "        return None\n",
    "pkgutil.ImpImporter = DummyImporter\n",
    "import pkg_resources\n",
    "\n",
    "import torchaudio\n",
    "torchaudio.get_audio_backend = lambda: 'soundfile'\n",
    "torchaudio.set_audio_backend = lambda x: None\n",
    "\n",
    "!pip install onnx\n"
]

json.dump(nb, open('fixed_openwakeword.ipynb', 'w'), indent=2)
