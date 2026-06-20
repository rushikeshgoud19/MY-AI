from setuptools import setup, find_packages

setup(
    name="mizune-os",
    version="8.0.0",
    description="Mizune Agentic Operating System",
    author="Rushi",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "pyautogui>=0.9.54",
        "pyperclip>=1.8.2",
        "psutil>=5.9.0",
        "websockets>=12.0",
        "pytesseract>=0.3.10",
        "pure-python-adb>=0.3.0"
    ],
    extras_require={
        "windows": ["pywin32>=306"],
        "voice": ["openai-whisper>=20231117"],
        "vision": ["opencv-python>=4.8.0", "ultralytics>=8.0.0"],
    },
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "mizune=main:main",
        ],
    },
)
