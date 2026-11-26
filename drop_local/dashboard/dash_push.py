"""dash_push r2: keep the standalone dashboard (Cloudflare Pages) live from the trading box, outbound HTTPS only.

Runs every minute as SYSTEM (task QuantForge-DashPush, installed once by the owner). Stdlib only (Python 3.14 on the box,
no node/wrangler there). One tick:
  1. setup, once and idempotent: KV namespace `quant-feed`, Pages project, FEED_KV bound to production.
  2. deploy the site when the package (or the worker, or the binding) changed, or every 2 h while KV is unusable
     (the 2 h redeploy carries a fresh feed.static.json, which is the no-KV fallback).
  3. write the feed to KV key `feed` when it changed, at most once per 90 s and at most 900 writes per UTC day
     (free tier is 1,000), then read it back through the public URL and record build -> visible latency.
Secrets: the token and account id are read from STATE\\cf_token.txt / STATE\\cf_account.txt when present (admin/SYSTEM-only),
else from machine env (CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID), and are never logged. (r2) Error text carries the
method and an endpoint shape only: the account id, the KV namespace id and every other hex id are replaced by <id>. The slug (48 hex, generated once) lives only in STATE\\slug.txt (admin/SYSTEM-only) and in the deployed worker.
The public report (REPORT) carries no slug, no URL, no account id. The URL is in STATE\\url.txt for the owner.
A feed is refused (never pushed) if it holds anything shaped like a credential, a login, a host or an IP address.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

API = 'https://api.cloudflare.com/client/v4'
STATE = Path(os.environ.get('DASH_STATE', r'C:\ProgramData\QuantBox\dash'))
SITE = Path(os.environ.get('DASH_SITE', r'C:\opt\bridge\quant\drop_local\dashboard\site'))
FEEDS = [Path(p) for p in os.environ.get('DASH_FEEDS', r'C:\opt\quant\desks\mt5\reports\DASHBOARD_FEED.json;'
                                          r'C:\opt\bridge\quant\drop_local\dashboard\feed.json').split(';') if p]
REPORT = Path(os.environ.get('DASH_REPORT', r'C:\opt\quant\desks\mt5\reports\DASHBOARD_PUSH.json'))
PROJECT = os.environ.get('DASH_PROJECT', 'quantdesk-site')
KV_TITLE = 'quant-feed'
KV_MIN_GAP_S = 90
KV_DAY_CAP = 900
REDEPLOY_NO_KV_S = 2 * 3600
DEPLOY_MONTH_CAP = 400          # free direct-upload cap is 500/month
COMPAT_DATE = '2024-09-23'
JOURNAL_MAX = 5_000_000

# Anything shaped like these in a feed means the feed builder leaked something: refuse the push, never redact.
_BAD_KEYS = re.compile(r'^(login|password|passwd|token|api_?key|secret|server|host|hostname|ip|account_?id|investor)$', re.IGNORECASE)
_BAD_VALS = [re.compile(p) for p in (r'\b\d{1,3}(?:\.\d{1,3}){3}\b', r'glpat-', r'ghp_', r'github_pat_', r'sk-[A-Za-z0-9]{16}',
                                     r'(?i)bearer\s+[a-z0-9]', r'(?i)\bpassword\b', r'[A-Za-z0-9_-]{40,}')]


def now() -> float:
    return time.time()


def iso(t: float | None = None) -> str:
    return dt.datetime.fromtimestamp(now() if t is None else t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class CfError(RuntimeError):
    pass


_HEXID = re.compile(r'[0-9a-fA-F]{16,}')


def endpoint(path: str) -> str:
    """(r2, Audit F1) the shape of an API path with every id removed: safe for the public report."""
    p = re.sub(r'^/accounts/[^/]+', '/accounts/<id>', path.split('?')[0])
    p = re.sub(r'/namespaces/[^/]+', '/namespaces/<id>', p)
    return _HEXID.sub('<id>', p)


class Cf:
    """Minimal Cloudflare v4 client. `send` is replaceable for tests. Never puts the token in an exception."""

    def __init__(self, token: str, account: str, send: Any = None):
        self._token, self.account = token, account
        self._send = send or self._urlopen

    @staticmethod
    def _urlopen(method, url, headers, body):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def call(self, method, path, *, json_body=None, raw=None, ctype=None, bearer=None, base=API, ok_404=False):
        headers = {'Authorization': f'Bearer {bearer or self._token}', 'User-Agent': 'quant-dash-push/1'}
        body = None
        if json_body is not None:
            body, headers['Content-Type'] = json.dumps(json_body).encode(), 'application/json'
        elif raw is not None:
            body, headers['Content-Type'] = raw, ctype or 'application/octet-stream'
        status, data = self._send(method, base + path, headers, body)
        if ok_404 and status == 404:
            return None
        try:
            doc = json.loads(data or b'{}')
        except ValueError:
            doc = {}
        if status >= 400 or (isinstance(doc, dict) and doc.get('success') is False):
            errs = doc.get('errors') if isinstance(doc, dict) else None
            msg = '; '.join(f"{e.get('code')} {e.get('message')}" for e in errs or [] if isinstance(e, dict))[:300]
            msg = _HEXID.sub('<id>', msg.replace(self._token, '***').replace(self.account, '<id>'))
            raise CfError(f'{method} {endpoint(path)} -> {status} {msg}')
        return doc.get('result') if isinstance(doc, dict) else doc

    def acct(self, path):
        return f'/accounts/{self.account}{path}'


# ---------------------------------------------------------------- state

def load_state() -> dict:
    try:
        return json.loads((STATE / 'state.json').read_text())
    except (OSError, ValueError):
        return {}


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True))
    os.replace(tmp, path)


def slug() -> str:
    p = STATE / 'slug.txt'
    if p.exists():
        s = p.read_text().strip()
        if re.fullmatch(r'[0-9a-f]{48}', s):
            return s
        raise SystemExit('slug.txt is present but malformed; refusing to mint a new permanent link')
    s = secrets.token_hex(24)
    STATE.mkdir(parents=True, exist_ok=True)
    p.write_text(s)
    return s


# ---------------------------------------------------------------- feed

def feed_problems(obj, path='') -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _BAD_KEYS.match(str(k)):
                out.append(f'key {path}/{k}')
            out += feed_problems(v, f'{path}/{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += feed_problems(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        for rx in _BAD_VALS:
            if rx.search(obj):
                out.append(f'value at {path} matches {rx.pattern[:20]}')
                break
    return out


def pick_feed() -> tuple[bytes | None, dict]:
    """Newest valid schema-1 feed by built_at. Returns (bytes, info). Info never holds feed content."""
    best: tuple[bytes, str, str] | None = None
    info: dict[str, Any] = {'candidates': []}
    for p in FEEDS:
        c: dict[str, Any] = {'path': str(p)}
        try:
            raw = p.read_bytes()
            doc = json.loads(raw)
            if doc.get('schema') != 1 or not doc.get('built_at'):
                c['skip'] = 'not schema 1 / no built_at'
            elif bad := feed_problems(doc):
                c['skip'] = f'REFUSED: {len(bad)} credential/host-shaped fields, first {bad[0]}'
            else:
                c['built_at'] = doc['built_at']
                if best is None or doc['built_at'] > best[1]:
                    best = (raw, doc['built_at'], str(p))
        except FileNotFoundError:
            c['skip'] = 'absent'
        except (OSError, ValueError) as e:
            c['skip'] = f'unreadable: {type(e).__name__}'
        info['candidates'].append(c)
    if best is None:
        return None, info
    info.update(built_at=best[1], source=best[2])
    return best[0], info


# ---------------------------------------------------------------- site

def worker_js(sl: str) -> str:
    return """// Generated by dash_push. Serves only /robots.txt and /<slug>/...; everything else is 404.
const SLUG = '__SLUG_VALUE__';
const H = {'x-robots-tag': 'noindex, nofollow, noarchive', 'referrer-policy': 'no-referrer', 'cache-control': 'no-store',
           'x-content-type-options': 'nosniff'};
export default {
  async fetch(request, env) {
    const u = new URL(request.url), p = '/' + SLUG;
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('', {status: 405, headers: H});
    if (u.pathname === '/robots.txt') return withH(await env.ASSETS.fetch(request));
    if (u.pathname === p) return Response.redirect(u.origin + p + '/', 301);
    if (!u.pathname.startsWith(p + '/')) return new Response('Not found', {status: 404, headers: H});
    if (u.pathname === p + '/feed.json') {
      const h = Object.assign({'content-type': 'application/json'}, H);
      if (env.FEED_KV) { const v = await env.FEED_KV.get('feed'); if (v) return new Response(v, {headers: h}); }
      const r = await env.ASSETS.fetch(new URL(p + '/feed.static.json', u.origin));
      return r.ok ? new Response(r.body, {headers: h}) : new Response('{}', {status: 404, headers: h});
    }
    return withH(await env.ASSETS.fetch(request));
  }
};
function withH(r) { const n = new Response(r.body, r); for (const k in H) n.headers.set(k, H[k]); return n; }
""".replace('__SLUG_VALUE__', sl)


def assets(sl: str, feed: bytes | None) -> dict[str, bytes]:
    """Published path -> bytes. The page and its static fallback feed live under /<slug>/; root has 404 + robots."""
    if not (SITE / 'index.html').is_file():
        raise SystemExit(f'site package missing: {SITE}\\index.html')
    out = {f'/{sl}/index.html': (SITE / 'index.html').read_bytes()}
    for name in ('404.html', 'robots.txt'):
        if (SITE / name).is_file():
            out['/' + name] = (SITE / name).read_bytes()
    static = feed if feed is not None else ((SITE / 'feed.static.json').read_bytes() if (SITE / 'feed.static.json').is_file() else b'{}')
    out[f'/{sl}/feed.static.json'] = static
    return out


def ahash(path: str, data: bytes) -> str:
    # content-addressed key; extension folded in so identical bytes with different types do not collide
    return hashlib.sha256(base64.b64encode(data) + Path(path).suffix.encode()).hexdigest()[:32]


def multipart(fields: dict[str, tuple[str | None, str, bytes]]) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    parts = []
    for name, (fname, ctype, data) in fields.items():
        disp = f'form-data; name="{name}"' + (f'; filename="{fname}"' if fname else '')
        parts.append(f'--{b}\r\nContent-Disposition: {disp}\r\nContent-Type: {ctype}\r\n\r\n'.encode() + data + b'\r\n')
    return b''.join(parts) + f'--{b}--\r\n'.encode(), f'multipart/form-data; boundary={b}'


def deploy(cf: Cf, sl: str, files: dict[str, bytes]) -> str:
    jwt = cf.call('GET', cf.acct(f'/pages/projects/{PROJECT}/upload-token'))['jwt']
    manifest = {p: ahash(p, d) for p, d in files.items()}
    by_hash = {manifest[p]: (p, d) for p, d in files.items()}
    missing = cf.call('POST', '/pages/assets/check-missing', json_body={'hashes': list(by_hash)}, bearer=jwt) or []
    if missing:
        cf.call('POST', '/pages/assets/upload', bearer=jwt, json_body=[
            {'key': h, 'value': base64.b64encode(by_hash[h][1]).decode(), 'base64': True,
             'metadata': {'contentType': mimetypes.guess_type(by_hash[h][0])[0] or 'application/octet-stream'}}
            for h in missing])
    cf.call('POST', '/pages/assets/upsert-hashes', json_body={'hashes': list(by_hash)}, bearer=jwt)
    fields = {'manifest': (None, 'application/json', json.dumps(manifest).encode()),
              'branch': (None, 'text/plain', b'main'),
              '_worker.js': ('_worker.js', 'application/javascript+module', worker_js(sl).encode())}
    if (SITE / '_headers').is_file():
        fields['_headers'] = ('_headers', 'text/plain', (SITE / '_headers').read_bytes())
    body, ctype = multipart(fields)
    res = cf.call('POST', cf.acct(f'/pages/projects/{PROJECT}/deployments'), raw=body, ctype=ctype)
    return (res or {}).get('id', '?')


# ---------------------------------------------------------------- setup

def ensure_setup(cf: Cf, st: dict) -> None:
    if not st.get('kv_ns'):
        found = None
        page = 1
        while found is None:
            rows = cf.call('GET', cf.acct(f'/storage/kv/namespaces?per_page=100&page={page}')) or []
            found = next((r['id'] for r in rows if r.get('title') == KV_TITLE), None)
            if len(rows) < 100:
                break
            page += 1
        st['kv_ns'] = found or cf.call('POST', cf.acct('/storage/kv/namespaces'), json_body={'title': KV_TITLE})['id']
    proj = cf.call('GET', cf.acct(f'/pages/projects/{PROJECT}'), ok_404=True)
    if proj is None:
        proj = cf.call('POST', cf.acct('/pages/projects'), json_body={'name': PROJECT, 'production_branch': 'main'})
    st['subdomain'] = proj.get('subdomain') or f'{PROJECT}.pages.dev'
    prod = ((proj.get('deployment_configs') or {}).get('production') or {})
    bound = ((prod.get('kv_namespaces') or {}).get('FEED_KV') or {}).get('namespace_id')
    if bound != st['kv_ns']:
        cf.call('PATCH', cf.acct(f'/pages/projects/{PROJECT}'), json_body={'deployment_configs': {'production': {
            'kv_namespaces': {'FEED_KV': {'namespace_id': st['kv_ns']}}, 'compatibility_date': COMPAT_DATE}}})
        st['binding_changed_at'] = iso()


def fetch_public(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'quant-dash-push/1',
                                                                         'Cache-Control': 'no-cache'}), timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except OSError:
        return 0, b''


# ---------------------------------------------------------------- tick

def tick(cf: Cf, *, fetch: Any = fetch_public) -> dict[str, Any]:
    st = load_state()
    sl = slug()
    rep: dict = {'at': iso(), 'project': PROJECT, 'ok': True, 'steps': []}
    t0 = now()
    ensure_setup(cf, st)
    url = f"https://{st['subdomain']}/{sl}/"
    (STATE / 'url.txt').write_text(url + '\n')

    feed, finfo = pick_feed()
    rep['feed'] = finfo
    files = assets(sl, None)            # site hash excludes the feed so a feed change alone never burns a deployment
    site_hash = hashlib.sha256(json.dumps({p: ahash(p, d) for p, d in files.items()}, sort_keys=True).encode()
                               + worker_js(sl).encode() + str(st.get('binding_changed_at')).encode()).hexdigest()
    month = iso()[:7]
    if st.get('deploy_month') != month:
        st['deploy_month'], st['deploys_this_month'] = month, 0
    kv_ok = st.get('kv_ok', True)
    due_site = site_hash != st.get('site_hash')
    due_fallback = (not kv_ok) and feed is not None and now() - st.get('last_deploy_t', 0) >= REDEPLOY_NO_KV_S
    if (due_site or due_fallback) and st['deploys_this_month'] < DEPLOY_MONTH_CAP:
        dep = deploy(cf, sl, assets(sl, feed))
        st.update(site_hash=site_hash, last_deploy_t=now(), last_deploy_at=iso(), last_deploy_id=dep)
        st['deploys_this_month'] += 1
        rep['steps'].append(f"deployed ({'site changed' if due_site else '2 h no-KV fallback'})")
    elif due_site or due_fallback:
        rep['steps'].append(f'deploy due but monthly cap {DEPLOY_MONTH_CAP} reached')
        rep['ok'] = False

    day = iso()[:10]
    if st.get('kv_day') != day:
        st['kv_day'], st['kv_writes_today'] = day, 0
    if feed is None:
        rep['steps'].append('no valid feed: nothing written')
        rep['ok'] = False
    else:
        fh = hashlib.sha256(feed).hexdigest()
        if fh == st.get('kv_feed_hash'):
            rep['steps'].append('feed unchanged')
        elif now() - st.get('kv_last_t', 0) < KV_MIN_GAP_S:
            rep['steps'].append('feed changed; waiting for the 90 s gap')
        elif st['kv_writes_today'] >= KV_DAY_CAP:
            rep['steps'].append(f'feed changed; daily KV cap {KV_DAY_CAP} reached')
        else:
            try:
                cf.call('PUT', cf.acct(f"/storage/kv/namespaces/{st['kv_ns']}/values/feed"), raw=feed, ctype='text/plain')
                st.update(kv_feed_hash=fh, kv_last_t=now(), kv_last_at=iso(), kv_ok=True)
                st['kv_writes_today'] += 1
                rep['steps'].append('feed written to KV')
                status, body = fetch(url + 'feed.json')
                try:
                    seen = json.loads(body).get('built_at') if status == 200 else None
                except ValueError:
                    seen = None
                rep['visible'] = {'status': status, 'matches': seen == finfo['built_at'],
                                  'build_to_visible_s': round(now() - dt.datetime.strptime(finfo['built_at'], '%Y-%m-%dT%H:%M:%SZ')
                                                              .replace(tzinfo=dt.timezone.utc).timestamp())
                                  if seen == finfo['built_at'] else None}
            except CfError as e:
                st['kv_ok'] = False
                rep['steps'].append(f'KV write failed, 2 h redeploy fallback armed: {e}')
                rep['ok'] = False
    rep.update(kv_writes_today=st['kv_writes_today'], deploys_this_month=st['deploys_this_month'],
               last_deploy_at=st.get('last_deploy_at'), kv_last_at=st.get('kv_last_at'), kv_ok=st.get('kv_ok', True),
               tick_s=round(now() - t0, 2))
    save_json(STATE / 'state.json', st)
    return rep


def _secret(name: str, env: str) -> str | None:
    """(r2, Audit 5) an admin-only file in STATE wins over machine env, so moving the token off env is one admin step."""
    try:
        v = (STATE / name).read_text().strip()
        if v:
            return v
    except OSError:
        pass
    return os.environ.get(env) or None


def scrub(text: str, *secrets_: str | None) -> str:
    for v in secrets_:
        if v:
            text = text.replace(v, '<id>')
    return _HEXID.sub('<id>', text)


def main() -> int:
    token, account = _secret('cf_token.txt', 'CLOUDFLARE_API_TOKEN'), _secret('cf_account.txt', 'CLOUDFLARE_ACCOUNT_ID')
    rep: dict[str, Any]
    if not token or not account:
        rep = {'at': iso(), 'ok': False, 'steps': ['CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not in env: nothing done']}
    else:
        try:
            rep = tick(Cf(token, account))
        except (CfError, OSError, KeyError, SystemExit) as e:
            rep = {'at': iso(), 'ok': False, 'steps': [f'{type(e).__name__}: {scrub(str(e), token, account)[:300]}']}
        rep['steps'] = [scrub(x, token, account) for x in rep.get('steps', [])]
    save_json(REPORT, rep)
    STATE.mkdir(parents=True, exist_ok=True)
    jp = STATE / 'journal.jsonl'
    try:
        if jp.stat().st_size > JOURNAL_MAX:     # (r2) keep one rotated generation, ~3.5 days at one line a minute
            os.replace(jp, STATE / 'journal.1.jsonl')
    except OSError:
        pass
    with jp.open('a') as j:
        j.write(json.dumps(rep) + '\n')
    return 0 if rep.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
