from setuptools import find_packages, setup

setup(
    name="juno",
    version="0.5.0",
    packages=find_packages(),
    python_requires=">= 3.9",
    install_requires=[
        "aiohttp",
        "aiolimiter",
        "colorlog",
        "mergedeep",
        "more-itertools",
        "multidict",
        "numpy",
        "pandas",
        "python-dateutil",
        "pytweening",
        "simplejson",
        "tenacity",
        "types-python-dateutil",
        "types-setuptools",
        "types-simplejson",
        "typing-inspect",
    ],
    extras_require={
        "api": [
            "aiohttp",
            "aiohttp_cors",
        ],
        "dev": [
            "black",
            "flake8",
            "flake8-broken-line",
            "flake8-bugbear",
            "flake8-comprehensions",
            "flake8-isort",
            "flake8-quotes",
            "isort",
            "mypy",
            "pytest",
            "pytest-aiohttp",
            "pytest-lazy-fixture",
            "pytest-mock",
            "pyyaml",
            "rope",
            "types-pyyaml",
        ],
        "discord": [
            "discord.py",
        ],
        "plotly": [
            "plotly",
        ],
        "slack": [
            "slack_sdk",
        ],
    },
)
