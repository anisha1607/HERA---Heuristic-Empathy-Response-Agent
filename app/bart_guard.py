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

# We run zero-shot classification with natural-language descriptions (works better than single keywords)
DESCRIPTIONS: Dict[str, str] = {
    LABEL_IN: "parenting communication advice, empathy coaching, or how to talk to a child in a supportive way",
    LABEL_SPY: "getting instructions to spy on, hack, track, or monitor a phone secretly",
    LABEL_LEGAL: "legal advice such as custody, suing, court, or legal procedures",
    LABEL_MED: "medical diagnosis, prescribing treatment, medication advice, or symptom evaluation",
    LABEL_ADV: "harmful, harassing, hateful content, or jokes targeting vulnerable teens",
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
            multi_label=False,
        )

        desc_to_label = {v: k for k, v in DESCRIPTIONS.items()}
        scores = {desc_to_label[lbl]: float(score) for lbl, score in zip(out["labels"], out["scores"])}

        best_desc = out["labels"][0]
        best_score = float(out["scores"][0])
        best_label = desc_to_label[best_desc]
        return GuardResult(label=best_label, confidence=best_score, scores=scores)

    def should_refuse(self, text: str) -> Tuple[bool, GuardResult]:
        res = self.classify(text)
        if res.label != LABEL_IN and res.confidence >= self.threshold:
            return True, res
        return False, res