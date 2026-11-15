from __future__ import annotations
import argparse,json
from pathlib import Path
from .core import ProductInput,apply_fixed_rules,validate_product,run_queue,QueuePolicy,render_markdown
from .partner_center import dryrun_uploader
from .live_draft import LiveDraftWorkflow,LivePlaywrightConnection
from .github_context import fetch_context
from .ollama import complete_product

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
    p=sp.add_parser("prepare"); p.add_argument("--input",required=True); p.add_argument("--output",required=True); p.add_argument("--ollama",action="store_true"); p.add_argument("--model",default="qwen3:8b"); p.add_argument("--github-token",default=""); p.add_argument("--github-ref",default="")
    v=sp.add_parser("validate"); v.add_argument("--input",required=True)
    i=sp.add_parser("verify-existing-identity")
    i.add_argument("--job",required=True)
    i.add_argument("--output",required=True)
    i.add_argument("--cdp-url",required=True,help="CDP endpoint for one already-authenticated Partner Center tab")
    i.add_argument("--selector-map",default=str(Path(__file__).resolve().parents[1]/"docs"/"PARTNER_CENTER_MAP.json"))
    i.add_argument("--evidence-dir",default="partner-center-evidence")
    n=sp.add_parser("night-run"); n.add_argument("--queue",required=True); n.add_argument("--json-report",required=True); n.add_argument("--markdown-report",required=True)
    n.add_argument("--execution-mode",choices=("dry_run","live"),default="dry_run")
    n.add_argument("--confirm-live-draft",action="store_true",help="Explicitly authorize Partner Center package upload and Save draft only")
    n.add_argument("--cdp-url",default="",help="CDP endpoint for the already-authenticated browser")
    n.add_argument("--selector-map",default=str(Path(__file__).resolve().parents[1]/"docs"/"PARTNER_CENTER_MAP.json"))
    n.add_argument("--evidence-dir",default="partner-center-evidence")
    a=ap.parse_args()
    if a.cmd=="prepare":
        x=ProductInput.load(a.input); apply_fixed_rules(x); ctx=fetch_context(x.repository,a.github_token,a.github_ref) if a.github_token and x.repository else ""
        if a.ollama: complete_product(x,ctx,model=a.model)
        x.save(a.output); print(a.output); return
    if a.cmd=="validate":
        fs=validate_product(ProductInput.load(a.input)); [print(f"[{f.severity.value.upper()}] {f.code}: {f.message}") for f in fs]; raise SystemExit(2 if any(f.severity.value in {"hold","fatal"} for f in fs) else 0)
    if a.cmd=="verify-existing-identity":
        raw=json.loads(Path(a.job).read_text(encoding="utf-8"))
        if raw.get("schema_version")!="existing-store-identity-reverify/1":
            raise SystemExit("unsupported identity reverify job schema")
        expected=raw.get("expected") or {}
        permissions=raw.get("permissions") or {}
        if permissions != {
            "read_partner_center": True,
            "create_product": False,
            "start_submission": False,
            "upload_package": False,
            "edit_pricing": False,
            "submit_certification": False,
            "publish": False,
        }:
            raise SystemExit("identity reverify job permissions are not read-only")
        with LivePlaywrightConnection(a.cdp_url,a.selector_map,a.evidence_dir) as port:
            verified=port.verify_existing_identity_values(
                product_name=str(expected.get("product_name") or ""),
                store_product_id=str(expected.get("store_id") or ""),
                identity_name=str(expected.get("identity_name") or ""),
                identity_publisher=str(expected.get("publisher") or ""),
                package_family_name=str(expected.get("package_family_name") or ""),
                package_sid=str(expected.get("package_sid") or ""),
            )
        receipt={
            "schema_version":"existing-store-identity-reverify-receipt/1",
            "status":verified["status"],
            "partner_center_reverified":True,
            "source_sha":raw.get("source_sha"),
            "package_sha256":raw.get("package_sha256"),
            "store_id":verified["store_product_id"],
            "identity_name":verified["identity_name"],
            "publisher":verified["identity_publisher"],
            "package_family_name":verified["package_family_name"],
            "package_sid":verified["package_sid"],
            "matched_fields":verified["matched_fields"],
            "identity_url":verified["identity_url"],
            "created_or_reserved_product":False,
            "submission_started":False,
            "package_uploaded":False,
            "pricing_changed":False,
            "submitted":False,
            "published":False,
        }
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":receipt["status"],"output":a.output},ensure_ascii=False))
        return
    raw=json.loads(Path(a.queue).read_text(encoding="utf-8")); products=[ProductInput.from_dict(x) for x in raw]
    if a.execution_mode=="live":
        if not a.confirm_live_draft:
            ap.error("live mode requires --confirm-live-draft at action time")
        if not a.cdp_url:
            ap.error("live mode requires --cdp-url for an already-authenticated browser")
        with LivePlaywrightConnection(a.cdp_url,a.selector_map,a.evidence_dir) as port:
            r=run_queue(products,LiveDraftWorkflow(port),QueuePolicy())
    else:
        r=run_queue(products,dryrun_uploader,QueuePolicy())
    Path(a.json_report).write_text(json.dumps(r.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8"); Path(a.markdown_report).write_text(render_markdown(r),encoding="utf-8"); print(json.dumps(r.to_dict(),ensure_ascii=False,indent=2))
if __name__=="__main__": main()
