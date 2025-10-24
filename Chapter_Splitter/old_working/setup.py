from setuptools import setup

APP = ['ui_tk.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['pypdf'],
    'iconfile': 'youricon.icns',  # Optional, remove this line if no icon
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)