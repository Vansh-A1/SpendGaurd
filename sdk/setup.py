from setuptools import setup, find_packages

setup(
    name="spendguard",
    version="0.1.0",
    description="SpendGuard: AI Agent Corporate Spend Governance and Four-Pillar Trust Gate SDK",
    author="SpendGuard AI",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pydantic>=2.0.0",
    ],
)
