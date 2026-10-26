from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable
import json

class ValueMode(str, Enum):
    FIXED="fixed"; OLLAMA="ollama"; MANUAL="manual"; BLANK="blank"; REVIEW="review"
class Severity(str, Enum):
    INFO="info"; WARN="warn"; HOLD="hold"; FATAL="fatal"

@dataclass(frozen=True)
class ChoiceField:
    key:str; label:str; choices:tuple[str,...]; required:bool=False; sensitive:bool=False; section:str=""; max_selections:int=1
@dataclass
class FieldValue:
    key:str; mode:ValueMode=ValueMode.OLLAMA; value:Any=None; source:str=""; confidence:float|None=None; rationale:str=""
@dataclass
class ProductInput:
    product_type:str; product_name:str; app_summary:str; repository:str=""; package_path:str=""; images_dir:str=""; store_product_id:str=""; price_mode:str="manual"; price_value:str=""; market_preset:str=""; fields:dict[str,FieldValue]=field(default_factory=dict)
    def to_dict(self):
        d=asdict(self)
        for v in d.get("fields",{}).values():
            if isinstance(v.get("mode"),ValueMode): v["mode"]=v["mode"].value
        return d
    @classmethod
    def from_dict(cls,d):
        d=dict(d); fs={}
        for k,v in (d.get("fields") or {}).items():
            v=dict(v); v["mode"]=ValueMode(v.get("mode","ollama")); fs[k]=FieldValue(**v)
        d["fields"]=fs; return cls(**d)
    @classmethod
    def load(cls,path): return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    def save(self,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(self.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
@dataclass
class Finding:
    code:str; message:str; severity:Severity; field:str=""
@dataclass
class ProductResult:
    product_name:str; status:str; findings:list[Finding]=field(default_factory=list); actions:list[str]=field(default_factory=list)

APP_CATEGORIES=("Books + reference","Business","Developer tools","Education","Entertainment","Food + dining","Government + politics","Health + fitness","Kids + family","Lifestyle","Medical","Multimedia design","Music","Navigation + maps","News + weather","Personal finance","Personalization","Photo + video","Productivity","Security","Shopping","Social","Sports","Travel","Utilities + tools")
GAME_GENRES=("Action + adventure","Card + board","Casino","Classics","Educational","Family + kids","Fighting","Multi-Player Online Battle Arena","Music","Other","Platformer","Puzzle + trivia","Racing + flying","Role playing","Shooter","Simulation","Sports","Strategy","Tools","Word")
VISIBILITY_CHOICES=("discoverable","direct_link_only")
FREE_TRIAL_CHOICES=("none","1_day","7_days","15_days","30_days","unlimited")
PUBLISH_HOLD_CHOICES=("as_soon_as_certified","manual_publish","specific_date")
COMMON_FIELDS=(
 ChoiceField("product_type","Product type",("app","game"),True),
 ChoiceField("submission_kind","Submission kind",("new","update"),True),
 ChoiceField("pricing_model","Pricing",("free","paid"),True,False,"pricing"),
 ChoiceField("visibility","Visibility",VISIBILITY_CHOICES,True,False,"pricing"),
 ChoiceField("free_trial","Free trial",FREE_TRIAL_CHOICES,False,False,"pricing"),
 ChoiceField("publish_hold","Publishing hold",PUBLISH_HOLD_CHOICES,False,False,"submission_options"),
 ChoiceField("collects_personal_data","Collects personal data",("yes","no"),True,True,"properties"),
 ChoiceField("uses_external_accounts","External account required",("yes","no"),False,True,"properties"),
 ChoiceField("has_in_app_purchases","In-app purchases",("yes","no"),False,True,"properties"),
 ChoiceField("contains_ads","Advertising",("yes","no"),False,True,"properties"),
)
APP_FIELDS=(ChoiceField("primary_category","Primary category",APP_CATEGORIES,True,False,"properties"),ChoiceField("requires_internet","Internet connection",("yes","no"),False,False,"properties"),ChoiceField("background_activity","Background activity",("yes","no"),False,False,"properties"))
GAME_FIELDS=(ChoiceField("game_genres","Game genres",GAME_GENRES,True,False,"properties",3),ChoiceField("online_multiplayer","Online multiplayer",("yes","no"),False,True,"properties"),ChoiceField("user_generated_content","User-generated content",("yes","no"),False,True,"age_ratings"),ChoiceField("violence","Violence",("yes","no"),True,True,"age_ratings"),ChoiceField("gambling","Gambling",("yes","no"),True,True,"age_ratings"),ChoiceField("sexual_content","Sexual content",("yes","no"),True,True,"age_ratings"),ChoiceField("drugs_alcohol_tobacco","Drugs/alcohol/tobacco",("yes","no"),True,True,"age_ratings"),ChoiceField("strong_language","Strong language",("yes","no"),True,True,"age_ratings"))
TEXT_FIELDS={"description":{"required":True,"max_chars":10000},"whats_new":{"required":False,"max_chars":1500},"features":{"required":False},"support_url":{"required":False},"privacy_policy_url":{"required":False},"certification_notes":{"required":False}}
PACKAGE_EXTENSIONS={".msix",".msixupload",".msixbundle",".appx",".appxupload",".appxbundle"}

def fields_for(kind:str):
    if kind=="app": return COMMON_FIELDS+APP_FIELDS
    if kind=="game": return COMMON_FIELDS+GAME_FIELDS
    raise ValueError("product_type must be app or game")

def apply_fixed_rules(p:ProductInput):
    defs={f.key:f for f in fields_for(p.product_type)}; proposed={"product_type":p.product_type}
    if p.price_mode in {"free","paid"}: proposed["pricing_model"]=p.price_mode
    text=(p.app_summary or "").lower()
    if any(x in text for x in ("offline","no internet","オフライン","インターネット不要")): proposed["requires_internet"]="no"
    elif any(x in text for x in ("api","cloud","online","web","クラウド","インターネット")): proposed["requires_internet"]="yes"
    for k,v in proposed.items():
        if k not in defs: continue
        cur=p.fields.get(k)
        if cur and cur.mode in {ValueMode.MANUAL,ValueMode.FIXED,ValueMode.BLANK,ValueMode.REVIEW}: continue
        p.fields[k]=FieldValue(k,ValueMode.FIXED,v,"rule",1.0,"deterministic")

def validate_product(p:ProductInput):
    out=[]
    if p.product_type not in {"app","game"}: out.append(Finding("TYPE","Product type must be app or game",Severity.HOLD,"product_type")); return out
    if not p.product_name.strip(): out.append(Finding("NAME","Product name missing",Severity.HOLD,"product_name"))
    if not p.package_path: out.append(Finding("PACKAGE_MISSING","MSIX/MSIXUPLOAD not selected",Severity.HOLD,"package_path"))
    else:
        q=Path(p.package_path)
        if q.suffix.lower() not in PACKAGE_EXTENSIONS: out.append(Finding("PACKAGE_TYPE",f"Unsupported package extension: {q.suffix}",Severity.HOLD,"package_path"))
        if not q.exists(): out.append(Finding("PACKAGE_NOT_FOUND","Package file does not exist",Severity.HOLD,"package_path"))
    if not p.images_dir: out.append(Finding("IMAGES_MISSING","Screenshot folder not selected",Severity.WARN,"images_dir"))
    else:
        d=Path(p.images_dir)
        if not d.is_dir(): out.append(Finding("IMAGES_NOT_FOUND","Image directory not found",Severity.WARN,"images_dir"))
        elif not any(x.is_file() and x.suffix.lower() in {".png",".jpg",".jpeg"} for x in d.iterdir()): out.append(Finding("SCREENSHOT_REQUIRED","At least one screenshot is required",Severity.HOLD,"images_dir"))
    defs={f.key:f for f in fields_for(p.product_type)}
    for k,d in defs.items():
        fv=p.fields.get(k)
        if not fv:
            if d.required: out.append(Finding("CHOICE_UNRESOLVED",f"Required choice unresolved: {d.label}",Severity.HOLD,k))
            continue
        if fv.mode==ValueMode.REVIEW: out.append(Finding("REVIEW",f"Needs review: {d.label}",Severity.HOLD if d.required else Severity.WARN,k))
        if fv.mode==ValueMode.BLANK and d.required: out.append(Finding("REQUIRED_BLANK",f"Required choice blank: {d.label}",Severity.HOLD,k))
        if fv.value is not None:
            vals=fv.value if isinstance(fv.value,list) else [fv.value]
            if len(vals)>d.max_selections or any(v not in d.choices for v in vals): out.append(Finding("INVALID_CHOICE",f"Invalid value for {d.label}: {fv.value}",Severity.HOLD,k))
    desc=p.fields.get("description")
    if not desc or desc.mode==ValueMode.REVIEW or not str(desc.value or "").strip(): out.append(Finding("DESCRIPTION_REQUIRED","Store description is required",Severity.HOLD,"description"))
    elif len(str(desc.value))>10000: out.append(Finding("DESCRIPTION_TOO_LONG","Description exceeds 10,000 characters",Severity.HOLD,"description"))
    personal=p.fields.get("collects_personal_data"); privacy=p.fields.get("privacy_policy_url")
    if personal and personal.value=="yes" and not str(privacy.value if privacy else "").strip(): out.append(Finding("PRIVACY_POLICY","Privacy policy URL required by declaration",Severity.HOLD,"privacy_policy_url"))
    return out

@dataclass(frozen=True)
class LiveQuestion:
    question_id:str; question_text:str; options:tuple[str,...]; allows_multiple:bool=False; required:bool=True; section:str=""
@dataclass(frozen=True)
class LiveAnswer:
    question_id:str; selected:tuple[str,...]; confidence:float; rationale:str; needs_review:bool

def validate_live_answer(q:LiveQuestion,raw:dict,sensitive=True):
    selected=tuple(raw.get("selected") or ()); confidence=float(raw.get("confidence") or 0); review=bool(raw.get("needs_review"))
    valid=tuple(x for x in selected if x in q.options)
    if valid!=selected or (not q.allows_multiple and len(valid)>1) or (q.required and not valid) or (sensitive and confidence<.90): review=True
    return LiveAnswer(q.question_id,valid,confidence,str(raw.get("rationale") or ""),review)

class GlobalAuthError(RuntimeError): pass
class AmbiguousWriteError(RuntimeError): pass
@dataclass
class QueuePolicy:
    continue_after_product_hold:bool=True; continue_after_product_error:bool=True; stop_on_global_auth_error:bool=True; stop_on_ambiguous_write:bool=False
@dataclass
class QueueReport:
    results:list[ProductResult]=field(default_factory=list); stopped_early:bool=False; stop_reason:str=""
    def to_dict(self):
        return {"stopped_early":self.stopped_early,"stop_reason":self.stop_reason,"results":[{"product_name":r.product_name,"status":r.status,"findings":[{"code":f.code,"message":f.message,"severity":f.severity.value,"field":f.field} for f in r.findings],"actions":r.actions} for r in self.results]}

def run_queue(products:list[ProductInput],uploader:Callable[[ProductInput],list[str]],policy:QueuePolicy|None=None):
    policy=policy or QueuePolicy(); report=QueueReport()
    for p in products:
        findings=validate_product(p)
        if any(f.severity==Severity.HOLD for f in findings):
            report.results.append(ProductResult(p.product_name,"HOLD",findings,[]))
            if not policy.continue_after_product_hold: report.stopped_early=True; report.stop_reason="product_hold"; break
            continue
        try: report.results.append(ProductResult(p.product_name,"DONE",findings,uploader(p)))
        except GlobalAuthError as e:
            report.results.append(ProductResult(p.product_name,"AUTH_ERROR",findings+[Finding("AUTH",str(e),Severity.FATAL)],[]))
            if policy.stop_on_global_auth_error: report.stopped_early=True; report.stop_reason="global_auth_error"; break
        except AmbiguousWriteError as e:
            report.results.append(ProductResult(p.product_name,"UNKNOWN",findings+[Finding("AMBIGUOUS_WRITE",str(e),Severity.HOLD)],[]))
            if policy.stop_on_ambiguous_write: report.stopped_early=True; report.stop_reason="ambiguous_write"; break
        except Exception as e:
            report.results.append(ProductResult(p.product_name,"ERROR",findings+[Finding("UPLOAD_ERROR",str(e),Severity.HOLD)],[]))
            if not policy.continue_after_product_error: report.stopped_early=True; report.stop_reason="product_error"; break
    return report

def render_markdown(report:QueueReport):
    counts={}
    for r in report.results: counts[r.status]=counts.get(r.status,0)+1
    lines=["# Microsoft Store 夜間処理レポート","","| 状態 | 件数 |","|---|---:|"]+[f"| {s} | {counts.get(s,0)} |" for s in ("DONE","HOLD","UNKNOWN","ERROR","AUTH_ERROR")]
    for r in report.results:
        lines += ["",f"## {r.product_name} — {r.status}"]+[f"- **{f.severity.value.upper()} / {f.code}**: {f.message}" for f in r.findings]
    return "\n".join(lines)+"\n"
