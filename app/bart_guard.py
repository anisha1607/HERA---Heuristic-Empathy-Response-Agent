from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Tuple

from transformers import pipeline

REFUSAL = (
    "I am an empathy coach, not a medical, legal or technical advisor. "
    "I can only help you refine the tone of your conversation."
)

# Internal labels
LABEL_IN = "IN_DOMAIN_COACHING"
LABEL_SPY = "OUT_OF_SCOPE_SPYING_OR_HACKING"
LABEL_LEGAL = "OUT_OF_SCOPE_LEGAL_ADVICE"
LABEL_MED = "OUT_OF_SCOPE_MEDICAL_DIAGNOSIS"
LABEL_ADV = "OUT_OF_SCOPE_ADVERSARIAL_OR_HARMFUL"
LABEL_OUT = "OUT_OF_SCOPE_GENERAL_KNOWLEDGE"

# We run zero-shot classification with natural-language descriptions
DESCRIPTIONS: Dict[str, str] = {
    LABEL_IN: "a parent seeking help with empathetic communication, de-escalating conflict, or using Non-Violent Communication (NVC) with their child",
    LABEL_SPY: "requests to read private text messages, hack social media, track location secretly, or bypass a child's digital privacy or phone security",
    LABEL_LEGAL: "legal questions about divorce, custody battles, court procedures, lawyers, or suing people",
    LABEL_MED: "medical questions about medication dosages, diagnosing mental health conditions, or treating physical illness symptoms",
    LABEL_ADV: "harmful behavior, bullying, emotional manipulation, hate speech, malicious intent, or encouraging unsafe actions",
    LABEL_OUT: "general knowledge, recipes, baking, computer programming, history, math, or anything unrelated to parenting and communication",
}

HYPOTHESIS_TEMPLATE = "This message is about {}."

@dataclass
class GuardResult:
    label: str
    confidence: float
    scores: Dict[str, float]

class BartGuard:
    def __init__(self, model_name: str | None = None, threshold: float | None = None):
        self.model_name = model_name or os.getenv("BART_MODEL", "facebook/bart-large-mnli")
        self.threshold = float(threshold if threshold is not None else os.getenv("GUARD_THRESHOLD", "0.60"))
        # CPU by default; set device=0 if you have GPU
        self.classifier = pipeline(
            "zero-shot-classification",
            model=self.model_name,
            device=-1,
        )

    def classify(self, text: str) -> GuardResult:
        candidates = list(DESCRIPTIONS.values())
        out = self.classifier(
            sequences=text,
            candidate_labels=candidates,
            hypothesis_template=HYPOTHESIS_TEMPLATE,
            multi_label=True, # Allow labels to be evaluated independently
        )

        desc_to_label = {v: k for k, v in DESCRIPTIONS.items()}
        scores = {desc_to_label[lbl]: float(score) for lbl, score in zip(out["labels"], out["scores"])}

        # For multi-label, we return the highest scoring non-IN label as the representative refusal label
        # but we also keep the full score map.
        sorted_labels = out["labels"]
        sorted_scores = out["scores"]
        
        best_desc = sorted_labels[0]
        best_score = float(sorted_scores[0])
        best_label = desc_to_label[best_desc]
        
        return GuardResult(label=best_label, confidence=best_score, scores=scores)

    def should_refuse(self, text: str) -> Tuple[bool, GuardResult]:
        res = self.classify(text)
        
        # In multi-label mode, we check EVERY category.
        # If any out-of-scope category exceeds the threshold, we refuse.
        for label, score in res.scores.items():
            if label != LABEL_IN and score >= self.threshold:
                # Update the result to reflect the specific violation found
                res.label = label
                res.confidence = score
                return True, res
            
        return False, res
