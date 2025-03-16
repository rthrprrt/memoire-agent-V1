# setup.py
from setuptools import setup, find_packages

setup(
    name="memoire-assistant",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.103.1",
        "uvicorn>=0.23.2",
        "httpx>=0.25.0",
        "pydantic>=2.3.0",
        "python-multipart>=0.0.6",
        "sqlalchemy>=2.0.20",
        "websockets>=11.0.3",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "aiofiles>=23.2.1",
        "tenacity>=8.2.3",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.1.0",
        "httpx>=0.25.0"
    ],
    extras_require={
        "dev": [
            "black",
            "isort",
            "mypy",
            "flake8"
        ],
        "test": [
            "pytest",
            "pytest-asyncio",
            "pytest-cov"
        ],
        "docs": [
            "sphinx",
            "sphinx-rtd-theme"
        ]
    },
    python_requires=">=3.9",
)