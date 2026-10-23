"""Scan intended Git files for common secrets and locked PyPI versions via OSV.

Uses network only for public package names/versions; never sends repository
content. Nonzero on findings, network failure or incomplete vulnerability data.
This bounded scan is not a guarantee that every secret/CVE is detectable.
"""
import json
from pathlib import Path
import re
import subprocess
import tomllib
import urllib.request

REPO=Path(__file__).resolve().parents[1]
PATTERNS=[rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
          rb"gh[pousr]_[A-Za-z0-9]{36,}",rb"github_pat_[A-Za-z0-9_]{70,}",
          rb"sk-proj-[A-Za-z0-9_-]{40,}"]


def secret_findings(path, data):
    name=path.name.lower()
    return (name in {".env","auth.json","credentials.json"}
            or name.endswith((".pem",".p12",".pfx",".key"))
            or any(re.search(pattern,data) for pattern in PATTERNS))


def dependency_findings(packages, response):
    results=response.get("results")
    if not isinstance(results,list) or len(results)!=len(packages):
        raise ValueError("Incomplete OSV response")
    findings=[]
    for package,result in zip(packages,results):
        if not isinstance(result,dict) or set(result)-{"vulns"}:
            raise ValueError("Unexpected OSV result")
        vulns=result.get("vulns",[])
        if not isinstance(vulns,list): raise ValueError("Invalid OSV vulnerabilities")
        for vuln in vulns:
            findings.append(f"{package['name']} {package['version']}: {vuln['id']}")
    return findings


def main():
    try:
        listed=subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard"],cwd=REPO)
        paths=sorted(set(listed.decode("utf-8").split("\0"))-{ "" })
        findings=[]
        for value in paths:
            path=REPO/value
            if not path.resolve().is_relative_to(REPO.resolve()): raise ValueError("Git path escapes repository")
            if secret_findings(path,path.read_bytes()): findings.append(f"Possible secret: {value}")
        packages=[p for p in tomllib.loads((REPO/"uv.lock").read_text(encoding="utf-8"))["package"] if "registry" in p.get("source",{})]
        if not packages: raise ValueError("No locked dependencies to audit")
        payload={"queries":[{"package":{"name":p["name"],"ecosystem":"PyPI"},"version":p["version"]} for p in packages]}
        request=urllib.request.Request("https://api.osv.dev/v1/querybatch",json.dumps(payload).encode(),{"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(request,timeout=45) as response: data=json.load(response)
        findings+=dependency_findings(packages,data)
        if findings: raise ValueError("\n".join(findings))
        print(f"PASS: {len(paths)} intended Git files; {len(packages)} locked PyPI packages; no detected secrets or OSV advisories")
        print("Scope: bounded patterns and OSV package/version records at execution time")
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__=="__main__":
    raise SystemExit(main())
