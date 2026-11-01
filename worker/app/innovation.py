from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any

def _terms(design: dict[str, Any], notes: str) -> set[str]:
    raw=json.dumps(design,ensure_ascii=False).lower()+" "+notes.lower()
    return set(re.findall(r"[a-z]{3,}",raw))

def _need(terms:set[str], words:set[str])->bool:return bool(terms & words)

def build_innovation_dossier(root:Path, design:dict[str,Any], selections:dict[str,str], notes:str)->list[dict[str,Any]]:
    """Create engineering candidates and comparison rules. Candidates are explicitly non-release concepts."""
    terms=_terms(design,notes)
    modules=design.get("modules",[])
    interface=selections.get("foundry_interface","adaptive_foundry")
    posture=selections.get("innovation","purposeful_innovation")
    needs_power=_need(terms,{"battery","solar","portable","remote","charging"})
    needs_outdoor=_need(terms,{"outdoor","farm","agriculture","dust","rain","water","rugged"})
    needs_data=_need(terms,{"data","wireless","cellular","wifi","bluetooth","sensor","gps"})
    family="HF-Link Rugged" if needs_outdoor else ("HF-Link Core" if needs_power or needs_data else "HF-Link Mini")
    candidates=[
      {"approach":"conventional","summary":"Established component and enclosure architecture with standard interfaces.","strength":"Lowest validation uncertainty","risk":"May miss product-specific cost, sealing or integration improvements."},
      {"approach":"optimised","summary":"Simplify part count and combine functions using proven manufacturing processes.","strength":"Strong cost/durability balance","risk":"Requires comparative DFM and reliability analysis."},
      {"approach":"foundry_innovation","summary":"Adapt a compatible interface-family member and explore multifunction physical geometry.","strength":"Distinctive ecosystem and potential integration gains","risk":"Connector mating, electrical envelope, tooling and environmental performance require dedicated validation."},
    ]
    interface_spec={
      "family":family,"strategy":interface,
      "shared_dna":{"keying":"family-controlled orientation; exact geometry must be tolerance-designed","compatibility":"pin role, voltage/current envelope and signalling must be checked before mating","cable":"overmould and strain relief selected for duty cycle; wire gauge and shielding remain calculated requirements","safety":"no pin assignment is released without protection and misuse analysis"},
      "variant_generation_inputs":["required circuits and pin roles","maximum voltage/current","data signalling class","mating cycles","ingress/environment target","available enclosure volume","cable bend/strain requirements"],
      "release_status":"CONCEPT_ONLY_PENDING_CONNECTOR_ENGINEERING",
    }
    report={"status":"CANDIDATES_GENERATED_NOT_VALIDATED","innovation_posture":posture,"modules_considered":len(modules),"candidates":candidates,"interface_family":interface_spec,
      "decision_rule":"A novel candidate may replace the baseline only when measurable evidence supports cost, durability, manufacturability, repairability or user-value improvement.",
      "required_validation":["electrical calculations and protection analysis","component and material data confirmation","tolerance stack and mating analysis","prototype fit/function testing","environmental and cycle testing appropriate to intended use","applicable EMC/safety/regulatory assessment"]}
    out=root/"02_System_Architecture";out.mkdir(parents=True,exist_ok=True)
    (out/"generative_innovation_dossier.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    (out/"foundry_interface_family.json").write_text(json.dumps(interface_spec,indent=2),encoding="utf-8")
    return [{"passed":True,"status":"CANDIDATES_GENERATED","files":["02_System_Architecture/generative_innovation_dossier.json","02_System_Architecture/foundry_interface_family.json"],"note":"Generative candidates and a reusable interface-family contract were produced. They are concepts pending detailed engineering and validation."}]
