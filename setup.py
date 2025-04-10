from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="used-cars-analysis",
    version="0.1.0",
    author="Seu Nome",
    author_email="seu.email@exemplo.com",
    description="Sistema de análise e processamento de dados de veículos usados",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seu-usuario/seu-repositorio",
    project_urls={
        "Bug Tracker": "https://github.com/seu-usuario/seu-repositorio/issues",
        "Documentation": "https://github.com/seu-usuario/seu-repositorio#readme",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "run-etl=scripts.run_etl:main",
            "run-api=scripts.run_api:main",
            "run-dashboard=scripts.run_dashboard:main",
        ],
    },
) 