"""
HIVE215 Skills Package

Custom skills for the Fast Brain LLM. Each skill defines a persona,
system prompt, and knowledge base for specific use cases.

Available Skills:
- tara_sales: Tara's Sales Assistant for TheDashTool demos
"""

from .tara_sales import TARA_SALES_SKILL, SKILL_ID as TARA_SKILL_ID, create_tara_skill

__all__ = [
    "TARA_SALES_SKILL",
    "TARA_SKILL_ID",
    "create_tara_skill",
]
