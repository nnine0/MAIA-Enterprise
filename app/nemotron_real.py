"""
MAIA Nemotron 3 Content Safety - Real Integration
============================================
Uses nvidia/Nemotron-3-Content-Safety (Gemma-3-4B-it based)

Features:
- 22 Safety Categories
- Multimodal (text + image)
- 12 languages
- vLLM or Transformers runtime

Categories (22):
- Violence, Sexual, Criminal Planning, Guns, Controlled Substances
- Suicide, Hate/Identity, PII/Privacy, Harassment, Threat
- Profanity, Needs Caution, Manipulation, Fraud/Deception
- Malware, High Risk Gov Decision, Political/Misinformation
- Copyright/Trademark, Unauthorized Advice, Illegal Activity, Immoral/Unethical

Run: python3 -m app.nemotron_real
"""
