"""One-shot script: create + activate the notify-email-on-case-created
workflow in n8n via the Public REST API. Idempotent-ish: re-running
will create a second copy unless you delete the first manually.
"""
import json
import ssl
import sys
import urllib.error
import urllib.request
import uuid


def main() -> None:
    api_key = None
    with open("backend/.env", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("N8N_API_KEY="):
                api_key = line.strip().split("=", 1)[1]
                break
    if not api_key:
        sys.exit("N8N_API_KEY not found in backend/.env")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    webhook_id = str(uuid.uuid4())
    set_id = str(uuid.uuid4())
    email_id = str(uuid.uuid4())
    callback_if_id = str(uuid.uuid4())
    callback_id = str(uuid.uuid4())
    webhook_path_uuid = str(uuid.uuid4())

    # Email body. Each line uses single-quoted strings so n8n template
    # expressions ($json.x) are not eaten by Python f-strings.
    html_body = (
        '<html><body style="font-family: -apple-system, sans-serif;">\n'
        '<h2 style="color:#1f2937;">[CMS] Nuevo caso creado</h2>\n'
        '<table cellpadding="6" cellspacing="0" border="0" '
        'style="border-collapse:collapse;">\n'
        "<tr><td><b>Numero:</b></td><td>{{ $json.case_number }}</td></tr>\n"
        "<tr><td><b>Titulo:</b></td><td>{{ $json.title }}</td></tr>\n"
        "<tr><td><b>Tipo:</b></td><td>{{ $json.case_type }}</td></tr>\n"
        "<tr><td><b>Catalogo:</b></td>"
        "<td>{{ $json.service_catalog_label }}</td></tr>\n"
        "<tr><td><b>Creado:</b></td><td>{{ $json.created_at }}</td></tr>\n"
        "</table>\n"
        '<p>Ver detalle: <a href="{{ $json.cms_case_url }}">'
        "{{ $json.cms_case_url }}</a></p>\n"
        '<hr><p style="color:#6b7280;font-size:12px;">'
        "Email automatico generado por n8n workflow "
        "`notify-email-on-case-created`. "
        "Disparado por regla de notificacion de CMS.</p>\n"
        "</body></html>"
    )

    normalize_js = (
        "// Normaliza el payload (acepta tanto el shape CMS-real como "
        "un smoke test con curl).\n"
        "// Resuelve defaults para que el Email node nunca reciba "
        "undefined.\n"
        "const body = $json.body || $json;\n"
        "return {\n"
        "  case_id: body.case_id || 'TEST-' + Date.now(),\n"
        "  case_number: body.case_number || 'TEST-001',\n"
        "  case_type: body.case_type || 'request',\n"
        "  title: body.title || '(sin titulo)',\n"
        "  service_catalog_label: body.service_catalog_label\n"
        "    || (body.context && body.context.service_catalog_label)\n"
        "    || '(sin catalogo)',\n"
        "  recipient_email: body.recipient_email\n"
        "    || (body.context && body.context.recipient_email)\n"
        "    || 'inbox@example.com',\n"
        "  created_at: body.created_at || new Date().toISOString(),\n"
        "  cms_case_url: body.details_url\n"
        "    || ('https://cms.local/cases/' + "
        "(body.case_id || 'unknown')),\n"
        "  playbook_run_id: body.playbook_run_id || null,\n"
        "  callback_url: body.callback_url || null,\n"
        "  callback_jwt: body.callback_jwt || null,\n"
        "};"
    )

    callback_body = (
        "={\n"
        '  "playbook_run_id": "'
        "{{ $('Normalize payload').first().json.playbook_run_id }}"
        '",\n'
        '  "status": "completed",\n'
        '  "result": {\n'
        '    "email_sent_to": "'
        "{{ $('Normalize payload').first().json.recipient_email }}"
        '",\n'
        '    "subject": "[CMS] Nuevo caso #'
        "{{ $('Normalize payload').first().json.case_number }}"
        '",\n'
        '    "channel": "email"\n'
        "  }\n"
        "}"
    )

    workflow = {
        "name": "notify-email-on-case-created",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "notify-email-on-case-created",
                    "responseMode": "onReceived",
                    "options": {},
                },
                "id": webhook_id,
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [-200, 0],
                "webhookId": webhook_path_uuid,
            },
            {
                "parameters": {
                    "mode": "runOnceForEachItem",
                    "jsCode": normalize_js,
                },
                "id": set_id,
                "name": "Normalize payload",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [40, 0],
            },
            {
                "parameters": {
                    "fromEmail": "cms@example.com",
                    "toEmail": "={{ $json.recipient_email }}",
                    "subject": (
                        "=[CMS] Nuevo caso #{{ $json.case_number }} - "
                        "{{ $json.title }}"
                    ),
                    "emailFormat": "html",
                    "html": "=" + html_body,
                    "options": {},
                },
                "id": email_id,
                "name": "Send Email",
                "type": "n8n-nodes-base.emailSend",
                "typeVersion": 2.1,
                "position": [280, 0],
            },
            {
                "parameters": {
                    "conditions": {
                        "options": {
                            "caseSensitive": True,
                            "leftValue": "",
                            "typeValidation": "strict",
                        },
                        "conditions": [
                            {
                                "id": str(uuid.uuid4()),
                                "leftValue": (
                                    "={{ $('Normalize payload')."
                                    "first().json.callback_url }}"
                                ),
                                "rightValue": "",
                                "operator": {
                                    "type": "string",
                                    "operation": "notEmpty",
                                    "singleValue": True,
                                },
                            }
                        ],
                        "combinator": "and",
                    },
                    "options": {},
                },
                "id": callback_if_id,
                "name": "Has callback?",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [520, 0],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": (
                        "={{ $('Normalize payload')."
                        "first().json.callback_url }}"
                    ),
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {
                                "name": "Authorization",
                                "value": (
                                    "=Bearer {{ $('Normalize payload')."
                                    "first().json.callback_jwt }}"
                                ),
                            },
                            {
                                "name": "Content-Type",
                                "value": "application/json",
                            },
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": callback_body,
                    "options": {},
                },
                "id": callback_id,
                "name": "Callback to CMS",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [760, -100],
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{
                    "node": "Normalize payload",
                    "type": "main", "index": 0,
                }]]
            },
            "Normalize payload": {
                "main": [[{
                    "node": "Send Email",
                    "type": "main", "index": 0,
                }]]
            },
            "Send Email": {
                "main": [[{
                    "node": "Has callback?",
                    "type": "main", "index": 0,
                }]]
            },
            "Has callback?": {
                "main": [
                    [{
                        "node": "Callback to CMS",
                        "type": "main", "index": 0,
                    }],
                    [],
                ]
            },
        },
        "settings": {"executionOrder": "v1"},
    }

    req = urllib.request.Request(
        "https://cms.local/n8n-api/v1/workflows",
        data=json.dumps(workflow).encode(),
        headers={
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            created = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        sys.exit(f"CREATE HTTP {exc.code}: {exc.read().decode()[:600]}")

    wf_id = created["id"]
    print("Workflow creado:")
    print(f"  id     : {wf_id}")
    print(f"  name   : {created['name']}")
    print(f"  active : {created['active']}")
    print(f"  nodes  : {len(created['nodes'])}")
    print(
        "  webhook URL: "
        "https://cms.local/webhook/notify-email-on-case-created"
    )
    print()
    print(
        "NOTA: el workflow NO se activa todavia. "
        "El Email Send node necesita una credencial SMTP."
    )
    print("Pasos siguientes en n8n UI:")
    print("  1. Credentials -> Add credential -> SMTP")
    print("  2. Pega host/port/user/pass de Mailtrap sandbox")
    print("  3. Abre el workflow, click Send Email, asigna la credential")
    print("  4. Toggle Active = ON")


if __name__ == "__main__":
    main()
