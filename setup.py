from pathlib import Path

from setuptools import find_packages, setup


BASE_DIR = Path(__file__).parent
README = (BASE_DIR / "README.md").read_text(encoding="utf-8") if (BASE_DIR / "README.md").exists() else ""


setup(
    name="asciinode",
    version="0.1.0",
    description="ASCII diagram generation utilities and LLM helpers",
    long_description=README,
    long_description_content_type="text/markdown" if README else "text/plain",
    author="",
    packages=find_packages(exclude=("tests", "examples")),
    python_requires=">=3.11",
    install_requires=[
        "rich>=13.0.0",
        "requests>=2.31.0",
        "wcwidth>=0.2.6",
    ],
    include_package_data=True,
)
