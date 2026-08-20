"""
The 8-category checklist and their definitions, finalized in Phase 0 against
measured clause coverage on CUAD's Distributor Agreement corpus (see
DECISIONS.md, "Checklist Categories"). Category names match the keys used in
data/answer_keys/*.json exactly -- do not rename without updating both.
"""

CHECKLIST = [
    "Governing Law",
    "Non-Compete",
    "Termination For Convenience",
    "Cap On Liability",
    "Uncapped Liability",
    "Anti-Assignment",
    "Exclusivity",
    "License Grant",
]

DEFINITIONS = {
    "Governing Law": (
        "Which state/country's law applies if there's a dispute -- e.g. "
        '"this contract is interpreted under Texas law."'
    ),
    "Non-Compete": (
        "Restricts the distributor from selling competing products (or the "
        "supplier from using a competing distributor) during or after the "
        "contract."
    ),
    "Termination For Convenience": (
        "Either side can end the contract without needing a reason -- just "
        "advance written notice. Does NOT include termination for cause "
        "(breach, insolvency, etc.) -- that's a different clause and should "
        "not be extracted here."
    ),
    "Cap On Liability": (
        "Limits how much one party can be forced to pay the other in "
        "damages -- a dollar cap, or an exclusion of special/incidental/"
        "consequential damages."
    ),
    "Uncapped Liability": (
        "A carve-out from a liability cap -- specific situations (IP "
        "infringement, confidentiality breach, gross negligence, "
        "indemnification) where the cap doesn't apply."
    ),
    "Anti-Assignment": (
        "Restricts either party from transferring/assigning the contract "
        "without the other party's consent."
    ),
    "Exclusivity": (
        "The distributor is granted exclusive rights in a territory/for a "
        "product (or the relationship is explicitly non-exclusive -- only "
        "extract if the contract says \"exclusive,\" not \"non-exclusive\")."
    ),
    "License Grant": (
        "The clause where the supplier grants the distributor the right to "
        "use/sell/market the product (and often the trademark)."
    ),
}
