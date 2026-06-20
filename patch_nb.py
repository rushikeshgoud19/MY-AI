import json
nb = json.load(open('fixed_openwakeword.ipynb'))
patch_cell = {
    'cell_type': 'code',
    'execution_count': None,
    'metadata': {},
    'outputs': [],
    'source': [
        "# PATCH FOR COLAB PYTHON 3.12 CRASH\n",
        "import pkgutil\n",
        "class DummyImporter:\n",
        "    def find_module(self, fullname, path=None):\n",
        "        return None\n",
        "pkgutil.ImpImporter = DummyImporter\n",
        "import pkg_resources\n"
    ]
}
nb['cells'].insert(0, patch_cell)
json.dump(nb, open('fixed_openwakeword.ipynb', 'w'), indent=2)
