from __future__ import annotations
import argparse,json
from pathlib import Path
from .core import ProductInput,apply_fixed_rules,validate_product,run_queue,QueuePolicy,render_markdown,file_sha256
from .partner_center import dryrun_uploader
from .live_draft import (
    LiveDraftWorkflow,
    LivePlaywrightConnection,
    UNKNOWN_PARTNER_CENTER_STATE,
    reconcile_ambiguous_initial_submission,
)
from .github_context import fetch_context
from .ollama import complete_product


def _nonblank_path(value: str) -> str:
    if not str(value or "").strip():
        raise argparse.ArgumentTypeError("path is empty; use the local runner to initialize its paths")
    return value


def _load_queue(path_value: str) -> list[ProductInput]:
    value = str(path_value or "").strip()
    if not value:
        raise ValueError("queue path is empty; initialize it with scripts/run_local_store_upload.ps1")
    path = Path(value).expanduser()
    if not path.is_file():
        raise ValueError(f"queue file does not exist or is not a file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"queue file is unreadable or invalid JSON: {path}") from exc
    if not isinstance(raw, list) or not raw:
        raise ValueError("queue must be a non-empty JSON array of ProductInput objects")
    if any(not isinstance(item, dict) for item in raw):
        raise ValueError("every queue item must be a ProductInput JSON object")
    try:
        products = [ProductInput.from_dict(item) for item in raw]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("queue contains an invalid ProductInput object") from exc
    product_ids = [p.store_product_id.strip() for p in products]
    if any(not item for item in product_ids):
        raise ValueError("every queue item must have a Store Product ID")
    if len(set(product_ids)) != len(product_ids):
        raise ValueError("queue contains a duplicate Store Product ID; split products into separate runs")
    for product in products:
        if not product.draft_id.strip():
            raise ValueError(f"existing Draft ID is required for {product.product_name or product.store_product_id}")
    return products


def verify_live_report_payload(report: dict, product: ProductInput) -> dict:
    """Fail closed unless one live result proves the exact existing Draft and package.

    QueueReport.to_dict() flattens ProductResult.details into each result object.
    This verifier intentionally reads only that canonical top-level shape.
    """

    if not isinstance(report, dict) or report.get("schema_version") != 2:
        raise ValueError("unsupported or malformed QueueReport schema")
    if report.get("stopped_early") is not False:
        raise ValueError("QueueReport indicates an early stop or omits stopped_early")
    results = report.get("results")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError("live report must contain exactly one result object")
    summary = report.get("summary")
    if not isinstance(summary, dict) or summary.get("mode") != "single" or summary.get("total") != 1:
        raise ValueError("live report summary does not describe exactly one product")

    result = results[0]
    allowed_statuses = {
        "DRAFT_SAVED",
        "PACKAGE_SAVED_STORE_DRAFT_REMAINING_SECTIONS_REQUIRED",
    }
    if result.get("status") not in allowed_statuses:
        raise ValueError(f"live result is not a verified Draft-save status: {result.get('status')!r}")

    package_path = Path(product.package_path).expanduser()
    if not product.package_path or not package_path.is_file():
        raise ValueError("the original local package is missing after the upload attempt")
    expected_sha = str(product.package_sha256 or "").strip().lower()
    security_sha = str(product.security_package_sha256 or "").strip().lower()
    actual_sha = file_sha256(package_path).lower()
    if not expected_sha or len(expected_sha) != 64 or expected_sha != security_sha:
        raise ValueError("ProductInput package SHA and security-confirmed SHA are missing or inconsistent")
    if actual_sha != expected_sha:
        raise ValueError("local package bytes changed during the upload attempt")

    expected_values = {
        "product_name": product.product_name,
        "product_id": product.store_product_id,
        "draft_id": product.draft_id,
        "package_filename": package_path.name,
        "source_sha": str(product.source_sha or "").lower(),
        "source_branch": product.source_branch,
        "submission_route": product.submission_route,
        "package_sha256": expected_sha,
        "immutable_package_sha256": expected_sha,
    }
    for key, expected in expected_values.items():
        observed = result.get(key)
        if key in {"package_sha256", "immutable_package_sha256", "source_sha"}:
            observed = str(observed or "").lower()
        if observed != expected:
            raise ValueError(f"live result binding mismatch for {key}")

    identity = result.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("live result is missing its package Identity binding")
    expected_identity = {
        "name": product.identity_name,
        "publisher": product.identity_publisher,
        "version": product.package_version,
    }
    if identity != expected_identity:
        raise ValueError("live result Identity/Publisher/Version does not match ProductInput")

    required_true = ("package_uploaded", "package_saved", "save_verified_after_reload")
    for flag in required_true:
        if result.get(flag) is not True:
            raise ValueError(f"live result does not explicitly prove {flag}=true")

    required_false = (
        "created_or_reserved_product",
        "submission_started",
        "start_submission_clicked",
        "start_update_clicked",
        "pricing_changed",
        "submitted",
        "certified",
        "published",
    )
    for flag in required_false:
        if result.get(flag) is not False:
            raise ValueError(f"live result must explicitly prove {flag}=false")

    return {
        "schema_version": "local-store-upload-verification/1",
        "status": "LIVE_DRAFT_RECEIPT_VERIFIED",
        "result_status": result["status"],
        "product_name": product.product_name,
        "product_id": product.store_product_id,
        "draft_id": product.draft_id,
        "package_filename": package_path.name,
        "package_sha256": expected_sha,
        "verified_fields": list(expected_values) + ["identity", *required_true, *required_false],
        "microsoft_independent_sha256_observed": False,
        "note": "The local SHA-256 binds the local package selected by this runner; Partner Center UI does not independently expose the uploaded binary digest.",
    }


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
    s=sp.add_parser("inspect-existing-submission-state")
    s.add_argument("--input",required=True,help="Prepared ProductInput JSON for one existing Store product")
    s.add_argument("--output",required=True,help="Read-only submission-state receipt JSON")
    s.add_argument("--cdp-url",required=True,help="CDP endpoint for one already-authenticated Partner Center tab")
    s.add_argument("--selector-map",default=str(Path(__file__).resolve().parents[1]/"docs"/"PARTNER_CENTER_MAP.json"))
    s.add_argument("--evidence-dir",default="partner-center-evidence")
    r=sp.add_parser("reconcile-initial-submission-attempt")
    r.add_argument("--input",required=True,help="Prepared ProductInput JSON")
    r.add_argument("--output",required=True,help="Read-only reconciliation receipt JSON")
    r.add_argument("--cdp-url",required=True,help="CDP endpoint for one already-authenticated Partner Center tab")
    r.add_argument("--selector-map",default=str(Path(__file__).resolve().parents[1]/"docs"/"PARTNER_CENTER_MAP.json"))
    r.add_argument("--evidence-dir",default="partner-center-evidence")
    d=sp.add_parser("start-initial-submission")
    d.add_argument("--input",required=True,help="Prepared ProductInput JSON")
    d.add_argument("--job",required=True,help="Owner-authorized initial-submission job JSON")
    d.add_argument("--output",required=True,help="Initial draft creation receipt JSON")
    d.add_argument("--cdp-url",required=True,help="CDP endpoint for one already-authenticated Partner Center tab")
    d.add_argument("--confirm-start-submission",action="store_true",help="Action-time approval for Start submission only")
    d.add_argument("--selector-map",default=str(Path(__file__).resolve().parents[1]/"docs"/"PARTNER_CENTER_MAP.json"))
    d.add_argument("--evidence-dir",default="partner-center-evidence")
    qv=sp.add_parser("verify-live-report",help="Verify one local live Draft receipt against ProductInput")
    qv.add_argument("--report",required=True,type=_nonblank_path)
    qv.add_argument("--input",required=True,type=_nonblank_path)
    qv.add_argument("--output",required=True,type=_nonblank_path)
    n=sp.add_parser("night-run"); n.add_argument("--queue",required=True,type=_nonblank_path); n.add_argument("--json-report",required=True,type=_nonblank_path); n.add_argument("--markdown-report",required=True,type=_nonblank_path)
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
    if a.cmd=="verify-live-report":
        try:
            product=ProductInput.load(a.input)
            report=json.loads(Path(a.report).read_text(encoding="utf-8-sig"))
            receipt=verify_live_report_payload(report,product)
            output=Path(a.output)
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open("x",encoding="utf-8") as stream:
                json.dump(receipt,stream,ensure_ascii=False,indent=2)
                stream.write("\\n")
        except (OSError,UnicodeError,ValueError,TypeError) as exc:
            ap.error(f"live report verification failed: {exc}")
        print(json.dumps(receipt,ensure_ascii=False,indent=2))
        return
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
    if a.cmd=="inspect-existing-submission-state":
        product=ProductInput.load(a.input)
        if not all(str(getattr(product,name,"") or "").strip() for name in (
            "product_name","store_product_id","identity_name","identity_publisher"
        )):
            raise SystemExit("submission-state inspection requires existing product and exact identity values")
        with LivePlaywrightConnection(a.cdp_url,a.selector_map,a.evidence_dir) as port:
            result=port.inspect_existing_product_submission_state(product)
        kind_matches=(
            not result.required_submission_kind
            or product.submission_kind==result.required_submission_kind
        )
        status=(
            "HOLD_UNKNOWN_SUBMISSION_STATE"
            if result.state==UNKNOWN_PARTNER_CENTER_STATE
            else "HOLD_SUBMISSION_KIND_MISMATCH"
            if not kind_matches
            else "READ_ONLY_SUBMISSION_STATE_CLASSIFIED"
        )
        receipt={
            "schema_version":"existing-product-submission-state-receipt/1",
            "status":status,
            "submission_state":result.state,
            "required_submission_kind":result.required_submission_kind,
            "current_submission_kind":product.submission_kind,
            "submission_kind_matches":kind_matches,
            "hold_code":result.hold_code,
            "store_id":product.store_product_id,
            "draft_id":result.draft_id,
            "draft_url":result.draft_url,
            "created_or_reserved_product":False,
            "submission_started":False,
            "start_submission_clicked":False,
            "start_update_clicked":False,
            "package_uploaded":False,
            "pricing_changed":False,
            "submitted":False,
            "published":False,
        }
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":status,"submission_state":result.state,"output":a.output},ensure_ascii=False))
        return
    if a.cmd=="reconcile-initial-submission-attempt":
        product=ProductInput.load(a.input)
        if not all(str(getattr(product,name,"") or "").strip() for name in (
            "product_name","store_product_id","identity_name","identity_publisher"
        )):
            raise SystemExit("reconciliation requires existing product and exact identity values")
        with LivePlaywrightConnection(a.cdp_url,a.selector_map,a.evidence_dir) as port:
            result=port.inspect_existing_product_submission_state(product)
        status,retry_candidate=reconcile_ambiguous_initial_submission(result)
        receipt={
            "schema_version":"existing-store-initial-submission-reconcile-receipt/1",
            "status":status,
            "submission_state":result.state,
            "store_id":product.store_product_id,
            "draft_id":result.draft_id,
            "draft_url":result.draft_url,
            "retry_candidate":retry_candidate,
            "retry_authorized":False,
            "write_performed":False,
            "start_submission_clicked":False,
            "package_uploaded":False,
            "pricing_changed":False,
            "submitted":False,
            "published":False,
        }
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":status,"submission_state":result.state,"retry_candidate":retry_candidate,"output":a.output},ensure_ascii=False))
        return
    if a.cmd=="start-initial-submission":
        if not a.confirm_start_submission:
            ap.error("start-initial-submission requires --confirm-start-submission at action time")
        raw_input=json.loads(Path(a.input).read_text(encoding="utf-8"))
        if raw_input.get("schema_version")=="windows-all-auto/store-automator-input-1":
            product=ProductInput.from_dict(raw_input.get("windows_automator_input") or {})
        else:
            product=ProductInput.from_dict(raw_input)
        job=json.loads(Path(a.job).read_text(encoding="utf-8"))
        if job.get("schema_version")!="existing-store-initial-submission-start/1":
            raise SystemExit("unsupported initial submission job schema")
        expected=job.get("expected") or {}
        permissions=job.get("permissions") or {}
        exact_permissions={
            "read_partner_center":True,
            "create_product":False,
            "start_submission":True,
            "upload_package":False,
            "edit_pricing":False,
            "submit_certification":False,
            "publish":False,
        }
        if permissions!=exact_permissions:
            raise SystemExit("initial submission job permissions are not exact/safe")
        exact={
            "store_id":product.store_product_id,
            "source_sha":product.source_sha,
            "package_sha256":product.package_sha256,
            "submission_kind":product.submission_kind,
        }
        if any(str(expected.get(k) or "")!=str(v or "") for k,v in exact.items()):
            raise SystemExit("initial submission job does not match prepared product input")
        if expected.get("submission_state")!="EXISTING_PRODUCT_INITIAL_SUBMISSION":
            raise SystemExit("initial submission job is not bound to verified initial state")
        if job.get("owner_approved") is not True:
            raise SystemExit("initial submission job is not owner-approved")
        with LivePlaywrightConnection(a.cdp_url,a.selector_map,a.evidence_dir) as port:
            context=port.start_initial_submission_draft(product)
        receipt={
            "schema_version":"existing-store-initial-submission-start-receipt/1",
            "status":"INITIAL_SUBMISSION_DRAFT_CREATED",
            "store_id":product.store_product_id,
            "source_sha":product.source_sha,
            "package_sha256":product.package_sha256,
            "submission_kind":product.submission_kind,
            "draft_id":context.draft_id,
            "draft_url":context.draft_url,
            "created_or_reserved_product":False,
            "submission_started":True,
            "start_submission_clicked":True,
            "start_update_clicked":False,
            "package_uploaded":False,
            "pricing_changed":False,
            "submitted":False,
            "published":False,
        }
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":receipt["status"],"draft_id":context.draft_id,"output":a.output},ensure_ascii=False))
        return
    try:
        products=_load_queue(a.queue)
    except ValueError as exc:
        ap.error(str(exc))
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
