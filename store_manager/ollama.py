from __future__ import annotations
import json, urllib.request
from .core import ProductInput, FieldValue, ValueMode, fields_for, TEXT_FIELDS, LiveQuestion
from .submission_routes import default_route_for_product_type, route_template

def _post(url,model,prompt,timeout=90):
    data=json.dumps({"model":model,"prompt":prompt,"stream":False,"format":"json"}).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r: raw=json.loads(r.read().decode())
    return json.loads(raw.get("response","{}"))

def prepare_prompt(p:ProductInput,repo_context:str):
    template=route_template(p.submission_route or default_route_for_product_type(p.product_type),p.product_type)
    allowed=set(template.ai_fillable_fields)
    choices={f.key:list(f.choices) for f in fields_for(p.product_type)}
    text=[key for key in TEXT_FIELDS if key in allowed]
    return f'''Prepare a Microsoft Store draft for the immutable upstream route shown below. Return JSON only. Never infer, replace, or recommend a different route. Do not invent legal/compliance declarations. Use only the exact listed choice values. If evidence is weak for sensitive fields, return null.\nSubmission route (read-only): {template.route_id} [{template.partner_center_label}]\nProduct type: {p.product_type}\nProduct name: {p.product_name}\nSummary:\n{p.app_summary}\nRepository context:\n{repo_context[:18000]}\nAllowed choice fields: {json.dumps(choices,ensure_ascii=False)}\nAllowed text fields: {json.dumps(text,ensure_ascii=False)}\nReturn {{"choices":{{}},"text":{{}}}}.'''

def apply_answer(p:ProductInput,answer:dict,min_confidence=.70):
    template=route_template(p.submission_route or default_route_for_product_type(p.product_type),p.product_type)
    allowed=set(template.ai_fillable_fields)
    defs={f.key:f for f in fields_for(p.product_type)}
    for k,info in (answer.get("choices") or {}).items():
        if k not in defs: continue
        cur=p.fields.get(k)
        if cur and cur.mode in {ValueMode.MANUAL,ValueMode.FIXED,ValueMode.BLANK,ValueMode.REVIEW}: continue
        d=defs[k]; val=info.get("value"); conf=float(info.get("confidence") or 0)
        vals=val if isinstance(val,list) else ([val] if val is not None else [])
        if len(vals)>d.max_selections or any(x not in d.choices for x in vals): p.fields[k]=FieldValue(k,ValueMode.REVIEW,None,"ollama",conf,"invalid option"); continue
        if d.max_selections==1: val=vals[0] if vals else None
        mode=ValueMode.REVIEW if d.sensitive and conf<.90 else (ValueMode.OLLAMA if val is not None and conf>=min_confidence else ValueMode.REVIEW)
        p.fields[k]=FieldValue(k,mode,val,"ollama",conf,str(info.get("rationale") or ""))
    for k,info in (answer.get("text") or {}).items():
        if k not in TEXT_FIELDS or k not in allowed: continue
        cur=p.fields.get(k)
        if cur and cur.mode in {ValueMode.MANUAL,ValueMode.FIXED,ValueMode.BLANK,ValueMode.REVIEW}: continue
        val=info.get("value"); conf=float(info.get("confidence") or 0)
        p.fields[k]=FieldValue(k,ValueMode.OLLAMA if val and conf>=min_confidence else ValueMode.REVIEW,val,"ollama",conf,str(info.get("rationale") or ""))

def complete_product(p,repo_context="",url="http://127.0.0.1:11434/api/generate",model="qwen3:8b"):
    ans=_post(url,model,prepare_prompt(p,repo_context)); apply_answer(p,ans); return ans

def answer_live_question(q:LiveQuestion,product_context:str,url="http://127.0.0.1:11434/api/generate",model="qwen3:8b"):
    prompt=f'''Answer one currently visible Microsoft Partner Center question. Choose ONLY from the exact options. If evidence is insufficient, selected must be [] and needs_review=true.\nEvidence:\n{product_context[:18000]}\nQuestion: {q.question_text}\nOptions: {json.dumps(q.options,ensure_ascii=False)}\nMultiple: {q.allows_multiple}\nRequired: {q.required}\nReturn JSON only: {{"selected":[],"confidence":0.0,"rationale":"","needs_review":true}}'''
    return _post(url,model,prompt)
